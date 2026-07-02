import json
import re
from datetime import datetime, timezone
from pathlib import Path

from config import LOGS_DIR


def _sanitize_filename(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", value.strip())
    return cleaned.strip("_") or "unknown"


def log_incoming_payload(payload: dict) -> Path:
    """Log the raw Alertmanager webhook payload to stdout and to a file."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    formatted = json.dumps(payload, indent=2, ensure_ascii=False)

    # Console log — same format as received
    print(f"[{timestamp}] INCOMING ALERTMANAGER PAYLOAD:\n{formatted}")

    # File log
    logs_path = Path(LOGS_DIR)
    logs_path.mkdir(parents=True, exist_ok=True)

    alertname = (
        (payload.get("commonLabels") or {}).get("alertname")
        or (payload.get("alerts") or [{}])[0].get("labels", {}).get("alertname")
        or "unknown"
    )
    filename = f"{timestamp}_incoming_{_sanitize_filename(alertname)}.json"
    log_file = logs_path / filename
    log_file.write_text(formatted + "\n", encoding="utf-8")
    return log_file


def save_rca(alert: dict, rca: str) -> Path:
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")
    pod = labels.get("pod", "unknown")
    fingerprint = alert.get("fingerprint", "")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    parts = [_sanitize_filename(alertname)]
    if pod:
        parts.append(_sanitize_filename(pod))
    if fingerprint:
        parts.append(_sanitize_filename(fingerprint)[:12])

    filename = f"{timestamp}_{'_'.join(parts)}.log"
    logs_path = Path(LOGS_DIR)
    logs_path.mkdir(parents=True, exist_ok=True)

    log_file = logs_path / filename
    log_file.write_text(rca.strip() + "\n", encoding="utf-8")
    return log_file
