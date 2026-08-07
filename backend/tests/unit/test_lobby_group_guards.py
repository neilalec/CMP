from sockets.lobby import handle_force_live_ready_event, handle_join_lobby_event, vote_map_event
from state.lobby import find_active_lobby_for_user, is_user_in_any_lobby
import app as backend_app
import wiring


class DummyLogger:
    def __init__(self):
        self.messages = []

    def info(self, message, *args, **kwargs):
        self.messages.append(('info', message % args if args else message))

    def warning(self, message, *args, **kwargs):
        self.messages.append(('warning', message % args if args else message))

    def error(self, message, *args, **kwargs):
        self.messages.append(('error', message % args if args else message))


class DummyRequest:
    sid = 'sid-1'


def test_socket_backend_exports_admin_lobby_handlers():
    backend = wiring._socket_backend_api()

    assert backend.handle_force_live_ready_event is backend_app.handle_force_live_ready_event
    assert backend.handle_group_seed_event is backend_app.handle_group_seed_event


def test_group_member_cannot_join_open_lobby_directly():
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'captains': {'team1': None, 'team2': None},
            'step': 2,
            'max_players': 4,
            'map_pool': [],
        }
    }

    response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'bob', 'allow_new': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=4,
        get_user_group=lambda username: 'ABC123' if username == 'bob' else None,
        groups={'ABC123': {'members': ['bob']}},
        user_to_group={'bob': 'ABC123'},
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: None,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {},
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: None,
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
    )

    assert response == {
        'success': False,
        'message': 'Leave your group before joining an open lobby directly.',
    }
    assert lobbies['lobby_1']['players'] == ['alice']


def test_new_player_cannot_join_finalized_lobby_with_open_slot():
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'captains': {'team1': None, 'team2': None},
            'step': 5,
            'max_players': 4,
            'map_pool': [],
        }
    }

    response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'bob', 'allow_new': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=4,
        get_user_group=lambda username: None,
        groups={},
        user_to_group={},
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: None,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {},
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: None,
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
    )

    assert response == {
        'success': False,
        'message': 'This lobby has finished and is closed to new players.',
    }
    assert lobbies['lobby_1']['players'] == ['alice']


def test_finalized_lobby_does_not_count_as_active_membership():
    backend_app.lobbies.clear()
    backend_app.lobbies.update({
        'lobby_final': {
            'players': ['alice'],
            'step': 5,
        },
        'lobby_live': {
            'players': ['bob'],
            'step': 3,
        },
    })

    assert find_active_lobby_for_user('alice') is None
    assert is_user_in_any_lobby('alice') is False
    assert find_active_lobby_for_user('bob') == 'lobby_live'
    assert is_user_in_any_lobby('bob') is True


def test_group_member_can_rejoin_lobby_they_are_already_in():
    joined_rooms = []
    synced = []
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': None, 'team2': None},
            'step': 2,
            'max_players': 4,
            'map_pool': [],
        }
    }

    response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'bob', 'rejoin': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=4,
        get_user_group=lambda username: 'ABC123' if username == 'bob' else None,
        groups={'ABC123': {'members': ['bob']}},
        user_to_group={'bob': 'ABC123'},
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: joined_rooms.append(room),
        upsert_player_activity=lambda *args, **kwargs: None,
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {},
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: synced.append((username, lobby_id)),
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
    )

    assert response['success'] is True
    assert response['data']['players'] == ['alice', 'bob']
    assert 'lobby_1' in joined_rooms
    assert ('bob', 'lobby_1') in synced


def test_admin_can_spectate_lobby_without_becoming_player():
    joined_rooms = []
    synced = []
    activity = {}
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'captains': {'team1': None, 'team2': None},
            'step': 3,
            'max_players': 2,
            'map_pool': [],
        }
    }

    response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'neil', 'spectate': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=2,
        get_user_group=lambda username: None,
        groups={},
        user_to_group={},
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: joined_rooms.append(room),
        upsert_player_activity=lambda username, **kwargs: activity.update({username: kwargs}),
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {},
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: synced.append((username, lobby_id)),
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
        is_admin_user=lambda username: username == 'neil',
    )

    assert response['success'] is True
    assert response['data']['is_spectator'] is True
    assert lobbies['lobby_1']['players'] == ['alice']
    assert lobbies['lobby_1']['teams'] == {'team1': ['alice'], 'team2': []}
    assert 'lobby_1' in joined_rooms
    assert activity['neil']['status'] == 'spectating_lobby'
    assert activity['neil']['spectating_lobby_id'] == 'lobby_1'
    assert synced == []


