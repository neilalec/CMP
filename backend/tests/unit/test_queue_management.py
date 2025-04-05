import unittest
from unittest.mock import patch, MagicMock
from app import update_queue_state, handle_join_queue, app, socketio
from flask_socketio import emit
import pytest

class TestQueueManagement(unittest.TestCase):
    def setUp(self):
        self.app = app
        # Create a SocketIO test client
        self.client = socketio.test_client(app)
        self.app_context = self.app.app_context()
        self.app_context.push()
        # Mock socketio.emit to prevent actual broadcasts
        self.socketio_mock = patch('app.socketio.emit').start()
        # Mock emit function for direct responses
        self.emit_mock = patch('app.emit').start()
        self.queue_lock_mock = patch('app.queue_lock').start()

    def tearDown(self):
        self.app_context.pop()
        self.client.disconnect()
        patch.stopall()

    def test_update_queue_state(self):
        with patch('builtins.open', MagicMock()):
            update_queue_state(save=True, broadcast=True)
            self.socketio_mock.assert_called_once()

    @patch('app.save_queue')
    @patch('app.check_queue_and_start_countdown')
    def test_handle_join_queue_duplicate_user(self, mock_countdown, mock_save):
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            
            with patch('app.matchmaking_queue', ['existing_user']):
                handle_join_queue({'username': 'existing_user'})
                
                # Verify the failure response was emitted
                self.emit_mock.assert_called_with(
                    'join-queue_response',
                    {
                        'success': False,
                        'message': 'Already in queue'
                    }
                )
                # Verify queue wasn't modified
                mock_save.assert_not_called()
                mock_countdown.assert_not_called()

    @patch('app.save_queue')
    @patch('app.check_queue_and_start_countdown')
    def test_handle_join_queue_success(self, mock_countdown, mock_save):
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            
            with patch('app.matchmaking_queue', []), \
                 patch('app.player_activity', {}):
                
                handle_join_queue({'username': 'new_user'})
                
                # Verify broadcast was sent
                self.socketio_mock.assert_called_with(
                    'queue_update',
                    {
                        'playersInQueue': 1,
                        'queue': ['new_user']
                    }
                )
                
                # Verify success response was emitted
                self.emit_mock.assert_called_with(
                    'join-queue_response',
                    {
                        'success': True,
                        'inQueue': True,
                        'playersInQueue': 1,
                        'queue': ['new_user']
                    }
                )
                
                # Verify other functions were called
                mock_save.assert_called_once()
                mock_countdown.assert_called_once()

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