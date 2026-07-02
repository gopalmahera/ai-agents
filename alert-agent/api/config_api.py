"""API endpoints for reading and writing agent configuration."""

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


def _probe_mcp_server(url: str) -> dict:
    """Check that an internal MCP HTTP server is listening."""
    mcp_url = url if url.rstrip("/").endswith("/mcp") else f"{url.rstrip('/')}/mcp"
    try:
        # FastMCP streamable-http serves /mcp only (no /health). A 406 without
        # MCP Accept headers still proves the process is up.
        resp = requests.get(mcp_url, timeout=3, stream=True)
        resp.close()
        status = "healthy" if resp.status_code < 500 else "error"
        return {"url": url, "status": status, "code": resp.status_code}
    except Exception as exc:
        return {"url": url, "status": "unreachable", "error": str(exc)}


@bp.get("/mcp/health")
@require_auth
def mcp_health():
    results = {}
    for key, url_fn in _MCP_SERVERS.items():
        results[key] = _probe_mcp_server(url_fn())
    return jsonify(results)


_DIRECT_SERVICE_PROBES: dict[str, str | tuple[str, ...]] = {
    "PROMETHEUS_URL": "/-/healthy",
    # Bare Loki exposes /ready; gateway/nginx setups use a /loki prefix.
    "LOKI_URL": ("/ready", "/loki/ready", "/loki/api/v1/status/buildinfo"),
}


def _probe_http_service(url: str, probes: str | tuple[str, ...]) -> dict:
    if isinstance(probes, str):
        probes = (probes,)
    last_code: int | None = None
    last_error: str | None = None
    for probe in probes:
        try:
            resp = requests.get(f"{url.rstrip('/')}{probe}", timeout=3)
            if resp.status_code < 400:
                return {
                    "url": url,
                    "status": "healthy",
                    "code": resp.status_code,
                    "probe": probe,
                }
            last_code = resp.status_code
        except Exception as exc:
            last_error = str(exc)
    if last_code is not None:
        return {"url": url, "status": "error", "code": last_code}
    return {"url": url, "status": "unreachable", "error": last_error or "unknown"}


@bp.get("/services/health")
@require_auth
def services_health():
    """Health check for direct service endpoints (Prometheus, Loki)."""
    results = {}
    for key, url_fn in _DIRECT_SERVICES.items():
        url = url_fn()
        if not url:
            results[key] = {"url": "", "status": "not_configured"}
            continue
        probes = _DIRECT_SERVICE_PROBES.get(key, ("/",))
        results[key] = _probe_http_service(url, probes)
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
