from sockets.lobby import handle_join_lobby_event
from state.lobby import find_active_lobby_for_user, is_user_in_any_lobby
import app as backend_app


class DummyLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(('info', message))

    def warning(self, message):
        self.messages.append(('warning', message))

    def error(self, message):
        self.messages.append(('error', message))


class DummyRequest:
    sid = 'sid-1'


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
