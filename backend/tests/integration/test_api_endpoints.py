import pytest
import app as backend_app
from app import SOCKET_EVENTS, users
from services.auth_security import is_password_hash
from services.rate_limit import reset_rate_limits
import time

def test_health_check(flask_app):
    """Test the root endpoint (only REST endpoint)"""
    client = flask_app.test_client()
    response = client.get('/')
    assert response.status_code == 200
    assert 'CMP SocketIO backend running' in response.data.decode()

def test_socket_login(socket_client):
    """Test login via socket"""
    response = socket_client.emit(SOCKET_EVENTS['AUTH']['LOGIN'], {
        'username': 'neil',
        'password': '123'
    }, callback=True)
    
    assert response['success'] is True
    assert 'access_token' in response
    assert is_password_hash(users['neil']['password'])
    assert users['neil']['password'] != '123'

def test_socket_register(socket_client):
    """Test register via socket"""
    response = socket_client.emit(SOCKET_EVENTS['AUTH']['REGISTER'], {
        'username': 'testregister',  # Can use fixed name since test_users gives clean state
        'password': 'newpass'
    }, callback=True)
    
    assert response['success'] is True
    assert 'access_token' in response
    assert is_password_hash(users['testregister']['password'])
    assert users['testregister']['password'] != 'newpass'

def test_socket_authenticate(socket_client, auth_token):
    """Test authentication with token"""
    response = socket_client.emit(SOCKET_EVENTS['AUTH']['AUTHENTICATE'], {
        'token': auth_token,
        'username': 'neil'
    }, callback=True)
    
    assert response is True

def test_invalid_login(socket_client):
    """Test login with invalid credentials"""
    response = socket_client.emit(SOCKET_EVENTS['AUTH']['LOGIN'], {
        'username': 'wronguser',
        'password': 'wrongpass'
    }, callback=True)
    
    assert response['success'] is False
    assert 'message' in response 


def test_password_login_disabled(socket_client, monkeypatch):
    monkeypatch.setattr(backend_app, 'PASSWORD_AUTH_ENABLED', False)

    response = socket_client.emit(SOCKET_EVENTS['AUTH']['LOGIN'], {
        'username': 'neil',
        'password': '123'
    }, callback=True)

    assert response['success'] is False
    assert response['message'] == 'Password login is disabled'


def test_password_registration_disabled(socket_client, monkeypatch):
    monkeypatch.setattr(backend_app, 'PASSWORD_AUTH_ENABLED', False)

    response = socket_client.emit(SOCKET_EVENTS['AUTH']['REGISTER'], {
        'username': 'newuser',
        'password': 'newpass'
    }, callback=True)

    assert response['success'] is False
    assert response['message'] == 'Password registration is disabled'


def test_socket_login_rate_limit(socket_client, monkeypatch):
    reset_rate_limits()
    monkeypatch.setattr(backend_app, 'AUTH_LOGIN_MAX_ATTEMPTS', 1)
    monkeypatch.setattr(backend_app, 'AUTH_RATE_LIMIT_WINDOW_SECONDS', 60)

    first = socket_client.emit(SOCKET_EVENTS['AUTH']['LOGIN'], {
        'username': 'neil',
        'password': 'wrongpass'
    }, callback=True)
    second = socket_client.emit(SOCKET_EVENTS['AUTH']['LOGIN'], {
        'username': 'neil',
        'password': 'wrongpass'
    }, callback=True)

    assert first['success'] is False
    assert first['message'] == 'Invalid credentials'
    assert second['success'] is False
    assert 'Too many attempts' in second['message']
    assert second['retry_after'] > 0
