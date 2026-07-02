"""Structured JSON logging for the alert agent."""
import json
import logging
import os
import sys
from datetime import datetime, timezone

# Standard LogRecord attributes — everything else in record.__dict__ is a
# caller-supplied `extra` field and should be emitted in the JSON payload.
_RESERVED = set(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message", "asctime", "taskName"}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include every extra field (event, version, silence_id, retry_seconds, …).
        for key, value in record.__dict__.items():
            if key in _RESERVED or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # default=str coerces any non-JSON-serializable extra value.
        return json.dumps(payload, ensure_ascii=False, default=str)


_configured = False


def setup_logging() -> None:
    global _configured
    if _configured:
        return
    _configured = True
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    # Replace any pre-existing root handlers (e.g. installed by gunicorn or an
    # earlier basicConfig) so app logs are always JSON. Gunicorn's own access/
    # error logs use separate named loggers and are unaffected.
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
