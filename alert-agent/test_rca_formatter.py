import unittest

from alert_context import AlertContext
from rca_formatter import format_rca


def _host_ctx() -> AlertContext:
    return AlertContext(
        alertname="EC2HostMemoryUnderMemoryPressure",
        resource_type="host",
        namespace=None,
        pod=None,
        container=None,
        instance="10.1.64.41:9100",
        module=None,
        job=None,
        topic=None,
        group_id=None,
        host_ip="10.1.64.41",
        scrape_instance="10.1.64.41:9100",
        target=None,
        msk_job=None,
        workload_namespace=None,
        workload_deployment=None,
        scrape_job="AWSEC2NodeExporter",
        alert_firing_value=2257.3,
        primary_metric="major_page_faults_per_sec",
        region=None,
        cloud=None,
        stage=None,
    )


THIN_RCA = """*Alert summary:*
Memory pressure on host.

*Subject:*
Host: 10.1.64.41

*Metrics:*
• Major page faults: 2257.3/s (threshold > 1000/s) [from alert]
• Major page faults: 2257.3/s (threshold > 1000/s)

*Probable root cause:*
Cannot determine due to missing data.

*Recommended actions:*
1. Check node-exporter
2. Verify Prometheus
3. Restart monitoring
"""

PREFETCHED = {
    "bullets": [
        "Major page faults: 2257.3/s (threshold > 1000/s)",
        "Memory available: 11.0% (880 MiB / 8.0 GiB) [MemAvailable]",
        "Node exporter up: 1 (job: AWSEC2NodeExporter)",
    ],
    "findings": [
        "Page faults at 2257.3/s exceed threshold — host is under memory pressure.",
        "Memory available is 11.0% on host 10.1.64.41.",
        "Scrape target is healthy (up=1, job: AWSEC2NodeExporter).",
    ],
    "up": 1.0,
    "alert_valid": True,
    "snapshot": {"major_page_faults_per_sec": 2257.3, "memory": {"available_percent": 11.0}},
}


class TestRcaFormatterHost(unittest.TestCase):
    def test_replaces_metrics_without_duplicates(self):
        ctx = _host_ctx()
        result = format_rca(THIN_RCA, ctx, prefetched=PREFETCHED)
        self.assertEqual(result.count("Major page faults"), 1)
        self.assertIn("Memory available: 11.0%", result)
        self.assertIn("Node exporter up: 1", result)

    def test_injects_findings_when_missing(self):
        ctx = _host_ctx()
        result = format_rca(THIN_RCA, ctx, prefetched=PREFETCHED)
        self.assertIn("*Findings:*", result)
        self.assertIn("2257.3/s exceed threshold", result)
        self.assertNotIn("missing findings", result.lower())

    def test_removes_data_gaps_when_metrics_sufficient(self):
        ctx = _host_ctx()
        rca_with_gaps = THIN_RCA + "\n\n*Data gaps:*\n• Missing memory"
        result = format_rca(rca_with_gaps, ctx, prefetched=PREFETCHED)
        self.assertNotIn("*Data gaps:*", result)


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


POD_PREFETCHED = {
    "bullets": [
        "CPU usage % of limit: 92% (threshold >= 90%)",
        "CPU usage rate: 0.181 cores (5m avg)",
        "CPU limit: 200m (0.200 cores)",
        "Container restarts: 0",
    ],
    "findings": [
        "Container consumer is at 92% of its CPU limit — alert condition confirmed.",
        "Workload stable since last ReplicaSet change (4d 17h ago).",
    ],
    "alert_meaning": "Pod container CPU usage reached ≥90% of its configured CPU limit for 5+ minutes.",
    "workload_bullets": [
        "Region: ap-south-1 | cloud: aws | stage: prod",
        "Deployment: dozeeplatform/request-rawfiles-consumer",
        "Last ReplicaSet change: 4d 17h ago",
    ],
    "alert_valid": True,
    "snapshot": {"resource": "cpu", "usage_percent": 92.0},
}


THIN_POD_RCA = """*Alert summary:*
CPU high on pod.

*Subject:*
Namespace: dozeeplatform
Pod: consumer-abc

*Metrics:*
• CPU usage rate: 0.181 cores/sec

*Probable root cause:*
Missing CPU limits may be misconfigured.

*Recommended actions:*
1. Add limits
2. Check config
3. Restart pod
"""


class TestRcaFormatterKubernetes(unittest.TestCase):
    def test_replaces_pod_metrics_and_injects_workload(self):
        ctx = _k8s_ctx()
        result = format_rca(THIN_POD_RCA, ctx, prefetched=POD_PREFETCHED)
        self.assertIn("92%", result)
        self.assertIn(":package: *Workload:*", result)
        self.assertIn("Deployment: dozeeplatform/request-rawfiles-consumer", result)
        self.assertIn(":mag: *What this alert means:*", result)
        self.assertNotIn("Missing CPU limits", result)

    def test_emoji_sections_applied(self):
        ctx = _k8s_ctx()
        result = format_rca(THIN_POD_RCA, ctx, prefetched=POD_PREFETCHED)
        self.assertIn(":bar_chart: *Metrics:*", result)
        self.assertIn(":clipboard: *Findings:*", result)


if __name__ == "__main__":
    unittest.main()
