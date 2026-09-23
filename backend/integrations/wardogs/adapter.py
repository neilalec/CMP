"""Normalized, read-only WARDOGS adapter over the WDRCON client."""

from __future__ import annotations

from integrations.wardogs.client import WDRCONClient
from integrations.wardogs.errors import WDRCONError
from services.game_server_adapter import (
    AdapterError, AdapterErrorKind, ControlOperation, capability_is_usable,
)
from services.game_server_contracts import CONTROL_CAPABILITIES, CapabilityState


def _adapter_error(error: WDRCONError) -> AdapterError:
    if error.status in (401, 403):
        return AdapterError(AdapterErrorKind.AUTHENTICATION_FAILURE)
    if error.kind.startswith("invalid") or error.kind == "response too large":
        return AdapterError(AdapterErrorKind.MALFORMED_RESPONSE)
    return AdapterError(AdapterErrorKind.TRANSPORT_FAILURE)


class WardogsAdapter:
    """Only verified reads are implemented; advertised writes cannot run."""

    def __init__(self, client: WDRCONClient):
        self._client = client

    @property
    def capability_snapshot(self):
        return self._client.capability_snapshot

    def supports(self, capability: str) -> bool:
        return capability_is_usable(self.capability_snapshot, capability)

    def _read(self, method):
        try:
            return method()
        except WDRCONError as error:
            raise _adapter_error(error) from None

    def get_capabilities(self):
        return self._read(self._client.fetch_capabilities)

    def get_status(self):
        return self._read(self._client.fetch_status)

    def get_players(self):
        return self._read(self._client.fetch_players)

    def get_rotation(self):
        return self._read(self._client.fetch_rotation)

    def observe_lifecycle(self):
        return self._client.observe_lifecycle()

    def require_control(self, operation: ControlOperation | str) -> None:
        """Fail safely until a separately reviewed write implementation exists."""
        if operation not in CONTROL_CAPABILITIES:
            raise AdapterError(AdapterErrorKind.OPERATION_UNSUPPORTED)
        if self.capability_snapshot.state_of(operation) == CapabilityState.UNAVAILABLE:
            raise AdapterError(AdapterErrorKind.OPERATION_UNSUPPORTED)
        if not self.supports(operation):
            raise AdapterError(AdapterErrorKind.CAPABILITY_UNVERIFIED)
        raise AdapterError(AdapterErrorKind.OPERATION_UNSUPPORTED)
