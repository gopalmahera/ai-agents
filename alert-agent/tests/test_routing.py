import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

import yaml

import services.notification.routing as routing
from services.notification import time_intervals


def _write_config(data: dict) -> str:
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.safe_dump(data, fh)
    fh.close()
    return fh.name


class TestRouting(unittest.TestCase):
    def setUp(self):
        routing.reset_cache()
        time_intervals.reset_cache()
        self.addCleanup(routing.reset_cache)
        self.addCleanup(time_intervals.reset_cache)
        patcher = mock.patch.object(routing._redis, "routing_yaml_load", return_value=None)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _load(self, cfg: dict) -> None:
        path = _write_config(cfg)
        patcher = mock.patch.object(routing._cfg, "ROUTING_CONFIG_PATH", path, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        routing.reset_cache()

    def test_exact_match_wins(self):
        self._load({
            "default_slack_webhook_url": "https://default",
            "routes": [
                {"match": {"severity": "critical"}, "slack_webhook_url": "https://critical"},
                {"match": {"severity": "warning"}, "slack_webhook_url": "https://warning"},
            ],
        })
        self.assertEqual(routing.resolve_webhook_url({"severity": "critical"}), "https://critical")
        self.assertEqual(routing.resolve_webhook_url({"severity": "warning"}), "https://warning")

    def test_regex_match(self):
        self._load({
            "default_slack_webhook_url": "https://default",
            "routes": [
                {"match_re": {"alertname": "^EC2Host.*"}, "slack_webhook_url": "https://infra"},
            ],
        })
        self.assertEqual(routing.resolve_webhook_url({"alertname": "EC2HostDown"}), "https://infra")
        self.assertEqual(routing.resolve_webhook_url({"alertname": "PodOOMKilled"}), "https://default")

    def test_multi_label_and(self):
        self._load({
            "default_slack_webhook_url": "https://default",
            "routes": [
                {"match": {"severity": "critical", "stage": "prod"}, "slack_webhook_url": "https://prod-critical"},
            ],
        })
        self.assertEqual(
            routing.resolve_webhook_url({"severity": "critical", "stage": "prod"}),
            "https://prod-critical",
        )
        self.assertEqual(
            routing.resolve_webhook_url({"severity": "critical", "stage": "sit"}),
            "https://default",
        )

    def test_first_match_wins(self):
        self._load({
            "default_slack_webhook_url": "https://default",
            "routes": [
                {"match": {"severity": "critical"}, "slack_webhook_url": "https://first"},
                {"match": {"severity": "critical"}, "slack_webhook_url": "https://second"},
            ],
        })
        self.assertEqual(routing.resolve_webhook_url({"severity": "critical"}), "https://first")

    def test_mute_time_interval_skips_route(self):
        time_intervals.set_intervals([
            {
                "name": "always",
                "time_intervals": [{
                    "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
                    "times": [],
                    "location": "UTC",
                }],
            }
        ])
        self._load({
            "default_slack_webhook_url": "https://default",
            "routes": [
                {
                    "match": {"severity": "critical"},
                    "slack_webhook_url": "https://muted",
                    "mute_time_intervals": ["always"],
                },
                {"match": {"severity": "critical"}, "slack_webhook_url": "https://fallback"},
            ],
        })
        self.assertEqual(routing.resolve_webhook_url({"severity": "critical"}), "https://fallback")

    def test_no_config_falls_back_to_env(self):
        with mock.patch.object(routing._cfg, "ROUTING_CONFIG_PATH", "", create=True), \
             mock.patch.object(routing._cfg, "SLACK_WEBHOOK_URL", "https://env-fallback"):
            routing.reset_cache()
            self.assertEqual(routing.resolve_webhook_url({"severity": "warning"}), "https://env-fallback")

    def test_default_webhook_in_config(self):
        self._load({
            "default_slack_webhook_url": "https://config-default",
            "routes": [],
        })
        self.assertEqual(routing.resolve_webhook_url({"severity": "warning"}), "https://config-default")

    def test_redis_rules_win_over_file(self):
        path = _write_config({
            "default_slack_webhook_url": "https://from-file",
            "routes": [],
        })
        redis_yaml = yaml.safe_dump({
            "default_slack_webhook_url": "https://from-redis",
            "routes": [],
        })
        with mock.patch.object(routing._redis, "routing_yaml_load", return_value=redis_yaml), \
             mock.patch.object(routing._cfg, "ROUTING_CONFIG_PATH", path, create=True):
            routing.reset_cache()
            self.assertEqual(routing.resolve_webhook_url({}), "https://from-redis")


if __name__ == "__main__":
    unittest.main()
