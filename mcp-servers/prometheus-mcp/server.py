import contextvars
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
_TIMEOUT = int(os.getenv("MCP_SOCKET_TIMEOUT", "30"))

# Per-request header capture: the agent injects the alert's environment endpoint
# via X-Prometheus-Url; each request falls back to the boot default if absent.
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
    return (_req_headers.get() or {}).get("x-prometheus-url") or PROMETHEUS_URL


def _auth_header() -> dict:
    # The agent injects a ready-to-use Authorization value for the env's endpoint.
    auth = (_req_headers.get() or {}).get("x-prometheus-authorization")
    return {"Authorization": auth} if auth else {}


def _get(url: str, **kwargs):
    headers = kwargs.pop("headers", None) or {}
    headers.update(_auth_header())
    return requests.get(url, headers=headers or None, timeout=_TIMEOUT, **kwargs)


def _query(query: str):
    response = _get(f"{_base_url()}/api/v1/query", params={"query": query})
    response.raise_for_status()
    return response.json()


def _instance_filter(instance: str) -> str:
    escaped = instance.replace("\\", "\\\\").replace('"', '\\"')
    return f'instance="{escaped}"'


def _first_scalar(result: dict) -> float | None:
    data = result.get("data", {})
    if data.get("resultType") != "vector":
        return None
    results = data.get("result", [])
    if not results:
        return None
    value = results[0].get("value")
    if not value or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def _fetch_node_up(instance: str, job: str | None = None) -> dict:
    inst = _instance_filter(instance)
    if job:
        escaped_job = job.replace("\\", "\\\\").replace('"', '\\"')
        raw = _query(f'up{{job="{escaped_job}",{inst}}}')
    else:
        raw = _query(f"up{{{inst}}}")
    results = raw.get("data", {}).get("result", [])
    if not results:
        return {"up": None, "job": None, "raw": raw}
    labels = results[0].get("metric", {})
    try:
        up_val = float(results[0]["value"][1])
    except (KeyError, TypeError, ValueError):
        up_val = None
    return {"up": up_val, "job": labels.get("job"), "raw": raw}


def _fetch_node_memory(instance: str) -> dict:
    inst = _instance_filter(instance)
    available = _first_scalar(_query(f"node_memory_MemAvailable_bytes{{{inst}}}"))
    free = _first_scalar(_query(f"node_memory_MemFree_bytes{{{inst}}}"))
    total = _first_scalar(_query(f"node_memory_MemTotal_bytes{{{inst}}}"))
    page_faults = _first_scalar(_query(f"rate(node_vmstat_pgmajfault{{{inst}}}[5m])"))

    memory_source = "unavailable"
    avail_bytes = None
    avail_percent = None

    if available is not None and total:
        memory_source = "MemAvailable"
        avail_bytes = available
        avail_percent = 100 * available / total
    elif free is not None and total:
        memory_source = "MemFree"
        avail_bytes = free
        avail_percent = 100 * free / total

    return {
        "available_bytes": avail_bytes,
        "free_bytes": free,
        "total_bytes": total,
        "available_percent": avail_percent,
        "memory_source": memory_source,
        "major_page_faults_per_sec": page_faults,
    }


def _fetch_ec2_host_snapshot(instance: str) -> dict:
    inst = _instance_filter(instance)
    memory = _fetch_node_memory(instance)
    up_info = _fetch_node_up(instance)
    cpu = _first_scalar(
        _query(
            f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",{inst}}}[5m])) * 100)'
        )
    )
    load1 = _first_scalar(_query(f"node_load1{{{inst}}}"))
    disk_pct = _first_scalar(
        _query(
            f"100 * node_filesystem_avail_bytes{{{inst},fstype!~'tmpfs|overlay'}} "
            f"/ node_filesystem_size_bytes{{{inst},fstype!~'tmpfs|overlay'}}"
        )
    )
    return {
        "memory": memory,
        "up": up_info.get("up"),
        "scrape_job": up_info.get("job"),
        "cpu_percent": cpu,
        "load1": load1,
        "disk_avail_percent": disk_pct,
        "major_page_faults_per_sec": memory.get("major_page_faults_per_sec"),
    }


@mcp.tool()
def query_promql(query: str):
    """Execute a PromQL query."""
    return _query(query)


@mcp.tool()
def get_alerts():
    """Get active alerts."""
    response = _get(f"{_base_url()}/api/v1/alerts")
    response.raise_for_status()
    return response.json()


@mcp.tool()
def get_targets():
    """Get scrape targets."""
    response = _get(f"{_base_url()}/api/v1/targets")
    response.raise_for_status()
    return response.json()


@mcp.tool()
def get_node_up(instance: str, job: str | None = None):
    """Check node-exporter scrape health for an EC2 host."""
    return _fetch_node_up(instance, job=job)


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
    return _fetch_node_memory(instance)


@mcp.tool()
def get_ec2_host_snapshot(instance: str):
    """Get EC2 host metrics snapshot: memory, CPU, disk, load, up, page faults."""
    return _fetch_ec2_host_snapshot(instance)


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
def get_probe_http_status(instance: str, job: str = "blackbox-exporter"):
    """Get HTTP status code from blackbox HTTP probe."""
    inst = _instance_filter(instance)
    escaped_job = job.replace("\\", "\\\\").replace('"', '\\"')
    return _query(f'probe_http_status_code{{job="{escaped_job}",{inst}}}')


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


