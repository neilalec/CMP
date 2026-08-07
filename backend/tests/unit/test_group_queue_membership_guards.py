from sockets.group import (
    handle_group_create_event,
    handle_group_join_event,
    handle_group_leave_event,
    handle_group_queue_event,
    handle_group_seed_event,
)
from sockets.lobby import handle_join_lobby_event


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


class DummyLogger:
    def __init__(self):
        self.messages = []
        self.last_error = None

    def info(self, message):
        self.messages.append(('info', message))

    def warning(self, message):
        self.messages.append(('warning', message))

    def error(self, message):
        self.last_error = message
        self.messages.append(('error', message))


class DummyRequest:
    sid = 'sid-1'


class DummySocketServer:
    def __init__(self):
        self.left_rooms = []

    def leave_room(self, sid, room):
        self.left_rooms.append((sid, room))


class DummySocket:
    def __init__(self):
        self.server = DummySocketServer()
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def build_group_context():
    groups = {
        'ABC123': {
            'code': 'ABC123',
            'leader': 'alice',
            'members': ['alice'],
        }
    }
    user_to_group = {'alice': 'ABC123'}
    broadcasts = []
    joined_rooms = []
    left_rooms = []

    def get_user_group(username):
        return user_to_group.get(username)

    def get_group_payload(code):
        group = groups.get(code)
        if not group:
            return None
        return {
            'code': group['code'],
            'leader': group['leader'],
            'members': list(group['members']),
        }

    return {
        'logger': DummyLogger(),
        'group_lock': DummyLock(),
        'queue_lock': DummyLock(),
        'matchmaking_queue': {
            'skirmish': [],
            'hotdrop': [],
        },
        'is_user_in_any_lobby': lambda username: False,
        'get_user_group': get_user_group,
        'generate_group_code': lambda: 'NEW123',
        'groups': groups,
        'max_lobby_players': 40,
        'user_to_group': user_to_group,
        'upsert_player_activity': lambda *args, **kwargs: None,
        'join_room': lambda room: joined_rooms.append(room),
        'leave_room': lambda room: left_rooms.append(room),
        'get_group_payload': get_group_payload,
        'broadcast_group_update': lambda code, payload: broadcasts.append((code, payload)),
        'broadcasts': broadcasts,
        'joined_rooms': joined_rooms,
        'left_rooms': left_rooms,
    }


