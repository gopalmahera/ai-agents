import json
import logging
import unittest

from utils.log import JsonFormatter


class TestJsonFormatter(unittest.TestCase):
    def _format(self, level, msg, **extra):
        record = logging.LogRecord(
            name="test", level=level, pathname=__file__, lineno=1,
            msg=msg, args=(), exc_info=None,
        )
        for k, v in extra.items():
            setattr(record, k, v)
        return json.loads(JsonFormatter().format(record))

    def test_core_fields(self):
        out = self._format(logging.INFO, "hello")
        self.assertEqual(out["level"], "INFO")
        self.assertEqual(out["logger"], "test")
        self.assertEqual(out["message"], "hello")
        self.assertIn("ts", out)

    def test_emits_arbitrary_extra_fields(self):
        # Fields outside the old allowlist (version, silence_id, retry_seconds)
        # must now appear in the payload.
        out = self._format(
            logging.WARNING, "sync",
            event="config_sync", version=7, silence_id="s-1", retry_seconds=5,
        )
        self.assertEqual(out["event"], "config_sync")
        self.assertEqual(out["version"], 7)
        self.assertEqual(out["silence_id"], "s-1")
        self.assertEqual(out["retry_seconds"], 5)

    def test_non_serializable_extra_is_coerced(self):
        out = self._format(logging.INFO, "obj", thing=object())
        self.assertIsInstance(out["thing"], str)

    def test_exception_included(self):
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record = logging.LogRecord(
                name="t", level=logging.ERROR, pathname=__file__, lineno=1,
                msg="failed", args=(), exc_info=sys.exc_info(),
            )
            out = json.loads(JsonFormatter().format(record))
        self.assertIn("exception", out)
        self.assertIn("boom", out["exception"])


if __name__ == "__main__":
    unittest.main()
