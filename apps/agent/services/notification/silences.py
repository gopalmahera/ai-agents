"""Agent-managed silences — skip LLM and Slack for matching alerts."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import yaml

import services.store.settings_store as _settings_store
from services.notification.routing import matches_labels
from utils.fs import atomic_write_text
from utils.log import get_logger

logger = get_logger(__name__)

_config: dict[str, Any] | None = None
_SILENCES_CONFIG_PATH = os.getenv("SILENCES_CONFIG_PATH", "/app/config/silences.yaml")
_LEGACY_MUTE_PATH = os.getenv("MUTE_CONFIG_PATH", "/app/config/mute_config.yaml")


def _default_config() -> dict[str, Any]:
    return {"silences": {"active": [], "disabled": []}}


def _extract_silences(doc: dict[str, Any] | None) -> dict[str, Any]:
    if not doc:
        return _default_config()
    silences = doc.get("silences")
    if not isinstance(silences, dict):
        return _default_config()
    return {
        "silences": {
            "active": silences.get("active") or [],
            "disabled": silences.get("disabled") or [],
        }
    }


def _load_config() -> dict[str, Any]:
    global _config
    cached = _config
    if cached is not None:
        return cached

    data = _settings_store.load_silences_config()
    if data.get("silences"):
        _config = data
        active = len(data.get("silences", {}).get("active", []))
        print(f"[silences] Loaded {active} active silence(s) from mongodb")
        return data

    text = None
    source = ""
    if os.path.exists(_SILENCES_CONFIG_PATH):
        with open(_SILENCES_CONFIG_PATH, encoding="utf-8") as fh:
            text = fh.read()
        source = _SILENCES_CONFIG_PATH

    if not text and os.path.exists(_LEGACY_MUTE_PATH):
        with open(_LEGACY_MUTE_PATH, encoding="utf-8") as fh:
            text = fh.read()
        source = _LEGACY_MUTE_PATH

    if not text:
        data = _default_config()
        _config = data
        return data

    parsed = yaml.safe_load(text) or {}
    data = _extract_silences(parsed)
    _config = data
    active = len(data.get("silences", {}).get("active", []))
    print(f"[silences] Loaded {active} active silence(s) from {source}")
    return data


def reset_cache() -> None:
    global _config
    _config = None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _silence_is_active(rule: dict[str, Any], now: datetime) -> bool:
    mode = (rule.get("mode") or "permanent").strip().lower()
    if mode == "permanent":
        return True
    if mode == "until":
        ends_at = _parse_dt(rule.get("ends_at"))
        return ends_at is not None and now < ends_at
    return False


def prune_expired(now: datetime | None = None) -> bool:
    """Move expired ``until`` silences from active to disabled. Returns True if changed."""
    cfg = _load_config()
    current = now or datetime.now(timezone.utc)
    active = cfg.get("silences", {}).get("active", [])
    disabled = cfg.get("silences", {}).get("disabled", [])
    kept: list[dict[str, Any]] = []
    changed = False

    for rule in active:
        mode = (rule.get("mode") or "").strip().lower()
        if mode == "until":
            ends_at = _parse_dt(rule.get("ends_at"))
            if ends_at is not None and current >= ends_at:
                expired = dict(rule)
                expired["disabled_at"] = current.isoformat().replace("+00:00", "Z")
                expired["disabled_reason"] = "expired"
                disabled.append(expired)
                changed = True
                continue
        kept.append(rule)

    if changed:
        cfg["silences"]["active"] = kept
        cfg["silences"]["disabled"] = disabled
        # Best-effort: this runs on the hot path (every alert). If Redis is
        # down we skip persisting — the expired rule is re-pruned next time.
        _persist_config(cfg, required=False)
    return changed


def _persist_config(cfg: dict[str, Any], *, required: bool = True) -> None:
    """Silence persistence is handled by the Next.js admin API."""
    reset_cache()
    if required:
        logger.warning(
            "Silences persist skipped — admin API owns writes",
            extra={"event": "config_store_readonly"},
        )


def save_config(body: dict[str, Any]) -> None:
    from services.config_store import ConfigStoreUnavailable
    raise ConfigStoreUnavailable("Silence writes are handled by the admin API")


def is_silenced(labels: dict) -> tuple[bool, str | None]:
    """Return (silenced, silence_id) for alert labels."""
    prune_expired()
    cfg = _load_config()
    now = datetime.now(timezone.utc)
    for rule in cfg.get("silences", {}).get("active", []):
        if not matches_labels(labels, rule):
            continue
        if _silence_is_active(rule, now):
            return True, rule.get("id")
    return False, None


def get_config() -> dict[str, Any]:
    prune_expired()
    return _load_config()
