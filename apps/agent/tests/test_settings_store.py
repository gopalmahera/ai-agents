import unittest
from unittest.mock import patch

import services.store.settings_store as ss


class TestSettingsStore(unittest.TestCase):
    @patch.object(ss, "_get_db")
    def test_load_agent_settings(self, mock_db_fn):
        mock_db = mock_db_fn.return_value
        mock_db.agent_settings.find_one.return_value = {
            "_id": "runtime",
            "AI_PROVIDER": "openai",
        }
        out = ss.load_agent_settings()
        self.assertEqual(out["AI_PROVIDER"], "openai")

    @patch.object(ss, "_get_db")
    def test_get_settings_version(self, mock_db_fn):
        mock_db = mock_db_fn.return_value
        mock_db.settings_meta.find_one.return_value = {"_id": "version", "version": 3}
        self.assertEqual(ss.get_settings_version(), 3)

    @patch.object(ss, "_get_db", return_value=None)
    def test_unavailable_returns_empty(self, _mock_db):
        self.assertEqual(ss.load_agent_settings(), {})
        self.assertEqual(ss.get_settings_version(), 0)


if __name__ == "__main__":
    unittest.main()
