import requests

from alert_context import AlertContext, build_alert_context
from config import SLACK_WEBHOOK_URL


_SEVERITY_COLORS = {
    "critical": "#E01E5A",
    "warning": "#ECB22E",
    "info": "#36C5F0",
}
_DEFAULT_COLOR = "#808080"


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


def _format_header(ctx: AlertContext, labels: dict) -> str:
    severity = labels.get("severity", "unknown")
    lines = [f"*RCA — {ctx.alertname}* | severity: {severity}"]

    region_line = _region_line(ctx, labels)
    if region_line:
        lines.append(region_line)

    resource_line = _resource_line(ctx)
    if resource_line:
        lines.append(resource_line)

    return "\n".join(lines)


def _attachment_color(labels: dict) -> str:
    severity = (labels.get("severity") or "").lower()
    return _SEVERITY_COLORS.get(severity, _DEFAULT_COLOR)


def send_slack(message: str, alert: dict | None = None) -> None:
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set")

    text = message
    payload: dict = {"text": text}

    if alert is not None:
        ctx = build_alert_context(alert)
        labels = alert.get("labels", {})
        text = f"{_format_header(ctx, labels)}\n\n{message}"
        payload = {
            "attachments": [
                {
                    "color": _attachment_color(labels),
                    "text": text,
                    "mrkdwn_in": ["text"],
                }
            ]
        }

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
