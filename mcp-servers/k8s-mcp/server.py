import json
import os
import tempfile

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException
from mcp.server.fastmcp import FastMCP
import yaml


def _normalize_kubeconfig(kubeconfig: str) -> str:
    with open(kubeconfig, "r", encoding="utf-8") as handle:
        kubeconfig_data = yaml.safe_load(handle) or {}

    contexts = kubeconfig_data.get("contexts")
    if contexts:
        return kubeconfig

    clusters = kubeconfig_data.get("clusters") or []
    users = kubeconfig_data.get("users") or []
    if not clusters or not users:
        return kubeconfig

    synthesized_context = os.getenv("KUBECONTEXT", clusters[0]["name"])
    kubeconfig_data["contexts"] = [
        {
            "name": synthesized_context,
            "context": {
                "cluster": clusters[0]["name"],
                "user": users[0]["name"],
            },
        }
    ]
    kubeconfig_data["current-context"] = synthesized_context

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        encoding="utf-8",
    )
    yaml.safe_dump(kubeconfig_data, temp_file)
    temp_file.close()
    return temp_file.name


def _load_kube_config() -> None:
    kubeconfig = os.getenv("KUBECONFIG")
    kubecontext = os.getenv("KUBECONTEXT")

    if kubeconfig:
        kubeconfig = _normalize_kubeconfig(kubeconfig)
        try:
            config.load_kube_config(config_file=kubeconfig, context=kubecontext)
        except ConfigException:
            contexts, _ = config.list_kube_config_contexts(config_file=kubeconfig)
            if not contexts:
                raise
            config.load_kube_config(
                config_file=kubeconfig,
                context=contexts[0]["name"],
            )
        return

    try:
        config.load_incluster_config()
    except ConfigException:
        config.load_kube_config()


_K8S_UNAVAILABLE_MSG = {"error": "Kubernetes is not configured — no kubeconfig or in-cluster credentials available."}
_K8S_AVAILABLE = True
try:
    _load_kube_config()
except Exception as _exc:
    _K8S_AVAILABLE = False
    print(f"[k8s-mcp] WARNING: kubeconfig unavailable — k8s tools will return an error ({_exc})")


class _UnavailableApi:
    """Placeholder when kubeconfig is missing — every method call returns an error dict."""
    def __getattr__(self, name):
        def _noop(*args, **kwargs):
            raise client.exceptions.ApiException(status=503, reason="Kubernetes is not configured — no kubeconfig or in-cluster credentials available.")
        return _noop


core_v1 = client.CoreV1Api() if _K8S_AVAILABLE else _UnavailableApi()
apps_v1 = client.AppsV1Api() if _K8S_AVAILABLE else _UnavailableApi()

mcp = FastMCP(
    "kubernetes",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)


@mcp.tool()
def get_namespaces():
    """Get all namespaces."""
    try:
        namespaces = core_v1.list_namespace()
    except client.exceptions.ApiException as exc:
        return {"error": exc.reason, "status": exc.status, "body": exc.body}
    return [ns.metadata.name for ns in namespaces.items]


@mcp.tool()
def get_pods(namespace: str):
    """Get all pods in a namespace."""
    try:
        pods = core_v1.list_namespaced_pod(namespace)
    except client.exceptions.ApiException as exc:
        return {"error": exc.reason, "status": exc.status, "body": exc.body}
    return [
        {
            "name": pod.metadata.name,
            "status": pod.status.phase,
            "node": pod.spec.node_name,
        }
        for pod in pods.items
    ]


def _pod_container_names(pod) -> list[str]:
    return [container.name for container in pod.spec.containers]


def _pick_default_container(pod) -> str:
    containers = _pod_container_names(pod)
    if len(containers) == 1:
        return containers[0]

    sidecar_markers = ("reloader", "istio-proxy", "linkerd-proxy", "envoy", "sidecar")
    primary = [
        name
        for name in containers
        if not any(marker in name for marker in sidecar_markers)
    ]
    if len(primary) == 1:
        return primary[0]
    if primary:
        return primary[0]
    return containers[0]


@mcp.tool()
def describe_pod(namespace: str, pod_name: str):
    """Describe a pod."""
    pod = core_v1.read_namespaced_pod(namespace=namespace, name=pod_name)
    init_containers = [container.name for container in pod.spec.init_containers or []]
    containers = _pod_container_names(pod)
    return {
        "name": pod.metadata.name,
        "namespace": pod.metadata.namespace,
        "status": pod.status.phase,
        "node": pod.spec.node_name,
        "pod_ip": pod.status.pod_ip,
        "host_ip": pod.status.host_ip,
        "service_account": pod.spec.service_account_name,
        "containers": containers,
        "init_containers": init_containers,
        "default_log_container": _pick_default_container(pod),
    }


@mcp.tool()
def get_logs(
    namespace: str,
    pod_name: str,
    container: str | None = None,
    lines: int = 100,
):
    """Get pod logs. For multi-container pods, pass container or the main app container is used."""
    pod = core_v1.read_namespaced_pod(namespace=namespace, name=pod_name)
    containers = _pod_container_names(pod)
    selected_container = container or _pick_default_container(pod)

    try:
        logs = core_v1.read_namespaced_pod_log(
            namespace=namespace,
            name=pod_name,
            container=selected_container,
            tail_lines=lines,
        )
    except client.exceptions.ApiException as exc:
        message = exc.reason or str(exc)
        if exc.body:
            try:
                message = json.loads(exc.body).get("message", message)
            except Exception:
                pass
        return {
            "error": message,
            "container": selected_container,
            "available_containers": containers,
            "logs": "",
        }

    return {
        "container": selected_container,
        "available_containers": containers,
        "logs": logs,
    }


