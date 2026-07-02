import os
import re


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
AI_PROVIDER = os.getenv("AI_PROVIDER", "openai")  # openai|anthropic|gemini|bedrock|fake
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

# ── Provider credentials / settings (env names match the underlying SDKs) ──────
# OpenAI (also Azure/proxy via base URL)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "")
# Anthropic (direct API)
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# Gemini — Vertex (service-account JSON) or GLA (API key)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GOOGLE_SA_JSON = os.getenv("GOOGLE_SA_JSON", "")  # SA JSON *content*; materialised to a file
GOOGLE_APPLICATION_CREDENTIALS = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GOOGLE_GENAI_USE_VERTEXAI = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
# AWS Bedrock — auth via pod IAM role (IRSA); optional cross-account assume-role
AWS_REGION = os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", ""))
AWS_ROLE_ARN = os.getenv("AWS_ROLE_ARN", "")

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
# CloudWatch MCP (AWS metrics/logs). Empty disables the CloudWatch toolset.
CLOUDWATCH_MCP_URL = os.getenv("CLOUDWATCH_MCP_URL", "http://127.0.0.1:8005/mcp")
LOGS_DIR = os.getenv("LOGS_DIR", "/app/logs")
ROUTING_CONFIG_PATH = os.getenv("ROUTING_CONFIG_PATH", "")
ALERT_CATALOG_PATH = os.getenv("ALERT_CATALOG_PATH", "")
# Named endpoint registry (Prometheus/Loki/Kubernetes/AWS + auth) referenced by
# environments; managed from the Web UI (Settings → Endpoint Management).
ENDPOINTS_CONFIG_PATH = os.getenv("ENDPOINTS_CONFIG_PATH", "/app/config/endpoints.yaml")
# Environments map named endpoints to a per-env webhook path (/webhook/<env>).
ENVIRONMENTS_CONFIG_PATH = os.getenv("ENVIRONMENTS_CONFIG_PATH", "/app/config/environments.yaml")

DEDUP_TTL_SECONDS = int(os.getenv("DEDUP_TTL_SECONDS", "900"))
ALLOWED_ALERTNAMES = os.getenv("ALLOWED_ALERTNAMES", "")
LLM_ENABLED = os.getenv("LLM_ENABLED", "true").lower() in ("1", "true", "yes")
INVESTIGATION_MAX_WORKERS = int(os.getenv("INVESTIGATION_MAX_WORKERS", "8"))
INVESTIGATION_QUEUE_MAX = int(os.getenv("INVESTIGATION_QUEUE_MAX", "100"))
OPENAI_MODEL_INFO = os.getenv("OPENAI_MODEL_INFO", "gpt-4o-mini")
RECURRENCE_LOOKBACK_DAYS = int(os.getenv("RECURRENCE_LOOKBACK_DAYS", "7"))
RECURRENCE_THRESHOLD = int(os.getenv("RECURRENCE_THRESHOLD", "3"))

ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
CONFIG_STORE_PATH = os.getenv("CONFIG_STORE_PATH", "/app/config/web_config.json")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
# Optional durable history/reports store. Empty = disabled (Redis stream only).
MONGO_URL = os.getenv("MONGO_URL", "")
MONGO_DB = os.getenv("MONGO_DB", "alert_agent")
AGENT_PORT = int(os.getenv("AGENT_PORT", "8080"))

_allowed_alertname_pattern: re.Pattern[str] | None = None
if ALLOWED_ALERTNAMES:
    _allowed_alertname_pattern = re.compile(ALLOWED_ALERTNAMES)
