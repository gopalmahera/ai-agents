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


def fetch_workload_rollout_info(namespace: str, pod_name: str) -> dict:
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

    dep_ref = next((ref for ref in (rs.metadata.owner_references or []) if ref.kind == "Deployment"), None)
    if dep_ref:
        owner_kind = "Deployment"
        deployment_name = dep_ref.name
        try:
            deployment = apps_v1.read_namespaced_deployment(namespace=namespace, name=deployment_name)
            deployment_rollout = _deployment_rollout_time(deployment)
        except Exception:
            deployment_rollout = None

    rollout_ts = deployment_rollout or rs_created
    age_human = _format_age(rollout_ts)
    age_seconds = None
    if rollout_ts:
        if rollout_ts.tzinfo is None:
            rollout_ts = rollout_ts.replace(tzinfo=timezone.utc)
        age_seconds = int((datetime.now(timezone.utc) - rollout_ts).total_seconds())

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
    }
