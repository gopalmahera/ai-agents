"""API endpoints for metrics and reports — backed by Redis."""
from collections import defaultdict
from datetime import datetime, timezone, timedelta

from flask import Blueprint, jsonify, request

from api.auth import require_auth
import services.store.redis_client as _redis
import services.store.mongo_client as _mongo

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
    "tokens_input",
    "tokens_output",
    "tokens_total",
    "cost_micro_usd",
]


@bp.get("/metrics/stats")
@require_auth
def metrics_stats():
    try:
        counts = _redis.counter_get_all(_COUNTER_KEYS)
        by_alertname = _redis.alertname_counts()
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    try:
        cost_by_model = {
            m: round(micro / 1_000_000, 4)
            for m, micro in _redis.llm_cost_micro_by_model().items()
        }
    except Exception:
        cost_by_model = {}

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
        "llm_usage": {
            "input_tokens": counts["tokens_input"],
            "output_tokens": counts["tokens_output"],
            "total_tokens": counts["tokens_total"],
            "cost_usd": round(counts["cost_micro_usd"] / 1_000_000, 4),
        },
        "cost_by_model": cost_by_model,
        "by_alertname": by_alertname,
    })


@bp.get("/reports/summary")
@require_auth
def reports_summary():
    """Aggregate alert stats for the last N days.

    Prefers MongoDB (durable, adds cost + unbounded range); falls back to the
    Redis stream (capped ~50k events) when Mongo is not configured/available.
    """
    days = int(request.args.get("days", 7))
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=days)

    # Preferred: Mongo (richer — includes cost)
    try:
        mongo = _mongo.report_summary(start_dt, now)
    except Exception:
        mongo = {}
    if mongo:
        total = sum(v["rca"] + v["incoming"] for v in mongo["by_alertname"].values())
        return jsonify({
            "source": "mongo",
            "files": total,
            "by_alertname": mongo["by_alertname"],
            "timeline": mongo["timeline"],
            "totals": mongo["totals"],
            "cost_by_model": mongo["cost_by_model"],
            "days": days,
        })

    # Fallback: Redis stream
    since_ms = int(start_dt.timestamp() * 1000)
    try:
        entries = _redis.stream_range(start=f"{since_ms}-0", count=50_000)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500

    by_alertname: dict[str, dict] = defaultdict(lambda: {"rca": 0, "incoming": 0})
    hourly: dict[str, int] = defaultdict(int)
    for entry in entries:
        alertname = entry.get("alertname", "unknown")
        outcome = entry.get("outcome", "")
        ts_ms = entry.get("ts_ms", 0)
        if outcome in ("rca_success", "rca_slack_error"):
            by_alertname[alertname]["rca"] += 1
        elif outcome == "accepted":
            by_alertname[alertname]["incoming"] += 1
        if ts_ms:
            dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
            hourly[dt.strftime("%Y-%m-%dT%H:00Z")] += 1

    timeline = [{"hour": h, "count": c} for h, c in sorted(hourly.items())]
    total = sum(v["rca"] + v["incoming"] for v in by_alertname.values())
    return jsonify({
        "source": "redis",
        "files": total,
        "by_alertname": dict(by_alertname),
        "timeline": timeline,
        "days": days,
    })


@bp.get("/reports/events")
@require_auth
def reports_events():
    """Browsable, filtered, paginated alert-event history (MongoDB-backed)."""
    days = int(request.args.get("days", 7))
    now = datetime.now(timezone.utc)
    start_dt = now - timedelta(days=days)
    alertname = request.args.get("alertname") or None
    outcome = request.args.get("outcome") or None
    limit = min(int(request.args.get("limit", 100)), 1000)
    skip = max(int(request.args.get("skip", 0)), 0)

    if not _mongo.is_available():
        return jsonify({"available": False, "events": [], "reason": "MongoDB history store not configured"}), 200
    events = _mongo.recent_events(start_dt, now, alertname=alertname, outcome=outcome, limit=limit, skip=skip)
    return jsonify({"available": True, "events": events, "count": len(events)})


@bp.get("/redis/health")
@require_auth
def redis_health():
    available = _redis.is_available()
    return jsonify({"status": "ok" if available else "unavailable"}), (200 if available else 503)


@bp.get("/mongo/health")
@require_auth
def mongo_health():
    import config as _cfg
    if not _cfg.MONGO_URL:
        return jsonify({"status": "disabled"}), 200
    available = _mongo.is_available()
    return jsonify({"status": "ok" if available else "unavailable"}), (200 if available else 503)
