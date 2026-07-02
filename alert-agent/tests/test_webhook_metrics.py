import importlib
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

sys.modules.pop("controllers.webhook_controller", None)
import controllers.webhook_controller as webhook_module  # noqa: E402
importlib.reload(webhook_module)


FIRING_WEBHOOK = {
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "fingerprint": "fp-metrics-1",
            "labels": {"alertname": "PodRestart", "namespace": "default"},
        }
    ],
}


class TestWebhookMetrics(unittest.TestCase):
    def setUp(self):
        self.app = webhook_module.create_app()
        self.client = self.app.test_client()

    @patch.object(webhook_module, "alerts_accepted")
    @patch.object(webhook_module, "alerts_received")
    @patch.object(webhook_module, "log_incoming_payload")
    @patch.object(webhook_module, "_redis")
    @patch.object(webhook_module, "threading")
    def test_accepted_alert_increments_prometheus_counters(
        self, mock_threading, mock_redis, _mock_log, mock_received, mock_accepted
    ):
        mock_redis.dedup_check_and_set.return_value = False
        mock_threading.Thread.return_value = MagicMock(start=MagicMock())
        label_counter = MagicMock()
        mock_received.labels.return_value = label_counter

        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)

        mock_received.labels.assert_called_once_with(alertname="PodRestart")
        label_counter.inc.assert_called_once()
        mock_accepted.inc.assert_called_once()

    @patch.object(webhook_module, "alerts_deduplicated")
    @patch.object(webhook_module, "log_incoming_payload")
    @patch.object(webhook_module, "_redis")
    @patch.object(webhook_module, "threading")
    def test_duplicate_alert_increments_deduplicated_counter(
        self, mock_threading, mock_redis, _mock_log, mock_deduplicated
    ):
        mock_redis.dedup_check_and_set.return_value = True

        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["accepted"], 0)
        mock_threading.Thread.assert_not_called()
        mock_deduplicated.inc.assert_called_once()


if __name__ == "__main__":
    unittest.main()
