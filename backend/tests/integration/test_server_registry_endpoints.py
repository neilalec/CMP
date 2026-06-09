from flask_jwt_extended import create_access_token

import app as backend_app
import app_core
import services.server_registry as server_registry_service


def _admin_headers(flask_app):
    backend_app.users['admin'] = {
        'password': 'unused',
        'steam_id': '76561198000000001'
    }
    app_core.ADMIN_STEAM_IDS.add('76561198000000001')
    with flask_app.app_context():
        token = create_access_token(identity='admin')
    return {'Authorization': f'Bearer {token}'}


def test_admin_can_create_and_list_servers(flask_app, monkeypatch):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    fake_result = {
        'bridgeReachable': True,
        'capabilities': {
            'players': True,
            'layer_change': True,
            'broadcast': True,
            'round_result': True,
        },
        'serverInfo': {'serverName': 'Test Server'},
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    create_response = client.post('/api/admin/servers', json={
        'display_name': 'Test Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
        'steam_lobby_id': '109775243419695307',
        'connect_address': '127.0.0.1:7787'
    }, headers=headers)
    assert create_response.status_code == 201
    create_payload = create_response.get_json()
    assert create_payload['success'] is True
    assert create_payload['server']['display_name'] == 'Test Server'
    assert create_payload['server']['steam_lobby_id'] == '109775243419695307'
    assert create_payload['server']['submitted_by'] == 'admin'
    assert create_payload['server']['status'] == 'pending'

    test_response = client.post('/api/admin/servers/test', json={
        'display_name': 'Test Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers)
    assert test_response.status_code == 200
    assert test_response.get_json()['result']['bridgeReachable'] is True

    list_response = client.get('/api/admin/servers', headers=headers)
    assert list_response.status_code == 200
    list_payload = list_response.get_json()
    assert list_payload['success'] is True
    assert len(list_payload['servers']) == 1
    assert list_payload['servers'][0]['bridge_token_masked']


def test_admin_can_health_check_approve_and_enable_server(flask_app, monkeypatch):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    fake_result = {
        'bridgeReachable': True,
        'capabilities': {
            'players': True,
            'layer_change': True,
            'broadcast': True,
            'round_result': True,
        },
        'serverInfo': {'serverName': 'Ready Server'},
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    created = client.post('/api/admin/servers', json={
        'display_name': 'Ready Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload['server']['last_health_status'] == 'healthy'

    approve_response = client.post(f"/api/admin/servers/{created['id']}/approve", headers=headers)
    assert approve_response.status_code == 200
    approve_payload = approve_response.get_json()
    assert approve_payload['server']['status'] == 'approved'
    assert approve_payload['server']['approved_by'] == 'admin'

    enable_response = client.post(f"/api/admin/servers/{created['id']}/enable", headers=headers)
    assert enable_response.status_code == 200
    enable_payload = enable_response.get_json()
    assert enable_payload['server']['enabled'] is True


def test_admin_cannot_enable_pending_server(flask_app):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    created = client.post('/api/admin/servers', json={
        'display_name': 'Pending Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    enable_response = client.post(f"/api/admin/servers/{created['id']}/enable", headers=headers)
    assert enable_response.status_code == 400
    assert 'approved' in enable_response.get_json()['message'].lower()


def test_lobby_join_link_returns_squad_url(flask_app):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    backend_app.lobbies['lobby_test'] = {
        'server_details': {
            'connectAddress': '127.0.0.1:7787',
            'password': 'secretpass'
        }
    }

    response = client.get('/api/lobbies/lobby_test/join-link', headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['join_url'].startswith('steam://run/393380//+connect')


def test_lobby_join_link_prefers_steam_lobby_id(flask_app):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    backend_app.lobbies['lobby_test_lobby_id'] = {
        'server_details': {
            'steamLobbyId': '109775243419695307',
            'connectAddress': '127.0.0.1:7787',
            'password': 'secretpass'
        }
    }

    response = client.get('/api/lobbies/lobby_test_lobby_id/join-link', headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert payload['join_url'] == 'steam://joinlobby/393380/109775243419695307'
