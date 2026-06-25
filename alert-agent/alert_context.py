import copy
import re
from dataclasses import dataclass


_POD_NS_RE = re.compile(
    r"Pod\s+([^\s/]+)/([^\s(]+)",
    re.IGNORECASE,
)
_NS_POD_RE = re.compile(
    r"namespace\s+([^\s]+).{0,40}pod\s+([^\s.]+)",
    re.IGNORECASE,
)

_CONSUMER_LAG_DESC = re.compile(
    r"Consumer Lag on (group\.[^\s>]+)",
    re.IGNORECASE,
)
_TOPIC_LAG_SUMMARY = re.compile(
    r"Topic Lag on ([^\s]+)",
    re.IGNORECASE,
)

# Misnamed MSK lag alerts use alertname pod.restart.* with namespace label msk.
_POD_RESTART_MSK_TOPICS: dict[str, tuple[str, str, str]] = {
    "pod.restart.vitalsstream": ("msk-kb", "wss.vitalsstream", "group.wss.vitalsstream"),
    "pod.restart.ecgstream": ("msk-kb", "misc.ecgstream", "group.misc.ecgstream"),
    "pod.restart.vitals.kims": ("msk-kb", "wss.vitalsstream", "group.wss.vitals.kims"),
}

_POD_RESTART_WORKLOADS: dict[str, tuple[str, str]] = {
    "pod.restart.ecgstream": ("dozeeplatform", "sse"),
    "pod.restart.vitalsstream": ("dozeeplatform", "vitalswss"),
    "pod.restart.vitals.kims": ("dozeeplatform", "kimsvitalsint"),
}

_FAKE_NAMESPACES = frozenset({"ec2", "blackbox", "msk", "kbc.msk", "kbcmsk"})

_ALERT_VALUE_RE = re.compile(r"VALUE\s*=\s*([\d.]+)", re.IGNORECASE)
_EC2_DEFAULT_SCRAPE_JOB = "AWSEC2NodeExporter"

_EC2_PRIMARY_METRIC: dict[str, str] = {
    "EC2HostMemoryUnderMemoryPressure": "major_page_faults_per_sec",
    "EC2HostOutOfMemory": "memory_available_percent",
    "EC2HostHighCpuLoad": "cpu_percent",
    "EC2HostCpuStealNoisyNeighbor": "cpu_steal_percent",
    "EC2HostUnusualNetworkThroughputIn": "network_receive_mbps",
    "EC2HostUnusualNetworkThroughputOut": "network_transmit_mbps",
    "EC2HostUnusualDiskReadRate": "disk_read_mbps",
    "EC2HostUnusualDiskWriteRate": "disk_write_mbps",
    "EC2HostOutOfDiskSpace": "disk_avail_percent",
    "EC2HostDiskWillFillIn24Hours": "disk_avail_percent",
}


