from alert_context import AlertContext
from host_metrics import build_findings_bullets, default_host_actions


def _host_summary(ctx: AlertContext) -> str:
    if ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
        return f"{ctx.alertname}: Host experiencing high rate of major page faults indicating memory pressure."
    return f"{ctx.alertname}: Alert fired on host {ctx.host_ip or ctx.scrape_instance}."


def _host_root_cause(ctx: AlertContext, prefetched: dict | None) -> str:
    snapshot = (prefetched or {}).get("snapshot") or {}
    page_faults = snapshot.get("major_page_faults_per_sec") or ctx.alert_firing_value
    memory = snapshot.get("memory") or {}
    avail = memory.get("available_percent")

    host = ctx.host_ip or ctx.scrape_instance or "the host"
    if page_faults is not None and ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
        cause = (
            f"Host {host} has sustained major page faults at {page_faults:.1f}/s, "
            "indicating significant memory pressure."
        )
        if avail is not None:
            cause += f" Memory available is critically low at {avail:.1f}%."
        return cause

    return f"Host {host} triggered {ctx.alertname}; review prefetched metrics for the primary signal."


def build_deterministic_rca(ctx: AlertContext, prefetched: dict | None) -> str:
    host = ctx.host_ip or "unknown"
    scrape = ctx.scrape_instance or ctx.instance or "unknown"

    lines = [
        f"*Alert summary:*\n{_host_summary(ctx)}",
        "",
        "*Subject:*",
        f"Host: {host}",
        f"Instance (scrape): {scrape}",
    ]

    bullets = list((prefetched or {}).get("bullets") or [])
    lines.extend(["", "*Metrics:*"])
    if bullets:
        lines.extend(f"• {b}" for b in bullets)
    else:
        lines.append("• No metrics prefetched")

    findings = list((prefetched or {}).get("findings") or [])
    if not findings and prefetched:
        findings = build_findings_bullets(ctx, prefetched)
    lines.extend(["", "*Findings:*"])
    if findings:
        lines.extend(f"• {f}" for f in findings)
    else:
        lines.append("• Alert condition confirmed from available signals.")

    lines.extend(["", "*Probable root cause:*", _host_root_cause(ctx, prefetched)])

    actions = default_host_actions(ctx)
    lines.extend(["", "*Recommended actions:*"])
    for idx, action in enumerate(actions[:3], start=1):
        lines.append(f"{idx}. {action}")

    return "\n".join(lines)
