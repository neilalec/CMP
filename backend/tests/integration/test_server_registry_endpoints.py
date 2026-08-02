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


def _user_headers(flask_app, username='user'):
    backend_app.users[username] = {
        'password': 'unused',
        'steam_id': '76561198000000099'
    }
    with flask_app.app_context():
        token = create_access_token(identity=username)
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


def test_authenticated_user_can_test_and_submit_server(flask_app, monkeypatch):
    client = flask_app.test_client()
    headers = _user_headers(flask_app, username='submitter')

    fake_result = {
        'bridgeReachable': True,
        'capabilities': {
            'players': True,
            'layer_change': True,
            'broadcast': True,
            'round_result': True,
        },
        'serverInfo': {'serverName': 'Community Server'},
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    test_response = client.post('/api/servers/test', json={
        'display_name': 'Community Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers)
    assert test_response.status_code == 200
    assert test_response.get_json()['result']['bridgeReachable'] is True

    create_response = client.post('/api/servers/submit', json={
        'display_name': 'Community Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
        'connect_address': '127.0.0.1:7787'
    }, headers=headers)
    assert create_response.status_code == 201
    payload = create_response.get_json()
    assert payload['success'] is True
    assert payload['server']['display_name'] == 'Community Server'
    assert payload['server']['submitted_by'] == 'submitter'
    assert payload['server']['status'] == 'pending'


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
        'server_id': 77,
        'server_details': {
            'connectAddress': '127.0.0.1:7787',
            'password': 'secretpass'
        }
    }
    original_get_server_connection_details = backend_app.get_server_connection_details
    backend_app.get_server_connection_details = lambda server_id=None, lobby_id=None: {
        'connectAddress': '127.0.0.1:7787',
        'password': 'secretpass'
    }

    try:
        response = client.get('/api/lobbies/lobby_test/join-link', headers=headers)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['success'] is True
        assert payload['join_url'] == 'steam://connect/127.0.0.1:7787/secretpass'
    finally:
        backend_app.get_server_connection_details = original_get_server_connection_details


def test_lobby_join_link_prefers_synthetic_lobby_when_live_session_is_fresh(flask_app, monkeypatch):
    client = flask_app.test_client()
    headers = _admin_headers(flask_app)

    backend_app.lobbies['lobby_test_synthetic'] = {
        'server_id': 88,
        'server_details': {
            'connectAddress': '164.152.123.232:27050',
            'password': 'adhd',
            'liveSession': {
                'matched': True,
                'fresh': True,
                'targetServerId': '10afa1f20f534c248561dd53a25356e2',
                'lastSeenAt': 1000,
                'source': 'local_squad_log',
            }
        }
    }
    original_get_server_connection_details = backend_app.get_server_connection_details
    backend_app.get_server_connection_details = lambda server_id=None, lobby_id=None: {
        'connectAddress': '164.152.123.232:27050',
        'password': 'adhd',
        'liveSession': {
            'matched': True,
            'fresh': True,
            'targetServerId': '10afa1f20f534c248561dd53a25356e2',
            'lastSeenAt': 1000,
            'source': 'local_squad_log',
        }
    }
    monkeypatch.setattr(
        app_core,
        'create_synthetic_lobby_join_url_service',
        lambda bridge_request, session_id: {
            'ok': True,
            'lobbyId': '109775243617917159',
            'joinUrl': 'steam://joinlobby/393380/109775243617917159',
            'sessionId': session_id,
        }
    )

    try:
        response = client.get('/api/lobbies/lobby_test_synthetic/join-link', headers=headers)
        assert response.status_code == 200
        payload = response.get_json()
        assert payload['success'] is True
        assert payload['join_url'] == 'steam://joinlobby/393380/109775243617917159'
    finally:
        backend_app.get_server_connection_details = original_get_server_connection_details


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


def test_health_check_discovers_steam_lobby_id_from_bridge_payload(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': 'Bridge Steam ID Server',
            'steamID': '109775243617917159',
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    created = client.post('/api/admin/servers', json={
        'display_name': 'Bridge Steam ID Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload['server']['steam_lobby_id'] == '109775243617917159'


def test_health_check_records_bridge_network_identity(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': 'Verified Identity Server',
            'host': '164.152.123.232',
            'queryPort': 27165,
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {
            'ok': True,
            'details': {
                'host': '164.152.123.232',
                'queryPort': 27165,
            }
        }
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    created = client.post('/api/admin/servers', json={
        'display_name': 'Verified Identity Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    network_identity = health_payload['result']['networkIdentity']
    assert network_identity['host'] == '164.152.123.232'
    assert network_identity['queryPort'] == 27165
    assert network_identity['externalKey'] == '164.152.123.232:27165'


def test_health_check_surfaces_session_discovery_hints(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': 'Session Hint Server',
            'sessionCandidates': [
                {
                    'key': 'RedpointEOSRoomId_s',
                    'value': 'Session:EOS-SESSION-12345',
                }
            ],
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)

    created = client.post('/api/admin/servers', json={
        'display_name': 'Session Hint Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    session_discovery = health_payload['result']['sessionDiscovery']
    assert session_discovery['matched'] is True
    assert session_discovery['targetServerId'] == 'EOS-SESSION-12345'
    assert session_discovery['sourceField'] == 'RedpointEOSRoomId_s'


def test_health_check_surfaces_eos_matchmaking_resolution(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': '4K War Server',
            'host': '164.152.123.232',
            'queryPort': 27052,
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(
        server_registry_service,
        'lookup_eos_matchmaking_session',
        lambda server_name, connect_address='', host='', query_port=None, timeout=5: (
            'EOS-SESSION-12345',
            {
                'attempted': True,
                'configured': True,
                'serverName': server_name,
                'deploymentId': '5dee4062a90b42cd98fcad618b6636c2',
                'url': 'https://api.epicgames.dev/matchmaking/v1/5dee4062a90b42cd98fcad618b6636c2/filter',
                'matched': True,
                'matchedCount': 1,
                'sessionId': 'Session:EOS-SESSION-12345',
                'targetServerId': 'EOS-SESSION-12345',
                'sourceField': 'ADVERTISEDSESSIONID_s',
                'selectedServerName': server_name,
                'candidates': [],
                'error': '',
            },
        ),
    )

    created = client.post('/api/admin/servers', json={
        'display_name': '4K War Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload['result']['eosDiscovery']['matched'] is True
    assert health_payload['result']['eosDiscovery']['targetServerId'] == 'EOS-SESSION-12345'
    assert health_payload['result']['sessionDiscovery']['matched'] is True
    assert health_payload['result']['sessionDiscovery']['sourceField'] == 'eos_matchmaking.ADVERTISEDSESSIONID_s'


def test_health_check_surfaces_local_squad_log_resolution(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': '4K War Server',
            'host': '164.152.123.232',
            'queryPort': 27052,
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {'ok': True}
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(
        server_registry_service,
        'lookup_eos_matchmaking_session',
        lambda server_name, connect_address='', host='', query_port=None, timeout=5: (
            '',
            {
                'attempted': False,
                'configured': False,
                'serverName': server_name,
                'deploymentId': '5dee4062a90b42cd98fcad618b6636c2',
                'url': '',
                'matched': False,
                'matchedCount': 0,
                'sessionId': '',
                'targetServerId': '',
                'sourceField': '',
                'selectedServerName': '',
                'candidates': [],
                'error': '',
            },
        ),
    )
    monkeypatch.setattr(
        server_registry_service,
        'lookup_local_log_session_id',
        lambda connect_address='': (
            '10afa1f20f534c248561dd53a25356e2',
            {
                'attempted': True,
                'configured': True,
                'logPath': 'C:\\Users\\neila\\AppData\\Local\\SquadGame\\Saved\\Logs\\SquadGame.log',
                'matched': True,
                'targetServerId': '10afa1f20f534c248561dd53a25356e2',
                'sessionId': 'Session:10afa1f20f534c248561dd53a25356e2',
                'roomId': 'Session:10afa1f20f534c248561dd53a25356e2',
                'connectAddress': connect_address,
                'matchedConnectAddress': True,
                'sourceField': 'RedpointEOSRoomId',
                'error': '',
            },
        ),
    )

    created = client.post('/api/admin/servers', json={
        'display_name': '4K War Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
        'connect_address': '164.152.123.232:27050',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload['result']['sessionDiscovery']['matched'] is True
    assert health_payload['result']['sessionDiscovery']['targetServerId'] == '10afa1f20f534c248561dd53a25356e2'
    assert health_payload['result']['sessionDiscovery']['sourceField'] == 'local_squad_log.RedpointEOSRoomId'
    assert health_payload['result']['eosDiscovery']['clientLog']['matched'] is True
    assert health_payload['result']['liveSession']['matched'] is True
    assert health_payload['result']['liveSession']['targetServerId'] == '10afa1f20f534c248561dd53a25356e2'


def test_health_check_discovers_steam_lobby_id_from_a2s_query(flask_app, monkeypatch):
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
        'serverInfo': {
            'serverName': 'A2S Identity Server',
            'host': '164.152.123.232',
            'queryPort': 27165,
        },
        'warnings': [],
        'playerCount': 0,
        'bridge': {
            'ok': True,
            'details': {
                'host': '164.152.123.232',
                'queryPort': 27165,
            }
        }
    }
    monkeypatch.setattr(backend_app, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'test_server_connection', lambda payload: fake_result)
    monkeypatch.setattr(server_registry_service, 'query_a2s_info_steam_id', lambda host, query_port, timeout=3: '109775243617917159')

    created = client.post('/api/admin/servers', json={
        'display_name': 'A2S Identity Server',
        'bridge_url': 'http://127.0.0.1:3001',
        'bridge_token': 'secret-token',
    }, headers=headers).get_json()['server']

    health_response = client.post(f"/api/admin/servers/{created['id']}/health-check", headers=headers)
    assert health_response.status_code == 200
    health_payload = health_response.get_json()
    assert health_payload['server']['steam_lobby_id'] == '109775243617917159'
