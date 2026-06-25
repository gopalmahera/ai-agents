import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

from alert_context import AlertContext
from pod_metrics import (
    _build_cpu_bullets,
    _build_memory_bullets,
    _format_pct_windows,
    build_findings_bullets,
    prefetch_pod_metrics,
)


def _cpu_ctx() -> AlertContext:
    return AlertContext(
        alertname="PODCPULimitsUage>=90",
        resource_type="kubernetes",
        namespace="dozeeplatform",
        pod="consumer-abc-123",
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


class TestPodMetricsBullets(unittest.TestCase):
    def test_pct_windows_format(self):
        line = _format_pct_windows({"1m": 94.2, "5m": 90.8, "15m": 88.1})
        self.assertIn("94.2% (1m avg)", line)
        self.assertIn("90.8% (5m avg)", line)
        self.assertIn("15m avg", line)

    def test_cpu_bullets_multi_window(self):
        snapshot = {
            "usage_percent_by_window": {"1m": 94.2, "5m": 90.8, "15m": 88.1},
            "limit_cores": 0.2,
            "restarts": 0,
            "resource": "cpu",
        }
        bullets = _build_cpu_bullets(_cpu_ctx(), snapshot)
        self.assertTrue(any("1m avg" in b and "5m avg" in b for b in bullets))
        self.assertTrue(any("CPU limit" in b for b in bullets))

    def test_memory_bullets_multi_window(self):
        ctx = AlertContext(**{**_cpu_ctx().__dict__, "alertname": "PODMemoryLimitsUage>=90"})
        snapshot = {
            "usage_percent_by_window": {"1m": 91.5, "5m": 90.2, "15m": 89.0},
            "usage_bytes": 900 * 1024**2,
            "limit_bytes": 1 * 1024**3,
            "restarts": 0,
            "resource": "memory",
        }
        bullets = _build_memory_bullets(ctx, snapshot)
        self.assertTrue(any("Memory usage % of limit" in b for b in bullets))
        self.assertTrue(any("MiB" in b for b in bullets))

    def test_findings_image_change_on_recent_rollout(self):
        prefetched = {
            "snapshot": {"resource": "cpu", "usage_percent": 92.0, "restarts": 0},
            "workload": {
                "rollout": {
                    "rollout_age_seconds": 900,
                    "rollout_age_human": "15m",
                    "image_changed": True,
                }
            },
        }
        findings = build_findings_bullets(_cpu_ctx(), prefetched)
        self.assertTrue(any("new image" in f for f in findings))

    @patch("pod_metrics._fetch_pod_cpu_snapshot")
    def test_prefetch_cpu(self, mock_fetch):
        mock_fetch.return_value = {
            "usage_percent_by_window": {"1m": 95.0, "5m": 90.8, "15m": 88.0},
            "usage_percent": 90.8,
            "limit_cores": 0.2,
            "restarts": 0,
            "resource": "cpu",
        }
        result = prefetch_pod_metrics(_cpu_ctx(), {"labels": {}})
        self.assertTrue(result["alert_valid"])
        self.assertTrue(any("1m avg" in b for b in result["bullets"]))


if __name__ == "__main__":
    unittest.main()
