import re

import requests

from alert_context import AlertContext
from config import PROMETHEUS_URL


_EC2_DEFAULT_SCRAPE_JOB = "AWSEC2NodeExporter"

_EC2_ALERT_THRESHOLDS: dict[str, str] = {
    "EC2HostMemoryUnderMemoryPressure": "threshold > 1000/s",
    "EC2HostOutOfMemory": "threshold < 10%",
    "EC2HostHighCpuLoad": "threshold > 80%",
}


def _query_promql(query: str) -> dict:
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


def _fetch_node_up(instance: str) -> dict:
    inst = _instance_filter(instance)
    raw = _query_promql(f"up{{{inst}}}")
    results = raw.get("data", {}).get("result", [])
    if not results:
        return {"up": None, "job": None}
    labels = results[0].get("metric", {})
    try:
        up_val = float(results[0]["value"][1])
    except (KeyError, TypeError, ValueError):
        up_val = None
    return {"up": up_val, "job": labels.get("job")}


def _fetch_ec2_host_snapshot(instance: str) -> dict:
    inst = _instance_filter(instance)
    available = _first_scalar(_query_promql(f"node_memory_MemAvailable_bytes{{{inst}}}"))
    free = _first_scalar(_query_promql(f"node_memory_MemFree_bytes{{{inst}}}"))
    total = _first_scalar(_query_promql(f"node_memory_MemTotal_bytes{{{inst}}}"))
    page_faults = _first_scalar(_query_promql(f"rate(node_vmstat_pgmajfault{{{inst}}}[5m])"))

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

    up_info = _fetch_node_up(instance)
    cpu = _first_scalar(
        _query_promql(
            f'100 - (avg by(instance) (rate(node_cpu_seconds_total{{mode="idle",{inst}}}[5m])) * 100)'
        )
    )
    load1 = _first_scalar(_query_promql(f"node_load1{{{inst}}}"))
    disk_pct = _first_scalar(
        _query_promql(
            f"100 * node_filesystem_avail_bytes{{{inst},fstype!~'tmpfs|overlay'}} "
            f"/ node_filesystem_size_bytes{{{inst},fstype!~'tmpfs|overlay'}}"
        )
    )

    return {
        "memory": {
            "available_bytes": avail_bytes,
            "free_bytes": free,
            "total_bytes": total,
            "available_percent": avail_percent,
            "memory_source": memory_source,
            "major_page_faults_per_sec": page_faults,
        },
        "up": up_info.get("up"),
        "scrape_job": up_info.get("job"),
        "cpu_percent": cpu,
        "load1": load1,
        "disk_avail_percent": disk_pct,
        "major_page_faults_per_sec": page_faults,
    }


def _format_bytes(num_bytes: float | None) -> str | None:
    if num_bytes is None:
        return None
    gib = num_bytes / (1024**3)
    if gib >= 1:
        return f"{gib:.1f} GiB"
    mib = num_bytes / (1024**2)
    return f"{mib:.0f} MiB"


def _build_metric_bullets(ctx: AlertContext, snapshot: dict) -> list[str]:
    bullets: list[str] = []
    memory = snapshot.get("memory", {})
    threshold = _EC2_ALERT_THRESHOLDS.get(ctx.alertname, "")

    page_faults = snapshot.get("major_page_faults_per_sec")
    if page_faults is None and ctx.alert_firing_value is not None:
        if ctx.primary_metric == "major_page_faults_per_sec":
            page_faults = ctx.alert_firing_value
    if page_faults is not None:
        suffix = f" ({threshold})" if threshold and "page" in (ctx.primary_metric or "") else ""
        if not suffix and ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
            suffix = " (threshold > 1000/s)"
        source = ""
        if page_faults == ctx.alert_firing_value and snapshot.get("major_page_faults_per_sec") is None:
            source = " [from alert]"
        bullets.append(f"Major page faults: {page_faults:.1f}/s{suffix}{source}")

    avail_pct = memory.get("available_percent")
    avail_bytes = memory.get("available_bytes")
    total_bytes = memory.get("total_bytes")
    if avail_pct is not None:
        mem_source = memory.get("memory_source", "unknown")
        size_part = ""
        if avail_bytes is not None and total_bytes is not None:
            size_part = f" ({_format_bytes(avail_bytes)} / {_format_bytes(total_bytes)})"
        bullets.append(f"Memory available: {avail_pct:.1f}%{size_part} [{mem_source}]")

    up_val = snapshot.get("up")
    scrape_job = snapshot.get("scrape_job") or ctx.scrape_job or _EC2_DEFAULT_SCRAPE_JOB
    if up_val is not None:
        bullets.append(f"Node exporter up: {int(up_val)} (job: {scrape_job})")

    cpu = snapshot.get("cpu_percent")
    if cpu is not None:
        bullets.append(f"CPU utilization: {cpu:.1f}%")

    load1 = snapshot.get("load1")
    if load1 is not None:
        bullets.append(f"Load average (1m): {load1:.2f}")

    disk = snapshot.get("disk_avail_percent")
    if disk is not None:
        bullets.append(f"Disk available: {disk:.1f}%")

    return bullets


def prefetch_host_metrics(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.resource_type != "host":
        return None

    instance = ctx.scrape_instance or ctx.instance
    if not instance:
        bullets = []
        if ctx.alert_firing_value is not None and ctx.primary_metric == "major_page_faults_per_sec":
            bullets.append(
                f"Major page faults: {ctx.alert_firing_value:.1f}/s (threshold > 1000/s) [from alert]"
            )
        return {
            "instance": None,
            "snapshot": {},
            "bullets": bullets,
            "up": None,
            "alert_valid": ctx.alert_firing_value is not None,
        }

    try:
        snapshot = _fetch_ec2_host_snapshot(instance)
    except requests.RequestException as exc:
        bullets = []
        if ctx.alert_firing_value is not None and ctx.primary_metric == "major_page_faults_per_sec":
            bullets.append(
                f"Major page faults: {ctx.alert_firing_value:.1f}/s (threshold > 1000/s) [from alert]"
            )
        return {
            "instance": instance,
            "snapshot": {},
            "bullets": bullets,
            "up": None,
            "error": str(exc),
            "alert_valid": ctx.alert_firing_value is not None,
        }

    bullets = _build_metric_bullets(ctx, snapshot)
    return {
        "instance": instance,
        "snapshot": snapshot,
        "bullets": bullets,
        "up": snapshot.get("up"),
        "alert_valid": ctx.alert_firing_value is not None or bool(bullets),
    }


def prefetched_to_prompt_block(prefetched: dict | None) -> str:
    if not prefetched or not prefetched.get("bullets"):
        return ""
    lines = ["Prefetched metrics (authoritative — use these in the Metrics section):"]
    for bullet in prefetched["bullets"]:
        lines.append(f"• {bullet}")
    if prefetched.get("alert_valid"):
        lines.append(
            "note: alert fired from node_exporter metrics — scrape is working; do not claim exporter is down"
        )
    return "\n".join(lines)
