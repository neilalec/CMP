"""Small application-facing boundary for normalized server observations.

Reads may be attempted before their capability is observed: a successful read is
what establishes that state. Controls have a separate, fail-closed gate.
"""

from __future__ import annotations

from enum import Enum
from typing import Protocol

from services.game_server_contracts import (
    ALL_CAPABILITIES, CONTROL_CAPABILITIES, LIFECYCLE_CAPABILITIES,
    READ_CAPABILITIES, CapabilityState, LifecycleObservation, PlayerSnapshot,
    RotationSnapshot, ServerCapabilities, ServerStatus,
)


class ControlOperation(str, Enum):
    BROADCAST = "broadcast"
    ASSIGN_FACTION = "faction_assignment_write"
    CHANGE_MAP = "map_change"
    RESTART_MATCH = "restart_match"
    END_MATCH = "end_match"
    KICK_PLAYER = "kick_player"


class AdapterErrorKind(str, Enum):
    INTEGRATION_UNAVAILABLE = "integration_unavailable"
    OPERATION_UNSUPPORTED = "operation_unsupported"
    CAPABILITY_UNVERIFIED = "capability_unverified"
    TRANSPORT_FAILURE = "transport_failure"
    AUTHENTICATION_FAILURE = "authentication_failure"
    MALFORMED_RESPONSE = "malformed_response"


class AdapterError(RuntimeError):
    """Safe, protocol-neutral failure; never includes remote response text."""

    def __init__(self, kind: AdapterErrorKind):
        self.kind = kind
        super().__init__(kind.value)


def capability_is_usable(snapshot: ServerCapabilities, name: str) -> bool:
    """Apply the minimum confidence for the kind of capability requested."""
    if name not in ALL_CAPABILITIES:
        return False
    state = snapshot.state_of(name)
    if name in READ_CAPABILITIES:
        return state in (CapabilityState.OBSERVED, CapabilityState.EFFECT_VERIFIED,
                         CapabilityState.SEMANTIC_VERIFIED)
    if name in CONTROL_CAPABILITIES:
        return state in (CapabilityState.EFFECT_VERIFIED, CapabilityState.SEMANTIC_VERIFIED)
    if name in LIFECYCLE_CAPABILITIES:
        return state == CapabilityState.SEMANTIC_VERIFIED
    return False


class GameServerAdapter(Protocol):
    @property
    def capability_snapshot(self) -> ServerCapabilities: ...

    def get_capabilities(self) -> ServerCapabilities: ...
    def get_status(self) -> ServerStatus: ...
    def get_players(self) -> PlayerSnapshot: ...
    def get_rotation(self) -> RotationSnapshot: ...
    def get_join_id(self) -> str: ...
    def observe_lifecycle(self) -> LifecycleObservation: ...
    def supports(self, capability: str) -> bool: ...
    def require_control(self, operation: ControlOperation | str) -> None: ...

    # This is only a preflight gate. A separate write API may be added later
    # after effect verification and application authorization.
