import requests

from alert_context import AlertContext
from config import PROMETHEUS_URL

_POD_CPU_ALERT = "PODCPULimitsUage>=90"
_POD_MEMORY_ALERT = "PODMemoryLimitsUage>=90"

_CPU_THRESHOLD = ">= 90%"
_MEMORY_THRESHOLD = ">= 90%"


def _pod_labels_filter(namespace: str, pod: str, container: str) -> str:
    ns = namespace.replace("\\", "\\\\").replace('"', '\\"')
    pod_esc = pod.replace("\\", "\\\\").replace('"', '\\"')
    cont = container.replace("\\", "\\\\").replace('"', '\\"')
    return f'namespace="{ns}",pod="{pod_esc}",container="{cont}"'


def _query_promql(query: str) -> dict:
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _first_scalar(result: dict) -> float | None:
    data = result.get("data", {})
    if data.get("resultType") != "vector":
        return None
    results = data.get("result", [])
    if not results:
        return None
    value = results[0].get("value")
    if not value or len(value) < 2:
        return None
    try:
        return float(value[1])
    except (TypeError, ValueError):
        return None


def _format_cores(cores: float | None) -> str | None:
    if cores is None:
        return None
    if cores < 1:
        millicores = cores * 1000
        if abs(millicores - round(millicores)) < 0.05:
            return f"{int(round(millicores))}m ({cores:.3f} cores)"
        return f"{millicores:.0f}m ({cores:.3f} cores)"
    return f"{cores:.3f} cores"


def _format_bytes(num_bytes: float | None) -> str | None:
    if num_bytes is None:
        return None
    gib = num_bytes / (1024**3)
    if gib >= 1:
        return f"{gib:.2f} GiB"
    mib = num_bytes / (1024**2)
    return f"{mib:.0f} MiB"


def _fetch_pod_cpu_snapshot(namespace: str, pod: str, container: str) -> dict:
    labels = _pod_labels_filter(namespace, pod, container)
    usage = _first_scalar(
        _query_promql(f"sum(rate(container_cpu_usage_seconds_total{{{labels}}}[5m]))")
    )
    limit = _first_scalar(
        _query_promql(
            f"sum(cluster:namespace:pod_cpu:active:kube_pod_container_resource_limits{{{labels}}})"
        )
    )
    pct = None
    if usage is not None and limit:
        pct = round(100 * usage / limit, 1)
    restarts = _first_scalar(
        _query_promql(f"sum(kube_pod_container_status_restarts_total{{{labels}}})")
    )
    return {
        "usage_cores": usage,
        "limit_cores": limit,
        "usage_percent": pct,
        "restarts": restarts,
        "resource": "cpu",
    }


def _fetch_pod_memory_snapshot(namespace: str, pod: str, container: str) -> dict:
    labels = _pod_labels_filter(namespace, pod, container)
    working_set = _first_scalar(
        _query_promql(f"sum(container_memory_working_set_bytes{{{labels}}})")
    )
    limit = _first_scalar(
        _query_promql(
            "sum(cluster:namespace:pod_memory:active:kube_pod_container_resource_limits"
            f"{{{labels}}})"
        )
    )
    pct = None
    if working_set is not None and limit:
        pct = round(100 * working_set / limit, 1)
    restarts = _first_scalar(
        _query_promql(f"sum(kube_pod_container_status_restarts_total{{{labels}}})")
    )
    return {
        "usage_bytes": working_set,
        "limit_bytes": limit,
        "usage_percent": pct,
        "restarts": restarts,
        "resource": "memory",
    }


def _build_cpu_bullets(ctx: AlertContext, snapshot: dict) -> list[str]:
    bullets: list[str] = []
    pct = snapshot.get("usage_percent")
    if pct is not None:
        bullets.append(f"CPU usage % of limit: {pct}% (threshold {_CPU_THRESHOLD})")
    usage = snapshot.get("usage_cores")
    if usage is not None:
        bullets.append(f"CPU usage rate: {usage:.3f} cores (5m avg)")
    limit = snapshot.get("limit_cores")
    if limit is not None:
        formatted = _format_cores(limit)
        bullets.append(f"CPU limit: {formatted}")
    restarts = snapshot.get("restarts")
    if restarts is not None:
        bullets.append(f"Container restarts: {int(restarts)}")
    return bullets


