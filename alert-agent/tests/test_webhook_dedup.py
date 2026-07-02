import re
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
            "fingerprint": "fp-allow-1",
            "labels": {"alertname": "PodRestart", "namespace": "default"},
        }
    ],
}

FILTERED_WEBHOOK = {
    "status": "firing",
    "alerts": [
        {
            "status": "firing",
            "fingerprint": "fp-filtered-1",
            "labels": {"alertname": "UnknownAlert", "namespace": "default"},
        }
    ],
}


class TestWebhookDedupAndAllowlist(unittest.TestCase):
    def setUp(self):
        self.app = webhook_module.create_app()
        self.client = self.app.test_client()

    @patch.object(webhook_module, "log_incoming_payload")
    @patch.object(webhook_module, "_redis")
    @patch.object(webhook_module, "_get_executor")
    @patch.object(webhook_module._cfg, "_allowed_alertname_pattern", re.compile(r"^Pod"))
    def test_allowlist_skips_non_matching_alertname(self, mock_executor, mock_redis, _mock_log):
        mock_redis.dedup_check_and_set.return_value = False
        mock_executor.return_value = MagicMock()

        response = self.client.post("/webhook", json=FILTERED_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["accepted"], 0)
        mock_executor.return_value.submit.assert_not_called()

    @patch.object(webhook_module, "log_incoming_payload")
    @patch.object(webhook_module, "_redis")
    @patch.object(webhook_module, "_get_executor")
    def test_duplicate_fingerprint_is_skipped(self, mock_executor, mock_redis, _mock_log):
        mock_redis.dedup_check_and_set.return_value = True
        response = self.client.post("/webhook", json=FIRING_WEBHOOK)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["accepted"], 0)
        mock_executor.return_value.submit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
