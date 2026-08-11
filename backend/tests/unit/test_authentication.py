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
    @patch('app.decode_token')
    def test_handle_connect_valid_token(self, mock_decode_token, mock_join_room, mock_emit):
        mock_decode_token.return_value = {'sub': 'testuser'}
        
        # Use test request context and modify its attributes
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            context.request.args = {'auth': '{"token": "valid_token", "username": "testuser"}'}
            
            result = handle_connect(None)
            self.assertTrue(result)
            mock_decode_token.assert_called_once_with('valid_token')

    @patch('app.emit')
    @patch('app.join_room')
    @patch('app.decode_token')
    def test_handle_connect_invalid_token(self, mock_decode_token, mock_join_room, mock_emit):
        mock_decode_token.side_effect = Exception('Invalid token')
        
        # Use the test request context and modify its attributes
        with self.app.test_request_context() as context:
            # Set request attributes
            context.request.sid = 'test_sid'
            context.request.args = {'auth': '{"token": "invalid_token", "username": "testuser"}'}
            
            result = handle_connect(None)
            self.assertFalse(result)
