"""Validate time intervals config submitted via the Web UI."""

from __future__ import annotations

from typing import Any
from zoneinfo import ZoneInfo

_WEEKDAYS = {
    "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday",
}


def _validate_time_string(value: str, field: str) -> list[str]:
    parts = value.strip().split(":")
    if len(parts) != 2:
        return [f"{field} must be HH:MM"]
    try:
        hour, minute = int(parts[0]), int(parts[1])
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        return [f"{field} must be HH:MM"]
    return []


def validate_time_intervals_body(body: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    interval_names: set[str] = set()

    intervals = body.get("time_intervals")
    if intervals is None:
        errors.append("time_intervals must be a list.")
        return errors
    if not isinstance(intervals, list):
        errors.append("time_intervals must be a list.")
        return errors

    for i, entry in enumerate(intervals, start=1):
        prefix = f"Time interval {i}"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object.")
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            errors.append(f"{prefix}: name is required.")
        elif name in interval_names:
            errors.append(f"{prefix}: duplicate name {name!r}.")
        else:
            interval_names.add(name)

        subs = entry.get("time_intervals")
        if not isinstance(subs, list) or not subs:
            errors.append(f"{prefix}: at least one sub-interval is required.")
            continue

        for j, sub in enumerate(subs, start=1):
            sp = f"{prefix} sub-interval {j}"
            if not isinstance(sub, dict):
                errors.append(f"{sp} must be an object.")
                continue
            location = (sub.get("location") or "UTC").strip() or "UTC"
            try:
                ZoneInfo(location)
            except Exception:
                errors.append(f"{sp}: invalid location {location!r}.")

            weekdays = sub.get("weekdays") or []
            for day in weekdays:
                if str(day).lower() not in _WEEKDAYS:
                    errors.append(f"{sp}: invalid weekday {day!r}.")

            times = sub.get("times") or []
            if not times:
                errors.append(f"{sp}: at least one time range is required.")
            for slot in times:
                if not isinstance(slot, dict):
                    errors.append(f"{sp}: times entries must be objects.")
                    continue
                errors.extend(_validate_time_string(slot.get("start_time", ""), f"{sp} start_time"))
                errors.extend(_validate_time_string(slot.get("end_time", ""), f"{sp} end_time"))

    return errors
