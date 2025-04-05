import pytest
from app import SOCKET_EVENTS
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

def test_socket_register(socket_client):
    """Test register via socket"""
    response = socket_client.emit(SOCKET_EVENTS['AUTH']['REGISTER'], {
        'username': 'testregister',  # Can use fixed name since test_users gives clean state
        'password': 'newpass'
    }, callback=True)
    
    assert response['success'] is True
    assert 'access_token' in response

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