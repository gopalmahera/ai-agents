import requests

from config import SLACK_WEBHOOK_URL


def _format_header(alert: dict) -> str:
    labels = alert.get("labels", {})
    parts = [
        f"*Alert:* `{labels.get('alertname', 'unknown')}`",
        f"*Severity:* `{labels.get('severity', 'unknown')}`",
    ]
    if labels.get("namespace"):
        parts.append(f"*Namespace:* `{labels['namespace']}`")
    if labels.get("pod"):
        parts.append(f"*Pod:* `{labels['pod']}`")
    if labels.get("instance"):
        parts.append(f"*Instance:* `{labels['instance']}`")
    return " | ".join(parts)


def send_slack(message: str, alert: dict | None = None) -> None:
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set")

    text = message
    if alert is not None:
        text = f"{_format_header(alert)}\n\n{message}"

    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={"text": text},
        timeout=30,
    )
    response.raise_for_status()
