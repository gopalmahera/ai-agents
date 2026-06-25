from alert_catalog import get_alert_meaning
from alert_context import AlertContext
from host_metrics import build_findings_bullets, default_host_actions
from kafka_metrics import build_findings_bullets as build_kafka_findings_bullets
from pod_metrics import build_findings_bullets as build_pod_findings_bullets

_POD_RESOURCE_ALERTS = frozenset(
    {
        "PODCPULimitsUage>=90",
        "PODMemoryLimitsUage>=90",
    }
)


def _host_summary(ctx: AlertContext) -> str:
    if ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
        return f"{ctx.alertname}: Host experiencing high rate of major page faults indicating memory pressure."
    return f"{ctx.alertname}: Alert fired on host {ctx.host_ip or ctx.scrape_instance}."


def _pod_summary(ctx: AlertContext) -> str:
    resource = "CPU" if ctx.alertname == "PODCPULimitsUage>=90" else "memory"
    return (
        f"{ctx.alertname}: Pod {ctx.namespace}/{ctx.pod} container "
        f"{ctx.container or 'main'} at ≥90% of {resource} limit."
    )


def _host_root_cause(ctx: AlertContext, prefetched: dict | None) -> str:
    snapshot = (prefetched or {}).get("snapshot") or {}
    page_faults = snapshot.get("major_page_faults_per_sec") or ctx.alert_firing_value
    memory = snapshot.get("memory") or {}
    avail = memory.get("available_percent")

    host = ctx.host_ip or ctx.scrape_instance or "the host"
    if page_faults is not None and ctx.alertname == "EC2HostMemoryUnderMemoryPressure":
        cause = (
            f"Host {host} has sustained major page faults at {page_faults:.1f}/s, "
            "indicating significant memory pressure."
        )
        if avail is not None:
            cause += f" Memory available is critically low at {avail:.1f}%."
        return cause

    return f"Host {host} triggered {ctx.alertname}; review prefetched metrics for the primary signal."


def _pod_root_cause(ctx: AlertContext, prefetched: dict | None) -> str:
    snapshot = (prefetched or {}).get("snapshot") or {}
    pct = snapshot.get("usage_percent")
    resource = snapshot.get("resource", "resource")
    workload = (prefetched or {}).get("workload") or {}
    rollout = workload.get("rollout") or {}
    age_seconds = rollout.get("rollout_age_seconds")

    target = f"{ctx.namespace}/{ctx.pod}"
    if pct is not None:
        cause = (
            f"Sustained {resource} saturation on {target} at {pct}% of limit — "
            "likely workload-driven."
        )
    else:
        cause = f"{ctx.alertname} fired on {target}; review prefetched metrics."

    if age_seconds is not None and age_seconds < 3600:
        cause += " Recent ReplicaSet change may have contributed."
    elif rollout.get("rollout_age_human"):
        cause += f" Workload stable since last rollout {rollout['rollout_age_human']} ago."
    return cause


def _default_pod_actions(ctx: AlertContext) -> list[str]:
    if ctx.alertname == "PODCPULimitsUage>=90":
        return [
            "Review CPU limit vs actual need; consider raising the limit or scaling replicas.",
            f"Check logs for {ctx.pod} for retry loops or hot paths driving CPU.",
            "Monitor CPU % of limit trend after peak traffic.",
        ]
    return [
        "Review memory limit vs working set; consider raising the limit or scaling replicas.",
        f"Check logs for {ctx.pod} for memory leaks or large in-memory buffers.",
        "Monitor memory % of limit and OOM risk after changes.",
    ]


def _kafka_summary(ctx: AlertContext) -> str:
    return (
        f"{ctx.alertname} alert fired due to consumer lag exceeding threshold of 1000."
    )


def _kafka_root_cause(ctx: AlertContext, prefetched: dict | None) -> str:
    snapshot = (prefetched or {}).get("snapshot") or {}
    lag = snapshot.get("consumer_lag")
    rate = snapshot.get("topic_message_rate_5m")
    group = ctx.group_id or "the consumer group"
    topic = ctx.topic or "the topic"

    if lag is not None and rate is not None:
        return (
            f"The consumer group for {topic} ({group}) is experiencing lag because it is "
            f"unable to process the incoming message rate of {int(rate)} messages/5m. "
            "This could be due to insufficient consumer processing capacity or "
            "performance inefficiencies in handling the message workload."
        )
    if lag is not None:
        return (
            f"Consumer lag on {group} for topic {topic} is {int(lag)}, above the threshold."
        )
    return f"{ctx.alertname} indicates elevated consumer lag on {topic}."


def _default_kafka_actions(ctx: AlertContext) -> list[str]:
    group = ctx.group_id or "the consumer group"
    return [
        f"Scale up the consumer instances for {group} to handle the incoming message rate more effectively.",
        "Investigate potential bottlenecks or inefficiencies in the consumer application code or configuration.",
        "Monitor the consumer processing rate versus the topic message rate to identify and address any mismatches promptly.",
    ]


