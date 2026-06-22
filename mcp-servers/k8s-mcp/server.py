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


_load_kube_config()

core_v1 = client.CoreV1Api()
apps_v1 = client.AppsV1Api()

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


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
