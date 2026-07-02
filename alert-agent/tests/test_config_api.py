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

    # ── environments (endpoint refs, no label matching) ───────────────────
    def test_post_environments_unknown_ref_returns_400(self):
        body = {"environments": [{"name": "prod", "prometheus": "missing-endpoint"}]}
        import api.config_api as config_api
        with patch.object(config_api._environments, "endpoint_index", return_value={}), \
             patch.object(config_api._redis, "save_yaml_and_publish") as save:
            resp = self.client.post("/api/config/environments", json=body)
        self.assertEqual(resp.status_code, 400)
        save.assert_not_called()

    def test_post_environments_valid_persists_with_kind(self):
        body = {"environments": [{"name": "prod", "prometheus": "prod-prom"}]}
        registry = {"prod-prom": {"name": "prod-prom", "type": "prometheus", "url": "http://p"}}
        import api.config_api as config_api
        with patch.object(config_api._cfg, "ENVIRONMENTS_CONFIG_PATH", ""), \
             patch.object(config_api._environments, "endpoint_index", return_value=registry), \
             patch.object(config_api._redis, "save_yaml_and_publish") as save, \
             patch.object(config_api._environments, "reset_cache"):
            resp = self.client.post("/api/config/environments", json=body)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(save.call_args.args[0], "environments")

    def test_post_environments_reserved_name_returns_400(self):
        body = {"environments": [{"name": "test"}]}
        import api.config_api as config_api
        with patch.object(config_api._environments, "endpoint_index", return_value={}), \
             patch.object(config_api._redis, "save_yaml_and_publish") as save:
            resp = self.client.post("/api/config/environments", json=body)
        self.assertEqual(resp.status_code, 400)
        save.assert_not_called()

    def test_post_environments_redis_down_returns_503(self):
        body = {"environments": [{"name": "prod"}]}
        import api.config_api as config_api
        with patch.object(config_api._cfg, "ENVIRONMENTS_CONFIG_PATH", ""), \
             patch.object(config_api._environments, "endpoint_index", return_value={}), \
             patch.object(config_api._redis, "save_yaml_and_publish", side_effect=Exception("down")):
            resp = self.client.post("/api/config/environments", json=body)
        self.assertEqual(resp.status_code, 503)

    # ── endpoints registry ────────────────────────────────────────────────
    def test_get_endpoints_masks_secrets(self):
        import yaml
        import api.config_api as config_api
        stored = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p", "auth": {"mode": "bearer", "token": "SECRET"}}]}
        with patch.object(config_api._cfg, "ENDPOINTS_CONFIG_PATH", ""), \
             patch.object(config_api._redis, "endpoints_yaml_load", return_value=yaml.safe_dump(stored)):
            resp = self.client.get("/api/config/endpoints")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["endpoints"][0]["auth"]["token"], "***")

    def test_post_endpoints_invalid_type_returns_400(self):
        body = {"endpoints": [{"name": "x", "type": "nope"}]}
        import api.config_api as config_api
        with patch.object(config_api._redis, "endpoints_yaml_load", return_value=""), \
             patch.object(config_api._redis, "save_yaml_and_publish") as save:
            resp = self.client.post("/api/config/endpoints", json=body)
        self.assertEqual(resp.status_code, 400)
        save.assert_not_called()

    def test_post_endpoints_masked_secret_preserved(self):
        import yaml
        import api.config_api as config_api
        stored = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p", "auth": {"mode": "bearer", "token": "REAL"}}]}
        # UI re-posts with the secret still masked → the stored value must survive.
        body = {"endpoints": [
            {"name": "p", "type": "prometheus", "url": "http://p", "auth": {"mode": "bearer", "token": "***"}}]}
        captured = {}

        def _save(kind, yaml_text):
            captured["yaml"] = yaml_text
            return 1

        with patch.object(config_api._cfg, "ENDPOINTS_CONFIG_PATH", ""), \
             patch.object(config_api._redis, "endpoints_yaml_load", return_value=yaml.safe_dump(stored)), \
             patch.object(config_api._redis, "save_yaml_and_publish", side_effect=_save), \
             patch.object(config_api._environments, "reset_cache"):
            resp = self.client.post("/api/config/endpoints", json=body)
        self.assertEqual(resp.status_code, 200)
        saved = yaml.safe_load(captured["yaml"])
        self.assertEqual(saved["endpoints"][0]["auth"]["token"], "REAL")

    def test_post_endpoints_redis_down_returns_503(self):
        body = {"endpoints": [{"name": "p", "type": "prometheus", "url": "http://p"}]}
        import api.config_api as config_api
        with patch.object(config_api._redis, "endpoints_yaml_load", return_value=""), \
             patch.object(config_api._redis, "save_yaml_and_publish", side_effect=Exception("down")):
            resp = self.client.post("/api/config/endpoints", json=body)
        self.assertEqual(resp.status_code, 503)


if __name__ == "__main__":
    unittest.main()
