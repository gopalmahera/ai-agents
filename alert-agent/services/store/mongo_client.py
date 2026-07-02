"""MongoDB — durable, queryable alert-event history and cost analytics.

Redis stays the source of truth for the hot path (dedup, counters, config
sync). Mongo is an ADDITIVE history store: every alert event is dual-written
here so reports can span arbitrary date ranges with rich aggregation
(by alertname, cost over time, per-model spend) instead of scanning a capped
Redis stream in-process.

Fully optional and best-effort:
- If ``MONGO_URL`` is unset, every function is a no-op / empty result.
- If Mongo (or pymongo) is unavailable, writes are dropped with a warning and
  reads return empty — alert processing is never affected.

Collection ``alert_events`` document::

    {ts, alertname, namespace, fingerprint, outcome, severity,
     model, input_tokens, output_tokens, total_tokens, cost_usd}
"""
from datetime import datetime, timezone

import config as _cfg
from utils.log import get_logger

logger = get_logger(__name__)

_EVENTS = "alert_events"
_db = None
_import_failed = False


def _get_db():
    global _db, _import_failed
    if _db is not None:
        return _db
    if _import_failed or not _cfg.MONGO_URL:
        return None
    try:
        from pymongo import ASCENDING, DESCENDING, MongoClient
    except Exception as exc:  # pymongo not installed
        _import_failed = True
        logger.warning("pymongo unavailable; history store disabled", extra={"event": "mongo_disabled", "error": str(exc)})
        return None
    try:
        client = MongoClient(_cfg.MONGO_URL, serverSelectionTimeoutMS=2000, tz_aware=True)
        db = client[_cfg.MONGO_DB]
        db[_EVENTS].create_index([("ts", DESCENDING)])
        db[_EVENTS].create_index([("alertname", ASCENDING), ("ts", DESCENDING)])
        db[_EVENTS].create_index([("outcome", ASCENDING), ("ts", DESCENDING)])
        _db = db
        return _db
    except Exception as exc:
        # Connection/index errors here shouldn't latch — MongoClient reconnects.
        logger.warning("Mongo init failed", extra={"event": "mongo_init_error", "error": str(exc)})
        return None


def is_available() -> bool:
    db = _get_db()
    if db is None:
        return False
    try:
        db.command("ping")
        return True
    except Exception:
        return False


def record_event(**fields) -> None:
    """Best-effort insert of one alert event. Never raises."""
    db = _get_db()
    if db is None:
        return
    try:
        doc = {"ts": datetime.now(timezone.utc)}
        doc.update({k: v for k, v in fields.items() if v is not None and v != ""})
        db[_EVENTS].insert_one(doc)
    except Exception as exc:
        logger.warning("Mongo record_event failed", extra={"event": "mongo_write_error", "error": str(exc)})


# ── Reports ───────────────────────────────────────────────────────────────────

_RCA_OUTCOMES = ("rca_success", "rca_slack_error")


def report_summary(start: datetime, end: datetime) -> dict:
    """Aggregate events in [start, end]: per-alertname counts + cost, totals,
    cost-by-model, and an hourly timeline. Returns {} if Mongo is unavailable."""
    db = _get_db()
    if db is None:
        return {}
    match = {"ts": {"$gte": start, "$lte": end}}

    by_alertname: dict[str, dict] = {}
    for row in db[_EVENTS].aggregate([
        {"$match": match},
        {"$group": {
            "_id": {"alertname": "$alertname", "outcome": "$outcome"},
            "count": {"$sum": 1},
            "cost": {"$sum": {"$ifNull": ["$cost_usd", 0]}},
        }},
    ]):
        name = row["_id"].get("alertname") or "unknown"
        outcome = row["_id"].get("outcome") or ""
        entry = by_alertname.setdefault(name, {"incoming": 0, "rca": 0, "cost_usd": 0.0})
        if outcome == "accepted":
            entry["incoming"] += row["count"]
        elif outcome in _RCA_OUTCOMES:
            entry["rca"] += row["count"]
        entry["cost_usd"] = round(entry["cost_usd"] + float(row.get("cost", 0) or 0), 6)

    totals = {"events": 0, "cost_usd": 0.0, "total_tokens": 0}
    for row in db[_EVENTS].aggregate([
        {"$match": match},
        {"$group": {
            "_id": None,
            "events": {"$sum": 1},
            "cost": {"$sum": {"$ifNull": ["$cost_usd", 0]}},
            "tokens": {"$sum": {"$ifNull": ["$total_tokens", 0]}},
        }},
    ]):
        totals = {
            "events": row["events"],
            "cost_usd": round(float(row.get("cost", 0) or 0), 6),
            "total_tokens": int(row.get("tokens", 0) or 0),
        }

    cost_by_model: dict[str, float] = {}
    for row in db[_EVENTS].aggregate([
        {"$match": {**match, "model": {"$exists": True}}},
        {"$group": {"_id": "$model", "cost": {"$sum": {"$ifNull": ["$cost_usd", 0]}}}},
    ]):
        if row["_id"]:
            cost_by_model[row["_id"]] = round(float(row.get("cost", 0) or 0), 6)

    timeline = []
    for row in db[_EVENTS].aggregate([
        {"$match": match},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%dT%H:00Z", "date": "$ts", "timezone": "UTC"}},
            "count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]):
        timeline.append({"hour": row["_id"], "count": row["count"]})

    return {
        "by_alertname": by_alertname,
        "totals": totals,
        "cost_by_model": cost_by_model,
        "timeline": timeline,
    }


def recent_events(
    start: datetime,
    end: datetime,
    alertname: str | None = None,
    outcome: str | None = None,
    limit: int = 100,
    skip: int = 0,
) -> list[dict]:
    """Browsable, filtered, paginated event list (newest first)."""
    db = _get_db()
    if db is None:
        return []
    q: dict = {"ts": {"$gte": start, "$lte": end}}
    if alertname:
        q["alertname"] = alertname
    if outcome:
        q["outcome"] = outcome
    try:
        cursor = db[_EVENTS].find(q, {"_id": 0}).sort("ts", -1).skip(max(0, skip)).limit(min(limit, 1000))
        out = []
        for d in cursor:
            ts = d.get("ts")
            if isinstance(ts, datetime):
                d["ts"] = ts.astimezone(timezone.utc).isoformat()
            out.append(d)
        return out
    except Exception as exc:
        logger.warning("Mongo recent_events failed", extra={"event": "mongo_read_error", "error": str(exc)})
        return []
