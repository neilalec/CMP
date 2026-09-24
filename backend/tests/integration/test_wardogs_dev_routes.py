import app as backend_app
import matchmaking
from flask_jwt_extended import create_access_token
from services.wardogs_dev import fill_queue
from services.wardogs_lobby import get_wardogs_lobby


def _headers(flask_app, username):
    with flask_app.app_context():
        token = create_access_token(identity=username)
    return {'Authorization': f'Bearer {token}'}


def test_dev_routes_require_local_mode_and_admin(flask_app, monkeypatch):
    client = flask_app.test_client()
    url = '/api/admin/dev/wardogs/fill'
    assert client.post(url).status_code == 401
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda name: name == 'admin')
    assert client.post(url, headers=_headers(flask_app, 'player')).status_code == 404
    monkeypatch.setattr(backend_app, 'DEV_MODE', False)
    assert client.post(url, headers=_headers(flask_app, 'admin')).status_code == 404
    assert client.post('/api/admin/dev/wardogs/simulate',
                       headers=_headers(flask_app, 'admin'), json={'lobbyId': 'x', 'enabled': True}).status_code == 404
    assert client.post('/api/admin/dev/wardogs/reset', headers=_headers(flask_app, 'admin')).status_code == 404


def test_dev_status_available_only_to_admin_in_local_mode(flask_app, monkeypatch):
    monkeypatch.setattr(backend_app, 'DEV_MODE', True)
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda name: name == 'admin')
    response = flask_app.test_client().get('/api/admin/dev/wardogs',
                                           headers=_headers(flask_app, 'admin'))
    assert response.status_code == 200
    assert response.get_json()['queueMode'] == 'wardogs_beta9'


def test_dev_fill_uses_normal_acceptance_and_three_by_three_finalizer(flask_app, monkeypatch):
    from threading import RLock
    monkeypatch.setattr(backend_app, 'DEV_MODE', True)
    monkeypatch.setattr(backend_app, 'users', {'neil': {'steam_id': '76561198000000001'}})
    monkeypatch.setattr(backend_app, 'matchmaking_queue', {'wardogs_beta9': ['neil']})
    monkeypatch.setattr(backend_app, 'pending_match', {'wardogs_beta9': None})
    monkeypatch.setattr(backend_app, 'queue_lock', RLock())
    monkeypatch.setattr(backend_app, 'groups', {})
    monkeypatch.setattr(backend_app, 'user_to_group', {})
    monkeypatch.setattr(backend_app, 'allocate_server_for_lobby', lambda *_args, **_kwargs: None)
    monkeypatch.setattr('services.queue.eventlet.spawn', lambda _task: None)
    fill_queue(
        enabled=True, username='neil', users=backend_app.users,
        matchmaking_queue=backend_app.matchmaking_queue, queue_lock=backend_app.queue_lock,
        upsert_player_activity=lambda *_args, **_kwargs: None,
        save_users=lambda: None, save_queue=lambda: None,
        check_queue_and_start_countdown=matchmaking.check_queue_and_start_countdown,
        pending_match=backend_app.pending_match,
        broadcast_queue_update=lambda: None)
    pending = backend_app.pending_match['wardogs_beta9']
    assert pending and pending['accepted']['neil'] is False
    assert sum(pending['accepted'].values()) == 8
    pending['accepted']['neil'] = True
    lobby_id = matchmaking.finalize_pending_match(pending['id'])
    lobby = get_wardogs_lobby(backend_app.get_db_connection, lobby_id)
    assert sorted(sum(len(group['players']) for group in faction['groups'])
                  for faction in lobby['factions']) == [3, 3, 3]
    assert lobby['provenance']['snapshotSource'] == 'accepted_cmp_party_snapshot'
