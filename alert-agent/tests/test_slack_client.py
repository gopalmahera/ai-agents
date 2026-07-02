import unittest
from unittest.mock import MagicMock, patch

from services.notification.slack_client import format_alert_status, format_status_for_alert, send_alert_report, send_alert_status


FIRING_PAYLOAD = {
    "status": "firing",
    "commonLabels": {"alertname": "PODCPULimitsUage>=90", "severity": "critical"},
    "alerts": [
        {"status": "firing", "labels": {"alertname": "PODCPULimitsUage>=90"}},
    ],
}

RESOLVED_PAYLOAD = {
    "status": "resolved",
    "commonLabels": {"alertname": "PODCPULimitsUage>=90", "severity": "critical"},
    "alerts": [
        {"status": "resolved", "labels": {"alertname": "PODCPULimitsUage>=90"}},
    ],
}


class TestSlackClient(unittest.TestCase):
    def test_firing_status_format(self):
        self.assertEqual(
            format_alert_status(FIRING_PAYLOAD),
            "[FIRING:1] PODCPULimitsUage>=90",
        )

    def test_resolved_status_format(self):
        self.assertEqual(
            format_alert_status(RESOLVED_PAYLOAD),
            "[RESOLVED] PODCPULimitsUage>=90",
        )

    def test_firing_count_multiple_alerts(self):
        payload = {
            "status": "firing",
            "commonLabels": {"alertname": "PODCPULimitsUage>=90"},
            "alerts": [
                {"status": "firing"},
                {"status": "firing"},
            ],
        }
        self.assertEqual(format_alert_status(payload), "[FIRING:2] PODCPULimitsUage>=90")

    def test_status_for_single_alert(self):
        alert = {
            "status": "firing",
            "labels": {"alertname": "pod.restart.vitalsstream", "severity": "critical"},
        }
        self.assertEqual(
            format_status_for_alert(alert),
            "[FIRING:1] pod.restart.vitalsstream",
        )

    @patch("services.notification.slack_client.requests.post")
    @patch("services.notification.slack_client.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_send_status_only(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        send_alert_status(FIRING_PAYLOAD)
        payload = mock_post.call_args.kwargs["json"]
        text = payload["attachments"][0]["text"]
        self.assertEqual(text, "[FIRING:1] PODCPULimitsUage>=90")
        self.assertNotIn("RCA", text)
        self.assertNotIn("Region:", text)
        self.assertNotIn("Alertname", text)

    @patch("services.notification.slack_client.requests.post")
    @patch("services.notification.slack_client.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_send_full_report(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        alert = {
            "status": "firing",
            "labels": {
                "alertname": "pod.restart.vitalsstream",
                "severity": "critical",
            },
        }
        header = ":rotating_light: *pod.restart.vitalsstream* | severity: critical"
        body = "*Findings:*\n• lag high"
        send_alert_report(alert, header, body)
        attachments = mock_post.call_args.kwargs["json"]["attachments"]
        # Header attachment is first (colored)
        self.assertIn("pod.restart.vitalsstream", attachments[0]["text"])
        self.assertEqual(attachments[0]["color"], "#E01E5A")
        # Body is in second attachment
        self.assertIn("*Findings:*", attachments[1]["text"])
        self.assertNotIn("[FIRING:1]", attachments[0]["text"])

    @patch("services.notification.slack_client.requests.post")
    @patch("services.notification.slack_client.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_body_truncated_when_too_long(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        alert = {"labels": {"alertname": "TestAlert", "severity": "warning"}}
        long_body = "x" * 5000
        send_alert_report(alert, "header", long_body)
        body_text = mock_post.call_args.kwargs["json"]["attachments"][1]["text"]
        self.assertLessEqual(len(body_text), 4000)
        self.assertIn("truncated", body_text)


if __name__ == "__main__":
    unittest.main()
