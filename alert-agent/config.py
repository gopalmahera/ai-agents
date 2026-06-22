import os


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")

K8S_MCP_URL = os.getenv("K8S_MCP_URL", "http://127.0.0.1:8001/mcp")
PROMETHEUS_MCP_URL = os.getenv(
    "PROMETHEUS_MCP_URL",
    "http://127.0.0.1:8002/mcp",
)
LOKI_MCP_URL = os.getenv("LOKI_MCP_URL", "http://127.0.0.1:8003/mcp")
LOGS_DIR = os.getenv("LOGS_DIR", "/app/logs")
