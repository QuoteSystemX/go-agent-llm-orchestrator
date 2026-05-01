import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.resilience import ResilientSession

class TestResilienceLibrary(unittest.TestCase):
    def setUp(self):
        self.host = "http://test.local"
        self.session = ResilientSession(host=self.host)

    @patch('requests.request')
    def test_direct_success(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_request.return_value = mock_response

        result = self.session.request("GET", "/health")
        self.assertEqual(result["status"], "ok")
        mock_request.assert_called_with(
            "GET", "http://test.local/health", 
            headers=self.session.headers, json=None, auth=None, timeout=10
        )

    @patch('requests.request')
    @patch('subprocess.check_output')
    def test_dns_fallback(self, mock_subproc, mock_request):
        # 1. First call fails with ConnectionError
        # 2. Second call (retry) succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "resolved"}
        
        mock_request.side_effects = [
            Exception("Connection failed"), # This is tricky with mock, let's use side_effect
        ]
        
        import requests
        # Setup side effect for request
        def side_effect(method, url, **kwargs):
            if "test.local" in url and "Host" not in kwargs.get('headers', {}):
                raise requests.exceptions.ConnectionError("Connection failed")
            return mock_response
        
        mock_request.side_effect = side_effect
        
        # Mock gateway and nslookup
        mock_subproc.side_effect = [
            b"172.31.0.1\n",   # Gateway
            b"192.168.1.200\n" # Resolved IP
        ]

        result = self.session.request("GET", "/health")
        self.assertEqual(result["status"], "resolved")
        
        # Verify it retried with the IP and Host header
        last_call_args = mock_request.call_args
        self.assertIn("192.168.1.200", last_call_args[0][1])
        self.assertEqual(last_call_args[1]['headers']['Host'], "test.local")

if __name__ == '__main__':
    unittest.main()
