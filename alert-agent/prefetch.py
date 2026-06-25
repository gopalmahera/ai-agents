from alert_context import AlertContext
from host_metrics import prefetch_host_metrics, prefetched_to_prompt_block as _host_prompt_block
from pod_metrics import build_findings_bullets as build_pod_findings_bullets, prefetch_pod_metrics
from workload_context import prefetch_workload_context


def build_prefetch(ctx: AlertContext, alert: dict) -> dict | None:
    metrics = prefetch_host_metrics(ctx, alert) or prefetch_pod_metrics(ctx, alert)
    workload = prefetch_workload_context(ctx, alert)

    if not metrics and not workload:
        return None

    result = metrics or {
        "bullets": [],
        "findings": [],
        "snapshot": {},
        "alert_valid": False,
    }

    if workload:
        result["workload"] = workload
        if workload.get("alert_meaning"):
            result["alert_meaning"] = workload["alert_meaning"]
        if workload.get("bullets"):
            result["workload_bullets"] = list(workload["bullets"])
        if result.get("snapshot", {}).get("resource") in ("cpu", "memory"):
            result["findings"] = build_pod_findings_bullets(ctx, result)

    return result


def prefetched_to_prompt_block(prefetched: dict | None) -> str:
    if not prefetched:
        return ""

    lines: list[str] = []
    if prefetched.get("alert_meaning"):
        lines.append(f"Alert meaning: {prefetched['alert_meaning']}")

    metrics_block = _host_prompt_block(prefetched)
    if metrics_block:
        lines.append(metrics_block)
    elif prefetched.get("bullets"):
        lines.append("Prefetched metrics (authoritative — use these in the Metrics section):")
        for bullet in prefetched["bullets"]:
            lines.append(f"• {bullet}")

    if prefetched.get("findings"):
        lines.append("")
        lines.append("Prefetched findings (use in Findings section):")
        for finding in prefetched["findings"]:
            lines.append(f"• {finding}")

    workload_bullets = prefetched.get("workload_bullets") or []
    if workload_bullets:
        lines.append("")
        lines.append("Prefetched workload context (use in Workload section):")
        for bullet in workload_bullets:
            lines.append(f"• {bullet}")

    snapshot = prefetched.get("snapshot") or {}
    if snapshot.get("resource") in ("cpu", "memory") and prefetched.get("alert_valid"):
        lines.append(
            "note: pod resource limit alert fired — limits are configured; "
            "do not claim missing limits"
        )

    return "\n".join(lines)
