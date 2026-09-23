from datetime import datetime, timezone
from types import SimpleNamespace

import app_core
import matchmaking

from app_state import QUEUE_MODES
from threading import RLock
from services.wardogs_assignment import WardogsAssignmentConfig, WardogsAssignmentResult
from services.wardogs_finalization import finalize_wardogs_accepted_match
from services.wardogs_lobby import get_wardogs_lobby, latest_wardogs_lobby_for_user


MODES = {'wardogs-internal': {'id': 'wardogs-internal', 'game_type': 'wardogs'}}
AT = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def _pending(players, accepted=None, match_id='match-final'):
    return {
        'id': match_id, 'game_type': 'wardogs', 'queue_mode': 'wardogs-internal',
        'players': list(players),
        'accepted': accepted if accepted is not None else {player: True for player in players},
    }


def _finalize(pending, *, groups=None, user_to_group=None, profiles=None, config=None):
    return finalize_wardogs_accepted_match(
        pending, queue_modes=MODES, groups=groups or {},
        user_to_group=user_to_group or {}, profiles=profiles or {},
        config=config or WardogsAssignmentConfig(2, 1),
        get_db_connection=app_core.get_db_connection, created_at=AT,
    )


def _roster(lobby):
    return [player for faction in lobby['factions'] for group in faction['groups']
            for player in group['players']]


def _groups(lobby):
    return [group for faction in lobby['factions'] for group in faction['groups']]


def test_accepted_solos_create_three_faction_lobby_with_planned_state():
    result = _finalize(_pending(['alice', 'bob', 'carol']),
                       profiles={'alice': {'display_name': 'Alice A', 'steam_id': '76561198000000001'}})
    assert result.success and result.status == 'complete'
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    assert [faction['id'] for faction in lobby['factions']] == ['valkyra', 'lonestar', 'manticore']
    assert [len(faction['groups']) for faction in lobby['factions']] == [1, 1, 1]
    assert sorted(player['id'] for player in _roster(lobby)) == ['alice', 'bob', 'carol']
    assert all(player['ready'] is False and player['rosterStatus'] == 'active' for player in _roster(lobby))
    assert all('connected' not in player and 'alignmentState' not in player for player in _roster(lobby))
    assert lobby['serverId'] is None
    assert result.read_model['observation']['state'] == 'none'
    assert latest_wardogs_lobby_for_user(app_core.get_db_connection, 'alice') == result.lobby_id
    assert latest_wardogs_lobby_for_user(app_core.get_db_connection, 'outsider') is None
    assert all(player['connected'] is None and player['alignmentState'] == 'unknown'
               for faction in result.read_model['factions'] for group in faction['groups']
               for player in group['players'])
    assert next(player for player in _roster(lobby) if player['id'] == 'alice')['displayName'] == 'Alice A'


def test_beta_nine_accepted_players_form_complete_serverless_lobby():
    players = [f'player-{number}' for number in range(9)]
    result = finalize_wardogs_accepted_match(
        {**_pending(players), 'queue_mode': 'wardogs_beta9'},
        queue_modes=QUEUE_MODES, groups={}, user_to_group={}, profiles={},
        config=WardogsAssignmentConfig(3, 0),
        get_db_connection=app_core.get_db_connection, created_at=AT,
    )
    assert result.success
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    assert sorted(player['id'] for player in _roster(lobby)) == players
    assert [sum(len(group['players']) for group in faction['groups']) for faction in lobby['factions']] == [3, 3, 3]
    assert lobby['serverId'] is None
    assert latest_wardogs_lobby_for_user(app_core.get_db_connection, players[0]) == result.lobby_id


def test_accepted_premade_and_solo_preserve_group_leader_and_exclude_unaccepted_member():
    groups = {'ABC': {'code': 'ABC', 'leader': 'alice', 'members': ['alice', 'bob', 'outsider']}}
    user_map = {'alice': 'ABC', 'bob': 'ABC', 'outsider': 'ABC'}
    result = _finalize(_pending(['alice', 'bob', 'carol']), groups=groups, user_to_group=user_map)
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    premade = next(group for group in _groups(lobby) if group['type'] == 'premade')
    assert {player['id'] for player in premade['players']} == {'alice', 'bob'}
    assert premade['leaderId'] == 'alice'
    assert sorted(player['id'] for player in _roster(lobby)) == ['alice', 'bob', 'carol']
    assert 'outsider' not in [player['id'] for player in _roster(lobby)]
    assert len([group for group in _groups(lobby) if group['type'] == 'solo']) == 1


def test_premade_can_be_wholly_reserve_and_solo_active():
    groups = {'ABC': {'code': 'ABC', 'leader': 'alice', 'members': ['alice', 'bob', 'carol']}}
    user_map = {player: 'ABC' for player in ('alice', 'bob', 'carol')}
    result = _finalize(_pending(['alice', 'bob', 'carol', 'solo']), groups=groups,
                       user_to_group=user_map, config=WardogsAssignmentConfig(1, 3))
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    premade = next(group for group in _groups(lobby) if group['type'] == 'premade')
    assert {player['rosterStatus'] for player in premade['players']} == {'reserve'}
    assert next(player for player in _roster(lobby) if player['id'] == 'solo')['rosterStatus'] == 'active'
    assert len(_roster(lobby)) == 4


