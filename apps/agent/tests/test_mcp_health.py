import unittest
from unittest.mock import patch, MagicMock

from controllers.webhook_controller import create_app


class TestInternalHealth(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.client = self.app.test_client()

    @patch("controllers.webhook_controller.requests.get")
    def test_internal_mcp_health_route(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp
        r = self.client.get("/internal/mcp/health")
        self.assertEqual(r.status_code, 200)
        body = r.get_json()
        self.assertIn("K8S_MCP_URL", body)

    @patch("controllers.webhook_controller.requests.get")
    def test_internal_services_health_route(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp
        r = self.client.get("/internal/services/health")
        self.assertEqual(r.status_code, 200)
        self.assertIn("PROMETHEUS_URL", r.get_json())


if __name__ == "__main__":
    unittest.main()
