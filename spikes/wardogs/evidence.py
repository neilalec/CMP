"""Small, credential-safe writer for WARDOGS evidence bundles."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SENSITIVE_KEYS = {"password", "token", "authorization", "secret", "api_key", "apikey"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(value: Any) -> Any:
    """Remove credentials even if a server unexpectedly echoes them."""
    if isinstance(value, dict):
        return {str(key): "[REDACTED]" if str(key).lower().replace("-", "_") in SENSITIVE_KEYS
                else sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


class EvidenceSession:
    def __init__(self, directory: str | Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def write_json(self, name: str, value: Any) -> None:
        (self.directory / name).write_text(json.dumps(sanitize(value), indent=2, sort_keys=True) + "\n",
                                             encoding="utf-8")

    def append(self, name: str, value: dict) -> None:
        with (self.directory / name).open("a", encoding="utf-8") as output:
            output.write(json.dumps(sanitize(value), separators=(",", ":"), sort_keys=True) + "\n")

    def observation(self, stream: str, endpoint: str, *, response: Any = None,
                    error: Any = None, source: str = "wdrcon") -> None:
        entry = {"timestamp": utc_now(), "source": source, "endpoint": endpoint,
                 "success": error is None}
        if error is None:
            entry["response"] = response
        else:
            entry["error"] = error
            self.append("errors.jsonl", entry)
        self.append(stream, entry)

    def action(self, action_type: str, request: dict, acknowledgement: Any,
               subsequent_state: Any = None) -> None:
        entry = {"timestamp": utc_now(), "actionType": action_type,
                 "request": request, "httpAcknowledgement": acknowledgement}
        if subsequent_state is not None:
            entry["subsequentObservedState"] = subsequent_state
        self.append("actions.jsonl", entry)
