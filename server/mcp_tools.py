"""SameBeat MCP 读取层（Phase 3）。

只把 Server 里已有的事实交给 AI，不解释、不推断情绪、不接歌词、不控制播放、不写 OB。

- 状态语义：playing / paused / occluded / idle / offline；occluded 与 offline 都是「状态未知」
- 当前进度可以外推，但用 position_estimated 标明；历史时长只用确认过的 playing 区间
- 「今天 / 某一天」和所有人类可读时间按 user_timezone 计算
"""

from __future__ import annotations

import time
from datetime import date as Date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from store import Store, track_key

STATUS_MEANING = {
    "playing": "QQ 音乐可见，正在播放",
    "paused": "QQ 音乐可见，已暂停",
    "occluded": "Mac 在线，但 Now Playing 被其他媒体源占用，QQ 音乐当前状态未知（不等于没在播放）",
    "idle": "Mac 在线，系统当前没有任何 Now Playing",
    "offline": "超过 2 分钟没有收到 Mac 端数据，当前状态未知（不等于没在播放）",
}
END_REASON = {"track_change": "换歌", "loop": "单曲循环进入下一遍", "idle": "播放源消失"}


# ---------------------------------------------------------------- 格式化

def mmss(sec) -> str | None:
    if sec is None:
        return None
    sec = int(round(sec))
    return f"{sec // 60}:{sec % 60:02d}"


def dur_text(sec: float) -> str:
    sec = int(round(sec))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}小时{m}分"
    return f"{m}分{s}秒" if m else f"{s}秒"


class Ctx:
    def __init__(self, store: Store, tz: ZoneInfo, now: float | None = None):
        self.store = store
        self.tz = tz
        self.now = time.time() if now is None else now

    def local(self, ts) -> str | None:
        if ts is None:
            return None
        return datetime.fromtimestamp(ts, self.tz).strftime("%Y-%m-%d %H:%M:%S")

    def day_bounds(self, d: Date) -> tuple[float, float]:
        start = datetime(d.year, d.month, d.day, tzinfo=self.tz)
        end = start + timedelta(days=1)
        return start.timestamp(), end.timestamp()

    def today(self) -> Date:
        return datetime.fromtimestamp(self.now, self.tz).date()


def track_of(d: dict) -> dict:
    return {k: d.get(k) for k in ("title", "artist", "album", "duration")}


def label(d: dict) -> str:
    return f"《{d['title']}》— {d['artist']}" if d.get("artist") else f"《{d['title']}》"


def consecutive_play(store: Store, play: dict) -> int:
    """这一段是同一首歌连续第几遍：往前数紧邻的、以单曲循环结束的同一首歌。"""
    n = 1
    for prev in store.plays_before(play["id"]):
        if track_key(prev) != track_key(play) or prev["end_reason"] != "loop":
            break
        n += 1
    return n


def longest_loop_run(plays: list[dict]) -> tuple[int, dict | None]:
    """按时间顺序的播放段里，同一首歌靠单曲循环连起来的最长一串。"""
    best, best_play, run = 0, None, 0
    for i, p in enumerate(plays):
        chained = (i > 0 and track_key(plays[i - 1]) == track_key(p) and plays[i - 1]["end_reason"] == "loop")
        run = run + 1 if chained else 1
        if run > best:
            best, best_play = run, p
    return best, best_play


def play_item(c: Ctx, p: dict) -> dict:
    return {
        **track_of(p),
        "play_index": p["play_index"],
        "started_at": c.local(p["started_at"]),
        "ended_at": c.local(p["ended_at"]),
        "ongoing": p["ended_at"] is None,
        "confirmed_listened_seconds": p["listened_seconds"],
        "end_reason": p["end_reason"],
    }


# ---------------------------------------------------------------- 工具实现（纯函数，便于测试）

def now_playing(c: Ctx) -> dict[str, Any]:
    st = c.store.state(c.now)
    status = st["status"]
    out: dict[str, Any] = {
        "status": status,
        "status_meaning": STATUS_MEANING[status],
        "mac_last_seen_at": c.local(st.get("agent_last_seen_at")),
    }
    if status in ("playing", "paused"):
        playing = status == "playing"
        pos = st["position"]
        extrapolated = playing and pos is not None and c.now - st["base_at"] > 0.5
        estimated = pos is not None and (extrapolated or st["position_confirmed"] is False)
        out.update({
            "track": track_of(st),
            "position_seconds": pos,
            "position_text": f"{mmss(pos)} / {mmss(st['duration'])}" if pos is not None else None,
            # 进度是否为推算值：按上次上报外推，或上报本身就是 Agent 的估计（position_confirmed=false）
            "position_estimated": estimated,
            "position_confirmed": st["position_confirmed"],
            "position_reported_seconds": st.get("position_reported"),
            "position_reported_at": c.local(st["base_at"]),
        })
        play = st["current_play"]
        if play:
            out["play_index"] = play["play_index"]
            out["consecutive_play"] = consecutive_play(c.store, play)
        if pos is None:
            pos_text = "进度未知"
        else:
            pos_text = out["position_text"] + ("（推算）" if estimated else "")
        parts = [STATUS_MEANING[status], label(st), pos_text]
        if play and out["consecutive_play"] > 1:
            parts.append(f"连续第 {out['consecutive_play']} 遍")
        out["summary"] = " · ".join(parts)
    else:
        lk = st.get("last_known")
        if lk:
            out["last_known"] = {
                "stale": True, **track_of(lk),
                "position_seconds": lk.get("position"), "playing": lk.get("playing"),
                "observed_at": c.local(lk.get("observed_at")),
            }
        summary = STATUS_MEANING[status]
        if lk and lk.get("title"):
            summary += f"。最后一次确认看到的是 {label(lk)}（{c.local(lk.get('observed_at'))}，旧状态）"
        out["summary"] = summary
    return out