@dataclass
class AlertContext:
    alertname: str
    resource_type: str
    namespace: str | None
    pod: str | None
    container: str | None
    instance: str | None
    module: str | None
    job: str | None
    topic: str | None
    group_id: str | None
    host_ip: str | None
    scrape_instance: str | None
    target: str | None
    msk_job: str | None
    workload_namespace: str | None
    workload_deployment: str | None
    scrape_job: str | None
    alert_firing_value: float | None
    primary_metric: str | None
    region: str | None
    cloud: str | None
    stage: str | None

    def to_prompt_block(self) -> str:
        lines = [
            f"alertname: {self.alertname}",
            f"resource_type: {self.resource_type}",
        ]
        if self.resource_type == "kubernetes":
            if self.namespace:
                lines.append(f"namespace: {self.namespace}")
            if self.pod:
                lines.append(f"pod: {self.pod}")
            if self.container:
                lines.append(f"container: {self.container}")
            if self.region:
                lines.append(f"region: {self.region}")
            if self.cloud:
                lines.append(f"cloud: {self.cloud}")
            if self.stage:
                lines.append(f"stage: {self.stage}")
            if self.alertname in ("PODCPULimitsUage>=90", "PODMemoryLimitsUage>=90"):
                lines.append(
                    "note: prefetched pod metrics use the same PromQL as the alert rule; "
                    "do not claim CPU/memory limits are missing when alert fired"
                )
        elif self.resource_type == "host":
            if self.host_ip:
                lines.append(f"host_ip: {self.host_ip}")
            if self.scrape_instance:
                lines.append(f"scrape_instance: {self.scrape_instance}")
            if self.scrape_job:
                lines.append(f"scrape_job: {self.scrape_job}")
            if self.primary_metric:
                lines.append(f"primary_metric: {self.primary_metric}")
            if self.alert_firing_value is not None:
                lines.append(f"alert_firing_value: {self.alert_firing_value}")
            lines.append(
                "note: EC2 hosts use scrape job AWSEC2NodeExporter; alert firing proves node_exporter is reachable"
            )
        elif self.resource_type == "probe":
            if self.target:
                lines.append(f"target: {self.target}")
            if self.module:
                lines.append(f"module: {self.module}")
        elif self.resource_type == "kafka":
            if self.topic:
                lines.append(f"topic: {self.topic}")
            if self.group_id:
                lines.append(f"group_id: {self.group_id}")
            if self.msk_job:
                lines.append(f"msk_job: {self.msk_job}")
            if self.workload_namespace and self.workload_deployment:
                lines.append(
                    f"related_workload: {self.workload_namespace}/{self.workload_deployment}"
                )
                lines.append(
                    "note: alertname pod.restart.* with namespace msk is MSK consumer lag, not a pod restart"
                )
        return "\n".join(lines)


def _parse_alert_firing_value(annotations: dict) -> float | None:
    description = annotations.get("description", "")
    match = _ALERT_VALUE_RE.search(description)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _primary_metric_for_alert(alertname: str) -> str | None:
    return _EC2_PRIMARY_METRIC.get(alertname)


def _parse_from_description(description: str) -> tuple[str | None, str | None]:
    if not description:
        return None, None
    match = _POD_NS_RE.search(description)
    if match:
        return match.group(1), match.group(2)
    match = _NS_POD_RE.search(description)
    if match:
        return match.group(1), match.group(2)
    return None, None


def _parse_kafka_from_annotations(
    annotations: dict,
) -> tuple[str | None, str | None]:
    description = annotations.get("description", "")
    summary = annotations.get("summary", "")
    group_id = None
    topic = None
    match = _CONSUMER_LAG_DESC.search(description)
    if match:
        group_id = match.group(1)
    match = _TOPIC_LAG_SUMMARY.search(summary)
    if match:
        topic = match.group(1)
    return topic, group_id


def _is_kafka_alert(alertname: str, labels: dict) -> bool:
    if alertname.startswith("msk."):
        return True
    job = labels.get("job", "")
    if job.startswith("msk-") and labels.get("topic"):
        return True
    if alertname.startswith("pod.restart.") and labels.get("namespace", "").lower() == "msk":
        return True
    return False


def _resource_type(alertname: str, labels: dict) -> str:
    if _is_kafka_alert(alertname, labels):
        return "kafka"
    if alertname.startswith("EC2Host"):
        return "host"
    if alertname.startswith("Blackbox") or alertname == "TLSCertificateExpiringSoon":
        return "probe"
    return "kubernetes"


def _infer_msk_from_pod_restart_alertname(
    alertname: str,
) -> tuple[str | None, str | None, str | None]:
    return _POD_RESTART_MSK_TOPICS.get(alertname, (None, None, None))


def _host_ip(instance: str | None) -> str | None:
    if not instance:
        return None
    if ":" in instance:
        return instance.rsplit(":", 1)[0]
    return instance


