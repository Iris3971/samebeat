"""SameBeat Server 的 SQLite 存储与状态逻辑。

规则来源：docs/PLAN.md Phase 2 与 docs/phase0-findings.md §7 / Iris 2026-09-26 的 Phase 2 决定：
- 状态只有 playing / paused / occluded / idle / offline，不抽象 is_listening。
  occluded 与 offline 都是「QQ 状态未知」，不能解释成没在听。
- 实际听歌时长只累计能确认的 playing 区间。
- 同一首歌自然播完回到开头 = 单曲循环，新开一段、play_index+1；
  手动 seek 回开头不算新播放。
- observed_at 与服务器 received_at 偏差超过 30 秒时，用 received_at 作为进度基准并记 warning。
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading

log = logging.getLogger("samebeat.store")

OFFLINE_AFTER = 120.0   # 秒；超过没收到 Agent 数据 → offline
CLOCK_TOLERANCE = 30.0  # 秒；observed_at 与 received_at 偏差超过它视为客户端时间不可信
LOOP_END_SLACK = 3.0    # 秒；上一段外推进度 ≥ duration - 它，才算「已经放到结尾」
LOOP_START_MAX = 10.0   # 秒；新进度 ≤ 它，才算「回到了开头」

VISIBLE = ("playing", "paused")

SCHEMA = """
CREATE TABLE IF NOT EXISTS current (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    status TEXT NOT NULL,
    title TEXT, artist TEXT, album TEXT, duration REAL,
    position REAL,
    position_confirmed INTEGER,
    base_at REAL NOT NULL,          -- position 对应的时刻（正常=observed_at，时钟不可信时=received_at）
    observed_at REAL NOT NULL,      -- 客户端原值
    received_at REAL NOT NULL,
    sent_at REAL,
    reason TEXT,
    clock_untrusted INTEGER NOT NULL DEFAULT 0,
    last_known TEXT,                -- JSON，Agent 给的旧状态（stale）
    play_id INTEGER                 -- 当前（最近）打开的播放段
);
CREATE TABLE IF NOT EXISTS plays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL, artist TEXT NOT NULL, album TEXT NOT NULL, duration REAL NOT NULL,
    play_index INTEGER NOT NULL,    -- 这首歌第几次播放（全部历史）
    started_at REAL NOT NULL,
    last_seen_at REAL NOT NULL,     -- 最后一次确认看到它（playing/paused）的时刻
    ended_at REAL,                  -- NULL = 这一段还开着
    listened_seconds REAL NOT NULL DEFAULT 0,
    end_reason TEXT                 -- track_change / loop / idle / ...
);
CREATE INDEX IF NOT EXISTS plays_track ON plays (title, artist, album, duration);
CREATE INDEX IF NOT EXISTS plays_started ON plays (started_at);
"""


def track_key(d: dict | sqlite3.Row | None):
    if d is None or not d["title"]:
        return None
    return (d["title"], d["artist"] or "", d["album"] or "", float(d["duration"] or 0))


class Store:
    def __init__(self, path: str):
        self.db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(SCHEMA)
        self.lock = threading.Lock()

    # ------------------------------------------------------------ 写入

    def ingest(self, p: dict, received_at: float) -> dict:
        """处理一条 Agent 上报，返回 {"accepted": bool, ...}。"""
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                result = self._ingest(p, received_at)
                self.db.execute("COMMIT")
                return result
            except BaseException:
                self.db.execute("ROLLBACK")
                raise

    def _ingest(self, p: dict, received_at: float) -> dict:
        observed_at = float(p["observed_at"])
        clock_untrusted = abs(observed_at - received_at) > CLOCK_TOLERANCE
        if clock_untrusted:
            log.warning("客户端时间不可信：observed_at 与 received_at 相差 %.1f 秒，改用 received_at",
                        observed_at - received_at)
        base_at = received_at if clock_untrusted else observed_at

        cur = self.db.execute("SELECT * FROM current WHERE id = 1").fetchone()
        if cur is not None and base_at < cur["base_at"]:
            return {"accepted": False, "detail": "older than current state"}

        status = p["status"]
        duration = p.get("duration")
        position = p.get("position")
        if position is not None and duration:
            position = min(max(position, 0.0), float(duration))

        play_id = cur["play_id"] if cur else None
        play = self.db.execute("SELECT * FROM plays WHERE id = ?", (play_id,)).fetchone() if play_id else None

        # 1) 把上一条到这一条之间确认在播放的时间记到当前播放段
        if cur is not None and play is not None and play["ended_at"] is None:
            self._accumulate(cur, play, base_at)

        # 2) 播放段的开关
        if status in VISIBLE:
            key = track_key(p)
            if play is not None and play["ended_at"] is None:
                if track_key(play) != key:
                    self._close(play["id"], play["last_seen_at"] if cur["status"] not in VISIBLE else base_at,
                                "track_change")
                    play = None
                elif self._is_natural_loop(cur, play, position, base_at):
                    self._close(play["id"], base_at, "loop")
                    play = None
            if play is None or play["ended_at"] is not None:
                # 只有真的开始播放才开一段；停在某首歌上（例如 Agent 启动时 QQ 是暂停的）不算听过
                play_id = self._open(p, base_at, position) if status == "playing" else None
            else:
                self.db.execute("UPDATE plays SET last_seen_at = ? WHERE id = ?", (base_at, play["id"]))
        elif status == "idle" and play is not None and play["ended_at"] is None:
            # 系统里没有任何 Now Playing：这一段结束在最后一次确认看到它的时刻
            self._close(play["id"], play["last_seen_at"], "idle")
        # occluded：QQ 状态未知，播放段保持打开，不累计时长

        last_known = p.get("last_known")
        self.db.execute(
            """INSERT INTO current (id, status, title, artist, album, duration, position, position_confirmed,
                                    base_at, observed_at, received_at, sent_at, reason, clock_untrusted,
                                    last_known, play_id)
               VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(id) DO UPDATE SET
                 status=excluded.status, title=excluded.title, artist=excluded.artist, album=excluded.album,
                 duration=excluded.duration, position=excluded.position,
                 position_confirmed=excluded.position_confirmed, base_at=excluded.base_at,
                 observed_at=excluded.observed_at, received_at=excluded.received_at, sent_at=excluded.sent_at,
                 reason=excluded.reason, clock_untrusted=excluded.clock_untrusted,
                 last_known=excluded.last_known, play_id=excluded.play_id""",
            (status, p.get("title"), p.get("artist"), p.get("album"), duration, position,
             None if p.get("position_confirmed") is None else int(bool(p["position_confirmed"])),
             base_at, observed_at, received_at, p.get("sent_at"), p.get("reason"), int(clock_untrusted),
             json.dumps(last_known, ensure_ascii=False) if last_known else None, play_id),
        )
        return {"accepted": True, "clock_untrusted": clock_untrusted}

    def _accumulate(self, cur: sqlite3.Row, play: sqlite3.Row, base_at: float) -> None:
        """上一条是 playing 且间隔没超过离线阈值，这段时间才算确认的听歌时间。"""
        if cur["status"] != "playing":
            return
        gap = base_at - cur["base_at"]
        if 0 < gap <= OFFLINE_AFTER:
            self.db.execute("UPDATE plays SET listened_seconds = listened_seconds + ? WHERE id = ?",
                            (gap, play["id"]))

    def _is_natural_loop(self, cur: sqlite3.Row, play: sqlite3.Row, position, base_at: float) -> bool:
        """同一首歌：上一条在播放、按时间外推已经到结尾，这一条回到了开头。"""
        if cur["status"] != "playing" or cur["position"] is None or position is None:
            return False
        if base_at - cur["base_at"] > OFFLINE_AFTER:
            return False
        duration = float(play["duration"] or 0)
        if duration <= 0:
            return False
        projected = cur["position"] + (base_at - cur["base_at"])
        return projected >= duration - LOOP_END_SLACK and position <= LOOP_START_MAX

    def _open(self, p: dict, base_at: float, position) -> int:
        key = track_key(p)
        n = self.db.execute(
            "SELECT COUNT(*) FROM plays WHERE title = ? AND artist = ? AND album = ? AND duration = ?",
            key).fetchone()[0]
        c = self.db.execute(
            """INSERT INTO plays (title, artist, album, duration, play_index, started_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (*key, n + 1, base_at, base_at))
        return c.lastrowid

    def _close(self, play_id: int, ended_at: float, reason: str) -> None:
        self.db.execute("UPDATE plays SET ended_at = ?, end_reason = ? WHERE id = ? AND ended_at IS NULL",
                        (ended_at, reason, play_id))

    # ------------------------------------------------------------ 读取

    def state(self, now: float, recent: int = 5) -> dict:
        with self.lock:
            cur = self.db.execute("SELECT * FROM current WHERE id = 1").fetchone()
            plays = self.db.execute("SELECT * FROM plays ORDER BY id DESC LIMIT ?", (recent,)).fetchall()
        if cur is None:
            return {"status": "offline", "detail": "还没有收到过 Agent 数据", "now": now,
                    "current_play": None, "recent_plays": []}

        status = cur["status"]
        offline = now - cur["received_at"] > OFFLINE_AFTER
        out = {
            "now": now,
            "status": "offline" if offline else status,
            "title": None, "artist": None, "album": None, "duration": None,
            "position": None, "playing": None, "position_confirmed": None,
            "agent_last_seen_at": cur["received_at"],
            "observed_at": cur["observed_at"],
            "base_at": cur["base_at"],
            "sent_at": cur["sent_at"],
            "clock_untrusted": bool(cur["clock_untrusted"]),
            "last_reason": cur["reason"],
            "last_known": None,
        }
        if status in VISIBLE and not offline:
            out.update(
                title=cur["title"], artist=cur["artist"], album=cur["album"], duration=cur["duration"],
                position=self._project(cur, now), position_reported=cur["position"],
                playing=status == "playing",
                position_confirmed=None if cur["position_confirmed"] is None else bool(cur["position_confirmed"]),
            )
        elif status in VISIBLE:
            # offline：Agent 失联前最后看到的 QQ 状态，只作为旧状态给出
            out["last_known"] = {
                "stale": True, "title": cur["title"], "artist": cur["artist"], "album": cur["album"],
                "duration": cur["duration"], "position": cur["position"], "playing": status == "playing",
                "observed_at": cur["base_at"],
            }
        elif cur["last_known"]:
            out["last_known"] = json.loads(cur["last_known"])

        open_play = None
        if cur["play_id"]:
            row = next((r for r in plays if r["id"] == cur["play_id"]), None)
            if row is None:
                with self.lock:
                    row = self.db.execute("SELECT * FROM plays WHERE id = ?", (cur["play_id"],)).fetchone()
            if row is not None and row["ended_at"] is None:
                open_play = self._play_dict(row)
                if status == "playing" and not offline:
                    # 最后一条上报之后仍在播放的这段时间，按同样规则计入
                    gap = now - cur["base_at"]
                    if 0 < gap <= OFFLINE_AFTER:
                        open_play["listened_seconds"] = round(open_play["listened_seconds"] + gap, 1)
        out["current_play"] = open_play
        out["recent_plays"] = [self._play_dict(r) for r in plays]
        return out

    # ------------------------------------------------------------ MCP 读取（Phase 3）

    def _rows(self, sql: str, args=()) -> list[dict]:
        with self.lock:
            return [self._play_dict(r) for r in self.db.execute(sql, args).fetchall()]

    def plays_since(self, since: float, limit: int) -> list[dict]:
        """started_at ≥ since 的播放段，新的在前。"""
        return self._rows("SELECT * FROM plays WHERE started_at >= ? ORDER BY id DESC LIMIT ?", (since, limit))

    def plays_between(self, start: float, end: float) -> list[dict]:
        """start ≤ started_at < end 的播放段，按时间顺序。"""
        return self._rows("SELECT * FROM plays WHERE started_at >= ? AND started_at < ? ORDER BY id", (start, end))

    def plays_of_track(self, key: tuple) -> list[dict]:
        return self._rows(
            "SELECT * FROM plays WHERE title = ? AND artist = ? AND album = ? AND duration = ? ORDER BY id", key)

    def plays_before(self, play_id: int, limit: int = 200) -> list[dict]:
        """id < play_id 的播放段，紧邻的在前（用于数连续循环）。"""
        return self._rows("SELECT * FROM plays WHERE id < ? ORDER BY id DESC LIMIT ?", (play_id, limit))

    def last_play(self) -> dict | None:
        rows = self._rows("SELECT * FROM plays ORDER BY id DESC LIMIT 1")
        return rows[0] if rows else None

    def find_tracks(self, title: str, artist: str | None) -> list[dict]:
        """按歌名（及歌手）精确匹配，不区分大小写；每首歌返回最近一段。"""
        sql = ("SELECT * FROM plays WHERE id IN (SELECT MAX(id) FROM plays WHERE lower(title) = lower(?)"
               + (" AND lower(artist) = lower(?)" if artist else "")
               + " GROUP BY title, artist, album, duration) ORDER BY id DESC")
        return self._rows(sql, (title, artist) if artist else (title,))

    @staticmethod
    def _project(cur: sqlite3.Row, now: float):
        pos = cur["position"]
        if pos is None:
            return None
        if cur["status"] == "playing":
            pos += max(0.0, now - cur["base_at"])
        if cur["duration"]:
            pos = min(pos, float(cur["duration"]))
        return round(max(pos, 0.0), 1)

    @staticmethod
    def _play_dict(r: sqlite3.Row) -> dict:
        return {
            "id": r["id"], "title": r["title"], "artist": r["artist"], "album": r["album"],
            "duration": r["duration"], "play_index": r["play_index"],
            "started_at": r["started_at"], "last_seen_at": r["last_seen_at"], "ended_at": r["ended_at"],
            "listened_seconds": round(r["listened_seconds"], 1), "end_reason": r["end_reason"],
        }