def recent_history(c: Ctx, hours: float = 24, limit: int = 20) -> dict[str, Any]:
    hours = min(max(hours, 1), 24 * 30)
    limit = min(max(int(limit), 1), 100)
    plays = c.store.plays_since(c.now - hours * 3600, limit)
    items = [play_item(c, p) for p in plays]
    total = sum(p["listened_seconds"] for p in plays)
    lines = [
        f"{i['started_at'][11:16]} {label(i)} · 第{i['play_index']}次 · 确认听了{dur_text(i['confirmed_listened_seconds'])}"
        + (" · 进行中" if i["ongoing"] else f" · {END_REASON.get(i['end_reason'], i['end_reason'] or '')}")
        for i in items
    ]
    head = f"最近 {hours:g} 小时共 {len(items)} 段（最多列 {limit} 段），确认听歌时长合计 {dur_text(total)}"
    return {
        "summary": head + ("：\n" + "\n".join(lines) if lines else "，没有播放记录"),
        "hours": hours,
        "confirmed_listened_seconds_total": round(total, 1),
        "plays": items,
    }


def track_context(c: Ctx, title: str | None = None, artist: str | None = None) -> dict[str, Any]:
    st = c.store.state(c.now)
    other_matches: list[dict] = []
    if title:
        found = c.store.find_tracks(title, artist)
        if not found:
            return {"found": False, "summary": f"没有《{title}》的播放记录"}
        target, other_matches = found[0], found[1:]
        source = "query"
    elif st["status"] in ("playing", "paused") and st.get("title"):
        target, source = st, "current"
    else:
        target, source = c.store.last_play(), "last_played"
        if target is None:
            return {"found": False, "summary": "还没有任何播放记录"}

    key = track_key(target)
    plays = c.store.plays_of_track(key)
    is_current = st["status"] in ("playing", "paused") and track_key(st) == key
    d0, d1 = c.day_bounds(c.today())
    # 这首歌历史上最长的单曲循环串（紧邻、以 loop 连起来的同一首歌）
    loop_best = max((consecutive_play(c.store, p) for p in plays), default=0)

    out: dict[str, Any] = {
        "found": True,
        "source": source,  # query / current / last_played
        "track": track_of(target),
        "is_current": is_current,
        "total_plays": len(plays),
        "confirmed_listened_seconds_total": round(sum(p["listened_seconds"] for p in plays), 1),
        "first_played_at": c.local(plays[0]["started_at"]) if plays else None,
        "last_played_at": c.local(plays[-1]["started_at"]) if plays else None,
        "plays_today": sum(1 for p in plays if d0 <= p["started_at"] < d1),
        "longest_consecutive_plays": loop_best,
        "recent_plays": [play_item(c, p) for p in plays[-5:][::-1]],
    }
    if is_current and st.get("current_play"):
        out["current_consecutive_play"] = consecutive_play(c.store, st["current_play"])
    if other_matches:
        out["other_matches"] = [track_of(m) for m in other_matches]

    parts = [label(target)]
    if target.get("album"):
        parts.append(f"专辑《{target['album']}》")
    if target.get("duration"):
        parts.append(f"时长 {mmss(target['duration'])}")
    if plays:
        parts.append(f"共播放 {len(plays)} 次，确认听了 {dur_text(out['confirmed_listened_seconds_total'])}")
        parts.append(f"今天 {out['plays_today']} 次")
        parts.append(f"首次 {out['first_played_at']}，最近 {out['last_played_at']}")
        if loop_best > 1:
            parts.append(f"最长连续循环 {loop_best} 遍")
    else:
        parts.append("没有完整的播放记录")
    if out.get("current_consecutive_play", 1) > 1:
        parts.append(f"当前连续第 {out['current_consecutive_play']} 遍")
    out["summary"] = " · ".join(parts)
    return out


