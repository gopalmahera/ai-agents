"""Runtime config store — reads/writes web_config.json, merges with env vars."""
import json
import os
import threading
from pathlib import Path

import config as _cfg

_lock = threading.Lock()

CONFIGURABLE_KEYS = [
    "AI_PROVIDER",
    "OPENAI_MODEL",
    "OPENAI_API_KEY",
    "LLM_ENABLED",
    "SLACK_WEBHOOK_URL",
    "PROMETHEUS_URL",
    "LOKI_URL",
    "K8S_MCP_URL",
    "PROMETHEUS_MCP_URL",
    "LOKI_MCP_URL",
    "KAFKA_MCP_URL",
    "LOGS_DIR",
    "DEDUP_TTL_SECONDS",
    "ALLOWED_ALERTNAMES",
    "ALERT_CATALOG_PATH",
    "ROUTING_CONFIG_PATH",
]

SENSITIVE_KEYS = {"OPENAI_API_KEY", "SLACK_WEBHOOK_URL"}

_DEFAULTS: dict = {
    "AI_PROVIDER": "openai",
    "OPENAI_MODEL": "gpt-4o",
    "OPENAI_API_KEY": "",
    "LLM_ENABLED": True,
    "SLACK_WEBHOOK_URL": "",
    "PROMETHEUS_URL": "http://service-gps.monitoring.svc.cluster.local:9090",
    "LOKI_URL": "http://localhost:3100",
    "K8S_MCP_URL": "http://127.0.0.1:8001/mcp",
    "PROMETHEUS_MCP_URL": "http://127.0.0.1:8002/mcp",
    "LOKI_MCP_URL": "http://127.0.0.1:8003/mcp",
    "KAFKA_MCP_URL": "http://127.0.0.1:8004/mcp",
    "LOGS_DIR": "/app/logs",
    "DEDUP_TTL_SECONDS": 900,
    "ALLOWED_ALERTNAMES": "",
    "ALERT_CATALOG_PATH": "/app/config/alert_catalog.yaml",
    "ROUTING_CONFIG_PATH": "",
}


def _store_path() -> Path:
    return Path(_cfg.CONFIG_STORE_PATH)


def _load_file() -> dict:
    p = _store_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[config_store] Failed to load {p}: {exc}")
        return {}


def get_all() -> dict:
    """Return all configurable values (file overrides env, env overrides defaults)."""
    stored = _load_file()
    result = {}
    for key in CONFIGURABLE_KEYS:
        env_val = os.environ.get(key)
        file_val = stored.get(key)
        if env_val is not None:
            result[key] = env_val
        elif file_val is not None:
            result[key] = file_val
        else:
            result[key] = _DEFAULTS.get(key, "")
    return result


def get_masked() -> dict:
    """Like get_all() but sensitive values replaced with '***' if non-empty."""
    values = get_all()
    for key in SENSITIVE_KEYS:
        if values.get(key):
            values[key] = "***"
    return values


def update(updates: dict) -> dict:
    """Merge updates into web_config.json and apply to live process where possible."""
    with _lock:
        stored = _load_file()
        for key, value in updates.items():
            if key not in CONFIGURABLE_KEYS:
                continue
            stored[key] = value
            _apply_live(key, value)

        p = _store_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(stored, indent=2), encoding="utf-8")

    return get_masked()


def _apply_live(key: str, value) -> None:
    """Apply config change to live process without restart where safe."""
    import config as cfg
    str_val = str(value)

    if key == "LLM_ENABLED":
        cfg.LLM_ENABLED = str(value).lower() in ("1", "true", "yes", "True", True)
    elif key == "DEDUP_TTL_SECONDS":
        try:
            cfg.DEDUP_TTL_SECONDS = int(value)
        except (ValueError, TypeError):
            pass
    elif key in ("OPENAI_API_KEY", "OPENAI_MODEL", "AI_PROVIDER", "SLACK_WEBHOOK_URL",
                 "PROMETHEUS_URL", "LOKI_URL", "K8S_MCP_URL", "PROMETHEUS_MCP_URL",
                 "LOKI_MCP_URL", "KAFKA_MCP_URL", "LOGS_DIR",
                 "ALLOWED_ALERTNAMES", "ALERT_CATALOG_PATH", "ROUTING_CONFIG_PATH"):
        setattr(cfg, key, str_val)
        os.environ[key] = str_val
