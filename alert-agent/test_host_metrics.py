import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

from alert_context import AlertContext, build_alert_context
from host_metrics import (
    _build_metric_bullets,
    build_findings_bullets,
    prefetch_host_metrics,
    resolve_scrape_instance,
)


def _host_ctx(**kwargs) -> AlertContext:
    defaults = {
        "alertname": "EC2HostMemoryUnderMemoryPressure",
        "resource_type": "host",
        "namespace": None,
        "pod": None,
        "container": None,
        "instance": "10.1.64.41:9100",
        "module": None,
        "job": None,
        "topic": None,
        "group_id": None,
        "host_ip": "10.1.64.41",
        "scrape_instance": "10.1.64.41:9100",
        "target": None,
        "msk_job": None,
        "workload_namespace": None,
        "workload_deployment": None,
        "scrape_job": "AWSEC2NodeExporter",
        "alert_firing_value": 1423.2,
        "primary_metric": "major_page_faults_per_sec",
    }
    defaults.update(kwargs)
    return AlertContext(**defaults)


class TestResolveScrapeInstance(unittest.TestCase):
    @patch("host_metrics._has_up_metric")
    def test_exact_match(self, mock_up):
        mock_up.side_effect = lambda inst: inst == "10.1.64.41:9100"
        resolved, method = resolve_scrape_instance("10.1.64.41:9100", "10.1.64.41")
        self.assertEqual(resolved, "10.1.64.41:9100")
        self.assertEqual(method, "exact")

    @patch("host_metrics._discover_instance_by_host_ip")
    @patch("host_metrics._has_up_metric", return_value=False)
    def test_discovered_by_host_ip(self, _mock_up, mock_discover):
        mock_discover.return_value = "10.1.64.41:9100"
        resolved, method = resolve_scrape_instance("10.1.64.41", "10.1.64.41")
        self.assertEqual(resolved, "10.1.64.41:9100")
        self.assertEqual(method, "discovered")


class TestBuildMetricBullets(unittest.TestCase):
    def test_full_snapshot(self):
        ctx = _host_ctx()
        snapshot = {
            "major_page_faults_per_sec": 1423.2,
            "memory": {
                "available_percent": 8.0,
                "available_bytes": 640 * 1024 * 1024,
                "total_bytes": 8 * 1024**3,
                "memory_source": "MemAvailable",
            },
            "up": 1.0,
            "scrape_job": "AWSEC2NodeExporter",
            "cpu_percent": 72.0,
        }
        bullets = _build_metric_bullets(ctx, snapshot)
        self.assertGreaterEqual(len(bullets), 3)
        self.assertTrue(any("Major page faults" in b for b in bullets))
        self.assertTrue(any("Memory available" in b for b in bullets))
        self.assertTrue(any("Node exporter up: 1" in b for b in bullets))

    def test_alert_value_fallback_when_promql_empty(self):
        ctx = _host_ctx()
        snapshot = {
            "major_page_faults_per_sec": None,
            "memory": {"available_percent": None, "memory_source": "unavailable"},
            "up": 1.0,
            "scrape_job": "AWSEC2NodeExporter",
        }
        bullets = _build_metric_bullets(ctx, snapshot)
        self.assertTrue(any("1423.2" in b and "from alert" in b for b in bullets))


class TestBuildFindingsBullets(unittest.TestCase):
    def test_findings_from_prefetch(self):
        ctx = _host_ctx()
        prefetched = {
            "up": 1.0,
            "alert_valid": True,
            "snapshot": {
                "major_page_faults_per_sec": 2257.3,
                "scrape_job": "AWSEC2NodeExporter",
                "memory": {"available_percent": 11.0},
            },
        }
        findings = build_findings_bullets(ctx, prefetched)
        self.assertTrue(any("2257" in f for f in findings))
        self.assertTrue(any("11.0%" in f for f in findings))
        self.assertTrue(any("up=1" in f for f in findings))


class TestPrefetchHostMetrics(unittest.TestCase):
    @patch("host_metrics._fetch_ec2_host_snapshot")
    @patch("host_metrics.resolve_scrape_instance")
    def test_prefetch_calls_prometheus(self, mock_resolve, mock_fetch):
        mock_resolve.return_value = ("10.1.64.41:9100", "exact")
        mock_fetch.return_value = {
            "major_page_faults_per_sec": 1500.0,
            "memory": {
                "available_percent": 12.0,
                "available_bytes": 1e9,
                "total_bytes": 8e9,
                "memory_source": "MemFree",
            },
            "up": 1.0,
            "scrape_job": "AWSEC2NodeExporter",
            "cpu_percent": 50.0,
            "load1": 1.2,
            "disk_avail_percent": 45.0,
        }
        alert = {
            "labels": {
                "alertname": "EC2HostMemoryUnderMemoryPressure",
                "instance": "10.1.64.41:9100",
            },
            "annotations": {
                "description": "High page faults\n  VALUE = 1500",
            },
        }
        ctx = build_alert_context(alert)
        result = prefetch_host_metrics(ctx, alert)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertGreaterEqual(len(result["bullets"]), 3)
        self.assertEqual(result["up"], 1.0)
        self.assertIn("findings", result)
        mock_fetch.assert_called_once_with("10.1.64.41:9100")


if __name__ == "__main__":
    unittest.main()
