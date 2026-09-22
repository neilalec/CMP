import argparse
import contextlib
import io
import secrets
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

from feed_receiver import handler_for as feed_handler_for
from mock_server import MockState, handler_for
from probe import WDRCONClient, WDRCONError, action, changes, has_route, snapshot


class ProbeAgainstSyntheticFixture(unittest.TestCase):
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
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def setUp(self):
        self.client = WDRCONClient(self.url, self.password)
        self.state.map = "Kavkazi"
        self.state.pending_map = None
        self.state.scores = {"Valkyra": 34, "Lonestar": 27, "Manticore": 30}
        self.state.players[0]["faction"] = "Valkyra"

    def test_read_and_capability_negotiation(self):
        result = snapshot(self.client)
        self.assertEqual(result["errors"], {})
        self.assertEqual(result["observations"]["players"]["players"][0]["steamId"], "76561198000000001")
        self.assertNotIn("matchSeconds", result["observations"]["status"])
        caps = result["capabilities"]
        self.assertTrue(has_route(caps, "PATCH", "/v1/players/{steamId}"))
        self.assertFalse(has_route(caps, "POST", "/v1/rotation/entries"))

    def test_auth_and_unsupported_route_errors(self):
        with self.assertRaises(WDRCONError) as ctx:
            WDRCONClient(self.url, secrets.token_urlsafe(24)).capabilities()
        self.assertEqual((ctx.exception.status, ctx.exception.code), (401, "unauthorized"))
        with self.assertRaises(WDRCONError) as ctx:
            self.client.request("GET", "/v1/unknown")
        self.assertEqual((ctx.exception.status, ctx.exception.code), (404, "not_found"))

    def test_map_is_queued_and_end_changes_observed_map(self):
        caps = self.client.capabilities()
        before = snapshot(self.client, caps)
        args = argparse.Namespace(action="map", map="Europe", experience=None, lighting=None,
                                  alternator=None, confirm_mutation=True)
        action(self.client, caps, args)
        self.assertEqual(self.client.request("GET", "/v1/status")["map"], "Kavkazi")
        action(self.client, caps, argparse.Namespace(action="end", confirm_mutation=True))
        after = snapshot(self.client, caps)
        self.assertEqual(changes(before, after)["mapChanged"], {"from": "Kavkazi", "to": "Europe"})
        self.assertIn("factionScoresChanged", changes(before, after))
        self.assertNotIn("matchEnded", changes(before, after))

    def test_restart_response_does_not_prove_match_completion(self):
        caps = self.client.capabilities()
        before = snapshot(self.client, caps)
        result = action(self.client, caps, argparse.Namespace(action="restart", confirm_mutation=True))
        after = snapshot(self.client, caps)
        self.assertIn("message", result["acceptedResponse"])
        self.assertEqual(after["observations"]["status"]["map"], before["observations"]["status"]["map"])
        self.assertNotIn("matchEnded", changes(before, after))

    def test_roster_diff_is_observation_only(self):
        caps = self.client.capabilities()
        before = snapshot(self.client, caps)
        extra = {"name": "Fixture C", "steamId": "76561198000000003", "faction": "Manticore",
                 "kills": 0, "deaths": 0, "cash": 0, "pingMs": 50}
        self.state.players.append(extra)
        try:
            after = snapshot(self.client, caps)
            self.assertEqual(changes(before, after)["connectedSteamIds"], [extra["steamId"]])
            self.state.players.remove(extra)
            final = snapshot(self.client, caps)
            self.assertEqual(changes(after, final)["disconnectedSteamIds"], [extra["steamId"]])
        finally:
            if extra in self.state.players:
                self.state.players.remove(extra)

    def test_assign_requires_explicit_confirmation_and_is_observable(self):
        caps = self.client.capabilities()
        args = argparse.Namespace(action="assign", steam_id="76561198000000001", faction="Lonestar",
                                  confirm_mutation=False)
        with self.assertRaises(ValueError):
            action(self.client, caps, args)
        before = snapshot(self.client, caps)
        args.confirm_mutation = True
        action(self.client, caps, args)
        after = snapshot(self.client, caps)
        self.assertEqual(changes(before, after)["factionChanges"][args.steam_id]["to"], "Lonestar")


class FeedReceiverSyntheticPost(unittest.TestCase):
    def test_token_and_batch_shape(self):
        token = secrets.token_urlsafe(24)
        server = ThreadingHTTPServer(("127.0.0.1", 0), feed_handler_for(token))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/api/ingest/events"
        data = b'{"serverId":"fixture","events":[{"eventId":"fixture","type":"killed"}]}'
        try:
            captured = io.StringIO()
            with contextlib.redirect_stdout(captured):
                req = urllib.request.Request(url, data=data, headers={"Authorization": f"Bearer {token}"})
                with urllib.request.urlopen(req) as response:
                    self.assertEqual(response.status, 200)
            self.assertIn('"type":"killed"', captured.getvalue())
            req = urllib.request.Request(url, data=data, headers={"Authorization": "Bearer incorrect"})
            with self.assertRaises(urllib.error.HTTPError) as ctx:
                urllib.request.urlopen(req)
            self.assertEqual(ctx.exception.code, 401)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

if __name__ == "__main__":
    unittest.main()
