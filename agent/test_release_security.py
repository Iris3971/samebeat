import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import urllib.error

from samebeat_agent import Config, NoRedirect, Sender, valid_server_url, QQTracker, QQ_BUNDLE

class ReleaseSecurityTest(unittest.TestCase):
    def test_only_exact_loopback_http(self):
        for url in ('http://localhost.evil.example/ingest', 'http://127.0.0.1.evil.example/ingest', 'http://example.com/ingest', 'https://user:pass@example.com/ingest', 'https://example.com/ingest?q=value', 'https://example.com:bad/ingest'):
            with self.subTest(url=url):self.assertFalse(valid_server_url(url))
        for url in ('', 'http://localhost:8766/ingest', 'http://127.0.0.1/ingest', 'http://[::1]/ingest', 'https://samebeat.example.com/ingest'):
            with self.subTest(url=url):self.assertTrue(valid_server_url(url))

    def test_bad_hot_reload_disables_sharing(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config.toml'
            p.write_text('server_url = "https://samebeat.example.com/ingest"\nsharing_enabled = true\n')
            cfg=Config(p);cfg.reload_if_changed()
            p.write_text('server_url = "http://localhost.evil.example/ingest"\nsharing_enabled = true\n')
            os.utime(p,(p.stat().st_atime,p.stat().st_mtime+2))
            cfg.reload_if_changed()
            self.assertFalse(cfg.sharing_enabled)
            self.assertEqual(cfg.server_url,'https://samebeat.example.com/ingest')

    def test_redirect_never_creates_forward_request(self):
        self.assertIsNone(NoRedirect().redirect_request(None,None,302,'redirect',{},'https://other.example/ingest'))

    def test_sender_uses_no_redirect_and_logs_no_error_details(self):
        cfg=Config(Path('unused'));cfg.server_url='https://samebeat.example.com/ingest';cfg.token='synthetic-test-value'
        with patch('samebeat_agent.urllib.request.build_opener') as build, patch('samebeat_agent.log') as log:
            build.return_value.open.side_effect=urllib.error.URLError('sensitive diagnostic value')
            self.assertFalse(Sender(cfg).send({'reason':'heartbeat','status':'playing'},1))
            self.assertIsInstance(build.call_args.args[0],NoRedirect)
            self.assertNotIn('sensitive diagnostic value',str(log.call_args_list))

class PositionProvenanceTest(unittest.TestCase):
    def tracker(self):
        tr=QQTracker()
        event={"bundleIdentifier":QQ_BUNDLE,"title":"Synthetic Track","artist":"Synthetic Artist",
               "durationMicros":200_000_000,"elapsedTimeMicros":10_000_000,
               "timestampEpochMicros":1_000_000_000,"playing":True}
        tr.on_event(event,event,1000)
        return tr,event

    def test_heartbeat_extrapolation_is_not_player_confirmation(self):
        tr,_=self.tracker()
        self.assertTrue(tr.snapshot(1000)["position_confirmed"])
        self.assertFalse(tr.snapshot(1030)["position_confirmed"])
        self.assertEqual(tr.snapshot(1030)["position"],40)

    def test_pause_without_progress_freezes_estimate(self):
        tr,event=self.tracker()
        event["playing"]=False
        tr.on_event(event,{"playing":False},1020)
        snap=tr.snapshot(1050)
        self.assertEqual(snap["position"],30)
        self.assertFalse(snap["position_confirmed"])
