"""API endpoints for browsing and reading log files."""
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file

import config as _cfg
from api.auth import require_auth

bp = Blueprint("logs_api", __name__, url_prefix="/api/logs")

_TS_RE = re.compile(r'^(\d{8}T\d{6}Z)')
_SAFE_NAME_RE = re.compile(r'^[\w.\-]+$')


def _log_entry(f: Path) -> dict:
    name = f.name
    ts_match = _TS_RE.match(name)
    ts_str = ts_match.group(1) if ts_match else ""
    try:
        dt = datetime.strptime(ts_str, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        iso = dt.isoformat()
    except ValueError:
        iso = ""

    if "_incoming_" in name:
        log_type = "incoming"
        alertname = name[len(ts_str) + len("_incoming_"):].rsplit(".", 1)[0]
    else:
        log_type = "rca"
        rest = name[len(ts_str) + 1:] if ts_str else name
        alertname = rest.split("_")[0]

    return {
        "name": name,
        "type": log_type,
        "alertname": alertname,
        "timestamp": iso,
        "size": f.stat().st_size,
    }


@bp.get("")
@require_auth
def list_logs():
    logs_dir = Path(_cfg.LOGS_DIR)
    if not logs_dir.exists():
        return jsonify([])

    q = request.args.get("q", "").lower()
    log_type = request.args.get("type", "")
    limit = int(request.args.get("limit", "100"))

    files = sorted(
        (f for f in logs_dir.iterdir() if f.is_file()),
        key=lambda f: f.stat().st_mtime,
        reverse=True,
    )

    entries = []
    for f in files:
        entry = _log_entry(f)
        if q and q not in entry["alertname"].lower() and q not in f.name.lower():
            continue
        if log_type and entry["type"] != log_type:
            continue
        entries.append(entry)
        if len(entries) >= limit:
            break

    return jsonify(entries)


@bp.get("/<filename>")
@require_auth
def get_log(filename: str):
    if not _SAFE_NAME_RE.match(filename):
        return jsonify({"error": "Invalid filename"}), 400

    log_file = Path(_cfg.LOGS_DIR) / filename
    if not log_file.exists():
        return jsonify({"error": "Not found"}), 404

    content = log_file.read_text(encoding="utf-8", errors="replace")
    return jsonify({"name": filename, "content": content})


@bp.delete("/<filename>")
@require_auth
def delete_log(filename: str):
    if not _SAFE_NAME_RE.match(filename):
        return jsonify({"error": "Invalid filename"}), 400

    log_file = Path(_cfg.LOGS_DIR) / filename
    if not log_file.exists():
        return jsonify({"error": "Not found"}), 404

    log_file.unlink()
    return jsonify({"status": "deleted"})
