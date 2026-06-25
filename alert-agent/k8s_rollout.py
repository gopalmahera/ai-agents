from __future__ import annotations

from datetime import datetime, timezone

_apps_v1 = None
_core_v1 = None
_config_loaded = False


def _ensure_k8s_clients():
    global _apps_v1, _core_v1, _config_loaded
    from kubernetes import client, config
    from kubernetes.config.config_exception import ConfigException

    if not _config_loaded:
        try:
            config.load_incluster_config()
        except ConfigException:
            config.load_kube_config()
        _config_loaded = True
    if _core_v1 is None:
        _core_v1 = client.CoreV1Api()
    if _apps_v1 is None:
        _apps_v1 = client.AppsV1Api()
    return _core_v1, _apps_v1


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
