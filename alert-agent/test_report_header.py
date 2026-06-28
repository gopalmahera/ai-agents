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
        self.assertIn("PODCPULimitsUage>=90", header)
        self.assertIn(":rotating_light:", header)
        self.assertIn("severity: critical", header)
        self.assertNotIn("Alertname", header)
        self.assertIn("Region: ap-south-1", header)
        self.assertIn("Namespace: dozeeplatform", header)

    def test_includes_started_at(self):
        labels = {"severity": "warning"}
        alert = {"startsAt": "2026-01-15T10:30:00Z"}
        header = format_report_header(_k8s_ctx(), labels, alert=alert)
        self.assertIn("2026-01-15 10:30 UTC", header)

    def test_includes_generator_url(self):
        labels = {"severity": "warning"}
        alert = {"generatorURL": "http://prometheus/graph?g0.expr=up"}
        header = format_report_header(_k8s_ctx(), labels, alert=alert)
        self.assertIn("View in Prometheus", header)
        self.assertIn("http://prometheus/graph", header)

    def test_includes_summary_from_annotations(self):
        labels = {"severity": "warning"}
        alert = {"annotations": {"summary": "Pod OOM killed in namespace foo"}}
        header = format_report_header(_k8s_ctx(), labels, alert=alert)
        self.assertIn("Pod OOM killed", header)

    def test_no_started_at_when_zero_time(self):
        labels = {"severity": "warning"}
        alert = {"startsAt": "0001-01-01T00:00:00Z"}
        header = format_report_header(_k8s_ctx(), labels, alert=alert)
        self.assertNotIn("Started:", header)


if __name__ == "__main__":
    unittest.main()
