from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone

# Clients cached per environment Kubernetes endpoint so different clusters reuse
# their own connection. The key covers kube-context AND explicit api-server/token
# so distinct endpoints never collide. Empty key = in-cluster / default kubeconfig.
_clients_by_context: dict = {}


def _explicit_api_client(client, kube):
    """Build an ApiClient for an explicit api-server + bearer token (+ optional CA)."""
    configuration = client.Configuration()
    configuration.host = kube.api_server
    configuration.api_key = {"authorization": kube.token}
    configuration.api_key_prefix = {"authorization": "Bearer"}
    if kube.ca_cert:
        fd, path = tempfile.mkstemp(suffix=".pem")
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(kube.ca_cert)
        configuration.ssl_ca_cert = path
    else:
        configuration.verify_ssl = False
    return client.ApiClient(configuration)


def _ensure_k8s_clients():
    from kubernetes import client, config
    from kubernetes.config.config_exception import ConfigException
    from services import environments as _environments

    kube = _environments.current().kubernetes
    cache_key = (kube.kube_context, kube.api_server, kube.token, kube.ca_cert)
    cached = _clients_by_context.get(cache_key)
    if cached is not None:
        return cached

    if kube.explicit:
        # Explicit api-server + token (e.g. a cross-cluster service-account token).
        api_client = _explicit_api_client(client, kube)
        core_v1 = client.CoreV1Api(api_client)
        apps_v1 = client.AppsV1Api(api_client)
    elif kube.kube_context:
        # A named environment cluster from the mounted multi-context kubeconfig.
        api_client = config.new_client_from_config(context=kube.kube_context)
        core_v1 = client.CoreV1Api(api_client)
        apps_v1 = client.AppsV1Api(api_client)
    else:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()
        core_v1 = client.CoreV1Api()
        apps_v1 = client.AppsV1Api()

    _clients_by_context[cache_key] = (core_v1, apps_v1)
    return core_v1, apps_v1


def _format_age(created: datetime | None) -> str | None:
    if created is None:
        return None
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - created
    seconds = int(delta.total_seconds())
    if seconds < 0:
        seconds = 0
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


def _iso_timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.strftime("%Y-%m-%d %H:%M UTC")


def _deployment_rollout_time(deployment) -> datetime | None:
    conditions = deployment.status.conditions or []
    latest: datetime | None = None
    for condition in conditions:
        if condition.type in ("Progressing", "Available") and condition.last_transition_time:
            ts = condition.last_transition_time
            if latest is None or ts > latest:
                latest = ts
    return latest


def _container_image(replica_set, container_name: str | None) -> str | None:
    containers = replica_set.spec.template.spec.containers or []
    if container_name:
        for container in containers:
            if container.name == container_name:
                return container.image
    if containers:
        return containers[0].image
    return None


def _replica_sets_for_deployment(apps_v1, namespace: str, deployment_name: str) -> list:
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


def fetch_workload_rollout_info(
    namespace: str,
    pod_name: str,
    container: str | None = None,
) -> dict:
    """Return ReplicaSet / Deployment rollout metadata for a pod."""
    try:
        core_v1, apps_v1 = _ensure_k8s_clients()
        pod = core_v1.read_namespaced_pod(namespace=namespace, name=pod_name)
    except Exception as exc:
        return {"error": str(exc)}

    owner_refs = pod.metadata.owner_references or []
    rs_ref = next((ref for ref in owner_refs if ref.kind == "ReplicaSet"), None)
    if not rs_ref:
        return {"error": "pod has no ReplicaSet owner"}

    try:
        rs = apps_v1.read_namespaced_replica_set(namespace=namespace, name=rs_ref.name)
    except Exception as exc:
        return {"error": str(exc), "replicaset": rs_ref.name}

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
        except Exception:
            deployment_rollout = None

        replica_sets = _replica_sets_for_deployment(apps_v1, namespace, deployment_name)
        if len(replica_sets) > 1:
            previous_rs = replica_sets[1]
            previous_replicaset = previous_rs.metadata.name
            previous_image = _container_image(previous_rs, container)

    rollout_ts = deployment_rollout or rs_created
    age_human = _format_age(rollout_ts)
    age_seconds = None
    if rollout_ts:
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
