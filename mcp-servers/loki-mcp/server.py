import contextvars
import os
from datetime import datetime, timedelta, timezone

import requests
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "loki",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)

LOKI_URL = os.getenv("LOKI_URL", "http://host.docker.internal:3100")
_TIMEOUT = int(os.getenv("MCP_SOCKET_TIMEOUT", "30"))

# Per-request header capture: the agent injects the alert's environment endpoint
# via X-Loki-Url; each request falls back to the boot default if absent.
_req_headers: contextvars.ContextVar = contextvars.ContextVar("req_headers", default=None)


class _HeaderCaptureMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            hdrs = {k.decode("latin1").lower(): v.decode("latin1") for k, v in (scope.get("headers") or [])}
            token = _req_headers.set(hdrs)
            try:
                await self.app(scope, receive, send)
            finally:
                _req_headers.reset(token)
        else:
            await self.app(scope, receive, send)


def _base_url() -> str:
    return (_req_headers.get() or {}).get("x-loki-url") or LOKI_URL


def _auth_header() -> dict:
    # The agent injects a ready-to-use Authorization value for the env's endpoint.
    auth = (_req_headers.get() or {}).get("x-loki-authorization")
    return {"Authorization": auth} if auth else {}


def _default_time_range():
    end = datetime.now(timezone.utc)
    start = end - timedelta(minutes=30)
    return start, end


def _query_range(query: str, start: str | None = None, end: str | None = None, limit: int = 100):
    if start is None or end is None:
        default_start, default_end = _default_time_range()
        start = start or default_start.isoformat()
        end = end or default_end.isoformat()

    response = requests.get(
        f"{_base_url()}/loki/api/v1/query_range",
        params={
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
        },
        headers=_auth_header() or None,
        timeout=_TIMEOUT,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def search_logs(query: str, start: str | None = None, end: str | None = None, limit: int = 100):
    """Search logs with a raw LogQL query."""
    return _query_range(query=query, start=start, end=end, limit=limit)


@mcp.tool()
def search_errors(namespace: str, pod: str | None = None, start: str | None = None, end: str | None = None):
    """Search for error logs in a namespace, optionally narrowed to a pod."""
    selectors = [f'namespace="{namespace}"']
    if pod:
        selectors.append(f'pod="{pod}"')
    query = "{" + ",".join(selectors) + '} |= "error"'
    return _query_range(query=query, start=start, end=end, limit=50)


def _run() -> None:
    import uvicorn

    app = mcp.streamable_http_app()
    app.add_middleware(_HeaderCaptureMiddleware)
    uvicorn.run(
        app,
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        log_level=os.getenv("MCP_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    _run()
