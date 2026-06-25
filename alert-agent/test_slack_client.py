import unittest
from unittest.mock import MagicMock, patch

from slack_client import _attachment_color, _format_header, send_slack
from alert_context import AlertContext


def _k8s_ctx() -> AlertContext:
    return AlertContext(
        alertname="PODCPULimitsUage>=90",
        resource_type="kubernetes",
        namespace="dozeeplatform",
        pod="consumer-abc",
        container="consumer",
        instance=None,
        module=None,
        job=None,
        topic=None,
        group_id=None,
        host_ip=None,
        scrape_instance=None,
        target=None,
        msk_job=None,
        workload_namespace=None,
        workload_deployment=None,
        scrape_job=None,
        alert_firing_value=None,
        primary_metric=None,
        region="ap-south-1",
        cloud="aws",
        stage="prod",
    )


class TestSlackClient(unittest.TestCase):
    def test_header_includes_region(self):
        labels = {"severity": "critical", "region": "ap-south-1", "cloud": "aws", "stage": "prod"}
        header = _format_header(_k8s_ctx(), labels)
        self.assertIn("Region: ap-south-1", header)
        self.assertIn("Cloud: aws", header)
        self.assertIn("Stage: prod", header)
        self.assertIn("Namespace: dozeeplatform", header)

    def test_attachment_color_by_severity(self):
        self.assertEqual(_attachment_color({"severity": "critical"}), "#E01E5A")
        self.assertEqual(_attachment_color({"severity": "warning"}), "#ECB22E")
        self.assertEqual(_attachment_color({"severity": "info"}), "#36C5F0")

    @patch("slack_client.requests.post")
    @patch("slack_client.SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    def test_send_uses_colored_attachment(self, mock_post):
        mock_post.return_value = MagicMock(status_code=200, raise_for_status=MagicMock())
        alert = {
            "labels": {
                "alertname": "PODCPULimitsUage>=90",
                "severity": "critical",
                "namespace": "dozeeplatform",
                "pod": "consumer-abc",
                "region": "ap-south-1",
            }
        }
        send_slack("RCA body", alert=alert)
        payload = mock_post.call_args.kwargs["json"]
        self.assertIn("attachments", payload)
        self.assertEqual(payload["attachments"][0]["color"], "#E01E5A")
        self.assertIn("Region: ap-south-1", payload["attachments"][0]["text"])


if __name__ == "__main__":
    unittest.main()