def test_queued_user_cannot_create_group():
    context = build_group_context()
    context['matchmaking_queue']['skirmish'].append('bob')

    response = handle_group_create_event(
        {'username': 'bob'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'max_lobby_players',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'Leave the queue before creating a group',
    }
    assert 'NEW123' not in context['groups']


def test_group_queue_rejects_groups_larger_than_team_size():
    groups = {
        'DUO123': {
            'code': 'DUO123',
            'leader': 'alice',
            'members': ['alice', 'bob'],
        },
        'TEN123': {
            'code': 'TEN123',
            'leader': 'p1',
            'members': [f'p{index}' for index in range(1, 11)],
        },
    }
    user_to_group = {
        'alice': 'DUO123',
        'bob': 'DUO123',
        **{f'p{index}': 'TEN123' for index in range(1, 11)}
    }

    def queue_group(username, queue_mode):
        return handle_group_queue_event(
            {'username': username, 'queueMode': queue_mode},
            logger=DummyLogger(),
            group_lock=DummyLock(),
            get_user_group=lambda member: user_to_group.get(member),
            groups=groups,
            queue_lock=DummyLock(),
            matchmaking_queue={'ocbt1': [], 'ocbt5': []},
            queue_modes={
                'ocbt1': {'team_size': 1, 'max_players': 2},
                'ocbt5': {'team_size': 5, 'max_players': 10},
            },
            user_has_steam_id=lambda member: True,
            is_user_in_any_lobby=lambda member: False,
            upsert_player_activity=lambda *args, **kwargs: None,
            save_queue=lambda: None,
            broadcast_queue_update=lambda: None,
            check_queue_and_start_countdown=lambda: None,
            build_queue_payload=lambda **kwargs: {'success': True},
            has_available_server_capacity=lambda *args, **kwargs: True,
            lobbies={},
            pending_match={},
        )

    assert queue_group('alice', 'ocbt1') == {
        'success': False,
        'message': 'Group is too large to stay on one team',
    }
    assert queue_group('p1', 'ocbt5') == {
        'success': False,
        'message': 'Group is too large to stay on one team',
    }


def test_admin_can_seed_current_group_with_custom_bot_count():
    context = build_group_context()
    users = {'alice': {'steam_id': '76561198000000001'}}
    saved_users = []
    activity = []

    response = handle_group_seed_event(
        {'count': 3},
        request=DummyRequest(),
        logger=DummyLogger(),
        group_lock=context['group_lock'],
        get_user_group=lambda username: context['user_to_group'].get(username),
        queue_lock=context['queue_lock'],
        matchmaking_queue=context['matchmaking_queue'],
        is_user_in_any_lobby=lambda username: False,
        groups=context['groups'],
        user_to_group=context['user_to_group'],
        users=users,
        save_users=lambda: saved_users.append(True),
        hash_password=lambda password: f'hashed:{password}',
        upsert_player_activity=lambda username, **kwargs: activity.append((username, kwargs)),
        get_group_payload=context['get_group_payload'],
        broadcast_group_update=context['broadcast_group_update'],
        get_username_by_sid=lambda sid: 'alice',
        is_admin_user=lambda username: username == 'alice',
        max_group_members=5,
    )

    assert response['success'] is True
    assert len(response['seeded']) == 3
    assert context['groups']['ABC123']['members'][0] == 'alice'
    assert len(context['groups']['ABC123']['members']) == 4
    assert saved_users == [True]
    assert len(activity) == 3
    for seed_username in response['seeded']:
        assert seed_username in users
        assert users[seed_username]['password'] == 'hashed:seed-player-dev-password'
        assert context['user_to_group'][seed_username] == 'ABC123'


def test_group_seed_is_admin_only_and_capped_to_max_group_members():
    context = build_group_context()

    denied = handle_group_seed_event(
        {'count': 1},
        request=DummyRequest(),
        logger=DummyLogger(),
        group_lock=context['group_lock'],
        get_user_group=lambda username: context['user_to_group'].get(username),
        queue_lock=context['queue_lock'],
        matchmaking_queue=context['matchmaking_queue'],
        is_user_in_any_lobby=lambda username: False,
        groups=context['groups'],
        user_to_group=context['user_to_group'],
        users={},
        save_users=lambda: None,
        hash_password=lambda password: password,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_group_payload=context['get_group_payload'],
        broadcast_group_update=context['broadcast_group_update'],
        get_username_by_sid=lambda sid: 'alice',
        is_admin_user=lambda username: False,
        max_group_members=5,
    )

    capped = handle_group_seed_event(
        {'count': 12},
        request=DummyRequest(),
        logger=DummyLogger(),
        group_lock=context['group_lock'],
        get_user_group=lambda username: context['user_to_group'].get(username),
        queue_lock=context['queue_lock'],
        matchmaking_queue=context['matchmaking_queue'],
        is_user_in_any_lobby=lambda username: False,
        groups=context['groups'],
        user_to_group=context['user_to_group'],
        users={'alice': {}},
        save_users=lambda: None,
        hash_password=lambda password: password,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_group_payload=context['get_group_payload'],
        broadcast_group_update=context['broadcast_group_update'],
        get_username_by_sid=lambda sid: 'alice',
        is_admin_user=lambda username: True,
        max_group_members=3,
    )

    assert denied == {'success': False, 'message': 'Admin only'}
    assert capped['success'] is True
    assert len(capped['seeded']) == 2
    assert len(context['groups']['ABC123']['members']) == 3


def test_queued_user_cannot_join_group():
    context = build_group_context()
    context['matchmaking_queue']['skirmish'].append('bob')

    response = handle_group_join_event(
        {'username': 'bob', 'code': 'ABC123'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'Leave the queue before joining a group',
    }
    assert context['groups']['ABC123']['members'] == ['alice']


def test_user_cannot_join_group_that_is_already_queued():
    context = build_group_context()
    context['matchmaking_queue']['skirmish'].append('alice')

    response = handle_group_join_event(
        {'username': 'bob', 'code': 'ABC123'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'This group is already queued. Ask the leader to leave the queue before new members join.',
    }
    assert context['groups']['ABC123']['members'] == ['alice']


def test_user_can_leave_group_while_group_is_queued_and_is_removed_from_queue():
    context = build_group_context()
    context['groups']['ABC123']['members'].append('bob')
    context['user_to_group']['bob'] = 'ABC123'
    context['matchmaking_queue']['skirmish'].extend(['alice', 'bob'])
    queue_saves = []
    queue_broadcasts = []

    response = handle_group_leave_event(
        {'username': 'bob'},
        save_queue=lambda: queue_saves.append(True),
        broadcast_queue_update=lambda: queue_broadcasts.append(True),
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'max_lobby_players',
            'join_room',
            'upsert_player_activity',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response['success'] is True
    assert response['removedFromQueue'] is True
    assert context['groups']['ABC123']['members'] == ['alice']
    assert 'bob' not in context['user_to_group']
    assert context['matchmaking_queue']['skirmish'] == ['alice']
    assert queue_saves == [True]
    assert queue_broadcasts == [True]


def test_user_in_lobby_cannot_create_group():
    context = build_group_context()
    context['is_user_in_any_lobby'] = lambda username: username == 'bob'

    response = handle_group_create_event(
        {'username': 'bob'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'max_lobby_players',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'Leave the lobby before creating a group',
    }
    assert 'NEW123' not in context['groups']


def test_user_in_lobby_cannot_join_group():
    context = build_group_context()
    context['is_user_in_any_lobby'] = lambda username: username == 'bob'

    response = handle_group_join_event(
        {'username': 'bob', 'code': 'ABC123'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'Leave the lobby before joining a group',
    }
    assert context['groups']['ABC123']['members'] == ['alice']


def test_user_cannot_join_group_that_has_member_in_lobby():
    context = build_group_context()
    context['is_user_in_any_lobby'] = lambda username: username == 'alice'

    response = handle_group_join_event(
        {'username': 'bob', 'code': 'ABC123'},
        request=DummyRequest(),
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'leave_room',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response == {
        'success': False,
        'message': 'This group has a member in a lobby. Group changes are locked until everyone leaves the lobby.',
    }
    assert context['groups']['ABC123']['members'] == ['alice']


def test_user_can_leave_group_while_another_group_member_is_in_lobby():
    context = build_group_context()
    context['groups']['ABC123']['members'].append('bob')
    context['user_to_group']['bob'] = 'ABC123'
    context['is_user_in_any_lobby'] = lambda username: username == 'alice'

    response = handle_group_leave_event(
        {'username': 'bob'},
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'max_lobby_players',
            'join_room',
            'upsert_player_activity',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response['success'] is True
    assert context['groups']['ABC123']['members'] == ['alice']
    assert 'bob' not in context['user_to_group']


def test_leaving_group_removes_user_from_lobby_and_visual_grouping():
    context = build_group_context()
    context['groups']['ABC123']['members'].append('bob')
    context['user_to_group']['bob'] = 'ABC123'
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': 'alice', 'team2': 'bob'},
            'step': 3,
            'max_players': 4,
            'map_pool': ['Map A'],
            'map_votes': {'alice': 'Map A', 'bob': 'Map A'},
            'player_groups': {'alice': 'ABC123', 'bob': 'ABC123'},
            'disconnected_players': set(),
        }
    }
    player_activity = {'bob': {'lobby_id': 'lobby_1', 'status': 'in_lobby'}}
    socketio = DummySocket()
    open_lobby_broadcasts = []
    active_syncs = []

    response = handle_group_leave_event(
        {'username': 'bob'},
        lobbies=lobbies,
        player_activity=player_activity,
        get_player_sids=lambda username: ['sid-bob'],
        socketio=socketio,
        broadcast_open_lobbies_update=lambda: open_lobby_broadcasts.append(True),
        emit_active_lobby_sync=lambda username, lobby_id: active_syncs.append((username, lobby_id)),
        select_captains=lambda teams: {'team1': teams['team1'][0] if teams['team1'] else None, 'team2': None},
        **{key: value for key, value in context.items() if key not in {
            'generate_group_code',
            'max_lobby_players',
            'join_room',
            'upsert_player_activity',
            'broadcasts',
            'joined_rooms',
            'left_rooms',
        }}
    )

    assert response['success'] is True
    assert response['leftLobby'] is True
    assert lobbies['lobby_1']['players'] == ['alice']
    assert lobbies['lobby_1']['teams'] == {'team1': ['alice'], 'team2': []}
    assert lobbies['lobby_1']['map_votes'] == {'alice': 'Map A'}
    assert lobbies['lobby_1']['player_groups'] == {'alice': 'ABC123'}
    assert player_activity['bob']['status'] == 'authenticated'
    assert 'lobby_id' not in player_activity['bob']
    assert ('sid-bob', 'lobby_1') in socketio.server.left_rooms
    assert ('bob', None) in active_syncs
    assert open_lobby_broadcasts == [True]

    rejoin_logger = DummyLogger()
    rejoin_response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'bob', 'allow_new': True},
        request=DummyRequest(),
        logger=rejoin_logger,
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=4,
        get_user_group=lambda username: context['user_to_group'].get(username),
        groups=context['groups'],
        user_to_group=context['user_to_group'],
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: None,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {
            player: context['user_to_group'][player]
            for player in players
            if player in context['user_to_group']
        },
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: None,
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
    )

    assert rejoin_response['success'] is True, (rejoin_response, rejoin_logger.last_error)
    assert rejoin_response['data']['player_groups'] == {'alice': 'ABC123'}
    assert lobbies['lobby_1']['player_groups'] == {'alice': 'ABC123'}
