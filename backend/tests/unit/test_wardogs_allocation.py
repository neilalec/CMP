import json
import time

import pytest

import app_core
from services.server_registry import (
    allocate_server_for_lobby, approve_server, create_server, get_server_by_id,
    set_server_enabled, update_server_record,
)
from services.wardogs_allocation import cleanup_wardogs_lobby
from services.wardogs_lobby import (
    build_wardogs_join_state, build_wardogs_read_model, get_wardogs_lobby,
    save_wardogs_lobby,
)


SECRET = 'offline-test-secret'


def _lobby(lobby_id):
    return {
        'id': lobby_id, 'phase': 'assembling', 'label': 'WARDOGS lobby',
        'serverId': None,
        'factions': [
            {'id': faction, 'commanderId': None, 'groups': []}
            for faction in ('valkyra', 'lonestar', 'manticore')
        ],
    }


def _save_lobby(lobby_id):
    save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id))


def _server(monkeypatch, name, game_type='wardogs', enabled=True):
    payload = {'game_type': game_type, 'display_name': name,
               'bridge_url': 'http://127.0.0.1:9876'}
    if game_type == 'wardogs':
        monkeypatch.setenv('CMP_WARDOGS_RCON_TEST', 'private-password')
        payload['wdrcon_secret_env'] = 'CMP_WARDOGS_RCON_TEST'
    server = create_server(app_core.get_db_connection, SECRET, payload, submitted_by='admin')
    approve_server(app_core.get_db_connection, SECRET, server['id'], 'admin')
    update_server_record(
        app_core.get_db_connection, SECRET, server['id'],
        status='healthy', last_health_status='healthy', last_health_check_at=time.time(),
        metadata={'serverInfo': {'serverName': name}},
    )
    if enabled:
        set_server_enabled(app_core.get_db_connection, SECRET, server['id'], True)
    return server['id']


def _allocate(lobby_id, game_type='wardogs'):
    return allocate_server_for_lobby(app_core.get_db_connection, SECRET, lobby_id, game_type)


def test_wardogs_allocation_is_atomic_idempotent_and_survives_reload(monkeypatch):
    _save_lobby('wd-1')
    _save_lobby('wd-2')
    server_id = _server(monkeypatch, 'WARDOGS test server')
    first = _allocate('wd-1')
    assert first['id'] == server_id
    assert first['current_lobby_id'] == 'wd-1'
    assert get_wardogs_lobby(app_core.get_db_connection, 'wd-1')['serverId'] == server_id
    assert _allocate('wd-1')['id'] == server_id
    assert _allocate('wd-2') is None
    assert get_wardogs_lobby(app_core.get_db_connection, 'wd-2')['serverId'] is None
    with app_core.get_db_connection() as conn:
        assert conn.execute("SELECT COUNT(*) FROM server_allocations WHERE state='reserved'").fetchone()[0] == 1
    # A new connection is the same persisted ownership source after restart.
    assert _allocate('wd-2') is None
    assert get_server_by_id(app_core.get_db_connection, server_id, SECRET)['current_lobby_id'] == 'wd-1'


def test_wardogs_rejects_squad_disabled_and_unhealthy_servers(monkeypatch):
    _save_lobby('wd-wait')
    squad_id = _server(monkeypatch, 'Squad server', game_type='squad')
    disabled_id = _server(monkeypatch, 'Disabled WARDOGS', enabled=False)
    unhealthy_id = _server(monkeypatch, 'Unhealthy WARDOGS')
    update_server_record(app_core.get_db_connection, SECRET, unhealthy_id,
                         status='offline', last_health_status='offline')
    assert _allocate('wd-wait') is None
    assert get_wardogs_lobby(app_core.get_db_connection, 'wd-wait')['serverId'] is None
    assert _allocate('squad-lobby', game_type='squad')['id'] == squad_id
    assert _allocate('another-squad-lobby', game_type='squad') is None
    assert get_server_by_id(app_core.get_db_connection, disabled_id, SECRET)['current_lobby_id'] is None
    assert get_server_by_id(app_core.get_db_connection, unhealthy_id, SECRET)['current_lobby_id'] is None


def test_stale_health_cannot_allocate_until_rechecked(monkeypatch):
    _save_lobby('wd-stale')
    server_id = _server(monkeypatch, 'Stale WARDOGS')
    update_server_record(app_core.get_db_connection, SECRET, server_id,
                         last_health_check_at=time.time() - 3600)
    assert _allocate('wd-stale') is None
    update_server_record(app_core.get_db_connection, SECRET, server_id,
                         last_health_check_at=time.time())
    assert _allocate('wd-stale')['id'] == server_id


def test_waiting_and_join_unavailable_states_never_expose_admin_details(monkeypatch):
    _save_lobby('wd-join')
    lobby = get_wardogs_lobby(app_core.get_db_connection, 'wd-join')
    waiting = build_wardogs_read_model(lobby)['join']
    assert waiting == {'state': 'waiting_for_server', 'serverName': None,
                       'instructions': None, 'directJoinUrl': None}
    server_id = _server(monkeypatch, 'Visible WARDOGS server')
    _allocate('wd-join')
    lobby = get_wardogs_lobby(app_core.get_db_connection, 'wd-join')
    server = get_server_by_id(app_core.get_db_connection, server_id, SECRET)
    joined = build_wardogs_join_state(lobby, server)
    assert joined['state'] == 'server_allocated_join_unavailable'
    assert joined['serverName'] == 'Visible WARDOGS server'
    assert joined['instructions'] is None and joined['directJoinUrl'] is None
    serialized = json.dumps(joined)
    assert '127.0.0.1' not in serialized
    assert 'private-password' not in serialized
    assert 'CMP_WARDOGS_RCON_TEST' not in serialized
    assert 'bridge_url' not in serialized
    server['metadata']['serverInfo']['serverName'] = 'private-password'
    assert build_wardogs_join_state(lobby, server)['serverName'] is None


def test_explicit_cleanup_releases_wardogs_but_failed_probe_does_not(monkeypatch):
    _save_lobby('wd-clean')
    server_id = _server(monkeypatch, 'WARDOGS cleanup')
    _allocate('wd-clean')
    update_server_record(app_core.get_db_connection, SECRET, server_id,
                         status='offline', last_health_status='offline')
    assert get_server_by_id(app_core.get_db_connection, server_id, SECRET)['current_lobby_id'] == 'wd-clean'
    assert cleanup_wardogs_lobby(app_core.get_db_connection, 'wd-clean') == server_id
    assert get_wardogs_lobby(app_core.get_db_connection, 'wd-clean') is None
    server = get_server_by_id(app_core.get_db_connection, server_id, SECRET)
    assert server['current_lobby_id'] is None and server['status'] == 'offline'
    with app_core.get_db_connection() as conn:
        assert conn.execute("SELECT state FROM server_allocations WHERE server_id=?", (server_id,)).fetchone()[0] == 'released'


def test_inconsistent_ownership_fails_closed_without_reassigning(monkeypatch):
    _save_lobby('wd-bad')
    _save_lobby('wd-other')
    server_id = _server(monkeypatch, 'WARDOGS inconsistent')
    _allocate('wd-bad')
    lobby = get_wardogs_lobby(app_core.get_db_connection, 'wd-bad')
    lobby['serverId'] = None
    save_wardogs_lobby(app_core.get_db_connection, lobby)
    with pytest.raises(ValueError, match='ownership is inconsistent'):
        _allocate('wd-bad')
    assert _allocate('wd-other') is None
