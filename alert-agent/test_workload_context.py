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
        container="request-rawfiles-consumer",
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
    def test_prefetch_includes_images(self, mock_rollout):
        mock_rollout.return_value = {
            "owner_kind": "Deployment",
            "owner_name": "request-rawfiles-consumer",
            "replicaset": "request-rawfiles-consumer-7d6dd796cb",
            "current_image": "414448255958.dkr.ecr.ap-south-1.amazonaws.com/app:v2.3.1",
            "previous_image": "414448255958.dkr.ecr.ap-south-1.amazonaws.com/app:v2.3.0",
            "previous_replicaset": "request-rawfiles-consumer-6c8f9d4b5a",
            "rollout_age_human": "4d 17h",
            "rollout_timestamp": "2026-06-20 14:32 UTC",
            "rollout_age_seconds": 410000,
        }
        result = prefetch_workload_context(_ctx(), {"labels": {"region": "ap-south-1"}})
        bullets = result["bullets"]
        self.assertTrue(any("Current image:" in b for b in bullets))
        self.assertTrue(any("Previous image:" in b for b in bullets))
        self.assertTrue(any("v2.3.1" in b for b in bullets))

    @patch("workload_context.fetch_workload_rollout_info")
    def test_handles_missing_previous_image(self, mock_rollout):
        mock_rollout.return_value = {
            "replicaset": "app-abc",
            "current_image": "img:v1",
            "rollout_age_human": "2d",
        }
        result = prefetch_workload_context(_ctx(), {"labels": {}})
        bullets = result["bullets"]
        self.assertTrue(any("Current image:" in b for b in bullets))
        self.assertFalse(any("Previous image:" in b for b in bullets))


if __name__ == "__main__":
    unittest.main()
