import sys
import unittest
from unittest.mock import patch

from alert_context import AlertContext
from workload_context import prefetch_workload_context


def _ctx() -> AlertContext:
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


class TestWorkloadContext(unittest.TestCase):
    @patch("workload_context.fetch_workload_rollout_info")
    def test_prefetch_includes_region_and_rollout(self, mock_rollout):
        mock_rollout.return_value = {
            "owner_kind": "Deployment",
            "owner_name": "request-rawfiles-consumer",
            "replicaset": "request-rawfiles-consumer-7d6dd796cb",
            "rollout_age_human": "4d 17h",
            "rollout_timestamp": "2026-06-20 14:32 UTC",
            "rollout_age_seconds": 410000,
        }
        alert = {
            "labels": {
                "region": "ap-south-1",
                "cloud": "aws",
                "stage": "prod",
            }
        }
        result = prefetch_workload_context(_ctx(), alert)
        self.assertIsNotNone(result)
        bullets = result["bullets"]
        self.assertTrue(any("Region: ap-south-1" in b for b in bullets))
        self.assertTrue(any("Deployment: dozeeplatform/request-rawfiles-consumer" in b for b in bullets))
        self.assertTrue(any("Last ReplicaSet change" in b for b in bullets))
        self.assertIn("alert_meaning", result)

    def test_skips_non_pod_resource_alerts(self):
        ctx = AlertContext(**{**_ctx().__dict__, "alertname": "PodRestarting"})
        self.assertIsNone(prefetch_workload_context(ctx, {"labels": {}}))

    @patch("workload_context.fetch_workload_rollout_info")
    def test_handles_missing_owner(self, mock_rollout):
        mock_rollout.return_value = {"error": "pod has no ReplicaSet owner"}
        result = prefetch_workload_context(_ctx(), {"labels": {"region": "ap-south-1"}})
        self.assertIsNotNone(result)
        self.assertTrue(any("Region:" in b for b in result["bullets"]))


if __name__ == "__main__":
    unittest.main()