def _build_memory_bullets(ctx: AlertContext, snapshot: dict) -> list[str]:
    bullets: list[str] = []
    pct = snapshot.get("usage_percent")
    if pct is not None:
        bullets.append(f"Memory usage % of limit: {pct}% (threshold {_MEMORY_THRESHOLD})")
    usage = snapshot.get("usage_bytes")
    limit = snapshot.get("limit_bytes")
    if usage is not None:
        size = _format_bytes(usage)
        if limit is not None:
            bullets.append(f"Memory working set: {size} / {_format_bytes(limit)}")
        else:
            bullets.append(f"Memory working set: {size}")
    elif limit is not None:
        bullets.append(f"Memory limit: {_format_bytes(limit)}")
    restarts = snapshot.get("restarts")
    if restarts is not None:
        bullets.append(f"Container restarts: {int(restarts)}")
    return bullets


def build_findings_bullets(ctx: AlertContext, prefetched: dict | None) -> list[str]:
    if not prefetched:
        return []

    findings: list[str] = []
    snapshot = prefetched.get("snapshot") or {}
    resource = snapshot.get("resource")

    if resource == "cpu":
        pct = snapshot.get("usage_percent")
        if pct is not None:
            findings.append(
                f"Container {ctx.container or 'main'} is at {pct}% of its CPU limit — "
                "alert condition confirmed."
            )
        elif prefetched.get("alert_valid"):
            findings.append(
                f"CPU limit alert fired for {ctx.namespace}/{ctx.pod}; "
                "limits exist — do not claim misconfiguration."
            )
    elif resource == "memory":
        pct = snapshot.get("usage_percent")
        if pct is not None:
            findings.append(
                f"Container {ctx.container or 'main'} is at {pct}% of its memory limit — "
                "alert condition confirmed."
            )
        elif prefetched.get("alert_valid"):
            findings.append(
                f"Memory limit alert fired for {ctx.namespace}/{ctx.pod}; "
                "limits exist — do not claim misconfiguration."
            )

    rollout = (prefetched.get("workload") or {}).get("rollout") or {}
    age_seconds = rollout.get("rollout_age_seconds")
    age = rollout.get("rollout_age_human")
    if age_seconds is not None:
        if age_seconds < 3600:
            findings.append(
                f"ReplicaSet changed {age} ago — correlate alert timing with recent deploy."
            )
        elif age:
            findings.append(f"Workload stable since last ReplicaSet change ({age} ago).")
    elif age:
        findings.append(f"Last ReplicaSet change: {age} ago.")

    restarts = snapshot.get("restarts")
    if restarts is not None and restarts == 0:
        findings.append("No container restarts observed.")

    return findings


def prefetch_pod_metrics(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.resource_type != "kubernetes":
        return None
    if not ctx.namespace or not ctx.pod or not ctx.container:
        return None

    if ctx.alertname == _POD_CPU_ALERT:
        fetcher = _fetch_pod_cpu_snapshot
        bullet_builder = _build_cpu_bullets
    elif ctx.alertname == _POD_MEMORY_ALERT:
        fetcher = _fetch_pod_memory_snapshot
        bullet_builder = _build_memory_bullets
    else:
        return None

    try:
        snapshot = fetcher(ctx.namespace, ctx.pod, ctx.container)
    except requests.RequestException as exc:
        return {
            "snapshot": {},
            "bullets": [],
            "findings": [],
            "up": None,
            "alert_valid": True,
            "error": str(exc),
        }

    bullets = bullet_builder(ctx, snapshot)
    result = {
        "snapshot": snapshot,
        "bullets": bullets,
        "up": None,
        "alert_valid": bool(bullets) or ctx.alertname in (_POD_CPU_ALERT, _POD_MEMORY_ALERT),
    }
    result["findings"] = build_findings_bullets(ctx, result)
    return result
