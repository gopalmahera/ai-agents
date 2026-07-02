import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models import catalog as catalog_module
from models.catalog import (
    CATALOG,
    get_alert_meaning,
    get_runbook_url,
    export_catalog_yaml,
)


class TestCatalog(unittest.TestCase):
    def test_catalog_has_at_least_153_entries(self):
        self.assertGreaterEqual(len(CATALOG), 153)

    def test_static_alerts_have_descriptions_and_runbooks(self):
        entry = CATALOG["PODCPULimitsUage>=90"]
        self.assertIn("CPU", entry.description)
        self.assertTrue(entry.runbook)

    def test_msk_expansion_present(self):
        self.assertIn("msk.kb.wss.vitalsstream > 3000", CATALOG)

    def test_pattern_fallback_for_unknown_msk(self):
        meaning = get_alert_meaning("msk.kb.custom.topic > 9999")
        self.assertIsNotNone(meaning)
        self.assertIn("lag", meaning.lower())

    def test_runbook_url_lookup(self):
        url = get_runbook_url("PodOOMKilled")
        self.assertIn("runbooks", url or "")

    def test_export_round_trip(self):
        path = Path(__file__).resolve().parent / "_tmp_catalog.yaml"
        try:
            count = export_catalog_yaml(path)
            self.assertGreaterEqual(count, 153)
            self.assertTrue(path.exists())
        finally:
            if path.exists():
                path.unlink()

    def test_yaml_overlay_reload(self):
        original_path = catalog_module._CATALOG_PATH
        path = Path(__file__).resolve().parent / "_overlay_catalog.yaml"
        path.write_text(
            "CustomTestAlert:\n"
            "  description: Custom alert for unit test\n"
            "  runbook: https://example.com/runbook\n"
        )
        try:
            catalog_module._CATALOG_PATH = path
            reloaded = catalog_module._build_catalog()
            self.assertIn("CustomTestAlert", reloaded)
            self.assertEqual(reloaded["CustomTestAlert"].description, "Custom alert for unit test")
        finally:
            catalog_module._CATALOG_PATH = original_path
            if path.exists():
                path.unlink()


if __name__ == "__main__":
    unittest.main()
