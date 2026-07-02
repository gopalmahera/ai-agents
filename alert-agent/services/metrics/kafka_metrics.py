import requests

from services.classification.alert_classifier import AlertContext
from config import PROMETHEUS_URL

_LAG_THRESHOLD = 1000


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


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


def _query_first_scalar(queries: list[str]) -> float | None:
    for query in queries:
        value = _first_scalar(_query_promql(query))
        if value is not None:
            return value
    return None


def _fetch_consumer_lag(ctx: AlertContext) -> float | None:
    if not ctx.topic or not ctx.group_id:
        return None
    top = _escape(ctx.topic)
    group = _escape(ctx.group_id)
    queries = []
    if ctx.msk_job:
        job = _escape(ctx.msk_job)
        queries.append(
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{job="{job}",topic="{top}",'
            f'name="SumOffsetLag",groupId="{group}"}}'
        )
    queries.extend(
        [
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{topic="{top}",name="SumOffsetLag",groupId="{group}"}}',
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{groupId="{group}"}}',
        ]
    )
    return _query_first_scalar(queries)


def _fetch_topic_message_rate(ctx: AlertContext) -> float | None:
    if not ctx.topic:
        return None
    top = _escape(ctx.topic)
    queries = []
    if ctx.msk_job:
        job = _escape(ctx.msk_job)
        queries.append(
            f'sum(increase(kafka_log_Log_Value{{job="{job}",name="LogEndOffset",topic="{top}"}}[5m]))'
        )
    queries.append(
        f'sum(increase(kafka_log_Log_Value{{name="LogEndOffset",topic="{top}"}}[5m]))'
    )
    return _query_first_scalar(queries)


def _build_kafka_bullets(ctx: AlertContext, snapshot: dict) -> list[str]:
    bullets: list[str] = []
    lag = snapshot.get("consumer_lag")
    if lag is not None:
        bullets.append(f"Consumer Lag: {int(lag)} (> {_LAG_THRESHOLD} threshold)")
    rate = snapshot.get("topic_message_rate_5m")
    if rate is not None:
        bullets.append(f"Topic Message Rate: {int(rate)} messages/5m (contextual reference)")
    return bullets


def build_findings_bullets(ctx: AlertContext, prefetched: dict | None) -> list[str]:
    if not prefetched:
        return []

    findings: list[str] = []
    snapshot = prefetched.get("snapshot") or {}
    lag = snapshot.get("consumer_lag")
    rate = snapshot.get("topic_message_rate_5m")

    if lag is not None and ctx.topic and ctx.group_id:
        findings.append(
            f"The consumer lag for {ctx.group_id} on topic {ctx.topic} is {int(lag)}, "
            f"which is above the critical threshold of {_LAG_THRESHOLD}."
        )
    if rate is not None:
        findings.append(
            f"The topic message rate is {int(rate)} messages over a 5-minute interval, "
            "indicating a high volume of messages."
        )
    if lag is not None and lag > _LAG_THRESHOLD:
        findings.append(
            "The alert indicates possible performance issues with the consumer group's "
            "ability to process messages at the incoming rate."
        )
    return findings


def prefetch_kafka_metrics(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.resource_type != "kafka":
        return None
    if not ctx.topic and not ctx.group_id:
        return None

    try:
        snapshot = {
            "consumer_lag": _fetch_consumer_lag(ctx),
            "topic_message_rate_5m": _fetch_topic_message_rate(ctx),
            "resource": "kafka",
        }
    except requests.RequestException as exc:
        return {
            "snapshot": {},
            "bullets": [],
            "findings": [],
            "alert_valid": True,
            "error": str(exc),
        }

    bullets = _build_kafka_bullets(ctx, snapshot)
    result = {
        "snapshot": snapshot,
        "bullets": bullets,
        "alert_valid": bool(bullets) or bool(ctx.topic),
    }
    result["findings"] = build_findings_bullets(ctx, result)
    return result
