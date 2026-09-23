from threading import RLock
from types import SimpleNamespace

import app_core
import matchmaking
from app_state import DEFAULT_QUEUE_MODE, QUEUE_MODES
from services.queue import (
    build_queue_payload,
    check_queue_and_start_countdown,
    get_server_availability,
    has_available_server_capacity,
    resolve_queue_game_type,
    start_match_acceptance,
)
from sockets.queue import handle_join_queue_event


TEST_MODES = {
    'skirmish': {'id': 'skirmish', 'label': 'Squad', 'short_label': 'SQ', 'max_players': 2, 'team_size': 1},
    'wardogs_test': {'id': 'wardogs_test', 'game_type': 'wardogs', 'label': 'WARDOGS',
                     'short_label': 'WD', 'max_players': 3, 'team_size': 1},
}


def test_squad_mode_ids_resolve_without_renaming():
    assert DEFAULT_QUEUE_MODE == 'skirmish'
    assert all(resolve_queue_game_type(QUEUE_MODES, mode_id) == 'squad' for mode_id in QUEUE_MODES)
    assert resolve_queue_game_type(TEST_MODES, 'skirmish') == 'squad'
    assert resolve_queue_game_type(TEST_MODES, 'wardogs_test') == 'wardogs'
    assert resolve_queue_game_type(TEST_MODES, 'wardogs_test', 'squad') is None
    assert resolve_queue_game_type(TEST_MODES, 'missing') is None
    assert resolve_queue_game_type({'bad': {'id': 'bad', 'game_type': 'other'}}, 'bad') is None
    assert resolve_queue_game_type({'bad': {'id': 'another'}}, 'bad') is None


def test_capacity_and_disabled_modes_are_isolated_by_game():
    pending = {'skirmish': None, 'wardogs_test': {'id': 'wd1', 'queue_mode': 'wardogs_test', 'game_type': 'wardogs'}}
    assert has_available_server_capacity({}, pending, {'squad': 1, 'wardogs': 0},
                                         game_type='squad', queue_modes=TEST_MODES)
    assert not has_available_server_capacity({}, pending, 1, game_type='wardogs', queue_modes=TEST_MODES)
    assert get_server_availability({}, pending, {'squad': 1, 'wardogs': 0},
                                   game_type='wardogs', queue_modes=TEST_MODES)['capacity'] == 0
    payload = build_queue_payload(
        {'skirmish': [], 'wardogs_test': []}, lambda _user: True, lambda _user: None,
        TEST_MODES, disabled_queue_modes={'skirmish'}, pending_match=pending,
        server_capacity={'squad': 1, 'wardogs': 0}, queue_mode='wardogs_test'
    )
    assert payload['gameType'] == 'wardogs'
    assert payload['serverAvailable'] is False
    assert payload['queueModes']['wardogs_test']['enabled'] is True
    assert payload['queueModes']['skirmish']['enabled'] is False


def test_full_wardogs_test_mode_cannot_start_acceptance_with_squad_capacity():
    started = []
    check_queue_and_start_countdown(
        queue_lock=RLock(), pending_match={'skirmish': None, 'wardogs_test': None},
        matchmaking_queue={'skirmish': ['a', 'b'], 'wardogs_test': ['x', 'y', 'z']},
        queue_modes=TEST_MODES, lobbies={}, server_capacity={'squad': 1, 'wardogs': 0},
        start_match_acceptance=lambda players, queue_mode: started.append((queue_mode, players)),
    )
    assert started == [('skirmish', ['a', 'b'])]


def _join(mode, game_type=None):
    responses = []
    queue = {'skirmish': [], 'wardogs_test': []}
    handle_join_queue_event(
        {'username': 'alice', 'queueMode': mode, 'gameType': game_type},
        socket_events={'QUEUE': {'JOIN': 'join_queue'}}, emit=lambda _event, payload: responses.append(payload),
        socketio=SimpleNamespace(), broadcast_queue_update=lambda: None,
        request=SimpleNamespace(sid='sid'), logger=SimpleNamespace(error=lambda *_args: None),
        group_lock=RLock(), get_user_group=lambda _user: None, user_has_steam_id=lambda _user: True,
        build_queue_payload=lambda **_kwargs: {'success': True}, queue_lock=RLock(),
        matchmaking_queue=queue, queue_modes=TEST_MODES, disabled_queue_modes=set(),
        pending_match={}, lobbies={}, upsert_player_activity=lambda *_args, **_kwargs: None,
        save_queue=lambda: None, check_queue_and_start_countdown=lambda: None,
        has_available_server_capacity=has_available_server_capacity,
    )
    return responses[-1], queue


def test_squad_join_succeeds_and_wardogs_or_mismatched_game_does_not():
    response, queue = _join('skirmish')
    assert response['success'] is True
    assert queue['skirmish'] == ['alice']
    response, queue = _join('wardogs_test')
    assert response['success'] is False
    assert queue['wardogs_test'] == []
    response, queue = _join('skirmish', 'wardogs')
    assert response['success'] is False
    assert queue['skirmish'] == []
    response, queue = _join('missing')
    assert response['success'] is False
    assert 'missing' not in queue


