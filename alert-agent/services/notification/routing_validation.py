"""Validate routing config submitted via the Web UI."""

import re
from typing import Any
from urllib.parse import urlparse

_SLACK_WEBHOOK_ENV = "${SLACK_WEBHOOK_URL}"


def _is_valid_webhook(url: str) -> bool:
    url = (url or "").strip()
    if not url:
        return False
    if url == _SLACK_WEBHOOK_ENV:
        return True
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    return parsed.scheme == "https" and parsed.netloc == "hooks.slack.com"


def validate_routing_body(
    body: dict[str, Any],
    *,
    interval_names: list[str] | None = None,
) -> list[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    errors: list[str] = []

    default_url = (body.get("default_slack_webhook_url") or "").strip()
    if default_url and not _is_valid_webhook(default_url):
        errors.append(
            "default_slack_webhook_url must be a Slack webhook URL "
            "(https://hooks.slack.com/services/…) or empty."
        )

    routes = body.get("routes")
    if routes is None:
        errors.append("routes must be a list.")
        return errors
    if not isinstance(routes, list):
        errors.append("routes must be a list.")
        return errors

    for i, rule in enumerate(routes, start=1):
        if not isinstance(rule, dict):
            errors.append(f"Rule {i} must be an object.")
            continue

        prefix = f"Rule {i}"
        match = rule.get("match") or {}
        match_re = rule.get("match_re") or {}
        if not isinstance(match, dict) or not isinstance(match_re, dict):
            errors.append(f"{prefix}: match and match_re must be objects.")
            continue

        if not match and not match_re:
            errors.append(f"{prefix}: at least one label matcher is required.")

        for key, value in match.items():
            if not str(key).strip():
                errors.append(f"{prefix}: match keys cannot be empty.")
            if value is None or str(value).strip() == "":
                errors.append(f"{prefix}: match value for '{key}' cannot be empty.")

        for key, pattern in match_re.items():
            if not str(key).strip():
                errors.append(f"{prefix}: match_re keys cannot be empty.")
            if pattern is None or str(pattern).strip() == "":
                errors.append(f"{prefix}: regex for '{key}' cannot be empty.")
            else:
                try:
                    re.compile(str(pattern))
                except re.error as exc:
                    errors.append(f"{prefix}: invalid regex for '{key}': {exc}")

        webhook = (rule.get("slack_webhook_url") or "").strip()
        if not _is_valid_webhook(webhook):
            errors.append(f"{prefix}: a valid slack_webhook_url is required.")

        mute_names = rule.get("mute_time_intervals") or []
        if mute_names is not None and not isinstance(mute_names, list):
            errors.append(f"{prefix}: mute_time_intervals must be a list.")
        elif mute_names:
            known = set(interval_names or [])
            for name in mute_names:
                label = str(name).strip()
                if not label:
                    errors.append(f"{prefix}: mute_time_intervals cannot contain empty names.")
                elif interval_names is not None and label not in known:
                    errors.append(f"{prefix}: unknown mute_time_interval {label!r}.")

    return errors
