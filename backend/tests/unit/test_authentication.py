import unittest
from unittest.mock import patch, MagicMock
from app import app, socketio, handle_connect
from flask import request

class TestAuthentication(unittest.TestCase):
    def setUp(self):
        self.app = app
        # Create a SocketIO test client
        self.client = socketio.test_client(app)
        self.app_context = self.app.app_context()
        self.app_context.push()

    def tearDown(self):
        self.app_context.pop()
        self.client.disconnect()

    @patch('app.emit')
    @patch('app.join_room')
    @patch('app.verify_jwt_in_request')
    def test_handle_connect_valid_token(self, mock_verify, mock_join_room, mock_emit):
        mock_verify.return_value = True
        
        # Use test request context and modify its attributes
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            context.request.args = {'auth': '{"token": "valid_token", "username": "testuser"}'}
            
            # Mock get_jwt_identity
            with patch('app.get_jwt_identity', return_value='testuser'):
                result = handle_connect(None)
                self.assertTrue(result)

    @patch('app.emit')
    @patch('app.join_room')
    @patch('app.verify_jwt_in_request')
    def test_handle_connect_invalid_token(self, mock_verify, mock_join_room, mock_emit):
        mock_verify.side_effect = Exception('Invalid token')
        
        # Use the test request context and modify its attributes
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            context.request.args = {'auth': '{"token": "invalid_token", "username": "testuser"}'}
            
            result = handle_connect(None)
            self.assertFalse(result)
