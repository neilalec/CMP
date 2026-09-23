"""Offline tests based on the checked-in CL-501228 response shapes."""

import io
import json
import urllib.error

import pytest

from integrations.wardogs.client import WDRCONClient
from integrations.wardogs.errors import WDRCONError, WDRCONPayloadError
from integrations.wardogs.parsing import (
    parse_capabilities, parse_players, parse_rotation, parse_status,
)
from services.game_server_contracts import CapabilityState, LifecycleState


CAPABILITIES = {
    "apiVersion": 1, "build": "++Wardogs+Live-CL-501228",
    "limits": {"maxBodyBytes": 65536, "maxRequestsPerMinutePerIp": 600},
    "routes": [
        "GET /v1/status", "GET /v1/players", "GET /v1/rotation", "GET /v1/server-id",
        "POST /v1/match/restart", "PATCH /v1/players/{id}",
        "GET /v1/some-new-route",
    ],
}
STATUS = {
    "serverName": "Test server", "map": "Bakurani",
    "experiences": ["Bakurani_KOTH_01"], "lighting": "DayEarlyClear",
    "alternator": "ZoneAlternator.Bakurani.Default.Circle",
    "players": {"current": 2, "max": 100},
    "factionScores": [
        {"name": "Lonestar", "colorHex": "#4CB1EF", "score": 12},
        {"name": "Valkyra", "colorHex": "#FA503E", "score": 10},
        {"name": "Manticore", "colorHex": "#1DD65C", "score": 8},
    ],
    "rotation": {"nowIndex": 0, "nextIndex": 1},
    "scoreTick": {"current": 24, "min": 18, "max": 30},
}
PLAYERS = {"count": 2, "players": [
    {"steamId": "76561198000000001", "name": "Aster", "faction": "Valkyra",
     "kills": 4, "deaths": 2, "cash": 100, "pingMs": 42},
    {"steamId": None, "name": "Unlinked", "faction": "Unknown faction"},
]}
ROTATION = {"enabled": True, "mode": "sequential", "count": 2, "entries": [
    {"index": 1, "map": "Second", "experiences": ["Mode B", "Mode C"],
     "lighting": "Night", "zoneAlternator": "Alt B", "status": "next", "denied": False,
     "newField": "ignored"},
    {"index": 0, "map": "Bakurani", "experiences": ["Mode A"],
     "status": "now", "denied": False},
]}


class FakeResponse:
    def __init__(self, payload):
        self.body = io.BytesIO(json.dumps(payload).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, size=-1):
        return self.body.read(size)


def test_capabilities_advertisement_never_promotes_mutation_or_lifecycle():
    parsed = parse_capabilities(CAPABILITIES)
    assert parsed.api_version == 1
    assert parsed.build == "++Wardogs+Live-CL-501228"
    assert parsed.max_requests_per_minute_per_ip == 600
    assert parsed.state_of("server_status") == CapabilityState.ADVERTISED
    assert parsed.state_of("restart_match") == CapabilityState.ADVERTISED
    assert parsed.state_of("faction_assignment_write") == CapabilityState.ADVERTISED
    assert parsed.state_of("broadcast") == CapabilityState.UNAVAILABLE
    assert parsed.state_of("authoritative_end") == CapabilityState.UNKNOWN
    assert parsed.state_of("same_map_restart_identity") == CapabilityState.UNKNOWN


def test_status_normalizes_three_scores_and_optional_metadata():
    status = parse_status({**STATUS, "newField": "ignored"})
    assert status.map_id == "Bakurani"
    assert status.experiences == ("Bakurani_KOTH_01",)
    assert status.lighting == "DayEarlyClear"
    assert status.alternator == "ZoneAlternator.Bakurani.Default.Circle"
    assert (status.current_players, status.max_players) == (2, 100)
    assert [(score.faction, score.score) for score in status.faction_scores] == [
        ("Lonestar", 12), ("Valkyra", 10), ("Manticore", 8)
    ]
    assert (status.rotation_now_index, status.rotation_next_index) == (0, 1)
    assert status.score_tick.current == 24
    assert parse_status({}).faction_scores == ()
    assert parse_status({"factionScores": [{"name": "Future faction"}]}).faction_scores[0].score is None
    with pytest.raises(WDRCONPayloadError, match="factionScores"):
        parse_status({"factionScores": "bad"})


