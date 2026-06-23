import requests

from alert_context import AlertContext, build_alert_context
from config import SLACK_WEBHOOK_URL


def _format_header(ctx: AlertContext, labels: dict) -> str:
    severity = labels.get("severity", "unknown")
    line1 = f"*RCA — {ctx.alertname}* | severity: {severity}"

    line2 = ""
    if ctx.resource_type == "kubernetes":
        parts = []
        if ctx.namespace:
            parts.append(f"Namespace: {ctx.namespace}")
        if ctx.pod:
            parts.append(f"Pod: {ctx.pod}")
        line2 = " | ".join(parts)
    elif ctx.resource_type == "host":
        line2 = f"Host: {ctx.host_ip or ctx.instance or 'unknown'}"
    elif ctx.resource_type == "probe":
        line2 = f"Target: {ctx.target or ctx.instance or 'unknown'}"
    elif ctx.resource_type == "kafka":
        parts = []
        if ctx.topic:
            parts.append(f"Topic: {ctx.topic}")
        if ctx.group_id:
            parts.append(f"Group: {ctx.group_id}")
        line2 = " | ".join(parts)

    if line2:
        return f"{line1}\n{line2}"
    return line1


def send_slack(message: str, alert: dict | None = None) -> None:
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set")

    text = message
    if alert is not None:
        ctx = build_alert_context(alert)
        labels = alert.get("labels", {})
        text = f"{_format_header(ctx, labels)}\n\n{message}"

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
        timeout=30,
    )
    response.raise_for_status()