def build_deterministic_rca(ctx: AlertContext, prefetched: dict | None) -> str:
    if ctx.alertname in _POD_RESOURCE_ALERTS:
        return _build_pod_rca(ctx, prefetched)
    if ctx.resource_type == "kafka":
        return _build_kafka_rca(ctx, prefetched)
    return _build_host_rca(ctx, prefetched)


def _build_kafka_rca(ctx: AlertContext, prefetched: dict | None) -> str:
    lines = [
        f"*Alert summary:*\n{_kafka_summary(ctx)}",
        "",
        "*Subject:*",
    ]
    if ctx.topic:
        lines.append(f"Topic: {ctx.topic}")
    if ctx.group_id:
        lines.append(f"Consumer group: {ctx.group_id}")
    if ctx.msk_job:
        lines.append(f"MSK job: {ctx.msk_job}")

    meaning = (prefetched or {}).get("alert_meaning") or get_alert_meaning(ctx.alertname)
    if meaning:
        lines.extend(["", "*What this alert means:*", meaning])

    bullets = list((prefetched or {}).get("bullets") or [])
    lines.extend(["", "*Metrics:*"])
    if bullets:
        lines.extend(f"• {b}" for b in bullets)
    else:
        lines.append("• No metrics prefetched")

    workload_bullets = list((prefetched or {}).get("workload_bullets") or [])
    if workload_bullets:
        lines.extend(["", "*Workload:*"])
        lines.extend(f"• {b}" for b in workload_bullets)

    findings = list((prefetched or {}).get("findings") or [])
    if not findings and prefetched:
        findings = build_kafka_findings_bullets(ctx, prefetched)
    lines.extend(["", "*Findings:*"])
    if findings:
        lines.extend(f"• {f}" for f in findings)
    else:
        lines.append("• Alert condition confirmed from available signals.")

    lines.extend(["", "*Probable root cause:*", _kafka_root_cause(ctx, prefetched)])

    actions = _default_kafka_actions(ctx)
    lines.extend(["", "*Recommended actions:*"])
    for idx, action in enumerate(actions[:3], start=1):
        lines.append(f"{idx}. {action}")

    return "\n".join(lines)


def _build_pod_rca(ctx: AlertContext, prefetched: dict | None) -> str:
    lines = [
        f"*Alert summary:*\n{_pod_summary(ctx)}",
        "",
        "*Subject:*",
        f"Namespace: {ctx.namespace}",
        f"Pod: {ctx.pod}",
    ]
    if ctx.container:
        lines.append(f"Container: {ctx.container}")

    meaning = (prefetched or {}).get("alert_meaning") or get_alert_meaning(ctx.alertname)
    if meaning:
        lines.extend(["", "*What this alert means:*", meaning])

    bullets = list((prefetched or {}).get("bullets") or [])
    lines.extend(["", "*Metrics:*"])
    if bullets:
        lines.extend(f"• {b}" for b in bullets)
    else:
        lines.append("• No metrics prefetched")

    workload_bullets = list((prefetched or {}).get("workload_bullets") or [])
    if workload_bullets:
        lines.extend(["", "*Workload:*"])
        lines.extend(f"• {b}" for b in workload_bullets)

    findings = list((prefetched or {}).get("findings") or [])
    if not findings and prefetched:
        findings = build_pod_findings_bullets(ctx, prefetched)
    lines.extend(["", "*Findings:*"])
    if findings:
        lines.extend(f"• {f}" for f in findings)
    else:
        lines.append("• Alert condition confirmed from available signals.")

    lines.extend(["", "*Probable root cause:*", _pod_root_cause(ctx, prefetched)])

    actions = _default_pod_actions(ctx)
    lines.extend(["", "*Recommended actions:*"])
    for idx, action in enumerate(actions[:3], start=1):
        lines.append(f"{idx}. {action}")

    return "\n".join(lines)


def _build_host_rca(ctx: AlertContext, prefetched: dict | None) -> str:
    host = ctx.host_ip or "unknown"
    scrape = ctx.scrape_instance or ctx.instance or "unknown"

    lines = [
        f"*Alert summary:*\n{_host_summary(ctx)}",
        "",
        "*Subject:*",
        f"Host: {host}",
        f"Instance (scrape): {scrape}",
    ]

    bullets = list((prefetched or {}).get("bullets") or [])
    lines.extend(["", "*Metrics:*"])
    if bullets:
        lines.extend(f"• {b}" for b in bullets)
    else:
        lines.append("• No metrics prefetched")

    findings = list((prefetched or {}).get("findings") or [])
    if not findings and prefetched:
        findings = build_findings_bullets(ctx, prefetched)
    lines.extend(["", "*Findings:*"])
    if findings:
        lines.extend(f"• {f}" for f in findings)
    else:
        lines.append("• Alert condition confirmed from available signals.")

    lines.extend(["", "*Probable root cause:*", _host_root_cause(ctx, prefetched)])

    actions = default_host_actions(ctx)
    lines.extend(["", "*Recommended actions:*"])
    for idx, action in enumerate(actions[:3], start=1):
        lines.append(f"{idx}. {action}")

    return "\n".join(lines)
