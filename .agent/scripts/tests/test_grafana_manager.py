import unittest
from unittest.mock import patch, MagicMock
import json
import os
import sys

# Add parent directory to path to import grafana_manager
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from grafana_manager import GrafanaManager

class TestGrafanaManager(unittest.TestCase):
    def setUp(self):
        self.host = "http://grafana.example.com"
        self.token = "test-token"
        self.manager = GrafanaManager(host=self.host, token=self.token)

    @patch('requests.request')
    def test_get_dashboard(self, mock_request):
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"dashboard": {"title": "Test DB"}, "meta": {}}
        mock_request.return_value = mock_response

        result = self.manager.get_dashboard("test-uid")

        mock_request.assert_called_once_with(
            "GET",
            f"{self.host}/api/dashboards/uid/test-uid",
            headers=self.manager.headers,
            json=None,
            timeout=10
        )
        self.assertEqual(result["dashboard"]["title"], "Test DB")

    @patch('requests.request')
    def test_create_dashboard(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "uid": "new-uid"}
        mock_request.return_value = mock_response

        db_json = {"title": "New Dashboard", "panels": []}
        result = self.manager.create_dashboard(db_json)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["uid"], "new-uid")

    @patch('requests.request')
    def test_explore_prometheus(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "success", "data": ["metric_1", "metric_2"]}
        mock_request.return_value = mock_response

        result = self.manager.query_prometheus_labels(datasource_id=1, label="__name__")

        mock_request.assert_called_with(
            "GET",
            f"{self.host}/api/datasources/proxy/1/api/v1/label/__name__/values",
            headers=self.manager.headers,
            json=None,
            timeout=10
        )
        self.assertIn("metric_1", result["data"])

    @patch('requests.request')
    def test_get_alert_rules(self, mock_request):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{"id": 1, "name": "High CPU"}]
        mock_request.return_value = mock_response

        result = self.manager.get_alert_rules()
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "High CPU")

    def test_initialization_from_env(self):
        with patch.dict(os.environ, {"GRAFANA_HOST": "http://env-host", "GRAFANA_TOKEN": "env-token"}):
            env_manager = GrafanaManager()
            self.assertEqual(env_manager.host, "http://env-host")
            self.assertEqual(env_manager.headers["Authorization"], "Bearer env-token")

if __name__ == '__main__':
    unittest.main()
