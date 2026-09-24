"""Participant history only reads authoritative WARDOGS revisions and rating replay."""

from datetime import datetime, timedelta, timezone

import app_core
from flask_jwt_extended import create_access_token

from services.wardogs_lobby import save_wardogs_lobby
from services.wardogs_rating import get_player_rating
from services.wardogs_results import (
    confirm_wardogs_result, correct_wardogs_result, get_wardogs_result_history,
)


FACTIONS = ('valkyra', 'lonestar', 'manticore')


def _lobby(lobby_id, *, reserve=False):
    members = ('alice', 'bob', 'carol')
    factions = []
    for faction, username in zip(FACTIONS, members, strict=True):
        groups = [{'id': f'{faction}-active', 'type': 'solo', 'name': 'Solo',
                   'leaderId': None, 'players': [{'id': username, 'registered': True,
                                                  'rosterStatus': 'active', 'ready': False}]}]
        if reserve and faction == 'valkyra':
            groups.append({'id': 'reserve', 'type': 'solo', 'name': 'Solo',
                           'leaderId': None, 'players': [{'id': 'dana', 'registered': True,
                                                          'rosterStatus': 'reserve', 'ready': False}]})
        factions.append({'id': faction, 'commanderId': None, 'groups': groups})
    return {'id': lobby_id, 'phase': 'assembling', 'serverId': None, 'factions': factions}


def _headers(flask_app, username):
    with flask_app.app_context():
        token = create_access_token(identity=username)
    return {'Authorization': f'Bearer {token}'}


def _result(status='completed_win'):
    if status in {'incomplete', 'void'}:
        return {'status': status}
    return {'status': status, 'scores': dict(zip(FACTIONS, (90, 20, 5), strict=True)),
            'placementGroups': [['valkyra'], ['lonestar'], ['manticore']]}


def test_participant_history_requires_auth_and_excludes_unconfirmed_and_other_players(flask_app):
    save_wardogs_lobby(app_core.get_db_connection, _lobby('wd-current'))
    client = flask_app.test_client()
    current_url = '/api/wardogs/matches/current'
    history_url = '/api/wardogs/matches/history'
    assert client.get(current_url).status_code == 401
    assert client.get(history_url).status_code == 401
    current = client.get(current_url, headers=_headers(flask_app, 'alice')).get_json()['match']
    assert current == {'lobbyId': 'wd-current', 'factionId': 'valkyra',
                       'rosterStatus': 'active', 'state': 'waiting_for_server', 'createdAt': None}
    assert client.get(current_url, headers=_headers(flask_app, 'outsider')).get_json()['match'] is None
    assert client.get(history_url, headers=_headers(flask_app, 'alice')).get_json()['matches'] == []
    confirm_wardogs_result(app_core.get_db_connection, 'wd-current', 'admin', _result())
    assert client.get(current_url, headers=_headers(flask_app, 'alice')).get_json()['match'] is None
    assert client.get(history_url, headers=_headers(flask_app, 'outsider')).get_json()['matches'] == []

    allocated = _lobby('wd-allocated')
    allocated['serverId'] = 7
    save_wardogs_lobby(app_core.get_db_connection, allocated)
    current = client.get(current_url, headers=_headers(flask_app, 'alice')).get_json()['match']
    assert current['state'] == 'server_allocated'


