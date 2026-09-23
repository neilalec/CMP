"""Read-only, server-scoped WDRCON client. No CMP runtime or Squad imports."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request

from services.game_server_contracts import (
    ALL_CAPABILITIES, Capability, LifecycleObservation, LifecycleState,
    ServerCapabilities,
)
from .errors import WDRCONError
from .parsing import (
    mark_read_observed, parse_capabilities, parse_players, parse_rotation,
    parse_status, utc_now,
    parse_server_join_id,
)


MAX_RESPONSE_BYTES = 2 * 1024 * 1024
_SAFE_ERROR_CODE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _retry_after_seconds(header: str | None) -> float | None:
    try:
        seconds = float(header)
        return seconds if 0 <= seconds <= 86400 else None
    except (TypeError, ValueError):
        return None


class WDRCONClient:
    """Only fixed GET paths are exposed; the powerful RCON credential stays server-side."""

    def __init__(self, base_url: str, password: str, *, timeout: float = 5,
                 opener=None):
        if not isinstance(base_url, str) or any(char in base_url for char in "\r\n\t"):
            raise ValueError("WDRCON base URL must be a plain HTTP(S) origin")
        parsed = urllib.parse.urlsplit(base_url)
        try:
            valid_port = parsed.port is None or parsed.port > 0
        except ValueError:
            valid_port = False
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname or
                not valid_port or parsed.path not in {"", "/"} or parsed.query or
                parsed.fragment or parsed.username or parsed.password):
            raise ValueError("WDRCON base URL must be an HTTP(S) origin without credentials or path")
        if not isinstance(password, str) or not password or any(char in password for char in "\r\n"):
            raise ValueError("WDRCON password is required")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or timeout <= 0:
            raise ValueError("WDRCON timeout must be positive")
        self._base_url = base_url.rstrip("/")
        self._password = password
        self._timeout = timeout
        self._opener = opener or urllib.request.urlopen
        self._capabilities = ServerCapabilities(
            capabilities={name: Capability() for name in ALL_CAPABILITIES}
        )

    @property
    def capability_snapshot(self) -> ServerCapabilities:
        return self._capabilities

    def _get(self, path: str) -> dict:
        request = urllib.request.Request(
            self._base_url + path,
            headers={"Authorization": f"Bearer {self._password}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with self._opener(request, timeout=self._timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            code = None
            try:
                body = json.loads(exc.read(MAX_RESPONSE_BYTES + 1))
                candidate = (body.get("error") or {}).get("code") if isinstance(body, dict) else None
                if isinstance(candidate, str) and _SAFE_ERROR_CODE.fullmatch(candidate):
                    code = candidate
            except (ValueError, AttributeError, TypeError):
                pass
            retry_header = exc.headers.get("Retry-After") if exc.headers else None
            raise WDRCONError("HTTP error", status=exc.code, code=code,
                               retry_after_seconds=_retry_after_seconds(retry_header)) from None
        except (urllib.error.URLError, TimeoutError, OSError):
            # urllib's reason may contain the URL or sensitive server text.
            raise WDRCONError("connection failure") from None
        if len(raw) > MAX_RESPONSE_BYTES:
            raise WDRCONError("response too large")
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise WDRCONError("invalid JSON") from None
        if not isinstance(payload, dict):
            raise WDRCONError("invalid JSON object")
        return payload

    def fetch_capabilities(self) -> ServerCapabilities:
        payload = self._get("/v1/capabilities")
        snapshot = parse_capabilities(payload)
        self._capabilities = snapshot
        return snapshot

    def fetch_status(self):
        status = parse_status(self._get("/v1/status"))
        names = ["server_status"]
        if status.faction_scores:
            names.append("faction_scores")
        if status.map_id or status.experiences or status.lighting or status.alternator:
            names.append("map_config")
        self._capabilities = mark_read_observed(
            self._capabilities, tuple(names), observed_at=status.observed_at,
            evidence="GET /v1/status",
        )
        return status

    def fetch_players(self):
        snapshot = parse_players(self._get("/v1/players"))
        names = ["players"]
        if any(player.steam_id for player in snapshot.players):
            names.append("steam_identity")
        if any(player.faction for player in snapshot.players):
            names.append("faction_assignment_read")
        self._capabilities = mark_read_observed(
            self._capabilities, tuple(names), observed_at=snapshot.observed_at,
            evidence="GET /v1/players",
        )
        return snapshot

    def fetch_rotation(self):
        rotation = parse_rotation(self._get("/v1/rotation"))
        self._capabilities = mark_read_observed(
            self._capabilities, ("rotation",), observed_at=rotation.observed_at,
            evidence="GET /v1/rotation",
        )
        return rotation

    def fetch_server_join_id(self) -> str:
        join_id = parse_server_join_id(self._get("/v1/server-id"))
        self._capabilities = mark_read_observed(
            self._capabilities, ("server_join_id",), observed_at=utc_now(),
            evidence="GET /v1/server-id; returned ID resolved in live WARDOGS Join By ID and player joined",
        )
        return join_id

    def observe_lifecycle(self) -> LifecycleObservation:
        # No verified WDRCON read currently establishes start/end or finality.
        return LifecycleObservation(LifecycleState.UNKNOWN, utc_now(), "wdrcon_read_only")
