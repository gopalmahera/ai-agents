import unittest
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.notification import time_intervals


class TestTimeIntervals(unittest.TestCase):
    def setUp(self):
        time_intervals.set_intervals(
            [
                {
                    "name": "weeknights",
                    "time_intervals": [
                        {
                            "weekdays": ["monday", "tuesday", "wednesday", "thursday", "friday"],
                            "times": [{"start_time": "22:00", "end_time": "06:00"}],
                            "location": "UTC",
                        }
                    ],
                },
                {
                    "name": "always",
                    "time_intervals": [{"weekdays": ["monday"], "times": [], "location": "UTC"}],
                },
            ]
        )

    def tearDown(self):
        time_intervals.reset_cache()

    def test_active_during_overnight_window(self):
        now = datetime(2026, 7, 6, 23, 0, tzinfo=timezone.utc)  # Monday
        self.assertTrue(time_intervals.is_interval_active("weeknights", now))

    def test_inactive_outside_window(self):
        now = datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc)  # Monday noon
        self.assertFalse(time_intervals.is_interval_active("weeknights", now))

    def test_respects_timezone(self):
        time_intervals.set_intervals(
            [
                {
                    "name": "india_morning",
                    "time_intervals": [
                        {
                            "weekdays": ["monday"],
                            "times": [{"start_time": "09:00", "end_time": "10:00"}],
                            "location": "Asia/Kolkata",
                        }
                    ],
                }
            ]
        )
        # 03:30 UTC = 09:00 IST on Monday
        now = datetime(2026, 7, 6, 3, 30, tzinfo=timezone.utc)
        self.assertTrue(time_intervals.is_interval_active("india_morning", now))

    def test_unknown_interval(self):
        self.assertFalse(time_intervals.is_interval_active("missing"))


if __name__ == "__main__":
    unittest.main()