def listening_summary(c: Ctx, date: str | None = None) -> dict[str, Any]:
    try:
        day = Date.fromisoformat(date) if date else c.today()
    except ValueError:
        return {"summary": f"日期格式应为 YYYY-MM-DD，收到的是 {date!r}"}
    start, end = c.day_bounds(day)
    plays = c.store.plays_between(start, end)
    by_track: dict[tuple, dict] = {}
    for p in plays:
        t = by_track.setdefault(track_key(p), {**track_of(p), "plays": 0, "confirmed_listened_seconds": 0.0})
        t["plays"] += 1
        t["confirmed_listened_seconds"] += p["listened_seconds"]
    tracks = sorted(by_track.values(), key=lambda t: (-t["plays"], -t["confirmed_listened_seconds"]))
    for t in tracks:
        t["confirmed_listened_seconds"] = round(t["confirmed_listened_seconds"], 1)
    total = sum(p["listened_seconds"] for p in plays)
    loop_len, loop_play = longest_loop_run(plays)

    out: dict[str, Any] = {
        "date": day.isoformat(),
        "timezone": str(c.tz),
        "total_plays": len(plays),
        "distinct_tracks": len(tracks),
        "confirmed_listened_seconds_total": round(total, 1),
        "most_played": tracks[0] if tracks else None,
        "longest_single_track_loop": ({**track_of(loop_play), "consecutive_plays": loop_len}
                                      if loop_len > 1 else None),
        "tracks": tracks[:20],
    }
    if not plays:
        out["summary"] = f"{day.isoformat()}（{c.tz}）没有播放记录"
        return out
    parts = [f"{day.isoformat()}（{c.tz}）共 {len(plays)} 段、{len(tracks)} 首歌，确认听歌时长 {dur_text(total)}",
             f"播放次数最多：{label(tracks[0])} {tracks[0]['plays']} 次"]
    if loop_len > 1:
        parts.append(f"单曲循环最长：{label(loop_play)} 连续 {loop_len} 遍")
    out["summary"] = "；".join(parts)
    return out


# ---------------------------------------------------------------- 注册到 MCP

INSTRUCTIONS = (
    "SameBeat 提供用户在 QQ 音乐（Mac）上的听歌事实：此刻在听什么、听到哪里、最近听了什么。"
    "只提供事实，不代表用户的情绪或意图。occluded 和 offline 表示状态未知，不等于没在听。"
    "所有时间均为用户时区的本地时间。"
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)


def build_mcp(store: Store, tz: ZoneInfo) -> MCPServer:
    mcp = MCPServer(name="SameBeat", instructions=INSTRUCTIONS)

    @mcp.tool(name="now_playing", annotations=READ_ONLY)
    def _now_playing() -> dict[str, Any]:
        """此刻 QQ 音乐的播放状态。

        status 取值：playing / paused / occluded（被其他媒体源遮挡，状态未知）/ idle（没有任何 Now Playing）/
        offline（Mac 端失联，状态未知）。occluded 和 offline 都不等于没在听。
        position_estimated=true 表示进度是按最后一次上报推算的，不是播放器刚刚报告的值。
        consecutive_play 是同一首歌通过单曲循环连续播放到第几遍。"""
        return now_playing(Ctx(store, tz))

    @mcp.tool(name="recent_history", annotations=READ_ONLY)
    def _recent_history(hours: float = 24, limit: int = 20) -> dict[str, Any]:
        """最近 hours 小时内开始的播放段（新的在前，最多 limit 段）。

        confirmed_listened_seconds 只包含确认在播放的时间：被其他媒体源遮挡或 Mac 离线的时间不计入，
        正在进行的那一段只计到最后一次上报为止。end_reason：track_change 换歌 / loop 单曲循环进入下一遍 /
        idle 播放源消失；ongoing=true 表示仍在进行。"""
        return recent_history(Ctx(store, tz), hours, limit)

    @mcp.tool(name="track_context", annotations=READ_ONLY)
    def _track_context(title: str | None = None, artist: str | None = None) -> dict[str, Any]:
        """一首歌的已知信息与播放历史。不传参数时取当前这首（没有当前歌曲时取最近播放的一首）；
        传 title（可选 artist）时按歌名精确匹配。返回总播放次数、确认听歌时长、今天播放次数、
        首次/最近播放时间、最长连续循环遍数和最近几次播放。不含歌词。"""
        return track_context(Ctx(store, tz), title, artist)

    @mcp.tool(name="listening_summary", annotations=READ_ONLY)
    def _listening_summary(date: str | None = None) -> dict[str, Any]:
        """某一天（YYYY-MM-DD，按用户时区；默认今天）听了什么：播放段数、不同歌曲数、确认听歌时长、
        播放次数最多的歌、单曲循环连续遍数最多的歌。播放段按开始时间归属到当天。"""
        return listening_summary(Ctx(store, tz), date)

    return mcp