def _infer_msk_from_alertname(alertname: str) -> tuple[str | None, str | None, str | None]:
    """Return (job, topic, group_id) parsed from msk.* alertnames."""
    nomessage = re.match(r"^msk\.(kbc|kb)\.nomessage\.(.+?)\s*=\s*0", alertname)
    if nomessage:
        cluster, topic_suffix = nomessage.group(1), nomessage.group(2).strip()
        topic = topic_suffix
        if cluster == "kbc" and not topic.startswith("compute."):
            topic = f"compute.{topic}"
        return f"msk-{cluster}", topic, None

    lag = re.match(r"^msk\.(kbc|kb)\.(.+?)\s*>\s*\d+", alertname)
    if lag:
        cluster, topic = lag.group(1), lag.group(2).strip()
        return f"msk-{cluster}", topic, f"group.{topic}"

    group_lag = re.match(r"^msk\.(kbc|kb)\.group\.(.+?)\s*>\s*\d+", alertname)
    if group_lag:
        cluster, topic = group_lag.group(1), group_lag.group(2).strip()
        return f"msk-{cluster}", f"compute.{topic}", f"group.compute.{topic}"

    return None, None, None


def build_alert_context(alert: dict) -> AlertContext:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    alertname = labels.get("alertname", "unknown")
    resource_type = _resource_type(alertname, labels)

    namespace = labels.get("namespace")
    pod = labels.get("pod")
    container = labels.get("container")
    instance = labels.get("instance")
    module = labels.get("module")
    job = labels.get("job")
    topic = labels.get("topic")
    group_id = labels.get("groupId") or labels.get("group_id")
    workload_namespace = None
    workload_deployment = None

    if namespace and namespace.lower() in _FAKE_NAMESPACES:
        namespace = None

    if resource_type == "kafka":
        parsed_job, parsed_topic, parsed_group = _infer_msk_from_alertname(alertname)
        job = job or parsed_job
        topic = topic or parsed_topic
        group_id = group_id or parsed_group

        if alertname.startswith("pod.restart."):
            restart_job, restart_topic, restart_group = _infer_msk_from_pod_restart_alertname(
                alertname
            )
            job = job or restart_job
            topic = topic or restart_topic
            group_id = group_id or restart_group
            workload = _POD_RESTART_WORKLOADS.get(alertname)
            if workload:
                workload_namespace, workload_deployment = workload

        ann_topic, ann_group = _parse_kafka_from_annotations(annotations)
        topic = topic or ann_topic
        group_id = group_id or ann_group

    if resource_type == "kubernetes" and pod and not namespace:
        description = annotations.get("description", "")
        parsed_ns, parsed_pod = _parse_from_description(description)
        namespace = namespace or parsed_ns
        pod = pod or parsed_pod
        if namespace and namespace.lower() in _FAKE_NAMESPACES:
            namespace = None

    if resource_type in ("host", "probe", "kafka"):
        namespace = None
        pod = None

    host_ip = _host_ip(instance) if resource_type == "host" else None
    scrape_instance = instance if resource_type == "host" else None
    target = instance if resource_type == "probe" else None
    msk_job = job if resource_type == "kafka" else None
    scrape_job = None
    alert_firing_value = None
    primary_metric = None

    if resource_type == "host":
        scrape_job = labels.get("job") or _EC2_DEFAULT_SCRAPE_JOB
        alert_firing_value = _parse_alert_firing_value(annotations)
        primary_metric = _primary_metric_for_alert(alertname)

    return AlertContext(
        alertname=alertname,
        resource_type=resource_type,
        namespace=namespace,
        pod=pod,
        container=container,
        instance=instance,
        module=module,
        job=job,
        topic=topic,
        group_id=group_id,
        host_ip=host_ip,
        scrape_instance=scrape_instance,
        target=target,
        msk_job=msk_job,
        workload_namespace=workload_namespace,
        workload_deployment=workload_deployment,
        scrape_job=scrape_job,
        alert_firing_value=alert_firing_value,
        primary_metric=primary_metric,
        region=labels.get("region"),
        cloud=labels.get("cloud"),
        stage=labels.get("stage"),
    )


def alert_for_prompt(alert: dict, ctx: AlertContext) -> dict:
    """Return a copy of the alert with misleading k8s labels removed for non-k8s types."""
    sanitized = copy.deepcopy(alert)
    if ctx.resource_type == "kubernetes":
        return sanitized
    labels = sanitized.setdefault("labels", {})
    for key in ("namespace", "pod", "container"):
        labels.pop(key, None)
    return sanitized