def test_non_admin_cannot_spectate_lobby():
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'captains': {'team1': None, 'team2': None},
            'step': 3,
            'max_players': 2,
            'map_pool': [],
        }
    }

    response = handle_join_lobby_event(
        {'lobby_id': 'lobby_1', 'username': 'bob', 'spectate': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        matchmaking_queue={'skirmish': [], 'hotdrop': []},
        queue_lock=None,
        MAX_LOBBY_PLAYERS=2,
        get_user_group=lambda username: None,
        groups={},
        user_to_group={},
        save_queue=lambda: None,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: None,
        join_room=lambda room: None,
        upsert_player_activity=lambda *args, **kwargs: None,
        get_user_room=lambda username: f'user:{username}',
        get_player_groups=lambda players: {},
        emit=lambda *args, **kwargs: None,
        emit_active_lobby_sync=lambda username, lobby_id: None,
        assign_teams=lambda players: {'team1': players, 'team2': []},
        select_captains=lambda teams: {'team1': None, 'team2': None},
        is_admin_user=lambda username: False,
    )

    assert response == {
        'success': False,
        'message': 'Admin access required',
    }
    assert lobbies['lobby_1']['players'] == ['alice']


def test_admin_can_mark_lobby_live_ready_in_join_server_phase():
    emitted = []
    recorded = []
    saved = []
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'teams': {'team1': ['alice'], 'team2': []},
            'captains': {'team1': None, 'team2': None},
            'step': 3,
            'max_players': 2,
            'map_pool': [],
            'live_roll_countdown': 120,
        }
    }

    class Socket:
        def emit(self, *args, **kwargs):
            emitted.append((args, kwargs))

    response = handle_force_live_ready_event(
        {'lobby_id': 'lobby_1'},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=Socket(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: username == 'neil',
        record_lobby_event=lambda *args, **kwargs: recorded.append((args, kwargs)),
        save_runtime_state=lambda: saved.append(True),
    )

    assert response['success'] is True
    assert lobbies['lobby_1']['live_roll_admin_ready_override'] is True
    assert lobbies['lobby_1']['live_roll_countdown'] == 0
    assert recorded[0][0][1] == 'admin_live_ready_override'
    assert saved == [True]
    assert emitted[0][0][0] == 'lobby_update'


def test_admin_can_force_lobby_ready_then_mark_live_ready():
    emitted = []
    recorded = []
    started = []
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': None, 'team2': None},
            'step': 2,
            'max_players': 2,
            'map_pool': ['Map A'],
            'map_votes': {},
        }
    }

    class Socket:
        def emit(self, *args, **kwargs):
            emitted.append((args, kwargs))

    response = handle_force_live_ready_event(
        {'lobby_id': 'lobby_1', 'force_lobby_ready': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=Socket(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: username == 'neil',
        select_map_from_votes_fn=lambda lobby: ('Map A', {}),
        start_live_roll_monitor=lambda lobby_id: started.append(lobby_id),
        get_server_connection_details=lambda server_id=None: {'password': 'pw'},
        get_selected_map_team_labels=lambda selected_map, server_id=None: {'team1': 'A', 'team2': 'B'},
        ready_grace_seconds=120,
        record_lobby_event=lambda *args, **kwargs: recorded.append((args, kwargs)),
        save_runtime_state=lambda: None,
    )

    assert response['success'] is True
    assert lobbies['lobby_1']['step'] == 3
    assert lobbies['lobby_1']['selected_map'] == 'Map A'
    assert lobbies['lobby_1']['live_roll_admin_ready_override'] is True
    assert lobbies['lobby_1']['live_roll_countdown'] == 0
    assert started == ['lobby_1']
    assert [event[0][1] for event in recorded] == [
        'admin_forced_lobby_ready',
        'admin_live_ready_override',
    ]
    assert [event[0][0] for event in emitted] == ['lobby_update', 'lobby_update']


def test_admin_force_lobby_ready_survives_server_detail_failure():
    emitted = []
    started = []
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': None, 'team2': None},
            'step': 2,
            'max_players': 2,
            'map_pool': ['Map A'],
            'map_votes': {},
        }
    }

    class Socket:
        def emit(self, *args, **kwargs):
            emitted.append((args, kwargs))

    response = handle_force_live_ready_event(
        {'lobby_id': 'lobby_1', 'force_lobby_ready': True},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=Socket(),
        get_username_by_sid=lambda sid: 'neil',
        is_admin_user=lambda username: username == 'neil',
        select_map_from_votes_fn=lambda lobby: ('Map A', {}),
        start_live_roll_monitor=lambda lobby_id: started.append(lobby_id),
        get_server_connection_details=lambda server_id=None: (_ for _ in ()).throw(RuntimeError('bridge down')),
        get_selected_map_team_labels=lambda selected_map, server_id=None: {'team1': 'A', 'team2': 'B'},
        ready_grace_seconds=120,
        record_lobby_event=lambda *args, **kwargs: None,
        save_runtime_state=lambda: None,
    )

    assert response['success'] is True
    assert lobbies['lobby_1']['step'] == 3
    assert lobbies['lobby_1']['live_roll_admin_ready_override'] is True
    assert lobbies['lobby_1']['server_details']['bridgeAvailable'] is False
    assert lobbies['lobby_1']['server_details']['bridgeError'] == 'bridge down'
    assert response['data']['step'] == 3
    assert response['data']['admin_live_ready_override'] is True
    assert started == ['lobby_1']


def test_non_player_cannot_vote_in_lobby():
    lobbies = {
        'lobby_1': {
            'players': ['alice'],
            'map_votes': {},
        }
    }

    response = vote_map_event(
        {'lobby_id': 'lobby_1', 'map': 'Narva Skirmish v1'},
        request=DummyRequest(),
        logger=DummyLogger(),
        lobbies=lobbies,
        socketio=None,
        get_username_by_sid=lambda sid: 'neil',
    )

    assert response == {
        'success': False,
        'message': 'Only lobby players can vote',
    }
    assert lobbies['lobby_1']['map_votes'] == {}
