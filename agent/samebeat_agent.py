#!/usr/bin/env python3
"""SameBeat Mac Agent.

读取 `media-control stream`，只跟踪 QQ 音乐官方客户端的播放状态，
在状态变化 / 心跳时上报给 samebeat-server 的 POST /ingest。

依据 docs/phase0-findings.md：
- 4.1 Now Playing 被其他 App 占用 → status=occluded（QQ 状态未知），
      其他 App 的任何媒体信息都不保存、不上传；最后已知的 QQ 状态放进 last_known 并标记 stale。
- 4.2 暂停事件不带进度 → 收到暂停的那一刻自己冻结进度。
- 4.3 旧缓存状态重放 → 只接受 timestamp 严格更新的进度信息。
- 4.4 contentItemIdentifier 不稳定 → 用 title/artist/album/duration 识别歌曲。
- 4.5 切歌瞬时抖动 → 事件安静 debounce_seconds 后才判断是否上报。

只用标准库；需要 Python 3.11+（tomllib）。
"""

from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
import tomllib
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path

QQ_BUNDLE = "com.tencent.QQMusicMac"
DEFAULT_CONFIG = Path.home() / ".config" / "samebeat" / "config.toml"
SEEK_THRESHOLD = 2.5  # 秒；实际进度与按上次上报外推的进度差超过它，视为拖进度 / 循环重播


def log(msg: str) -> None:
    print(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}", flush=True)


def valid_server_url(value: str) -> bool:
    if not value:
        return True
    try:
        u = urlsplit(value)
        port = u.port
        return bool(u.hostname) and not (u.username or u.password or u.query or u.fragment) and (
            u.scheme == "https" or (u.scheme == "http" and u.hostname in ("localhost", "127.0.0.1", "::1")))
    except ValueError:
        return False


# ---------------------------------------------------------------- 配置

class Config:
    def __init__(self, path: Path):
        self.path = path
        self.mtime = None
        self.server_url = ""
        self.token = ""
        self.sharing_enabled = True
        self.media_control = "/opt/homebrew/bin/media-control"
        self.debounce_seconds = 0.8
        self.heartbeat_seconds = 30.0

    def reload_if_changed(self) -> bool:
        """配置文件变了就重新读，返回是否有变化。读失败时保留旧配置。"""
        try:
            mtime = self.path.stat().st_mtime
        except FileNotFoundError:
            if self.mtime is None:
                raise
            return False
        if mtime == self.mtime:
            return False
        try:
            with open(self.path, "rb") as f:
                data = tomllib.load(f)
        except (OSError, tomllib.TOMLDecodeError) as e:
            log(f"配置读取失败，沿用旧配置: {e}")
            self.mtime = mtime
            return False
        server_url = str(data.get("server_url", "")).strip()
        if not valid_server_url(server_url):
            log("配置拒绝：server_url 必须为 HTTPS 或准确的本机 HTTP 地址，不能带凭据、查询或片段")
            self.mtime = mtime
            # Invalid configuration disables sharing, including on hot reload.
            self.sharing_enabled = False
            return True
        self.mtime = mtime
        self.server_url = server_url
        self.token = str(data.get("token", ""))
        self.sharing_enabled = bool(data.get("sharing_enabled", True))
        self.media_control = str(data.get("media_control", self.media_control))
        self.debounce_seconds = float(data.get("debounce_seconds", 0.8))
        self.heartbeat_seconds = float(data.get("heartbeat_seconds", 30))
        return True


# ---------------------------------------------------------------- 系统 Now Playing 镜像

class RawMirror:
    """按 media-control 的 diff 协议还原「系统当前 Now Playing」的完整状态。

    diff=false 整体替换；diff=true 只合并变化字段（值为 null 表示删除）。
    diff 事件不带 bundleIdentifier，属于当时占着 Now Playing 的那个 App，
    所以必须先还原完整状态，再判断它是不是 QQ 音乐。
    """

    def __init__(self):
        self.state: dict = {}

    def apply(self, msg: dict) -> dict | None:
        """返回本条事件实际带来的字段（delta）；非数据事件返回 None。"""
        if msg.get("type") != "data":
            return None
        payload = msg.get("payload") or {}
        if not msg.get("diff"):
            self.state = {k: v for k, v in payload.items() if v is not None}
            return dict(payload)
        for k, v in payload.items():
            if v is None:
                self.state.pop(k, None)
            else:
                self.state[k] = v
        return dict(payload)


