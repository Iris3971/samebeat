"""Phase 3 MCP 读取层测试。

运行（在 server/ 目录）：python3 -m unittest test_mcp.py
"""

import json
import logging
import os
import tempfile
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

import mcp_tools as T
from store import OFFLINE_AFTER, Store
from test_server import hidden, paused, playing

TZ = ZoneInfo("Asia/Shanghai")
# 2026-09-26 22:00:00 北京时间
T0 = datetime(2026, 9, 26, 22, 0, tzinfo=TZ).timestamp()


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def feed(self, p):
        self.s.ingest(p, p["observed_at"])

    def loop_three_times(self):
        """放到结尾自然循环两次（每 30 秒一次心跳，和真实 Agent 一样）。"""
        self.feed(playing(T0, 190))
        t = T0 + 17
        for _ in range(2):
            self.feed(playing(t, 1, reason="seek"))
            for k in range(1, 7):
                self.feed(playing(t + 30 * k, 1 + 30 * k))
            t += 206
        return t - 206

    def ctx(self, now, tz=TZ):
        return T.Ctx(self.s, tz, now)

    # ---- now_playing

    def test_playing_position_is_marked_estimated(self):
        self.feed(playing(T0, 60))
        r = T.now_playing(self.ctx(T0 + 12))
        self.assertEqual(r["status"], "playing")
        self.assertEqual(r["position_seconds"], 72)
        self.assertTrue(r["position_estimated"])
        self.assertEqual(r["position_reported_seconds"], 60)
        self.assertEqual(r["position_reported_at"], "2026-09-26 22:00:00")
        self.assertIn("1:12 / 3:26（推算）", r["summary"])

    def test_paused_confirmed_is_not_estimated(self):
        self.feed(paused(T0, 69))
        r = T.now_playing(self.ctx(T0 + 100))
        self.assertEqual((r["position_seconds"], r["position_estimated"]), (69, False))
        self.assertNotIn("推算", r["summary"])

    def test_paused_unknown_position(self):
        self.feed(dict(paused(T0, 0), position=None, position_confirmed=False))
        r = T.now_playing(self.ctx(T0 + 1))
        self.assertIsNone(r["position_seconds"])
        self.assertIn("进度未知", r["summary"])

    def test_occluded_and_offline_are_unknown_not_stopped(self):
        self.feed(playing(T0, 10))
        lk = {"stale": True, "title": "终身美丽", "artist": "郑秀文", "album": "Shocking Pink",
              "duration": 206.0, "position": 20.0, "playing": True, "observed_at": T0 + 10}
        self.feed(hidden(T0 + 10, last_known=lk))
        r = T.now_playing(self.ctx(T0 + 20))
        self.assertEqual(r["status"], "occluded")
        self.assertNotIn("track", r)
        self.assertTrue(r["last_known"]["stale"])
        self.assertIn("状态未知", r["summary"])
        self.assertIn("不等于没在播放", r["summary"])
        r = T.now_playing(self.ctx(T0 + 10 + OFFLINE_AFTER + 5))
        self.assertEqual(r["status"], "offline")
        self.assertIn("状态未知", r["summary"])

    def test_consecutive_play_counts_loops(self):
        t = self.loop_three_times()
        r = T.now_playing(self.ctx(t + 5))
        self.assertEqual(r["consecutive_play"], 3)
        self.assertEqual(r["play_index"], 3)
        self.assertIn("连续第 3 遍", r["summary"])

    def test_play_index_not_consecutive_after_other_song(self):
        self.feed(playing(T0, 0))
        self.feed(playing(T0 + 10, 0, title="Digital Love", duration=301.0, reason="track_change"))
        self.feed(playing(T0 + 20, 0, reason="track_change"))
        r = T.now_playing(self.ctx(T0 + 21))
        self.assertEqual((r["play_index"], r["consecutive_play"]), (2, 1))
        self.assertNotIn("连续", r["summary"])

    # ---- recent_history

    def test_recent_history_confirmed_only(self):
        self.feed(playing(T0, 0))
        self.feed(playing(T0 + 30, 30))
        self.feed(hidden(T0 + 31))                              # 遮挡 5 分钟
        self.feed(playing(T0 + 331, 331 % 206, reason="visibility"))
        self.feed(playing(T0 + 341, 0, title="Digital Love", duration=301.0, reason="track_change"))
        r = T.recent_history(self.ctx(T0 + 350), hours=1)
        self.assertEqual([p["title"] for p in r["plays"]], ["Digital Love", "终身美丽"])
        self.assertAlmostEqual(r["plays"][1]["confirmed_listened_seconds"], 41, delta=0.5)
        self.assertTrue(r["plays"][0]["ongoing"])
        self.assertEqual(r["plays"][1]["end_reason"], "track_change")
        self.assertIn("22:00 《终身美丽》— 郑秀文", r["summary"])

    def test_recent_history_limits(self):
        self.feed(playing(T0 - 5 * 3600, 0))
        self.feed(playing(T0, 0, title="Digital Love", duration=301.0, reason="track_change"))
        self.assertEqual(len(T.recent_history(self.ctx(T0 + 1), hours=1)["plays"]), 1)
        self.assertEqual(len(T.recent_history(self.ctx(T0 + 1), hours=24)["plays"]), 2)
        self.assertEqual(len(T.recent_history(self.ctx(T0 + 1), hours=24, limit=1)["plays"]), 1)

    # ---- track_context

    def test_track_context_current_and_query(self):
        self.feed(playing(T0, 190))
        self.feed(playing(T0 + 17, 1, reason="seek"))
        self.feed(playing(T0 + 30, 0, title="Digital Love", duration=301.0, reason="track_change"))
        cur = T.track_context(self.ctx(T0 + 40))
        self.assertEqual((cur["source"], cur["track"]["title"], cur["is_current"]), ("current", "Digital Love", True))
        q = T.track_context(self.ctx(T0 + 40), title="终身美丽")
        self.assertEqual((q["total_plays"], q["plays_today"], q["longest_consecutive_plays"]), (2, 2, 2))
        self.assertFalse(q["is_current"])
        self.assertAlmostEqual(q["confirmed_listened_seconds_total"], 30, delta=0.5)
        self.assertFalse(T.track_context(self.ctx(T0), title="不存在")["found"])

    def test_track_context_falls_back_to_last_played(self):
        self.feed(playing(T0, 0))
        self.feed(hidden(T0 + 10, status="idle"))
        r = T.track_context(self.ctx(T0 + 20))
        self.assertEqual((r["source"], r["track"]["title"]), ("last_played", "终身美丽"))

    # ---- listening_summary

    def test_summary_day_boundary_uses_user_timezone(self):
        # 北京时间 23:59 开始的一段算 26 号；00:01 开始的算 27 号
        self.feed(playing(T0 + 7140, 0))
        self.feed(playing(T0 + 7260, 0, title="Digital Love", duration=301.0, reason="track_change"))
        d26 = T.listening_summary(self.ctx(T0 + 7300), "2026-09-26")
        d27 = T.listening_summary(self.ctx(T0 + 7300), "2026-09-27")
        self.assertEqual([t["title"] for t in d26["tracks"]], ["终身美丽"])
        self.assertEqual([t["title"] for t in d27["tracks"]], ["Digital Love"])
        self.assertEqual(T.listening_summary(self.ctx(T0 + 7300))["date"], "2026-09-27")  # 默认今天
        # 换时区只改配置：同一数据按 UTC，两段都在 26 号
        utc = T.listening_summary(self.ctx(T0 + 7300, ZoneInfo("UTC")), "2026-09-26")
        self.assertEqual(utc["total_plays"], 2)

    def test_summary_longest_loop_and_most_played(self):
        t = self.loop_three_times()
        self.feed(playing(t + 10, 0, title="Digital Love", duration=301.0, reason="track_change"))
        r = T.listening_summary(self.ctx(t + 20), "2026-09-26")
        self.assertEqual(r["most_played"]["title"], "终身美丽")
        self.assertEqual(r["longest_single_track_loop"]["consecutive_plays"], 3)
        self.assertIn("单曲循环最长：《终身美丽》— 郑秀文 连续 3 遍", r["summary"])

    def test_summary_bad_date(self):
        self.assertIn("YYYY-MM-DD", T.listening_summary(self.ctx(T0), "昨天")["summary"])

    def test_no_interpretation_words(self):
        self.feed(playing(T0, 190))
        self.feed(playing(T0 + 17, 1, reason="seek"))
        c = self.ctx(T0 + 20)
        blob = json.dumps([T.now_playing(c), T.recent_history(c), T.track_context(c),
                           T.listening_summary(c)], ensure_ascii=False)
        for w in ("心情", "情绪", "难过", "开心", "喜欢", "想念", "伤心"):
            self.assertNotIn(w, blob)


