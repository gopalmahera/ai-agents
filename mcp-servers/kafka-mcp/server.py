import os

import requests
from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "kafka",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://prometheus-sit.dozee.int")


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


@mcp.tool()
def get_consumer_lag(group_id: str, topic: str, job: str = "msk-kbc"):
    """Get Kafka consumer group lag for a topic."""
    group = _escape(group_id)
    top = _escape(topic)
    job_esc = _escape(job)
    return _query(
        f'kafka_consumer_group_ConsumerLagMetrics_Value{{job="{job_esc}",topic="{top}",'
        f'name="SumOffsetLag",groupId="{group}"}}'
    )


@mcp.tool()
def get_topic_message_rate(topic: str, job: str = "msk-kbc"):
    """Get Kafka topic message rate from log end offset increase over 5m."""
    top = _escape(topic)
    job_esc = _escape(job)
    return _query(
        f'sum by (topic, job) (increase(kafka_log_Log_Value{{job="{job_esc}", '
        f'name="LogEndOffset", topic="{top}"}}[5m]))'
    )


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
