# AI Alert Agent

AI-powered Alertmanager webhook that automatically investigates firing alerts using live data from Kubernetes, Prometheus, Loki, and Kafka — then posts a structured Root Cause Analysis (RCA) to the right Slack channel.

The stack has three services (via `docker compose`):

| Service | Port | Purpose |
|---|---|---|
| `alert-agent` | 5001 | Flask webhook, LLM agent, four embedded MCP tool servers |
| `web` | 3000 | Next.js config dashboard (AI provider, MCP URLs, routing, logs, reports) |
| `redis` | 6379 | Persistent store — dedup cache, counters, alert event stream |

---

## How It Works

```
Alertmanager
    │
    │  POST /webhook
    ▼
┌─────────────────────────────────────────────────────┐
│                  alert-agent container               │
│                                                     │
│  Flask webhook  ──►  Classify alert by type         │
│                           │                         │
│                           ▼                         │
│                   PydanticAI Agent (GPT-4o)         │
│                    │    │    │    │                  │
│               k8s  prom loki kafka  ◄── MCP servers │
│              :8001 :8002 :8003 :8004                │
└─────────────────────────────────────────────────────┘
    │
    │  RCA report
    ▼
Slack channel  (routed by routing.yaml)
```

1. Alertmanager fires → `POST /webhook`
2. Alert is classified by resource type: `kubernetes`, `host`, `probe`, `kafka`
3. The LLM agent queries live MCP tools (pod events, Prometheus metrics, Loki logs, Kafka lag)
4. Produces a structured RCA with **Findings**, **Probable Root Cause**, and **Recommended Actions**
5. Posts the report to the configured Slack channel via `routing.yaml` rules

---

## Alert Coverage

| Alert Category | Resource Type | MCP Tools Used |
|---|---|---|
| Pod CPU / memory limits | `kubernetes` | k8s events + prom metrics + loki logs |
| Pod OOM kill / eviction | `kubernetes` | k8s events + prom memory snapshot |
| Pod anomaly (cpu/memory/network) | `kubernetes` | prom baseline comparison |
| Pod restart | `kubernetes` | k8s events + loki logs |
| EC2 host down / CPU / memory | `host` | prom node-exporter |
| EC2 swap / inodes / disk latency | `host` | prom `get_node_advanced` |
| EC2 systemd / RAID / clock / temp | `host` | prom `get_node_advanced` |
| Blackbox HTTP / TCP probe | `probe` | prom probe metrics |
| TLS certificate expiry | `probe` | prom probe metrics |
| MSK / Kafka consumer lag | `kafka` | kafka lag + prom + loki |
| Kafka broker throughput | `kafka` | kafka `get_broker_throughput` |

---

## Quick Start (Local)

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env — set OPENAI_API_KEY, SLACK_WEBHOOK_URL, PROMETHEUS_URL, LOKI_URL
```

### 2. Configure Slack routing

```bash
cp alert-agent/routing.example.yaml alert-agent/routing.yaml
# Edit routing.yaml — add your webhook URLs and match rules
```

### 3. Run

```bash
docker compose up --build
```

### 4. Verify

```bash
# Health check
curl http://localhost:5001/health

# Send a test alert
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d @sample/network-pod-high-transmit-alert.json

# Prometheus metrics
curl http://localhost:5001/metrics
```

---

## Slack Channel Routing

Alerts are routed to different Slack channels using `alert-agent/routing.yaml`. Rules use the same `match` / `match_re` semantics as Alertmanager.

```yaml
# alert-agent/routing.yaml

default_slack_webhook_url: "https://hooks.slack.com/services/DEFAULT/..."

routes:
  # Critical prod alerts → #alerts-prod-critical
  - match:
      severity: critical
      stage: prod
    slack_webhook_url: "https://hooks.slack.com/services/CRITICAL/..."

  # All EC2 / infra alerts → #infra-alerts
  - match_re:
      alertname: "^EC2Host.*"
    slack_webhook_url: "https://hooks.slack.com/services/INFRA/..."

  # Kafka alerts → #kafka-alerts
  - match_re:
      alertname: "^(msk\\.|NetworkKafka).*"
    slack_webhook_url: "https://hooks.slack.com/services/KAFKA/..."
