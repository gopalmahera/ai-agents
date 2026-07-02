"""Agent worker entrypoint — MCP servers + outbound WebSocket to API."""

from __future__ import annotations

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from controllers.investigation_controller import investigate_alert
from services.transport import ws_client
from utils.log import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

HEALTH_PORT = int(os.getenv("AGENT_HEALTH_PORT", os.getenv("AGENT_PORT", "8080")))


class _HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in ("/health", "/health/"):
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        return


def _start_health_server() -> None:
    server = HTTPServer(("0.0.0.0", HEALTH_PORT), _HealthHandler)
    logger.info("Health server on :%s", HEALTH_PORT)
    server.serve_forever()


def _handle_investigate_job(job: dict) -> dict:
    alert = job.get("alert") or {}
    env = job.get("env")
    result = investigate_alert(alert, env=env)
    if result is None:
        return {"status": "skipped", "reason": "non-firing or filtered"}
    return {"status": "ok", **result}


def main() -> None:
    threading.Thread(target=_start_health_server, daemon=True).start()
    ws_client.set_investigate_handler(_handle_investigate_job)
    logger.info("Starting WebSocket worker (agent_id=%s)", os.getenv("AGENT_ID", "default"))
    ws_client.connect(block=True)


if __name__ == "__main__":
    main()
