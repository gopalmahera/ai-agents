import contextvars
import os
import time
from datetime import datetime, timedelta, timezone

from mcp.server.fastmcp import FastMCP


mcp = FastMCP(
    "cloudwatch",
    host=os.getenv("MCP_HOST", "0.0.0.0"),
    port=int(os.getenv("MCP_PORT", "8000")),
    stateless_http=True,
)

# Boot default region (IRSA / pod role). Per-request headers override it.
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", ""))

# Per-request header capture: the agent injects the alert's environment AWS
# endpoint (region + auth) via X-Aws-* headers; requests without them use the
# default credential chain (IRSA / pod role).
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


def _hdr(name: str) -> str | None:
    return (_req_headers.get() or {}).get(name)


def _session():
    """Build a boto3 Session from the per-request AWS headers.

    Modes (X-Aws-Auth-Mode): ``assume_role`` (STS), ``keys`` (static access
    keys), or ``default`` — the ambient credential chain (IRSA / pod role).
    boto3 is imported lazily so the module loads without it installed.
    """
    import boto3

    region = _hdr("x-aws-region") or AWS_REGION or None
    mode = (_hdr("x-aws-auth-mode") or "default").lower()

    if mode == "assume_role":
        role_arn = _hdr("x-aws-role-arn")
        if role_arn:
            sts = boto3.client("sts", region_name=region)
            creds = sts.assume_role(RoleArn=role_arn, RoleSessionName="dai-agent-cw")["Credentials"]
            return boto3.Session(
                aws_access_key_id=creds["AccessKeyId"],
                aws_secret_access_key=creds["SecretAccessKey"],
                aws_session_token=creds["SessionToken"],
                region_name=region,
            )
    elif mode == "keys":
        access_key = _hdr("x-aws-access-key-id")
        secret_key = _hdr("x-aws-secret-access-key")
        if access_key and secret_key:
            return boto3.Session(
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region,
            )

    return boto3.Session(region_name=region)


def _dimensions(dimensions: dict | None) -> list:
    return [{"Name": str(k), "Value": str(v)} for k, v in (dimensions or {}).items()]


@mcp.tool()
def list_metrics(namespace: str, metric_name: str | None = None, dimensions: dict | None = None):
    """List CloudWatch metrics in a namespace (e.g. AWS/RDS, AWS/ApplicationELB),
    optionally filtered by metric name and dimension name/value pairs."""
    try:
        kwargs: dict = {"Namespace": namespace}
        if metric_name:
            kwargs["MetricName"] = metric_name
        if dimensions:
            kwargs["Dimensions"] = [{"Name": str(k), "Value": str(v)} for k, v in dimensions.items()]
        resp = _session().client("cloudwatch").list_metrics(**kwargs)
        return {"metrics": resp.get("Metrics", [])}
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def get_metric_statistics(
    namespace: str,
    metric_name: str,
    dimensions: dict | None = None,
    stat: str = "Average",
    period: int = 300,
    minutes: int = 60,
):
    """Get CloudWatch metric statistics over the last N minutes. ``stat`` is one
    of Average, Sum, Minimum, Maximum, SampleCount. ``dimensions`` is a
    name→value map (e.g. {"DBInstanceIdentifier": "prod-db"})."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        resp = _session().client("cloudwatch").get_metric_statistics(
            Namespace=namespace,
            MetricName=metric_name,
            Dimensions=_dimensions(dimensions),
            StartTime=start,
            EndTime=end,
            Period=period,
            Statistics=[stat],
        )
        points = sorted(resp.get("Datapoints", []), key=lambda d: d.get("Timestamp"))
        return {
            "label": resp.get("Label"),
            "datapoints": [
                {"timestamp": p.get("Timestamp").isoformat() if p.get("Timestamp") else None,
                 "value": p.get(stat), "unit": p.get("Unit")}
                for p in points
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def describe_alarms(state_value: str = "ALARM", max_records: int = 50):
    """List CloudWatch alarms, by default those currently in ALARM state
    (state_value: OK | ALARM | INSUFFICIENT_DATA)."""
    try:
        resp = _session().client("cloudwatch").describe_alarms(
            StateValue=state_value, MaxRecords=max_records
        )
        alarms = resp.get("MetricAlarms", []) + resp.get("CompositeAlarms", [])
        return {
            "alarms": [
                {"name": a.get("AlarmName"), "state": a.get("StateValue"),
                 "reason": a.get("StateReason"), "metric": a.get("MetricName"),
                 "namespace": a.get("Namespace")}
                for a in alarms
            ]
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def filter_log_events(log_group: str, filter_pattern: str = "", minutes: int = 30, limit: int = 100):
    """Fetch recent CloudWatch Logs events from a log group, optionally filtered
    by a CloudWatch Logs filter pattern (e.g. "ERROR")."""
    try:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        kwargs: dict = {
            "logGroupName": log_group,
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(end.timestamp() * 1000),
            "limit": limit,
        }
        if filter_pattern:
            kwargs["filterPattern"] = filter_pattern
        resp = _session().client("logs").filter_log_events(**kwargs)
        return {
            "events": [
                {"timestamp": e.get("timestamp"), "message": e.get("message"),
                 "stream": e.get("logStreamName")}
                for e in resp.get("events", [])
            ]
        }
    except Exception as exc:
        return {"error": str(exc)}


@mcp.tool()
def logs_insights_query(log_group: str, query: str, minutes: int = 30):
    """Run a CloudWatch Logs Insights query over the last N minutes and return
    its result rows (blocks until the query completes)."""
    try:
        client = _session().client("logs")
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=minutes)
        query_id = client.start_query(
            logGroupName=log_group,
            startTime=int(start.timestamp()),
            endTime=int(end.timestamp()),
            queryString=query,
        )["queryId"]

        for _ in range(30):  # ~30s max
            out = client.get_query_results(queryId=query_id)
            if out.get("status") in ("Complete", "Failed", "Cancelled", "Timeout"):
                break
            time.sleep(1)

        return {
            "status": out.get("status"),
            "rows": [
                {field.get("field"): field.get("value") for field in row}
                for row in out.get("results", [])
            ],
        }
    except Exception as exc:
        return {"error": str(exc)}


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
