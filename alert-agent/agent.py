import asyncio
import traceback

from alert_context import build_alert_context
from config import LLM_ENABLED
from deterministic_rca import build_deterministic_rca
from prefetch import build_prefetch
from log_writer import save_rca
from mcp_client import run_investigation
from rca_formatter import format_rca
from report_header import format_report_header
from slack_client import send_alert_report


def _is_quota_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("RateLimitError", "ModelHTTPError"):
        return True
    message = str(exc).lower()
    return "insufficient_quota" in message or "429" in message


def _run_rca(alert: dict, ctx, prefetched) -> str:
    if not LLM_ENABLED:
        return build_deterministic_rca(ctx, prefetched)

    try:
        return asyncio.run(run_investigation(alert, prefetched=prefetched))
    except Exception as exc:
        if _is_quota_error(exc) or not LLM_ENABLED:
            print(f"LLM unavailable ({exc}); using deterministic RCA")
            return build_deterministic_rca(ctx, prefetched)
        raise


def _save_report(alert: dict, ctx, body: str) -> None:
    labels = alert.get("labels", {})
    header = format_report_header(ctx, labels)
    report = f"{header}\n\n{body.strip()}"
    print("=" * 80)
    print(f"Alert report for {ctx.alertname}")
    print("=" * 80)
    print(report)
    log_file = save_rca(alert, report)
    print(f"Alert report saved to {log_file}")
    try:
        send_alert_report(alert, report)
    except Exception as exc:
        print(f"Failed to send Slack alert report: {exc}")


def investigate_alert(alert: dict) -> None:
    status = alert.get("status")
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")

    if status != "firing":
        print(f"Skipping non-firing alert: {alertname} status={status}")
        return

    ctx = build_alert_context(alert)
    prefetched = build_prefetch(ctx, alert)

    try:
        rca = _run_rca(alert, ctx, prefetched)
        rca = format_rca(rca, ctx, prefetched=prefetched)
        _save_report(alert, ctx, rca)
    except Exception as exc:
        if _is_quota_error(exc) and prefetched:
            try:
                rca = format_rca(
                    build_deterministic_rca(ctx, prefetched), ctx, prefetched=prefetched
                )
                _save_report(alert, ctx, rca)
                print("(deterministic fallback)")
                return
            except Exception:
                pass

        if _is_quota_error(exc):
            error_message = (
                f"Alert investigation failed for {alertname}: OpenAI quota exceeded. "
                "Enable billing, set a valid OPENAI_API_KEY, or set LLM_ENABLED=false."
            )
        else:
            error_message = (
                f"Alert investigation failed for {alertname}.\n\n"
                f"Traceback:\n{traceback.format_exc()}"
            )
        print(error_message)
