from controllers.webhook_controller import create_app
from api.config_api import bp as config_bp
from api.metrics_api import bp as metrics_bp
from api.logs_api import bp as logs_bp

app = create_app()
app.register_blueprint(config_bp)
app.register_blueprint(metrics_bp)
app.register_blueprint(logs_bp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
