import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

from services.classification.alert_classifier import AlertContext, build_alert_context
from services.metrics.kafka_metrics import prefetch_kafka_metrics


def _vitalsstream_alert() -> dict:
    return {
        "status": "firing",
        "labels": {
            "alertname": "pod.restart.vitalsstream",
            "severity": "critical",
            "namespace": "msk",
            "job": "msk-kb",
            "topic": "wss.vitalsstream",
            "groupId": "group.wss.vitalsstream",
            "region": "ap-south-1",
        },
        "annotations": {
            "description": "Consumer Lag on group.wss.vitalsstream > 1000",
        },
    }


class TestKafkaMetrics(unittest.TestCase):
    @patch("services.metrics.kafka_metrics._fetch_consumer_lag")
    @patch("services.metrics.kafka_metrics._fetch_topic_message_rate")
    def test_prefetch_builds_lag_and_rate_bullets(self, mock_rate, mock_lag):
        mock_lag.return_value = 2718.0
        mock_rate.return_value = 16730.0
        alert = _vitalsstream_alert()
        ctx = build_alert_context(alert)
        result = prefetch_kafka_metrics(ctx, alert)
        self.assertIsNotNone(result)
        self.assertTrue(any("2718" in b for b in result["bullets"]))
        self.assertTrue(any("16730" in b for b in result["bullets"]))
        self.assertTrue(result["findings"])


if __name__ == "__main__":
    unittest.main()
