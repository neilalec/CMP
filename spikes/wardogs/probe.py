"""Standalone, standard-library WDRCON probe. No CMP imports or server credentials in code."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


class WDRCONError(Exception):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None,
                 retry_after: str | None = None):
        super().__init__(message)
        self.status, self.code, self.retry_after = status, code, retry_after

    def as_dict(self) -> dict:
        return {"message": str(self), "httpStatus": self.status, "code": self.code,
                "retryAfter": self.retry_after}


class WDRCONClient:
    def __init__(self, url: str, password: str, timeout: float = 5):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.path not in ("", "/"):
            raise ValueError("WDRCON_URL must be an http(s) origin without a path")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("WDRCON_URL must not contain credentials, query or fragment")
        if not password:
            raise ValueError("Set WDRCON_PASSWORD")
        self.url, self.password, self.timeout = url.rstrip("/"), password, timeout

    def request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Authorization": f"Bearer {self.password}", "Accept": "application/json"}
        if body is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.url + path, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read()
                result = json.loads(raw) if raw else {}
                if not isinstance(result, dict):
                    raise WDRCONError("Expected a JSON object")
                return result
        except urllib.error.HTTPError as exc:
            try:
                payload = json.loads(exc.read())
                error = payload.get("error", {})
            except (ValueError, AttributeError):
                error = {}
            raise WDRCONError(error.get("message", f"HTTP {exc.code}"), status=exc.code,
                               code=error.get("code"), retry_after=exc.headers.get("Retry-After")) from None
        except urllib.error.URLError as exc:
            raise WDRCONError(f"Connection failed: {exc.reason}") from None

    def capabilities(self) -> dict:
        return self.request("GET", "/v1/capabilities")


def has_route(capabilities: dict, method: str, path: str) -> bool:
    # Live builds advertise player placeholders as {id}; docs and mocks may use {steamId}.
    target = f"{method} {path}"
    routes = capabilities.get("routes", [])
    if target in routes:
        return True
    if "{steamId}" in target:
        return target.replace("{steamId}", "{id}") in routes
    return False


def snapshot(client: WDRCONClient, capabilities: dict | None = None) -> dict:
    caps = capabilities or client.capabilities()
    result = {"capabilities": caps, "observations": {}, "errors": {}}
    for key, path in (("status", "/v1/status"), ("players", "/v1/players"),
                      ("rotation", "/v1/rotation"), ("maps", "/v1/catalog/maps")):
        if not has_route(caps, "GET", path):
            result["errors"][key] = {"code": "route_not_advertised"}
            continue
        try:
            result["observations"][key] = client.request("GET", path)
        except WDRCONError as exc:
            result["errors"][key] = exc.as_dict()
    return result


def changes(previous: dict, current: dict) -> dict:
    """Report observable deltas only; never label a poll as a definitive match boundary."""
    old, new = previous.get("observations", {}), current.get("observations", {})
    result = {}
    if "status" in old and "status" in new:
        a, b = old["status"], new["status"]
        if a.get("map") != b.get("map"):
            result["mapChanged"] = {"from": a.get("map"), "to": b.get("map")}
        af = {x.get("name"): x.get("score") for x in a.get("factionScores", [])}
        bf = {x.get("name"): x.get("score") for x in b.get("factionScores", [])}
        if af != bf:
            result["factionScoresChanged"] = {"from": af, "to": bf}
        if "matchSeconds" in a and "matchSeconds" in b and b["matchSeconds"] < a["matchSeconds"]:
            result["matchClockResetCandidate"] = True
    if "players" in old and "players" in new:
        a = {str(x.get("steamId")): x for x in old["players"].get("players", [])}
        b = {str(x.get("steamId")): x for x in new["players"].get("players", [])}
        result["connectedSteamIds"] = sorted(b.keys() - a.keys())
        result["disconnectedSteamIds"] = sorted(a.keys() - b.keys())
        result["factionChanges"] = {sid: {"from": a[sid].get("faction"), "to": b[sid].get("faction")}
                                    for sid in a.keys() & b.keys() if a[sid].get("faction") != b[sid].get("faction")}
    return result


def action(client: WDRCONClient, caps: dict, args: argparse.Namespace) -> dict:
    if not args.confirm_mutation:
        raise ValueError("Mutations require --confirm-mutation")
    if args.action == "map":
        method, template, path = "POST", "/v1/match/map", "/v1/match/map"
        body = {"map": args.map}
        if args.experience:
            body["experiences"] = args.experience
        if args.lighting:
            body["lighting"] = args.lighting
        if args.alternator:
            body["zoneAlternator"] = args.alternator
    elif args.action == "assign":
        method, template = "PATCH", "/v1/players/{steamId}"
        path = "/v1/players/" + urllib.parse.quote(args.steam_id, safe="")
        body = {"faction": args.faction}
    else:
        method, template, path = "POST", f"/v1/match/{args.action}", f"/v1/match/{args.action}"
        body = None
    if not has_route(caps, method, template):
        raise WDRCONError(f"{method} {template} is not advertised by this build", code="route_not_advertised")
    return {"request": {"method": method, "path": path, "body": body},
            "acceptedResponse": client.request(method, path, body),
            "verification": "Response confirms request acceptance only; observe subsequent state separately."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot", help="Read capabilities, status, players, rotation and maps")
    watch = sub.add_parser("watch", help="Poll state and report observable deltas")
    watch.add_argument("--samples", type=int, default=3)
    watch.add_argument("--interval", type=float, default=2)
    act = sub.add_parser("action", help="Explicit, capability-gated mutation")
    act.add_argument("action", choices=("map", "assign", "restart", "end"))
    act.add_argument("--map")
    act.add_argument("--experience", action="append")
    act.add_argument("--lighting")
    act.add_argument("--alternator")
    act.add_argument("--steam-id")
    act.add_argument("--faction")
    act.add_argument("--confirm-mutation", action="store_true")
    args = parser.parse_args()
    try:
        url = os.getenv("WDRCON_URL") or f"http://{os.getenv('WDRCON_HOST', '127.0.0.1')}:{os.getenv('WDRCON_PORT', '7776')}"
        client = WDRCONClient(url, os.getenv("WDRCON_PASSWORD", ""), float(os.getenv("WDRCON_TIMEOUT", "5")))
        if args.command == "snapshot":
            output = snapshot(client)
        elif args.command == "watch":
            if args.samples < 1 or args.interval < 0:
                raise ValueError("--samples must be positive and --interval nonnegative")
            caps = client.capabilities()
            previous = None
            for sample in range(args.samples):
                current = snapshot(client, caps)
                print(json.dumps({"sample": sample + 1, "observation": current["observations"],
                                  "errors": current["errors"],
                                  "changes": changes(previous, current) if previous else {}}, sort_keys=True), flush=True)
                previous = current
                if sample + 1 < args.samples:
                    time.sleep(args.interval)
            return 0
        else:
            if args.action == "map" and not args.map or args.action == "assign" and not (args.steam_id and args.faction):
                raise ValueError("map requires --map; assign requires --steam-id and --faction")
            output = action(client, client.capabilities(), args)
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0
    except (ValueError, WDRCONError) as exc:
        print(json.dumps({"error": exc.as_dict() if isinstance(exc, WDRCONError) else {"message": str(exc)}}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
