"""Alert catalog — descriptions and runbook links for RCA headers.

Entries can be extended at runtime via ALERT_CATALOG_PATH (default: /app/config/alert_catalog.yaml).
Each entry supports:
  description: one-line human-readable meaning
  runbook: optional URL shown in the Slack header
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_RUNBOOK_BASE = os.getenv("RUNBOOK_BASE_URL", "https://wiki.dozee.internal/runbooks").rstrip("/")
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_MSK_TOPICS_PATH = _DATA_DIR / "msk_topics.yaml"
_CATALOG_PATH = Path(os.environ.get("ALERT_CATALOG_PATH", "/app/config/alert_catalog.yaml"))


@dataclass(frozen=True)
class CatalogEntry:
    description: str
    runbook: str | None = None


def _runbook(category: str, slug: str) -> str:
    return f"{_RUNBOOK_BASE}/{category}/{slug}"


_STATIC_CATALOG: dict[str, CatalogEntry] = {
    # Kubernetes pod
    "PODCPULimitsUage>=90": CatalogEntry(
        "Pod container CPU usage reached ≥90% of its configured CPU limit for 5+ minutes.",
        _runbook("kubernetes", "pod-cpu-limits"),
    ),
    "PODMemoryLimitsUage>=90": CatalogEntry(
        "Pod container memory usage reached ≥90% of its configured memory limit for 5+ minutes.",
        _runbook("kubernetes", "pod-memory-limits"),
    ),
    "PODMemoryLimitsUage>=80": CatalogEntry(
        "Pod container memory usage reached ≥80% of its configured memory limit for 5+ minutes.",
        _runbook("kubernetes", "pod-memory-limits"),
    ),
    "PodRestart": CatalogEntry(
        "Kubernetes pod container restarted within the last 5 minutes.",
        _runbook("kubernetes", "pod-restart"),
    ),
    "PodRestarting": CatalogEntry(
        "Kubernetes pod is in a restart loop — container keeps restarting.",
        _runbook("kubernetes", "pod-restart"),
    ),
    "PodOOMKilled": CatalogEntry(
        "Pod container was killed by the kernel OOM reaper after exceeding its memory limit.",
        _runbook("kubernetes", "pod-oom"),
    ),
    "PodEvicted": CatalogEntry(
        "Pod was evicted from its node due to resource pressure (memory, disk, or CPU).",
        _runbook("kubernetes", "pod-evicted"),
    ),
    "NetworkPodHighTransmit": CatalogEntry(
        "Pod network transmit rate exceeded the configured threshold.",
        _runbook("kubernetes", "pod-network-transmit"),
    ),
    "NetworkPodHighReceive": CatalogEntry(
        "Pod network receive rate exceeded the configured threshold.",
        _runbook("kubernetes", "pod-network-receive"),
    ),
    "pod.restart.vitalsstream": CatalogEntry(
        "MSK consumer lag on group.wss.vitalsstream exceeded threshold.",
        _runbook("kafka", "msk-consumer-lag"),
    ),
    "pod.restart.ecgstream": CatalogEntry(
        "MSK consumer lag on group.misc.ecgstream exceeded threshold.",
        _runbook("kafka", "msk-consumer-lag"),
    ),
    "pod.restart.vitals.kims": CatalogEntry(
        "MSK consumer lag on group.wss.vitals.kims exceeded threshold.",
        _runbook("kafka", "msk-consumer-lag"),
    ),
    # Pod anomaly detection
    "pod.anomaly.cpu.1h": CatalogEntry(
        "Pod CPU usage is statistically anomalous (>2σ) compared to its 1-hour baseline.",
        _runbook("kubernetes", "pod-anomaly-cpu"),
    ),
    "pod.anomaly.cpu.1d": CatalogEntry(
        "Pod CPU usage is statistically anomalous (>2σ) compared to its 1-day baseline.",
        _runbook("kubernetes", "pod-anomaly-cpu"),
    ),
    "pod.anomaly.memory.1h": CatalogEntry(
        "Pod memory usage is statistically anomalous (>2σ) compared to its 1-hour baseline.",
        _runbook("kubernetes", "pod-anomaly-memory"),
    ),
    "pod.anomaly.memory.1d": CatalogEntry(
        "Pod memory usage is statistically anomalous (>2σ) compared to its 1-day baseline.",
        _runbook("kubernetes", "pod-anomaly-memory"),
    ),
    "pod.anomaly.network.transmit.1h": CatalogEntry(
        "Pod network transmit traffic is anomalous (>2σ) compared to its 1-hour baseline.",
        _runbook("kubernetes", "pod-anomaly-network"),
    ),
    "pod.anomaly.network.transmit.1d": CatalogEntry(
        "Pod network transmit traffic is anomalous (>2σ) compared to its 1-day baseline.",
        _runbook("kubernetes", "pod-anomaly-network"),
    ),
    "pod.anomaly.network.receive.1h": CatalogEntry(
        "Pod network receive traffic is anomalous (>2σ) compared to its 1-hour baseline.",
        _runbook("kubernetes", "pod-anomaly-network"),
    ),
    "pod.anomaly.network.receive.1d": CatalogEntry(
        "Pod network receive traffic is anomalous (>2σ) compared to its 1-day baseline.",
        _runbook("kubernetes", "pod-anomaly-network"),
    ),
    # Blackbox / probe / TLS
    "BlackboxTargetDown": CatalogEntry(
        "HTTP probe to target failed — endpoint returned no response or probe_success=0.",
        _runbook("probe", "blackbox-target-down"),
    ),
    "BlackboxHighLatency": CatalogEntry(
        "HTTP probe latency exceeded 1.5 seconds — target is slow to respond.",
        _runbook("probe", "blackbox-high-latency"),
    ),
    "BlackboxTCPProbeFailed": CatalogEntry(
        "TCP probe to target failed — port is unreachable or connection refused.",
        _runbook("probe", "blackbox-tcp-failed"),
    ),
    "TLSCertificateExpiringSoon": CatalogEntry(
        "TLS certificate for the probed target expires within the configured warning window.",
        _runbook("probe", "tls-certificate-expiring"),
    ),
    # Kafka broker throughput
    "NetworkKafkaHighBytesOut": CatalogEntry(
        "Kafka topic outbound throughput exceeded 1024 KB/s — consumers or connectors are under high read load.",
        _runbook("kafka", "broker-throughput"),
    ),
    "NetworkKafkaHighBytesIn": CatalogEntry(
        "Kafka topic inbound throughput exceeded 1024 KB/s — producers are sending a high volume of data.",
        _runbook("kafka", "broker-throughput"),
    ),
    # EC2 host
    "EC2HostDown": CatalogEntry(
        "Node-exporter scrape target is down — Prometheus cannot reach the EC2 instance.",
        _runbook("ec2", "host-down"),
    ),
    "EC2HostOutOfMemory": CatalogEntry(
        "EC2 host has less than 10% memory available.",
        _runbook("ec2", "out-of-memory"),
    ),
    "EC2HostMemoryUnderMemoryPressure": CatalogEntry(
        "EC2 host is under memory pressure with a high rate of major page faults.",
        _runbook("ec2", "memory-pressure"),
    ),
    "EC2HostMemoryUnderUtilized": CatalogEntry(
        "EC2 host memory has been under 20% utilization for 1 week — possible over-provisioning.",
        _runbook("ec2", "memory-underutilized"),
    ),
    "EC2HostHighCpuLoad": CatalogEntry(
        "EC2 host CPU utilization exceeded 80% for the configured duration.",
        _runbook("ec2", "high-cpu"),
    ),
    "EC2HostHighCPU": CatalogEntry(
        "EC2 host CPU utilization exceeded the configured threshold.",
        _runbook("ec2", "high-cpu"),
    ),
    "EC2HostCpuStealNoisyNeighbor": CatalogEntry(
        "EC2 host CPU steal time is elevated — noisy neighbor on the hypervisor.",
        _runbook("ec2", "cpu-steal"),
    ),
    "EC2HostUnusualNetworkThroughputIn": CatalogEntry(
        "EC2 host inbound network throughput is unusually high.",
        _runbook("ec2", "network-throughput"),
    ),
    "EC2HostUnusualNetworkThroughputOut": CatalogEntry(
        "EC2 host outbound network throughput is unusually high.",
        _runbook("ec2", "network-throughput"),
    ),
    "EC2HostUnusualDiskReadRate": CatalogEntry(
        "EC2 host disk read throughput is unusually high.",
        _runbook("ec2", "disk-io"),
    ),
    "EC2HostUnusualDiskWriteRate": CatalogEntry(
        "EC2 host disk write throughput is unusually high.",
        _runbook("ec2", "disk-io"),
    ),
    "EC2HostOutOfDiskSpace": CatalogEntry(
        "EC2 host filesystem has less than 10% disk space available.",
        _runbook("ec2", "disk-space"),
    ),
    "EC2HostDiskWillFillIn24Hours": CatalogEntry(
        "EC2 host filesystem is predicted to run out of disk space within 24 hours.",
        _runbook("ec2", "disk-space"),
    ),
    "EC2HostSwapIsFillingUp": CatalogEntry(
        "EC2 host swap space is over 80% used — memory pressure is spilling into swap.",
        _runbook("ec2", "swap"),
    ),
    "EC2HostOutOfInodes": CatalogEntry(
        "EC2 host filesystem has less than 10% inodes remaining.",
        _runbook("ec2", "inodes"),
    ),
    "EC2HostInodesWillFillIn24Hours": CatalogEntry(
        "EC2 host filesystem inodes predicted to run out within 24 hours.",
        _runbook("ec2", "inodes"),
    ),
    "EC2HostUnusualDiskReadLatency": CatalogEntry(
        "EC2 host disk read operations are taking >100ms — storage may be degraded.",
        _runbook("ec2", "disk-latency"),
    ),
    "EC2HostUnusualDiskWriteLatency": CatalogEntry(
        "EC2 host disk write operations are taking >100ms — storage may be degraded.",
        _runbook("ec2", "disk-latency"),
    ),
    "EC2HostSystemdServiceCrashed": CatalogEntry(
        "A systemd service on the EC2 host has entered the failed state.",
        _runbook("ec2", "systemd-failed"),
    ),
    "EC2HostNetworkInterfaceSaturated": CatalogEntry(
        "EC2 host network interface is >80% saturated (rx+tx approaching link speed).",
        _runbook("ec2", "network-saturation"),
    ),
    "EC2HostConntrackLimit": CatalogEntry(
        "EC2 host connection tracking table is >80% full — new connections may be dropped.",
        _runbook("ec2", "conntrack"),
    ),
    "EC2HostClockSkew": CatalogEntry(
        "EC2 host system clock is skewed >50ms and diverging — NTP sync issue.",
        _runbook("ec2", "clock-skew"),
    ),
    "EC2HostClockNotSynchronising": CatalogEntry(
        "EC2 host NTP synchronisation is not active — clock accuracy degraded.",
        _runbook("ec2", "clock-sync"),
    ),
    "EC2HostPhysicalComponentTooHot": CatalogEntry(
        "EC2 host physical component temperature exceeded 75°C.",
        _runbook("ec2", "temperature"),
    ),
    "EC2HostNodeOvertemperatureAlarm": CatalogEntry(
        "EC2 host critical over-temperature alarm triggered on a physical component.",
        _runbook("ec2", "temperature"),
    ),
    "EC2HostRaidArrayGotInactive": CatalogEntry(
        "EC2 host RAID array became inactive due to disk failures — data at risk.",
        _runbook("ec2", "raid"),
    ),
    "EC2HostRaidDiskFailure": CatalogEntry(
        "EC2 host RAID array has at least one failed disk.",
        _runbook("ec2", "raid"),
    ),
    "EC2HostEdacCorrectableErrorsDetected": CatalogEntry(
        "EC2 host EDAC correctable memory errors detected — hardware may be degrading.",
        _runbook("ec2", "edac"),
    ),
    "EC2HostEdacUncorrectableErrorsDetected": CatalogEntry(
        "EC2 host EDAC uncorrectable memory errors detected — hardware failure imminent.",
        _runbook("ec2", "edac"),
    ),
}


def _load_msk_topics() -> list[str]:
    if not _MSK_TOPICS_PATH.exists():
        return []
    data = yaml.safe_load(_MSK_TOPICS_PATH.read_text()) or {}
    return [str(t) for t in data.get("topics", [])]


def _msk_catalog() -> dict[str, CatalogEntry]:
    entries: dict[str, CatalogEntry] = {}
    lag_runbook = _runbook("kafka", "msk-consumer-lag")
    nomessage_runbook = _runbook("kafka", "msk-no-messages")
    for topic in _load_msk_topics():
        entries[f"msk.kb.{topic} > 3000"] = CatalogEntry(
            f"MSK KB cluster consumer lag on topic {topic} exceeded 3000 messages.",
            lag_runbook,
        )
        entries[f"msk.kb.{topic} > 50000"] = CatalogEntry(
            f"MSK KB cluster consumer lag on topic {topic} exceeded 50000 messages.",
            lag_runbook,
        )
        entries[f"msk.kbc.{topic} > 50000"] = CatalogEntry(
            f"MSK KBC cluster consumer lag on topic {topic} exceeded 50000 messages.",
            lag_runbook,
        )
        entries[f"msk.kb.nomessage.{topic} = 0"] = CatalogEntry(
            f"No messages observed on MSK KB topic {topic} within the expected window.",
            nomessage_runbook,
        )
        entries[f"msk.kbc.nomessage.{topic} = 0"] = CatalogEntry(
            f"No messages observed on MSK KBC topic {topic} within the expected window.",
            nomessage_runbook,
        )
    return entries


def _parse_yaml_entry(value) -> CatalogEntry | None:
    if isinstance(value, str):
        return CatalogEntry(description=value)
    if isinstance(value, dict):
        description = value.get("description")
        if not description:
            return None
        runbook = value.get("runbook")
        return CatalogEntry(description=str(description), runbook=str(runbook) if runbook else None)
    return None


def _load_yaml_overlay(path: Path) -> dict[str, CatalogEntry]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:
        from utils.log import get_logger
        get_logger(__name__).warning(
            "Failed to load alert catalog from %s: %s; using built-in catalog",
            path,
            exc,
        )
        return {}
    if not isinstance(data, dict):
        return {}
    overlay: dict[str, CatalogEntry] = {}
    for key, value in data.items():
        entry = _parse_yaml_entry(value)
        if entry:
            overlay[str(key)] = entry
    return overlay


def _build_catalog() -> dict[str, CatalogEntry]:
    merged = dict(_STATIC_CATALOG)
    merged.update(_msk_catalog())
    merged.update(_load_yaml_overlay(_CATALOG_PATH))
    return merged


CATALOG: dict[str, CatalogEntry] = _build_catalog()

# Backward-compatible flat description map.
ALERT_MEANINGS: dict[str, str] = {k: v.description for k, v in CATALOG.items()}


_PATTERN_RULES: list[tuple[re.Pattern[str], CatalogEntry]] = [
    (re.compile(r"^msk\.(kbc|kb)\..+>\s*\d+"), CatalogEntry(
        "MSK consumer lag exceeded the configured threshold for this topic.",
        _runbook("kafka", "msk-consumer-lag"),
    )),
    (re.compile(r"^msk\.(kbc|kb)\.nomessage\..+=\s*0"), CatalogEntry(
        "No messages observed on this MSK topic within the expected window.",
        _runbook("kafka", "msk-no-messages"),
    )),
    (re.compile(r"^pod\.restart\."), CatalogEntry(
        "MSK consumer lag alert (misnamed pod.restart.* rule) exceeded threshold.",
        _runbook("kafka", "msk-consumer-lag"),
    )),
    (re.compile(r"^pod\.anomaly\."), CatalogEntry(
        "Pod metric is statistically anomalous compared to its baseline window.",
        _runbook("kubernetes", "pod-anomaly"),
    )),
    (re.compile(r"^EC2Host"), CatalogEntry(
        "EC2 host infrastructure alert from node-exporter metrics.",
        _runbook("ec2", "host-generic"),
    )),
    (re.compile(r"^Blackbox"), CatalogEntry(
        "Blackbox probe check failed or degraded.",
        _runbook("probe", "blackbox-generic"),
    )),
    (re.compile(r"^loki\.|^Loki"), CatalogEntry(
        "Loki log-based alert — log pattern or error rate threshold breached.",
        _runbook("loki", "log-alert"),
    )),
]


def _lookup_entry(alertname: str) -> CatalogEntry | None:
    if alertname in CATALOG:
        return CATALOG[alertname]
    for pattern, entry in _PATTERN_RULES:
        if pattern.search(alertname):
            return entry
    return None


def get_alert_meaning(alertname: str, alert: dict | None = None) -> str | None:
    entry = _lookup_entry(alertname)
    if entry:
        return entry.description

    if alertname.startswith("pod.restart."):
        annotations = (alert or {}).get("annotations") or {}
        description = annotations.get("description")
        if description:
            return description.strip().split("\n")[0]

    return None


def get_runbook_url(alertname: str) -> str | None:
    entry = _lookup_entry(alertname)
    return entry.runbook if entry else None


def export_catalog_yaml(path: Path) -> int:
    """Write the built-in catalog (static + MSK expansion) to a YAML file."""
    payload = {
        name: {"description": entry.description, "runbook": entry.runbook}
        for name, entry in sorted({**_STATIC_CATALOG, **_msk_catalog()}.items())
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=True, allow_unicode=True))
    return len(payload)
