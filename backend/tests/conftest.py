import pytest
from app import app, socketio, load_users, users
from flask_jwt_extended import create_access_token
import json
import os

@pytest.fixture(scope='session')
def flask_app():
    app.config.update({
        'TESTING': True,
        'JWT_SECRET_KEY': 'test-secret',
        'SECRET_KEY': 'test-secret',
        'USERS_FILE': 'test_users.json'
    })
    return app

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