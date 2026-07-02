import unittest
from unittest import mock

import services.config_sync as sync


class TestConfigSync(unittest.TestCase):
    def setUp(self):
        sync._applied_version = -1
        self.addCleanup(setattr, sync, "_applied_version", -1)

    def test_applies_when_version_changes(self):
        with mock.patch.object(sync._redis, "config_version", return_value=3), \
             mock.patch.object(sync.config_store, "apply_stored") as apply_stored:
            sync._apply_if_newer()
        apply_stored.assert_called_once()
        self.assertEqual(sync._applied_version, 3)

    def test_skips_when_version_unchanged(self):
        sync._applied_version = 3
        with mock.patch.object(sync._redis, "config_version", return_value=3), \
             mock.patch.object(sync.config_store, "apply_stored") as apply_stored:
            sync._apply_if_newer()
        apply_stored.assert_not_called()

    def test_force_applies_even_when_current(self):
        sync._applied_version = 3
        with mock.patch.object(sync._redis, "config_version", return_value=3), \
             mock.patch.object(sync.config_store, "apply_stored") as apply_stored:
            sync._apply_if_newer(force=True)
        apply_stored.assert_called_once()

    def test_apply_resets_routing_cache(self):
        from services.notification import routing
        with mock.patch.object(sync.config_store, "apply_stored"), \
             mock.patch.object(routing, "reset_cache") as reset:
            sync._apply(7)
        reset.assert_called_once()
        self.assertEqual(sync._applied_version, 7)

    def test_version_not_advanced_when_apply_raises(self):
        # Redis blip during apply_stored must NOT burn the version, or the
        # replica would skip this update forever.
        sync._applied_version = 5
        with mock.patch.object(sync._redis, "config_version", return_value=9), \
             mock.patch.object(sync.config_store, "apply_stored", side_effect=Exception("redis down")):
            with self.assertRaises(Exception):
                sync._apply_if_newer()
        self.assertEqual(sync._applied_version, 5)  # unchanged → retried later

    def test_start_is_idempotent(self):
        with mock.patch.object(sync.threading, "Thread") as thread_cls:
            sync._started = False
            self.addCleanup(setattr, sync, "_started", False)
            sync.start()
            sync.start()
        self.assertEqual(thread_cls.call_count, 1)


if __name__ == "__main__":
    unittest.main()
