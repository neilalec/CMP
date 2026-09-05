from flask_jwt_extended import create_access_token

import app as backend_app
import app_core


def test_match_history_endpoint(flask_app):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    backend_app.save_completed_match('lobby_history', {
        'created_at': 1000,
        'live_started_at': 1100,
        'selected_map': 'Tallil Outskirts Skirmish v2',
        'players': ['neil', 'sam'],
        'teams': {'team1': ['neil'], 'team2': ['sam']},
        'server_details': {'serverName': '4K War Server'},
        'round_result': {'layer': 'Tallil Outskirts Skirmish v2'}
    }, completed_at=1200)

    response = client.get('/api/matches/history', headers={
        'Authorization': f'Bearer {token}'
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert any(match['lobby_id'] == 'lobby_history' for match in payload['matches'])


def test_match_history_can_filter_by_player_and_scored_results(flask_app):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    backend_app.save_completed_match('lobby_scored', {
        'created_at': 1000,
        'live_started_at': 1100,
        'selected_map': 'Narva Skirmish v1',
        'players': ['neil', 'sam'],
        'teams': {'team1': ['neil'], 'team2': ['sam']},
        'server_details': {'serverName': 'Scored Server'},
        'round_result': {
            'winner': {'faction': 'USA', 'tickets': 102},
            'loser': {'faction': 'RGF', 'tickets': 0}
        }
    }, completed_at=1300)

    backend_app.save_completed_match('lobby_unscored', {
        'created_at': 1001,
        'live_started_at': 1101,
        'selected_map': 'Belaya Skirmish v1',
        'players': ['neil', 'alex'],
        'teams': {'team1': ['neil'], 'team2': ['alex']},
        'server_details': {'serverName': 'Unscored Server'},
        'round_result': {
            'partial': True,
            'winner': {'faction': 'USA', 'inferred': True}
        }
    }, completed_at=1400)

    backend_app.save_completed_match('lobby_other_player', {
        'created_at': 1002,
        'live_started_at': 1102,
        'selected_map': 'Chora Skirmish v1',
        'players': ['jamie', 'alex'],
        'teams': {'team1': ['jamie'], 'team2': ['alex']},
        'server_details': {'serverName': 'Other Server'},
        'round_result': {
            'winner': {'faction': 'USA', 'tickets': 150},
            'loser': {'faction': 'INS', 'tickets': 20}
        }
    }, completed_at=1500)

    response = client.get('/api/matches/history?player=neil&scored=1', headers={
        'Authorization': f'Bearer {token}'
    })

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    lobby_ids = [match['lobby_id'] for match in payload['matches']]
    assert 'lobby_scored' in lobby_ids
    assert 'lobby_unscored' not in lobby_ids
    assert 'lobby_other_player' not in lobby_ids


def test_save_completed_match_applies_elo_once(flask_app):
    original_users = dict(backend_app.users)
    try:
        backend_app.users.clear()
        backend_app.users.update({
            'neil': {
                'password': 'hash',
                'display_name': 'Neil',
                'elo_rating': 1000,
                'elo_matches': 0,
            },
            'sam': {
                'password': 'hash',
                'display_name': 'Sam',
                'elo_rating': 1000,
                'elo_matches': 0,
            },
        })

        lobby = {
            'created_at': 1000,
            'live_started_at': 1100,
            'selected_map': 'Narva Skirmish v1',
            'players': ['neil', 'sam'],
            'teams': {'team1': ['neil'], 'team2': ['sam']},
            'server_details': {'serverName': 'Scored Server'},
            'round_result': {
                'winner': {'team': '1', 'faction': 'USA', 'tickets': 102},
                'loser': {'team': '2', 'faction': 'RGF', 'tickets': 0}
            }
        }

        backend_app.save_completed_match('lobby_elo_scored', lobby, completed_at=1300)
        backend_app.save_completed_match('lobby_elo_scored', lobby, completed_at=1301)

        assert backend_app.users['neil']['elo_rating'] == 1020
        assert backend_app.users['neil']['elo_matches'] == 1
        assert backend_app.users['sam']['elo_rating'] == 980
        assert backend_app.users['sam']['elo_matches'] == 1
    finally:
        backend_app.users.clear()
        backend_app.users.update(original_users)


def test_save_completed_match_dev_solo_smoke_applies_negative_elo(flask_app, monkeypatch):
    monkeypatch.setattr(app_core, 'DEV_MODE', True)
    monkeypatch.setattr(app_core, 'DEV_SOLO_ELO_SMOKE_ENABLED', True)
    monkeypatch.setattr(app_core, 'DEV_SOLO_ELO_SMOKE_USERNAME', 'neil')

    original_users = dict(backend_app.users)
    try:
        backend_app.users.clear()
        backend_app.users.update({
            'neil': {
                'password': 'hash',
                'display_name': 'Neil',
                'elo_rating': 1000,
                'elo_matches': 0,
            },
        })

        backend_app.save_completed_match('lobby_dev_solo_elo', {
            'created_at': 1000,
            'live_started_at': 1100,
            'selected_map': 'Narva Skirmish v1',
            'players': ['neil'],
            'teams': {'team1': ['neil'], 'team2': []},
            'server_details': {'serverName': 'Dev Solo Server'},
            'round_result': {
                'winner': {'team': '2', 'faction': 'RGF', 'tickets': 1},
                'loser': {'team': '1', 'faction': 'USA', 'tickets': 0}
            }
        }, completed_at=1300)

        assert backend_app.users['neil']['elo_rating'] == 980
        assert backend_app.users['neil']['elo_matches'] == 1
    finally:
        backend_app.users.clear()
        backend_app.users.update(original_users)


def test_leaderboard_endpoint_returns_players_by_elo(flask_app):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    original_users = dict(backend_app.users)
    try:
        backend_app.users.clear()
        backend_app.users.update({
            'neil': {
                'password': 'hash',
                'display_name': 'Neil',
                'elo_rating': 1050,
                'elo_matches': 3,
            },
            'sam': {
                'password': 'hash',
                'display_name': 'Sam',
                'elo_rating': 1110,
                'elo_matches': 6,
            },
        })

        response = client.get('/api/leaderboard', headers={
            'Authorization': f'Bearer {token}'
        })
    finally:
        backend_app.users.clear()
        backend_app.users.update(original_users)

    assert response.status_code == 200
    payload = response.get_json()
    assert payload['success'] is True
    assert [player['username'] for player in payload['players']] == ['sam', 'neil']
    assert payload['players'][0]['elo_rating'] == 1110


def test_admin_diagnostics_requires_admin(flask_app, monkeypatch):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: False)

    response = client.get('/api/admin/diagnostics', headers={
        'Authorization': f'Bearer {token}'
    })

    assert response.status_code == 403
