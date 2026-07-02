import sys
import unittest
from unittest.mock import MagicMock, patch

sys.modules.setdefault("requests", MagicMock())

import api.metrics_api as metrics_api
from app import app


class TestMetricsStats(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def _counts(self, **overrides):
        c = {k: 0 for k in metrics_api._COUNTER_KEYS}
        c.update(overrides)
        return c

    def test_stats_exposes_llm_cost_and_tokens(self):
        counts = self._counts(
            tokens_input=4000, tokens_output=800, tokens_total=4800,
            cost_micro_usd=18000,  # $0.018
        )
        with patch.object(metrics_api._redis, "counter_get_all", return_value=counts), \
             patch.object(metrics_api._redis, "alertname_counts", return_value={}), \
             patch.object(metrics_api._redis, "llm_cost_micro_by_model", return_value={"gpt-4o": 18000}):
            resp = self.client.get("/api/metrics/stats")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["llm_usage"]["input_tokens"], 4000)
        self.assertEqual(body["llm_usage"]["total_tokens"], 4800)
        self.assertAlmostEqual(body["llm_usage"]["cost_usd"], 0.018, places=4)
        self.assertAlmostEqual(body["cost_by_model"]["gpt-4o"], 0.018, places=4)

    def test_cost_by_model_degrades_gracefully(self):
        with patch.object(metrics_api._redis, "counter_get_all", return_value=self._counts()), \
             patch.object(metrics_api._redis, "alertname_counts", return_value={}), \
             patch.object(metrics_api._redis, "llm_cost_micro_by_model", side_effect=Exception("down")):
            resp = self.client.get("/api/metrics/stats")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["cost_by_model"], {})


class TestReports(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_summary_prefers_mongo_with_cost(self):
        mongo_summary = {
            "by_alertname": {"PodRestart": {"incoming": 5, "rca": 4, "cost_usd": 0.072}},
            "totals": {"events": 9, "cost_usd": 0.072, "total_tokens": 19200},
            "cost_by_model": {"gpt-4o": 0.072},
            "timeline": [{"hour": "2026-07-02T09:00Z", "count": 9}],
        }
        with patch.object(metrics_api._mongo, "report_summary", return_value=mongo_summary):
            resp = self.client.get("/api/reports/summary?days=7")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["source"], "mongo")
        self.assertEqual(body["files"], 9)  # 5 incoming + 4 rca
        self.assertAlmostEqual(body["totals"]["cost_usd"], 0.072, places=4)
        self.assertEqual(body["cost_by_model"]["gpt-4o"], 0.072)

    def test_summary_falls_back_to_redis_when_mongo_empty(self):
        redis_entries = [
            {"alertname": "PodRestart", "outcome": "accepted", "ts_ms": 1751446800000},
            {"alertname": "PodRestart", "outcome": "rca_success", "ts_ms": 1751446800000},
        ]
        with patch.object(metrics_api._mongo, "report_summary", return_value={}), \
             patch.object(metrics_api._redis, "stream_range", return_value=redis_entries):
            resp = self.client.get("/api/reports/summary?days=7")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["source"], "redis")
        self.assertEqual(body["by_alertname"]["PodRestart"]["incoming"], 1)

    def test_events_unavailable_when_mongo_off(self):
        with patch.object(metrics_api._mongo, "is_available", return_value=False):
            resp = self.client.get("/api/reports/events")
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.get_json()["available"])

    def test_events_returns_list_when_available(self):
        events = [{"ts": "2026-07-02T09:00:00+00:00", "alertname": "PodRestart", "outcome": "rca_success", "cost_usd": 0.018}]
        with patch.object(metrics_api._mongo, "is_available", return_value=True), \
             patch.object(metrics_api._mongo, "recent_events", return_value=events):
            resp = self.client.get("/api/reports/events?alertname=PodRestart&limit=10")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertTrue(body["available"])
        self.assertEqual(body["count"], 1)
        self.assertEqual(body["events"][0]["alertname"], "PodRestart")


if __name__ == "__main__":
    unittest.main()
