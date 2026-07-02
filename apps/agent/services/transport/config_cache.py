"""In-memory settings cache refreshed from API Socket.IO events."""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_cache: dict[str, Any] = {}
_version: int = 0


def update(config: dict[str, Any], version: int | None = None) -> None:
    global _cache, _version
    with _lock:
        _cache = dict(config or {})
        if version is not None:
            _version = int(version)


def get_snapshot() -> dict[str, Any]:
    with _lock:
        return dict(_cache)


def get_version() -> int:
    with _lock:
        return _version


def get_agent_settings() -> dict[str, Any]:
    with _lock:
        return dict(_cache.get("agent") or {})


def get_routing_config() -> dict[str, Any]:
    with _lock:
        return dict(_cache.get("routing") or {})


def get_silences_config() -> dict[str, Any]:
    with _lock:
        return dict(_cache.get("silences") or {})


def get_endpoints() -> list[dict[str, Any]]:
    with _lock:
        return list(_cache.get("endpoints") or [])


def get_environments() -> list[dict[str, Any]]:
    with _lock:
        return list(_cache.get("environments") or [])
