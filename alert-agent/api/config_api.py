"""API endpoints for reading and writing agent configuration."""
import re

import requests
import yaml
from flask import Blueprint, jsonify, request

import config as _cfg
import services.store.redis_client as _redis
from api.auth import require_auth
from services.config_store import get_masked, update
from services.notification import routing as _routing

bp = Blueprint("config_api", __name__, url_prefix="/api/config")

# Internal MCP servers — run inside the agent container on fixed ports.
# Read-only status; not configurable from the UI.
_MCP_SERVERS = {
    "K8S_MCP_URL": lambda: _cfg.K8S_MCP_URL,
    "PROMETHEUS_MCP_URL": lambda: _cfg.PROMETHEUS_MCP_URL,
    "LOKI_MCP_URL": lambda: _cfg.LOKI_MCP_URL,
    "KAFKA_MCP_URL": lambda: _cfg.KAFKA_MCP_URL,
}

_DIRECT_SERVICES = {
    "PROMETHEUS_URL": lambda: _cfg.PROMETHEUS_URL,
    "LOKI_URL": lambda: getattr(_cfg, "LOKI_URL", ""),
}


@bp.get("")
@require_auth
def get_config():
    return jsonify(get_masked())


@bp.post("")
@require_auth
def post_config():
    body = request.get_json(silent=True) or {}
    result = update(body)
    return jsonify(result)


@bp.get("/mcp/health")
@require_auth
def mcp_health():
    results = {}
    for key, url_fn in _MCP_SERVERS.items():
        url = url_fn()
        base = re.sub(r"/mcp$", "", url)
        try:
            resp = requests.get(f"{base}/health", timeout=3)
            results[key] = {
                "url": url,
                "status": "healthy" if resp.status_code < 400 else "error",
                "code": resp.status_code,
            }
        except Exception as exc:
            results[key] = {"url": url, "status": "unreachable", "error": str(exc)}
    return jsonify(results)


@bp.get("/services/health")
@require_auth
def services_health():
    """Health check for direct service endpoints (Prometheus, Loki)."""
    results = {}
    _PROBES = {
        "PROMETHEUS_URL": "/-/healthy",
        "LOKI_URL": "/ready",
    }
    for key, url_fn in _DIRECT_SERVICES.items():
        url = url_fn()
        if not url:
            results[key] = {"url": "", "status": "not_configured"}
            continue
        probe = _PROBES.get(key, "/")
        try:
            resp = requests.get(f"{url.rstrip('/')}{probe}", timeout=3)
            results[key] = {
                "url": url,
                "status": "healthy" if resp.status_code < 400 else "error",
                "code": resp.status_code,
            }
        except Exception as exc:
            results[key] = {"url": url, "status": "unreachable", "error": str(exc)}
    return jsonify(results)


@bp.get("/routing")
@require_auth
def get_routing():
    """Current routing rules — Redis first (shared), local file fallback."""
    try:
        text = None
        try:
            text = _redis.routing_yaml_load()
        except Exception:
            text = None
        if not text:
            import os
            path = _cfg.ROUTING_CONFIG_PATH or ""
            if not path or not os.path.exists(path):
                return jsonify({"routes": [], "default_slack_webhook_url": ""})
            text = open(path, encoding="utf-8").read()
        data = yaml.safe_load(text) or {}
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/routing")
@require_auth
def post_routing():
    """Save routing rules to Redis and broadcast to all replicas."""
    body = request.get_json(silent=True) or {}
    yaml_text = yaml.safe_dump(body, default_flow_style=False, allow_unicode=True)

    redis_ok = False
    try:
        _redis.routing_yaml_save(yaml_text)
        _redis.publish_config_event("routing")
        redis_ok = True
    except Exception as exc:
        print(f"[config_api] Redis unavailable — routing saved to file only: {exc}")

    # Local file mirror (fallback when Redis is down; optional)
    file_error = None
    path = _cfg.ROUTING_CONFIG_PATH or ""
    if path:
        try:
            import os
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(yaml_text)
        except Exception as exc:
            file_error = str(exc)

    if not redis_ok and (not path or file_error):
        return jsonify({"error": file_error or "Redis unavailable and no ROUTING_CONFIG_PATH set"}), 500

    _routing.reset_cache()
    return jsonify({"status": "ok", "synced": redis_ok})
