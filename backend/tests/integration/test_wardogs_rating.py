"""Offline WARDOGS rating policy, ledger, and revision replay tests."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import sqlite3

import pytest

import app_core
from flask_jwt_extended import create_access_token
from services.wardogs_lobby import save_wardogs_lobby
from services.wardogs_rating import (
    FACTION_ORDER, VERSION, calculate_match, conserve_deltas, get_player_rating,
    pairwise_actual_scores, replay_current_results, round_half_away,
)
from services.wardogs_results import confirm_wardogs_result, correct_wardogs_result


F = FACTION_ORDER


def _lobby(lobby_id, users=('alice', 'bob', 'carol'), *, reserve=None, unregistered=None):
    return {'id': lobby_id, 'phase': 'assembling', 'serverId': None, 'factions': [
        {'id': faction, 'commanderId': None, 'groups': [
            {'id': f'{faction}-active', 'type': 'solo', 'leaderId': None, 'players': [
                {'id': user, 'registered': user != unregistered, 'rosterStatus': 'active', 'ready': False}]},
            *([{'id': f'{faction}-reserve', 'type': 'solo', 'leaderId': None, 'players': [
                {'id': reserve, 'registered': True, 'rosterStatus': 'reserve', 'ready': False}]}]
              if reserve and faction == F[0] else []),
        ]} for faction, user in zip(F, users, strict=True)]}


def _accounts(*names):
    with app_core.get_db_connection() as conn:
        conn.executemany('INSERT INTO users (username, password) VALUES (?, ?)',
                         [(name, 'test') for name in names])


def _result(order=(F[0], F[1], F[2]), status='completed_win'):
    if status not in {'completed_win', 'tie'}:
        return {'status': status}
    scores = {faction: 3 - index for index, faction in enumerate(order)}
    return {'status': status, 'scores': scores,
            'placementGroups': [[faction] for faction in order]}


def _when(seconds=0):
    return datetime.now(timezone.utc) + timedelta(seconds=10 + seconds)


def _events(generation):
    with app_core.get_db_connection() as conn:
        return [dict(row) for row in conn.execute(
            'SELECT * FROM wardogs_rating_events WHERE generation_id=? ORDER BY match_order, faction_id, player_id',
            (generation,))]


def _generation():
    with app_core.get_db_connection() as conn:
        return conn.execute('SELECT active_generation_id FROM wardogs_rating_state').fetchone()[0]


@pytest.mark.parametrize('ratings,groups,expected', [
    ([1000, 1000, 1000], [[F[0]], [F[1]], [F[2]]], [24, 0, -24]),
    ([1200, 1000, 800], [[F[1]], [F[2]], [F[0]]], [-40, 24, 16]),
    ([1000, 1000, 1000], [[F[0], F[1]], [F[2]]], [12, 12, -24]),
    ([1000, 1000, 1000], [list(F)], [0, 0, 0]),
    ([1200, 1000, 800], [[F[0]], [F[1]], [F[2]]], [8, 0, -8]),
    ([1000, 1000, 1000], [[F[0]], [F[1], F[2]]], [24, -12, -12]),
])
def test_approved_calculation_examples(ratings, groups, expected):
    roster = {faction: [faction] for faction in F}
    result = calculate_match(roster, dict(zip(F, ratings, strict=True)), groups)
    assert [result['factionDeltas'][faction] for faction in F] == expected
    assert sum(result['playerDeltas'].values()) == 0


def test_pairwise_mapping_and_malformed_placements():
    scores = pairwise_actual_scores([[F[0], F[1]], [F[2]]])
    assert scores[(F[0], F[1])] == Decimal('0.5')
    assert scores[(F[0], F[2])] == scores[(F[1], F[2])] == 1
    scores = pairwise_actual_scores([[F[0]], [F[1], F[2]]])
    assert scores[(F[1], F[2])] == Decimal('0.5')
    for groups in ([], [[F[0]]], [[F[0], F[0]]], [list(F[1:])], None):
        with pytest.raises(ValueError):
            pairwise_actual_scores(groups)


def test_mean_rounding_conservation_and_input_order():
    roster = {F[0]: ['a', 'b'], F[1]: ['c', 'd'], F[2]: ['e', 'f']}
    ratings = {'a': 800, 'b': 1200, 'c': 1000, 'd': 1000, 'e': 1000, 'f': 1000}
    groups = [[F[0]], [F[1]], [F[2]]]
    normal = calculate_match(roster, ratings, groups)
    reordered = calculate_match(dict(reversed(list(roster.items()))), ratings, groups)
    assert normal['meanRatings'][F[0]] == 1000
    assert normal['factionDeltas'] == reordered['factionDeltas'] == dict(zip(F, (24, 0, -24)))
    assert sum(normal['playerDeltas'].values()) == 0
    assert calculate_match({faction: [faction] for faction in F},
                           {faction: -1000 for faction in F}, groups)['factionDeltas'] == dict(zip(F, (24, 0, -24)))
    assert round_half_away(Decimal('0.5')) == 1
    assert round_half_away(Decimal('-0.5')) == -1
    assert conserve_deltas({F[0]: Decimal('0.6'), F[1]: Decimal('0.6'), F[2]: Decimal('-1.2')}) == {
        F[0]: 0, F[1]: 1, F[2]: -1}
    assert conserve_deltas({F[0]: Decimal('-0.6'), F[1]: Decimal('-0.6'), F[2]: Decimal('1.2')}) == {
        F[0]: 0, F[1]: -1, F[2]: 1}
    with pytest.raises(ValueError, match='unequal_faction_sizes'):
        calculate_match({F[0]: ['a', 'b'], F[1]: ['c'], F[2]: ['e']}, ratings, groups)


def test_roster_eligibility_and_reserves_are_excluded():
    _accounts('alice', 'bob', 'carol', 'reserve')
    save_wardogs_lobby(app_core.get_db_connection, _lobby('r1', reserve='reserve'))
    confirm_wardogs_result(app_core.get_db_connection, 'r1', 'admin', _result(), now=_when())
    generation = _generation()
    _, idempotent = confirm_wardogs_result(app_core.get_db_connection, 'r1', 'admin', _result(), now=_when(1))
    assert idempotent and _generation() == generation
    assert get_player_rating(app_core.get_db_connection, 'alice', 'r1')['match']['delta'] == 24
    assert get_player_rating(app_core.get_db_connection, 'reserve', 'r1')['match'] is None
    for lobby_id, names, unregistered, reason in (
        ('r2', ('missing', 'bob', 'carol'), None, 'unresolved_player_identity'),
        ('r3', ('alice', 'bob', 'carol'), 'alice', 'unresolved_player_identity'),
    ):
        save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id, names, unregistered=unregistered))
        confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', _result(), now=_when(1))
        with app_core.get_db_connection() as conn:
            row = conn.execute('''SELECT reason FROM wardogs_rating_skips
                WHERE generation_id=? AND lobby_id=?''', (_generation(), lobby_id)).fetchone()
        assert row['reason'] == reason


def test_correction_replays_later_matches_and_keeps_old_generation():
    _accounts('alice', 'bob', 'carol')
    for lobby_id in ('early', 'later'):
        save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id))
    confirm_wardogs_result(app_core.get_db_connection, 'early', 'admin', _result(), now=_when())
    generation1 = _generation()
    assert [row['delta'] for row in _events(generation1)] == [0, -24, 24]
    confirm_wardogs_result(app_core.get_db_connection, 'later', 'admin', _result(), now=_when(1))
    generation2 = _generation()
    old_later = {row['player_id']: row['delta'] for row in _events(generation2) if row['lobby_id'] == 'later'}
    corrected, duplicate = correct_wardogs_result(
        app_core.get_db_connection, 'early', 'admin', _result((F[1], F[0], F[2])),
        expected_revision_id='wardogs:early:1', correction_reason='Correct placement', now=_when(2))
    assert not duplicate and corrected['revisionNumber'] == 2
    generation3 = _generation()
    assert generation3 > generation2 > generation1
    new_events = _events(generation3)
    assert len(new_events) == 6
    assert all(row['calculation_version'] == VERSION for row in new_events)
    assert {row['result_revision_id'] for row in new_events if row['lobby_id'] == 'early'} == {'wardogs:early:2'}
    assert {row['player_id']: row['delta'] for row in new_events if row['lobby_id'] == 'later'} != old_later
    assert len(_events(generation2)) == 6
    for row in new_events:
        assert row['rating_after'] == row['rating_before'] + row['delta']
    assert get_player_rating(app_core.get_db_connection, 'alice', 'early')['match']['delta'] == 0
    assert get_player_rating(app_core.get_db_connection, 'alice')['currentRating'] == next(
        row['rating_after'] for row in new_events if row['lobby_id'] == 'later' and row['player_id'] == 'alice')
    with app_core.get_db_connection() as conn:
        conn.execute('BEGIN IMMEDIATE')
        assert replay_current_results(conn) == generation3
    assert _generation() == generation3


def test_audit_rows_are_immutable_and_roster_survives_cleanup():
    _accounts('alice', 'bob', 'carol')
    save_wardogs_lobby(app_core.get_db_connection, _lobby('cleanup'))
    confirm_wardogs_result(app_core.get_db_connection, 'cleanup', 'admin', _result(), now=_when())
    original = _events(_generation())
    with app_core.get_db_connection() as conn:
        conn.execute('DELETE FROM wardogs_lobbies WHERE lobby_id=?', ('cleanup',))
    correct_wardogs_result(app_core.get_db_connection, 'cleanup', 'admin', _result((F[1], F[0], F[2])),
                           expected_revision_id='wardogs:cleanup:1', correction_reason='Review', now=_when(1))
    assert len(_events(_generation())) == 3
    with app_core.get_db_connection() as conn:
        stored = [dict(row) for row in conn.execute('''SELECT * FROM wardogs_rating_events
            WHERE generation_id=? ORDER BY match_order, faction_id, player_id''',
            (original[0]['generation_id'],))]
        assert stored == original
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('UPDATE wardogs_rating_events SET delta=999 WHERE event_id=?',
                         (original[0]['event_id'],))
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute('DELETE FROM wardogs_rating_events WHERE event_id=?',
                         (original[0]['event_id'],))


def test_activation_boundary_restart_and_void_correction():
    _accounts('alice', 'bob', 'carol')
    save_wardogs_lobby(app_core.get_db_connection, _lobby('legacy'))
    confirm_wardogs_result(app_core.get_db_connection, 'legacy', 'admin', _result(),
                           now=datetime(2020, 1, 1, tzinfo=timezone.utc))
    assert get_player_rating(app_core.get_db_connection, 'alice', 'legacy')['match'] is None
    correct_wardogs_result(app_core.get_db_connection, 'legacy', 'admin', _result((F[1], F[0], F[2])),
                           expected_revision_id='wardogs:legacy:1', correction_reason='Historical review', now=_when())
    assert get_player_rating(app_core.get_db_connection, 'alice', 'legacy')['match'] is None
    save_wardogs_lobby(app_core.get_db_connection, _lobby('current'))
    confirm_wardogs_result(app_core.get_db_connection, 'current', 'admin', _result(), now=_when())
    assert get_player_rating(app_core.get_db_connection, 'alice', 'current')['currentRating'] == 1024
    generation = _generation()
    app_core.init_database()
    assert _generation() == generation
    assert get_player_rating(app_core.get_db_connection, 'alice')['currentRating'] == 1024
    correct_wardogs_result(app_core.get_db_connection, 'current', 'admin', _result(status='void'),
                           expected_revision_id='wardogs:current:1', correction_reason='Void', now=_when(2))
    assert _generation() > generation
    assert get_player_rating(app_core.get_db_connection, 'alice', 'current') == {
        'currentRating': 1000, 'match': None}
    assert _events(_generation()) == []


def test_noncompetitive_outcomes_are_skipped_with_controlled_reason():
    _accounts('alice', 'bob', 'carol')
    for status in ('incomplete', 'void'):
        lobby_id = f'outcome-{status}'
        save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id))
        confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', _result(status=status), now=_when())
        with app_core.get_db_connection() as conn:
            row = conn.execute('''SELECT reason FROM wardogs_rating_skips
                WHERE generation_id=? AND lobby_id=?''', (_generation(), lobby_id)).fetchone()
        assert row['reason'] == 'unsupported_outcome'
        assert get_player_rating(app_core.get_db_connection, 'alice', lobby_id)['match'] is None


def test_participant_api_exposes_only_viewers_rating(flask_app):
    _accounts('alice', 'bob', 'carol')
    save_wardogs_lobby(app_core.get_db_connection, _lobby('api-rating'))
    confirm_wardogs_result(app_core.get_db_connection, 'api-rating', 'admin', _result(), now=_when())
    client = flask_app.test_client()
    for username, expected in (('alice', 1024), ('bob', 1000), ('carol', 976)):
        with flask_app.app_context():
            token = create_access_token(identity=username)
        response = client.get('/api/wardogs/lobbies/api-rating',
                              headers={'Authorization': f'Bearer {token}'})
        assert response.status_code == 200
        rating = response.get_json()['match']['rating']
        assert rating['currentRating'] == expected
        assert rating['match']['after'] == expected
        assert 'playerId' not in rating
    with flask_app.app_context():
        token = create_access_token(identity='outsider')
    response = client.get('/api/wardogs/lobbies/api-rating',
                          headers={'Authorization': f'Bearer {token}'})
    assert response.status_code == 403


def test_failed_replay_rolls_back_result_revision(monkeypatch):
    _accounts('alice', 'bob', 'carol')
    save_wardogs_lobby(app_core.get_db_connection, _lobby('atomic'))
    import services.wardogs_results as results
    monkeypatch.setattr(results, 'apply_result_revision', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('failure')))
    with pytest.raises(RuntimeError):
        confirm_wardogs_result(app_core.get_db_connection, 'atomic', 'admin', _result(), now=_when())
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions WHERE lobby_id="atomic"').fetchone()[0] == 0
    assert _generation() is None
