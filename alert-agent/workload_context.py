from alert_context import AlertContext
from alert_catalog import get_alert_meaning
from k8s_rollout import fetch_workload_rollout_info

_POD_RESOURCE_ALERTS = frozenset(
    {
        "PODCPULimitsUage>=90",
        "PODMemoryLimitsUage>=90",
    }
)


def _region_bullets(ctx: AlertContext, labels: dict) -> list[str]:
    bullets: list[str] = []
    region = labels.get("region") or ctx.region
    cloud = labels.get("cloud") or ctx.cloud
    stage = labels.get("stage") or ctx.stage
    if region:
        parts = [f"Region: {region}"]
        if cloud:
            parts.append(f"cloud: {cloud}")
        if stage:
            parts.append(f"stage: {stage}")
        bullets.append(" | ".join(parts))
    return bullets


def prefetch_workload_context(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.alertname not in _POD_RESOURCE_ALERTS:
        return None
    if not ctx.namespace or not ctx.pod:
        return None

    labels = alert.get("labels", {})
    rollout = fetch_workload_rollout_info(ctx.namespace, ctx.pod, container=ctx.container)
    bullets = _region_bullets(ctx, labels)

    if rollout.get("owner_kind") == "Deployment" and rollout.get("owner_name"):
        bullets.append(f"Deployment: {ctx.namespace}/{rollout['owner_name']}")
    if rollout.get("replicaset"):
        bullets.append(f"ReplicaSet: {rollout['replicaset']}")
    if rollout.get("current_image"):
        bullets.append(f"Current image: {rollout['current_image']}")
    if rollout.get("previous_image"):
        prev_rs = rollout.get("previous_replicaset")
        suffix = f" (RS {prev_rs})" if prev_rs else ""
        bullets.append(f"Previous image: {rollout['previous_image']}{suffix}")
    if rollout.get("rollout_age_human"):
        ts = rollout.get("rollout_timestamp") or rollout.get("replicaset_created_at") or ""
        suffix = f" ({ts})" if ts else ""
        bullets.append(f"Last ReplicaSet change: {rollout['rollout_age_human']} ago{suffix}")

    meaning = get_alert_meaning(ctx.alertname)

    return {
        "rollout": rollout,
        "bullets": bullets,
        "alert_meaning": meaning,
        "region": labels.get("region") or ctx.region,
        "cloud": labels.get("cloud") or ctx.cloud,
        "stage": labels.get("stage") or ctx.stage,
    }
