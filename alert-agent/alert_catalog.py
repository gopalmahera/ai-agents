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
}


def get_alert_meaning(alertname: str) -> str | None:
    return ALERT_MEANINGS.get(alertname)
