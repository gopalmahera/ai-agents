"""API endpoints for reading and writing agent configuration."""

import requests
import yaml
from flask import Blueprint, jsonify, request

import config as _cfg
import services.store.redis_client as _redis
from api.auth import require_auth
from services.config_store import get_masked, update
from services.notification import routing as _routing
from services.notification.routing_validation import validate_routing_body
from services.notification import silences as _silences
from services.notification import time_intervals_store as _time_intervals_store
from services.notification.silences_validation import validate_silences_body
from services.notification.time_intervals_validation import validate_time_intervals_body

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
    interval_names = _time_intervals_store.get_interval_names()
    errors = validate_routing_body(body, interval_names=interval_names)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

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


@bp.get("/time-intervals")
@require_auth
def get_time_intervals():
    """Named time intervals for routing mute windows."""
    try:
        return jsonify(_time_intervals_store.get_config())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/time-intervals")
@require_auth
def post_time_intervals():
    body = request.get_json(silent=True) or {}
    errors = validate_time_intervals_body(body)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    try:
        _time_intervals_store.save_config(body)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok"})


@bp.get("/mute")
@require_auth
def get_mute():
    """Silences (active + disabled)."""
    try:
        return jsonify(_silences.get_config())
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


@bp.post("/mute")
@require_auth
def post_mute():
    body = request.get_json(silent=True) or {}
    errors = validate_silences_body(body)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    try:
        _silences.save_config(body)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"status": "ok"})


@bp.post("/mute/silences/<silence_id>/disable")
@require_auth
def disable_silence(silence_id: str):
    from datetime import datetime, timezone

    cfg = _silences.get_config()
    active = cfg.get("silences", {}).get("active", [])
    disabled = cfg.get("silences", {}).get("disabled", [])
    kept = []
    found = None
    for rule in active:
        if rule.get("id") == silence_id:
            found = dict(rule)
        else:
            kept.append(rule)
    if not found:
        return jsonify({"error": "Silence not found in active list"}), 404
    found["disabled_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    found["disabled_reason"] = "manual"
    cfg["silences"]["active"] = kept
    cfg["silences"]["disabled"] = [found, *disabled]
    errors = validate_silences_body(cfg, require_future_ends_at=False)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    _silences.save_config(cfg)
    return jsonify({"status": "ok"})


@bp.post("/mute/silences/<silence_id>/enable")
@require_auth
def enable_silence(silence_id: str):
    body = request.get_json(silent=True) or {}
    cfg = _silences.get_config()
    active = cfg.get("silences", {}).get("active", [])
    disabled = cfg.get("silences", {}).get("disabled", [])
    kept_disabled = []
    found = None
    for rule in disabled:
        if rule.get("id") == silence_id:
            found = dict(rule)
        else:
            kept_disabled.append(rule)
    if not found:
        return jsonify({"error": "Silence not found in disabled list"}), 404

    mode = (body.get("mode") or found.get("mode") or "permanent").strip().lower()
    found["mode"] = mode
    if mode == "until":
        found["ends_at"] = body.get("ends_at") or found.get("ends_at")
    found.pop("disabled_at", None)
    found.pop("disabled_reason", None)

    cfg["silences"]["active"] = [*active, found]
    cfg["silences"]["disabled"] = kept_disabled
    errors = validate_silences_body(cfg)
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400
    _silences.save_config(cfg)
    return jsonify({"status": "ok"})