def test_latest_revision_and_active_replayed_rating_are_read_without_mutation(flask_app):
    with app_core.get_db_connection() as conn:
        conn.executemany('INSERT INTO users (username, password) VALUES (?, ?)',
                         [(name, 'test') for name in ('alice', 'bob', 'carol')])
    save_wardogs_lobby(app_core.get_db_connection, _lobby('wd-rated'))
    confirm_wardogs_result(app_core.get_db_connection, 'wd-rated', 'admin', _result())
    client = flask_app.test_client()
    url = '/api/wardogs/matches/history'
    alice_before = client.get(url, headers=_headers(flask_app, 'alice')).get_json()['matches'][0]
    assert alice_before['result']['outcome'] == 'win'
    assert alice_before['result']['placement'] == 1
    assert alice_before['rating']['delta'] == 24
    bob = client.get(url, headers=_headers(flask_app, 'bob')).get_json()['matches'][0]
    assert bob['result']['outcome'] == 'loss'
    revision_id = get_wardogs_result_history(app_core.get_db_connection, 'wd-rated')[0]['revisionId']
    corrected = {'status': 'tie', 'scores': dict(zip(FACTIONS, (30, 30, 10), strict=True)),
                 'placementGroups': [['valkyra', 'lonestar'], ['manticore']]}
    correct_wardogs_result(app_core.get_db_connection, 'wd-rated', 'admin', corrected,
                           expected_revision_id=revision_id, correction_reason='Referee review')
    with app_core.get_db_connection() as conn:
        before = conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions').fetchone()[0]
        generation = conn.execute('SELECT active_generation_id FROM wardogs_rating_state').fetchone()[0]
    alice = client.get(url, headers=_headers(flask_app, 'alice')).get_json()['matches'][0]
    assert alice['result']['status'] == 'tie'
    assert alice['result']['outcome'] == 'tie'
    assert alice['result']['corrected'] is True
    assert alice['result']['revisionNumber'] == 2
    assert alice['rating'] == get_player_rating(app_core.get_db_connection, 'alice', 'wd-rated')['match']
    assert alice['rating']['delta'] != alice_before['rating']['delta']
    assert 'actorId' not in alice and 'correctionReason' not in alice['result']
    with app_core.get_db_connection() as conn:
        conn.execute('DELETE FROM wardogs_lobbies WHERE lobby_id=?', ('wd-rated',))
        conn.commit()
    after_cleanup = client.get(url, headers=_headers(flask_app, 'alice')).get_json()['matches'][0]
    assert after_cleanup['result'] == alice['result']
    assert after_cleanup['rating'] == alice['rating']
    with app_core.get_db_connection() as conn:
        assert conn.execute('SELECT COUNT(*) FROM wardogs_result_revisions').fetchone()[0] == before
        assert conn.execute('SELECT active_generation_id FROM wardogs_rating_state').fetchone()[0] == generation


def test_incomplete_void_and_reserve_keep_role_without_rating(flask_app):
    for status in ('incomplete', 'void'):
        lobby_id = f'wd-{status}'
        save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id, reserve=True))
        confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin', _result(status))
    rows = flask_app.test_client().get('/api/wardogs/matches/history',
                                       headers=_headers(flask_app, 'dana')).get_json()['matches']
    assert {row['result']['outcome'] for row in rows} == {'incomplete', 'void'}
    assert all(row['rosterStatus'] == 'reserve' and row['rating'] is None for row in rows)


def test_lower_placement_tie_is_a_loss_when_another_faction_wins(flask_app):
    save_wardogs_lobby(app_core.get_db_connection, _lobby('wd-lower-tie'))
    confirm_wardogs_result(app_core.get_db_connection, 'wd-lower-tie', 'admin', {
        'status': 'completed_win',
        'scores': dict(zip(FACTIONS, (90, 20, 20), strict=True)),
        'placementGroups': [['valkyra'], ['lonestar', 'manticore']],
    })
    rows = flask_app.test_client().get('/api/wardogs/matches/history',
                                       headers=_headers(flask_app, 'bob')).get_json()['matches']
    assert rows[0]['result']['outcome'] == 'loss'
    assert rows[0]['result']['placement'] == 2


def test_recent_history_orders_by_instant_across_utc_offsets(flask_app):
    earlier = datetime.now(timezone.utc) + timedelta(minutes=1)
    later = earlier + timedelta(minutes=1)
    for lobby_id, timestamp in (
        ('wd-earlier', earlier.astimezone(timezone(timedelta(hours=2)))),
        ('wd-later', later),
    ):
        save_wardogs_lobby(app_core.get_db_connection, _lobby(lobby_id))
        confirm_wardogs_result(app_core.get_db_connection, lobby_id, 'admin',
                               _result(), now=timestamp)
    rows = flask_app.test_client().get('/api/wardogs/matches/history?limit=1',
                                       headers=_headers(flask_app, 'alice')).get_json()['matches']
    assert [row['lobbyId'] for row in rows] == ['wd-later']
