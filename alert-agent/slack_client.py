import requests

from config import SLACK_WEBHOOK_URL


_SEVERITY_COLORS = {
    "critical": "#E01E5A",
    "warning": "#ECB22E",
    "info": "#36C5F0",
}
_DEFAULT_COLOR = "#808080"


def format_alert_status(payload: dict) -> str:
    status = (payload.get("status") or "firing").upper()
    common = payload.get("commonLabels") or {}
    alertname = common.get("alertname")
    if not alertname and payload.get("alerts"):
        alertname = payload["alerts"][0].get("labels", {}).get("alertname")
    alertname = alertname or "unknown"

    if status == "FIRING":
        count = sum(
            1 for alert in payload.get("alerts", []) if alert.get("status") == "firing"
        )
        if count == 0:
            count = len(payload.get("alerts", [])) or 1
        return f"[FIRING:{count}] {alertname}"
    return f"[RESOLVED] {alertname}"


def _attachment_color(payload: dict) -> str:
    common = payload.get("commonLabels") or {}
    severity = (common.get("severity") or "").lower()
    if not severity and payload.get("alerts"):
        severity = (payload["alerts"][0].get("labels", {}).get("severity") or "").lower()
    return _SEVERITY_COLORS.get(severity, _DEFAULT_COLOR)


def send_alert_status(payload: dict) -> None:
    if not SLACK_WEBHOOK_URL:
        raise ValueError("SLACK_WEBHOOK_URL is not set")

    text = format_alert_status(payload)
    response = requests.post(
        SLACK_WEBHOOK_URL,
        json={
            "attachments": [
                {
                    "color": _attachment_color(payload),
                    "text": text,
                    "mrkdwn_in": ["text"],
                }
            ]
        },
        timeout=30,
    )
    response.raise_for_status()