# ---------------------------------------------------------------- QQ 音乐状态

def track_key(track: dict | None):
    if not track:
        return None
    return (track["title"], track["artist"], track["album"], track["duration"])


class QQTracker:
    """只保存 QQ 音乐的状态。其他 App 只影响 source，内容一律不留。"""

    def __init__(self):
        self.source: str | None = None  # "qq" / "other" / "none" / None(还没收到任何事件)
        self.track: dict | None = None
        self.playing: bool | None = None
        self.anchor_pos = 0.0           # anchor_t 时刻的进度（秒）
        self.anchor_t = 0.0             # epoch 秒
        self.last_source_ts = 0.0       # 已接受的最新进度时间（系统 timestamp 或暂停时刻）
        self.confirmed = False          # 当前进度是否来自 QQ 在本次可见期间的新鲜上报
        self.known = False              # 是否有任何可信的进度（哪怕是外推的估计值）
        self.hidden_at: float | None = None
        self.last_event_t = 0.0

    def position(self, now: float) -> float:
        pos = self.anchor_pos
        if self.playing:
            pos += now - self.anchor_t
        dur = (self.track or {}).get("duration") or 0
        if dur > 0:
            pos = min(pos, dur)
        return max(pos, 0.0)

    def on_event(self, raw: dict, delta: dict, now: float) -> None:
        self.last_event_t = now
        bundle = raw.get("bundleIdentifier")
        if bundle != QQ_BUNDLE:
            # 被其他 App 占用，或者当前没有任何 Now Playing
            if self.source == "qq":
                self.anchor_pos = self.position(now)
                self.anchor_t = now
                self.hidden_at = now
            self.source = "other" if raw else "none"
            return

        was_visible = self.source == "qq"
        self.source = "qq"
        self.hidden_at = None
        if not was_visible:
            self.confirmed = False

        new_track = None
        if raw.get("title"):
            new_track = {
                "title": raw.get("title"),
                "artist": raw.get("artist") or "",
                "album": raw.get("album") or "",
                "duration": (raw.get("durationMicros") or 0) / 1e6,
            }
        track_changed = new_track is not None and track_key(new_track) != track_key(self.track)
        if track_changed:
            self.track = new_track

        # 先处理播放/暂停，再处理进度：同一事件里若带着新鲜进度，以进度为准
        if "playing" in delta:
            playing = bool(delta["playing"])
            if playing != self.playing:
                self.anchor_pos = self.position(now)  # 4.2 暂停不带进度，按当下外推值冻结
                self.confirmed = False  # 冻结的是估计值，除非本事件提供新鲜进度
                self.anchor_t = now
                if self.playing is None:
                    pass  # 启动时的第一条状态，不是暂停事件
                elif not playing:
                    self.last_source_ts = max(self.last_source_ts, now)
                self.playing = playing
        elif self.playing is None and "playing" in raw:
            self.playing = bool(raw["playing"])

        if "elapsedTimeMicros" in delta and "timestampEpochMicros" in delta:
            ts = delta["timestampEpochMicros"] / 1e6
            if ts > self.last_source_ts or track_changed:
                self.anchor_pos = delta["elapsedTimeMicros"] / 1e6
                self.anchor_t = ts
                self.last_source_ts = max(self.last_source_ts, ts)
                self.confirmed = True
                self.known = True
            # 否则是旧缓存重放（4.3），进度不采纳
        elif track_changed:
            self.anchor_pos = 0.0
            self.anchor_t = now
            self.confirmed = False
            self.known = True

        # 刚变得可见（Agent 启动 / 从其他 App 切回）时处于暂停：QQ 暂停不报进度，
        # 缓存里的 elapsed 是更早某次上报的值，暂停在哪一秒无从得知
        if not was_visible and not self.playing:
            self.confirmed = False
            self.known = False

    def snapshot(self, now: float) -> dict | None:
        """当前应上报的状态；还不知道任何状态时返回 None。"""
        if self.source is None:
            return None
        t = self.track or {}
        if self.source == "qq":
            return {
                "status": "playing" if self.playing else "paused",
                "title": t.get("title"),
                "artist": t.get("artist"),
                "album": t.get("album"),
                "duration": t.get("duration"),
                # 进度无从得知时不给数字，避免被当成真实进度
                "position": round(self.position(now), 3) if self.known else None,
                "playing": bool(self.playing),
                "position_confirmed": self.confirmed and (not self.playing or abs(now - self.anchor_t) <= 0.5),
                "observed_at": round(now, 3),
            }
        snap = {
            # occluded: 被其他 App 占着，QQ 此刻状态未知；idle: 系统里没有任何 Now Playing
            "status": "occluded" if self.source == "other" else "idle",
            "title": None, "artist": None, "album": None, "duration": None,
            "position": None,
            "playing": None,
            "observed_at": round(now, 3),
        }
        if self.track:
            snap["last_known"] = {
                "stale": True,
                "title": t.get("title"),
                "artist": t.get("artist"),
                "album": t.get("album"),
                "duration": t.get("duration"),
                "position": round(self.anchor_pos, 3),
                "playing": self.playing,
                "observed_at": round(self.hidden_at or self.anchor_t, 3),
            }
        return snap


