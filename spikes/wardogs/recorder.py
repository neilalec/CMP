"""Record raw, timestamped WDRCON observations in an isolated evidence session."""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.parse
from pathlib import Path

from evidence import EvidenceSession, utc_now
from probe import WDRCONClient, WDRCONError, changes, has_route


READ_STREAMS = (("status", "/v1/status", "status.jsonl"),
                ("players", "/v1/players", "players.jsonl"),
                ("rotation", "/v1/rotation", "rotation.jsonl"))


def session_directory(root: str | Path = "spikes/wardogs/evidence") -> Path:
    return Path(root) / datetime_session_id()


def datetime_session_id() -> str:
    return utc_now().replace(":", "").replace("-", "").replace(".", "").replace("Z", "Z")


def safe_origin(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc.split("@")[-1], "", "", ""))


class Recorder:
    def __init__(self, client: WDRCONClient, directory: str | Path, *, interval: float,
                 options: dict | None = None):
        if interval < 0:
            raise ValueError("poll interval must be nonnegative")
        self.client, self.evidence, self.interval = client, EvidenceSession(directory), interval
        self.options = options or {}
        self.capabilities: dict = {}
        self.previous: dict | None = None

    def start(self) -> None:
        """Capture negotiation data before polling; unsupported optional routes stay absent."""
        started = utc_now()
        try:
            self.capabilities = self.client.capabilities()
            self.evidence.write_json("capabilities.json", self.capabilities)
        except WDRCONError as exc:
            self.evidence.observation("events.jsonl", "/v1/capabilities", error=exc.as_dict())
            self.evidence.write_json("capabilities.json", {"error": exc.as_dict()})
        metadata = {"utcStarted": started, "origin": safe_origin(self.client.url),
                    "recorderPollingIntervalSeconds": self.interval,
                    "commandLineOptions": self.options,
                    "apiVersion": self.capabilities.get("apiVersion"),
                    "serverBuild": self.capabilities.get("build"),
                    "advertisedRoutes": self.capabilities.get("routes", []),
                    "advertisedRateLimits": self.capabilities.get("limits", {})}
        if has_route(self.capabilities, "GET", "/v1/server-id"):
            try:
                server_id = self.client.request("GET", "/v1/server-id")
                metadata["serverId"] = server_id
                self.evidence.observation("events.jsonl", "/v1/server-id", response=server_id)
            except WDRCONError as exc:
                self.evidence.observation("events.jsonl", "/v1/server-id", error=exc.as_dict())
        self.evidence.write_json("metadata.json", metadata)

    def poll_once(self) -> dict:
        current = {"observations": {}, "errors": {}}
        for key, endpoint, stream in READ_STREAMS:
            if not has_route(self.capabilities, "GET", endpoint):
                continue
            try:
                response = self.client.request("GET", endpoint)
                current["observations"][key] = response
                self.evidence.observation(stream, endpoint, response=response)
            except WDRCONError as exc:
                error = exc.as_dict()
                current["errors"][key] = error
                self.evidence.observation(stream, endpoint, error=error)
        if self.previous is not None:
            delta = changes(self.previous, current)
            if delta:
                self.evidence.append("events.jsonl", {"timestamp": utc_now(), "source": "recorder",
                    "kind": "DERIVED CANDIDATE", "candidateChanges": delta,
                    "note": "Polling comparison only; not an authoritative match lifecycle event."})
        self.previous = current
        return current

    def finish(self) -> None:
        summary = "# WARDOGS evidence session\n\n"
        summary += "Raw observations are timestamped JSON Lines. Entries marked `DERIVED CANDIDATE` are heuristics, not authoritative match start/end or result signals.\n"
        (self.evidence.directory / "summary.md").write_text(summary, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-root", default="spikes/wardogs/evidence")
    parser.add_argument("--interval", type=float, default=5.0, help="seconds; conservative default")
    parser.add_argument("--samples", type=int, default=0, help="0 polls until Ctrl+C")
    args = parser.parse_args()
    if args.samples < 0:
        parser.error("--samples must be zero or positive")
    url = os.getenv("WDRCON_URL") or f"http://{os.getenv('WDRCON_HOST', '127.0.0.1')}:{os.getenv('WDRCON_PORT', '7776')}"
    try:
        recorder = Recorder(WDRCONClient(url, os.getenv("WDRCON_PASSWORD", ""),
                                         float(os.getenv("WDRCON_TIMEOUT", "5"))),
                            session_directory(args.evidence_root), interval=args.interval,
                            options={"samples": args.samples, "interval": args.interval})
        recorder.start()
        print(recorder.evidence.directory)
        count = 0
        while not args.samples or count < args.samples:
            recorder.poll_once(); count += 1
            if not args.samples or count < args.samples:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        pass
    except (ValueError, WDRCONError) as exc:
        print(json.dumps({"error": exc.as_dict() if isinstance(exc, WDRCONError) else {"message": str(exc)}}))
        return 2
    finally:
        if "recorder" in locals():
            recorder.finish()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
