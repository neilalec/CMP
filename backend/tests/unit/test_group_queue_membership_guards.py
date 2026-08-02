from sockets.group import handle_group_create_event, handle_group_join_event, handle_group_leave_event
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
