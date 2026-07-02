import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

import services.config_store as config_store
import services.store.redis_client as redis_client
from app import app

_VALID_WEBHOOK = "https://hooks.slack.com/services/T000/B000/xxxxxxxx"


class TestConfigApi(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    # ── POST /api/config ──────────────────────────────────────────────────
    def test_post_config_non_dict_returns_400(self):
        resp = self.client.post("/api/config", json=["LOKI_URL"])
        self.assertEqual(resp.status_code, 400)

    def test_post_config_redis_down_returns_503(self):
        with patch.object(config_store._redis, "config_save_and_publish", side_effect=Exception("down")):
            resp = self.client.post("/api/config", json={"LOKI_URL": "http://x:3100"})
        self.assertEqual(resp.status_code, 503)

    def test_post_config_valid_returns_200(self):
        with patch.object(config_store._redis, "config_save_and_publish"), \
             patch.object(config_store._redis, "config_load", return_value={}):
            resp = self.client.post("/api/config", json={"LOKI_URL": "http://ok:3100"})
        self.assertEqual(resp.status_code, 200)

    # ── POST /api/config/routing ──────────────────────────────────────────
    def test_post_routing_non_dict_returns_400(self):
        resp = self.client.post("/api/config/routing", json=[1, 2, 3])
        self.assertEqual(resp.status_code, 400)

    def test_post_routing_invalid_regex_returns_400(self):
        body = {"routes": [{"match_re": {"alertname": "["}, "slack_webhook_url": _VALID_WEBHOOK}]}
        with patch.object(redis_client, "save_yaml_and_publish") as save:
            resp = self.client.post("/api/config/routing", json=body)
        self.assertEqual(resp.status_code, 400)
        save.assert_not_called()  # never persisted

    def test_post_routing_redis_down_returns_503(self):
        body = {"routes": [{"match": {"severity": "critical"}, "slack_webhook_url": _VALID_WEBHOOK}]}
        import api.config_api as config_api
        with patch.object(config_api._redis, "save_yaml_and_publish", side_effect=Exception("down")):
            resp = self.client.post("/api/config/routing", json=body)
        self.assertEqual(resp.status_code, 503)

    def test_post_routing_valid_persists_with_routing_kind(self):
        body = {"routes": [{"match": {"severity": "critical"}, "slack_webhook_url": _VALID_WEBHOOK}]}
        import api.config_api as config_api
        with patch.object(config_api._redis, "save_yaml_and_publish") as save, \
             patch.object(config_api._routing, "reset_cache"):
            resp = self.client.post("/api/config/routing", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(save.call_args.args[0], "routing")


if __name__ == "__main__":
    unittest.main()
