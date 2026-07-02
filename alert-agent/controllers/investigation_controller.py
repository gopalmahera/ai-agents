import asyncio
import traceback

from services.classification.alert_classifier import build_alert_context
from config import LLM_ENABLED
from services.llm.deterministic_rca import build_deterministic_rca
from services.metrics.prefetch import build_prefetch
from views.report_view import save_rca
from services.llm.mcp_client import run_investigation
from views.slack_view import format_rca, format_report_header
from services.notification.slack_client import send_alert_report
import services.store.redis_client as _redis
from utils.metrics import llm_investigations, slack_posts


def _is_quota_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in ("RateLimitError", "ModelHTTPError"):
        return True
    message = str(exc).lower()
    return "insufficient_quota" in message or "429" in message


def _is_transient_llm_error(exc: BaseException) -> bool:
    name = type(exc).__name__
    if name in (
        "TimeoutError",
        "ConnectionError",
        "APIConnectionError",
        "APITimeoutError",
        "ConnectTimeout",
        "ReadTimeout",
    ):
        return True
    message = str(exc).lower()
    transient_markers = (
        "timeout",
        "timed out",
        "connection",
        "503",
        "502",
        "500",
        "server error",
        "service unavailable",
    )
    return any(marker in message for marker in transient_markers)


def _should_fallback_to_deterministic(exc: BaseException, prefetched) -> bool:
    if not prefetched:
        return False
    return _is_quota_error(exc) or _is_transient_llm_error(exc)


def _record_llm_outcome(outcome: str) -> None:
    _redis.counter_inc(f"llm_{outcome}" if outcome != "error" else "llm_error")
    llm_investigations.labels(outcome=outcome).inc()


def _run_rca(alert: dict, ctx, prefetched) -> str:
    if not LLM_ENABLED:
        _record_llm_outcome("fallback")
        return build_deterministic_rca(ctx, prefetched)

    try:
        result = asyncio.run(run_investigation(alert, prefetched=prefetched))
        _record_llm_outcome("success")
        return result
    except Exception as exc:
        if _should_fallback_to_deterministic(exc, prefetched):
            print(f"LLM unavailable ({exc}); using deterministic RCA")
            _record_llm_outcome("fallback")
            return build_deterministic_rca(ctx, prefetched)
        _record_llm_outcome("error")
        raise


def _save_report(alert: dict, ctx, body: str, *, skip_slack: bool = False) -> dict:
    labels = alert.get("labels", {})
    header = format_report_header(ctx, labels, alert=alert)
    report = f"{header}\n\n{body.strip()}"
    print("=" * 80)
    print(f"Alert report for {ctx.alertname}")
    print("=" * 80)
    print(report)
    log_file = save_rca(alert, report)
    print(f"Alert report saved to {log_file}")
    result = {
        "alertname": ctx.alertname,
        "header": header,
        "body": body.strip(),
        "report": report,
        "log_file": log_file,
    }
    if skip_slack:
        return result

    alertname = alert.get("labels", {}).get("alertname", "unknown")
    try:
        send_alert_report(alert, header, body.strip())
        _redis.counter_inc("slack_success")
        slack_posts.labels(outcome="success").inc()
        _redis.stream_add(alertname=alertname, outcome="rca_success")
    except Exception as exc:
        _redis.counter_inc("slack_error")
        slack_posts.labels(outcome="error").inc()
        _redis.stream_add(alertname=alertname, outcome="rca_slack_error")
        print(f"Failed to send Slack alert report: {exc}")
    return result


def investigate_alert(alert: dict, *, skip_slack: bool = False) -> dict | None:
    status = alert.get("status")
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")

    if status != "firing":
        print(f"Skipping non-firing alert: {alertname} status={status}")
        return None

    ctx = build_alert_context(alert)
    prefetched = build_prefetch(ctx, alert)

    try:
        rca = _run_rca(alert, ctx, prefetched)
        rca = format_rca(rca, ctx, prefetched=prefetched)
        return _save_report(alert, ctx, rca, skip_slack=skip_slack)
    except Exception as exc:
        if _should_fallback_to_deterministic(exc, prefetched):
            try:
                rca = format_rca(
                    build_deterministic_rca(ctx, prefetched), ctx, prefetched=prefetched
                )
                print("(deterministic fallback)")
                return _save_report(alert, ctx, rca, skip_slack=skip_slack)
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
        raise
