"""Phase 2 Server 测试。

运行（在 server/ 目录，需要 requirements.txt 里的依赖 + httpx）：
  python3 -m unittest test_server.py
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from store import OFFLINE_AFTER, Store

T0 = 1790400000.0


def song(title="终身美丽", duration=206.0, **kw):
    return {"title": title, "artist": "郑秀文", "album": "Shocking Pink", "duration": duration, **kw}


def playing(t, pos, **kw):
    return {"status": "playing", "playing": True, "position": pos, "position_confirmed": True,
            "observed_at": t, "sent_at": t, "reason": kw.pop("reason", "heartbeat"), **song(**kw)}


def paused(t, pos, **kw):
    return dict(playing(t, pos, **kw), status="paused", playing=False)


def hidden(t, status="occluded", last_known=None):
    return {"status": status, "title": None, "artist": None, "album": None, "duration": None,
            "position": None, "playing": None, "observed_at": t, "sent_at": t, "reason": "visibility",
            "last_known": last_known}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self.s = Store(":memory:")

    def feed(self, p, recv=None):
        return self.s.ingest(p, p["observed_at"] if recv is None else recv)

    def test_extrapolates_only_while_playing(self):
        self.feed(playing(T0, 10))
        self.assertEqual(self.s.state(T0 + 5)["position"], 15)
        self.feed(paused(T0 + 20, 30, reason="play_state"))
        st = self.s.state(T0 + 50)
        self.assertEqual((st["status"], st["position"], st["playing"]), ("paused", 30, False))

    def test_position_clamped_to_duration(self):
        self.feed(playing(T0, 200))
        self.assertEqual(self.s.state(T0 + 30)["position"], 206)

    def test_null_position_stays_null(self):
        self.feed(dict(paused(T0, 0), position=None, position_confirmed=False))
        st = self.s.state(T0 + 1)
        self.assertIsNone(st["position"])
        self.assertFalse(st["position_confirmed"])

    def test_occluded_is_unknown_and_not_counted(self):
        self.feed(playing(T0, 0))
        self.feed(playing(T0 + 30, 30))
        lk = {"stale": True, **song(), "position": 31.0, "playing": True, "observed_at": T0 + 31}
        self.feed(hidden(T0 + 31, last_known=lk))
        st = self.s.state(T0 + 60)
        self.assertEqual(st["status"], "occluded")
        self.assertIsNone(st["playing"])
        self.assertIsNone(st["title"])
        self.assertEqual(st["last_known"]["title"], "终身美丽")
        self.assertTrue(st["last_known"]["stale"])
        # 遮挡 60 秒后同一首歌重新可见：还是同一段，遮挡期间不计时
        self.feed(playing(T0 + 91, 91, reason="visibility"))
        self.feed(playing(T0 + 101, 101))
        st = self.s.state(T0 + 101)
        self.assertEqual(len(st["recent_plays"]), 1)
        self.assertAlmostEqual(st["current_play"]["listened_seconds"], 41, delta=0.2)

    def test_offline_after_threshold(self):
        self.feed(playing(T0, 10))
        st = self.s.state(T0 + OFFLINE_AFTER + 1)
        self.assertEqual(st["status"], "offline")
        self.assertIsNone(st["playing"])
        self.assertTrue(st["last_known"]["stale"])
        self.assertEqual(st["last_known"]["title"], "终身美丽")

    def test_track_change_and_play_index(self):
        self.feed(playing(T0, 0))
        self.feed(playing(T0 + 10, 0, title="Digital Love", duration=301.0, reason="track_change"))
        self.feed(playing(T0 + 20, 0, reason="track_change"))
        plays = self.s.state(T0 + 20)["recent_plays"]
        self.assertEqual([(p["title"], p["play_index"]) for p in plays],
                         [("终身美丽", 2), ("Digital Love", 1), ("终身美丽", 1)])
        self.assertEqual(plays[2]["end_reason"], "track_change")
        self.assertAlmostEqual(plays[2]["listened_seconds"], 10)

    def test_natural_loop_counts_new_play(self):
        self.feed(playing(T0, 190))
        self.feed(playing(T0 + 17, 1, reason="seek"))  # 190+17=207 ≥ 206，回到 1 秒
        st = self.s.state(T0 + 17)
        self.assertEqual([p["play_index"] for p in st["recent_plays"]], [2, 1])
        self.assertEqual(st["recent_plays"][1]["end_reason"], "loop")

    def test_manual_seek_to_start_is_same_play(self):
        self.feed(playing(T0, 60))
        self.feed(playing(T0 + 5, 0, reason="seek"))  # 听前奏
        st = self.s.state(T0 + 5)
        self.assertEqual(len(st["recent_plays"]), 1)
        self.assertEqual(st["position"], 0)

    def test_untrusted_client_clock(self):
        with self.assertLogs("samebeat.store", "WARNING"):
            self.feed(playing(T0 - 100, 10), recv=T0)
        st = self.s.state(T0 + 5)
        self.assertTrue(st["clock_untrusted"])
        self.assertEqual(st["position"], 15)  # 以 received_at 为基准

    def test_small_clock_skew_kept(self):
        self.feed(playing(T0 - 2, 10), recv=T0)
        st = self.s.state(T0)
        self.assertFalse(st["clock_untrusted"])
        self.assertEqual(st["position"], 12)

    def test_listened_only_confirmed_playing(self):
        self.feed(playing(T0, 0))
        self.feed(paused(T0 + 30, 30, reason="play_state"))
        self.feed(playing(T0 + 90, 30, reason="play_state"))  # 暂停 60 秒不算
        self.feed(playing(T0 + 90 + OFFLINE_AFTER + 60, 60))  # Agent 掉线期间不算
        st = self.s.state(T0 + 90 + OFFLINE_AFTER + 60)
        self.assertAlmostEqual(st["current_play"]["listened_seconds"], 30)

    def test_older_report_ignored(self):
        self.feed(playing(T0 + 10, 10))
        self.assertFalse(self.feed(paused(T0, 0))["accepted"])
        self.assertEqual(self.s.state(T0 + 10)["status"], "playing")

    def test_paused_without_playing_opens_no_play(self):
        self.feed(dict(paused(T0, 0), position=None, position_confirmed=False, reason="startup"))
        st = self.s.state(T0 + 1)
        self.assertEqual((st["status"], st["current_play"], st["recent_plays"]), ("paused", None, []))
        self.feed(playing(T0 + 10, 0, reason="play_state"))
        self.assertEqual(self.s.state(T0 + 10)["current_play"]["play_index"], 1)

    def test_idle_closes_play(self):
        self.feed(playing(T0, 0))
        self.feed(paused(T0 + 20, 20, reason="play_state"))
        self.feed(hidden(T0 + 50, status="idle"))
        p = self.s.state(T0 + 50)["recent_plays"][0]
        self.assertEqual((p["ended_at"], p["end_reason"]), (T0 + 20, "idle"))


class ReplayTest(unittest.TestCase):
    """Phase 0 实录 → Phase 1 Agent 逻辑 → Server，端到端。"""

    def test_phase0_session(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
        import test_samebeat_agent

        s = Store(":memory:")
        for r in test_samebeat_agent.replay():
            s.ingest(dict(r, sent_at=r["observed_at"]), r["observed_at"])
        st = s.state(1790415890)
        blob = json.dumps(st, ensure_ascii=False)
        self.assertNotIn("OTHER_APP_PRIVATE_METADATA", blob)
        plays = list(reversed(st["recent_plays"]))
        self.assertEqual([(p["title"], p["play_index"]) for p in plays],
                         [("终身美丽", 1), ("Digital Love", 1), ("Blueming", 1), ("Digital Love", 2)])
        # Digital Love 第一段：两次被 B站遮挡的时间都不计
        self.assertLess(plays[1]["listened_seconds"], 300)
        self.assertEqual(st["status"], "playing")
        self.assertEqual(st["title"], "Digital Love")


class LoopReplayTest(unittest.TestCase):
    """2026-09-26 实测：QQ 单曲循环时的真实事件流（docs/fixtures/loop-stream.jsonl）。"""

    def test_real_single_track_loop(self):
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agent"))
        import test_samebeat_agent

        log = Path(__file__).resolve().parent.parent / "docs" / "fixtures" / "loop-stream.jsonl"
        s = Store(":memory:")
        for r in test_samebeat_agent.replay(log):
            s.ingest(dict(r, sent_at=r["observed_at"]), r["observed_at"])
        plays = s.state(1790431810)["recent_plays"]
        self.assertEqual([(p["title"], p["play_index"], p["end_reason"]) for p in plays],
                         [("Blueming", 2, None), ("Blueming", 1, "loop")])
        self.assertAlmostEqual(plays[1]["listened_seconds"], 8, delta=1.5)


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        os.environ["SAMEBEAT_TOKEN"] = "t" * 40
        os.environ["SAMEBEAT_MCP_SECRET"] = "s" * 48
        os.environ["SAMEBEAT_DB"] = os.path.join(cls.tmp.name, "s.db")
        import importlib
        from fastapi.testclient import TestClient
        import app
        cls.c = TestClient(importlib.reload(app).app)
        cls.auth = {"Authorization": "Bearer " + "t" * 40}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_auth_required(self):
        import time
        body = playing(time.time(), 1)
        self.assertEqual(self.c.post("/ingest", json=body).status_code, 401)
        self.assertEqual(self.c.post("/ingest", json=body, headers={"Authorization": "Bearer wrong"}).status_code, 401)
        self.assertEqual(self.c.get("/state").status_code, 401)
        self.assertEqual(self.c.post("/ingest", json=body, headers=self.auth).status_code, 200)
        st = self.c.get("/state", headers=self.auth).json()
        self.assertEqual(st["title"], "终身美丽")
        self.assertLessEqual(len(st["recent_plays"]), 5)

    def test_validation(self):
        import time
        bad = dict(playing(time.time(), 1), status="stopped")
        self.assertEqual(self.c.post("/ingest", json=bad, headers=self.auth).status_code, 422)
        no_title = dict(playing(time.time(), 1), title=None)
        self.assertEqual(self.c.post("/ingest", json=no_title, headers=self.auth).status_code, 422)


if __name__ == "__main__":
    unittest.main()
