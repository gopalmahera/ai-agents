import unittest

from services.notification.silences_validation import validate_silences_body
from services.notification.time_intervals_validation import validate_time_intervals_body


class TestSilencesValidation(unittest.TestCase):
    def test_valid_silence(self):
        errors = validate_silences_body(
            {
                "silences": {
                    "active": [
                        {
                            "id": "abc",
                            "mode": "permanent",
                            "match": {"severity": "critical"},
                        }
                    ],
                    "disabled": [],
                },
            }
        )
        self.assertEqual(errors, [])

    def test_rejects_until_without_ends_at(self):
        errors = validate_silences_body(
            {
                "silences": {
                    "active": [
                        {"id": "abc", "mode": "until", "match": {"severity": "critical"}},
                    ],
                    "disabled": [],
                },
            }
        )
        self.assertTrue(any("ends_at" in e for e in errors))


class TestTimeIntervalsValidation(unittest.TestCase):
    def test_valid_interval(self):
        errors = validate_time_intervals_body(
            {
                "time_intervals": [
                    {
                        "name": "night",
                        "time_intervals": [
                            {
                                "weekdays": ["monday"],
                                "times": [{"start_time": "22:00", "end_time": "06:00"}],
                                "location": "UTC",
                            }
                        ],
                    }
                ],
            }
        )
        self.assertEqual(errors, [])

    def test_rejects_duplicate_names(self):
        errors = validate_time_intervals_body(
            {
                "time_intervals": [
                    {"name": "night", "time_intervals": [{"times": [{"start_time": "22:00", "end_time": "06:00"}]}]},
                    {"name": "night", "time_intervals": [{"times": [{"start_time": "22:00", "end_time": "06:00"}]}]},
                ],
            }
        )
        self.assertTrue(any("duplicate" in e.lower() for e in errors))


if __name__ == "__main__":
    unittest.main()
