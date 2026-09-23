"""Protocol-neutral, read-only game-server observation contracts.

These are snapshots, not CMP lobby state. In particular, scores are not results and
presence in a roster read is not an explicit player readiness signal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class CapabilityState(str, Enum):
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"
    ADVERTISED = "advertised"
    OBSERVED = "observed"
    EFFECT_VERIFIED = "effect_verified"
    SEMANTIC_VERIFIED = "semantic_verified"


READ_CAPABILITIES = (
    "server_status", "players", "steam_identity", "faction_assignment_read",
    "faction_scores", "rotation", "map_config",
)
CONTROL_CAPABILITIES = (
    "broadcast", "faction_assignment_write", "map_change", "restart_match",
    "end_match", "kick_player",
)
LIFECYCLE_CAPABILITIES = (
    "authoritative_start", "authoritative_end", "authoritative_final_scores",
    "authoritative_winner", "stable_round_identity", "same_map_restart_identity",
)
ALL_CAPABILITIES = READ_CAPABILITIES + CONTROL_CAPABILITIES + LIFECYCLE_CAPABILITIES


@dataclass(frozen=True)
class Capability:
    state: CapabilityState = CapabilityState.UNKNOWN
    observed_at: datetime | None = None
    evidence: str | None = None


@dataclass(frozen=True)
class ServerCapabilities:
    api_version: int | None = None
    build: str | None = None
    max_requests_per_minute_per_ip: int | None = None
    max_body_bytes: int | None = None
    capabilities: dict[str, Capability] = field(default_factory=dict)
    observed_at: datetime | None = None

    def state_of(self, name: str) -> CapabilityState:
        return self.capabilities.get(name, Capability()).state


@dataclass(frozen=True)
class ServerPlayer:
    steam_id: str | None
    display_name: str
    faction: str | None
    kills: int | None = None
    deaths: int | None = None
    cash: int | None = None
    ping_ms: int | None = None


@dataclass(frozen=True)
class PlayerSnapshot:
    players: tuple[ServerPlayer, ...]
    observed_at: datetime
    reported_count: int | None = None


@dataclass(frozen=True)
class FactionScore:
    faction: str
    score: int | None
    color_hex: str | None = None


@dataclass(frozen=True)
class ScoreTick:
    current: int | None = None
    minimum: int | None = None
    maximum: int | None = None


@dataclass(frozen=True)
class ServerStatus:
    observed_at: datetime
    server_name: str | None = None
    map_id: str | None = None
    experiences: tuple[str, ...] = ()
    lighting: str | None = None
    alternator: str | None = None
    current_players: int | None = None
    max_players: int | None = None
    faction_scores: tuple[FactionScore, ...] = ()
    rotation_now_index: int | None = None
    rotation_next_index: int | None = None
    score_tick: ScoreTick | None = None


@dataclass(frozen=True)
class RotationEntry:
    index: int
    map_id: str | None = None
    experiences: tuple[str, ...] = ()
    lighting: str | None = None
    alternator: str | None = None
    status: str | None = None
    denied: bool | None = None


@dataclass(frozen=True)
class RotationSnapshot:
    entries: tuple[RotationEntry, ...]
    observed_at: datetime
    enabled: bool | None = None
    mode: str | None = None
    reported_count: int | None = None


class LifecycleState(str, Enum):
    UNKNOWN = "unknown"
    LIVE_OBSERVED = "live_observed"
    COMPLETED_AUTHORITATIVE = "completed_authoritative"


@dataclass(frozen=True)
class LifecycleObservation:
    state: LifecycleState = LifecycleState.UNKNOWN
    observed_at: datetime | None = None
    source: str | None = None
