"""Runtime config store — MongoDB-backed settings applied to each agent replica.

Source of truth is MongoDB (written by the Next.js admin API). The local
``web_config.json`` file is a boot fallback when Mongo is briefly down.

Precedence: Mongo-stored value > env var > built-in default.
"""
import json
import os
import threading
from pathlib import Path

import config as _cfg
import services.store.settings_store as _settings_store
from utils.fs import atomic_write_text
from utils.log import get_logger

logger = get_logger(__name__)

_lock = threading.RLock()


class ConfigStoreUnavailable(RuntimeError):
    """Raised when a config write cannot reach Redis (the source of truth)."""


CONFIGURABLE_KEYS = [
    "AI_PROVIDER",
    "OPENAI_MODEL",
    "OPENAI_MODEL_INFO",
    "OPENAI_API_KEY",
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_SA_JSON",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "AWS_REGION",
    "AWS_ROLE_ARN",
    "LLM_ENABLED",
    "SLACK_WEBHOOK_URL",
    "PROMETHEUS_URL",
    "LOKI_URL",
    "LOGS_DIR",
    "DEDUP_TTL_SECONDS",
    "ALLOWED_ALERTNAMES",
    "ALERT_CATALOG_PATH",
    "ROUTING_CONFIG_PATH",
]

SENSITIVE_KEYS = {
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_SA_JSON",
    "SLACK_WEBHOOK_URL",
}

# Provider credential/setting keys applied to cfg + os.environ verbatim.
_PROVIDER_ENV_KEYS = {
    "OPENAI_BASE_URL",
    "ANTHROPIC_API_KEY",
    "GEMINI_API_KEY",
    "GOOGLE_CLOUD_PROJECT",
    "GOOGLE_CLOUD_LOCATION",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "AWS_REGION",
    "AWS_ROLE_ARN",
    "OPENAI_MODEL_INFO",
}

_DEFAULTS: dict = {
    "AI_PROVIDER": "openai",
    "OPENAI_MODEL": "gpt-4o",
    "OPENAI_MODEL_INFO": "gpt-4o-mini",
    "OPENAI_API_KEY": "",
    "OPENAI_BASE_URL": "",
    "ANTHROPIC_API_KEY": "",
    "GEMINI_API_KEY": "",
    "GOOGLE_SA_JSON": "",
    "GOOGLE_CLOUD_PROJECT": "",
    "GOOGLE_CLOUD_LOCATION": "us-central1",
    "GOOGLE_GENAI_USE_VERTEXAI": "true",
    "AWS_REGION": "",
    "AWS_ROLE_ARN": "",
    "LLM_ENABLED": True,
    "SLACK_WEBHOOK_URL": "",
    "PROMETHEUS_URL": "http://service-gps.monitoring.svc.cluster.local:9090",
    "LOKI_URL": "http://localhost:3100",
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
        logger.warning("Failed to load config file", extra={"event": "config_file_error", "error": str(exc)})
        return {}


def _decode(raw: str):
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return raw


def _load_store_mongo() -> dict:
    """Stored (UI-set) values from MongoDB."""
    return _settings_store.load_agent_settings()


def _load_store() -> dict:
    """Stored values for READ paths — Mongo first, file mirror when Mongo is down."""
    stored = _load_store_mongo()
    if stored:
        return stored
    return _load_store_file()


def _load_store_file() -> dict:
    """Stored values from the local file mirror (read fallback only)."""
    return {k: v for k, v in _load_file().items() if k in CONFIGURABLE_KEYS}

def seed_redis_from_file() -> None:
    """Legacy no-op — seeding is handled by the Next.js admin API."""
    return


def get_all() -> dict:
    """Return all configurable values (stored overrides env, env overrides defaults)."""
    stored = _load_store()
    result = {}
    for key in CONFIGURABLE_KEYS:
        env_val = os.environ.get(key)
        if key in stored:
            result[key] = stored[key]
        elif env_val is not None:
            result[key] = env_val
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
    """Admin writes are handled by the Next.js API — apply locally only if needed."""
    raise ConfigStoreUnavailable("Config writes are handled by the admin API (Next.js)")


def apply_stored() -> None:
    """Apply every Mongo-stored value to this process."""
    with _lock:
        for key, value in _load_store_mongo().items():
            if key in CONFIGURABLE_KEYS:
                _apply_live(key, value)


def apply_from_file() -> None:
    """Apply the local file mirror to this process (Redis-independent boot path)."""
    with _lock:
        for key, value in _load_store_file().items():
            _apply_live(key, value)


def _apply_live(key: str, value) -> None:
    """Apply config change to live process without restart where safe."""
    import re

    import config as cfg
    str_val = str(value)

    if key == "LLM_ENABLED":
        cfg.LLM_ENABLED = str(value).lower() in ("1", "true", "yes", "True", True)
    elif key == "DEDUP_TTL_SECONDS":
        try:
            cfg.DEDUP_TTL_SECONDS = int(value)
        except (ValueError, TypeError):
            pass
    elif key == "ALLOWED_ALERTNAMES":
        try:
            cfg._allowed_alertname_pattern = re.compile(str_val) if str_val else None
        except re.error as exc:
            logger.warning(
                "Invalid ALLOWED_ALERTNAMES regex",
                extra={"event": "config_regex_error", "error": str(exc)},
            )
            return
        cfg.ALLOWED_ALERTNAMES = str_val
        os.environ[key] = str_val
    elif key == "GOOGLE_SA_JSON":
        # Materialise the SA JSON to a file per replica and point the SDK at it.
        cfg.GOOGLE_SA_JSON = str_val
        _apply_google_sa_json(cfg, str_val)
    elif key == "GEMINI_API_KEY":
        setattr(cfg, key, str_val)
        os.environ[key] = str_val
        os.environ["GOOGLE_API_KEY"] = str_val  # google-genai GLA reads this
    elif key in _PROVIDER_ENV_KEYS or key in (
        "OPENAI_API_KEY", "OPENAI_MODEL", "AI_PROVIDER", "SLACK_WEBHOOK_URL",
        "PROMETHEUS_URL", "LOKI_URL", "LOGS_DIR",
        "ALERT_CATALOG_PATH", "ROUTING_CONFIG_PATH",
    ):
        setattr(cfg, key, str_val)
        os.environ[key] = str_val


def _apply_google_sa_json(cfg, content: str) -> None:
    """Write the GCP service-account JSON to a file and set the SDK env var."""
    path = str(Path(cfg.CONFIG_STORE_PATH).parent / "gcp-sa.json")
    if not content.strip():
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
        cfg.GOOGLE_APPLICATION_CREDENTIALS = ""
        return
    try:
        atomic_write_text(path, content)
        os.chmod(path, 0o600)
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
        cfg.GOOGLE_APPLICATION_CREDENTIALS = path
    except Exception as exc:
        logger.warning(
            "Failed to materialise GOOGLE_SA_JSON",
            extra={"event": "config_sa_json_error", "error": str(exc)},
        )
