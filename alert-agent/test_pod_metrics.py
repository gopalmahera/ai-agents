import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

from alert_context import AlertContext
from pod_metrics import (
    _build_cpu_bullets,
    _build_memory_bullets,
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
    def test_cpu_bullets_format(self):
        snapshot = {
            "usage_percent": 92.0,
            "usage_cores": 0.181,
            "limit_cores": 0.2,
            "restarts": 0,
            "resource": "cpu",
        }
        bullets = _build_cpu_bullets(_cpu_ctx(), snapshot)
        self.assertTrue(any("92.0%" in b for b in bullets))
        self.assertTrue(any("0.181 cores" in b for b in bullets))
        self.assertTrue(any("CPU limit" in b for b in bullets))
        self.assertTrue(any("restarts: 0" in b.lower() for b in bullets))

    def test_memory_bullets_format(self):
        ctx = _cpu_ctx()
        ctx = AlertContext(**{**ctx.__dict__, "alertname": "PODMemoryLimitsUage>=90"})
        snapshot = {
            "usage_percent": 91.0,
            "usage_bytes": 900 * 1024**2,
            "limit_bytes": 1 * 1024**3,
            "restarts": 1,
            "resource": "memory",
        }
        bullets = _build_memory_bullets(ctx, snapshot)
        self.assertTrue(any("91.0%" in b for b in bullets))
        self.assertTrue(any("MiB" in b for b in bullets))
        self.assertTrue(any("restarts: 1" in b.lower() for b in bullets))

    def test_findings_confirm_alert(self):
        prefetched = {
            "snapshot": {"resource": "cpu", "usage_percent": 92.0, "restarts": 0},
            "workload": {"rollout": {"rollout_age_seconds": 200000, "rollout_age_human": "2d 7h"}},
        }
        findings = build_findings_bullets(_cpu_ctx(), prefetched)
        self.assertTrue(any("92.0%" in f for f in findings))
        self.assertTrue(any("stable" in f.lower() for f in findings))

    @patch("pod_metrics._fetch_pod_cpu_snapshot")
    def test_prefetch_cpu(self, mock_fetch):
        mock_fetch.return_value = {
            "usage_percent": 95.0,
            "usage_cores": 0.19,
            "limit_cores": 0.2,
            "restarts": 0,
            "resource": "cpu",
        }
        result = prefetch_pod_metrics(_cpu_ctx(), {"labels": {}})
        self.assertTrue(result["alert_valid"])
        self.assertEqual(len(result["bullets"]), 4)
        self.assertTrue(result["findings"])


if __name__ == "__main__":
    unittest.main()