@mcp.tool()
def get_events(namespace: str):
    """Get namespace events."""
    events = core_v1.list_namespaced_event(namespace)
    return [
        {
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
        }
        for event in events.items
    ]


@mcp.tool()
def get_pod_events(namespace: str, pod_name: str):
    """Get events for a pod."""
    events = core_v1.list_namespaced_event(namespace)
    return [
        {
            "type": event.type,
            "reason": event.reason,
            "message": event.message,
        }
        for event in events.items
        if event.involved_object and event.involved_object.name == pod_name
    ]


@mcp.tool()
def get_pod_restart_count(namespace: str):
    """Get restart counts for pods in a namespace."""
    pods = core_v1.list_namespaced_pod(namespace)
    result = []
    for pod in pods.items:
        restart_count = 0
        if pod.status.container_statuses:
            restart_count = sum(
                container.restart_count for container in pod.status.container_statuses
            )
        result.append({"pod": pod.metadata.name, "restarts": restart_count})
    return result


@mcp.tool()
def get_deployments(namespace: str):
    """Get deployments in a namespace."""
    deployments = apps_v1.list_namespaced_deployment(namespace)
    return [
        {
            "name": deployment.metadata.name,
            "replicas": deployment.spec.replicas,
            "available_replicas": deployment.status.available_replicas,
        }
        for deployment in deployments.items
    ]


def _format_age(created) -> str | None:
    if created is None:
        return None
    from datetime import datetime, timezone

    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    seconds = max(int(delta.total_seconds()), 0)
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes or not parts:
        parts.append(f"{minutes}m")
    return " ".join(parts)


def _iso_timestamp(value) -> str | None:
    if value is None:
        return None
    from datetime import timezone

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _deployment_rollout_time(deployment):
    conditions = deployment.status.conditions or []
    latest = None
    for condition in conditions:
        if condition.type in ("Progressing", "Available") and condition.last_transition_time:
            ts = condition.last_transition_time
            if latest is None or ts > latest:
                latest = ts
    return latest


def _container_image(replica_set, container_name: str | None = None) -> str | None:
    containers = replica_set.spec.template.spec.containers or []
    if container_name:
        for container in containers:
            if container.name == container_name:
                return container.image
    if containers:
        return containers[0].image
    return None


def _replica_sets_for_deployment(namespace: str, deployment_name: str) -> list:
    from datetime import datetime, timezone

    rs_list = apps_v1.list_namespaced_replica_set(namespace=namespace)
    owned = []
    for replica_set in rs_list.items:
        owner_refs = replica_set.metadata.owner_references or []
        if any(ref.kind == "Deployment" and ref.name == deployment_name for ref in owner_refs):
            owned.append(replica_set)
    owned.sort(
        key=lambda rs: rs.metadata.creation_timestamp
        or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return owned


@mcp.tool()
def get_workload_rollout_info(namespace: str, pod_name: str, container: str | None = None):
    """Return ReplicaSet and Deployment rollout metadata for a pod."""
    try:
        pod = core_v1.read_namespaced_pod(namespace=namespace, name=pod_name)
    except client.exceptions.ApiException as exc:
        return {"error": exc.reason, "status": exc.status}

    owner_refs = pod.metadata.owner_references or []
    rs_ref = next((ref for ref in owner_refs if ref.kind == "ReplicaSet"), None)
    if not rs_ref:
        return {"error": "pod has no ReplicaSet owner"}

    try:
        rs = apps_v1.read_namespaced_replica_set(namespace=namespace, name=rs_ref.name)
    except client.exceptions.ApiException as exc:
        return {"error": exc.reason, "replicaset": rs_ref.name}

    rs_created = rs.metadata.creation_timestamp
    deployment_name = None
    deployment_rollout = None
    owner_kind = "ReplicaSet"
    current_image = _container_image(rs, container)
    previous_image = None
    previous_replicaset = None

    dep_ref = next(
        (ref for ref in (rs.metadata.owner_references or []) if ref.kind == "Deployment"),
        None,
    )
    if dep_ref:
        owner_kind = "Deployment"
        deployment_name = dep_ref.name
        try:
            deployment = apps_v1.read_namespaced_deployment(namespace=namespace, name=deployment_name)
            deployment_rollout = _deployment_rollout_time(deployment)
        except client.exceptions.ApiException:
            deployment_rollout = None

        replica_sets = _replica_sets_for_deployment(namespace, deployment_name)
        if len(replica_sets) > 1:
            previous_rs = replica_sets[1]
            previous_replicaset = previous_rs.metadata.name
            previous_image = _container_image(previous_rs, container)

    rollout_ts = deployment_rollout or rs_created
    age_human = _format_age(rollout_ts)
    age_seconds = None
    if rollout_ts:
        from datetime import datetime, timezone

        if rollout_ts.tzinfo is None:
            rollout_ts = rollout_ts.replace(tzinfo=timezone.utc)
        age_seconds = int((datetime.now(timezone.utc) - rollout_ts).total_seconds())

    image_changed = bool(
        current_image and previous_image and current_image != previous_image
    )

    return {
        "owner_kind": owner_kind,
        "owner_name": deployment_name or rs_ref.name,
        "replicaset": rs_ref.name,
        "replicaset_created_at": _iso_timestamp(rs_created),
        "replicaset_age_human": age_human,
        "deployment_last_rollout": _iso_timestamp(deployment_rollout),
        "rollout_age_human": age_human,
        "rollout_timestamp": _iso_timestamp(rollout_ts),
        "rollout_age_seconds": age_seconds,
        "current_image": current_image,
        "previous_image": previous_image,
        "previous_replicaset": previous_replicaset,
        "image_changed": image_changed,
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
