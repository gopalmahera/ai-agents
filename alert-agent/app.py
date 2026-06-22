import threading

from flask import Flask, jsonify, request

from agent import investigate_alert


app = Flask(__name__)


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

    alerts = payload.get("alerts", [])
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

        thread = threading.Thread(
            target=_investigate_in_background,
            args=(alert,),
            daemon=True,
        )
        thread.start()

    return jsonify({"status": "ok", "alerts_received": len(alerts)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
