"""Outbound Socket.IO client — connects to NestJS API /agents namespace."""

from __future__ import annotations

import os
import threading
import time
from typing import Any, Callable

import requests
import socketio

from services.transport import config_cache
from utils.log import get_logger

logger = get_logger(__name__)

AGENT_ID = os.getenv("AGENT_ID", "default")
AGENT_TOKEN = os.getenv("AGENT_TOKEN", "")
API_WS_URL = os.getenv("API_WS_URL", "http://localhost:4000")
API_HTTP_URL = os.getenv("API_HTTP_URL", API_WS_URL.replace("ws://", "http://").replace("wss://", "https://"))
INVESTIGATE_HANDLER: Callable[[dict[str, Any]], dict[str, Any]] | None = None

_sio: socketio.Client | None = None
_connected = threading.Event()


def _mcp_health() -> dict[str, Any]:
    import config as _cfg

    servers = {
        "K8S_MCP_URL": getattr(_cfg, "K8S_MCP_URL", ""),
        "PROMETHEUS_MCP_URL": getattr(_cfg, "PROMETHEUS_MCP_URL", ""),
        "LOKI_MCP_URL": getattr(_cfg, "LOKI_MCP_URL", ""),
        "KAFKA_MCP_URL": getattr(_cfg, "KAFKA_MCP_URL", ""),
        "CLOUDWATCH_MCP_URL": getattr(_cfg, "CLOUDWATCH_MCP_URL", ""),
    }
    results: dict[str, Any] = {}
    for key, url in servers.items():
        if not url:
            results[key] = {"url": "", "status": "not_configured"}
            continue
        mcp_url = url if url.rstrip("/").endswith("/mcp") else f"{url.rstrip('/')}/mcp"
        try:
            resp = requests.get(mcp_url, timeout=3, stream=True)
            resp.close()
            status = "healthy" if resp.status_code < 500 else "error"
            results[key] = {"url": url, "status": status, "code": resp.status_code}
        except Exception as exc:
            results[key] = {"url": url, "status": "unreachable", "error": str(exc)}
    return results


def _bootstrap_config() -> None:
    url = f"{API_HTTP_URL.rstrip('/')}/api/v1/internal/agent/config"
    headers = {}
    if AGENT_TOKEN:
        headers["Authorization"] = f"Bearer {AGENT_TOKEN}"
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        config_cache.update(data.get("config") or {}, data.get("version"))
        logger.info("Bootstrapped config from API (version=%s)", data.get("version"))
    except Exception as exc:
        logger.warning("Config bootstrap failed: %s", exc)


def _on_config_updated(data: dict[str, Any]) -> None:
    config_cache.update(data.get("config") or {}, data.get("version"))
    logger.info("Config updated from API (version=%s)", data.get("version"))
    try:
        from services.notification import silences as _silences
        from services.notification import routing as _routing
        from services import environments as _environments

        _silences.reset_cache()
        _routing.reset_cache()
        _environments.reset_cache()
    except Exception:
        pass


def _on_investigate(job: dict[str, Any]) -> None:
    job_id = job.get("jobId", "")
    logger.info("Received investigate job %s", job_id)
    result: dict[str, Any] = {"status": "error", "message": "No handler registered"}
    try:
        if INVESTIGATE_HANDLER:
            result = INVESTIGATE_HANDLER(job)
    except Exception as exc:
        logger.exception("Investigation failed for job %s", job_id)
        result = {"status": "error", "message": str(exc)}
    sio = _sio
    if sio and sio.connected:
        sio.emit("job.result", {"jobId": job_id, "result": result})


def _build_client() -> socketio.Client:
    sio = socketio.Client(reconnection=True, reconnection_attempts=0, logger=False, engineio_logger=False)

    @sio.event
    def connect():
        logger.info("Connected to API WebSocket")
        _connected.set()
        ack = sio.call(
            "register",
            {
                "agentId": AGENT_ID,
                "version": os.getenv("AGENT_VERSION", "dev"),
                "capabilities": ["investigate"],
                "mcpHealth": _mcp_health(),
            },
            timeout=10,
        )
        if isinstance(ack, dict) and ack.get("config"):
            config_cache.update(ack.get("config") or {}, ack.get("configVersion"))

    @sio.event
    def disconnect():
        logger.warning("Disconnected from API WebSocket")
        _connected.clear()

    sio.on("config.updated", _on_config_updated)
    sio.on("investigate", _on_investigate)
    return sio


def connect(*, block: bool = True) -> None:
    global _sio
    _bootstrap_config()
    _sio = _build_client()
    namespace = "/agents"
    url = API_WS_URL.rstrip("/")
    auth = {"token": AGENT_TOKEN} if AGENT_TOKEN else None

    delay = 1.0
    while True:
        try:
            _sio.connect(url, namespaces=[namespace], auth=auth, wait_timeout=10)
            break
        except Exception as exc:
            logger.warning("WS connect failed (%s), retry in %.0fs", exc, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)

    if block:
        _sio.wait()


def set_investigate_handler(handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    global INVESTIGATE_HANDLER
    INVESTIGATE_HANDLER = handler


def is_connected() -> bool:
    return _connected.is_set()
