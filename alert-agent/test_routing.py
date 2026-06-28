import os
import tempfile
import unittest

import yaml

import routing


def _write_config(data: dict) -> str:
    fh = tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False)
    yaml.safe_dump(data, fh)
    fh.close()
    return fh.name


class TestRouting(unittest.TestCase):
    def setUp(self):
        routing._config = None  # reset cache between tests

    def _load(self, cfg: dict) -> None:
        path = _write_config(cfg)
        routing._ROUTING_CONFIG_PATH = path
        routing._config = None

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
        # Missing stage — should NOT match
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

    def test_no_config_falls_back_to_env(self):
        routing._ROUTING_CONFIG_PATH = ""
        routing._config = None
        import unittest.mock as mock
        with mock.patch("routing.SLACK_WEBHOOK_URL", "https://env-fallback"):
            self.assertEqual(routing.resolve_webhook_url({"severity": "warning"}), "https://env-fallback")

    def test_default_webhook_in_config(self):
        self._load({
            "default_slack_webhook_url": "https://config-default",
            "routes": [],
        })
        self.assertEqual(routing.resolve_webhook_url({"severity": "warning"}), "https://config-default")


if __name__ == "__main__":
    unittest.main()
