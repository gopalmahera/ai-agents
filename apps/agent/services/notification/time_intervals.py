"""Alertmanager-style named time intervals for mute schedules."""

from __future__ import annotations

from datetime import datetime, time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_WEEKDAYS = {
    "sunday": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
}

_intervals_by_name: dict[str, list[dict[str, Any]]] | None = None


def reset_cache() -> None:
    global _intervals_by_name
    _intervals_by_name = None


def set_intervals(time_intervals: list[dict[str, Any]] | None) -> None:
    """Load interval definitions from the time intervals config store."""
    global _intervals_by_name
    mapping: dict[str, list[dict[str, Any]]] = {}
    for entry in time_intervals or []:
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        mapping[name] = entry.get("time_intervals") or []
    _intervals_by_name = mapping


def _parse_time(value: str) -> time:
    parts = value.strip().split(":")
    if len(parts) != 2:
        raise ValueError(f"invalid time {value!r}, expected HH:MM")
    hour, minute = int(parts[0]), int(parts[1])
    return time(hour=hour, minute=minute)


def _time_in_range(now_t: time, start: time, end: time) -> bool:
    if start <= end:
        return start <= now_t <= end
    # Overnight span, e.g. 22:00–06:00
    return now_t >= start or now_t <= end


def _sub_interval_active(sub: dict[str, Any], now: datetime) -> bool:
    location = (sub.get("location") or "UTC").strip() or "UTC"
    try:
        tz = ZoneInfo(location)
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")

    local = now.astimezone(tz)
    weekdays = sub.get("weekdays")
    if weekdays:
        allowed = {_WEEKDAYS.get(str(day).lower()) for day in weekdays}
        allowed.discard(None)
        if local.weekday() not in allowed:
            return False

    times = sub.get("times") or []
    if not times:
        return True

    now_t = local.time().replace(second=0, microsecond=0)
    for slot in times:
        start = _parse_time(slot.get("start_time", "00:00"))
        end = _parse_time(slot.get("end_time", "23:59"))
        if _time_in_range(now_t, start, end):
            return True
    return False


def is_interval_active(name: str, now: datetime | None = None) -> bool:
    """Return True if any sub-interval for ``name`` is active at ``now``."""
    mapping = _intervals_by_name
    if mapping is None:
        from services.notification import time_intervals_store
        time_intervals_store.ensure_loaded()
        mapping = _intervals_by_name
    if mapping is None:
        return False
    subs = mapping.get(name)
    if not subs:
        return False
    current = now or datetime.now().astimezone()
    return any(_sub_interval_active(sub, current) for sub in subs)


def any_interval_active(names: list[str], now: datetime | None = None) -> bool:
    return any(is_interval_active(name, now) for name in names)
