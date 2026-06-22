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


def _query(query: str):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _instance_filter(instance: str) -> str:
    escaped = instance.replace("\\", "\\\\").replace('"', '\\"')
    return f'instance="{escaped}"'


@mcp.tool()
def query_promql(query: str):
    """Execute a PromQL query."""
    return _query(query)


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


@mcp.tool()
def get_node_up(instance: str):
    """Check node-exporter scrape health for an EC2 host."""
    inst = _instance_filter(instance)
    return _query(f'up{{job="node-exporter",{inst}}}')


@mcp.tool()
def get_node_cpu(instance: str):
    """Get EC2 host CPU utilization percent and load."""
    inst = _instance_filter(instance)
    return _query(
        f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",{inst}}}[5m])) * 100)'
    )


@mcp.tool()
def get_node_memory(instance: str):
    """Get EC2 host memory available bytes and utilization percent."""
    inst = _instance_filter(instance)
    return {
        "available_bytes": _query(f"node_memory_MemAvailable_bytes{{{inst}}}"),
        "total_bytes": _query(f"node_memory_MemTotal_bytes{{{inst}}}"),
        "available_percent": _query(
            f"100 * node_memory_MemAvailable_bytes{{{inst}}} / node_memory_MemTotal_bytes{{{inst}}}"
        ),
        "major_page_faults": _query(f"rate(node_vmstat_pgmajfault{{{inst}}}[5m])"),
    }


@mcp.tool()
def get_node_disk(instance: str):
    """Get EC2 host filesystem availability by mountpoint."""
    inst = _instance_filter(instance)
    return {
        "avail_percent": _query(
            f"100 * node_filesystem_avail_bytes{{{inst},fstype!~'tmpfs|overlay'}} "
            f"/ node_filesystem_size_bytes{{{inst},fstype!~'tmpfs|overlay'}}"
        ),
        "avail_bytes": _query(
            f"node_filesystem_avail_bytes{{{inst},fstype!~'tmpfs|overlay'}}"
        ),
    }


@mcp.tool()
def get_node_network(instance: str):
    """Get EC2 host network receive/transmit rates in MB/s."""
    inst = _instance_filter(instance)
    return {
        "receive_mbps": _query(
            f"sum by(instance) (rate(node_network_receive_bytes_total{{{inst}}}[5m])) / 1024 / 1024"
        ),
        "transmit_mbps": _query(
            f"sum by(instance) (rate(node_network_transmit_bytes_total{{{inst}}}[5m])) / 1024 / 1024"
        ),
        "receive_errors": _query(
            f"rate(node_network_receive_errs_total{{{inst}}}[5m])"
        ),
        "transmit_errors": _query(
            f"rate(node_network_transmit_errs_total{{{inst}}}[5m])"
        ),
    }


@mcp.tool()
def get_node_load(instance: str):
    """Get EC2 host load, CPU steal, and OOM kill counter."""
    inst = _instance_filter(instance)
    return {
        "load1": _query(f"node_load1{{{inst}}}"),
        "cpu_steal_percent": _query(
            f'avg by(instance) (rate(node_cpu_seconds_total{{mode="steal",{inst}}}[5m])) * 100'
        ),
        "oom_kills": _query(f"increase(node_vmstat_oom_kill{{{inst}}}[1h])"),
    }


@mcp.tool()
def get_probe_success(instance: str, job: str = "blackbox-exporter"):
    """Get blackbox probe success for a target."""
    inst = _instance_filter(instance)
    escaped_job = job.replace("\\", "\\\\").replace('"', '\\"')
    return _query(f'probe_success{{job="{escaped_job}",{inst}}}')


@mcp.tool()
def get_probe_duration(instance: str, job: str = "blackbox-exporter"):
    """Get blackbox probe duration in seconds."""
    inst = _instance_filter(instance)
    escaped_job = job.replace("\\", "\\\\").replace('"', '\\"')
    return _query(f'probe_duration_seconds{{job="{escaped_job}",{inst}}}')


@mcp.tool()
def get_probe_http_status(instance: str):
    """Get HTTP status code from blackbox HTTP probe."""
    inst = _instance_filter(instance)
    return _query(f'probe_http_status_code{{job="blackbox-exporter",{inst}}}')


@mcp.tool()
def get_probe_ssl_expiry(instance: str):
    """Get days until TLS certificate expiry from blackbox probe."""
    inst = _instance_filter(instance)
    return _query(
        f'(probe_ssl_earliest_cert_expiry{{job="blackbox-exporter",{inst}}} - time()) / 86400'
    )


@mcp.tool()
def get_probe_dns(instance: str):
    """Get DNS lookup time from blackbox probe."""
    inst = _instance_filter(instance)
    return _query(f'probe_dns_lookup_time_seconds{{job="blackbox-exporter",{inst}}}')


@mcp.tool()
def get_probe_phase(instance: str):
    """Get blackbox HTTP probe phase durations."""
    inst = _instance_filter(instance)
    return _query(f'probe_http_duration_seconds{{job="blackbox-exporter",{inst}}}')


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
