import unittest

from report_header import format_report_header
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


class TestReportHeader(unittest.TestCase):
    def test_uses_alertname_not_rca(self):
        labels = {"severity": "critical", "region": "ap-south-1", "cloud": "aws", "stage": "prod"}
        header = format_report_header(_k8s_ctx(), labels)
        self.assertTrue(header.startswith("RCA — PODCPULimitsUage>=90"))
        self.assertNotIn("Alertname", header)
        self.assertIn("Region: ap-south-1", header)
        self.assertIn("Namespace: dozeeplatform", header)


if __name__ == "__main__":
    unittest.main()
