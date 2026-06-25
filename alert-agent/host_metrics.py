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

_EC2_ACTIONS: dict[str, list[str]] = {
    "EC2HostMemoryUnderMemoryPressure": [
        "SSH to the host and run `free -h` and `ps aux --sort=-%mem | head` to find top memory consumers.",
        "Restart or scale the heaviest memory consumer, or increase instance memory if pressure is sustained.",
        "Monitor page fault rate and memory available over the next hour to confirm recovery.",
    ],
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


def _has_up_metric(instance: str) -> bool:
    inst = _instance_filter(instance)
    raw = _query_promql(f"up{{{inst}}}")
    return bool(raw.get("data", {}).get("result"))


def _discover_instance_by_host_ip(host_ip: str) -> str | None:
    raw = _query_promql(f'up{{job="{_EC2_DEFAULT_SCRAPE_JOB}"}}')
    results = raw.get("data", {}).get("result", [])
    for item in results:
        instance = item.get("metric", {}).get("instance", "")
        if host_ip in instance:
            return instance
    return None


def resolve_scrape_instance(
    alert_instance: str | None,
    host_ip: str | None,
) -> tuple[str | None, str]:
    """Return (resolved_instance, resolution_method)."""
    if not alert_instance and not host_ip:
        return None, "none"

    candidates: list[tuple[str, str]] = []
    if alert_instance:
        candidates.append((alert_instance, "exact"))
        if ":" not in alert_instance and host_ip:
            candidates.append((f"{alert_instance}:9100", "variant_port"))
        if host_ip and alert_instance != host_ip:
            candidates.append((host_ip, "variant_ip"))
            candidates.append((f"{host_ip}:9100", "variant_ip_port"))

    seen: set[str] = set()
    for instance, method in candidates:
        if instance in seen:
            continue
        seen.add(instance)
        try:
            if _has_up_metric(instance):
                return instance, method
        except requests.RequestException:
            continue

    if host_ip:
        try:
            discovered = _discover_instance_by_host_ip(host_ip)
            if discovered:
                return discovered, "discovered"
        except requests.RequestException:
            pass

    return alert_instance or host_ip, "unresolved"


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
    from_alert = False
    if page_faults is None and ctx.alert_firing_value is not None:
        if ctx.primary_metric == "major_page_faults_per_sec":
            page_faults = ctx.alert_firing_value
            from_alert = True
    if page_faults is not None:
        suffix = f" ({threshold})" if threshold and "page" in (ctx.primary_metric or "") else ""
        if not suffix and ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
            suffix = " (threshold > 1000/s)"
        source = " [from alert]" if from_alert else ""
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


def build_findings_bullets(ctx: AlertContext, prefetched: dict | None) -> list[str]:
    if not prefetched:
        return []

    findings: list[str] = []
    snapshot = prefetched.get("snapshot") or {}
    memory = snapshot.get("memory", {})

    page_faults = snapshot.get("major_page_faults_per_sec")
    if page_faults is None and ctx.alert_firing_value is not None:
        page_faults = ctx.alert_firing_value
    if page_faults is not None and ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
        findings.append(
            f"Page faults at {page_faults:.1f}/s exceed threshold — host is under memory pressure."
        )

    avail_pct = memory.get("available_percent")
    if avail_pct is not None:
        findings.append(f"Memory available is {avail_pct:.1f}% on host {ctx.host_ip or ctx.scrape_instance}.")

    up_val = prefetched.get("up")
    if up_val == 1:
        job = snapshot.get("scrape_job") or ctx.scrape_job or _EC2_DEFAULT_SCRAPE_JOB
        findings.append(f"Scrape target is healthy (up=1, job: {job}).")
    elif prefetched.get("alert_valid"):
        host = ctx.host_ip or ctx.scrape_instance or "host"
        findings.append(
            f"Alert fired from node_exporter metrics on {host}; scrape is working for the alert condition."
        )
        if not memory.get("available_percent"):
            findings.append(
                f"Additional memory/CPU metrics were unavailable from Prometheus for {host}."
            )

    return findings


def _fallback_bullets_from_alert(ctx: AlertContext) -> list[str]:
    if ctx.alert_firing_value is None or ctx.primary_metric != "major_page_faults_per_sec":
        return []
    return [
        f"Major page faults: {ctx.alert_firing_value:.1f}/s (threshold > 1000/s) [from alert]"
    ]


def prefetch_host_metrics(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.resource_type != "host":
        return None

    alert_instance = ctx.scrape_instance or ctx.instance
    resolved, resolution = resolve_scrape_instance(alert_instance, ctx.host_ip)

    if not resolved:
        bullets = _fallback_bullets_from_alert(ctx)
        return {
            "instance": None,
            "resolved_instance": None,
            "instance_resolution": resolution,
            "snapshot": {},
            "bullets": bullets,
            "findings": build_findings_bullets(ctx, {"alert_valid": bool(bullets)}),
            "up": None,
            "alert_valid": ctx.alert_firing_value is not None,
        }

    try:
        snapshot = _fetch_ec2_host_snapshot(resolved)
    except requests.RequestException as exc:
        bullets = _fallback_bullets_from_alert(ctx)
        result = {
            "instance": alert_instance,
            "resolved_instance": resolved,
            "instance_resolution": resolution,
            "snapshot": {},
            "bullets": bullets,
            "up": None,
            "error": str(exc),
            "alert_valid": ctx.alert_firing_value is not None,
        }
        result["findings"] = build_findings_bullets(ctx, result)
        return result

    bullets = _build_metric_bullets(ctx, snapshot)
    if not bullets and ctx.alert_firing_value is not None:
        bullets = _fallback_bullets_from_alert(ctx)

    result = {
        "instance": alert_instance,
        "resolved_instance": resolved,
        "instance_resolution": resolution,
        "snapshot": snapshot,
        "bullets": bullets,
        "up": snapshot.get("up"),
        "alert_valid": ctx.alert_firing_value is not None or bool(bullets),
    }
    result["findings"] = build_findings_bullets(ctx, result)
    return result


def prefetched_to_prompt_block(prefetched: dict | None) -> str:
    if not prefetched or not prefetched.get("bullets"):
        return ""
    lines = ["Prefetched metrics (authoritative — use these in the Metrics section):"]
    for bullet in prefetched["bullets"]:
        lines.append(f"• {bullet}")
    if prefetched.get("findings"):
        lines.append("")
        lines.append("Prefetched findings (use in Findings section):")
        for finding in prefetched["findings"]:
            lines.append(f"• {finding}")
    if prefetched.get("alert_valid"):
        lines.append(
            "note: alert fired from node_exporter metrics — scrape is working; do not claim exporter is down"
        )
    return "\n".join(lines)


def default_host_actions(ctx: AlertContext) -> list[str]:
    return _EC2_ACTIONS.get(
        ctx.alertname,
        [
            f"Investigate resource usage on host {ctx.host_ip or ctx.scrape_instance}.",
            "Review recent changes or deployments that may have increased load.",
            "Monitor host metrics over the next hour to confirm recovery.",
        ],
    )