# ---------------------------------------------------------------- 何时上报

class Reporter:
    """事件安静 debounce 秒后，比较与上次上报的差异，决定要不要上报。"""

    def __init__(self, tracker: QQTracker):
        self.tracker = tracker
        self.last: dict | None = None
        self.last_sent_t = 0.0

    def due(self, now: float, debounce: float, heartbeat: float) -> dict | None:
        tr = self.tracker
        if now - tr.last_event_t < debounce:
            return None
        snap = tr.snapshot(now)
        if snap is None:
            return None
        reason = self._reason(snap, now, heartbeat)
        if reason is None:
            return None
        snap["reason"] = reason
        return snap

    def _reason(self, snap: dict, now: float, heartbeat: float) -> str | None:
        last = self.last
        if last is None:
            return "startup"
        hidden = ("occluded", "idle")
        if snap["status"] in hidden or last["status"] in hidden:
            if snap["status"] != last["status"]:
                return "visibility"
        else:
            if track_key(snap) != track_key(last):
                return "track_change"
            if snap["status"] != last["status"]:
                return "play_state"
        if snap["position"] is not None and last["position"] is not None:
            expected = last["position"]
            if last["playing"]:
                expected += snap["observed_at"] - last["observed_at"]
            if abs(snap["position"] - expected) > SEEK_THRESHOLD:
                return "seek"
        if now - self.last_sent_t >= heartbeat:
            return "heartbeat"
        return None

    def mark_sent(self, snap: dict, now: float) -> None:
        self.last = snap
        self.last_sent_t = now


# ---------------------------------------------------------------- 发送

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Sender:
    """只保证最新一条送达：失败后按退避重试，重试时发当时最新的快照。"""

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.pending = False
        self.fail_count = 0
        self.next_try = 0.0

    def send(self, payload: dict, now: float) -> bool:
        payload = dict(payload, sent_at=round(now, 3))
        if not self.cfg.server_url:
            log(f"[dry-run] {json.dumps(payload, ensure_ascii=False)}")
            return True
        req = urllib.request.Request(
            self.cfg.server_url,
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.token}",
                # Cloudflare 会以 1010 拦截默认的 Python-urllib UA
                "User-Agent": "SameBeat-Agent/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.build_opener(NoRedirect()).open(req, timeout=10) as resp:
                ok = 200 <= resp.status < 300
        except (urllib.error.URLError, OSError) as e:
            log(f"上报失败: {type(e).__name__}")
            ok = False
        if ok:
            log(f"已上报 {payload['reason']} {payload['status']}")
            self.pending = False
            self.fail_count = 0
        else:
            self.pending = True
            self.fail_count += 1
            self.next_try = now + min(60, 5 * 2 ** (self.fail_count - 1))
        return ok


