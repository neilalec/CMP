import unittest
from unittest.mock import patch
from app import handle_connect

class TestAuthentication(unittest.TestCase):
    @patch('app.verify_jwt_in_request')
    def test_handle_connect_valid_token(self, mock_verify):
        mock_verify.return_value = True
        result = handle_connect({
            'token': 'valid_token',
            'username': 'testuser'
        })
        self.assertTrue(result)

    @patch('app.verify_jwt_in_request')
    def test_handle_connect_invalid_token(self, mock_verify):
        mock_verify.side_effect = Exception('Invalid token')
        result = handle_connect({
            'token': 'invalid_token',
            'username': 'testuser'
        })
        self.assertFalse(result)