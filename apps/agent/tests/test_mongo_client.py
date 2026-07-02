import unittest
from datetime import datetime, timezone
from unittest import mock

import config as _cfg
import services.store.mongo_client as mc


class TestMongoClient(unittest.TestCase):
    def tearDown(self):
        mc._db = None
        mc._import_failed = False

    def test_disabled_when_no_url(self):
        # MONGO_URL unset by default → everything is a safe no-op.
        with mock.patch.object(_cfg, "MONGO_URL", ""):
            mc._db = None
            self.assertFalse(mc.is_available())
            mc.record_event(alertname="X", outcome="accepted")  # must not raise
            self.assertEqual(mc.recent_events(datetime.now(timezone.utc), datetime.now(timezone.utc)), [])
            self.assertEqual(mc.report_summary(datetime.now(timezone.utc), datetime.now(timezone.utc)), {})

    def test_record_event_inserts_with_ts_and_drops_empties(self):
        fake_coll = mock.MagicMock()
        fake_db = {mc._EVENTS: fake_coll}
        with mock.patch.object(mc, "_get_db", return_value=fake_db):
            mc.record_event(
                alertname="PodRestart", outcome="rca_success", namespace="",
                cost_usd=0.018, model="gpt-4o",
            )
        fake_coll.insert_one.assert_called_once()
        doc = fake_coll.insert_one.call_args.args[0]
        self.assertIn("ts", doc)
        self.assertEqual(doc["alertname"], "PodRestart")
        self.assertEqual(doc["cost_usd"], 0.018)
        self.assertNotIn("namespace", doc)  # empty string dropped

    def test_record_event_swallows_errors(self):
        fake_coll = mock.MagicMock()
        fake_coll.insert_one.side_effect = Exception("mongo down")
        with mock.patch.object(mc, "_get_db", return_value={mc._EVENTS: fake_coll}):
            mc.record_event(alertname="X", outcome="accepted")  # must not raise

    def test_report_summary_shapes_aggregation(self):
        # Return different aggregate results per pipeline call in order:
        # by_alertname, totals, cost_by_model, timeline
        fake_coll = mock.MagicMock()
        fake_coll.aggregate.side_effect = [
            [  # by_alertname
                {"_id": {"alertname": "PodRestart", "outcome": "accepted"}, "count": 5, "cost": 0},
                {"_id": {"alertname": "PodRestart", "outcome": "rca_success"}, "count": 4, "cost": 0.072},
            ],
            [{"_id": None, "events": 9, "cost": 0.072, "tokens": 19200}],  # totals
            [{"_id": "gpt-4o", "cost": 0.072}],  # cost_by_model
            [{"_id": "2026-07-02T09:00Z", "count": 9}],  # timeline
        ]
        with mock.patch.object(mc, "_get_db", return_value={mc._EVENTS: fake_coll}):
            out = mc.report_summary(datetime.now(timezone.utc), datetime.now(timezone.utc))
        self.assertEqual(out["by_alertname"]["PodRestart"]["incoming"], 5)
        self.assertEqual(out["by_alertname"]["PodRestart"]["rca"], 4)
        self.assertAlmostEqual(out["by_alertname"]["PodRestart"]["cost_usd"], 0.072, places=4)
        self.assertEqual(out["totals"]["events"], 9)
        self.assertAlmostEqual(out["totals"]["cost_usd"], 0.072, places=4)
        self.assertEqual(out["cost_by_model"]["gpt-4o"], 0.072)
        self.assertEqual(out["timeline"], [{"hour": "2026-07-02T09:00Z", "count": 9}])


if __name__ == "__main__":
    unittest.main()
