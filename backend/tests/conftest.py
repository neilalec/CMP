import os
from pathlib import Path

import pytest
import app as backend_app
import app_core
from app import app, socketio, users
from flask_jwt_extended import create_access_token
import json

@pytest.fixture(scope='session')
def flask_app():
    app.config.update({
        'TESTING': True,
        'JWT_SECRET_KEY': 'test-secret-key-with-32-bytes-minimum',
        'SECRET_KEY': 'test-secret-key-with-32-bytes-minimum',
        'USERS_FILE': 'test_users.json'
    })
    return app


@pytest.fixture(scope='function', autouse=True)
def isolated_test_database(tmp_path, monkeypatch):
    database_path = tmp_path / 'test_app.db'
    monkeypatch.setattr(app_core, 'DATABASE_PATH', str(database_path))
    monkeypatch.setattr(backend_app, 'DATABASE_PATH', str(database_path))
    app_core.init_database()

    yield database_path

@pytest.fixture(scope='function')
def test_users():
    """Fixture to manage test users"""
    # Setup test users file
    test_users = {
        'neil': '123'  # Persistent test user
    }
    with open('test_users.json', 'w') as f:
        json.dump(test_users, f)
    
    # Configure app to use test file
    app.config['USERS_FILE'] = 'test_users.json'
    users.clear()
    users.update(test_users)
    
    yield users
    
    # Cleanup
    users.clear()
    if os.path.exists('test_users.json'):
        os.remove('test_users.json')

@pytest.fixture(scope='function')
def socket_client(flask_app, test_users):
    return socketio.test_client(app)

@pytest.fixture(scope='function')
def auth_token(flask_app):
    with flask_app.app_context():
        return create_access_token(identity='testuser')

@pytest.fixture(scope='function')
def authenticated_socket_client(socket_client, auth_token):
    """Returns a socket client that's already authenticated"""
    socket_client.emit('authenticate', {
        'token': auth_token,
        'username': 'testuser'
    })
    received = socket_client.get_received()
    if not any(msg.get('name') == 'authentication_success' for msg in received):
        pytest.fail("Authentication failed")
    return socket_client 
