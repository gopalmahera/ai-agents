"""Persist and load named time intervals (Alertmanager-style)."""

from __future__ import annotations

import os
from typing import Any

import yaml

import services.store.redis_client as _redis
from services.config_store import ConfigStoreUnavailable
from services.notification import time_intervals as _engine
from utils.fs import atomic_write_text
from utils.log import get_logger

logger = get_logger(__name__)

_CONFIG_PATH = os.getenv("TIME_INTERVALS_CONFIG_PATH", "/app/config/time_intervals.yaml")
_config: dict[str, Any] | None = None


def _default_config() -> dict[str, Any]:
    return {"time_intervals": []}


def _load_config() -> dict[str, Any]:
    global _config
    cached = _config
    if cached is not None:
        return cached

    text = None
    source = ""
    try:
        text = _redis.time_intervals_yaml_load()
        source = "redis"
    except Exception:
        text = None

    if not text and os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            text = fh.read()
        source = _CONFIG_PATH

    if not text:
        try:
            legacy = _redis.mute_yaml_load()
            if legacy:
                parsed = yaml.safe_load(legacy) or {}
                intervals = parsed.get("time_intervals")
                if intervals:
                    text = yaml.safe_dump({"time_intervals": intervals})
                    source = "redis (legacy mute)"
        except Exception:
            pass

    legacy_path = os.getenv("MUTE_CONFIG_PATH", "/app/config/mute_config.yaml")
    if not text and os.path.exists(legacy_path):
        with open(legacy_path, encoding="utf-8") as fh:
            parsed = yaml.safe_load(fh) or {}
        intervals = parsed.get("time_intervals")
        if intervals:
            text = yaml.safe_dump({"time_intervals": intervals})
            source = legacy_path

    if not text:
        data = _default_config()
        _config = data
        _engine.set_intervals([])
        return data

    data = yaml.safe_load(text) or _default_config()
    if "time_intervals" not in data:
        data["time_intervals"] = []

    _config = data
    _engine.set_intervals(data.get("time_intervals"))
    count = len(data.get("time_intervals", []))
    print(f"[time_intervals] Loaded {count} named interval(s) from {source}")
    return data


def reset_cache() -> None:
    global _config
    _config = None
    _engine.reset_cache()


def ensure_loaded() -> None:
    _load_config()


def get_config() -> dict[str, Any]:
    return _load_config()


def get_interval_names() -> list[str]:
    cfg = _load_config()
    return [
        (entry.get("name") or "").strip()
        for entry in cfg.get("time_intervals", [])
        if (entry.get("name") or "").strip()
    ]


def save_config(body: dict[str, Any]) -> None:
    """Persist named time intervals to Redis (required) and the file mirror.

    Raises ConfigStoreUnavailable if Redis is down so the endpoint returns 503;
    the cache is only refreshed after a successful save.
    """
    yaml_text = yaml.safe_dump(body, default_flow_style=False, allow_unicode=True)
    try:
        _redis.save_yaml_and_publish("time_intervals", yaml_text)
    except Exception as exc:
        raise ConfigStoreUnavailable(str(exc)) from exc
    try:
        atomic_write_text(_CONFIG_PATH, yaml_text)
    except Exception as exc:
        logger.warning("Time-intervals file mirror failed", extra={"event": "config_file_error", "error": str(exc)})
    reset_cache()
    _load_config()
