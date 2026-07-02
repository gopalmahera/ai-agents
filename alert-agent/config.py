import os
import re


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai|anthropic|gemini|bedrock|fake
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

PROMETHEUS_URL = os.getenv(
    "PROMETHEUS_URL",
    "http://service-gps.monitoring.svc.cluster.local:9090",
)
LOKI_URL = os.getenv("LOKI_URL", "http://localhost:3100")
K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8001/mcp")
PROMETHEUS_MCP_URL = os.getenv(
    "PROMETHEUS_MCP_URL",
    "http://127.0.0.1:8002/mcp",
)
LOKI_MCP_URL = os.getenv("LOKI_MCP_URL", "http://127.0.0.1:8003/mcp")
KAFKA_MCP_URL = os.getenv("KAFKA_MCP_URL", "http://127.0.0.1:8004/mcp")
LOGS_DIR = os.getenv("LOGS_DIR", "/app/logs")
ROUTING_CONFIG_PATH = os.getenv("ROUTING_CONFIG_PATH", "")
ALERT_CATALOG_PATH = os.getenv("ALERT_CATALOG_PATH", "")

DEDUP_TTL_SECONDS = int(os.getenv("DEDUP_TTL_SECONDS", "900"))
ALLOWED_ALERTNAMES = os.getenv("ALLOWED_ALERTNAMES", "")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CONFIG_STORE_PATH = os.getenv("CONFIG_STORE_PATH", "/app/config/web_config.json")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

_allowed_alertname_pattern: re.Pattern[str] | None = None
if ALLOWED_ALERTNAMES:
    _allowed_alertname_pattern = re.compile(ALLOWED_ALERTNAMES)
