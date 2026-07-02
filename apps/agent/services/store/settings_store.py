"""Read-only MongoDB settings loader for the Python agent runtime.

Admin CRUD lives in the Next.js app; this module lets each agent replica
load the same settings documents and hot-apply them via config_sync.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import config as _cfg

_db = None
_import_failed = False


def _get_db():
    global _db, _import_failed
    if _db is not None:
        return _db
    if _import_failed or not getattr(_cfg, "MONGO_URL", ""):
        return None
    try:
        from pymongo import MongoClient
    except Exception:
        _import_failed = True
        return None
    try:
        client = MongoClient(_cfg.MONGO_URL, serverSelectionTimeoutMS=2000, tz_aware=True)
        _db = client[_cfg.MONGO_DB]
        return _db
    except Exception:
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


def get_settings_version() -> int:
    db = _get_db()
    if db is None:
        return 0
    try:
        doc = db.settings_meta.find_one({"_id": "version"})
        return int(doc.get("version", 0)) if doc else 0
    except Exception:
        return 0


def load_agent_settings() -> dict[str, Any]:
    try:
        from services.transport import config_cache

        cached = config_cache.get_agent_settings()
        if cached:
            return cached
    except Exception:
        pass
    db = _get_db()
    if db is None:
        return {}
    try:
        doc = db.agent_settings.find_one({"_id": "runtime"}) or {}
        return {k: v for k, v in doc.items() if k != "_id"}
    except Exception:
        return {}


def list_endpoints() -> list[dict[str, Any]]:
    try:
        from services.transport import config_cache

        cached = config_cache.get_endpoints()
        if cached:
            return cached
    except Exception:
        pass
    db = _get_db()
    if db is None:
        return []
    try:
        return [
            {k: v for k, v in doc.items() if k != "_id"}
            for doc in db.endpoints.find({}).sort("name", 1)
        ]
    except Exception:
        return []


def list_environments() -> list[dict[str, Any]]:
    try:
        from services.transport import config_cache

        cached = config_cache.get_environments()
        if cached:
            return cached
    except Exception:
        pass
    db = _get_db()
    if db is None:
        return []
    try:
        return [
            {k: v for k, v in doc.items() if k != "_id"}
            for doc in db.environments.find({}).sort("name", 1)
        ]
    except Exception:
        return []


def load_routing_config() -> dict[str, Any]:
    try:
        from services.transport import config_cache

        cached = config_cache.get_routing_config()
        if cached:
            return cached
    except Exception:
        pass
    db = _get_db()
    if db is None:
        return {}
    try:
        meta = db.routing_settings.find_one({"_id": "meta"}) or {}
        rules = list(db.routing_rules.find({}).sort("order", 1))
        routes = []
        for r in rules:
            item = {k: v for k, v in r.items() if k not in ("_id", "id", "order")}
            routes.append(item)
        return {
            "default_slack_webhook_url": meta.get("default_slack_webhook_url", ""),
            "routes": routes,
        }
    except Exception:
        return {}


def load_silences_config() -> dict[str, Any]:
    try:
        from services.transport import config_cache

        cached = config_cache.get_silences_config()
        if cached:
            return cached
    except Exception:
        pass
    db = _get_db()
    if db is None:
        return {"silences": {"active": [], "disabled": []}}
    try:
        active = []
        disabled = []
        for doc in db.silences.find({}):
            item = {k: v for k, v in doc.items() if k not in ("_id", "status")}
            if doc.get("status") == "disabled":
                disabled.append(item)
            else:
                active.append(item)
        return {"silences": {"active": active, "disabled": disabled}}
    except Exception:
        return {"silences": {"active": [], "disabled": []}}


def load_time_intervals_config() -> dict[str, Any]:
    db = _get_db()
    if db is None:
        return {"time_intervals": []}
    try:
        intervals = [
            {k: v for k, v in doc.items() if k not in ("_id", "order")}
            for doc in db.time_intervals.find({}).sort("order", 1)
        ]
        return {"time_intervals": intervals}
    except Exception:
        return {"time_intervals": []}


def settings_updated_at() -> datetime | None:
    db = _get_db()
    if db is None:
        return None
    try:
        doc = db.settings_meta.find_one({"_id": "version"})
        ts = doc.get("updated_at") if doc else None
        return ts if isinstance(ts, datetime) else None
    except Exception:
        return None
