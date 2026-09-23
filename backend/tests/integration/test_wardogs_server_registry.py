"""Game-aware registry behavior, with all WDRCON traffic mocked offline."""

import io
import json
import sqlite3
import time
import urllib.error

import app_core
import pytest
from flask_jwt_extended import create_access_token
import app as backend_app

from services import server_registry
from services.wardogs_lobby import save_wardogs_lobby


SECRET_NAME = 'CMP_WARDOGS_RCON_TEST_SERVER'
SECRET = 'offline-test-credential'
CAPABILITIES = {
    'apiVersion': 1, 'build': '++Wardogs+Live-CL-501228',
    'limits': {'maxRequestsPerMinutePerIp': 600},
    'routes': ['GET /v1/status', 'GET /v1/players', 'GET /v1/rotation',
               'POST /v1/match/restart', 'PATCH /v1/players/{id}'],
}
STATUS = {
    'serverName': 'WARDOGS test server', 'map': 'Bakurani',
    'experiences': ['Bakurani_KOTH_01'], 'lighting': 'DayEarlyClear',
    'alternator': 'ZoneAlternator.Bakurani.Default.Circle',
    'players': {'current': 0, 'max': 100},
    'factionScores': [{'name': name, 'score': 0} for name in ('Valkyra', 'Lonestar', 'Manticore')],
    'rotation': {'nowIndex': 0, 'nextIndex': 1},
}


class Response:
    def __init__(self, payload):
        self.body = io.BytesIO(json.dumps(payload).encode())

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.body.close()

    def read(self, size=-1):
        return self.body.read(size)


def _mock_wdrcon(monkeypatch, *, error=None):
    requests = []

    def open_request(request, timeout):
        requests.append(request)
        if error:
            raise error()
        path = request.full_url.split('example.test')[1]
        return Response({'/v1/capabilities': CAPABILITIES, '/v1/status': STATUS}[path])

    monkeypatch.setattr('integrations.wardogs.client.urllib.request.urlopen', open_request)
    return requests


def _wardogs_payload():
    return {
        'display_name': 'WARDOGS server', 'game_type': 'wardogs',
        'bridge_url': 'https://example.test', 'wdrcon_secret_env': SECRET_NAME,
    }


def _create_wardogs(monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET)
    return server_registry.create_server(app_core.get_db_connection, 'test-key', _wardogs_payload())


def test_existing_rows_migrate_to_squad_by_default(tmp_path):
    database_path = tmp_path / 'legacy-registry.db'

    def connection():
        conn = sqlite3.connect(database_path)
        conn.row_factory = sqlite3.Row
        return conn

    # Minimal historical schema plus every column read by the existing payload mapper.
    with connection() as conn:
        conn.execute('''CREATE TABLE servers (
            id INTEGER PRIMARY KEY, slug TEXT, display_name TEXT, owner_label TEXT,
            steam_lobby_id TEXT, connect_address TEXT, join_password TEXT,
            bridge_url TEXT, bridge_token_encrypted TEXT, submitted_by TEXT,
            approved_by TEXT, approved_at REAL, status TEXT, enabled INTEGER,
            current_lobby_id TEXT, reserved_at REAL, last_health_check_at REAL,
            last_health_status TEXT, last_health_error TEXT, cap_players INTEGER,
            cap_layer_change INTEGER, cap_broadcast INTEGER, cap_round_result INTEGER,
            metadata_json TEXT, created_at REAL, updated_at REAL
        )''')
        conn.execute('''INSERT INTO servers VALUES (
            1, 'legacy', 'Legacy Squad', '', '', '', '',
            'http://127.0.0.1:3001', '', '', '', NULL, 'approved', 1,
            NULL, NULL, NULL, NULL, NULL, 0, 0, 0, 0, '{}', 1, 1
        )''')
    server_registry.init_server_registry_tables(connection)
    server_registry.init_server_registry_tables(connection)
    migrated = server_registry.get_server_by_id(connection, 1, 'test-key')
    assert migrated['game_type'] == 'squad'
    assert migrated['wdrcon_secret_env'] == ''
    assert server_registry.list_available_servers(connection, 'test-key')[0]['id'] == 1


