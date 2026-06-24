import asyncio
import traceback

from alert_context import build_alert_context
from host_metrics import prefetch_host_metrics
from log_writer import save_rca
from mcp_client import run_investigation
from rca_formatter import format_rca
from slack_client import send_slack


def investigate_alert(alert: dict) -> None:
    status = alert.get("status")
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")

    if status != "firing":
        print(f"Skipping non-firing alert: {alertname} status={status}")
        return

    try:
        ctx = build_alert_context(alert)
        prefetched = prefetch_host_metrics(ctx, alert)
        rca = asyncio.run(run_investigation(alert, prefetched=prefetched))
        rca = format_rca(rca, ctx, prefetched=prefetched)
        print("=" * 80)
        print(f"RCA for {alertname}")
        print("=" * 80)
        print(rca)
        log_file = save_rca(alert, rca)
        print(f"RCA saved to {log_file}")
        send_slack(rca, alert=alert)
    except Exception:
        error_message = (
            f"Alert investigation failed for {alertname}.\n\n"
            f"Traceback:\n{traceback.format_exc()}"
        )
        print(error_message)
        try:
            send_slack(error_message, alert=alert)
        except Exception:
            print("Failed to send Slack error notification.")
