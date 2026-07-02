import asyncio
import traceback

from services.classification.alert_classifier import build_alert_context
import config as _cfg
from services.llm.deterministic_rca import build_deterministic_rca
from services.metrics.prefetch import build_prefetch
from views.report_view import save_rca
from services.llm.mcp_client import run_investigation
from views.slack_view import format_rca, format_report_header
from services.notification.slack_client import send_alert_report
import services.store.redis_client as _redis
import services.store.mongo_client as _mongo
from services import environments as _environments
from utils.metrics import llm_investigations, slack_posts
from services.notification import silences as _silences
from utils.log import get_logger

logger = get_logger(__name__)


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


def _attach_recurrence(alert: dict) -> dict:
    fingerprint = alert.get("fingerprint", "")
    try:
        count = _redis.fingerprint_count_days(fingerprint, _cfg.RECURRENCE_LOOKBACK_DAYS)
    except Exception:
        count = 0
    if count >= _cfg.RECURRENCE_THRESHOLD:
        return {**alert, "_recurrence_count": count}
    return alert


def _run_rca(alert: dict, ctx, prefetched) -> tuple[str, dict | None]:
    """Return (rca_text, usage). usage is the priced LLM usage dict or None
    (deterministic fallback has no LLM cost)."""
    if not _cfg.LLM_ENABLED:
        _record_llm_outcome("fallback")
        return build_deterministic_rca(ctx, prefetched), None

    try:
        output, usage = asyncio.run(run_investigation(alert, prefetched=prefetched))
        _record_llm_outcome("success")
        return output, usage
    except Exception as exc:
        if _should_fallback_to_deterministic(exc, prefetched):
            logger.warning(
                "LLM unavailable; using deterministic RCA",
                extra={"alertname": ctx.alertname, "error": str(exc), "event": "llm_fallback"},
            )
            _record_llm_outcome("fallback")
            return build_deterministic_rca(ctx, prefetched), None
        _record_llm_outcome("error")
        raise


def _save_report(alert: dict, ctx, body: str, *, usage: dict | None = None, skip_slack: bool = False) -> dict:
    labels = alert.get("labels", {})
    header = format_report_header(ctx, labels, alert=alert)
    report = f"{header}\n\n{body.strip()}"
    logger.info(
        "Alert report generated",
        extra={"event": "rca_generated", "alertname": ctx.alertname},
    )
    log_file = save_rca(alert, report)
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
    fingerprint = alert.get("fingerprint", "")
    namespace = labels.get("namespace", "")
    severity = labels.get("severity", "")
    usage = usage or {}
    try:
        send_alert_report(alert, header, body.strip())
        _redis.counter_inc("slack_success")
        slack_posts.labels(outcome="success").inc()
        _redis.stream_add(
            alertname=alertname,
            outcome="rca_success",
            fingerprint=fingerprint,
        )
        _mongo.record_event(
            alertname=alertname, outcome="rca_success", namespace=namespace,
            fingerprint=fingerprint, severity=severity, **usage,
        )
    except Exception as exc:
        _redis.counter_inc("slack_error")
        slack_posts.labels(outcome="error").inc()
        _redis.stream_add(
            alertname=alertname,
            outcome="rca_slack_error",
            fingerprint=fingerprint,
        )
        _mongo.record_event(
            alertname=alertname, outcome="rca_slack_error", namespace=namespace,
            fingerprint=fingerprint, severity=severity, **usage,
        )
        logger.warning(
            "Failed to send Slack alert report",
            extra={"alertname": alertname, "error": str(exc), "event": "slack_error"},
            exc_info=exc,
        )
    return result


def investigate_alert(alert: dict, *, env: str | None = None, skip_slack: bool = False) -> dict | None:
    status = alert.get("status")
    labels = alert.get("labels", {})
    alertname = labels.get("alertname", "unknown")

    # Resolve this environment's endpoints (from the webhook path /webhook/<env>)
    # for the investigation — direct queries + MCP tools read them via
    # environments.current(). No env → the "default" environment / boot defaults.
    _env_token = _environments.bind(env)
    try:
        return _investigate_alert(alert, labels, alertname, status, skip_slack=skip_slack)
    finally:
        _environments.reset(_env_token)


def _investigate_alert(alert, labels, alertname, status, *, skip_slack=False):
    if status != "firing":
        logger.info(
            "Skipping non-firing alert",
            extra={"alertname": alertname, "outcome": status, "event": "alert_skipped"},
        )
        return None

    silenced, silence_id = _silences.is_silenced(labels)
    if silenced:
        logger.info(
            "Skipping silenced alert",
            extra={
                "alertname": alertname,
                "silence_id": silence_id,
                "outcome": "silenced",
                "event": "alert_silenced",
            },
        )
        return None

    alert = _attach_recurrence(alert)
    ctx = build_alert_context(alert)
    prefetched = build_prefetch(ctx, alert)

    try:
        rca, usage = _run_rca(alert, ctx, prefetched)
        rca = format_rca(rca, ctx, prefetched=prefetched)
        return _save_report(alert, ctx, rca, usage=usage, skip_slack=skip_slack)
    except Exception as exc:
        if _should_fallback_to_deterministic(exc, prefetched):
            try:
                rca = format_rca(
                    build_deterministic_rca(ctx, prefetched), ctx, prefetched=prefetched
                )
                logger.info(
                    "Deterministic fallback after investigation error",
                    extra={"alertname": alertname, "event": "llm_fallback"},
                )
                return _save_report(alert, ctx, rca, usage=None, skip_slack=skip_slack)
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
        logger.error(
            error_message,
            extra={"alertname": alertname, "event": "investigation_error"},
            exc_info=exc,
        )
        raise
