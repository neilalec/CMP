"""Offline adapter boundary and fail-closed capability tests."""

import io
import json
import urllib.error

import pytest

from integrations.wardogs.adapter import WardogsAdapter
from integrations.wardogs.client import WDRCONClient
from services.game_server_adapter import (
    AdapterError, AdapterErrorKind, ControlOperation,
)
from services.game_server_contracts import (
    Capability, CapabilityState, LifecycleState, ServerCapabilities,
)
from services.server_registry import get_game_server_adapter_for_server


CAPABILITIES = {
    "routes": ["GET /v1/status", "GET /v1/players", "GET /v1/rotation",
               "POST /v1/broadcast", "POST /v1/match/end"],
}
STATUS = {
    "map": "Bakurani", "players": {"current": 1, "max": 100},
    "factionScores": [
        {"name": "Valkyra", "score": 99999},
        {"name": "Lonestar", "score": 1},
        {"name": "Manticore", "score": 0},
    ], "rotation": {"nowIndex": 0, "nextIndex": 1},
}
PLAYERS = {"count": 1, "players": [
    {"steamId": "76561198000000001", "name": "Aster", "faction": "Valkyra"},
]}
ROTATION = {"entries": [{"index": 0, "map": "Bakurani"}]}


class Response:
    def __init__(self, payload):
        self.body = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, size=-1):
        return self.body.read(size)


def adapter_with_requests(payloads=None):
    calls = []
    payloads = payloads or {
        "/v1/capabilities": CAPABILITIES, "/v1/status": STATUS,
        "/v1/players": PLAYERS, "/v1/rotation": ROTATION,
    }

    def opener(request, timeout):
        calls.append(request)
        return Response(payloads[request.full_url.split("example.test")[1]])

    return WardogsAdapter(WDRCONClient("https://example.test", "offline-secret", opener=opener)), calls


def test_normalized_reads_and_capability_gates():
    adapter, calls = adapter_with_requests()
    assert not adapter.supports("server_status")
    caps = adapter.get_capabilities()
    assert isinstance(caps, ServerCapabilities)
    assert caps.state_of("broadcast") == CapabilityState.ADVERTISED
    assert not adapter.supports("broadcast")
    assert not adapter.supports("authoritative_end")
    assert adapter.get_status().map_id == "Bakurani"
    assert adapter.get_players().players[0].steam_id == "76561198000000001"
    assert adapter.get_rotation().entries[0].map_id == "Bakurani"
    assert adapter.supports("server_status")
    assert adapter.supports("players")
    assert adapter.supports("rotation")
    assert not adapter.supports("broadcast")
    assert not adapter.supports("unknown_name")
    assert {call.get_method() for call in calls} == {"GET"}


def test_lifecycle_ignores_scores_and_rotation_changes():
    adapter, calls = adapter_with_requests({
        "/v1/capabilities": CAPABILITIES,
        "/v1/status": {**STATUS, "rotation": {"nowIndex": 8, "nextIndex": 9}},
        "/v1/players": PLAYERS, "/v1/rotation": ROTATION,
    })
    adapter.get_capabilities()
    assert adapter.get_status().faction_scores[0].score == 99999
    assert adapter.observe_lifecycle().state == LifecycleState.UNKNOWN
    assert not adapter.supports("authoritative_winner")
    assert not adapter.supports("authoritative_end")
    assert all(call.get_method() == "GET" for call in calls)


def test_controls_remain_unavailable_even_if_snapshot_claims_verified():
    adapter, calls = adapter_with_requests()
    adapter.get_capabilities()
    for operation in ControlOperation:
        with pytest.raises(AdapterError) as caught:
            adapter.require_control(operation.value)
        expected = (AdapterErrorKind.CAPABILITY_UNVERIFIED
                    if operation in (ControlOperation.BROADCAST, ControlOperation.END_MATCH)
                    else AdapterErrorKind.OPERATION_UNSUPPORTED)
        assert caught.value.kind == expected
    adapter._client._capabilities = ServerCapabilities(capabilities={
        "broadcast": Capability(CapabilityState.EFFECT_VERIFIED),
    })
    assert adapter.supports("broadcast")
    with pytest.raises(AdapterError) as caught:
        adapter.require_control("broadcast")
    assert caught.value.kind == AdapterErrorKind.OPERATION_UNSUPPORTED
    assert [call.get_method() for call in calls] == ["GET"]


def test_adapter_maps_transport_auth_and_malformed_failures_without_secret():
    secret = "offline-secret"
    failures = [
        (lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError(secret)),
         AdapterErrorKind.TRANSPORT_FAILURE),
        (lambda *_args, **_kwargs: (_ for _ in ()).throw(
            urllib.error.HTTPError("https://example.test/v1/status", 401, secret, {}, io.BytesIO(b"{}"))),
         AdapterErrorKind.AUTHENTICATION_FAILURE),
        (lambda *_args, **_kwargs: Response({"factionScores": "bad"}),
         AdapterErrorKind.MALFORMED_RESPONSE),
    ]
    for opener, expected in failures:
        adapter = WardogsAdapter(WDRCONClient("https://example.test", secret, opener=opener))
        with pytest.raises(AdapterError) as caught:
            adapter.get_status()
        assert caught.value.kind == expected
        assert secret not in str(caught.value)


def test_registry_selection_keeps_squad_on_legacy_path(monkeypatch):
    monkeypatch.setenv("CMP_WARDOGS_RCON_TEST", "offline-secret")
    record = {"game_type": "wardogs", "bridge_url": "https://example.test",
              "wdrcon_secret_env": "CMP_WARDOGS_RCON_TEST"}
    assert isinstance(get_game_server_adapter_for_server(record), WardogsAdapter)
    assert get_game_server_adapter_for_server({"game_type": "squad"}) is None
    with pytest.raises(AdapterError) as caught:
        get_game_server_adapter_for_server({"game_type": "unknown"})
    assert caught.value.kind == AdapterErrorKind.OPERATION_UNSUPPORTED
    monkeypatch.delenv("CMP_WARDOGS_RCON_TEST")
    with pytest.raises(AdapterError) as caught:
        get_game_server_adapter_for_server(record)
    assert caught.value.kind == AdapterErrorKind.INTEGRATION_UNAVAILABLE
