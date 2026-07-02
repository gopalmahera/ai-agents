"""Unit tests for WebSocket transport config cache."""

import unittest

from services.transport import config_cache


class TestConfigCache(unittest.TestCase):
    def test_update_and_read(self):
        config_cache.update({"agent": {"LLM_ENABLED": True}}, version=3)
        self.assertEqual(config_cache.get_version(), 3)
        self.assertTrue(config_cache.get_agent_settings().get("LLM_ENABLED"))


if __name__ == "__main__":
    unittest.main()
