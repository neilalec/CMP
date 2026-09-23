from datetime import datetime, timedelta, timezone

import pytest

from services.game_server_adapter import AdapterError, AdapterErrorKind
from services.game_server_contracts import FactionScore, PlayerSnapshot, ServerPlayer, ServerStatus
from services.wardogs_lobby import (
    build_wardogs_read_model, observe_wardogs_lobby, validate_lobby,
)


AT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def owned_lobby(server_id=None):
    return {
        "id": "wd-test", "phase": "assembling", "label": "Practice",
        "serverId": server_id,
        "factions": [
            {"id": "valkyra", "commanderId": "alice", "groups": [
                {"id": "group-a", "type": "squad", "name": "A Team", "leaderId": "alice", "players": [
                    {"id": "alice", "displayName": "Alice", "steamId": "76561198000000001",
                     "registered": True, "rosterStatus": "active", "ready": False},
                    {"id": "bob", "displayName": "Bob", "steamId": "76561198000000002",
                     "registered": True, "rosterStatus": "reserve", "ready": True},
                ]},
            ]},
            {"id": "lonestar", "commanderId": None, "groups": [
                {"id": "group-c", "type": "solo", "name": "Solo", "leaderId": None, "players": [
                    {"id": "carol", "displayName": "Carol", "steamId": "76561198000000003",
                     "registered": True, "rosterStatus": "active", "ready": True},
                ]},
            ]},
            {"id": "manticore", "commanderId": None, "groups": [
                {"id": "group-d", "type": "clan", "name": "Clan", "leaderId": None, "players": [
                    {"id": "dave", "displayName": "Dave", "steamId": "76561198000000004",
                     "registered": True, "rosterStatus": "active", "ready": False},
                ]},
            ]},
        ],
    }


def snapshots():
    players = PlayerSnapshot((
        ServerPlayer("76561198000000001", "Different display", "Valkyra"),
        ServerPlayer("76561198000000003", "Carol server", "Manticore"),
        ServerPlayer("76561198000000004", "Dave server", "Future faction"),
        ServerPlayer("76561198000000099", "Stranger", "Lonestar"),
    ), AT)
    status = ServerStatus(AT, map_id="Bakurani", current_players=4, max_players=100,
                          faction_scores=(FactionScore("Manticore", 9),
                                          FactionScore("Valkyra", 999),
                                          FactionScore("Lonestar", 10)))
    return players, status


def test_reconciliation_keeps_owned_groups_roles_and_readiness():
    players, status = snapshots()
    model = build_wardogs_read_model(owned_lobby(), players=players, status=status, now=AT)
    assert [item["id"] for item in model["factions"]] == ["valkyra", "lonestar", "manticore"]
    valkyra = model["factions"][0]
    assert valkyra["commanderId"] == "alice"
    assert valkyra["groups"][0]["leaderId"] == "alice"
    assert valkyra["groups"][0]["type"] == "squad"
    alice, bob = valkyra["groups"][0]["players"]
    assert alice["displayName"] == "Alice"  # server display never overwrites CMP identity
    assert (alice["connected"], alice["alignmentState"], alice["ready"]) == (True, "aligned", False)
    assert (bob["connected"], bob["rosterStatus"], bob["ready"]) == (False, "reserve", True)
    carol = model["factions"][1]["groups"][0]["players"][0]
    assert (carol["connected"], carol["alignmentState"], carol["ready"]) == (True, "mismatch", True)
    dave = model["factions"][2]["groups"][0]["players"][0]
    assert (dave["observedFactionId"], dave["alignmentState"]) == (None, "unknown")
    assert [item["displayName"] for item in model["unexpectedPlayers"]] == ["Stranger"]
    assert model["scores"] == {"valkyra": 999, "lonestar": 10, "manticore": 9}
    assert model["result"]["status"] == "unconfirmed"
    assert "winner" not in model and "ranking" not in model


def test_no_empty_and_stale_observations_are_distinct():
    lobby = owned_lobby()
    none = build_wardogs_read_model(lobby, now=AT)
    assert none["observation"]["state"] == "none"
    assert none["factions"][0]["groups"][0]["players"][0]["connected"] is None
    empty = build_wardogs_read_model(lobby, players=PlayerSnapshot((), AT), now=AT)
    assert empty["observation"]["state"] == "fresh"
    assert empty["factions"][0]["groups"][0]["players"][0]["connected"] is False
    players, status = snapshots()
    stale = build_wardogs_read_model(lobby, players=players, status=status,
                                     now=AT + timedelta(minutes=2))
    assert stale["observation"]["state"] == "stale"
    assert stale["factions"][0]["groups"][0]["players"][0]["connected"] is None
    assert stale["scores"]["valkyra"] is None


def test_failed_read_keeps_roster_and_marks_cached_snapshot_stale():
    players, status = snapshots()
    class Adapter:
        def __init__(self):
            self.fails = False
        def get_status(self):
            if self.fails:
                raise AdapterError(AdapterErrorKind.TRANSPORT_FAILURE)
            return status
        def get_players(self):
            return players
    adapter = Adapter()
    lobby = owned_lobby(server_id=98)
    assert observe_wardogs_lobby(lobby, adapter, now=AT)["observation"]["state"] == "fresh"
    adapter.fails = True
    stale = observe_wardogs_lobby(lobby, adapter, now=AT + timedelta(seconds=1))
    assert stale["observation"]["state"] == "stale"
    assert stale["factions"][0]["groups"][0]["players"][0]["ready"] is False


def test_validation_rejects_noncanonical_factions_and_invalid_leaders():
    lobby = owned_lobby()
    lobby["factions"][2]["id"] = "fourth"
    with pytest.raises(ValueError):
        validate_lobby(lobby)
    lobby = owned_lobby()
    lobby["factions"][0]["groups"][0]["leaderId"] = "carol"
    with pytest.raises(ValueError):
        validate_lobby(lobby)


def test_ambiguous_or_invalid_steam_ids_are_never_auto_matched():
    lobby = owned_lobby()
    lobby["factions"][0]["groups"][0]["players"][1]["steamId"] = "76561198000000001"
    lobby["factions"][1]["groups"][0]["players"][0]["steamId"] = "not-a-steam-id"
    players, status = snapshots()
    model = build_wardogs_read_model(lobby, players=players, status=status, now=AT)
    alice, bob = model["factions"][0]["groups"][0]["players"]
    carol = model["factions"][1]["groups"][0]["players"][0]
    assert alice["connected"] is None and bob["connected"] is None
    assert carol["connected"] is None
    assert any(item["steamId"] == "76561198000000001" for item in model["unexpectedPlayers"])
