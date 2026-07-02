"""Persist and load named time intervals (Alertmanager-style)."""

from __future__ import annotations

import os
from typing import Any

import yaml

import services.store.redis_client as _redis
from services.notification import time_intervals as _engine

_CONFIG_PATH = os.getenv("TIME_INTERVALS_CONFIG_PATH", "/app/config/time_intervals.yaml")
_config: dict[str, Any] | None = None


def _default_config() -> dict[str, Any]:
    return {"time_intervals": []}


def _load_config() -> dict[str, Any]:
    global _config
    if _config is not None:
        return _config

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
        _config = _default_config()
        _engine.set_intervals([])
        return _config

    _config = yaml.safe_load(text) or _default_config()
    if "time_intervals" not in _config:
        _config["time_intervals"] = []

    _engine.set_intervals(_config.get("time_intervals"))
    count = len(_config.get("time_intervals", []))
    print(f"[time_intervals] Loaded {count} named interval(s) from {source}")
    return _config


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
    global _config
    _config = body
    yaml_text = yaml.safe_dump(body, default_flow_style=False, allow_unicode=True)
    try:
        _redis.time_intervals_yaml_save(yaml_text)
        _redis.publish_config_event("time_intervals")
    except Exception as exc:
        print(f"[time_intervals] Redis save failed: {exc}")
    try:
        os.makedirs(os.path.dirname(_CONFIG_PATH) or ".", exist_ok=True)
        with open(_CONFIG_PATH, "w", encoding="utf-8") as fh:
            fh.write(yaml_text)
    except Exception as exc:
        print(f"[time_intervals] File save failed: {exc}")
    reset_cache()
    _load_config()