def test_players_normalize_and_handle_missing_optional_stats():
    snapshot = parse_players(PLAYERS)
    assert snapshot.reported_count == 2
    assert snapshot.players[0].steam_id == "76561198000000001"
    assert snapshot.players[0].display_name == "Aster"
    assert snapshot.players[0].faction == "Valkyra"
    assert (snapshot.players[0].kills, snapshot.players[0].deaths,
            snapshot.players[0].cash, snapshot.players[0].ping_ms) == (4, 2, 100, 42)
    assert snapshot.players[1].steam_id is None
    assert snapshot.players[1].faction == "Unknown faction"
    assert snapshot.players[1].kills is None
    assert parse_players({"players": [], "count": 0}).players == ()
    with pytest.raises(WDRCONPayloadError, match="player name"):
        parse_players({"players": [{"steamId": "123"}]})
    with pytest.raises(WDRCONPayloadError, match="players must be an array"):
        parse_players({"players": {}})


def test_rotation_orders_entries_and_preserves_status_and_experiences():
    rotation = parse_rotation(ROTATION)
    assert [entry.index for entry in rotation.entries] == [0, 1]
    assert rotation.entries[0].status == "now"
    assert rotation.entries[1].status == "next"
    assert rotation.entries[1].experiences == ("Mode B", "Mode C")
    assert rotation.entries[1].alternator == "Alt B"
    assert rotation.entries[1].denied is False
    with pytest.raises(WDRCONPayloadError, match="rotation entries"):
        parse_rotation({"entries": "bad"})


def test_client_uses_bearer_gets_only_and_marks_successful_reads_observed():
    payloads = {
        "/v1/capabilities": CAPABILITIES, "/v1/status": STATUS,
        "/v1/players": PLAYERS, "/v1/rotation": ROTATION,
        "/v1/server-id": {"serverId": "wardogs-test-join-id"},
    }
    requests = []

    def open_request(request, timeout):
        requests.append((request, timeout))
        return FakeResponse(payloads[request.full_url.split("example.test")[1]])

    client = WDRCONClient("https://example.test/", "secret-value", timeout=3, opener=open_request)
    assert client.capability_snapshot.state_of("players") == CapabilityState.UNKNOWN
    client.fetch_capabilities()
    assert client.capability_snapshot.state_of("players") == CapabilityState.ADVERTISED
    assert client.capability_snapshot.state_of("steam_identity") == CapabilityState.ADVERTISED
    client.fetch_status()
    client.fetch_players()
    client.fetch_rotation()
    states = client.capability_snapshot
    for name in ("server_status", "faction_scores", "map_config", "players",
                 "steam_identity", "faction_assignment_read", "rotation"):
        assert states.state_of(name) == CapabilityState.OBSERVED
    assert states.state_of("restart_match") == CapabilityState.ADVERTISED
    assert states.state_of("authoritative_winner") == CapabilityState.UNKNOWN
    assert client.fetch_server_join_id() == "wardogs-test-join-id"
    assert client.capability_snapshot.state_of("server_join_id") == CapabilityState.OBSERVED
    assert {request.get_method() for request, _ in requests} == {"GET"}
    assert all(request.get_header("Authorization") == "Bearer secret-value" for request, _ in requests)
    assert all(timeout == 3 for _, timeout in requests)


@pytest.mark.parametrize("payload", [
    {}, {"serverId": ""}, {"serverId": "   "}, {"serverId": 123},
    {"serverId": "contains spaces"}, [],
])
def test_server_join_id_rejects_missing_blank_or_malformed_values(payload):
    client = WDRCONClient("https://example.test", "secret",
                          opener=lambda *_args, **_kwargs: FakeResponse(payload))
    with pytest.raises(WDRCONError):
        client.fetch_server_join_id()


