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

    @patch.object(webhook_controller, "log_incoming_payload")
    @patch.object(webhook_controller, "_redis")
    @patch.object(webhook_controller, "_get_executor")
    @patch.object(webhook_controller, "_get_slots")
    def test_queue_full_rejects_and_records(self, mock_slots, mock_executor, mock_redis, _mock_log):
        mock_redis.dedup_check_and_set.return_value = False
        mock_slots.return_value.acquire.return_value = False  # queue at capacity
        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["accepted"], 0)
        mock_executor.return_value.submit.assert_not_called()
        mock_redis.counter_inc.assert_any_call("queue_full")

    def test_webhook_test_requires_auth_when_token_set(self):
        with patch.object(webhook_controller._cfg, "ADMIN_TOKEN", "secret"), \
             patch.object(webhook_controller, "investigate_alert") as mock_investigate:
            response = self.client.post("/webhook/test", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 401)
        mock_investigate.assert_not_called()

    @patch.object(webhook_controller, "log_incoming_payload")
    @patch.object(webhook_controller, "_redis")
    @patch.object(webhook_controller, "_get_executor")
    def test_webhook_env_threads_environment(self, mock_executor, mock_redis, _mock_log):
        mock_redis.dedup_check_and_set.return_value = False
        mock_executor.return_value = MagicMock()
        response = self.client.post("/webhook/prod", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        submit = mock_executor.return_value.submit
        submit.assert_called_once()
        # submit(_investigate_in_background, alert, env) — env threaded from the path.
        self.assertEqual(submit.call_args.args[2], "prod")

    def test_webhook_test_not_shadowed_by_env_route(self):
        # POST /webhook/test hits the (auth-gated) test route, not /webhook/<env>.
        with patch.object(webhook_controller, "investigate_alert", return_value={"rca": "x"}) as mock_inv:
            response = self.client.post("/webhook/test", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        mock_inv.assert_called_once()
        self.assertNotEqual(mock_inv.call_args.kwargs.get("env"), "test")


if __name__ == "__main__":
    unittest.main()
