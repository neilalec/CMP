import json
import secrets
import tempfile
import threading
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer

from mock_server import MockState, handler_for
from probe import WDRCONClient
from recorder import Recorder


class RecorderAgainstSyntheticFixture(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.password = secrets.token_urlsafe(24)
        cls.state = MockState(live_like=True)
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(cls.state, cls.password))
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join(timeout=2)

    def setUp(self):
        self.state.map = "Kavkazi"
        self.state.scores = {"Valkyra": 34, "Lonestar": 27, "Manticore": 30}
        self.state.players[0]["faction"] = "Valkyra"
        self.temp = tempfile.TemporaryDirectory()
        self.recorder = Recorder(WDRCONClient(self.url, self.password), Path(self.temp.name) / "session",
                                 interval=5, options={"password": self.password})
        self.recorder.start()

    def tearDown(self):
        self.recorder.finish(); self.temp.cleanup()

    def lines(self, name):
        return [json.loads(line) for line in (self.recorder.evidence.directory / name).read_text().splitlines()]

    def test_records_metadata_repeated_raw_observations_and_deltas(self):
        self.recorder.poll_once()
        self.state.scores["Valkyra"] = 35
        self.state.players[0]["faction"] = "Lonestar"
        self.state.map = "Europe"
        self.recorder.poll_once()
        self.assertTrue((self.recorder.evidence.directory / "metadata.json").exists())
        self.assertEqual(len(self.lines("status.jsonl")), 2)
        self.assertEqual(len(self.lines("players.jsonl")), 2)
        candidates = [row for row in self.lines("events.jsonl") if row.get("kind") == "DERIVED CANDIDATE"]
        self.assertEqual(candidates[-1]["candidateChanges"]["mapChanged"]["to"], "Europe")
        self.assertIn("factionScoresChanged", candidates[-1]["candidateChanges"])
        self.assertIn("factionChanges", candidates[-1]["candidateChanges"])

    def test_same_map_score_reset_is_only_a_candidate_and_credentials_are_redacted(self):
        self.recorder.poll_once()
        self.state.scores = dict.fromkeys(self.state.scores, 0)
        self.recorder.poll_once()
        data = (self.recorder.evidence.directory / "metadata.json").read_text()
        self.assertNotIn(self.password, data)
        candidate = [row for row in self.lines("events.jsonl") if row.get("kind")][-1]
        self.assertEqual(candidate["kind"], "DERIVED CANDIDATE")
        self.assertEqual(self.state.map, "Kavkazi")
        self.assertTrue(candidate["candidateChanges"]["possibleRestartCandidate"])
        self.assertNotIn("matchEnded", candidate["candidateChanges"])

    def test_sanitized_action_and_error_are_written(self):
        self.recorder.evidence.action("restart", {"Authorization": "Bearer bad", "body": {"token": "bad"}},
                                      {"message": "accepted"})
        action_data = (self.recorder.evidence.directory / "actions.jsonl").read_text()
        self.assertNotIn("Bearer bad", action_data)
        self.recorder.capabilities = {"routes": ["GET /v1/status"]}
        self.recorder.client = WDRCONClient(self.url, "wrong-password")
        self.recorder.poll_once()
        self.assertEqual(self.lines("errors.jsonl")[-1]["error"]["httpStatus"], 401)


if __name__ == "__main__":
    unittest.main()