def test_server_join_id_read_uses_bearer_get_and_does_not_leak_credentials():
    seen = []

    def opener(request, timeout):
        seen.append((request, timeout))
        return FakeResponse({"serverId": "server-id-from-read"})

    client = WDRCONClient("https://example.test", "private-token", opener=opener)
    assert client.fetch_server_join_id() == "server-id-from-read"
    request, _ = seen[0]
    assert request.full_url == "https://example.test/v1/server-id"
    assert request.get_method() == "GET"
    assert request.get_header("Authorization") == "Bearer private-token"


def test_empty_roster_does_not_verify_identity_or_faction_fields():
    client = WDRCONClient("http://127.0.0.1:7776", "secret", opener=lambda *_args, **_kwargs: FakeResponse({"players": []}))
    client.fetch_players()
    assert client.capability_snapshot.state_of("players") == CapabilityState.OBSERVED
    assert client.capability_snapshot.state_of("steam_identity") == CapabilityState.UNKNOWN
    assert client.capability_snapshot.state_of("faction_assignment_read") == CapabilityState.UNKNOWN


@pytest.mark.parametrize("url", ["https://secret@example.test", "https://example.test/v1", "ftp://example.test"])
def test_client_rejects_unsafe_base_urls(url):
    with pytest.raises(ValueError):
        WDRCONClient(url, "secret")


def test_client_rejects_header_control_characters():
    with pytest.raises(ValueError):
        WDRCONClient("https://example.test\nInjected: value", "secret")
    with pytest.raises(ValueError):
        WDRCONClient("https://example.test", "secret\r\nInjected: value")


def test_transport_errors_are_controlled_and_do_not_leak_secret():
    secret = "very-private-token"

    def connection_error(*_args, **_kwargs):
        raise urllib.error.URLError(f"failed near {secret}")

    client = WDRCONClient("https://example.test", secret, opener=connection_error)
    with pytest.raises(WDRCONError) as caught:
        client.fetch_status()
    assert caught.value.kind == "connection failure"
    assert secret not in str(caught.value)

    def timed_out(*_args, **_kwargs):
        raise TimeoutError(f"timed out with {secret}")

    with pytest.raises(WDRCONError) as caught:
        WDRCONClient("https://example.test", secret, opener=timed_out).fetch_status()
    assert caught.value.kind == "connection failure"
    assert secret not in str(caught.value)

    def http_error(*_args, **_kwargs):
        body = json.dumps({"error": {"code": "rate_limited", "message": secret}}).encode()
        raise urllib.error.HTTPError("https://example.test/v1/status", 429, secret,
                                     {"Retry-After": "7"}, io.BytesIO(body))

    client = WDRCONClient("https://example.test", secret, opener=http_error)
    with pytest.raises(WDRCONError) as caught:
        client.fetch_status()
    assert caught.value.status == 429
    assert caught.value.code == "rate_limited"
    assert caught.value.retry_after_seconds == 7
    assert secret not in str(caught.value)

    with pytest.raises(WDRCONError) as caught:
        WDRCONClient("https://example.test", secret,
                     opener=lambda *_args, **_kwargs: FakeResponse("not an object")).fetch_status()
    assert caught.value.kind == "invalid JSON object"

    class BadJsonResponse(FakeResponse):
        def __init__(self):
            self.body = io.BytesIO(b"{broken")

    with pytest.raises(WDRCONError) as caught:
        WDRCONClient("https://example.test", secret,
                     opener=lambda *_args, **_kwargs: BadJsonResponse()).fetch_status()
    assert caught.value.kind == "invalid JSON"


def test_high_live_scores_never_create_a_result_or_lifecycle_claim():
    client = WDRCONClient("https://example.test", "secret",
                         opener=lambda *_args, **_kwargs: FakeResponse({
                             **STATUS, "factionScores": [
                                 {"name": "Valkyra", "score": 99999},
                                 {"name": "Lonestar", "score": 1},
                                 {"name": "Manticore", "score": 0},
                             ], "matchSeconds": 0, "scoreCap": 100,
                         }))
    status = client.fetch_status()
    assert status.faction_scores[0].score == 99999
    assert client.observe_lifecycle().state == LifecycleState.UNKNOWN
    assert client.capability_snapshot.state_of("authoritative_end") == CapabilityState.UNKNOWN