def test_registration_requires_valid_type_url_and_external_credential(monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET)
    with pytest.raises(ValueError, match='game_type'):
        server_registry.create_server(app_core.get_db_connection, 'test-key',
                                      {**_wardogs_payload(), 'game_type': 'other'})
    with pytest.raises(ValueError, match='origin'):
        server_registry.create_server(app_core.get_db_connection, 'test-key',
                                      {**_wardogs_payload(), 'bridge_url': 'https://example.test/v1'})
    with pytest.raises(ValueError, match='wdrcon_secret_env'):
        server_registry.create_server(app_core.get_db_connection, 'test-key',
                                      {**_wardogs_payload(), 'wdrcon_secret_env': ''})
    monkeypatch.delenv(SECRET_NAME)
    with pytest.raises(ValueError, match='credential is unavailable'):
        server_registry.create_server(app_core.get_db_connection, 'test-key', _wardogs_payload())
    monkeypatch.setenv(SECRET_NAME, SECRET)
    with pytest.raises(ValueError, match='not bridge_token'):
        server_registry.create_server(app_core.get_db_connection, 'test-key',
                                      {**_wardogs_payload(), 'bridge_token': SECRET})
    with pytest.raises(ValueError, match='join details'):
        server_registry.create_server(app_core.get_db_connection, 'test-key',
                                      {**_wardogs_payload(), 'connect_address': 'fake:1234'})


def test_wardogs_health_is_read_only_and_persists_capability_confidence(monkeypatch):
    requests = _mock_wdrcon(monkeypatch)
    registered = _create_wardogs(monkeypatch)
    assert registered['game_type'] == 'wardogs'
    assert registered['bridge_token_masked'] == ''
    assert 'bridge_token' not in registered
    with pytest.raises(ValueError, match='only available for Squad'):
        server_registry.build_bridge_request_for_server(registered)
    checked, result = server_registry.run_server_health_check(app_core.get_db_connection, 'test-key', registered['id'])
    assert checked['last_health_status'] == 'healthy'
    assert result['serverInfo']['map'] == 'Bakurani'
    assert result['capabilityStates']['server_status']['state'] == 'observed'
    assert result['capabilityStates']['players']['state'] == 'advertised'
    assert result['capabilityStates']['restart_match']['state'] == 'advertised'
    assert result['capabilityStates']['authoritative_end']['state'] == 'unknown'
    assert checked['metadata']['capabilityStates'] == result['capabilityStates']
    assert [request.get_method() for request in requests] == ['GET', 'GET']
    assert [request.full_url.rsplit('/', 1)[1] for request in requests] == ['capabilities', 'status']
    assert all(request.get_header('Authorization') == f'Bearer {SECRET}' for request in requests)
    assert SECRET not in json.dumps(checked)
    assert SECRET not in json.dumps(result)
    with app_core.get_db_connection() as conn:
        row = conn.execute('SELECT bridge_token_encrypted, metadata_json FROM servers WHERE id=?',
                           (registered['id'],)).fetchone()
    assert row['bridge_token_encrypted'] == ''
    assert SECRET not in row['metadata_json']


def test_registry_redacts_unexpected_secret_in_server_display_field(monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET)
    monkeypatch.setattr('integrations.wardogs.client.urllib.request.urlopen',
                        lambda request, timeout: Response(
                            CAPABILITIES if request.full_url.endswith('/capabilities')
                            else {**STATUS, 'serverName': f'echo {SECRET}'})
                        )
    result = server_registry.test_server_connection(_wardogs_payload())
    assert result['serverInfo']['serverName'] == 'echo [REDACTED]'
    assert SECRET not in json.dumps(result)


@pytest.mark.parametrize('failure', [
    lambda: urllib.error.URLError(f'connection failed: {SECRET}'),
    lambda: urllib.error.HTTPError('https://example.test/v1/capabilities', 401, SECRET,
                                   {}, io.BytesIO(json.dumps({'error': {'message': SECRET}}).encode())),
])
def test_wardogs_failed_health_is_offline_and_never_leaks_secret(monkeypatch, failure):
    _mock_wdrcon(monkeypatch, error=failure)
    registered = _create_wardogs(monkeypatch)
    checked, result = server_registry.run_server_health_check(app_core.get_db_connection, 'test-key', registered['id'])
    assert checked['last_health_status'] == 'offline'
    assert result['reachable'] is False
    assert SECRET not in json.dumps(checked)
    assert SECRET not in json.dumps(result)


