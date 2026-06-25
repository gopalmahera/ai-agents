"""One-line descriptions of alerts for RCA headers."""

ALERT_MEANINGS: dict[str, str] = {
    "PODCPULimitsUage>=90": (
        "Pod container CPU usage reached ≥90% of its configured CPU limit for 5+ minutes."
    ),
    "PODMemoryLimitsUage>=90": (
        "Pod container memory usage reached ≥90% of its configured memory limit for 5+ minutes."
    ),
    "EC2HostMemoryUnderMemoryPressure": (
        "EC2 host is under memory pressure with a high rate of major page faults."
    ),
    "PodRestart": "Kubernetes pod container restarted within the last 5 minutes.",
    "pod.restart.vitalsstream": "Consumer Lag on group.wss.vitalsstream > 1000",
    "pod.restart.ecgstream": "Consumer Lag on group.misc.ecgstream > 1000",
    "pod.restart.vitals.kims": "Consumer Lag on group.wss.vitals.kims > 1000",
}


def get_alert_meaning(alertname: str, alert: dict | None = None) -> str | None:
    if alertname in ALERT_MEANINGS:
        return ALERT_MEANINGS[alertname]

    if alertname.startswith("pod.restart."):
        annotations = (alert or {}).get("annotations") or {}
        description = annotations.get("description")
        if description:
            return description.strip().split("\n")[0]

    return None
