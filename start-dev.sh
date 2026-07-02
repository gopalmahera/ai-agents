#!/bin/sh
# Development entrypoint — MCP servers + auto-reload worker on Python changes
set -e

cleanup() {
  kill "$K8S_PID" "$PROM_PID" "$LOKI_PID" "$KAFKA_PID" "$CW_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

wait_for_port() {
  host="$1"
  port="$2"
  name="$3"
  i=1
  while [ "$i" -le 60 ]; do
    if python -c "import socket; s=socket.socket(); s.settimeout(1); s.connect(('$host', $port)); s.close()" 2>/dev/null; then
      echo "$name is ready on port $port"
      return 0
    fi
    sleep 1
    i=$((i + 1))
  done
  echo "$name failed to start on port $port" >&2
  return 1
}

MCP_HOST=0.0.0.0 MCP_PORT=8001 \
  KUBECONFIG="${KUBECONFIG:-}" \
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

MCP_HOST=0.0.0.0 MCP_PORT=8004 \
  PROMETHEUS_URL="${PROMETHEUS_URL:-http://prometheus-sit.dozee.int}" \
  python /app/mcp-servers/kafka-mcp/server.py &
KAFKA_PID=$!

MCP_HOST=0.0.0.0 MCP_PORT=8005 \
  AWS_REGION="${AWS_REGION:-}" \
  python /app/mcp-servers/cloudwatch-mcp/server.py &
CW_PID=$!

wait_for_port 127.0.0.1 8001 "k8s-mcp"
wait_for_port 127.0.0.1 8002 "prometheus-mcp"
wait_for_port 127.0.0.1 8003 "loki-mcp"
wait_for_port 127.0.0.1 8004 "kafka-mcp"
wait_for_port 127.0.0.1 8005 "cloudwatch-mcp"

export K8S_MCP_URL="${K8S_MCP_URL:-http://127.0.0.1:8001/mcp}"
export PROMETHEUS_MCP_URL="${PROMETHEUS_MCP_URL:-http://127.0.0.1:8002/mcp}"
export LOKI_MCP_URL="${LOKI_MCP_URL:-http://127.0.0.1:8003/mcp}"
export KAFKA_MCP_URL="${KAFKA_MCP_URL:-http://127.0.0.1:8004/mcp}"
export CLOUDWATCH_MCP_URL="${CLOUDWATCH_MCP_URL:-http://127.0.0.1:8005/mcp}"

cd /app/agent
echo "Starting worker with file watch (dev)…"
exec watchfiles --filter python 'python worker.py' /app/agent
