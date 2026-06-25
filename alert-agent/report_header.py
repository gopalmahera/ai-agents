from alert_context import AlertContext


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


def format_report_header(ctx: AlertContext, labels: dict) -> str:
    severity = labels.get("severity", "unknown")
    lines = [f"RCA — {ctx.alertname} | severity: {severity}"]

    region_line = _region_line(ctx, labels)
    if region_line:
        lines.append(region_line)

    resource_line = _resource_line(ctx)
    if resource_line:
        lines.append(resource_line)

    return "\n".join(lines)
