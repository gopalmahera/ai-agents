import threading
import time

from flask import Flask, jsonify, request

from agent import investigate_alert
from config import DEDUP_TTL_SECONDS, _allowed_alertname_pattern
from slack_client import send_alert_status


app = Flask(__name__)

_dedup_lock = threading.Lock()
_recent_fingerprints: dict[str, float] = {}


def _is_allowed_alertname(alertname: str) -> bool:
    if _allowed_alertname_pattern is None:
        return True
    return _allowed_alertname_pattern.search(alertname) is not None


def _is_duplicate(fingerprint: str) -> bool:
    now = time.time()
    with _dedup_lock:
        expired = [
            key
            for key, seen_at in _recent_fingerprints.items()
            if now - seen_at > DEDUP_TTL_SECONDS
        ]
        for key in expired:
            del _recent_fingerprints[key]

        if fingerprint in _recent_fingerprints:
            return True

        _recent_fingerprints[fingerprint] = now
        return False


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


def _investigate_in_background(alert: dict) -> None:
    investigate_alert(alert)


@app.post("/webhook")
def webhook():
    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify({"status": "error", "message": "Invalid or missing JSON body"}), 400

    group_status = payload.get("status", "unknown")
    alerts = payload.get("alerts", [])

    try:
        send_alert_status(payload)
    except Exception as exc:
        print(f"Failed to send Slack status notification: {exc}")

    if group_status == "resolved":
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

        if status != "firing":
            print(f"Skipping alert alertname={alertname} because status={status}")
            continue

        if not _is_allowed_alertname(alertname):
            print(f"Skipping alert alertname={alertname} — not in ALLOWED_ALERTNAMES")
            continue

        if _is_duplicate(fingerprint):
            print(
                f"Skipping duplicate alert alertname={alertname} fingerprint={fingerprint}"
            )
            continue

        thread = threading.Thread(
            target=_investigate_in_background,
            args=(alert,),
            daemon=True,
        )
        thread.start()
        accepted += 1

    return jsonify({"status": "ok", "alerts_received": len(alerts), "accepted": accepted})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