```

**Rules:**
- Evaluated **top-to-bottom**; first match wins
- `match` — exact label equality (all keys must match, AND logic)
- `match_re` — regex per label value
- Both can be combined in one rule
- Falls back to `default_slack_webhook_url`, then `SLACK_WEBHOOK_URL` env var

The file is **volume-mounted** — edit it and restart the container; no image rebuild needed.

---

## RCA Output Format

Each Slack post has two attachments — a colored header and a body:

**Header** (colored by severity):
```
🚨 *PODCPULimitsUage>=90* | severity: critical
Namespace: dozeeplatform | Pod: consumer-abc | Region: ap-south-1 | Started: 2026-06-28 11:30 UTC
_Pod CPU usage exceeded 90% of its limit for 5+ minutes_
<https://prometheus/graph?...|View in Prometheus>
```

**Body:**
```
*Findings:*
• CPU throttling at 94% over the last 10 minutes
• Pod consumer-abc restarted 2 times in the last hour
• Loki logs show repeated timeout errors at 11:28 UTC

*Probable Root Cause:*
Consumer thread pool saturated by a spike in Kafka message volume at 11:27 UTC.

*Recommended Actions:*
1. Scale the consumer deployment horizontally (currently 2 replicas)
2. Increase CPU limit from 500m to 1000m
3. Check upstream producer for message volume spike
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | _(required)_ | OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o` | Model to use |
| `SLACK_WEBHOOK_URL` | _(optional)_ | Fallback Slack webhook when no routing rule matches |
| `ROUTING_CONFIG_PATH` | _(optional)_ | Path to `routing.yaml` inside the container |
| `PROMETHEUS_URL` | cluster default | Prometheus base URL |
| `LOKI_URL` | cluster default | Loki base URL |
| `LOGS_DIR` | `/app/logs` | Directory for saved RCA log files |
| `DEDUP_TTL_SECONDS` | `900` | Ignore duplicate fingerprints for this many seconds |
| `ALLOWED_ALERTNAMES` | _(unset = all)_ | Regex filter — only process matching alert names |
| `LLM_ENABLED` | `true` | Set `false` to use deterministic RCA fallback only |

---

## Kubernetes Deployment

Manifests: [`deploy/k8s/ai-alert-agent.yaml`](deploy/k8s/ai-alert-agent.yaml)

### Build and push image

```bash
# Tag with git tag or short SHA; push to ECR
TAG=1.0.1 ./deploy/build-push.sh

# Also push :latest
TAG=1.0.1 TAG_LATEST=true ./deploy/build-push.sh
```

> **Apple Silicon note:** EKS nodes are `linux/amd64`. The build script sets `--platform linux/amd64` automatically. Never run a plain `docker build .` from an M1/M2 Mac for production.

### Create secrets (once per cluster)

```bash
kubectl -n monitoring create secret generic ai-alert-agent-secrets \
  --from-literal=openai-api-key="$OPENAI_API_KEY" \
  --from-literal=slack-webhook-url="$SLACK_WEBHOOK_URL"
```

### In-cluster URLs

| Variable | Value |
|---|---|
| `PROMETHEUS_URL` | `http://service-gps.monitoring.svc.cluster.local:9090` |
| `LOKI_URL` | `http://loki-gateway.monitoring.svc.cluster.local` |
| Kubernetes auth | ServiceAccount `ai-alert-agent` (in-cluster, no kubeconfig needed) |

Alertmanager receiver `ai-alert-agent` uses `continue: true` — existing Slack routes are unchanged.

---

## MCP Servers

| Server | Port | Tools |
|---|---|---|
| `k8s-mcp` | 8001 | `get_pods`, `get_events`, `get_deployment`, `get_pod_logs`, `describe_pod`, … |
| `prometheus-mcp` | 8002 | `query_promql`, `get_pod_cpu/memory`, `get_node_memory/load`, `get_node_advanced`, `get_probe_*`, … |
| `loki-mcp` | 8003 | `query_logs`, `get_pod_logs`, `get_error_logs` |
| `kafka-mcp` | 8004 | `get_consumer_lag`, `get_broker_throughput`, `list_topics`, … |

