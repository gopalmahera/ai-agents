import importlib
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

_prom_stub = types.ModuleType("prometheus_client")
_prom_stub.Counter = MagicMock(return_value=MagicMock())
_prom_stub.generate_latest = MagicMock(return_value=b"")
_prom_stub.CONTENT_TYPE_LATEST = "text/plain"
sys.modules.setdefault("prometheus_client", _prom_stub)

_metrics_stub = types.ModuleType("metrics")
for _name in (
    "alerts_received",
    "alerts_deduplicated",
    "alerts_skipped",
    "alerts_silenced",
    "alerts_accepted",
    "llm_investigations",
    "slack_posts",
):
    setattr(_metrics_stub, _name, MagicMock())
sys.modules.setdefault("utils.metrics", _metrics_stub)

sys.modules.pop("controllers.webhook_controller", None)
import controllers.webhook_controller as webhook_module  # noqa: E402
importlib.reload(webhook_module)

SAMPLE_ALERT = {
    "status": "firing",
    "fingerprint": "test-fp",
    "labels": {"alertname": "PodRestart", "namespace": "default", "pod": "my-pod"},
}


class TestWebhookTestEndpoint(unittest.TestCase):
    def setUp(self):
        self.app = webhook_module.create_app()
        self.client = self.app.test_client()

    @patch.object(webhook_module, "investigate_alert")
    def test_accepts_single_alert_object(self, mock_investigate):
        mock_investigate.return_value = {
            "alertname": "PodRestart",
            "header": "Header",
            "body": "Body",
            "report": "Header\n\nBody",
            "log_file": "/tmp/rca.log",
        }
        response = self.client.post("/webhook/test", json=SAMPLE_ALERT)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["body"], "Body")
        mock_investigate.assert_called_once()
        self.assertTrue(mock_investigate.call_args.kwargs.get("skip_slack"))

    @patch.object(webhook_module, "investigate_alert")
    def test_accepts_webhook_payload(self, mock_investigate):
        mock_investigate.return_value = {
            "alertname": "PodRestart",
            "header": "Header",
            "body": "Body",
            "report": "Header\n\nBody",
            "log_file": "/tmp/rca.log",
        }
        payload = {"status": "firing", "alerts": [SAMPLE_ALERT]}
        response = self.client.post("/webhook/test", json=payload)
        self.assertEqual(response.status_code, 200)
        mock_investigate.assert_called_once()

    def test_rejects_invalid_payload(self):
        response = self.client.post("/webhook/test", json={"status": "firing"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
