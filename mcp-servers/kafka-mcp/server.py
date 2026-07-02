import contextvars
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
_TIMEOUT = int(os.getenv("MCP_SOCKET_TIMEOUT", "30"))

# Per-request header capture: the agent injects the alert's environment endpoint
# via X-Prometheus-Url; each request falls back to the boot default if absent.
_req_headers: contextvars.ContextVar = contextvars.ContextVar("req_headers", default=None)


class _HeaderCaptureMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") == "http":
            hdrs = {k.decode("latin1").lower(): v.decode("latin1") for k, v in (scope.get("headers") or [])}
            token = _req_headers.set(hdrs)
            try:
                await self.app(scope, receive, send)
            finally:
                _req_headers.reset(token)
        else:
            await self.app(scope, receive, send)


def _base_url() -> str:
    return (_req_headers.get() or {}).get("x-prometheus-url") or PROMETHEUS_URL


def _auth_header() -> dict:
    # The agent injects a ready-to-use Authorization value for the env's endpoint.
    auth = (_req_headers.get() or {}).get("x-prometheus-authorization")
    return {"Authorization": auth} if auth else {}


def _get(url: str, **kwargs):
    headers = kwargs.pop("headers", None) or {}
    headers.update(_auth_header())
    return requests.get(url, headers=headers or None, timeout=_TIMEOUT, **kwargs)


_MSK_LAG_RE = re.compile(r"^msk\.(kbc|kb)\.(.+?)\s*>\s*\d+")
_MSK_NOMESSAGE_RE = re.compile(r"^msk\.(kbc|kb)\.nomessage\.(.+?)\s*=\s*0")


def _query(query: str):
    response = _get(f"{_base_url()}/api/v1/query", params={"query": query})
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
    payload = _get(f"{_base_url()}/api/v1/label/job/values")
    payload.raise_for_status()
    jobs = payload.json().get("data", [])
    return [job for job in jobs if "msk" in job or "kafka" in job]


@mcp.tool()
def list_active_msk_alerts():
    """List active Prometheus alerts with alertname starting with msk."""
    response = _get(f"{_base_url()}/api/v1/alerts")
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


@mcp.tool()
def get_broker_throughput(topic: str, job: str | None = None):
    """Get Kafka broker-level bytes-in and bytes-out per second for a topic."""
    top = _escape(topic)
    job_filter = f'job="{_escape(job)}",' if job else ""
    return {
        "bytes_out_per_sec_kb": _query(
            f'sum by(topic,job)(irate(kafka_server_BrokerTopicMetrics_Count{{{job_filter}name=~"BytesOutPerSec|BytesInPerSec",topic="{top}"}}[5m])) / 1024'
        ),
        "bytes_in_per_sec_kb": _query(
            f'sum by(topic,job)(irate(kafka_server_BrokerTopicMetrics_Count{{{job_filter}name="BytesInPerSec",topic="{top}"}}[5m])) / 1024'
        ),
    }


def _run() -> None:
    import uvicorn

    app = mcp.streamable_http_app()
    app.add_middleware(_HeaderCaptureMiddleware)
    uvicorn.run(
        app,
        host=os.getenv("MCP_HOST", "0.0.0.0"),
        port=int(os.getenv("MCP_PORT", "8000")),
        log_level=os.getenv("MCP_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    _run()
