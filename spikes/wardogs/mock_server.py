"""Synthetic HTTP fixture for probe transport tests; it is not a WARDOGS emulator."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit


class MockState:
    def __init__(self, *, live_like: bool = True):
        self.live_like = live_like
        self.map = "Kavkazi"
        self.pending_map = None
        self.scores = {"Valkyra": 34, "Lonestar": 27, "Manticore": 30}
        self.players = [
            {"name": "Fixture A", "steamId": "76561198000000001", "faction": "Valkyra",
             "kills": 1, "deaths": 0, "cash": 100, "pingMs": 30},
            {"name": "Fixture B", "steamId": "76561198000000002", "faction": "Lonestar",
             "kills": 0, "deaths": 1, "cash": 50, "pingMs": 40},
        ]
        self.routes = ["GET /v1/capabilities", "GET /v1/status", "GET /v1/players",
                       "GET /v1/rotation", "GET /v1/server-id", "GET /v1/catalog/maps", "POST /v1/match/map",
                       "PATCH /v1/players/{id}", "POST /v1/match/restart", "POST /v1/match/end"]

    def status(self):
        value = {"serverName": "CMP WDRCON fixture", "map": self.map,
                 "experiences": ["Bakurani_KOTH_01"], "lighting": "DayClear", "alternator": "None",
                 "scoreTick": {"current": 24, "min": 18, "max": 30},
                 "players": {"current": len(self.players), "max": 32},
                 "factionScores": [{"name": name, "colorHex": color, "score": score}
                                   for (name, score), color in zip(self.scores.items(),
                                                                    ("#D86060", "#5B95D8", "#7BC462"))],
                 "rotation": {"nowIndex": 0, "nextIndex": 1}}
        if not self.live_like:
            value.update(scoreCap=100, matchSeconds=120)
        return value


def handler_for(state: MockState, password: str):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status: int, value: dict, extra_headers: dict | None = None):
            raw = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            for key, val in (extra_headers or {}).items():
                self.send_header(key, val)
            self.end_headers()
            self.wfile.write(raw)

        def error(self, status: int, code: str, message: str, extra_headers: dict | None = None):
            self.reply(status, {"error": {"code": code, "message": message}}, extra_headers)

        def handle_request(self):
            if self.headers.get("Authorization") != f"Bearer {password}":
                return self.error(401, "unauthorized", "Invalid RCON password")
            path = urlsplit(self.path).path
            method = self.command
            route = f"{method} {path}"
            if method == "GET":
                if path == "/v1/capabilities":
                    return self.reply(200, {"apiVersion": 1, "build": "synthetic-live-like" if state.live_like else "synthetic-full",
                                            "auth": {"scheme": "bearer", "header": "Authorization"},
                                            "limits": {"maxBodyBytes": 65536, "maxRequestsPerMinutePerIp": 600},
                                            "config": {"writable": False, "document": "/v1/config"},
                                            "routes": state.routes})
                if path == "/v1/status":
                    return self.reply(200, state.status())
                if path == "/v1/players":
                    return self.reply(200, {"players": state.players, "count": len(state.players)})
                if path == "/v1/rotation":
                    return self.reply(200, {"enabled": True, "mode": "ordered", "entries": [
                        {"index": 0, "map": state.map, "experiences": ["Bakurani_KOTH_01"],
                         "lighting": "DayClear", "status": "now", "denied": False},
                        {"index": 1, "map": "Europe", "experiences": ["Madrid_KOTH_01"],
                         "lighting": "DayClear", "status": "next", "denied": False}]})
                if path == "/v1/server-id":
                    return self.reply(200, {"serverId": "fixture-live-join-id"})
                if path == "/v1/catalog/maps":
                    return self.reply(200, {"maps": [{"id": "Kavkazi", "displayName": "Bakurani"},
                                                     {"id": "Europe", "displayName": "Ozeti"}]})
            if method in ("POST", "PATCH"):
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                    body = json.loads(self.rfile.read(length)) if length else {}
                    if not isinstance(body, dict):
                        raise ValueError
                except (ValueError, json.JSONDecodeError):
                    return self.error(400, "bad_request", "Expected JSON object")
                if route == "POST /v1/match/map":
                    if body.get("map") not in ("Kavkazi", "Europe"):
                        return self.error(400, "invalid_map", "Unknown map")
                    state.pending_map = body["map"]
                    return self.reply(200, {"message": "Map queued for the end of the match"})
                if route == "POST /v1/match/end":
                    state.map = state.pending_map or ("Europe" if state.map == "Kavkazi" else "Kavkazi")
                    state.pending_map = None
                    state.scores = dict.fromkeys(state.scores, 0)
                    return self.reply(200, {"message": "Match end requested"})
                if route == "POST /v1/match/restart":
                    state.scores = dict.fromkeys(state.scores, 0)
                    return self.reply(200, {"message": "Match restart requested"})
                if method == "PATCH" and path.startswith("/v1/players/"):
                    sid = path.removeprefix("/v1/players/")
                    player = next((p for p in state.players if p["steamId"] == sid), None)
                    if player is None:
                        return self.error(404, "player_not_found", "Player not found")
                    if body.get("faction") not in state.scores:
                        return self.error(400, "invalid_faction", "Unknown faction")
                    player["faction"] = body["faction"]
                    return self.reply(200, {"message": "Faction changed"})
            return self.error(404, "not_found", "No such endpoint.")

        do_GET = handle_request
        do_POST = handle_request
        do_PATCH = handle_request

    return Handler


def main():
    password = os.getenv("WDRCON_PASSWORD")
    if not password:
        raise SystemExit("Set WDRCON_PASSWORD for the mock")
    host = os.getenv("WDRCON_MOCK_BIND", "127.0.0.1")
    port = int(os.getenv("WDRCON_MOCK_PORT", "17776"))
    state = MockState(live_like=os.getenv("WDRCON_MOCK_VARIANT", "live-like") == "live-like")
    server = ThreadingHTTPServer((host, port), handler_for(state, password))
    print(f"Synthetic WDRCON fixture listening on http://{host}:{server.server_port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
