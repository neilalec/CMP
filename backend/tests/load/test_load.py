import asyncio
import websockets
import time
import pytest
from app import app, socketio

async def connection_test(uri, num_connections):
    connections = []
    start_time = time.time()
    
    for i in range(num_connections):
        try:
            ws = await websockets.connect(uri)
            connections.append(ws)
        except Exception as e:
            print(f"Connection {i} failed: {e}")
    
    duration = time.time() - start_time
    print(f"Created {len(connections)} connections in {duration:.2f} seconds")
    return connections

def test_concurrent_connections():
    uri = "ws://localhost:5000"
    num_connections = 100
    connections = asyncio.run(connection_test(uri, num_connections))
    assert len(connections) == num_connections

@pytest.mark.asyncio
async def test_multiple_connections():
    """Test multiple simultaneous connections"""
    num_clients = 5
    clients = []
    
    # Create multiple test clients
    for _ in range(num_clients):
        client = socketio.test_client(app)
        clients.append(client)
    
    # Verify all clients are connected
    for client in clients:
        assert client.is_connected()
    
    # Clean up
    for client in clients:
        client.disconnect()

def test_rapid_queue_operations(authenticated_socket_client):
    """Test rapid queue join/leave operations"""
    operations = 10
    
    for _ in range(operations):
        # Join queue
        join_response = authenticated_socket_client.emit('join-queue', {
            'username': 'testuser'
        }, callback=True)
        assert join_response.get('success') is True
        
        # Leave queue
        leave_response = authenticated_socket_client.emit('leave-queue', {
            'username': 'testuser'
        }, callback=True)
        assert leave_response.get('success') is True