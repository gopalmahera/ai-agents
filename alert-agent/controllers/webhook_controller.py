from concurrent.futures import ThreadPoolExecutor

from flask import Flask, jsonify, request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from controllers.investigation_controller import investigate_alert
import config as _cfg
from views.report_view import log_incoming_payload
from services.notification.slack_client import send_alert_status
import services.store.redis_client as _redis
from utils.metrics import (
    alerts_received,
    alerts_deduplicated,
    alerts_skipped,
    alerts_silenced,
    alerts_accepted,
)
from services.notification import silences as _silences
from utils.log import get_logger

logger = get_logger(__name__)

_executor: ThreadPoolExecutor | None = None


def _get_executor() -> ThreadPoolExecutor:
    global _executor
    if _executor is None:
        _executor = ThreadPoolExecutor(
            max_workers=_cfg.INVESTIGATION_MAX_WORKERS,
            thread_name_prefix="investigate",
        )
    return _executor


def _is_allowed_alertname(alertname: str) -> bool:
    pattern = _cfg._allowed_alertname_pattern
    if pattern is None:
        return True
    return pattern.search(alertname) is not None


def _is_duplicate(fingerprint: str) -> bool:
    return _redis.dedup_check_and_set(fingerprint, _cfg.DEDUP_TTL_SECONDS)


def _investigate_in_background(alert: dict) -> None:
    investigate_alert(alert)


def _extract_test_alert(payload: dict) -> dict | None:
    alerts = payload.get("alerts")
    if alerts is not None:
        if not alerts:
            return None
        return alerts[0]
    if payload.get("labels"):
        return payload
    return None


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.post("/webhook/test")
    def webhook_test():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

        alert = _extract_test_alert(payload)
        if alert is None:
            return jsonify(
                {"status": "error", "message": "Expected webhook payload with alerts[] or a single alert object"}
            ), 400

        if alert.get("status") != "firing":
            alert = {**alert, "status": "firing"}

        try:
            result = investigate_alert(alert, skip_slack=True)
        except Exception as exc:
            return jsonify({"status": "error", "message": str(exc)}), 500

        if result is None:
            return jsonify({"status": "error", "message": "Alert must have status=firing"}), 400

        return jsonify({"status": "ok", **result})

    @app.post("/webhook")
    def webhook():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

        try:
            log_incoming_payload(payload)
        except Exception as exc:
            logger.warning("Failed to log incoming payload: %s", exc, exc_info=exc)

        group_status = payload.get("status", "unknown")
        alerts = payload.get("alerts", [])

        if group_status == "resolved":
            try:
                send_alert_status(payload)
            except Exception as exc:
                logger.warning("Failed to send Slack status notification: %s", exc, exc_info=exc)
            logger.info(
                "Resolved webhook processed",
                extra={"event": "webhook_resolved", "outcome": "resolved", "alerts": len(alerts)},
            )
            return jsonify({"status": "ok", "alerts_received": len(alerts), "accepted": 0})

        accepted = 0
        for alert in alerts:
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "unknown")
            status = alert.get("status", "unknown")
            fingerprint = alert.get("fingerprint", "missing")

            logger.info(
                "Alert received",
                extra={
                    "event": "alert_received",
                    "alertname": alertname,
                    "fingerprint": fingerprint,
                    "outcome": status,
                },
            )
            _redis.counter_inc("alerts_received")
            alerts_received.labels(alertname=alertname).inc()
            _redis.alertname_inc(alertname)

            if status != "firing":
                logger.info(
                    "Alert skipped — non-firing status",
                    extra={"event": "alert_skipped", "alertname": alertname, "outcome": status},
                )
                _redis.counter_inc("alerts_skipped")
                alerts_skipped.inc()
                continue

            if not _is_allowed_alertname(alertname):
                logger.info(
                    "Alert skipped — allowlist filter",
                    extra={"event": "alert_skipped", "alertname": alertname, "outcome": "allowlist"},
                )
                _redis.counter_inc("alerts_skipped")
                alerts_skipped.inc()
                continue

            silenced, silence_id = _silences.is_silenced(labels)
            if silenced:
                logger.info(
                    "Alert silenced",
                    extra={
                        "event": "alert_silenced",
                        "alertname": alertname,
                        "fingerprint": fingerprint,
                        "silence_id": silence_id,
                        "outcome": "silenced",
                    },
                )
                _redis.counter_inc("alerts_silenced")
                alerts_silenced.inc()
                _redis.stream_add(
                    alertname=alertname,
                    outcome="silenced",
                    namespace=labels.get("namespace", ""),
                    fingerprint=fingerprint,
                    extra={"silence_id": silence_id or ""},
                )
                continue

            if _is_duplicate(fingerprint):
                logger.info(
                    "Alert skipped — duplicate fingerprint",
                    extra={
                        "event": "alert_deduplicated",
                        "alertname": alertname,
                        "fingerprint": fingerprint,
                    },
                )
                _redis.counter_inc("alerts_deduplicated")
                alerts_deduplicated.inc()
                continue

            _get_executor().submit(_investigate_in_background, alert)
            _redis.counter_inc("alerts_accepted")
            alerts_accepted.inc()
            _redis.stream_add(
                alertname=alertname,
                outcome="accepted",
                namespace=alert.get("labels", {}).get("namespace", ""),
                fingerprint=fingerprint,
            )
            accepted += 1

        return jsonify({"status": "ok", "alerts_received": len(alerts), "accepted": accepted})

    return app
