"""用 Phase 0 实录的事件流（docs/fixtures/phase0-stream.jsonl）回放测试 Agent 的状态逻辑。

运行：python3 -m unittest agent/test_samebeat_agent.py
"""

import json
import unittest
from pathlib import Path

from samebeat_agent import QQTracker, RawMirror, Reporter

LOG = Path(__file__).resolve().parent.parent / "docs" / "fixtures" / "phase0-stream.jsonl"
DEBOUNCE = 0.8
HEARTBEAT = 30.0


def replay(log=LOG):
    """按录制时的接收时间回放，每 0.25 秒 tick 一次，返回所有上报。"""
    events = [json.loads(l) for l in Path(log).read_text().splitlines() if l.strip()]
    mirror, tracker = RawMirror(), QQTracker()
    reporter = Reporter(tracker)
    reports = []

    def tick_until(t_end, t):
        while t < t_end:
            snap = reporter.due(t, DEBOUNCE, HEARTBEAT)
            if snap:
                reports.append(snap)
                reporter.mark_sent(snap, t)
            t += 0.25
        return t

    t = events[0]["recv"]
    for ev in events:
        t = tick_until(ev["recv"], t)
        delta = mirror.apply(ev["raw"])
        if delta is not None:
            tracker.on_event(mirror.state, delta, ev["recv"])
    tick_until(events[-1]["recv"] + 5, t)
    return reports


class ReplayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reports = replay()

    def find(self, pred):
        return [r for r in self.reports if pred(r)]

    def test_never_uploads_other_app_media(self):
        blob = json.dumps(self.reports, ensure_ascii=False)
        self.assertNotIn("org.example.otherplayer", blob)
        self.assertNotIn("OTHER_APP_PRIVATE_METADATA", blob)

    def test_first_play(self):
        r = self.find(lambda r: r["title"] == "终身美丽" and r["status"] == "playing")[0]
        self.assertEqual(r["artist"], "郑秀文")
        self.assertEqual(r["duration"], 206)

    def test_pause_freezes_position(self):
        # Iris 暂停时 QQ 显示 1:09（findings §3）
        r = self.find(lambda r: r["title"] == "终身美丽" and r["status"] == "paused")[0]
        self.assertAlmostEqual(r["position"], 69, delta=1)

    def test_seek(self):
        r = self.find(lambda r: r["reason"] == "seek" and r["title"] == "终身美丽")[0]
        self.assertAlmostEqual(r["position"], 150, delta=1.5)

    def test_track_change_without_transient_pause(self):
        # 切歌时的「暂停 0.02 秒」不能被上报（findings 4.5）
        titles = [(r["title"], r["status"]) for r in self.reports if r["title"]]
        idx = titles.index(("Digital Love", "playing"))
        self.assertEqual(titles[idx - 1], ("终身美丽", "playing"))

    def test_occluded_is_unknown_not_stopped(self):
        occ = self.find(lambda r: r["status"] == "occluded")
        self.assertTrue(occ)
        for r in occ:
            self.assertIsNone(r["playing"])
            self.assertIsNone(r["title"])
            self.assertTrue(r["last_known"]["stale"])
            self.assertEqual(r["last_known"]["title"], "Digital Love")

    def test_stale_replay_discarded(self):
        # 从 B站切回 QQ 时先重放的是旧缓存（elapsed 0），真实进度是 1:04（findings 4.3）
        back = [r for i, r in enumerate(self.reports)
                if r["title"] == "Digital Love" and i > 0 and self.reports[i - 1]["status"] == "occluded"]
        self.assertAlmostEqual(back[0]["position"], 64, delta=1.5)

    def test_position_survives_occlusion(self):
        # B站占住两分多钟后，远程暂停时 Iris 看到 3:46
        r = self.find(lambda r: r["title"] == "Digital Love" and r["status"] == "paused"
                      and (r["position"] or 0) > 200)[0]
        self.assertAlmostEqual(r["position"], 226, delta=1.5)

    def test_seek_by_command(self):
        r = self.find(lambda r: r["reason"] == "seek" and r["title"] == "Digital Love"
                      and r["position"] is not None and r["position"] < 70)[0]
        self.assertAlmostEqual(r["position"], 60, delta=1.5)

    def test_next_and_previous(self):
        titles = [r["title"] for r in self.reports if r["reason"] == "track_change"]
        self.assertIn("Blueming", titles)
        self.assertEqual(titles[-1], "Digital Love")

    def test_heartbeat_only_every_30s(self):
        hb = [r["observed_at"] for r in self.reports if r["reason"] == "heartbeat"]
        for a, b in zip(hb, hb[1:]):
            self.assertGreaterEqual(b - a, HEARTBEAT - 0.5)


if __name__ == "__main__":
    unittest.main()
