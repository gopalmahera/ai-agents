"""API endpoints for reading and writing agent configuration."""
import re

import requests
import yaml
from flask import Blueprint, jsonify, request

import config as _cfg
from api.auth import require_auth
from services.config_store import get_masked, update

bp = Blueprint("config_api", __name__, url_prefix="/api/config")

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
    path = _cfg.ROUTING_CONFIG_PATH or ""
    if not path:
        return jsonify({"routes": [], "default_slack_webhook_url": ""})
    try:
        import os
        if not os.path.exists(path):
            return jsonify({"routes": [], "default_slack_webhook_url": ""})
        data = yaml.safe_load(open(path, encoding="utf-8").read()) or {}
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/routing")
@require_auth
def post_routing():
    body = request.get_json(silent=True) or {}
    path = _cfg.ROUTING_CONFIG_PATH or ""
    if not path:
        return jsonify({"error": "ROUTING_CONFIG_PATH not configured"}), 400
    try:
        import os
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(body, fh, default_flow_style=False, allow_unicode=True)
        # Reset routing cache
        try:
            from services.notification import routing as _routing
            _routing._config = None
        except Exception:
            pass
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