Tools are exposed with prefixes (`k8s_`, `prom_`, `loki_`, `kafka_`) so the LLM knows which server each tool belongs to.

---

## Guardrails

| Feature | Detail |
|---|---|
| **Deduplication** | Same alert `fingerprint` is ignored for `DEDUP_TTL_SECONDS` (default 15 min) |
| **Allowlist filter** | `ALLOWED_ALERTNAMES` regex — drop alerts not matching |
| **LLM fallback** | If OpenAI is unavailable or quota exceeded, falls back to a deterministic RCA using prefetched metrics |
| **Body truncation** | Slack body capped at 3,800 chars with a truncation notice |
| **Retry on Slack** | Up to 3 attempts with exponential backoff (2s → 4s → 8s) |
| **k8s degraded mode** | If no kubeconfig is available (local dev), k8s tools return an error dict instead of crashing |

---

## Running Tests

```bash
# Create venv (first time)
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt pytest

# Run all tests
PYTHONPATH=alert-agent .venv/bin/python -m pytest alert-agent/test_*.py -v
```

---

## Project Structure

```
ai-agents/
├── alert-agent/
│   ├── app.py                  # Flask webhook server
│   ├── agent.py                # Alert investigation orchestration
│   ├── mcp_client.py           # PydanticAI agent + MCP toolset setup
│   ├── alert_context.py        # Alert classification and context building
│   ├── alert_catalog.py        # One-line alert descriptions (42 entries)
│   ├── routing.py              # Slack channel routing engine
│   ├── routing.yaml            # Routing rules (edit this)
│   ├── routing.example.yaml    # Annotated example routing config
│   ├── slack_client.py         # Slack posting with retry and truncation
│   ├── report_header.py        # Rich Slack header formatting
│   ├── rca_formatter.py        # RCA post-processing and formatting
│   ├── deterministic_rca.py    # LLM-free fallback RCA
│   ├── prefetch.py             # Pre-fetches metrics before LLM call
│   ├── config.py               # Environment variable config
│   ├── metrics.py              # Prometheus metrics (counters)
│   ├── log_writer.py           # Saves RCA reports to disk
│   └── prompts/
│       └── rca_prompt.txt      # LLM system prompt with tool hints
├── mcp-servers/
│   ├── k8s-mcp/server.py       # Kubernetes MCP server
│   ├── prometheus-mcp/server.py# Prometheus MCP server
│   ├── loki-mcp/server.py      # Loki MCP server
│   └── kafka-mcp/server.py     # Kafka/MSK MCP server
├── deploy/
│   ├── k8s/ai-alert-agent.yaml # Kubernetes manifests
│   └── build-push.sh           # ECR build + push script
├── sample/                     # Sample Alertmanager payloads for testing
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── start.sh                    # Container entrypoint
```

---

## Future Improvements

- **Persistent dedup store** — replace in-memory dedup with Redis/SQLite so restarts don't re-trigger investigations
- **Alert queue** — bounded work queue instead of unbounded threads to handle alert storms gracefully
- **Runbook links** — add `runbook_url` per alert in catalog; append to every RCA
- **Multi-alert correlation** — group alerts firing on the same node/namespace into a single RCA
- **Historical comparison** — compare current metric values against 7-day baselines to flag recurring issues
- **Confidence score** — LLM rates certainty (low/medium/high); low-confidence RCAs flagged in Slack
- **`/webhook/test` endpoint** — synchronous RCA without Slack post, for local testing and CI
- **`routing.yaml` hot-reload** — reload routes without container restart (`POST /reload` endpoint)
- **Structured JSON logs** — replace `print()` with structured logging for Loki/CloudWatch ingestion
- **Grafana dashboard** — visualize `alerts_received`, `llm_investigations`, `slack_posts` with latency histograms
- **Multi-tenant routing** — route different alert groups to different OpenAI keys or models (e.g. GPT-4o-mini for `info` severity)
- **Helm chart** — package manifests with `routing.yaml` as a ConfigMap value for GitOps-native management
