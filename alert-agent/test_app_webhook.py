import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

agent_stub = types.ModuleType("agent")
agent_stub.investigate_alert = MagicMock()
sys.modules["agent"] = agent_stub


def _install_flask_stub() -> None:
    if "flask" in sys.modules:
        return

    flask_mod = types.ModuleType("flask")

    class Flask:
        def __init__(self, name):
            self.name = name
            self.view_functions = {}

        def get(self, rule, **kwargs):
            def decorator(fn):
                self.view_functions[("GET", rule)] = fn
                return fn

            return decorator

        def post(self, rule, **kwargs):
            def decorator(fn):
                self.view_functions[("POST", rule)] = fn
                return fn

            return decorator

        def test_client(self):
            return _TestClient(self)

    class _TestClient:
        def __init__(self, flask_app):
            self.flask_app = flask_app

        def post(self, path, json=None):
            handler = self.flask_app.view_functions.get(("POST", path))
            if handler is None:
                raise ValueError(f"No handler for POST {path}")

            request = MagicMock()
            request.get_json.return_value = json
            with patch("app.request", request):
                response = handler()
            return _Response(response)

    class _Response:
        def __init__(self, payload):
            self._payload = payload
            self.status_code = payload[1] if isinstance(payload, tuple) else 200

        def get_json(self):
            data = self._payload[0] if isinstance(self._payload, tuple) else self._payload
            return data.get_json()

    def jsonify(data):
        result = MagicMock()
        result.get_json.return_value = data
        return result

    flask_mod.Flask = Flask
    flask_mod.jsonify = jsonify
    flask_mod.request = MagicMock()
    sys.modules["flask"] = flask_mod


_install_flask_stub()

from app import app  # noqa: E402


FIRING_WEBHOOK = {
    "status": "firing",
    "commonLabels": {"alertname": "PODCPULimitsUage>=90", "severity": "critical"},
    "alerts": [
        {
            "status": "firing",
            "fingerprint": "abc123",
            "labels": {
                "alertname": "PODCPULimitsUage>=90",
                "namespace": "dozeeplatform",
                "pod": "consumer-abc",
                "container": "consumer",
            },
        }
    ],
}

RESOLVED_WEBHOOK = {
    "status": "resolved",
    "commonLabels": {"alertname": "PODCPULimitsUage>=90"},
    "alerts": [
        {
            "status": "resolved",
            "fingerprint": "abc123",
            "labels": {"alertname": "PODCPULimitsUage>=90"},
        }
    ],
}


class TestAppWebhook(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch("app.send_alert_status")
    @patch("app.threading.Thread")
    def test_firing_sends_status_and_starts_investigation(self, mock_thread, mock_slack):
        mock_thread.return_value = MagicMock(start=MagicMock())
        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        mock_slack.assert_called_once()
        mock_thread.assert_called_once()

    @patch("app.send_alert_status")
    @patch("app.threading.Thread")
    def test_resolved_sends_status_only(self, mock_thread, mock_slack):
        response = self.client.post("/webhook", json=RESOLVED_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        mock_slack.assert_called_once()
        mock_thread.assert_not_called()
        self.assertEqual(response.get_json()["accepted"], 0)


if __name__ == "__main__":
    unittest.main()
