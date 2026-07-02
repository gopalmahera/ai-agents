import threading

from flask import Flask, jsonify, request, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from controllers.investigation_controller import investigate_alert
import config as _cfg
from views.report_view import log_incoming_payload
from services.notification.slack_client import send_alert_status
import services.store.redis_client as _redis


def _is_allowed_alertname(alertname: str) -> bool:
    pattern = _cfg._allowed_alertname_pattern
    if pattern is None:
        return True
    return pattern.search(alertname) is not None


def _is_duplicate(fingerprint: str) -> bool:
    return _redis.dedup_check_and_set(fingerprint, _cfg.DEDUP_TTL_SECONDS)


def _investigate_in_background(alert: dict) -> None:
    investigate_alert(alert)


def create_app() -> Flask:
    app = Flask(__name__)

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"})

    @app.get("/metrics")
    def metrics():
        return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)

    @app.post("/webhook")
    def webhook():
        payload = request.get_json(silent=True)
        if payload is None:
            return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

        try:
            log_incoming_payload(payload)
        except Exception as exc:
            print(f"Failed to log incoming payload: {exc}")

        group_status = payload.get("status", "unknown")
        alerts = payload.get("alerts", [])

        if group_status == "resolved":
            try:
                send_alert_status(payload)
            except Exception as exc:
                print(f"Failed to send Slack status notification: {exc}")
            print(f"Resolved webhook processed for {len(alerts)} alert(s)")
            return jsonify({"status": "ok", "alerts_received": len(alerts), "accepted": 0})

        accepted = 0
        for alert in alerts:
            labels = alert.get("labels", {})
            alertname = labels.get("alertname", "unknown")
            status = alert.get("status", "unknown")
            fingerprint = alert.get("fingerprint", "missing")

            print(
                f"Received alert alertname={alertname} status={status} fingerprint={fingerprint}"
            )
            _redis.counter_inc("alerts_received")
            _redis.alertname_inc(alertname)

            if status != "firing":
                print(f"Skipping alert alertname={alertname} because status={status}")
                _redis.counter_inc("alerts_skipped")
                continue

            if not _is_allowed_alertname(alertname):
                print(f"Skipping alert alertname={alertname} — not in ALLOWED_ALERTNAMES")
                _redis.counter_inc("alerts_skipped")
                continue

            if _is_duplicate(fingerprint):
                print(
                    f"Skipping duplicate alert alertname={alertname} fingerprint={fingerprint}"
                )
                _redis.counter_inc("alerts_deduplicated")
                continue

            thread = threading.Thread(
                target=_investigate_in_background,
                args=(alert,),
                daemon=True,
            )
            thread.start()
            _redis.counter_inc("alerts_accepted")
            _redis.stream_add(
                alertname=alertname,
                outcome="accepted",
                namespace=alert.get("labels", {}).get("namespace", ""),
            )
            accepted += 1

        return jsonify({"status": "ok", "alerts_received": len(alerts), "accepted": accepted})

    return app
