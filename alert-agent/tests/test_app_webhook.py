import re
import sys
import unittest
from unittest.mock import MagicMock, patch

import controllers.webhook_controller as webhook_controller

sys.modules.setdefault("requests", MagicMock())

from app import app  # noqa: E402


FIRING_WEBHOOK = {
    "status": "firing",
    "commonLabels": {"alertname": "PODCPULimitsUage>=90", "severity": "critical"},
    "alerts": [
        {
            "status": "firing",
            "fingerprint": "test-fp-firing-unique",
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
            "fingerprint": "test-fp-resolved-unique",
            "labels": {"alertname": "PODCPULimitsUage>=90"},
        }
    ],
}


class TestAppWebhook(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    @patch.object(webhook_controller, "log_incoming_payload")
    @patch.object(webhook_controller, "_redis")
    @patch.object(webhook_controller, "send_alert_status")
    @patch.object(webhook_controller, "_get_executor")
    def test_firing_does_not_send_status_starts_investigation(
        self, mock_executor, mock_slack, mock_redis, _mock_log
    ):
        mock_redis.dedup_check_and_set.return_value = False
        mock_executor.return_value = MagicMock()
        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        mock_slack.assert_not_called()
        mock_executor.return_value.submit.assert_called_once()

    @patch.object(webhook_controller, "log_incoming_payload")
    @patch.object(webhook_controller, "_redis")
    @patch.object(webhook_controller, "send_alert_status")
    @patch.object(webhook_controller, "_get_executor")
    def test_resolved_sends_status_only(self, mock_executor, mock_slack, mock_redis, _mock_log):
        response = self.client.post("/webhook", json=RESOLVED_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        mock_slack.assert_called_once()
        mock_executor.return_value.submit.assert_not_called()
        self.assertEqual(response.get_json()["accepted"], 0)


if __name__ == "__main__":
    unittest.main()