def test_party_mutation_after_snapshot_cannot_change_finalized_group(monkeypatch):
    import services.wardogs_finalization as service
    groups = {'ABC': {'code': 'ABC', 'leader': 'alice', 'members': ['alice', 'bob']}}
    user_map = {'alice': 'ABC', 'bob': 'ABC'}
    original_assign = service.assign_wardogs_factions

    def mutate_after_snapshot(snapshot, config):
        groups['ABC']['members'].clear()
        groups['ABC']['leader'] = 'someone-else'
        user_map.clear()
        return original_assign(snapshot, config)

    monkeypatch.setattr(service, 'assign_wardogs_factions', mutate_after_snapshot)
    result = _finalize(_pending(['alice', 'bob']), groups=groups, user_to_group=user_map)
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    premade = next(group for group in _groups(lobby) if group['type'] == 'premade')
    assert [player['id'] for player in premade['players']] == ['alice', 'bob']
    assert premade['leaderId'] == 'alice'


def test_stale_party_mapping_falls_back_to_solos():
    groups = {'ABC': {'code': 'ABC', 'leader': 'alice', 'members': ['alice', 'bob']}}
    result = _finalize(_pending(['alice', 'bob']), groups=groups, user_to_group={'alice': 'ABC'})
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    assert [group['type'] for group in _groups(lobby)] == ['solo', 'solo']


def test_partial_assignment_preserves_overflow_and_creates_no_lobby():
    groups = {'ABC': {'code': 'ABC', 'leader': 'a', 'members': ['a', 'b', 'c', 'd']}}
    result = _finalize(_pending(['a', 'b', 'c', 'd']), groups=groups,
                       user_to_group={player: 'ABC' for player in ('a', 'b', 'c', 'd')},
                       config=WardogsAssignmentConfig(2, 1))
    assert result.status == 'partial' and not result.success
    assert len(result.unassigned) == 1
    assert {member.username for member in result.unassigned[0].entry.members} == {'a', 'b', 'c', 'd'}
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_invalid_matcher_or_pending_input_creates_no_lobby(monkeypatch):
    import services.wardogs_finalization as service
    monkeypatch.setattr(service, 'assign_wardogs_factions', lambda *_args: WardogsAssignmentResult(
        match_id='match-final', game_type='wardogs', queue_mode='wardogs-internal',
        status='invalid', factions=(), errors=('bad assignment',),
    ))
    result = _finalize(_pending(['alice']))
    assert result.status == 'invalid' and result.errors == ('bad assignment',)
    assert _finalize(_pending(['alice'], accepted={'alice': False})).status == 'invalid'
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_snapshot_failure_creates_no_lobby():
    result = _finalize(_pending(['alice', 'alice']))
    assert result.status == 'invalid' and result.errors
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_provenance_is_persisted_without_server_allocation():
    result = _finalize(_pending(['alice']), config=WardogsAssignmentConfig(3, 2))
    lobby = get_wardogs_lobby(app_core.get_db_connection, result.lobby_id)
    provenance = lobby['provenance']
    assert provenance['pendingMatchId'] == 'match-final'
    assert provenance['queueMode'] == 'wardogs-internal'
    assert provenance['gameType'] == 'wardogs'
    assert provenance['snapshotSource'] == 'accepted_cmp_party_snapshot'
    assert provenance['snapshotCreatedAt'] == AT.timestamp()
    assert provenance['createdAt'] == AT.isoformat()
    assert provenance['assignmentConfiguration'] == {
        'factions': ['valkyra', 'lonestar', 'manticore'],
        'activePerFaction': 3, 'reservePerFaction': 2, 'allowPremadeSplit': False,
    }
    assert lobby['serverId'] is None


def test_persistence_failure_is_controlled_and_leaves_no_lobby(monkeypatch):
    import services.wardogs_finalization as service
    monkeypatch.setattr(service, 'create_wardogs_lobby', lambda *_args: (_ for _ in ()).throw(RuntimeError('disk unavailable')))
    result = _finalize(_pending(['alice']))
    assert result.status == 'persistence_failed' and not result.success
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_database_insert_failure_rolls_back_atomically():
    with app_core.get_db_connection() as conn:
        conn.execute("""CREATE TRIGGER block_wardogs_lobby BEFORE INSERT ON wardogs_lobbies
            BEGIN SELECT RAISE(ABORT, 'blocked'); END""")
        conn.commit()
    result = _finalize(_pending(['alice']))
    assert result.status == 'persistence_failed'
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_exact_retry_reuses_existing_lobby_without_overwriting_and_conflict_fails():
    pending = _pending(['alice', 'bob'])
    first = _finalize(pending)
    with app_core.get_db_connection() as conn:
        original = conn.execute('SELECT roster_json, updated_at FROM wardogs_lobbies WHERE lobby_id=?',
                                (first.lobby_id,)).fetchone()
    retry = _finalize(pending)
    assert retry.success and retry.lobby_id == first.lobby_id
    conflict = _finalize(pending, config=WardogsAssignmentConfig(3, 0))
    assert conflict.status == 'invalid' and not conflict.success
    with app_core.get_db_connection() as conn:
        after = conn.execute('SELECT roster_json, updated_at FROM wardogs_lobbies WHERE lobby_id=?',
                             (first.lobby_id,)).fetchone()
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 1
    assert tuple(original) == tuple(after)


