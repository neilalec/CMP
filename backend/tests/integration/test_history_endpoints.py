from flask_jwt_extended import create_access_token

import app as backend_app


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


def test_admin_diagnostics_requires_admin(flask_app, monkeypatch):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: False)

    response = client.get('/api/admin/diagnostics', headers={
        'Authorization': f'Bearer {token}'
    })

    assert response.status_code == 403
