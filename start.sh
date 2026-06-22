#!/bin/sh
set -e

cleanup() {
  kill "$K8S_PID" "$PROM_PID" "$LOKI_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

MCP_HOST=0.0.0.0 MCP_PORT=8001 \
  KUBECONFIG="${KUBECONFIG:-/kube/config}" \
  python /app/mcp-servers/k8s-mcp/server.py &
K8S_PID=$!

MCP_HOST=0.0.0.0 MCP_PORT=8002 \
  PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus-sit.dozee.int}" \
  python /app/mcp-servers/prometheus-mcp/server.py &
PROM_PID=$!

MCP_HOST=0.0.0.0 MCP_PORT=8003 \
  LOKI_URL="${LOKI_URL:-http://host.docker.internal:3100}" \
  python /app/mcp-servers/loki-mcp/server.py &
LOKI_PID=$!

sleep 3

export K8S_MCP_URL="${K8S_MCP_URL:-http://127.0.0.1:8001/mcp}"
export PROMETHEUS_MCP_URL="${PROMETHEUS_MCP_URL:-http://127.0.0.1:8002/mcp}"
export LOKI_MCP_URL="${LOKI_MCP_URL:-http://127.0.0.1:8003/mcp}"

cd /app/alert-agent
exec python app.py
