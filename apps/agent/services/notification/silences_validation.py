"""Validate silences config submitted via the Web UI."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

_VALID_MODES = {"permanent", "until"}


def _parse_dt(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _has_matchers(rule: dict[str, Any]) -> bool:
    match = rule.get("match") or {}
    match_re = rule.get("match_re") or {}
    return bool(match or match_re)


def validate_silences_body(body: dict[str, Any], *, require_future_ends_at: bool = True) -> list[str]:
    errors: list[str] = []
    silences = body.get("silences")
    if silences is None or not isinstance(silences, dict):
        errors.append("silences must be an object with active and disabled lists.")
        return errors

    for section in ("active", "disabled"):
        rules = silences.get(section)
        if rules is None:
            errors.append(f"silences.{section} is required.")
            continue
        if not isinstance(rules, list):
            errors.append(f"silences.{section} must be a list.")
            continue
        for i, rule in enumerate(rules, start=1):
            errors.extend(
                _validate_silence_rule(
                    rule,
                    f"Silence ({section}) {i}",
                    require_future_ends_at and section == "active",
                )
            )

    return errors


def _validate_silence_rule(
    rule: Any,
    prefix: str,
    require_future_ends_at: bool,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(rule, dict):
        return [f"{prefix} must be an object."]

    if not (rule.get("id") or "").strip():
        errors.append(f"{prefix}: id is required.")

    if not _has_matchers(rule):
        errors.append(f"{prefix}: at least one label matcher (match or match_re) is required.")

    match = rule.get("match") or {}
    match_re = rule.get("match_re") or {}
    if not isinstance(match, dict) or not isinstance(match_re, dict):
        errors.append(f"{prefix}: match and match_re must be objects.")
    else:
        for key, value in match.items():
            if not str(key).strip():
                errors.append(f"{prefix}: match keys cannot be empty.")
            if value is None or str(value).strip() == "":
                errors.append(f"{prefix}: match value for {key!r} cannot be empty.")
        for key, pattern in match_re.items():
            if not str(key).strip():
                errors.append(f"{prefix}: match_re keys cannot be empty.")
            if pattern is None or str(pattern).strip() == "":
                errors.append(f"{prefix}: regex for {key!r} cannot be empty.")
            else:
                try:
                    re.compile(str(pattern))
                except re.error as exc:
                    errors.append(f"{prefix}: invalid regex for {key!r}: {exc}")

    mode = (rule.get("mode") or "permanent").strip().lower()
    if mode not in _VALID_MODES:
        errors.append(f"{prefix}: mode must be permanent or until.")

    if mode == "until":
        ends_at = _parse_dt(rule.get("ends_at", ""))
        if ends_at is None:
            errors.append(f"{prefix}: ends_at is required for until mode.")
        elif require_future_ends_at and ends_at <= datetime.now(timezone.utc):
            errors.append(f"{prefix}: ends_at must be in the future.")

    return errors
