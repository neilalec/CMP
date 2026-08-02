import random

from sockets.queue import handle_clear_queue_event, handle_seed_queue_event


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class DummyRequest:
    sid = 'admin-sid'


class DummyLogger:
    def error(self, message):
        self.last_error = message


def test_seed_queue_uses_mock_usernames_and_creates_groups():
    random.seed(7)
    users = {}
    groups = {}
    user_to_group = {}
    matchmaking_queue = {'skirmish': []}
    statuses = {}
    hashed_passwords = []

    response = handle_seed_queue_event(
        {'queueMode': 'skirmish', 'count': 12},
        request=DummyRequest(),
        socket_events={},
        socketio=None,
        broadcast_queue_update=lambda: None,
        logger=DummyLogger(),
        get_username_by_sid=lambda sid: 'admin',
        is_admin_user=lambda username: True,
        users=users,
        save_users=lambda: None,
        hash_password=lambda value: hashed_passwords.append(value) or f'hashed:{value}',
        queue_lock=DummyLock(),
        matchmaking_queue=matchmaking_queue,
        queue_modes={'skirmish': {'max_players': 12}},
        upsert_player_activity=lambda username, **kwargs: statuses.__setitem__(username, kwargs.get('status')),
        save_queue=lambda: None,
        build_queue_payload=lambda **kwargs: {'queueMode': kwargs.get('queue_mode')},
        check_queue_and_start_countdown=lambda: None,
        get_pending_match=lambda queue_mode: None,
        finalize_pending_match=lambda match_id: None,
        group_lock=DummyLock(),
        groups=groups,
        user_to_group=user_to_group,
    )

    assert response['success'] is True
    assert len(response['seeded']) == 12
    assert matchmaking_queue['skirmish'] == response['seeded']
    assert all('_bot_' not in username for username in response['seeded'])
    assert hashed_passwords == ['seed-player-dev-password']
    assert {record['password'] for record in users.values()} == {'hashed:seed-player-dev-password'}
    assert all(status == 'queued' for status in statuses.values())
    assert response['seededGroups']
    assert response['seededGroups'] == [
        {
            'code': code,
            'leader': group['leader'],
            'members': group['members'],
        }
        for code, group in groups.items()
    ]
    grouped_members = {
        member
        for group in response['seededGroups']
        for member in group['members']
    }
    assert grouped_members <= set(response['seeded'])
    assert all(user_to_group[member] in groups for member in grouped_members)
    assert response['message'] == 'Seeded 12 mock players'


def test_admin_can_seed_queue_without_extra_feature_flag():
    users = {}
    matchmaking_queue = {'skirmish': []}

    response = handle_seed_queue_event(
        {'queueMode': 'skirmish', 'count': 2},
        request=DummyRequest(),
        socket_events={},
        socketio=None,
        broadcast_queue_update=lambda: None,
        logger=DummyLogger(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: username == 'neil',
        users=users,
        save_users=lambda: None,
        hash_password=lambda value: f'hashed:{value}',
        queue_lock=DummyLock(),
        matchmaking_queue=matchmaking_queue,
        queue_modes={'skirmish': {'max_players': 2}},
        upsert_player_activity=lambda username, **kwargs: None,
        save_queue=lambda: None,
        build_queue_payload=lambda **kwargs: {'queueMode': kwargs.get('queue_mode')},
        check_queue_and_start_countdown=lambda: None,
        get_pending_match=lambda queue_mode: None,
        finalize_pending_match=lambda match_id: None,
    )

    assert response['success'] is True
    assert len(response['seeded']) == 2
    assert matchmaking_queue['skirmish'] == response['seeded']


def test_admin_can_clear_queue_without_extra_feature_flag():
    matchmaking_queue = {'skirmish': ['alice', 'bob']}
    player_activity = {
        'alice': {'status': 'queued'},
        'bob': {'status': 'queued'},
    }
    cancelled = []

    response = handle_clear_queue_event(
        {'queueMode': 'skirmish'},
        request=DummyRequest(),
        socket_events={},
        socketio=None,
        broadcast_queue_update=lambda: None,
        logger=DummyLogger(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: username == 'neil',
        queue_lock=DummyLock(),
        matchmaking_queue=matchmaking_queue,
        player_activity=player_activity,
        save_queue=lambda: None,
        build_queue_payload=lambda **kwargs: {'queueMode': kwargs.get('queue_mode')},
        cancel_pending_match=lambda reason, remove_players=None, queue_mode=None: cancelled.append((reason, remove_players, queue_mode)),
    )

    assert response['success'] is True
    assert matchmaking_queue['skirmish'] == []
    assert player_activity['alice']['status'] == 'authenticated'
    assert player_activity['bob']['status'] == 'authenticated'
    assert cancelled == [('Queue cleared by admin.', ['alice', 'bob'], 'skirmish')]
