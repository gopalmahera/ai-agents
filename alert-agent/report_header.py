from datetime import datetime, timezone

from alert_context import AlertContext


_SEVERITY_EMOJI = {
    "critical": ":rotating_light:",
    "warning": ":warning:",
    "info": ":information_source:",
}


def _region_line(ctx: AlertContext, labels: dict) -> str:
    region = labels.get("region") or ctx.region
    cloud = labels.get("cloud") or ctx.cloud
    stage = labels.get("stage") or ctx.stage
    if not region and not cloud and not stage:
        return ""
    parts = []
    if region:
        parts.append(f"Region: {region}")
    if cloud:
        parts.append(f"Cloud: {cloud}")
    if stage:
        parts.append(f"Stage: {stage}")
    return " | ".join(parts)


def _resource_line(ctx: AlertContext) -> str:
    if ctx.resource_type == "kubernetes":
        parts = []
        if ctx.namespace:
            parts.append(f"Namespace: {ctx.namespace}")
        if ctx.pod:
            parts.append(f"Pod: {ctx.pod}")
        return " | ".join(parts)
    if ctx.resource_type == "host":
        return f"Host: {ctx.host_ip or ctx.instance or 'unknown'}"
    if ctx.resource_type == "probe":
        return f"Target: {ctx.target or ctx.instance or 'unknown'}"
    if ctx.resource_type == "kafka":
        parts = []
        if ctx.topic:
            parts.append(f"Topic: {ctx.topic}")
        if ctx.group_id:
            parts.append(f"Group: {ctx.group_id}")
        return " | ".join(parts)
    return ""


def _format_started_at(alert: dict) -> str:
    starts_at = alert.get("startsAt", "")
    if not starts_at or starts_at.startswith("0001"):
        return ""
    try:
        dt = datetime.fromisoformat(starts_at.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return ""


def format_report_header(ctx: AlertContext, labels: dict, alert: dict | None = None) -> str:
    severity = labels.get("severity", "unknown")
    emoji = _SEVERITY_EMOJI.get(severity.lower(), ":bell:")

    # Line 1: alert name + severity
    lines = [f"{emoji} *{ctx.alertname}* | severity: {severity}"]

    # Line 2: resource identity + started timestamp
    meta_parts = []
    resource_line = _resource_line(ctx)
    if resource_line:
        meta_parts.append(resource_line)
    region_line = _region_line(ctx, labels)
    if region_line:
        meta_parts.append(region_line)
    started = _format_started_at(alert or {})
    if started:
        meta_parts.append(f"Started: {started}")
    if meta_parts:
        lines.append(" | ".join(meta_parts))

    # Line 3: annotation summary (first line, capped at 150 chars)
    annotations = (alert or {}).get("annotations", {})
    summary = (annotations.get("summary") or annotations.get("description") or "").strip()
    if summary:
        first_line = summary.split("\n")[0][:150]
        lines.append(f"_{first_line}_")

    # Line 4: Prometheus query link
    generator_url = (alert or {}).get("generatorURL", "")
    if generator_url:
        lines.append(f"<{generator_url}|View in Prometheus>")

    return "\n".join(lines)
