"""Offline coverage for referee-confirmed WARDOGS results."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3

import app as backend_app
import app_core
from flask_jwt_extended import create_access_token

from services.game_server_contracts import FactionScore, PlayerSnapshot, ServerStatus
from services.wardogs_lobby import get_wardogs_lobby, observe_wardogs_lobby, save_wardogs_lobby
from services.wardogs_results import (
    StaleWardogsRevisionError, confirm_wardogs_result, correct_wardogs_result,
    get_wardogs_result, get_wardogs_result_history, init_wardogs_result_tables,
)


FACTIONS = ('valkyra', 'lonestar', 'manticore')


def lobby(lobby_id='wd-result'):
    return {
        'id': lobby_id, 'phase': 'assembling', 'serverId': None,
        'factions': [{
            'id': faction, 'commanderId': None,
            'groups': [{
                'id': f'{faction}-solo', 'type': 'solo', 'name': 'Solo', 'leaderId': None,
                'players': [{
                    'id': user, 'displayName': user.title(),
                    'steamId': f'7656119800000000{index}', 'registered': True,
                    'rosterStatus': 'active', 'ready': False,
                }],
            }],
        } for index, (faction, user) in enumerate(zip(FACTIONS, ('alice', 'bob', 'carol'), strict=True), 1)],
    }


def auth_headers(flask_app, username):
    with flask_app.app_context():
        token = create_access_token(identity=username)
    return {'Authorization': f'Bearer {token}'}


def complete_win(scores=None):
    return {'status': 'completed_win', 'scores': scores or dict(zip(FACTIONS, (90, 20, 5))),
            'placementGroups': [['valkyra'], ['lonestar'], ['manticore']],
            'winnerFaction': 'valkyra', 'note': 'Referee checked the board.'}


def test_result_is_absent_until_explicit_admin_confirmation_and_survives_reread(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    client = flask_app.test_client()
    url = '/api/wardogs/lobbies/wd-result'
    assert client.get(url, headers=auth_headers(flask_app, 'alice')).get_json()['match']['result']['status'] == 'unconfirmed'
    result_url = '/api/admin/wardogs/lobbies/wd-result/result'
    assert client.post(result_url, json=complete_win(), headers=auth_headers(flask_app, 'alice')).status_code == 403
    assert client.post(result_url, json=complete_win()).status_code == 401
    response = client.post(result_url, json=complete_win(), headers=auth_headers(flask_app, 'admin'))
    assert response.status_code == 200
    assert response.get_json()['result']['winnerFaction'] == 'valkyra'
    assert response.get_json()['result']['placementGroups'] == [['valkyra'], ['lonestar'], ['manticore']]
    public = client.get(url, headers=auth_headers(flask_app, 'alice')).get_json()['match']['result']
    assert public == response.get_json()['result']
    assert 'confirmedBy' not in public and 'provenance' not in public
    with app_core.get_db_connection() as conn:
        row = conn.execute('SELECT * FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-result',)).fetchone()
    assert row['actor_id'] == 'admin'
    assert row['revision_type'] == 'confirmation'
    assert get_wardogs_result(app_core.get_db_connection, 'wd-result') == public


def test_all_explicit_outcomes_persist_with_three_faction_contract(flask_app):
    for result_status, payload in (
        ('completed_win', complete_win()),
        ('tie', {'status': 'tie', 'scores': dict(zip(FACTIONS, (10, 10, 10))),
                 'placementGroups': [['valkyra', 'lonestar', 'manticore']]}),
        ('incomplete', {'status': 'incomplete', 'note': 'Stopped early.'}),
        ('void', {'status': 'void', 'note': 'Cancelled.'}),
    ):
        lobby_id = f'wd-{result_status}'
        save_wardogs_lobby(app_core.get_db_connection, lobby(lobby_id))
        result, idempotent = confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', payload)
        assert idempotent is False
        assert result['status'] == result_status
        with app_core.get_db_connection() as conn:
            row = conn.execute('SELECT status, scores_json, placement_groups_json, winner_faction, tied FROM wardogs_result_revisions WHERE lobby_id=?',
                               (lobby_id,)).fetchone()
        assert row['status'] == result_status
        if result_status == 'tie':
            assert row['tied'] == 1 and row['winner_faction'] is None
            assert row['placement_groups_json'] is not None
        if result_status == 'completed_win':
            assert row['placement_groups_json'] is not None
        if result_status in {'incomplete', 'void'}:
            assert row['scores_json'] is None and row['winner_faction'] is None


def test_observation_prefill_provenance_records_match_and_divergence():
    save_wardogs_lobby(app_core.get_db_connection, lobby('wd-observed'))
    when = datetime(2026, 9, 23, tzinfo=timezone.utc)
    values = dict(zip(FACTIONS, (100, 60, 30)))

    def save_provenance(lobby_id, submitted):
        save_wardogs_lobby(app_core.get_db_connection, lobby(lobby_id))
        return confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', submitted,
                                      observed_scores=values, observed_at=when.isoformat(), now=when)

    save_provenance('wd-matching', complete_win(values))
    save_provenance('wd-diverged', complete_win(dict(zip(FACTIONS, (99, 60, 30)))))
    save_wardogs_lobby(app_core.get_db_connection, lobby('wd-manual'))
    confirm_wardogs_result(app_core.get_db_connection, 'wd-manual', 'admin', complete_win(), now=when)
    with app_core.get_db_connection() as conn:
        matching = conn.execute('SELECT * FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-matching',)).fetchone()
        diverged = conn.execute('SELECT * FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-diverged',)).fetchone()
        manual = conn.execute('SELECT * FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-manual',)).fetchone()
    assert matching['observation_available'] == 1 and matching['observed_at'] == when.isoformat()
    assert matching['observed_scores_json'] == matching['submitted_scores_json']
    assert matching['differs_from_observation'] == 0
    assert diverged['differs_from_observation'] == 1
    assert manual['observation_available'] == 0 and manual['observed_at'] is None


def test_invalid_factions_scores_and_outcome_semantics_are_rejected():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    invalid = [
        {'status': 'completed_win', 'scores': {'bad': 1}, 'placementGroups': [['valkyra'], ['lonestar'], ['manticore']], 'winnerFaction': 'valkyra'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, -1, 0))), 'placementGroups': [['valkyra'], ['lonestar'], ['manticore']], 'winnerFaction': 'valkyra'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, 1, 1))), 'placementGroups': [['valkyra'], ['lonestar'], ['manticore']], 'winnerFaction': 'nope'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, 2, 0))), 'placementGroups': [['valkyra'], ['lonestar'], ['manticore']], 'winnerFaction': 'valkyra'},
        {'status': 'tie', 'scores': dict(zip(FACTIONS, (1, 1, 1))), 'placementGroups': [['valkyra', 'lonestar', 'manticore']], 'winnerFaction': 'valkyra'},
        {'status': 'tie', 'scores': dict(zip(FACTIONS, (1, 2, 0))), 'placementGroups': [['valkyra'], ['lonestar'], ['manticore']]},
        {'status': 'incomplete', 'winnerFaction': 'valkyra'},
        {'status': 'void', 'scores': dict(zip(FACTIONS, (True, 0, 0)))},
    ]
    for payload in invalid:
        try:
            confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', payload)
        except ValueError:
            continue
        raise AssertionError(f'Invalid result unexpectedly accepted: {payload}')


def test_explicit_placement_groups_cover_supported_ties_and_validate_scores():
    cases = (
        ('completed_win', {'valkyra': 9, 'lonestar': 1, 'manticore': 4},
         [['valkyra'], ['manticore'], ['lonestar']], 'valkyra'),
        ('tie', {'valkyra': 9, 'lonestar': 1, 'manticore': 9},
         [['valkyra', 'manticore'], ['lonestar']], None),
        ('completed_win', {'valkyra': 9, 'lonestar': 4, 'manticore': 4},
         [['valkyra'], ['lonestar', 'manticore']], 'valkyra'),
        ('tie', {'valkyra': 9, 'lonestar': 9, 'manticore': 9},
         [['valkyra', 'lonestar', 'manticore']], None),
    )
    for index, (status, scores, groups, winner) in enumerate(cases):
        lobby_id = f'wd-placement-{index}'
        save_wardogs_lobby(app_core.get_db_connection, lobby(lobby_id))
        result, _ = confirm_wardogs_result(
            app_core.get_db_connection, lobby_id, 'admin',
            {'status': status, 'scores': scores, 'placementGroups': groups,
             'winnerFaction': winner})
        assert result['placementGroups'] == groups
        assert result['winnerFaction'] == winner

    invalid_groups = (
        [['valkyra'], ['valkyra'], ['manticore']],
        [['valkyra'], ['manticore']],
        [['valkyra'], ['manticore'], ['lonestar', 'unknown']],
        [['valkyra'], [], ['lonestar', 'manticore']],
        [['valkyra', 'lonestar'], ['manticore'], ['valkyra']],
        [['valkyra'], ['lonestar'], ['manticore'], []],
    )
    for groups in invalid_groups:
        try:
            confirm_wardogs_result(app_core.get_db_connection, 'wd-placement-0', 'admin', {
                'status': 'completed_win',
                'scores': {'valkyra': 9, 'lonestar': 1, 'manticore': 4},
                'placementGroups': groups,
            })
        except ValueError:
            continue
        raise AssertionError(f'Invalid placement unexpectedly accepted: {groups}')

    contradictory = (
        ('completed_win', {'valkyra': 4, 'lonestar': 9, 'manticore': 1},
         [['valkyra'], ['manticore'], ['lonestar']]),
        ('tie', {'valkyra': 9, 'lonestar': 1, 'manticore': 8},
         [['valkyra', 'manticore'], ['lonestar']]),
        ('completed_win', {'valkyra': 9, 'lonestar': 4, 'manticore': 3},
         [['valkyra'], ['lonestar', 'manticore']]),
        ('tie', {'valkyra': 9, 'lonestar': 8, 'manticore': 7},
         [['valkyra', 'lonestar', 'manticore']]),
    )
    for status, scores, groups in contradictory:
        try:
            confirm_wardogs_result(app_core.get_db_connection, 'wd-placement-0', 'admin', {
                'status': status, 'scores': scores, 'placementGroups': groups,
            })
        except ValueError:
            continue
        raise AssertionError(f'Score/placement contradiction accepted: {scores}, {groups}')


def test_existing_revision_table_is_upgraded_in_place_and_idempotently(tmp_path):
    database = tmp_path / 'wardogs-legacy-revisions.sqlite'

    def get_db_connection():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        return connection

    with get_db_connection() as conn:
        conn.execute("""CREATE TABLE wardogs_result_revisions (
            revision_id TEXT PRIMARY KEY, lobby_id TEXT NOT NULL, revision_number INTEGER NOT NULL,
            supersedes_revision_id TEXT, revision_type TEXT NOT NULL, status TEXT NOT NULL,
            scores_json TEXT, winner_faction TEXT, tied INTEGER NOT NULL DEFAULT 0,
            actor_id TEXT NOT NULL, created_at TEXT NOT NULL, confirmed_at TEXT NOT NULL,
            note TEXT, correction_reason TEXT, observation_available INTEGER NOT NULL,
            observed_at TEXT, observed_scores_json TEXT, submitted_scores_json TEXT,
            differs_from_observation INTEGER, request_json TEXT NOT NULL,
            UNIQUE (lobby_id, revision_number)
        )""")
        conn.execute("""INSERT INTO wardogs_result_revisions VALUES (
            'legacy-revision-7', 'wd-table-upgrade', 7, 'older-revision', 'correction',
            'completed_win', '{"valkyra":10,"lonestar":5,"manticore":1}', 'valkyra', 0,
            'admin', 'created', 'confirmed', 'kept note', 'kept reason', 1, 'observed',
            '{"valkyra":10,"lonestar":5,"manticore":1}',
            '{"valkyra":10,"lonestar":5,"manticore":1}', 0, '{}'
        )""")
        conn.commit()

    init_wardogs_result_tables(get_db_connection)
    init_wardogs_result_tables(get_db_connection)
    history = get_wardogs_result_history(get_db_connection, 'wd-table-upgrade')
    assert len(history) == 1
    assert history[0]['revisionId'] == 'legacy-revision-7'
    assert history[0]['revisionNumber'] == 7
    assert history[0]['actorId'] == 'admin'
    assert history[0]['correctionReason'] == 'kept reason'
    assert history[0]['placementGroups'] == [['valkyra'], ['lonestar'], ['manticore']]
    with get_db_connection() as conn:
        assert 'placement_groups_json' in {
            row['name'] for row in conn.execute('PRAGMA table_info(wardogs_result_revisions)')}
        assert conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions').fetchone()[0] == 1


def test_identical_retry_is_idempotent_conflict_is_immutable_and_race_is_safe():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    payload = complete_win()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(confirm_wardogs_result, app_core.get_db_connection,
                                  'wd-result', 'admin', payload) for _ in range(2)]
        results = [future.result() for future in futures]
    assert sorted(idempotent for _, idempotent in results) == [False, True]
    duplicate, idempotent = confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'second-admin', payload)
    assert idempotent is True and duplicate['winnerFaction'] == 'valkyra'
    conflicting = complete_win(dict(zip(FACTIONS, (91, 20, 5))))
    try:
        confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', conflicting)
    except FileExistsError:
        pass
    else:
        raise AssertionError('Conflicting result replaced an authoritative record')
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-result',)).fetchone()[0] == 1


def test_later_live_observation_does_not_change_authoritative_result():
    current = lobby('wd-immutable')
    save_wardogs_lobby(app_core.get_db_connection, current)
    confirmed, _ = confirm_wardogs_result(app_core.get_db_connection, 'wd-immutable', 'admin', complete_win())
    observed_at = datetime(2026, 9, 23, tzinfo=timezone.utc)

    class FakeAdapter:
        def get_status(self):
            return ServerStatus(observed_at, faction_scores=(
                FactionScore('Valkyra', 0), FactionScore('Lonestar', 999), FactionScore('Manticore', 1)))
        def get_players(self):
            return PlayerSnapshot((), observed_at)

    current['serverId'] = 7
    observe_wardogs_lobby(current, FakeAdapter(), now=observed_at)
    assert get_wardogs_result(app_core.get_db_connection, 'wd-immutable') == confirmed
    assert get_wardogs_lobby(app_core.get_db_connection, 'wd-immutable')['factions'][0]['id'] == 'valkyra'


def test_legacy_confirmation_migrates_once_to_revision_one_with_provenance():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    payload = complete_win()
    confirmed, _ = confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', payload)
    with app_core.get_db_connection() as conn:
        conn.execute('DELETE FROM wardogs_result_revisions WHERE lobby_id=?', ('wd-result',))
        conn.execute("""CREATE TABLE wardogs_results (
            lobby_id TEXT PRIMARY KEY, game_type TEXT NOT NULL, status TEXT NOT NULL,
            scores_json TEXT, winner_faction TEXT, tied INTEGER NOT NULL DEFAULT 0,
            confirmed_at TEXT NOT NULL, confirmed_by TEXT NOT NULL, note TEXT,
            observation_available INTEGER NOT NULL, observed_at TEXT,
            observed_scores_json TEXT, submitted_scores_json TEXT,
            differs_from_observation INTEGER, submission_json TEXT NOT NULL
        )""")
        conn.execute("""INSERT INTO wardogs_results (
            lobby_id, game_type, status, scores_json, winner_faction, tied,
            confirmed_at, confirmed_by, note, observation_available, observed_at,
            observed_scores_json, submitted_scores_json, differs_from_observation, submission_json
        ) VALUES (?, 'wardogs', ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, 1, ?)""", (
            'wd-result', 'completed_win', '{"valkyra":90,"lonestar":20,"manticore":5}',
            'valkyra', 0, '2026-09-23T12:00:00+00:00', 'admin', 'first note',
            '2026-09-23T11:59:00+00:00', '{"valkyra":1,"lonestar":2,"manticore":3}',
            '{"valkyra":90,"lonestar":20,"manticore":5}',
            '{"note":"Referee checked the board.","scores":{"lonestar":20,"manticore":5,"valkyra":90},"status":"completed_win","tied":false,"winnerFaction":"valkyra"}',
        ))
        conn.commit()
        conn.execute("""INSERT INTO wardogs_results (
            lobby_id, game_type, status, scores_json, winner_faction, tied,
            confirmed_at, confirmed_by, note, observation_available, observed_at,
            observed_scores_json, submitted_scores_json, differs_from_observation, submission_json
        ) VALUES (?, 'wardogs', 'completed_win', ?, 'manticore', 0, ?, 'admin', 'unsafe legacy',
                  0, NULL, NULL, ?, NULL, ?)""", (
            'wd-legacy-unsafe', '{"valkyra":10,"lonestar":4,"manticore":1}',
            '2026-09-23T14:00:00+00:00', '{"valkyra":10,"lonestar":4,"manticore":1}',
            '{"status":"completed_win","winnerFaction":"manticore","scores":{"valkyra":10,"lonestar":4,"manticore":1}}',
        ))
        conn.commit()
    init_wardogs_result_tables(app_core.get_db_connection)
    init_wardogs_result_tables(app_core.get_db_connection)
    history = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')
    assert len(history) == 1
    assert history[0]['revisionNumber'] == 1
    assert history[0]['revisionType'] == 'confirmation'
    assert history[0]['actorId'] == 'admin'
    assert history[0]['note'] == 'first note'
    assert history[0]['observation']['available'] is True
    assert history[0]['observation']['differsFromObservation'] is True
    assert history[0]['placementGroups'] == [['valkyra'], ['lonestar'], ['manticore']]
    assert get_wardogs_result(app_core.get_db_connection, 'wd-result')['revisionNumber'] == 1
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_results WHERE lobby_id=?', ('wd-result',)).fetchone()[0] == 1
        conn.execute("""INSERT INTO wardogs_results (
            lobby_id, game_type, status, scores_json, winner_faction, tied,
            confirmed_at, confirmed_by, note, observation_available, observed_at,
            observed_scores_json, submitted_scores_json, differs_from_observation, submission_json
        ) VALUES (?, 'wardogs', 'tie', ?, NULL, 1, ?, 'admin', 'legacy tie', 0, NULL,
                  NULL, ?, NULL, ?)""", (
            'wd-legacy-tie', '{"valkyra":10,"lonestar":10,"manticore":4}',
            '2026-09-23T13:00:00+00:00', '{"valkyra":10,"lonestar":10,"manticore":4}',
            '{"status":"tie","scores":{"valkyra":10,"lonestar":10,"manticore":4}}',
        ))
        conn.commit()
    init_wardogs_result_tables(app_core.get_db_connection)
    init_wardogs_result_tables(app_core.get_db_connection)
    tie_history = get_wardogs_result_history(app_core.get_db_connection, 'wd-legacy-tie')
    assert len(tie_history) == 1
    assert tie_history[0]['placementGroups'] == [['valkyra', 'lonestar'], ['manticore']]
    assert tie_history[0]['placementUnavailable'] is False
    unsafe_history = get_wardogs_result_history(app_core.get_db_connection, 'wd-legacy-unsafe')
    assert len(unsafe_history) == 1
    assert unsafe_history[0]['placementGroups'] is None
    assert unsafe_history[0]['placementUnavailable'] is True


def test_corrections_append_full_revisions_and_latest_is_authoritative():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', complete_win())
    revision1 = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]
    tie = {'status': 'tie', 'scores': dict(zip(FACTIONS, (30, 30, 10))),
           'placementGroups': [['valkyra', 'lonestar'], ['manticore']], 'note': 'Rechecked evidence.'}
    result2, duplicate = correct_wardogs_result(
        app_core.get_db_connection, 'wd-result', 'admin', tie,
        expected_revision_id=revision1['revisionId'], correction_reason='Wrong winner was entered.',
        observed_scores=dict(zip(FACTIONS, (35, 30, 10))),
        observed_at='2026-09-23T12:30:00+00:00')
    assert duplicate is False and result2['revisionNumber'] == 2 and result2['status'] == 'tie'
    assert result2['corrected'] is True
    revision2 = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[-1]
    assert revision2['supersedesRevisionId'] == revision1['revisionId']
    assert revision2['correctionReason'] == 'Wrong winner was entered.'
    assert revision2['observation']['differsFromObservation'] is True
    assert revision1['placementGroups'] == [['valkyra'], ['lonestar'], ['manticore']]
    assert revision2['placementGroups'] == [['valkyra', 'lonestar'], ['manticore']]
    history = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')
    assert [row['revisionNumber'] for row in history] == [1, 2]
    assert history[0]['authoritative'] is False and history[1]['authoritative'] is True
    assert history[0]['status'] == 'completed_win'
    correction3 = {'status': 'void', 'note': 'Cancelled after review.'}
    result3, _ = correct_wardogs_result(
        app_core.get_db_connection, 'wd-result', 'admin2', correction3,
        expected_revision_id=revision2['revisionId'], correction_reason='The match was cancelled.')
    assert result3['revisionNumber'] == 3 and result3['status'] == 'void'
    assert [row['revisionNumber'] for row in get_wardogs_result_history(
        app_core.get_db_connection, 'wd-result')] == [1, 2, 3]


def test_correction_requires_reason_and_fresh_expected_revision():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', complete_win())
    revision1 = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]
    correction = {'status': 'tie', 'scores': dict(zip(FACTIONS, (5, 5, 0))),
                  'placementGroups': [['valkyra', 'lonestar'], ['manticore']]}
    for reason in ('', '  '):
        try:
            correct_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', correction,
                                   expected_revision_id=revision1['revisionId'], correction_reason=reason)
        except ValueError:
            continue
        raise AssertionError('A correction without a reason was accepted')
    correct_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', correction,
                           expected_revision_id=revision1['revisionId'], correction_reason='Reviewed.')
    try:
        correct_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', correction,
                               expected_revision_id=revision1['revisionId'], correction_reason='Different reason.')
    except StaleWardogsRevisionError:
        pass
    else:
        raise AssertionError('A stale correction request was accepted')


def test_identical_correction_retry_is_idempotent_and_conflicting_race_is_stale():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', complete_win())
    revision1 = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]
    correction = {'status': 'tie', 'scores': dict(zip(FACTIONS, (5, 5, 0))),
                  'placementGroups': [['valkyra', 'lonestar'], ['manticore']]}
    kwargs = {'expected_revision_id': revision1['revisionId'], 'correction_reason': 'Audit review.'}
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(correct_wardogs_result, app_core.get_db_connection,
                                   'wd-result', 'admin', correction, **kwargs) for _ in range(2)]
        results = [future.result() for future in futures]
    assert sorted(idempotent for _, idempotent in results) == [False, True]
    assert len(get_wardogs_result_history(app_core.get_db_connection, 'wd-result')) == 2
    try:
        correct_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', complete_win(),
                               expected_revision_id=revision1['revisionId'],
                               correction_reason='A different concurrent correction.')
    except StaleWardogsRevisionError:
        pass
    else:
        raise AssertionError('A conflicting concurrent correction was accepted')


def test_admin_history_api_is_private_and_participant_gets_latest_only(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    confirm_url = '/api/admin/wardogs/lobbies/wd-result/result'
    correction_url = '/api/admin/wardogs/lobbies/wd-result/result/corrections'
    history_url = '/api/admin/wardogs/lobbies/wd-result/result/history'
    client = flask_app.test_client()
    confirmed = client.post(confirm_url, json=complete_win(), headers=auth_headers(flask_app, 'admin'))
    assert confirmed.status_code == 200
    revision_id = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]['revisionId']
    correction_body = {
        'expectedRevisionId': revision_id,
        'correctionReason': 'Reviewed referee sheet.',
        'result': {'status': 'tie', 'scores': dict(zip(FACTIONS, (10, 10, 5))),
                   'placementGroups': [['valkyra', 'lonestar'], ['manticore']]},
    }
    assert client.post(correction_url, json=correction_body,
                       headers=auth_headers(flask_app, 'alice')).status_code == 403
    assert client.get(history_url, headers=auth_headers(flask_app, 'alice')).status_code == 403
    assert client.post(correction_url, json=correction_body).status_code == 401
    revised = client.post(correction_url, json=correction_body, headers=auth_headers(flask_app, 'admin'))
    assert revised.status_code == 200
    participant = client.get('/api/wardogs/lobbies/wd-result',
                             headers=auth_headers(flask_app, 'alice')).get_json()['match']['result']
    assert participant['revisionNumber'] == 2 and participant['status'] == 'tie'
    assert participant['corrected'] is True
    assert 'actorId' not in participant and 'correctionReason' not in participant
    history = client.get(history_url, headers=auth_headers(flask_app, 'admin')).get_json()['revisions']
    assert len(history) == 2 and history[0]['authoritative'] is False and history[1]['authoritative'] is True
    assert history[1]['actorId'] == 'admin'
    assert history[1]['correctionReason'] == 'Reviewed referee sheet.'
    assert history[0]['placementGroups'] == [['valkyra'], ['lonestar'], ['manticore']]
    assert history[1]['placementGroups'] == [['valkyra', 'lonestar'], ['manticore']]


def test_stale_correction_api_returns_current_revision_for_reload(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    client = flask_app.test_client()
    headers = auth_headers(flask_app, 'admin')
    client.post('/api/admin/wardogs/lobbies/wd-result/result', json=complete_win(), headers=headers)
    old_id = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]['revisionId']
    first = {'expectedRevisionId': old_id, 'correctionReason': 'Fix one.',
             'result': {'status': 'tie', 'scores': dict(zip(FACTIONS, (8, 8, 3))),
                        'placementGroups': [['valkyra', 'lonestar'], ['manticore']]}}
    client.post('/api/admin/wardogs/lobbies/wd-result/result/corrections', json=first, headers=headers)
    stale = {'expectedRevisionId': old_id, 'correctionReason': 'Another version.',
             'result': {'status': 'void'}}
    response = client.post('/api/admin/wardogs/lobbies/wd-result/result/corrections', json=stale, headers=headers)
    assert response.status_code == 409
    assert response.get_json()['code'] == 'stale_revision'
    assert response.get_json()['currentRevisionId'] != old_id


def test_admin_history_and_corrections_survive_lobby_cleanup(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    client = flask_app.test_client()
    headers = auth_headers(flask_app, 'admin')
    client.post('/api/admin/wardogs/lobbies/wd-result/result', json=complete_win(), headers=headers)
    original = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[0]
    with app_core.get_db_connection() as conn:
        conn.execute('DELETE FROM wardogs_lobbies WHERE lobby_id=?', ('wd-result',))
        conn.commit()
    history = client.get('/api/admin/wardogs/lobbies/wd-result/result/history', headers=headers)
    assert history.status_code == 200 and len(history.get_json()['revisions']) == 1
    correction = {'expectedRevisionId': original['revisionId'], 'correctionReason': 'Final audit review.',
                  'result': {'status': 'void'}}
    response = client.post('/api/admin/wardogs/lobbies/wd-result/result/corrections', json=correction, headers=headers)
    assert response.status_code == 200 and response.get_json()['result']['status'] == 'void'
    latest = get_wardogs_result_history(app_core.get_db_connection, 'wd-result')[-1]
    assert latest['observation']['available'] is False
    assert latest['supersedesRevisionId'] == original['revisionId']
