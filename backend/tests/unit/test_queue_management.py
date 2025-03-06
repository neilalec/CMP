import unittest
from unittest.mock import patch, MagicMock
from app import update_queue_state, handle_join_queue
import pytest
from app import app

class TestQueueManagement(unittest.TestCase):
    def setUp(self):
        self.socketio_mock = patch('app.socketio').start()
        self.queue_lock_mock = patch('app.queue_lock').start()

    def tearDown(self):
        patch.stopall()

    def test_update_queue_state(self):
        with patch('builtins.open', MagicMock()):
            update_queue_state(save=True, broadcast=True)
            self.socketio_mock.emit.assert_called_once()

    def test_handle_join_queue_duplicate_user(self):
        with patch('app.matchmaking_queue', ['existing_user']):
            result = handle_join_queue({'username': 'existing_user'})
            self.assertFalse(result['success'])

    @patch('app.broadcast_queue_update')
    def test_handle_join_queue_success(self, mock_broadcast):
        with patch('app.matchmaking_queue', []):
            result = handle_join_queue({'username': 'new_user'})
            self.assertTrue(result['success'])
            mock_broadcast.assert_called_once()

def test_queue_initialization(flask_app):
    """Test queue initialization"""
    with flask_app.app_context():
        from app import matchmaking_queue
        assert isinstance(matchmaking_queue, list)

def test_queue_operations(flask_app):
    """Test basic queue operations"""
    with flask_app.app_context():
        from app import matchmaking_queue
        
        # Test queue addition
        username = 'testuser'
        if username not in matchmaking_queue:
            matchmaking_queue.append(username)
        assert username in matchmaking_queue
        
        # Test queue removal
        if username in matchmaking_queue:
            matchmaking_queue.remove(username)
        assert username not in matchmaking_queue