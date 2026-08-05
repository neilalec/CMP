from runtime import cleanup_stale_disconnected_players


class DummyLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class DummySocketIO:
    def __init__(self):
        self.emits = []

    def emit(self, event, payload, room=None):
        self.emits.append((event, payload, room))


def build_profiles(players):
    return {
        player: {
            'display_name': player,
            'steam_id': ''
        }
        for player in players
    }


def select_captains(teams):
    return {
        'team1': next(iter(teams.get('team1') or []), None),
        'team2': next(iter(teams.get('team2') or []), None)
    }


def test_stale_disconnected_player_reopens_pre_live_lobby_slot():
    socketio = DummySocketIO()
    events = []
    synced = []
    counters = {'queue': 0, 'lobbies': 0, 'saves': 0}
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': 'alice', 'team2': 'bob'},
            'disconnected_players': {'bob'},
            'player_groups': {'alice': 'AAA111', 'bob': 'BBB222'},
            'step': 3,
            'max_players': 4,
            'map_pool': [],
        }
    }
    activity = {
        'bob': {
            'status': 'disconnected',
            'last_seen': 0,
            'lobby_id': 'lobby_1',
        }
    }

    result = cleanup_stale_disconnected_players(
        current_time=601,
        queue_lock=DummyLock(),
        player_activity=activity,
        matchmaking_queue={'skirmish': []},
        lobbies=lobbies,
        broadcast_queue_update=lambda: counters.__setitem__('queue', counters['queue'] + 1),
        broadcast_open_lobbies_update=lambda: counters.__setitem__('lobbies', counters['lobbies'] + 1),
        socketio=socketio,
        build_player_profile_map=build_profiles,
        select_captains=select_captains,
        emit_active_lobby_sync=lambda username, lobby_id: synced.append((username, lobby_id)),
        record_lobby_event=lambda lobby_id, event_type, payload, created_at=None: events.append((event_type, payload)),
        save_runtime_state=lambda: counters.__setitem__('saves', counters['saves'] + 1),
        lobby_disconnect_grace_seconds=600,
        web_lobby_disconnect_tracking_enabled=True,
    )

    assert result['lobbiesChanged'] is True
    assert lobbies['lobby_1']['players'] == ['alice']
    assert lobbies['lobby_1']['teams'] == {'team1': ['alice'], 'team2': []}
    assert lobbies['lobby_1']['captains'] == {'team1': 'alice', 'team2': None}
    assert lobbies['lobby_1']['disconnected_players'] == set()
    assert lobbies['lobby_1']['player_groups'] == {'alice': 'AAA111'}
    assert 'bob' not in activity
    assert synced == [('bob', None)]
    assert counters['lobbies'] == 1
    assert counters['saves'] == 1
    assert events[0][0] == 'player_removed_after_disconnect_timeout'
    assert any(event == 'lobby_update' for event, _, _ in socketio.emits)


def test_stale_disconnected_player_does_not_reopen_live_lobby_slot():
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': 'alice', 'team2': 'bob'},
            'disconnected_players': {'bob'},
            'step': 4,
        }
    }
    activity = {
        'bob': {
            'status': 'disconnected',
            'last_seen': 0,
            'lobby_id': 'lobby_1',
        }
    }

    result = cleanup_stale_disconnected_players(
        current_time=601,
        queue_lock=DummyLock(),
        player_activity=activity,
        matchmaking_queue={'skirmish': []},
        lobbies=lobbies,
        broadcast_queue_update=lambda: None,
        lobby_disconnect_grace_seconds=600,
        web_lobby_disconnect_tracking_enabled=True,
    )

    assert result['lobbiesChanged'] is False
    assert lobbies['lobby_1']['players'] == ['alice', 'bob']
    assert lobbies['lobby_1']['teams'] == {'team1': ['alice'], 'team2': ['bob']}
    assert 'bob' not in activity


def test_empty_abandoned_lobby_is_closed_and_allocation_released():
    released = []
    events = []
    counters = {'lobbies': 0}
    lobbies = {
        'lobby_1': {
            'players': ['bob'],
            'teams': {'team1': ['bob'], 'team2': []},
            'captains': {'team1': 'bob', 'team2': None},
            'disconnected_players': {'bob'},
            'step': 2,
        }
    }
    activity = {
        'bob': {
            'status': 'disconnected',
            'last_seen': 0,
            'lobby_id': 'lobby_1',
        }
    }

    result = cleanup_stale_disconnected_players(
        current_time=601,
        queue_lock=DummyLock(),
        player_activity=activity,
        matchmaking_queue={'skirmish': []},
        lobbies=lobbies,
        broadcast_queue_update=lambda: None,
        broadcast_open_lobbies_update=lambda: counters.__setitem__('lobbies', counters['lobbies'] + 1),
        select_captains=select_captains,
        record_lobby_event=lambda lobby_id, event_type, payload, created_at=None: events.append((event_type, payload)),
        release_server_allocation=lambda lobby_id, reason=None: released.append((lobby_id, reason)),
        lobby_disconnect_grace_seconds=600,
        web_lobby_disconnect_tracking_enabled=True,
    )

    assert result['lobbiesChanged'] is True
    assert lobbies == {}
    assert 'bob' not in activity
    assert released == [('lobby_1', 'disconnect_timeout')]
    assert counters['lobbies'] == 1
    assert [event_type for event_type, _ in events] == [
        'player_removed_after_disconnect_timeout',
        'lobby_closed',
    ]


def test_web_disconnect_cleanup_is_disabled_by_default_for_pre_live_lobbies():
    lobbies = {
        'lobby_1': {
            'players': ['alice', 'bob'],
            'teams': {'team1': ['alice'], 'team2': ['bob']},
            'captains': {'team1': 'alice', 'team2': 'bob'},
            'disconnected_players': {'bob'},
            'step': 3,
        }
    }
    activity = {
        'bob': {
            'status': 'disconnected',
            'last_seen': 0,
            'lobby_id': 'lobby_1',
        }
    }

    result = cleanup_stale_disconnected_players(
        current_time=601,
        queue_lock=DummyLock(),
        player_activity=activity,
        matchmaking_queue={'skirmish': []},
        lobbies=lobbies,
        broadcast_queue_update=lambda: None,
        lobby_disconnect_grace_seconds=600,
    )

    assert result['lobbiesChanged'] is False
    assert lobbies['lobby_1']['players'] == ['alice', 'bob']
    assert activity['bob']['status'] == 'disconnected'
