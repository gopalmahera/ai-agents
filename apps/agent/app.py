"""Legacy Flask app — health/metrics probes only. Production uses worker.py."""

from controllers.webhook_controller import create_app
from utils.log import setup_logging

setup_logging()
app = create_app()

if __name__ == "__main__":
    from config import AGENT_PORT

    app.run(host="0.0.0.0", port=AGENT_PORT)
