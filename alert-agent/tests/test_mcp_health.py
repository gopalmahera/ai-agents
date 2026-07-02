import unittest
from unittest.mock import MagicMock, patch

from api.config_api import _probe_http_service, _probe_mcp_server


class TestMcpHealth(unittest.TestCase):
    @patch("api.config_api.requests.get")
    def test_probe_treats_mcp_406_as_healthy(self, mock_get):
        resp = MagicMock()
        resp.status_code = 406
        mock_get.return_value = resp

        result = _probe_mcp_server("http://127.0.0.1:8001/mcp")

        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["code"], 406)
        mock_get.assert_called_once_with(
            "http://127.0.0.1:8001/mcp", timeout=3, stream=True
        )
        resp.close.assert_called_once()

    @patch("api.config_api.requests.get")
    def test_probe_appends_mcp_path_when_missing(self, mock_get):
        resp = MagicMock()
        resp.status_code = 406
        mock_get.return_value = resp

        _probe_mcp_server("http://127.0.0.1:8002")

        mock_get.assert_called_once_with(
            "http://127.0.0.1:8002/mcp", timeout=3, stream=True
        )

    @patch("api.config_api.requests.get", side_effect=ConnectionError("refused"))
    def test_probe_unreachable_on_connection_error(self, _mock_get):
        result = _probe_mcp_server("http://127.0.0.1:8003/mcp")

        self.assertEqual(result["status"], "unreachable")
        self.assertIn("refused", result["error"])


class TestServiceHealth(unittest.TestCase):
    @patch("api.config_api.requests.get")
    def test_loki_gateway_probe_falls_back_to_buildinfo(self, mock_get):
        not_found = MagicMock()
        not_found.status_code = 404
        buildinfo = MagicMock()
        buildinfo.status_code = 200
        mock_get.side_effect = [not_found, not_found, buildinfo]

        result = _probe_http_service(
            "http://loki-sit.dozee.int",
            ("/ready", "/loki/ready", "/loki/api/v1/status/buildinfo"),
        )

        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["probe"], "/loki/api/v1/status/buildinfo")
        self.assertEqual(mock_get.call_count, 3)

    @patch("api.config_api.requests.get")
    def test_loki_bare_ready_is_healthy(self, mock_get):
        resp = MagicMock()
        resp.status_code = 200
        mock_get.return_value = resp

        result = _probe_http_service(
            "http://localhost:3100",
            ("/ready", "/loki/ready", "/loki/api/v1/status/buildinfo"),
        )

        self.assertEqual(result["status"], "healthy")
        self.assertEqual(result["probe"], "/ready")
        mock_get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
