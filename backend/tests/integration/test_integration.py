import pytest
from app import app, socketio

@pytest.fixture
def socket_client():
    client = socketio.test_client(app)
    return client

def test_queue_workflow(socket_client):
    # Test complete queue workflow
    response = socket_client.emit('join-queue', {'username': 'testuser'})
    assert response['success'] == True
    
    # Verify queue update received
    received = socket_client.get_received()
    assert any(msg['name'] == 'queue_update' for msg in received)
    
    # Test leaving queue
    response = socket_client.emit('leave-queue', {'username': 'testuser'})
    assert response['success'] == True

def test_socket_connection(authenticated_socket_client):
    """Test basic socket connection"""
    assert authenticated_socket_client.is_connected()

def test_queue_join(authenticated_socket_client):
    """Test joining queue"""
    response = authenticated_socket_client.emit('join-queue', {
        'username': 'testuser'
    }, callback=True)
    assert response[0].get('success') is True

def test_queue_leave(authenticated_socket_client):
    """Test leaving queue"""
    # First join the queue
    authenticated_socket_client.emit('join-queue', {
        'username': 'testuser'
    })
    
    # Then test leaving
    response = authenticated_socket_client.emit('leave-queue', {
        'username': 'testuser'
    }, callback=True)
    assert response[0].get('success') is True

def test_queue_status(authenticated_socket_client):
    """Test queue status retrieval"""
    response = authenticated_socket_client.emit('queue_status', callback=True)
    assert isinstance(response[0], dict)
    assert 'queue' in response[0]