"""Runtime config store — Redis-backed so every agent replica sees the same values.

Source of truth is the Redis hash ``config:store``. The local
``web_config.json`` file is a seed/mirror: it populates Redis on first
boot (migration from older single-node setups) and keeps local dev
working when Redis is down.

Precedence: UI-stored value (Redis) > env var > built-in default.

MCP server URLs are intentionally NOT configurable here — the MCP
servers run inside the agent container on fixed localhost ports.
"""
import json
import os
import threading
from pathlib import Path

import config as _cfg
import services.store.redis_client as _redis

_lock = threading.Lock()

CONFIGURABLE_KEYS = [
    "AI_PROVIDER",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "LLM_ENABLED",
    "SLACK_WEBHOOK_URL",
    "PROMETHEUS_URL",
    "LOKI_URL",
    "LOGS_DIR",
    "DEDUP_TTL_SECONDS",
    "ALLOWED_ALERTNAMES",
    "ALERT_CATALOG_PATH",
    "ROUTING_CONFIG_PATH",
]

SENSITIVE_KEYS = {"OPENAI_API_KEY", "SLACK_WEBHOOK_URL"}

_DEFAULTS: dict = {
    "AI_PROVIDER": "openai",
    "OPENAI_MODEL": "gpt-4o",
    "OPENAI_API_KEY": "",
    "LLM_ENABLED": True,
    "SLACK_WEBHOOK_URL": "",
    "PROMETHEUS_URL": "http://service-gps.monitoring.svc.cluster.local:9090",
    "LOKI_URL": "http://localhost:3100",
    "LOGS_DIR": "/app/logs",
    "DEDUP_TTL_SECONDS": 900,
    "ALLOWED_ALERTNAMES": "",
    "ALERT_CATALOG_PATH": "/app/config/alert_catalog.yaml",
    "ROUTING_CONFIG_PATH": "",
}


def _store_path() -> Path:
    return Path(_cfg.CONFIG_STORE_PATH)


def _load_file() -> dict:
    p = _store_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[config_store] Failed to load {p}: {exc}")
        return {}


def _decode(raw: str):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def _load_store() -> dict:
    """Stored (UI-set) values — Redis first, local file when Redis is down."""
    try:
        raw = _redis.config_load()
        return {k: _decode(v) for k, v in raw.items() if k in CONFIGURABLE_KEYS}
    except Exception:
        return {k: v for k, v in _load_file().items() if k in CONFIGURABLE_KEYS}


def seed_redis_from_file() -> None:
    """One-time migration: push web_config.json into Redis if the store is empty."""
    stored = {k: v for k, v in _load_file().items() if k in CONFIGURABLE_KEYS}
    if not stored:
        return
    if not _redis.config_is_empty():
        return
    _redis.config_save({k: json.dumps(v) for k, v in stored.items()})
    print(f"[config_store] Seeded Redis config store from {_store_path()}")


def get_all() -> dict:
    """Return all configurable values (stored overrides env, env overrides defaults)."""
    stored = _load_store()
    result = {}
    for key in CONFIGURABLE_KEYS:
        env_val = os.environ.get(key)
        if key in stored:
            result[key] = stored[key]
        elif env_val is not None:
            result[key] = env_val
        else:
            result[key] = _DEFAULTS.get(key, "")
    return result


def get_masked() -> dict:
    """Like get_all() but sensitive values replaced with '***' if non-empty."""
    values = get_all()
    for key in SENSITIVE_KEYS:
        if values.get(key):
            values[key] = "***"
    return values


def update(updates: dict) -> dict:
    """Persist updates, notify other replicas, and apply to this process."""
    accepted = {k: v for k, v in updates.items() if k in CONFIGURABLE_KEYS}
    if not accepted:
        return get_masked()

    with _lock:
        # Shared store — other replicas pick this up via config:events
        try:
            _redis.config_save({k: json.dumps(v) for k, v in accepted.items()})
            _redis.publish_config_event("config")
        except Exception as exc:
            print(f"[config_store] Redis unavailable — saved locally only: {exc}")

        # Local mirror: seeds Redis on cold start, fallback when Redis is down
        stored = _load_file()
        stored.update(accepted)
        p = _store_path()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(stored, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"[config_store] Failed to write {p}: {exc}")

        for key, value in accepted.items():
            _apply_live(key, value)

    return get_masked()


def apply_stored() -> None:
    """Apply every stored value to this process (used by the sync thread)."""
    for key, value in _load_store().items():
        _apply_live(key, value)


def _apply_live(key: str, value) -> None:
    """Apply config change to live process without restart where safe."""
    import re

    import config as cfg
    str_val = str(value)

    if key == "LLM_ENABLED":
        cfg.LLM_ENABLED = str(value).lower() in ("1", "true", "yes", "True", True)
    elif key == "DEDUP_TTL_SECONDS":
        try:
            cfg.DEDUP_TTL_SECONDS = int(value)
        except (ValueError, TypeError):
            pass
    elif key == "ALLOWED_ALERTNAMES":
        try:
            cfg._allowed_alertname_pattern = re.compile(str_val) if str_val else None
        except re.error as exc:
            print(f"[config_store] Invalid ALLOWED_ALERTNAMES regex {str_val!r}: {exc}")
            return
        cfg.ALLOWED_ALERTNAMES = str_val
        os.environ[key] = str_val
    elif key in ("OPENAI_API_KEY", "OPENAI_MODEL", "AI_PROVIDER", "SLACK_WEBHOOK_URL",
                 "PROMETHEUS_URL", "LOKI_URL", "LOGS_DIR",
                 "ALERT_CATALOG_PATH", "ROUTING_CONFIG_PATH"):
        setattr(cfg, key, str_val)
        os.environ[key] = str_val
