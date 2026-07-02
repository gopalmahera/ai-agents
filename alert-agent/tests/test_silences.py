import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from services.notification import silences


class TestSilences(unittest.TestCase):
    def setUp(self):
        silences.reset_cache()

    def _cfg(self, active, disabled=None):
        return {"silences": {"active": active, "disabled": disabled or []}}

    def test_permanent_silence_matches(self):
        with mock.patch.object(silences, "_load_config", return_value=self._cfg([
            {
                "id": "s1",
                "mode": "permanent",
                "match": {"severity": "critical"},
            }
        ])):
            silenced, sid = silences.is_silenced({"severity": "critical", "alertname": "X"})
        self.assertTrue(silenced)
        self.assertEqual(sid, "s1")

    def test_until_silence_expires(self):
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        with mock.patch.object(silences, "_load_config", return_value=self._cfg([
            {"id": "future", "mode": "until", "ends_at": future, "match": {"stage": "prod"}},
            {"id": "past", "mode": "until", "ends_at": past, "match": {"stage": "sit"}},
        ])):
            self.assertTrue(silences.is_silenced({"stage": "prod"})[0])
            self.assertFalse(silences.is_silenced({"stage": "sit"})[0])

    def test_prune_expired_moves_to_disabled(self):
        past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
        cfg = self._cfg([
            {"id": "exp", "mode": "until", "ends_at": past, "match": {"severity": "warning"}},
        ])
        with mock.patch.object(silences, "_load_config", return_value=cfg), \
             mock.patch.object(silences, "_persist_config") as persist:
            changed = silences.prune_expired()
        self.assertTrue(changed)
        persist.assert_called_once()
        saved = persist.call_args[0][0]
        self.assertEqual(saved["silences"]["active"], [])
        self.assertEqual(len(saved["silences"]["disabled"]), 1)
        self.assertEqual(saved["silences"]["disabled"][0]["disabled_reason"], "expired")


import controllers.investigation_controller as inv_module


class TestInvestigateSilence(unittest.TestCase):
    @mock.patch.object(inv_module._silences, "is_silenced", return_value=(True, "s1"))
    def test_returns_none_when_silenced(self, _mock_silence):
        result = inv_module.investigate_alert(
            {"status": "firing", "labels": {"alertname": "X"}},
            skip_slack=True,
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
