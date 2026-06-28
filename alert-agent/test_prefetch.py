import unittest
from unittest.mock import patch, MagicMock

from alert_context import AlertContext


def _k8s_ctx(**kwargs) -> AlertContext:
    defaults = dict(
        alertname="PodRestart",
        resource_type="kubernetes",
        namespace="default",
        pod="my-pod-abc123",
        container="app",
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
        region=None,
        cloud=None,
        stage=None,
    )
    defaults.update(kwargs)
    return AlertContext(**defaults)


FIRING_ALERT = {
    "status": "firing",
    "labels": {"alertname": "PodRestart", "namespace": "default", "pod": "my-pod-abc123"},
    "annotations": {},
}


class TestBuildPrefetch(unittest.TestCase):
    @patch("prefetch.prefetch_workload_context", return_value=None)
    @patch("prefetch.prefetch_kafka_context", return_value=None)
    @patch("prefetch.prefetch_kafka_metrics", return_value=None)
    @patch("prefetch.prefetch_pod_metrics", return_value=None)
    @patch("prefetch.prefetch_host_metrics", return_value=None)
    def test_returns_none_when_no_data(
        self, mock_host, mock_pod, mock_kafka, mock_kafka_ctx, mock_workload
    ):
        from prefetch import build_prefetch

        ctx = _k8s_ctx()
        result = build_prefetch(ctx, FIRING_ALERT)
        self.assertIsNone(result)

    @patch("prefetch.prefetch_workload_context", return_value=None)
    @patch("prefetch.prefetch_kafka_context", return_value=None)
    @patch("prefetch.prefetch_kafka_metrics", return_value=None)
    @patch(
        "prefetch.prefetch_pod_metrics",
        return_value={
            "bullets": ["restart_count: 3"],
            "findings": [],
            "snapshot": {"resource": "cpu"},
            "alert_valid": True,
        },
    )
    @patch("prefetch.prefetch_host_metrics", return_value=None)
    def test_returns_pod_metrics_when_present(
        self, mock_host, mock_pod, mock_kafka, mock_kafka_ctx, mock_workload
    ):
        from prefetch import build_prefetch

        ctx = _k8s_ctx()
        result = build_prefetch(ctx, FIRING_ALERT)
        self.assertIsNotNone(result)
        self.assertIn("restart_count: 3", result["bullets"])

    @patch("prefetch.prefetch_workload_context", return_value={"alert_meaning": "Consumer lag high", "bullets": ["lag: 5000"]})
    @patch("prefetch.prefetch_kafka_context", return_value=None)
    @patch("prefetch.prefetch_kafka_metrics", return_value=None)
    @patch("prefetch.prefetch_pod_metrics", return_value=None)
    @patch("prefetch.prefetch_host_metrics", return_value=None)
    def test_workload_context_merged(
        self, mock_host, mock_pod, mock_kafka, mock_kafka_ctx, mock_workload
    ):
        from prefetch import build_prefetch

        ctx = _k8s_ctx()
        result = build_prefetch(ctx, FIRING_ALERT)
        self.assertIsNotNone(result)
        self.assertEqual(result.get("alert_meaning"), "Consumer lag high")


if __name__ == "__main__":
    unittest.main()
