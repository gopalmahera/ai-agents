import unittest

from services.notification.routing_validation import validate_routing_body


class TestRoutingValidation(unittest.TestCase):
    def test_valid_minimal_config(self):
        errors = validate_routing_body(
            {
                "default_slack_webhook_url": "https://hooks.slack.com/services/T/B/x",
                "routes": [
                    {
                        "match": {"severity": "critical"},
                        "slack_webhook_url": "https://hooks.slack.com/services/T/B/y",
                    }
                ],
            }
        )
        self.assertEqual(errors, [])

    def test_rejects_rule_without_matchers(self):
        errors = validate_routing_body(
            {
                "routes": [
                    {
                        "slack_webhook_url": "https://hooks.slack.com/services/T/B/y",
                    }
                ],
            }
        )
        self.assertTrue(any("matcher" in e for e in errors))

    def test_rejects_invalid_webhook(self):
        errors = validate_routing_body(
            {
                "routes": [
                    {
                        "match": {"severity": "critical"},
                        "slack_webhook_url": "http://example.com/hook",
                    }
                ],
            }
        )
        self.assertTrue(any("slack_webhook_url" in e for e in errors))

    def test_rejects_invalid_regex(self):
        errors = validate_routing_body(
            {
                "routes": [
                    {
                        "match_re": {"alertname": "[invalid"},
                        "slack_webhook_url": "https://hooks.slack.com/services/T/B/y",
                    }
                ],
            }
        )
        self.assertTrue(any("invalid regex" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
