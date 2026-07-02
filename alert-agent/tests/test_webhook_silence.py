import unittest
from unittest import mock

import controllers.webhook_controller as webhook_module


class TestWebhookSilence(unittest.TestCase):
    def setUp(self):
        webhook_module._executor = None

    @mock.patch.object(webhook_module, "_get_executor")
    @mock.patch.object(webhook_module._redis, "stream_add")
    @mock.patch.object(webhook_module._redis, "counter_inc")
    @mock.patch.object(webhook_module._redis, "alertname_inc")
    @mock.patch.object(webhook_module._silences, "is_silenced", return_value=(True, "sil-1"))
    @mock.patch.object(webhook_module, "_is_duplicate")
    @mock.patch.object(webhook_module, "_is_allowed_alertname", return_value=True)
    @mock.patch.object(webhook_module, "log_incoming_payload")
    def test_silenced_alert_not_accepted(
        self,
        _log,
        _allow,
        _dedup,
        _is_silenced,
        _alertname_inc,
        _counter_inc,
        _stream_add,
        mock_executor,
    ):
        app = webhook_module.create_app()
        client = app.test_client()
        payload = {
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {"alertname": "PodCrash", "severity": "critical"},
                    "fingerprint": "fp-silenced",
                }
            ],
        }
        resp = client.post("/webhook", json=payload)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["accepted"], 0)
        mock_executor.return_value.submit.assert_not_called()
        _dedup.assert_not_called()
        _counter_inc.assert_any_call("alerts_silenced")
        _stream_add.assert_called_once()
        self.assertEqual(_stream_add.call_args.kwargs.get("outcome"), "silenced")


if __name__ == "__main__":
    unittest.main()
