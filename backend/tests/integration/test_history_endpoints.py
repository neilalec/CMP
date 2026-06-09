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


def test_admin_diagnostics_requires_admin(flask_app, monkeypatch):
    client = flask_app.test_client()
    with flask_app.app_context():
        token = create_access_token(identity='neil')

    monkeypatch.setattr(backend_app, 'is_admin_user', lambda username: False)

    response = client.get('/api/admin/diagnostics', headers={
        'Authorization': f'Bearer {token}'
    })

    assert response.status_code == 403
