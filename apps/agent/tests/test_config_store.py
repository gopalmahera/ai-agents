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
        os.unlink(fh.name)
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
        with mock.patch.object(cs._settings_store, "load_agent_settings",
                               return_value={"LOKI_URL": "http://stored:3100"}), \
             mock.patch.dict(os.environ, {"LOKI_URL": "http://env:3100",
                                          "PROMETHEUS_URL": "http://env:9090"}):
            values = cs.get_all()
        self.assertEqual(values["LOKI_URL"], "http://stored:3100")
        self.assertEqual(values["PROMETHEUS_URL"], "http://env:9090")

    def test_update_rejects_admin_api_owned(self):
        with self.assertRaises(cs.ConfigStoreUnavailable):
            cs.update({"LOKI_URL": "http://offline:3100"})

    def test_mcp_urls_not_configurable(self):
        for key in ("K8S_MCP_URL", "PROMETHEUS_MCP_URL", "LOKI_MCP_URL", "KAFKA_MCP_URL"):
            self.assertNotIn(key, cs.CONFIGURABLE_KEYS)

    def test_apply_stored_reads_mongo(self):
        with mock.patch.object(cs._settings_store, "load_agent_settings",
                               return_value={"LOKI_URL": "http://mongo:3100"}):
            cs.apply_stored()
        self.assertEqual(_cfg.LOKI_URL, "http://mongo:3100")

    def test_seed_is_noop(self):
        cs.seed_redis_from_file()  # should not raise


if __name__ == "__main__":
    unittest.main()
