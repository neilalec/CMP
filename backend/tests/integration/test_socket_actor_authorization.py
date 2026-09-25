"""User-facing socket commands cannot choose their actor from a payload."""

import pytest
from flask_jwt_extended import create_access_token

import app as backend


AUTHENTICATED_EVENTS = (
    'profile_status', 'profile_update_steam_id', 'profile_update_display_name',
    'join-queue', 'leave-queue', 'queue_status', 'queue_seed', 'queue_clear',
    'queue_set_enabled', 'queue_accept_match',
    'group_create', 'group_join', 'group_leave', 'group_kick', 'group_transfer',
    'group_status', 'group_seed', 'group_queue', 'group_unqueue',
    'open_lobbies_status', 'countdown_status', 'pause-countdown',
    'join-lobby', 'spectate-lobby', 'leave-lobby', 'delete-lobby',
    'get-lobby-data', 'lobby_server_presence', 'force-live-ready', 'vote-map',
    'skip-phase', 'prev-phase', 'start-lobby',
)


@pytest.fixture
def actors(flask_app, monkeypatch):
    originals = {
        'users': dict(backend.users),
        'activity': dict(backend.player_activity),
        'groups': dict(backend.groups),
        'user_to_group': dict(backend.user_to_group),
        'queues': {mode: list(queue) for mode, queue in backend.matchmaking_queue.items()},
        'pending': dict(backend.pending_match),
        'lobbies': dict(backend.lobbies),
    }
    backend.users.clear()
    backend.users.update({
        name: {'password': '', 'steam_id': f'7656119800000000{index}',
               'display_name': name}
        for index, name in enumerate(('alice', 'bob', 'admin'), 1)
    })
    backend.player_activity.clear()
    backend.groups.clear()
    backend.user_to_group.clear()
    backend.lobbies.clear()
    for queue in backend.matchmaking_queue.values():
        queue.clear()
    for mode in backend.pending_match:
        backend.pending_match[mode] = None
    monkeypatch.setattr(backend, 'is_admin_user', lambda name: name == 'admin')

    clients = []

    def connect(name=None):
        auth = None
        if name:
            with flask_app.app_context():
                auth = {'token': create_access_token(identity=name), 'username': name}
        client = backend.socketio.test_client(flask_app, auth=auth)
        assert client.is_connected()
        clients.append(client)
        return client

    yield connect

    for client in clients:
        if client.is_connected():
            client.disconnect()
    backend.users.clear()
    backend.users.update(originals['users'])
    backend.player_activity.clear()
    backend.player_activity.update(originals['activity'])
    backend.groups.clear()
    backend.groups.update(originals['groups'])
    backend.user_to_group.clear()
    backend.user_to_group.update(originals['user_to_group'])
    backend.lobbies.clear()
    backend.lobbies.update(originals['lobbies'])
    for mode, queue in originals['queues'].items():
        backend.matchmaking_queue[mode][:] = queue
    backend.pending_match.clear()
    backend.pending_match.update(originals['pending'])


def test_queue_join_and_leave_use_authenticated_actor(actors):
    alice = actors('alice')
    alice.emit('join-queue', {'username': 'bob', 'queueMode': 'skirmish'})
    assert 'alice' in backend.matchmaking_queue['skirmish']
    assert 'bob' not in backend.matchmaking_queue['skirmish']
    backend.matchmaking_queue['skirmish'].append('bob')
    alice.emit('leave-queue', {'username': 'bob', 'queueMode': 'skirmish'})
    assert 'alice' not in backend.matchmaking_queue['skirmish']
    assert 'bob' in backend.matchmaking_queue['skirmish']


def test_match_accept_cannot_accept_for_another_player(actors):
    alice = actors('alice')
    pending = {'id': 'actor-test', 'queue_mode': 'skirmish', 'game_type': 'squad',
               'players': ['alice', 'bob'], 'accepted': {'alice': False, 'bob': False}}
    backend.pending_match['skirmish'] = pending
    response = alice.emit('queue_accept_match', {'username': 'bob'}, callback=True)
    assert response['success'] is True
    assert pending['accepted'] == {'alice': True, 'bob': False}


