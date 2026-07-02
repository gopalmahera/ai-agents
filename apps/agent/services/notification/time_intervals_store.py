"""Persist and load named time intervals (Alertmanager-style)."""

from __future__ import annotations

import os
from typing import Any

import yaml

import services.store.settings_store as _settings_store
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

    data = _settings_store.load_time_intervals_config()
    if data.get("time_intervals") is not None:
        _config = data
        _engine.set_intervals(data.get("time_intervals"))
        count = len(data.get("time_intervals", []))
        print(f"[time_intervals] Loaded {count} named interval(s) from mongodb")
        return data

    text = None
    source = ""
    if os.path.exists(_CONFIG_PATH):
        with open(_CONFIG_PATH, encoding="utf-8") as fh:
            text = fh.read()
        source = _CONFIG_PATH

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
    raise ConfigStoreUnavailable("Time-interval writes are handled by the admin API (Next.js)")
