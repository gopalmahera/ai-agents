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
        f"{LOKI_URL}/loki/api/v1/query_range",
        params={
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
        },
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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