def _pod_labels_filter(namespace: str, pod: str, container: str) -> str:
    ns = namespace.replace("\\", "\\\\").replace('"', '\\"')
    pod_esc = pod.replace("\\", "\\\\").replace('"', '\\"')
    cont = container.replace("\\", "\\\\").replace('"', '\\"')
    return f'namespace="{ns}",pod="{pod_esc}",container="{cont}"'


def _fetch_pod_cpu_snapshot(namespace: str, pod: str, container: str) -> dict:
    labels = _pod_labels_filter(namespace, pod, container)
    limit = _first_scalar(
        _query(
            f"sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_limits{{{labels}}})"
        )
    )
    pct_by_window = {}
    for window in ("1m", "5m", "15m"):
        usage = _first_scalar(
            _query(f"sum(rate(container_cpu_usage_seconds_total{{{labels}}}[{window}]))")
        )
        pct_by_window[window] = (
            round(100 * usage / limit, 1) if usage is not None and limit else None
        )
    usage_5m = _first_scalar(
        _query(f"sum(rate(container_cpu_usage_seconds_total{{{labels}}}[5m]))")
    )
    restarts = _first_scalar(
        _query(f"sum(kube_pod_container_status_restarts_total{{{labels}}})")
    )
    return {
        "usage_cores": usage_5m,
        "limit_cores": limit,
        "usage_percent_by_window": pct_by_window,
        "usage_percent": pct_by_window.get("5m"),
        "restarts": restarts,
        "resource": "cpu",
    }


def _fetch_pod_memory_snapshot(namespace: str, pod: str, container: str) -> dict:
    labels = _pod_labels_filter(namespace, pod, container)
    limit = _first_scalar(
        _query(
            "sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_limits"
            f"{{{labels}}})"
        )
    )
    pct_by_window = {}
    for window in ("1m", "5m", "15m"):
        working_set = _first_scalar(
            _query(
                f"sum(avg_over_time(container_memory_working_set_bytes{{{labels}}}[{window}]))"
            )
        )
        pct_by_window[window] = (
            round(100 * working_set / limit, 1) if working_set is not None and limit else None
        )
    working_set = _first_scalar(
        _query(f"sum(container_memory_working_set_bytes{{{labels}}})")
    )
    restarts = _first_scalar(
        _query(f"sum(kube_pod_container_status_restarts_total{{{labels}}})")
    )
    return {
        "usage_bytes": working_set,
        "limit_bytes": limit,
        "usage_percent_by_window": pct_by_window,
        "usage_percent": pct_by_window.get("5m"),
        "restarts": restarts,
        "resource": "memory",
    }


@mcp.tool()
def get_pod_cpu_snapshot(namespace: str, pod: str, container: str):
    """Get pod CPU usage, limit, percent of limit, and restarts."""
    return _fetch_pod_cpu_snapshot(namespace, pod, container)


@mcp.tool()
def get_pod_memory_snapshot(namespace: str, pod: str, container: str):
    """Get pod memory working set, limit, percent of limit, and restarts."""
    return _fetch_pod_memory_snapshot(namespace, pod, container)


@mcp.tool()
def get_node_advanced(instance: str):
    """Get EC2 host advanced metrics: swap, inodes, disk latency, systemd, conntrack, clock, temperature, RAID."""
    inst = _instance_filter(instance)
    return {
        "swap_used_percent": _first_scalar(
            _query(
                f"(1 - (node_memory_SwapFree_bytes{{{inst}}} / node_memory_SwapTotal_bytes{{{inst}}})) * 100"
            )
        ),
        "inode_free_percent": _first_scalar(
            _query(
                f'node_filesystem_files_free{{{inst},mountpoint="/rootfs"}} / node_filesystem_files{{{inst},mountpoint="/rootfs"}} * 100'
            )
        ),
        "disk_read_latency_ms": _first_scalar(
            _query(
                f"rate(node_disk_read_time_seconds_total{{{inst}}}[5m]) / rate(node_disk_reads_completed_total{{{inst}}}[5m]) * 1000"
            )
        ),
        "disk_write_latency_ms": _first_scalar(
            _query(
                f'rate(node_disk_write_time_seconds_total{{{inst},device!~"mmcblk.+"}}[5m]) / rate(node_disk_writes_completed_total{{{inst},device!~"mmcblk.+"}}[5m]) * 1000'
            )
        ),
        "systemd_failed_units": _query(
            f'node_systemd_unit_state{{{inst},state="failed"}}'
        ),
        "conntrack_fill_percent": _first_scalar(
            _query(
                f"node_nf_conntrack_entries{{{inst}}} / node_nf_conntrack_entries_limit{{{inst}}} * 100"
            )
        ),
        "clock_offset_seconds": _first_scalar(
            _query(f"node_timex_offset_seconds{{{inst}}}")
        ),
        "ntp_sync_status": _first_scalar(
            _query(f"node_timex_sync_status{{{inst}}}")
        ),
        "hwmon_temp_celsius": _query(f"node_hwmon_temp_celsius{{{inst}}}"),
        "raid_inactive": _query(f'node_md_state{{{inst},state="inactive"}}'),
        "raid_failed_disks": _query(f'node_md_disks{{{inst},state="failed"}}'),
        "edac_correctable_errors": _first_scalar(
            _query(f"increase(node_edac_correctable_errors_total{{{inst}}}[1h])")
        ),
        "edac_uncorrectable_errors": _first_scalar(
            _query(f"node_edac_uncorrectable_errors_total{{{inst}}}")
        ),
    }


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
