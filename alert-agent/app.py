from config import AGENT_PORT
from controllers.webhook_controller import create_app
from api.config_api import bp as config_bp
from api.metrics_api import bp as metrics_bp
from api.logs_api import bp as logs_bp
from services import config_sync
from utils.log import setup_logging

setup_logging()

app = create_app()
app.register_blueprint(config_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(logs_bp)

# Keep this replica's config in sync with the shared Redis store (HA)
config_sync.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=AGENT_PORT)
