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

    def to_prompt_block(self) -> str:
        lines = [
            f"alertname: {self.alertname}",
            f"resource_type: {self.resource_type}",
        ]
        if self.namespace:
            lines.append(f"namespace: {self.namespace}")
        if self.pod:
            lines.append(f"pod: {self.pod}")
        if self.container:
            lines.append(f"container: {self.container}")
        if self.instance:
            lines.append(f"instance: {self.instance}")
        if self.module:
            lines.append(f"module: {self.module}")
        if self.job:
            lines.append(f"job: {self.job}")
        if self.topic:
            lines.append(f"topic: {self.topic}")
        if self.group_id:
            lines.append(f"group_id: {self.group_id}")
        return "\n".join(lines)


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


def _resource_type(alertname: str) -> str:
    if alertname.startswith("EC2Host"):
        return "host"
    if alertname.startswith("Blackbox") or alertname == "TLSCertificateExpiringSoon":
        return "probe"
    if alertname.startswith("msk."):
        return "kafka"
    return "kubernetes"


def build_alert_context(alert: dict) -> AlertContext:
    labels = alert.get("labels", {})
    annotations = alert.get("annotations", {})
    alertname = labels.get("alertname", "unknown")
    resource_type = _resource_type(alertname)

    namespace = labels.get("namespace")
    pod = labels.get("pod")
    container = labels.get("container")
    instance = labels.get("instance")
    module = labels.get("module")
    job = labels.get("job")
    topic = labels.get("topic")
    group_id = labels.get("groupId") or labels.get("group_id")

    if resource_type == "kubernetes" and pod and not namespace:
        description = annotations.get("description", "")
        parsed_ns, parsed_pod = _parse_from_description(description)
        namespace = namespace or parsed_ns
        pod = pod or parsed_pod

    if resource_type in ("host", "probe", "kafka"):
        namespace = None
        pod = None

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
    )