def test_valid_queue_restores_and_unknown_modes_never_become_skirmish():
    with app_core.get_db_connection() as conn:
        conn.executemany('INSERT INTO queue_entries (mode, position, username) VALUES (?, ?, ?)', [
            ('skirmish', 0, 'alice'), ('removed_mode', 0, 'bob'), ('wardogs_test', 0, 'carol'),
        ])
        conn.commit()
    restored = app_core.load_queue()
    assert restored['skirmish'] == ['alice']
    assert 'bob' not in restored['skirmish']
    assert 'carol' not in restored['skirmish']
    assert 'removed_mode' not in restored


def test_restart_keeps_valid_queue_and_discards_pending_acceptance(monkeypatch):
    with app_core.get_db_connection() as conn:
        conn.execute('INSERT INTO queue_entries (mode, position, username) VALUES (?, ?, ?)',
                     ('skirmish', 0, 'alice'))
        conn.commit()
    queue = {}
    pending = {'skirmish': {'id': 'old', 'queue_mode': 'skirmish', 'accepted': {'alice': True}}}
    monkeypatch.setattr(app_core, 'matchmaking_queue', queue)
    monkeypatch.setattr(app_core, 'pending_match', pending)
    app_core.initialize_state()
    assert queue['skirmish'] == ['alice']
    assert all(match is None for match in pending.values())


def test_shared_acceptance_records_game_without_team_fields(monkeypatch):
    monkeypatch.setattr('services.queue.eventlet.spawn', lambda _target: None)
    stored = []
    success, pending = start_match_acceptance(
        players=['alice', 'bob'], queue_mode='skirmish', game_type='squad', max_lobby_players=2,
        match_accept_countdown=30, pending_match=None, set_pending_match=stored.append,
        broadcast_queue_update=lambda: None, pause_aware_sleep=lambda _seconds: None,
        finalize_pending_match=lambda _match_id: None, cancel_pending_match=lambda *_args, **_kwargs: None,
    )
    assert success is True
    assert pending is stored[0]
    assert pending['queue_mode'] == 'skirmish'
    assert pending['game_type'] == 'squad'
    assert pending['accepted'] == {'alice': False, 'bob': False}
    assert 'teams' not in pending


def test_shared_acceptance_timeout_cancels_without_a_lobby(monkeypatch):
    countdown_tasks = []
    cancelled = []
    monkeypatch.setattr('services.queue.eventlet.spawn', countdown_tasks.append)
    success, pending = start_match_acceptance(
        players=['alice', 'bob'], queue_mode='wardogs_test', game_type='wardogs', max_lobby_players=2,
        match_accept_countdown=1, pending_match=None, set_pending_match=lambda _state: None,
        broadcast_queue_update=lambda: None, pause_aware_sleep=lambda _seconds: None,
        finalize_pending_match=lambda _match_id: None,
        cancel_pending_match=lambda reason, remove_players: cancelled.append((reason, remove_players)),
    )
    assert success is True
    assert pending['game_type'] == 'wardogs'
    countdown_tasks[0]()
    assert cancelled == [('Match acceptance timed out.', ['alice', 'bob'])]


def test_finalization_dispatches_squad_and_rejects_wardogs(monkeypatch):
    called = []
    pending = {'id': 'match_1', 'queue_mode': 'skirmish', 'game_type': 'squad',
               'players': ['alice'], 'accepted': {'alice': True}}
    fake_app = SimpleNamespace(
        pending_match={'skirmish': pending},
        logger=SimpleNamespace(info=lambda *_args: None, warning=lambda *_args: None),
    )
    monkeypatch.setattr(matchmaking, '_app', lambda: fake_app)
    monkeypatch.setattr(matchmaking, 'broadcast_queue_update', lambda: None)
    monkeypatch.setattr(matchmaking, 'create_lobby',
                        lambda players, queue_mode: called.append((players, queue_mode)) or 'lobby_1')
    assert matchmaking.finalize_pending_match('match_1') == 'lobby_1'
    assert called == [(['alice'], 'skirmish')]
    monkeypatch.setattr(matchmaking, 'QUEUE_MODES', {**TEST_MODES})
    fake_app.pending_match['wardogs_test'] = {
        **pending, 'id': 'match_2', 'queue_mode': 'wardogs_test', 'game_type': 'wardogs'
    }
    assert matchmaking.finalize_pending_match('match_2') is False
    assert called == [(['alice'], 'skirmish')]
    fake_app.pending_match['wardogs_test']['game_type'] = 'squad'
    assert matchmaking.finalize_pending_match('match_2') is False
    assert called == [(['alice'], 'skirmish')]
    fake_app.pending_match['wardogs_test']['queue_mode'] = 'skirmish'
    assert matchmaking.finalize_pending_match('match_2') is False
    assert called == [(['alice'], 'skirmish')]


def test_existing_squad_capacity_wrapper_ignores_wardogs_registration(monkeypatch):
    calls = []
    monkeypatch.setattr(app_core, 'get_server_pool_capacity_service',
                        lambda _db, _secret, game_type='squad': calls.append(game_type) or 1)
    assert app_core.get_server_pool_capacity() == 1
    assert calls == ['squad']