def test_shared_dispatch_uses_wardogs_finalizer_with_internal_config(monkeypatch):
    pending = _pending(['alice', 'bob', 'carol'])
    fake_app = SimpleNamespace(
        pending_match={'wardogs-internal': pending}, groups={}, user_to_group={}, users={},
        queue_lock=RLock(), matchmaking_queue={'wardogs-internal': ['alice', 'bob', 'carol']},
        player_activity={}, socketio=SimpleNamespace(emit=lambda *_a, **_k: None),
        SOCKET_EVENTS={'LOBBY': {'CREATED': 'lobby_created'}, 'QUEUE': {'MATCH_ACCEPT_CANCELLED': 'cancelled'}},
        get_user_room=lambda user: user,
        get_db_connection=app_core.get_db_connection,
        logger=SimpleNamespace(info=lambda *_args: None, warning=lambda *_args: None),
        allocate_server_for_lobby=lambda *_args: (_ for _ in ()).throw(AssertionError('allocation called')),
    )
    monkeypatch.setattr(matchmaking, '_app', lambda: fake_app)
    monkeypatch.setattr(matchmaking, 'broadcast_queue_update', lambda: None)
    monkeypatch.setattr(matchmaking, 'save_queue', lambda: None)
    monkeypatch.setattr(matchmaking, 'create_lobby', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('Squad builder called')))
    lobby_id = matchmaking.finalize_pending_match(
        'match-final', queue_modes=MODES, wardogs_config=WardogsAssignmentConfig(1, 0))
    assert isinstance(lobby_id, str)
    assert fake_app.pending_match['wardogs-internal'] is None
    assert len(_roster(get_wardogs_lobby(app_core.get_db_connection, lobby_id))) == 3


def test_shared_dispatch_keeps_pending_match_after_partial_failure(monkeypatch):
    pending = _pending(['a', 'b', 'c', 'd'])
    fake_app = SimpleNamespace(
        pending_match={'wardogs-internal': pending},
        queue_lock=RLock(), matchmaking_queue={'wardogs-internal': ['a', 'b', 'c', 'd']},
        player_activity={}, socketio=SimpleNamespace(emit=lambda *_a, **_k: None),
        SOCKET_EVENTS={'LOBBY': {'CREATED': 'lobby_created'}, 'QUEUE': {'MATCH_ACCEPT_CANCELLED': 'cancelled'}},
        get_user_room=lambda user: user,
        groups={'ABC': {'code': 'ABC', 'leader': 'a', 'members': ['a', 'b', 'c', 'd']}},
        user_to_group={player: 'ABC' for player in ('a', 'b', 'c', 'd')},
        users={}, get_db_connection=app_core.get_db_connection,
        logger=SimpleNamespace(info=lambda *_args: None, warning=lambda *_args: None),
    )
    monkeypatch.setattr(matchmaking, '_app', lambda: fake_app)
    monkeypatch.setattr(matchmaking, 'broadcast_queue_update', lambda: None)
    monkeypatch.setattr(matchmaking, 'save_queue', lambda: None)
    monkeypatch.setattr(matchmaking, 'create_lobby', lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError('Squad builder called')))
    assert matchmaking.finalize_pending_match(
        'match-final', queue_modes=MODES, wardogs_config=WardogsAssignmentConfig(2, 1)) is False
    assert fake_app.pending_match['wardogs-internal'] is None
    assert fake_app.matchmaking_queue['wardogs-internal'] == ['a', 'b', 'c', 'd']
    assert pending['accepted'] == {player: True for player in ('a', 'b', 'c', 'd')}
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_lobbies').fetchone()[0] == 0


def test_shared_dispatch_rejects_unknown_game_and_production_catalog_has_wardogs(monkeypatch):
    assert QUEUE_MODES['wardogs_beta9']['game_type'] == 'wardogs'
    fake_app = SimpleNamespace(
        pending_match={'unknown': _pending(['alice'])},
        logger=SimpleNamespace(info=lambda *_args: None, warning=lambda *_args: None),
    )
    monkeypatch.setattr(matchmaking, '_app', lambda: fake_app)
    assert matchmaking.finalize_pending_match('match-final', queue_modes={}) is False
