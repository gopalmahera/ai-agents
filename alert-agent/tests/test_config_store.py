import json
import os
import tempfile
import unittest
from unittest import mock

import config as _cfg
import services.config_store as cs


class TestConfigStore(unittest.TestCase):
    def setUp(self):
        fh = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        fh.close()
        os.unlink(fh.name)  # start with no file on disk
        self.store_path = fh.name
        patcher = mock.patch.object(_cfg, "CONFIG_STORE_PATH", self.store_path)
        patcher.start()
        self.addCleanup(patcher.stop)
        for key in ("LOKI_URL", "PROMETHEUS_URL", "ALLOWED_ALERTNAMES"):
            self.addCleanup(os.environ.pop, key, None)

    def tearDown(self):
        if os.path.exists(self.store_path):
            os.unlink(self.store_path)

    def test_precedence_stored_over_env_over_default(self):
        stored = {"LOKI_URL": json.dumps("http://stored:3100")}
        with mock.patch.object(cs._redis, "config_load", return_value=stored), \
             mock.patch.dict(os.environ, {"LOKI_URL": "http://env:3100",
                                          "PROMETHEUS_URL": "http://env:9090"}):
            values = cs.get_all()
        self.assertEqual(values["LOKI_URL"], "http://stored:3100")   # stored wins
        self.assertEqual(values["PROMETHEUS_URL"], "http://env:9090")  # env when not stored
        self.assertEqual(values["ALLOWED_ALERTNAMES"],
                         os.environ.get("ALLOWED_ALERTNAMES", ""))   # default otherwise

    def test_update_saves_atomically_and_applies(self):
        with mock.patch.object(cs._redis, "config_save_and_publish") as save, \
             mock.patch.object(cs._redis, "config_load", return_value={}):
            cs.update({"LOKI_URL": "http://new:3100", "NOT_A_KEY": "x"})
        # Atomic HSET+INCR+publish, unknown key filtered out
        save.assert_called_once_with({"LOKI_URL": json.dumps("http://new:3100")})
        self.assertEqual(_cfg.LOKI_URL, "http://new:3100")  # applied live
        with open(self.store_path, encoding="utf-8") as fh:  # file mirror written
            self.assertEqual(json.load(fh)["LOKI_URL"], "http://new:3100")

    def test_update_rejects_with_exception_on_redis_outage(self):
        with mock.patch.object(cs._redis, "config_save_and_publish", side_effect=Exception("down")):
            with self.assertRaises(cs.ConfigStoreUnavailable):
                cs.update({"LOKI_URL": "http://offline:3100"})
        # No local-only write — nothing persisted, nothing to silently revert later.
        self.assertFalse(os.path.exists(self.store_path))

    def test_mcp_urls_not_configurable(self):
        for key in ("K8S_MCP_URL", "PROMETHEUS_MCP_URL", "LOKI_MCP_URL", "KAFKA_MCP_URL"):
            self.assertNotIn(key, cs.CONFIGURABLE_KEYS)
        with mock.patch.object(cs._redis, "config_save_and_publish") as save:
            cs.update({"K8S_MCP_URL": "http://elsewhere:1234"})
        save.assert_not_called()

    def test_allowed_alertnames_recompiles_pattern(self):
        with mock.patch.object(cs._redis, "config_save_and_publish"), \
             mock.patch.object(cs._redis, "config_load", return_value={}):
            cs.update({"ALLOWED_ALERTNAMES": "^Pod.*"})
            self.assertIsNotNone(_cfg._allowed_alertname_pattern)
            self.assertTrue(_cfg._allowed_alertname_pattern.search("PodRestart"))
            cs.update({"ALLOWED_ALERTNAMES": ""})
            self.assertIsNone(_cfg._allowed_alertname_pattern)

    def test_seed_bumps_version_and_publishes(self):
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump({"LOKI_URL": "http://seed:3100", "K8S_MCP_URL": "ignored"}, fh)
        with mock.patch.object(cs._redis, "config_is_empty", return_value=True), \
             mock.patch.object(cs._redis, "config_save") as save, \
             mock.patch.object(cs._redis, "yaml_is_empty", return_value=False), \
             mock.patch.object(cs._redis, "publish_config_event") as publish:
            cs.seed_redis_from_file()
        save.assert_called_once_with({"LOKI_URL": json.dumps("http://seed:3100")})
        publish.assert_called_once_with("config")  # running replicas get notified

    def test_seed_noop_when_redis_already_populated(self):
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump({"LOKI_URL": "http://seed:3100"}, fh)
        with mock.patch.object(cs._redis, "config_is_empty", return_value=False), \
             mock.patch.object(cs._redis, "yaml_is_empty", return_value=False), \
             mock.patch.object(cs._redis, "config_save") as save, \
             mock.patch.object(cs._redis, "publish_config_event") as publish:
            cs.seed_redis_from_file()
        save.assert_not_called()
        publish.assert_not_called()

    def test_apply_stored_raises_when_redis_down(self):
        with mock.patch.object(cs._redis, "config_load", side_effect=Exception("down")):
            with self.assertRaises(Exception):
                cs.apply_stored()

    def test_apply_from_file_works_without_redis(self):
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump({"LOKI_URL": "http://fromfile:3100"}, fh)
        # No Redis interaction at all — reads the local mirror only.
        cs.apply_from_file()
        self.assertEqual(_cfg.LOKI_URL, "http://fromfile:3100")

    def test_get_masked_hides_secrets(self):
        stored = {"OPENAI_API_KEY": json.dumps("sk-secret")}
        with mock.patch.object(cs._redis, "config_load", return_value=stored):
            values = cs.get_masked()
        self.assertEqual(values["OPENAI_API_KEY"], "***")

    def test_get_all_falls_back_to_file_when_redis_down(self):
        with open(self.store_path, "w", encoding="utf-8") as fh:
            json.dump({"LOKI_URL": "http://filefallback:3100"}, fh)
        with mock.patch.object(cs._redis, "config_load", side_effect=Exception("down")):
            values = cs.get_all()
        self.assertEqual(values["LOKI_URL"], "http://filefallback:3100")


if __name__ == "__main__":
    unittest.main()
