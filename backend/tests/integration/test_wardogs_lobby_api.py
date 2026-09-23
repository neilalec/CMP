"""Authenticated, offline WARDOGS lobby read transport."""

from datetime import datetime, timezone

import app as backend_app
import app_core
import wiring
from flask_jwt_extended import create_access_token

from services.game_server_contracts import PlayerSnapshot, ServerPlayer, ServerStatus
from services.wardogs_assignment import WardogsAssignmentConfig
from services.wardogs_finalization import finalize_wardogs_accepted_match
from services.wardogs_lobby import get_wardogs_lobby, save_wardogs_lobby


def lobby(server_id=None):
    return {"id": "wd-api", "phase": "assembling", "serverId": server_id,
            "factions": [
                {"id": name, "commanderId": None, "groups": [
                    {"id": f"{name}-solo", "type": "solo", "name": "Solo", "leaderId": None,
                     "players": [{"id": username, "displayName": username.title(),
                                  "steamId": steam_id, "registered": True,
                                  "rosterStatus": "active", "ready": False}]}
                ]}
                for name, username, steam_id in (
                    ("valkyra", "alice", "76561198000000001"),
                    ("lonestar", "bob", "76561198000000002"),
                    ("manticore", "carol", "76561198000000003"),
                )]}


def headers(flask_app, username):
    with flask_app.app_context():
        token = create_access_token(identity=username)
    return {"Authorization": f"Bearer {token}"}


def test_lobby_is_durable_and_read_requires_membership_or_admin(flask_app):
    seeded = lobby()
    seeded["rawWdrcon"] = {"password": "must-not-be-stored"}
    save_wardogs_lobby(app_core.get_db_connection, seeded)
    assert get_wardogs_lobby(app_core.get_db_connection, "wd-api")["factions"][2]["id"] == "manticore"
    with app_core.get_db_connection() as conn:
        stored = conn.execute("SELECT roster_json FROM wardogs_lobbies WHERE lobby_id='wd-api'").fetchone()[0]
    assert "must-not-be-stored" not in stored and "rawWdrcon" not in stored
    client = flask_app.test_client()
    url = "/api/wardogs/lobbies/wd-api"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers(flask_app, "outsider")).status_code == 403
    response = client.get(url, headers=headers(flask_app, "alice"))
    assert response.status_code == 200
    match = response.get_json()["match"]
    assert match["observation"]["state"] == "none"
    assert match["factions"][0]["groups"][0]["players"][0]["ready"] is False
    assert client.get("/api/wardogs/lobbies/missing", headers=headers(flask_app, "alice")).status_code == 404
    backend_app.users["admin"] = {"password": "unused", "steam_id": "76561198000000099"}
    app_core.ADMIN_STEAM_IDS.add("76561198000000099")
    assert client.get(url, headers=headers(flask_app, "admin")).status_code == 200


def test_associated_server_reads_only_normalized_data_and_hides_credentials(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby(server_id=7))
    credential = "private-wdrcon-secret"
    monkeypatch.setenv("CMP_WARDOGS_RCON_PRIVATE", credential)
    monkeypatch.setattr(backend_app, "get_server_by_id", lambda _id: {
        "id": 7, "game_type": "wardogs", "wdrcon_secret_env": "CMP_WARDOGS_RCON_PRIVATE",
        "bridge_url": "https://example.test", "password": credential,
    })
    at = datetime.now(timezone.utc)
    class FakeAdapter:
        def get_status(self):
            return ServerStatus(at, map_id=f"Bakurani-{credential}", current_players=2, max_players=100)
        def get_players(self):
            return PlayerSnapshot((ServerPlayer("76561198000000001", "server-name", "Valkyra"),
                                   ServerPlayer("76561198000000099", credential, "Lonestar")), at)
    monkeypatch.setattr(wiring, "get_game_server_adapter_for_server", lambda _server: FakeAdapter())
    response = flask_app.test_client().get("/api/wardogs/lobbies/wd-api", headers=headers(flask_app, "alice"))
    assert response.status_code == 200
    body = response.get_json()["match"]
    assert body["serverId"] == 7
    assert body["factions"][0]["groups"][0]["players"][0]["connected"] is True
    assert body["factions"][0]["groups"][0]["players"][0]["ready"] is False
    text = response.get_data(as_text=True)
    assert credential not in text and "CMP_WARDOGS_RCON_PRIVATE" not in text
    assert "bridge_url" not in text and "server-name" not in text
    assert body["unexpectedPlayers"][0]["displayName"] == "[REDACTED]"


def test_unknown_associated_server_fails_safely(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby(server_id=999))
    monkeypatch.setattr(backend_app, "get_server_by_id", lambda _id: None)
    response = flask_app.test_client().get("/api/wardogs/lobbies/wd-api", headers=headers(flask_app, "alice"))
    assert response.status_code == 409


def test_finalized_lobby_is_readable_through_existing_authenticated_endpoint(flask_app):
    pending = {
        'id': 'accepted-api-match', 'game_type': 'wardogs', 'queue_mode': 'wardogs-internal',
        'players': ['alice', 'bob', 'carol'],
        'accepted': {'alice': True, 'bob': True, 'carol': True},
    }
    result = finalize_wardogs_accepted_match(
        pending, queue_modes={'wardogs-internal': {'id': 'wardogs-internal', 'game_type': 'wardogs'}},
        groups={}, user_to_group={}, profiles={}, config=WardogsAssignmentConfig(1, 0),
        get_db_connection=app_core.get_db_connection,
    )
    assert result.success
    response = flask_app.test_client().get(
        f'/api/wardogs/lobbies/{result.lobby_id}', headers=headers(flask_app, 'alice'))
    assert response.status_code == 200
    match = response.get_json()['match']
    assert match['id'] == result.lobby_id
    assert match['serverId'] is None and match['observation']['state'] == 'none'
    assert [faction['summary']['active'] for faction in match['factions']] == [1, 1, 1]
