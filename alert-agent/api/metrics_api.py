"""API endpoints for metrics and reports — backed by Redis."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request

from api.auth import require_auth
import services.store.redis_client as _redis

bp = Blueprint("metrics_api", __name__, url_prefix="/api")

_COUNTER_KEYS = [
    "alerts_received",
    "alerts_accepted",
    "alerts_deduplicated",
    "alerts_skipped",
    "alerts_silenced",
    "queue_full",
    "llm_success",
    "llm_fallback",
    "llm_error",
    "slack_success",
    "slack_error",
]


@bp.get("/metrics/stats")
@require_auth
def metrics_stats():
    try:
        counts = _redis.counter_get_all(_COUNTER_KEYS)
        by_alertname = _redis.alertname_counts()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    return jsonify({
        "alerts_received": counts["alerts_received"],
        "alerts_accepted": counts["alerts_accepted"],
        "alerts_deduplicated": counts["alerts_deduplicated"],
        "alerts_skipped": counts["alerts_skipped"],
        "alerts_silenced": counts["alerts_silenced"],
        "queue_full": counts["queue_full"],
        "llm_investigations": {
            "success": counts["llm_success"],
            "fallback": counts["llm_fallback"],
            "error": counts["llm_error"],
        },
        "slack_posts": {
            "success": counts["slack_success"],
            "error": counts["slack_error"],
        },
        "by_alertname": by_alertname,
    })


@bp.get("/reports/summary")
@require_auth
def reports_summary():
    """Aggregate alert stats from Redis stream (last 7 days by default)."""
    days = int(request.args.get("days", 7))
    since_ms = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    start = f"{since_ms}-0"

    try:
        entries = _redis.stream_range(start=start, count=50_000)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    by_alertname: dict[str, dict] = defaultdict(lambda: {"rca": 0, "incoming": 0})
    hourly: dict[str, int] = defaultdict(int)

    for entry in entries:
        alertname = entry.get("alertname", "unknown")
        outcome = entry.get("outcome", "")
        ts_ms = entry.get("ts_ms", 0)

        if outcome == "rca_success" or outcome == "rca_slack_error":
            by_alertname[alertname]["rca"] += 1
        elif outcome == "accepted":
            by_alertname[alertname]["incoming"] += 1

        if ts_ms:
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            hour_key = dt.strftime("%Y-%m-%dT%H:00Z")
            hourly[hour_key] += 1

    timeline = [{"hour": h, "count": c} for h, c in sorted(hourly.items())]
    total = sum(v["rca"] + v["incoming"] for v in by_alertname.values())

    return jsonify({
        "files": total,
        "by_alertname": dict(by_alertname),
        "timeline": timeline,
        "days": days,
    })


@bp.get("/redis/health")
@require_auth
def redis_health():
    available = _redis.is_available()
    return jsonify({"status": "ok" if available else "unavailable"}), (200 if available else 503)
