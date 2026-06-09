from services.queue import (
    add_to_queue,
    build_queue_payload,
    check_queue_and_start_countdown,
    find_user_queue_mode,
)


QUEUE_MODES = {
    'skirmish': {
        'label': '20v20 Skirmish',
        'short_label': 'Skirmish',
        'team_size': 20,
        'max_players': 40,
    },
    'hotdrop': {
        'label': '30v30 Hotdrop',
        'short_label': 'Hotdrop',
        'team_size': 30,
        'max_players': 60,
    }
}


def test_find_user_queue_mode_returns_matching_mode():
    matchmaking_queue = {
        'skirmish': ['alice'],
        'hotdrop': ['bob'],
    }

    assert find_user_queue_mode(matchmaking_queue, 'alice') == 'skirmish'
    assert find_user_queue_mode(matchmaking_queue, 'bob') == 'hotdrop'
    assert find_user_queue_mode(matchmaking_queue, 'carol') is None


def test_build_queue_payload_includes_both_queue_modes():
    matchmaking_queue = {
        'skirmish': ['alice'],
        'hotdrop': ['bob', 'carol'],
    }

    payload = build_queue_payload(
        matchmaking_queue,
        user_has_steam_id=lambda username: username == 'alice',
        get_match_accept_payload=lambda username: None,
        queue_modes=QUEUE_MODES,
        lobbies={},
        pending_match={'skirmish': None, 'hotdrop': None},
        server_capacity=1,
        username='alice'
    )

    assert payload['success'] is True
    assert payload['inQueue'] is True
    assert payload['queueMode'] == 'skirmish'
    assert payload['playersInQueue'] == 1
    assert payload['maxPlayers'] == 40
    assert payload['totalPlayersInQueue'] == 3
    assert payload['hasSteamId'] is True
    assert payload['serverAvailable'] is True
    assert payload['serverCapacity'] == 1
    assert payload['queueModes']['skirmish']['playersInQueue'] == 1
    assert payload['queueModes']['hotdrop']['playersInQueue'] == 2
    assert payload['queueModes']['hotdrop']['maxPlayers'] == 60


def test_add_to_queue_appends_user_to_selected_mode():
    matchmaking_queue = {
        'skirmish': [],
        'hotdrop': [],
    }
    statuses = {}
    saved = {'called': 0}

    def upsert_player_activity(username, **kwargs):
        statuses[username] = kwargs.get('status')

    def save_queue():
        saved['called'] += 1

    added = add_to_queue(
        'neil',
        matchmaking_queue,
        'hotdrop',
        upsert_player_activity,
        save_queue
    )

    assert added is True
    assert matchmaking_queue['hotdrop'] == ['neil']
    assert statuses['neil'] == 'queued'
    assert saved['called'] == 1


def test_check_queue_starts_countdown_for_full_modes_only_when_server_free():
    matchmaking_queue = {
        'skirmish': ['p1', 'p2', 'p3', 'p4'],
        'hotdrop': ['h1', 'h2'],
    }
    queue_modes = {
        'skirmish': {**QUEUE_MODES['skirmish'], 'max_players': 4},
        'hotdrop': {**QUEUE_MODES['hotdrop'], 'max_players': 3},
    }
    pending_match = {
        'skirmish': None,
        'hotdrop': None,
    }
    started = []

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    check_queue_and_start_countdown(
        queue_lock=DummyLock(),
        pending_match=pending_match,
        matchmaking_queue=matchmaking_queue,
        queue_modes=queue_modes,
        lobbies={},
        server_capacity=1,
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players))
    )

    assert started == [('skirmish', ['p1', 'p2', 'p3', 'p4'])]


def test_check_queue_does_not_start_countdown_when_server_is_busy():
    matchmaking_queue = {
        'skirmish': ['p1', 'p2', 'p3', 'p4'],
        'hotdrop': ['h1', 'h2'],
    }
    queue_modes = {
        'skirmish': {**QUEUE_MODES['skirmish'], 'max_players': 4},
        'hotdrop': {**QUEUE_MODES['hotdrop'], 'max_players': 3},
    }
    pending_match = {
        'skirmish': None,
        'hotdrop': {'id': 'existing'},
    }
    started = []

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    check_queue_and_start_countdown(
        queue_lock=DummyLock(),
        pending_match=pending_match,
        matchmaking_queue=matchmaking_queue,
        queue_modes=queue_modes,
        lobbies={},
        server_capacity=1,
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players))
    )

    assert started == []


def test_check_queue_does_not_start_countdown_when_server_pool_has_no_capacity():
    matchmaking_queue = {
        'skirmish': ['p1', 'p2', 'p3', 'p4'],
        'hotdrop': [],
    }
    queue_modes = {
        'skirmish': {**QUEUE_MODES['skirmish'], 'max_players': 4},
        'hotdrop': {**QUEUE_MODES['hotdrop'], 'max_players': 3},
    }
    pending_match = {'skirmish': None, 'hotdrop': None}
    started = []

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    check_queue_and_start_countdown(
        queue_lock=DummyLock(),
        pending_match=pending_match,
        matchmaking_queue=matchmaking_queue,
        queue_modes=queue_modes,
        lobbies={},
        server_capacity=0,
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players))
    )

    assert started == []
