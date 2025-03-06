import pytest
from app import app, socketio
from flask_jwt_extended import create_access_token

@pytest.fixture(scope='function')
def flask_app():
    app.config.update({
        'TESTING': True,
        'JWT_SECRET_KEY': 'test-secret',
        'SECRET_KEY': 'test-secret'
    })
    return app

@pytest.fixture(scope='function')
def socket_client(flask_app):
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