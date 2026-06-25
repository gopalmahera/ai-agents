import sys
import unittest
from unittest.mock import MagicMock

sys.modules.setdefault("requests", MagicMock())

from alert_context import build_alert_context
from deterministic_rca import build_deterministic_rca


class TestDeterministicRca(unittest.TestCase):
    def test_ec2_host_rca_without_llm(self):
        alert = {
            "labels": {
                "alertname": "EC2HostMemoryUnderMemoryPressure",
                "instance": "10.1.78.66:9100",
                "severity": "warning",
            },
            "annotations": {
                "description": "High page faults\n  VALUE = 2257.3",
            },
        }
        ctx = build_alert_context(alert)
        prefetched = {
            "bullets": [
                "Major page faults: 2257.3/s (threshold > 1000/s)",
                "Memory available: 11.0% (880 MiB / 8.0 GiB) [MemAvailable]",
                "Node exporter up: 1 (job: AWSEC2NodeExporter)",
            ],
            "findings": [
                "Page faults at 2257.3/s exceed threshold — host is under memory pressure.",
                "Memory available is 11.0% on host 10.1.78.66.",
                "Scrape target is healthy (up=1, job: AWSEC2NodeExporter).",
            ],
            "up": 1.0,
            "alert_valid": True,
            "snapshot": {
                "major_page_faults_per_sec": 2257.3,
                "memory": {"available_percent": 11.0},
            },
        }
        rca = build_deterministic_rca(ctx, prefetched)
        self.assertIn("*Alert summary:*", rca)
        self.assertIn("*Metrics:*", rca)
        self.assertIn("*Findings:*", rca)
        self.assertIn("*Probable root cause:*", rca)
        self.assertIn("*Recommended actions:*", rca)
        self.assertIn("2257.3/s", rca)
        self.assertIn("Host: 10.1.78.66", rca)


if __name__ == "__main__":
    unittest.main()