def test_squad_allocation_ignores_wardogs_and_explicit_filter_finds_it(monkeypatch):
    wardogs = _create_wardogs(monkeypatch)
    squad = server_registry.create_server(app_core.get_db_connection, 'test-key', {
        'display_name': 'Squad server', 'bridge_url': 'http://127.0.0.1:3001',
    })
    for server in (wardogs, squad):
        server_registry.update_server_record(app_core.get_db_connection, 'test-key', server['id'],
                                             status='healthy', enabled=True)
    server_registry.update_server_record(app_core.get_db_connection, 'test-key', wardogs['id'],
                                         approved_at=123.0, last_health_status='healthy',
                                         last_health_check_at=time.time())
    save_wardogs_lobby(app_core.get_db_connection, {
        'id': 'wardogs-lobby', 'phase': 'assembling', 'serverId': None,
        'factions': [{'id': faction, 'commanderId': None, 'groups': []}
                     for faction in ('valkyra', 'lonestar', 'manticore')],
    })
    assert [server['id'] for server in server_registry.list_available_servers(
        app_core.get_db_connection, 'test-key')] == [squad['id']]
    assert server_registry.get_server_pool_capacity(app_core.get_db_connection, 'test-key') == 1
    assert server_registry.allocate_server_for_lobby(app_core.get_db_connection, 'test-key', 'squad-lobby')['id'] == squad['id']
    assert server_registry.list_available_servers(app_core.get_db_connection, 'test-key') == []
    assert [server['id'] for server in server_registry.list_available_servers(
        app_core.get_db_connection, 'test-key', game_type='wardogs')] == [wardogs['id']]
    assert server_registry.get_server_pool_capacity(app_core.get_db_connection, 'test-key',
                                                     game_type='wardogs') == 1
    assert server_registry.allocate_server_for_lobby(app_core.get_db_connection, 'test-key',
                                                     'wardogs-lobby', game_type='wardogs')['id'] == wardogs['id']


def test_wardogs_only_registry_keeps_squad_global_fallback_capacity(monkeypatch):
    wardogs = _create_wardogs(monkeypatch)
    server_registry.update_server_record(app_core.get_db_connection, 'test-key', wardogs['id'],
                                         status='healthy', enabled=True)
    assert server_registry.get_server_pool_capacity(app_core.get_db_connection, 'test-key') == 1
    assert server_registry.list_available_servers(app_core.get_db_connection, 'test-key') == []
    assert server_registry.allocate_server_for_lobby(app_core.get_db_connection, 'test-key', 'squad-lobby') is None


def test_admin_api_accepts_wardogs_but_public_submission_requires_admin(flask_app, monkeypatch):
    monkeypatch.setenv(SECRET_NAME, SECRET)
    requests = _mock_wdrcon(monkeypatch)
    client = flask_app.test_client()
    backend_app.users['wardogs_admin'] = {'password': 'unused', 'steam_id': '76561198000000001'}
    app_core.ADMIN_STEAM_IDS.add('76561198000000001')
    with flask_app.app_context():
        admin_token = create_access_token(identity='wardogs_admin')
        user_token = create_access_token(identity='wardogs_user')
    admin_headers = {'Authorization': f'Bearer {admin_token}'}
    user_headers = {'Authorization': f'Bearer {user_token}'}

    for route in ('/api/servers/test', '/api/servers/submit'):
        denied = client.post(route, json=_wardogs_payload(), headers=user_headers)
        assert denied.status_code == 403

    tested = client.post('/api/admin/servers/test', json=_wardogs_payload(), headers=admin_headers)
    assert tested.status_code == 200
    assert tested.get_json()['result']['capabilityStates']['server_status']['state'] == 'observed'
    created = client.post('/api/admin/servers', json=_wardogs_payload(), headers=admin_headers)
    assert created.status_code == 201
    body = created.get_json()
    assert body['server']['game_type'] == 'wardogs'
    assert SECRET not in json.dumps(body)
    health = client.post(f"/api/admin/servers/{body['server']['id']}/health-check", headers=admin_headers)
    assert health.status_code == 200
    assert health.get_json()['server']['last_health_status'] == 'healthy'
    assert SECRET not in health.get_data(as_text=True)
    assert {request.get_method() for request in requests} == {'GET'}
