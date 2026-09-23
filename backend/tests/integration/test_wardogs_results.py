"""Offline coverage for referee-confirmed WARDOGS results."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import app as backend_app
import app_core
from flask_jwt_extended import create_access_token

from services.game_server_contracts import FactionScore, PlayerSnapshot, ServerStatus
from services.wardogs_lobby import get_wardogs_lobby, observe_wardogs_lobby, save_wardogs_lobby
from services.wardogs_results import confirm_wardogs_result, get_wardogs_result


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
            'winnerFaction': 'valkyra', 'note': 'Referee checked the board.'}


def test_result_is_absent_until_explicit_admin_confirmation_and_survives_reread(flask_app, monkeypatch):
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: username == 'admin')
    client = flask_app.test_client()
    url = '/api/wardogs/lobbies/wd-result'
    assert client.get(url, headers=auth_headers(flask_app, 'alice')).get_json()['match']['result'] == {
        'status': 'unconfirmed'
    }
    result_url = '/api/admin/wardogs/lobbies/wd-result/result'
    assert client.post(result_url, json=complete_win(), headers=auth_headers(flask_app, 'alice')).status_code == 403
    assert client.post(result_url, json=complete_win()).status_code == 401
    response = client.post(result_url, json=complete_win(), headers=auth_headers(flask_app, 'admin'))
    assert response.status_code == 200
    assert response.get_json()['result']['winnerFaction'] == 'valkyra'
    public = client.get(url, headers=auth_headers(flask_app, 'alice')).get_json()['match']['result']
    assert public == response.get_json()['result']
    assert 'confirmedBy' not in public and 'provenance' not in public
    with app_core.get_db_connection() as conn:
        row = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', ('wd-result',)).fetchone()
    assert row['confirmed_by'] == 'admin'
    assert row['game_type'] == 'wardogs'
    assert get_wardogs_result(app_core.get_db_connection, 'wd-result') == public


def test_all_explicit_outcomes_persist_with_three_faction_contract(flask_app):
    for result_status, payload in (
        ('completed_win', complete_win()),
        ('tie', {'status': 'tie', 'scores': dict(zip(FACTIONS, (10, 10, 10)))}),
        ('incomplete', {'status': 'incomplete', 'note': 'Stopped early.'}),
        ('void', {'status': 'void', 'note': 'Cancelled.'}),
    ):
        lobby_id = f'wd-{result_status}'
        save_wardogs_lobby(app_core.get_db_connection, lobby(lobby_id))
        result, idempotent = confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', payload)
        assert idempotent is False
        assert result['status'] == result_status
        with app_core.get_db_connection() as conn:
            row = conn.execute('SELECT status, scores_json, winner_faction, tied FROM wardogs_results WHERE lobby_id=?',
                               (lobby_id,)).fetchone()
        assert row['status'] == result_status
        if result_status == 'tie':
            assert row['tied'] == 1 and row['winner_faction'] is None
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
        matching = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', ('wd-matching',)).fetchone()
        diverged = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', ('wd-diverged',)).fetchone()
        manual = conn.execute('SELECT * FROM wardogs_results WHERE lobby_id=?', ('wd-manual',)).fetchone()
    assert matching['observation_available'] == 1 and matching['observed_at'] == when.isoformat()
    assert matching['observed_scores_json'] == matching['submitted_scores_json']
    assert matching['differs_from_observation'] == 0
    assert diverged['differs_from_observation'] == 1
    assert manual['observation_available'] == 0 and manual['observed_at'] is None


def test_invalid_factions_scores_and_outcome_semantics_are_rejected():
    save_wardogs_lobby(app_core.get_db_connection, lobby())
    invalid = [
        {'status': 'completed_win', 'scores': {'bad': 1}, 'winnerFaction': 'valkyra'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, -1, 0))), 'winnerFaction': 'valkyra'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, 1, 1))), 'winnerFaction': 'nope'},
        {'status': 'completed_win', 'scores': dict(zip(FACTIONS, (1, 2, 0))), 'winnerFaction': 'valkyra'},
        {'status': 'tie', 'scores': dict(zip(FACTIONS, (1, 1, 1))), 'winnerFaction': 'valkyra'},
        {'status': 'tie', 'scores': dict(zip(FACTIONS, (1, 2, 0)))},
        {'status': 'incomplete', 'winnerFaction': 'valkyra'},
        {'status': 'void', 'scores': dict(zip(FACTIONS, (True, 0, 0)))},
    ]
    for payload in invalid:
        try:
            confirm_wardogs_result(app_core.get_db_connection, 'wd-result', 'admin', payload)
        except ValueError:
            continue
        raise AssertionError(f'Invalid result unexpectedly accepted: {payload}')


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
        assert conn.execute('SELECT COUNT(*) FROM wardogs_results WHERE lobby_id=?', ('wd-result',)).fetchone()[0] == 1


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
