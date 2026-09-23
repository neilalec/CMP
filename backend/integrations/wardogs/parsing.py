"""Translate WDRCON JSON into CMP observation contracts."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

from services.game_server_contracts import (
    ALL_CAPABILITIES, LIFECYCLE_CAPABILITIES,
    Capability, CapabilityState, FactionScore, PlayerSnapshot, RotationEntry,
    RotationSnapshot, ScoreTick, ServerCapabilities, ServerPlayer, ServerStatus,
)
from .errors import WDRCONPayloadError


ROUTES = {
    "server_status": "GET /v1/status",
    "players": "GET /v1/players",
    "steam_identity": "GET /v1/players",
    "faction_assignment_read": "GET /v1/players",
    "faction_scores": "GET /v1/status",
    "rotation": "GET /v1/rotation",
    "map_config": "GET /v1/status",
    "broadcast": "POST /v1/broadcast",
    "faction_assignment_write": "PATCH /v1/players/{id}",
    "map_change": "POST /v1/match/map",
    "restart_match": "POST /v1/match/restart",
    "end_match": "POST /v1/match/end",
    "kick_player": "POST /v1/players/{id}/kick",
}


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _object(value, name: str) -> dict:
    if not isinstance(value, dict):
        raise WDRCONPayloadError(f"{name} must be an object")
    return value


def _list(value, name: str) -> list:
    if not isinstance(value, list):
        raise WDRCONPayloadError(f"{name} must be an array")
    return value


def _text(value, name: str, *, required: bool = False) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, str) or (required and not value.strip()):
        raise WDRCONPayloadError(f"{name} must be a string")
    return value.strip() or None


def _integer(value, name: str, *, required: bool = False) -> int | None:
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise WDRCONPayloadError(f"{name} must be an integer")
    return value


def _boolean(value, name: str) -> bool | None:
    if value is None:
        return None
    if not isinstance(value, bool):
        raise WDRCONPayloadError(f"{name} must be a boolean")
    return value


def _experiences(value) -> tuple[str, ...]:
    if value is None:
        return ()
    return tuple(_text(item, "experience", required=True) for item in _list(value, "experiences"))


def parse_capabilities(payload: dict, *, observed_at: datetime | None = None) -> ServerCapabilities:
    body = _object(payload, "capabilities")
    routes = _list(body.get("routes"), "routes")
    if any(not isinstance(route, str) for route in routes):
        raise WDRCONPayloadError("routes must contain strings")
    advertised = set(routes)
    # The live build uses {id}; older documentation/mocks may use {steamId}.
    advertised = {route.replace("{steamId}", "{id}") for route in advertised}
    limits = _object(body.get("limits") or {}, "limits")
    at = observed_at or utc_now()
    states = {}
    for name in ALL_CAPABILITIES:
        if name in LIFECYCLE_CAPABILITIES:
            state = CapabilityState.UNKNOWN
        else:
            state = CapabilityState.ADVERTISED if ROUTES[name] in advertised else CapabilityState.UNAVAILABLE
        states[name] = Capability(state=state, observed_at=at, evidence="route list" if state == CapabilityState.ADVERTISED else None)
    return ServerCapabilities(
        api_version=_integer(body.get("apiVersion"), "apiVersion"),
        build=_text(body.get("build"), "build"),
        max_requests_per_minute_per_ip=_integer(limits.get("maxRequestsPerMinutePerIp"), "maxRequestsPerMinutePerIp"),
        max_body_bytes=_integer(limits.get("maxBodyBytes"), "maxBodyBytes"),
        capabilities=states,
        observed_at=at,
    )


def mark_read_observed(snapshot: ServerCapabilities | None, names: tuple[str, ...],
                       *, observed_at: datetime, evidence: str) -> ServerCapabilities:
    snapshot = snapshot or ServerCapabilities(capabilities={name: Capability() for name in ALL_CAPABILITIES})
    updated = dict(snapshot.capabilities)
    for name in names:
        # A successful read, not advertisement, is what advances read confidence.
        updated[name] = Capability(CapabilityState.OBSERVED, observed_at, evidence)
    return replace(snapshot, capabilities=updated)


def parse_status(payload: dict, *, observed_at: datetime | None = None) -> ServerStatus:
    body = _object(payload, "status")
    scores = []
    for item in _list(body.get("factionScores", []), "factionScores"):
        score = _object(item, "faction score")
        scores.append(FactionScore(
            faction=_text(score.get("name"), "faction name", required=True),
            score=_integer(score.get("score"), "faction score"),
            color_hex=_text(score.get("colorHex"), "faction color"),
        ))
    players = _object(body.get("players") or {}, "players")
    rotation = _object(body.get("rotation") or {}, "rotation")
    tick_data = body.get("scoreTick")
    tick = None
    if tick_data is not None:
        tick_data = _object(tick_data, "scoreTick")
        tick = ScoreTick(
            current=_integer(tick_data.get("current"), "scoreTick.current"),
            minimum=_integer(tick_data.get("min"), "scoreTick.min"),
            maximum=_integer(tick_data.get("max"), "scoreTick.max"),
        )
    return ServerStatus(
        observed_at=observed_at or utc_now(),
        server_name=_text(body.get("serverName"), "serverName"),
        map_id=_text(body.get("map"), "map"),
        experiences=_experiences(body.get("experiences")),
        lighting=_text(body.get("lighting"), "lighting"),
        alternator=_text(body.get("alternator"), "alternator"),
        current_players=_integer(players.get("current"), "players.current"),
        max_players=_integer(players.get("max"), "players.max"),
        faction_scores=tuple(scores),
        rotation_now_index=_integer(rotation.get("nowIndex"), "rotation.nowIndex"),
        rotation_next_index=_integer(rotation.get("nextIndex"), "rotation.nextIndex"),
        score_tick=tick,
    )


def parse_players(payload: dict, *, observed_at: datetime | None = None) -> PlayerSnapshot:
    body = _object(payload, "players response")
    rows = _list(body.get("players"), "players")
    players = []
    for row in rows:
        item = _object(row, "player")
        players.append(ServerPlayer(
            steam_id=_text(item.get("steamId"), "steamId"),
            display_name=_text(item.get("name"), "player name", required=True),
            faction=_text(item.get("faction"), "player faction"),
            kills=_integer(item.get("kills"), "kills"),
            deaths=_integer(item.get("deaths"), "deaths"),
            cash=_integer(item.get("cash"), "cash"),
            ping_ms=_integer(item.get("pingMs"), "pingMs"),
        ))
    return PlayerSnapshot(tuple(players), observed_at or utc_now(), _integer(body.get("count"), "count"))


def parse_rotation(payload: dict, *, observed_at: datetime | None = None) -> RotationSnapshot:
    body = _object(payload, "rotation response")
    rows = _list(body.get("entries"), "rotation entries")
    entries = []
    for row in rows:
        item = _object(row, "rotation entry")
        entries.append(RotationEntry(
            index=_integer(item.get("index"), "rotation index", required=True),
            map_id=_text(item.get("map"), "rotation map"),
            experiences=_experiences(item.get("experiences")),
            lighting=_text(item.get("lighting"), "rotation lighting"),
            alternator=_text(item.get("zoneAlternator"), "rotation alternator"),
            status=_text(item.get("status"), "rotation status"),
            denied=_boolean(item.get("denied"), "rotation denied"),
        ))
    return RotationSnapshot(
        entries=tuple(sorted(entries, key=lambda entry: entry.index)),
        observed_at=observed_at or utc_now(),
        enabled=_boolean(body.get("enabled"), "rotation enabled"),
        mode=_text(body.get("mode"), "rotation mode"),
        reported_count=_integer(body.get("count"), "rotation count"),
    )
