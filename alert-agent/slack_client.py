import time
import requests

from config import SLACK_WEBHOOK_URL
from routing import resolve_webhook_url


_SEVERITY_COLORS = {
    "critical": "#E01E5A",
    "warning": "#ECB22E",
    "info": "#36C5F0",
}
_DEFAULT_COLOR = "#808080"
_BODY_COLOR = "#D3D3D3"
_MAX_BODY_CHARS = 3800


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


def format_status_for_alert(alert: dict) -> str:
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")
    if alert.get("status") == "resolved":
        return f"[RESOLVED] {alertname}"
    return f"[FIRING:1] {alertname}"


def _severity_color(labels: dict) -> str:
    severity = (labels.get("severity") or "").lower()
    return _SEVERITY_COLORS.get(severity, _DEFAULT_COLOR)


def _post_slack(payload: dict, webhook_url: str = "") -> None:
    url = webhook_url or SLACK_WEBHOOK_URL
    if not url:
        raise ValueError("No Slack webhook URL configured (set SLACK_WEBHOOK_URL or ROUTING_CONFIG_PATH)")
    delays = [2, 4, 8]
    last_exc: Exception | None = None
    for attempt, delay in enumerate(delays, start=1):
        try:
            response = requests.post(url, json=payload, timeout=30)
            response.raise_for_status()
            return
        except Exception as exc:
            last_exc = exc
            if attempt < len(delays):
                print(f"Slack post attempt {attempt} failed ({exc}); retrying in {delay}s")
                time.sleep(delay)
    raise last_exc


def send_alert_status(payload: dict) -> None:
    labels = payload.get("commonLabels") or {}
    if not labels and payload.get("alerts"):
        labels = payload["alerts"][0].get("labels", {})
    slack_payload = {
        "attachments": [
            {
                "color": _severity_color(labels),
                "text": format_alert_status(payload),
                "mrkdwn_in": ["text"],
            }
        ]
    }
    _post_slack(slack_payload, resolve_webhook_url(labels))


def send_alert_report(alert: dict, header: str, body: str) -> None:
    labels = alert.get("labels", {})
    if len(body) > _MAX_BODY_CHARS:
        body = body[:_MAX_BODY_CHARS] + "\n\n_[Report truncated — see log file for full output]_"
    slack_payload = {
        "attachments": [
            {
                "color": _severity_color(labels),
                "text": header,
                "mrkdwn_in": ["text"],
            },
            {
                "color": _BODY_COLOR,
                "text": body,
                "mrkdwn_in": ["text"],
            },
        ]
    }
    _post_slack(slack_payload, resolve_webhook_url(labels))
