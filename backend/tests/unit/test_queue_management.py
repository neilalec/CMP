from threading import RLock
from types import SimpleNamespace

from services.queue import (
    add_to_queue,
    build_queue_payload,
    check_queue_and_start_countdown,
    find_user_queue_mode,
    get_server_availability,
    has_available_server_capacity,
)
from matchmaking import team_assignment_matches_queue_format
from sockets.queue import handle_accept_match_event


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
    assert payload['serverAvailabilityReason'] == 'available'
    assert payload['serverCapacity'] == 1
    assert payload['queueModes']['skirmish']['playersInQueue'] == 1
    assert payload['queueModes']['hotdrop']['playersInQueue'] == 2
    assert payload['queueModes']['hotdrop']['maxPlayers'] == 60


def test_build_queue_payload_marks_disabled_modes():
    payload = build_queue_payload(
        {'skirmish': [], 'hotdrop': []},
        user_has_steam_id=lambda username: True,
        get_match_accept_payload=lambda username: None,
        queue_modes=QUEUE_MODES,
        disabled_queue_modes={'hotdrop'},
        lobbies={},
        pending_match={'skirmish': None, 'hotdrop': None},
        server_capacity=1,
        username='alice'
    )

    assert payload['queueModes']['skirmish']['enabled'] is True
    assert payload['queueModes']['skirmish']['disabled'] is False
    assert payload['queueModes']['hotdrop']['enabled'] is False
    assert payload['queueModes']['hotdrop']['disabled'] is True


def test_accept_match_schedules_background_finalize_after_all_accept():
    pending_match = {
        'skirmish': {
            'id': 'match_1',
            'queue_mode': 'skirmish',
            'players': ['alice', 'bob'],
            'accepted': {'alice': True, 'bob': False},
            'countdown': 30,
        }
    }
    broadcasts = []
    spawned = []
    finalized = []

    response = handle_accept_match_event(
        {'username': 'bob'},
        request=SimpleNamespace(sid='sid_bob'),
        logger=SimpleNamespace(
            info=lambda *_args, **_kwargs: None,
            warning=lambda *_args, **_kwargs: None,
            error=lambda *_args, **_kwargs: None,
        ),
        queue_lock=RLock(),
        pending_match=pending_match,
        get_username_by_sid=lambda sid: 'bob',
        get_match_accept_payload=lambda username: {
            'active': True,
            'queueMode': 'skirmish',
            'players': ['alice', 'bob'],
            'acceptedPlayers': ['alice', 'bob'],
            'acceptedCount': 2,
            'requiredCount': 2,
            'countdown': 30,
        },
        broadcast_queue_update=lambda: broadcasts.append(True),
        finalize_pending_match=lambda match_id: finalized.append(match_id),
        spawn_finalize_pending_match=lambda match_id: spawned.append(match_id),
    )

    assert response['success'] is True
    assert response['allAccepted'] is True
    assert response['finalizingLobby'] is True
    assert response['lobbyId'] is None
    assert spawned == ['match_1']
    assert finalized == []
    assert broadcasts == [True]


def test_team_assignment_must_fill_both_format_sides():
    queue_config = {'team_size': 1, 'max_players': 2}

    assert team_assignment_matches_queue_format(
        {'team1': ['alice'], 'team2': ['bob']},
        queue_config
    ) is True
    assert team_assignment_matches_queue_format(
        {'team1': ['alice', 'bob'], 'team2': []},
        queue_config
    ) is False


def test_finalized_released_lobby_does_not_consume_server_capacity():
    lobbies = {
        'finished': {
            'step': 5,
            'server_released_at': 1234,
        }
    }

    assert has_available_server_capacity(
        lobbies,
        pending_match={'skirmish': None},
        server_capacity=1
    ) is True


def test_server_availability_reports_server_in_use_reason():
    availability = get_server_availability(
        {
            'active': {
                'step': 4,
                'server_id': 1,
            }
        },
        pending_match={'skirmish': None},
        server_capacity=1
    )

    assert availability['available'] is False
    assert availability['reason'] == 'server_in_use'
    assert availability['activeLobbyCount'] == 1


def test_server_availability_reports_pending_match_reason():
    availability = get_server_availability(
        {},
        pending_match={'skirmish': {'id': 'match_1'}},
        server_capacity=1
    )

    assert availability['available'] is False
    assert availability['reason'] == 'match_acceptance_active'
    assert availability['activePendingMatchCount'] == 1


def test_server_availability_reports_no_servers_reason():
    availability = get_server_availability(
        {},
        pending_match={'skirmish': None},
        server_capacity=0
    )

    assert availability['available'] is False
    assert availability['reason'] == 'no_servers'


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


def test_check_queue_ignores_disabled_full_queue():
    started = []

    class DummyLock:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    check_queue_and_start_countdown(
        queue_lock=DummyLock(),
        pending_match={'skirmish': None},
        matchmaking_queue={'skirmish': ['p1', 'p2']},
        queue_modes={'skirmish': {**QUEUE_MODES['skirmish'], 'max_players': 2}},
        lobbies={},
        server_capacity=1,
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players)),
        disabled_queue_modes={'skirmish'}
    )

    assert started == []