class McpHttpTest(unittest.TestCase):
    SECRET = "s" * 48

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ.update(SAMEBEAT_TOKEN="t" * 40, SAMEBEAT_MCP_SECRET=cls.SECRET,
                          SAMEBEAT_DB=os.path.join(cls.tmp.name, "m.db"), SAMEBEAT_USER_TIMEZONE="Asia/Shanghai")
        import importlib
        import app
        cls.app = importlib.reload(app)
        from fastapi.testclient import TestClient
        cls.client_cm = TestClient(cls.app.app, base_url="http://127.0.0.1:8000")
        cls.c = cls.client_cm.__enter__()  # 运行 lifespan（MCP session manager）

    @classmethod
    def tearDownClass(cls):
        cls.client_cm.__exit__(None, None, None)
        cls.tmp.cleanup()

    def rpc(self, method, params=None, path=None, headers=None):
        h = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
             "MCP-Protocol-Version": "2025-06-18", **(headers or {})}
        return self.c.post(path or f"/mcp/{self.SECRET}", headers=h,
                           json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}})

    def test_list_and_call_tools(self):
        r = self.rpc("tools/list")
        self.assertEqual(r.status_code, 200, r.text)
        tools = {t["name"]: t for t in r.json()["result"]["tools"]}
        self.assertEqual(set(tools), {"now_playing", "recent_history", "track_context", "listening_summary"})
        for t in tools.values():
            self.assertTrue(t["annotations"]["readOnlyHint"])
        r = self.rpc("tools/call", {"name": "now_playing", "arguments": {}})
        self.assertEqual(r.status_code, 200, r.text)
        res = r.json()["result"]
        self.assertFalse(res.get("isError"), res)
        self.assertEqual(res["structuredContent"]["status"], "offline")

    def test_all_four_tools_respond_without_errors(self):
        for name in ("now_playing", "recent_history", "track_context", "listening_summary"):
            with self.subTest(tool=name):
                response = self.rpc("tools/call", {"name": name, "arguments": {}})
                self.assertEqual(response.status_code, 200)
                result = response.json()["result"]
                self.assertFalse(result.get("isError"), result)
                self.assertIn("summary", result["structuredContent"])

    def test_wrong_secret_is_404(self):
        self.assertEqual(self.rpc("tools/list", path="/mcp/" + "x" * 48).status_code, 404)
        self.assertEqual(self.rpc("tools/list", path="/mcp").status_code, 404)

    def test_foreign_host_rejected(self):
        r = self.rpc("tools/list", headers={"Host": "evil.example"})
        self.assertEqual(r.status_code, 421)

    def test_secret_redacted_in_access_log(self):
        rec = logging.LogRecord("uvicorn.access", logging.INFO, "", 0, '%s - "%s %s HTTP/%s" %d',
                                ("127.0.0.1:5", "POST", f"/mcp/{self.SECRET}", "1.1", 200), None)
        for f in logging.getLogger("uvicorn.access").filters:
            f.filter(rec)
        self.assertNotIn(self.SECRET, rec.getMessage())
        self.assertIn("/mcp/<secret>", rec.getMessage())

    def test_ingest_token_does_not_open_mcp(self):
        self.assertEqual(self.rpc("tools/list", path="/mcp/" + "t" * 40).status_code, 404)


if __name__ == "__main__":
    unittest.main()
