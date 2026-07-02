"""One-line descriptions of alerts for RCA headers.

ALERT_MEANINGS can be overridden at runtime by mounting a YAML file at the path
set in the ALERT_CATALOG_PATH environment variable (default: /app/config/alert_catalog.yaml).
The YAML file must be a flat mapping of alertname → description string.
"""
import os
from pathlib import Path

_BUILTIN_ALERT_MEANINGS: dict[str, str] = {
    # Kubernetes pod
    "PODCPULimitsUage>=90": (
        "Pod container CPU usage reached ≥90% of its configured CPU limit for 5+ minutes."
    ),
    "PODMemoryLimitsUage>=90": (
        "Pod container memory usage reached ≥90% of its configured memory limit for 5+ minutes."
    ),
    "PODMemoryLimitsUage>=80": (
        "Pod container memory usage reached ≥80% of its configured memory limit for 5+ minutes."
    ),
    "PodRestart": "Kubernetes pod container restarted within the last 5 minutes.",
    "PodOOMKilled": (
        "Pod container was killed by the kernel OOM reaper after exceeding its memory limit."
    ),
    "PodEvicted": (
        "Pod was evicted from its node due to resource pressure (memory, disk, or CPU)."
    ),
    "pod.restart.vitalsstream": "Consumer Lag on group.wss.vitalsstream > 1000",
    "pod.restart.ecgstream": "Consumer Lag on group.misc.ecgstream > 1000",
    "pod.restart.vitals.kims": "Consumer Lag on group.wss.vitals.kims > 1000",
    # Pod anomaly detection
    "pod.anomaly.cpu.1h": (
        "Pod CPU usage is statistically anomalous (>2σ) compared to its 1-hour baseline."
    ),
    "pod.anomaly.cpu.1d": (
        "Pod CPU usage is statistically anomalous (>2σ) compared to its 1-day baseline."
    ),
    "pod.anomaly.memory.1h": (
        "Pod memory usage is statistically anomalous (>2σ) compared to its 1-hour baseline."
    ),
    "pod.anomaly.memory.1d": (
        "Pod memory usage is statistically anomalous (>2σ) compared to its 1-day baseline."
    ),
    "pod.anomaly.network.transmit.1h": (
        "Pod network transmit traffic is anomalous (>2σ) compared to its 1-hour baseline."
    ),
    "pod.anomaly.network.transmit.1d": (
        "Pod network transmit traffic is anomalous (>2σ) compared to its 1-day baseline."
    ),
    "pod.anomaly.network.receive.1h": (
        "Pod network receive traffic is anomalous (>2σ) compared to its 1-hour baseline."
    ),
    "pod.anomaly.network.receive.1d": (
        "Pod network receive traffic is anomalous (>2σ) compared to its 1-day baseline."
    ),
    # Blackbox / probe
    "BlackboxTargetDown": (
        "HTTP probe to target failed — endpoint returned no response or probe_success=0."
    ),
    "BlackboxHighLatency": (
        "HTTP probe latency exceeded 1.5 seconds — target is slow to respond."
    ),
    "BlackboxTCPProbeFailed": (
        "TCP probe to target failed — port is unreachable or connection refused."
    ),
    # Kafka broker throughput
    "NetworkKafkaHighBytesOut": (
        "Kafka topic outbound throughput exceeded 1024 KB/s — consumers or connectors are under high read load."
    ),
    "NetworkKafkaHighBytesIn": (
        "Kafka topic inbound throughput exceeded 1024 KB/s — producers are sending a high volume of data."
    ),
    # EC2 host
    "EC2HostDown": (
        "Node-exporter scrape target is down — Prometheus cannot reach the EC2 instance."
    ),
    "EC2HostOutOfMemory": "EC2 host has less than 10% memory available.",
    "EC2HostMemoryUnderMemoryPressure": (
        "EC2 host is under memory pressure with a high rate of major page faults."
    ),
    "EC2HostMemoryUnderUtilized": (
        "EC2 host memory has been under 20% utilization for 1 week — possible over-provisioning."
    ),
    "EC2HostSwapIsFillingUp": (
        "EC2 host swap space is over 80% used — memory pressure is spilling into swap."
    ),
    "EC2HostOutOfInodes": "EC2 host filesystem has less than 10% inodes remaining.",
    "EC2HostInodesWillFillIn24Hours": (
        "EC2 host filesystem inodes predicted to run out within 24 hours."
    ),
    "EC2HostUnusualDiskReadLatency": (
        "EC2 host disk read operations are taking >100ms — storage may be degraded."
    ),
    "EC2HostUnusualDiskWriteLatency": (
        "EC2 host disk write operations are taking >100ms — storage may be degraded."
    ),
    "EC2HostSystemdServiceCrashed": (
        "A systemd service on the EC2 host has entered the failed state."
    ),
    "EC2HostNetworkInterfaceSaturated": (
        "EC2 host network interface is >80% saturated (rx+tx approaching link speed)."
    ),
    "EC2HostConntrackLimit": (
        "EC2 host connection tracking table is >80% full — new connections may be dropped."
    ),
    "EC2HostClockSkew": (
        "EC2 host system clock is skewed >50ms and diverging — NTP sync issue."
    ),
    "EC2HostClockNotSynchronising": (
        "EC2 host NTP synchronisation is not active — clock accuracy degraded."
    ),
    "EC2HostPhysicalComponentTooHot": (
        "EC2 host physical component temperature exceeded 75°C."
    ),
    "EC2HostNodeOvertemperatureAlarm": (
        "EC2 host critical over-temperature alarm triggered on a physical component."
    ),
    "EC2HostRaidArrayGotInactive": (
        "EC2 host RAID array became inactive due to disk failures — data at risk."
    ),
    "EC2HostRaidDiskFailure": "EC2 host RAID array has at least one failed disk.",
    "EC2HostEdacCorrectableErrorsDetected": (
        "EC2 host EDAC correctable memory errors detected — hardware may be degrading."
    ),
    "EC2HostEdacUncorrectableErrorsDetected": (
        "EC2 host EDAC uncorrectable memory errors detected — hardware failure imminent."
    ),
}

_CATALOG_PATH = Path(os.environ.get("ALERT_CATALOG_PATH", "/app/config/alert_catalog.yaml"))


def _load_catalog() -> dict[str, str]:
    if not _CATALOG_PATH.exists():
        return _BUILTIN_ALERT_MEANINGS
    try:
        import yaml
        data = yaml.safe_load(_CATALOG_PATH.read_text()) or {}
        if isinstance(data, dict):
            merged = dict(_BUILTIN_ALERT_MEANINGS)
            merged.update({str(k): str(v) for k, v in data.items()})
            return merged
    except Exception as exc:
        print(f"Failed to load alert catalog from {_CATALOG_PATH}: {exc}; using built-in catalog")
    return _BUILTIN_ALERT_MEANINGS


ALERT_MEANINGS: dict[str, str] = _load_catalog()


def get_alert_meaning(alertname: str, alert: dict | None = None) -> str | None:
    if alertname in ALERT_MEANINGS:
        return ALERT_MEANINGS[alertname]

    if alertname.startswith("pod.restart."):
        annotations = (alert or {}).get("annotations") or {}
        description = annotations.get("description")
        if description:
            return description.strip().split("\n")[0]

    return None
