"""
Slack channel routing — loads a YAML config and resolves the webhook URL
for a given alert's labels using first-match semantics (Alertmanager style).

Rules are loaded from Redis (``config:routing_yaml``, shared across
replicas — written by the Web UI) and fall back to the local
ROUTING_CONFIG_PATH file when Redis has no rules.
"""

import os
import re
from typing import Any

import yaml

import config as _cfg
import services.store.redis_client as _redis


_config: dict[str, Any] | None = None


def _load_config() -> dict[str, Any]:
    global _config
    if _config is not None:
        return _config

    text = None
    source = ""
    try:
        text = _redis.routing_yaml_load()
        source = "redis"
    except Exception:
        text = None

    if not text:
        path = getattr(_cfg, "ROUTING_CONFIG_PATH", "") or os.getenv("ROUTING_CONFIG_PATH", "")
        if not path or not os.path.exists(path):
            _config = {}
            return _config
        with open(path, "r", encoding="utf-8") as fh:
            text = fh.read()
        source = path

    _config = yaml.safe_load(text) or {}
    routes = _config.get("routes", [])
    print(f"[routing] Loaded {len(routes)} route(s) from {source}")
    return _config


def reset_cache() -> None:
    """Force a reload on next resolve — called when routing rules change."""
    global _config
    _config = None


def _matches(labels: dict, rule: dict) -> bool:
    for key, val in rule.get("match", {}).items():
        if labels.get(key) != val:
            return False
    for key, pattern in rule.get("match_re", {}).items():
        label_val = labels.get(key, "")
        if not re.search(pattern, label_val):
            return False
    return True


def resolve_webhook_url(labels: dict) -> str:
    """Return the Slack webhook URL for the given alert labels.

    Evaluates routes top-to-bottom; returns the first match.
    Falls back to default_slack_webhook_url in config, then SLACK_WEBHOOK_URL.
    """
    cfg = _load_config()
    for rule in cfg.get("routes", []):
        if _matches(labels, rule):
            url = rule.get("slack_webhook_url", "")
            if url:
                return url

    return cfg.get("default_slack_webhook_url", "") or _cfg.SLACK_WEBHOOK_URL
