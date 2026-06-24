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
        alert_firing_value=1423.2,
        primary_metric="major_page_faults_per_sec",
    )


THIN_RCA = """*Alert summary:*
Memory pressure on host.

*Subject:*
Host: 10.1.64.41

*Metrics:*
• Major page faults: 1423.2

*Findings:*
• Node-exporter service status is not retrievable.
• Missing memory metrics from node-exporter.

*Data gaps:*
• Missing memory available percentage metrics.
• Missing up status from node-exporter.

*Probable root cause:*
Cannot determine due to missing data.

*Recommended actions:*
1. Check node-exporter
2. Verify Prometheus
3. Restart monitoring
"""

PREFETCHED = {
    "bullets": [
        "Major page faults: 1423.2/s (threshold > 1000/s)",
        "Memory available: 8.0% (640 MiB / 8.0 GiB) [MemAvailable]",
        "Node exporter up: 1 (job: AWSEC2NodeExporter)",
    ],
    "up": 1.0,
    "alert_valid": True,
}


class TestRcaFormatterHost(unittest.TestCase):
    def test_injects_prefetched_metrics(self):
        ctx = _host_ctx()
        result = format_rca(THIN_RCA, ctx, prefetched=PREFETCHED)
        self.assertIn("Memory available: 8.0%", result)
        self.assertIn("Node exporter up: 1", result)

    def test_strips_false_exporter_down(self):
        ctx = _host_ctx()
        result = format_rca(THIN_RCA, ctx, prefetched=PREFETCHED)
        self.assertNotIn("not retrievable", result.lower())

    def test_removes_data_gaps_when_metrics_sufficient(self):
        ctx = _host_ctx()
        result = format_rca(THIN_RCA, ctx, prefetched=PREFETCHED)
        self.assertNotIn("*Data gaps:*", result)


if __name__ == "__main__":
    unittest.main()
