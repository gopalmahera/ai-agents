from alert_context import AlertContext
from host_metrics import prefetch_host_metrics, prefetched_to_prompt_block as _host_prompt_block
from kafka_context import prefetch_kafka_context
from kafka_metrics import build_findings_bullets as build_kafka_findings_bullets
from kafka_metrics import prefetch_kafka_metrics
from pod_metrics import build_findings_bullets as build_pod_findings_bullets, prefetch_pod_metrics
from workload_context import prefetch_workload_context


def build_prefetch(ctx: AlertContext, alert: dict) -> dict | None:
    metrics = (
        prefetch_host_metrics(ctx, alert)
        or prefetch_pod_metrics(ctx, alert)
        or prefetch_kafka_metrics(ctx, alert)
    )
    workload = prefetch_workload_context(ctx, alert)
    kafka_ctx = prefetch_kafka_context(ctx, alert)

    if not metrics and not workload and not kafka_ctx:
        return None

    result = metrics or {
        "bullets": [],
        "findings": [],
        "snapshot": {},
        "alert_valid": False,
    }

    context_block = workload or kafka_ctx
    if context_block:
        if context_block.get("alert_meaning"):
            result["alert_meaning"] = context_block["alert_meaning"]
        if context_block.get("bullets"):
            result["workload_bullets"] = list(context_block["bullets"])
        if workload:
            result["workload"] = workload

    snapshot = result.get("snapshot") or {}
    if snapshot.get("resource") == "cpu" or snapshot.get("resource") == "memory":
        result["findings"] = build_pod_findings_bullets(ctx, result)
    elif snapshot.get("resource") == "kafka" and not result.get("findings"):
        result["findings"] = build_kafka_findings_bullets(ctx, result)

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