def test_group_actor_and_leader_checks_preserve_target(actors):
    alice, bob = actors('alice'), actors('bob')
    created = alice.emit('group_create', {'username': 'bob'}, callback=True)
    assert created['success'] is True
    group = created['group']
    assert group['leader'] == 'alice'
    joined = bob.emit('group_join', {'username': 'alice', 'code': group['code']}, callback=True)
    assert joined['success'] is True
    denied = bob.emit('group_kick', {'username': 'alice', 'targetUsername': 'alice'}, callback=True)
    assert denied['success'] is False
    assert backend.groups[group['code']]['members'] == ['alice', 'bob']
    denied = bob.emit('group_transfer', {'username': 'alice', 'targetUsername': 'bob'}, callback=True)
    assert denied['success'] is False
    assert backend.groups[group['code']]['leader'] == 'alice'
    allowed = alice.emit('group_transfer', {'username': 'bob', 'targetUsername': 'bob'}, callback=True)
    assert allowed['success'] is True
    assert backend.groups[group['code']]['leader'] == 'bob'


def test_group_leave_and_profile_updates_use_authenticated_actor(actors):
    alice, bob = actors('alice'), actors('bob')
    group = alice.emit('group_create', {'username': 'bob'}, callback=True)['group']
    bob.emit('group_join', {'username': 'alice', 'code': group['code']}, callback=True)
    profile = alice.emit('profile_status', {'username': 'bob'}, callback=True)
    assert profile['profile']['username'] == 'alice'
    updated = alice.emit('profile_update_display_name',
                         {'username': 'bob', 'display_name': 'Alice Updated'}, callback=True)
    assert updated['success'] is True
    assert backend.users['alice']['display_name'] == 'Alice Updated'
    assert backend.users['bob']['display_name'] == 'bob'
    left = bob.emit('group_leave', {'username': 'alice'}, callback=True)
    assert left['success'] is True
    assert backend.groups[group['code']]['members'] == ['alice']


def test_anonymous_socket_cannot_bind_claimed_username_or_run_commands(actors, flask_app):
    anonymous = actors()
    assert anonymous.emit('authenticate', {'username': 'bob'}, callback=True) is False
    assert anonymous.emit('group_create', {'username': 'bob'}, callback=True)['success'] is False
    assert anonymous.emit('queue_accept_match', {'username': 'bob'}, callback=True)['success'] is False
    anonymous.emit('join-queue', {'username': 'bob', 'queueMode': 'skirmish'})
    assert 'bob' not in backend.matchmaking_queue['skirmish']
    with flask_app.app_context():
        token = create_access_token(identity='alice')
    assert anonymous.emit('authenticate', {'token': token, 'username': 'bob'}, callback=True) is False
    assert anonymous.emit('authenticate', {'token': token, 'username': 'alice'}, callback=True) is True
    assert anonymous.emit('group_create', {'username': 'bob'}, callback=True)['group']['leader'] == 'alice'


def test_every_registered_participant_command_rejects_anonymous_sid(actors):
    anonymous = actors()
    for event in AUTHENTICATED_EVENTS:
        response = anonymous.emit(event, {'username': 'admin'}, callback=True)
        assert response == {'success': False, 'message': 'Authentication required'}, event


def test_non_admin_cannot_impersonate_admin_and_disconnect_clears_sid(actors):
    alice = actors('alice')
    response = alice.emit('queue_clear', {'username': 'admin'}, callback=True)
    assert response['success'] is False
    response = alice.emit('group_seed', {'username': 'admin', 'count': 1}, callback=True)
    assert response['success'] is False
    response = alice.emit('start-lobby', {'username': 'admin', 'lobby_id': 'any'}, callback=True)
    assert response == {'success': False, 'message': 'Admin access required'}
    sid = next(iter(backend.get_player_sids('alice')))
    alice.disconnect()
    assert backend.get_username_by_sid(sid) is None
    replacement = actors('alice')
    assert replacement.emit('group_status', {'username': 'bob'}, callback=True)['success'] is True


def test_password_login_binds_and_rebinds_one_sid(actors, monkeypatch):
    monkeypatch.setattr(backend, 'PASSWORD_AUTH_ENABLED', True)
    backend.users['alice']['password'] = backend.hash_password('alice-secret')
    backend.users['bob']['password'] = backend.hash_password('bob-secret')
    client = actors()
    assert client.emit('login', {'username': 'alice', 'password': 'alice-secret'},
                       callback=True)['success'] is True
    sid = next(iter(backend.get_player_sids('alice')))
    assert client.emit('profile_status', {'username': 'bob'}, callback=True)['profile']['username'] == 'alice'
    assert client.emit('login', {'username': 'bob', 'password': 'bob-secret'},
                       callback=True)['success'] is True
    assert sid not in backend.get_player_sids('alice')
    assert sid in backend.get_player_sids('bob')
    assert client.emit('profile_status', {'username': 'alice'}, callback=True)['profile']['username'] == 'bob'
