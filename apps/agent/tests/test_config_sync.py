import unittest

import services.config_sync as sync


class TestConfigSync(unittest.TestCase):
    def test_start_is_idempotent(self):
        sync._started = False
        self.addCleanup(setattr, sync, "_started", False)
        sync.start()
        sync.start()
        self.assertTrue(sync._started)


if __name__ == "__main__":
    unittest.main()
