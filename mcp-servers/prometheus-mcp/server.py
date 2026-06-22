import os

import requests
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "prometheus",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-sit.dozee.int")


@mcp.tool()
def query_promql(query: str):
    """Execute a PromQL query."""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def get_alerts():
    """Get active alerts."""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/alerts",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


@mcp.tool()
def get_targets():
    """Get scrape targets."""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/targets",
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
