import os
import re

import requests
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "kafka",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-sit.dozee.int")

_MSK_LAG_RE = re.compile(r"^msk\.(kbc|kb)\.(.+?)\s*>\s*\d+")
_MSK_NOMESSAGE_RE = re.compile(r"^msk\.(kbc|kb)\.nomessage\.(.+?)\s*=\s*0")


def _query(query: str):
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/query",
        params={"query": query},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _has_results(payload: dict) -> bool:
    return bool(payload.get("data", {}).get("result"))


def _infer_from_alertname(alertname: str) -> dict:
    match = _MSK_NOMESSAGE_RE.match(alertname)
    if match:
        cluster, topic_suffix = match.group(1), match.group(2)
        topic = topic_suffix.replace(" ", "")
        if cluster == "kbc" and not topic.startswith("compute."):
            topic = f"compute.{topic}"
        return {"job": f"msk-{cluster}", "topic": topic}

    match = _MSK_LAG_RE.match(alertname)
    if match:
        cluster, topic = match.group(1), match.group(2).strip()
        group_id = f"group.{topic}"
        return {"job": f"msk-{cluster}", "topic": topic, "group_id": group_id}

    return {}


def _query_with_fallbacks(queries: list[str]) -> dict:
    attempts = []
    for query in queries:
        payload = _query(query)
        attempts.append({"query": query, "result_count": len(payload.get("data", {}).get("result", []))})
        if _has_results(payload):
            return {"data": payload.get("data"), "query_used": query, "attempts": attempts}
    return {
        "data": {"result": [], "resultType": "vector"},
        "query_used": None,
        "attempts": attempts,
        "note": "No time series matched. Check job/topic/group labels or use prom_query_promql with a broader selector.",
    }


@mcp.tool()
def get_consumer_lag(
    group_id: str,
    topic: str,
    job: str | None = None,
    alertname: str | None = None,
):
    """Get Kafka consumer group lag for a topic. job is usually msk-kbc or msk-kb."""
    inferred = _infer_from_alertname(alertname or "")
    group = _escape(group_id or inferred.get("group_id", ""))
    top = _escape(topic or inferred.get("topic", ""))
    job_name = job or inferred.get("job")

    queries = []
    if job_name:
        job_esc = _escape(job_name)
        queries.append(
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{job="{job_esc}",topic="{top}",'
            f'name="SumOffsetLag",groupId="{group}"}}'
        )
    queries.extend(
        [
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{topic="{top}",name="SumOffsetLag",groupId="{group}"}}',
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{groupId="{group}"}}',
            f'kafka_consumer_group_ConsumerLagMetrics_Value{{topic="{top}"}}',
        ]
    )
    return _query_with_fallbacks(queries)


@mcp.tool()
def get_topic_message_rate(
    topic: str,
    job: str | None = None,
    alertname: str | None = None,
):
    """Get Kafka topic message rate from log end offset increase over 5m."""
    inferred = _infer_from_alertname(alertname or "")
    top = _escape(topic or inferred.get("topic", ""))
    job_name = job or inferred.get("job")

    queries = []
    if job_name:
        job_esc = _escape(job_name)
        queries.append(
            f'sum by (topic, job) (increase(kafka_log_Log_Value{{job="{job_esc}", '
            f'name="LogEndOffset", topic="{top}"}}[5m]))'
        )
    queries.extend(
        [
            f'sum by (topic, job) (increase(kafka_log_Log_Value{{name="LogEndOffset", topic="{top}"}}[5m]))',
            f'sum by (topic, job) (increase(kafka_log_Log_Value{{topic="{top}"}}[5m]))',
        ]
    )
    return _query_with_fallbacks(queries)


@mcp.tool()
def list_kafka_jobs():
    """List Prometheus job label values related to MSK/Kafka scrapes."""
    payload = requests.get(
        f"{PROMETHEUS_URL}/api/v1/label/job/values",
        timeout=30,
    )
    payload.raise_for_status()
    jobs = payload.json().get("data", [])
    return [job for job in jobs if "msk" in job or "kafka" in job]


@mcp.tool()
def list_active_msk_alerts():
    """List active Prometheus alerts with alertname starting with msk."""
    response = requests.get(
        f"{PROMETHEUS_URL}/api/v1/alerts",
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    alerts = payload.get("data", {}).get("alerts", [])
    return [
        alert
        for alert in alerts
        if alert.get("labels", {}).get("alertname", "").startswith("msk.")
    ]


@mcp.tool()
def find_deployments_for_consumer_group(group_id: str):
    """Suggest deployment name patterns for a Kafka consumer group."""
    suffix = group_id.split(".")[-1] if group_id else ""
    patterns = [group_id, suffix, f"{suffix}worker", f"{suffix}consumer"]
    return {
        "group_id": group_id,
        "suggested_deployment_patterns": [p for p in patterns if p],
        "hint": "Search namespaces dozee* and computeworker* for deployments matching these patterns.",
    }


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
