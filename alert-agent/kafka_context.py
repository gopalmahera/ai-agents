from alert_catalog import get_alert_meaning
from alert_context import AlertContext


def prefetch_kafka_context(ctx: AlertContext, alert: dict) -> dict | None:
    if ctx.resource_type != "kafka":
        return None

    labels = alert.get("labels", {})
    bullets: list[str] = []

    region = labels.get("region") or ctx.region
    if region:
        bullets.append(f"region: {region}")
    if ctx.workload_namespace and ctx.workload_deployment:
        bullets.append(f"deployment: {ctx.workload_namespace}/{ctx.workload_deployment}")

    meaning = get_alert_meaning(ctx.alertname, alert)

    return {
        "bullets": bullets,
        "alert_meaning": meaning,
        "region": region,
        "cloud": labels.get("cloud") or ctx.cloud,
        "stage": labels.get("stage") or ctx.stage,
    }