# ---------------------------------------------------------------- 主循环

class Agent:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.proc: subprocess.Popen | None = None
        self.restart_delay = 1.0
        self.stopping = False
        self.tracker = QQTracker()
        self.reporter = Reporter(self.tracker)
        self.sender = Sender(cfg)

    def start_stream(self) -> None:
        cmd = [self.cfg.media_control, "stream", "--no-artwork", "--micros"]
        log(f"启动 {' '.join(cmd)}")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=0)
        os.set_blocking(self.proc.stdout.fileno(), False)
        self.buf = b""
        self.mirror = RawMirror()  # 重启后 media-control 会先发一条完整状态

    def stop_stream(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        self.proc = None

    def handle_line(self, line: bytes, now: float) -> None:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return
        delta = self.mirror.apply(msg)
        if delta is not None:
            self.tracker.on_event(self.mirror.state, delta, now)

    def step(self, now: float) -> None:
        if not self.cfg.sharing_enabled:
            return
        if self.sender.pending:
            if now >= self.sender.next_try:
                snap = self.tracker.snapshot(now)
                if snap:
                    snap["reason"] = "resend"
                    if self.sender.send(snap, now):
                        self.reporter.mark_sent(snap, now)
            return
        snap = self.reporter.due(now, self.cfg.debounce_seconds, self.cfg.heartbeat_seconds)
        if snap and self.sender.send(snap, now):
            self.reporter.mark_sent(snap, now)

    def run(self) -> None:
        sel = selectors.DefaultSelector()
        last_cfg_check = 0.0
        while not self.stopping:
            now = time.time()
            if now - last_cfg_check > 5:
                last_cfg_check = now
                was_sharing = self.cfg.sharing_enabled
                if self.cfg.reload_if_changed():
                    log(f"配置已更新 sharing_enabled={self.cfg.sharing_enabled}")
                    if self.cfg.sharing_enabled and not was_sharing:
                        self.reporter.last = None  # 重新打开分享时立即报一次
            if self.proc is None or self.proc.poll() is not None:
                if self.proc is not None:
                    log(f"media-control 退出（{self.proc.returncode}），{self.restart_delay:.0f} 秒后重启")
                    sel.unregister(self.proc.stdout)
                    self.proc = None
                    time.sleep(self.restart_delay)
                    self.restart_delay = min(30, self.restart_delay * 2)
                try:
                    self.start_stream()
                except OSError as e:
                    log(f"无法启动 media-control: {e}")
                    time.sleep(self.restart_delay)
                    self.restart_delay = min(30, self.restart_delay * 2)
                    continue
                sel.register(self.proc.stdout, selectors.EVENT_READ)
                started = time.time()
            for _key, _ in sel.select(timeout=0.25):
                chunk = self.proc.stdout.read()
                if not chunk:
                    continue
                self.buf += chunk
                *lines, self.buf = self.buf.split(b"\n")
                for line in lines:
                    if line.strip():
                        self.handle_line(line, time.time())
            if self.proc and time.time() - started > 60:
                self.restart_delay = 1.0  # 稳定运行一分钟后重置退避
            self.step(time.time())
        self.stop_stream()


def main() -> None:
    ap = argparse.ArgumentParser(description="SameBeat Mac Agent")
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    args = ap.parse_args()

    cfg = Config(args.config)
    try:
        cfg.reload_if_changed()
    except FileNotFoundError:
        sys.exit(f"找不到配置文件 {args.config}，请参考 config.example.toml 创建")
    agent = Agent(cfg)

    def _stop(*_):
        agent.stopping = True

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    log(f"SameBeat Agent 启动，{'dry-run（未配置 server_url）' if not cfg.server_url else '已配置服务器'}")
    agent.run()
    log("SameBeat Agent 退出")


if __name__ == "__main__":
    main()
