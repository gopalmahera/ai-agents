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
Alertmanager                        Web UI (Next.js :3000)
    │                                   │
    │  POST /webhook                    │  /api/config, /api/metrics, /api/logs
    ▼                                   ▼
┌─────────────────────────────────────────────────────┐
│                  alert-agent container               │
│                                                     │
│  Flask webhook  ──►  Classify alert by type         │
│                           │                         │
│                           ▼                         │
│              PydanticAI Agent (OpenAI/Anthropic/    │
│                    Gemini/Bedrock)                  │
│                    │    │    │    │                  │
│               k8s  prom loki kafka  ◄── MCP servers │
│              :8001 :8002 :8003 :8004                │
└──────────────┬──────────────────────────────────────┘
    │          │
    │          ▼
    │        Redis (:6379) — dedup, counters, alert history
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

# Send a test alert (async — posts to Slack)
curl -X POST http://localhost:5001/webhook \
  -H "Content-Type: application/json" \
  -d @sample/network-pod-high-transmit-alert.json

# Test RCA synchronously (no Slack post)
curl -X POST http://localhost:5001/webhook/test \
  -H "Content-Type: application/json" \
  -d @sample/pod-cpu-limits-usage-alert.json

# Prometheus metrics
curl http://localhost:5001/metrics
```

### 5. Open the Web UI

Visit **http://localhost:3000** — dashboard, config pages, routing editor, log browser, and reports.

---

## Web Config UI

Next.js dashboard (`web/`) for configuring and monitoring the agent without editing env files:

| Page | Purpose |
|---|---|
| **Dashboard** | Stat cards (received / accepted / deduplicated / LLM outcomes), MCP + Redis health |
| **Config → AI Provider** | Provider (`openai` / `anthropic` / `gemini` / `bedrock` / `fake`), model, API key, LLM on/off |
| **Config → Service Endpoints** | Direct data-source endpoints (`PROMETHEUS_URL`, `LOKI_URL`) with health checks; read-only status of the internal MCP servers |
| **Config → Storage** | Logs dir, dedup TTL, allowed alertnames regex, catalog/routing paths |
| **Routing** | Visual editor for `routing.yaml` rules |
| **Logs** | Browse and view RCA / incoming log files |
| **Reports** | 24h / 7d / 30d alert charts and per-alertname tables (from Redis stream) |

Changes are saved to the shared Redis store (hash `config:store`), mirrored to `config/web_config.json`, and applied to every running agent replica within seconds — no restart needed. Precedence: **UI-stored value > env var > built-in default** (env vars act as initial defaults; anything set from the UI wins until cleared).

MCP server URLs are **not** configurable — the MCP servers run inside the agent container on fixed localhost ports (8001-8004) and are shown as read-only status only.

**Auth:** set `ADMIN_TOKEN` to require `Authorization: Bearer <token>` on all `/api/*` endpoints. If unset, auth is skipped (dev mode).

### API Endpoints

```
GET/POST /api/config                  read / update config (sensitive keys masked)
GET      /api/config/mcp/health       health of the 4 MCP servers
GET      /api/config/services/health  health of Prometheus / Loki direct endpoints
GET/POST /api/config/routing          routing.yaml as JSON
GET      /api/metrics/stats           counters from Redis
GET      /api/reports/summary?days=7  aggregated alert history from Redis stream
GET      /api/logs, /api/logs/{name}  log file browser
GET      /api/redis/health            Redis availability
POST     /webhook/test                 synchronous RCA test (no Slack post)
POST     /webhook                      Alertmanager webhook intake
GET      /metrics                      Prometheus metrics scrape endpoint
```

---

## Persistence (Redis)

All runtime state lives in Redis (`redis_data` volume, AOF persistence) — it survives container restarts:

| Data | Mechanism |
|---|---|
| Dedup cache | `SET NX EX` per alert fingerprint (atomic, TTL = `DEDUP_TTL_SECONDS`) |
| Counters | `INCRBY` (`alerts_received`, `llm_success`, `slack_error`, …) |
| Per-alertname counts | `HINCRBY alertname:counts` |
| Alert event history | Redis Stream `stream:alerts` (capped at 50k events) — powers the Reports page |
| Runtime config | Hash `config:store` + version counter `config:version` |
| Routing rules | String `config:routing_yaml` (YAML text) |

Redis is a hard dependency at runtime — `docker compose` starts it automatically with a healthcheck before the agent.

---

## High Availability (multiple agent replicas)

The agent is HA-ready: run 2+ `alert-agent` replicas behind a load balancer with **one shared Redis**, and everything stays consistent.

```
                    ┌──────────────┐
   Web UI ────────► │ Load balancer│ ────► agent replica A ─┐
   Alertmanager ──► │              │ ────► agent replica B ─┤
                    └──────────────┘                        ▼
                                                     shared Redis
                                        (dedup, counters, config, pub/sub)
```

**Why it works:**

- **Dedup is atomic and shared** — `SET NX EX` in Redis means the same alert fingerprint is investigated exactly once, no matter which replica receives it.
- **Counters and reports are shared** — all replicas increment the same Redis keys, so the dashboard shows fleet-wide totals regardless of which replica serves the API request.
- **Config changes sync automatically** — every replica runs a background sync thread (`services/config_sync.py`):
  1. A config save (from the Web UI, hitting *any* replica) writes the Redis hash `config:store`, bumps `config:version`, and publishes to the `config:events` pub/sub channel.
  2. Every replica's sync thread receives the event and re-applies the shared config to its live process within ~1 second.
  3. A version poll every 30 s catches any pub/sub message missed during a Redis reconnect.
  4. On startup, a replica applies the stored config immediately — new or restarted replicas converge without intervention.
- **Routing rules sync the same way** — saved to `config:routing_yaml` in Redis and broadcast; each replica resets its routing cache on the event. The local `routing.yaml` file is only a fallback when Redis has no rules.
- **`web_config.json` is a seed/mirror** — it populates Redis on first boot (migration from single-node setups) and keeps local dev working; Redis is the source of truth once running.

If Redis is briefly unavailable, replicas keep serving with their last-applied config and reconnect automatically.

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

The file is **volume-mounted** in docker-compose for local dev. In Kubernetes the catalog ships in the container image at `/app/config/alert_catalog.yaml`. For zero-downtime routing updates, use the **Web UI** or `POST /api/config/routing` (Redis-backed hot-reload).

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

Most settings can be set from the Web UI (saved to Redis + `config/web_config.json`). Precedence: **UI-stored value > env var > built-in default** (env vars seed Redis on first boot; UI changes win until cleared).

| Variable | Default | Description |
|---|---|---|
| `AI_PROVIDER` | `openai` | `openai` \| `anthropic` \| `gemini` \| `bedrock` \| `fake` |
| `OPENAI_API_KEY` | _(required)_ | API key for the selected provider |
| `OPENAI_MODEL` | `gpt-4o` | Model name (interpreted per provider) |
| `OPENAI_MODEL_INFO` | `gpt-4o-mini` | Model for `info`-severity alerts (OpenAI provider only) |
| `SLACK_WEBHOOK_URL` | _(optional)_ | Fallback Slack webhook when no routing rule matches |
| `ROUTING_CONFIG_PATH` | _(optional)_ | Path to `routing.yaml` inside the container |
| `PROMETHEUS_URL` | cluster default | Prometheus base URL |
| `LOKI_URL` | cluster default | Loki base URL |
| `LOGS_DIR` | `/app/logs` | Directory for saved RCA log files |
| `DEDUP_TTL_SECONDS` | `900` | Ignore duplicate fingerprints for this many seconds |
| `ALLOWED_ALERTNAMES` | _(unset = all)_ | Regex filter — only process matching alert names |
| `LLM_ENABLED` | `true` | Set `false` to use deterministic RCA fallback only |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL (`redis://redis:6379/0` in compose) |
| `INVESTIGATION_MAX_WORKERS` | `8` | Max concurrent alert investigations |
| `RUNBOOK_BASE_URL` | `https://wiki.dozee.internal/runbooks` | Base URL for catalog runbook links |
| `ALERT_CATALOG_PATH` | `/app/config/alert_catalog.yaml` | Alert descriptions + runbooks |
| `RECURRENCE_LOOKBACK_DAYS` | `7` | Window for recurring-alert detection |
| `RECURRENCE_THRESHOLD` | `3` | Fires within window before flagging as recurring |
| `LOG_LEVEL` | `INFO` | JSON log level (`DEBUG`, `INFO`, `WARNING`, …) |
| `ADMIN_TOKEN` | _(unset = no auth)_ | Bearer token required by `/api/*` and the Web UI |
| `CONFIG_STORE_PATH` | `/app/config/web_config.json` | Where Web UI config is persisted |
| `NEXT_PUBLIC_API_URL` | `http://alert-agent:5001` | Backend URL used by the Web UI |

---

## Kubernetes Deployment

Manifests: [`deploy/k8s/ai-alert-agent.yaml`](deploy/k8s/ai-alert-agent.yaml) — includes the agent Deployment, logs PVC, **Redis Deployment + PVC**, and ClusterIP services.

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
| **Deduplication** | Same alert `fingerprint` is ignored for `DEDUP_TTL_SECONDS` (default 15 min) — stored in Redis, survives restarts |
| **Allowlist filter** | `ALLOWED_ALERTNAMES` regex — drop alerts not matching |
| **LLM fallback** | If OpenAI is unavailable, quota exceeded, or a transient error occurs (timeout, 5xx), falls back to a deterministic RCA using prefetched metrics |
| **Alert storm protection** | Bounded `ThreadPoolExecutor` (`INVESTIGATION_MAX_WORKERS`, default 8) instead of unbounded threads |
| **Recurring alerts** | Same fingerprint 3+ times in 7 days flagged in Slack header |
| **Runbook links** | Catalog entries include runbook URLs in the Slack header |
| **Cost optimization** | `info`-severity alerts use `gpt-4o-mini` (`OPENAI_MODEL_INFO`) |
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
PYTHONPATH=alert-agent .venv/bin/python -m pytest alert-agent/tests/ -v
```

---

## Project Structure

The backend follows an MVC layout:

```
ai-agents/
├── alert-agent/
│   ├── app.py                        # Flask app — wires blueprints + webhook route
│   ├── config.py                     # Environment variable config
│   ├── api/                          # REST API for the Web UI
│   │   ├── auth.py                   #   Bearer token auth (ADMIN_TOKEN)
│   │   ├── config_api.py             #   /api/config, MCP + service health, routing
│   │   ├── metrics_api.py            #   /api/metrics/stats, /api/reports/summary
│   │   └── logs_api.py               #   /api/logs browser
│   ├── controllers/
│   │   ├── webhook_controller.py     # Webhook intake, dedup, filtering
│   │   └── investigation_controller.py # RCA orchestration per alert
│   ├── models/
│   │   └── catalog.py                # Alert catalog (descriptions per alertname)
│   ├── services/
│   │   ├── classification/           # Alert type classification + context building
│   │   ├── llm/                      # PydanticAI agent, deterministic RCA fallback
│   │   ├── metrics/                  # Prometheus prefetch (pod/host/kafka metrics)
│   │   ├── notification/             # Slack client + routing.yaml engine
│   │   ├── store/redis_client.py     # Redis: dedup, counters, alert stream
│   │   └── config_store.py           # web_config.json read/write + live apply
│   ├── views/
│   │   ├── report_view.py            # RCA report + header formatting
│   │   └── slack_view.py             # Slack attachment layout
│   ├── utils/metrics.py              # Prometheus /metrics exposition
│   ├── tests/                        # pytest suite
│   ├── routing.yaml                  # Slack routing rules (edit this)
│   └── prompts/rca_prompt.txt        # LLM system prompt with tool hints
├── web/                              # Next.js 14 config dashboard
│   ├── app/                          #   dashboard, config/*, routing, logs, reports
│   ├── components/                   #   shell (top navbar), UI primitives
│   ├── lib/                          #   API client + shared types
│   └── Dockerfile                    #   multi-stage standalone build
├── mcp-servers/
│   ├── k8s-mcp/server.py             # Kubernetes MCP server
│   ├── prometheus-mcp/server.py      # Prometheus MCP server
│   ├── loki-mcp/server.py            # Loki MCP server
│   └── kafka-mcp/server.py           # Kafka/MSK MCP server
├── deploy/
│   ├── k8s/ai-alert-agent.yaml       # Kubernetes manifests
│   └── build-push.sh                 # ECR build + push script
├── config/                           # Volume-mounted: web_config.json lives here
├── sample/                           # Sample Alertmanager payloads for testing
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── start.sh                          # Container entrypoint
```

---

## Future Improvements

- **Multi-alert correlation** — group alerts firing on the same node/namespace into a single RCA
- **Confidence score** — LLM rates certainty (low/medium/high); low-confidence RCAs flagged in Slack
- **Grafana dashboard** — visualize `alerts_received`, `llm_investigations`, `slack_posts` with latency histograms
- **Helm chart** — package manifests with `routing.yaml` as a ConfigMap value for GitOps-native management
- **Slack slash commands** — `/rca replay <alert>` and `/rca status` from Slack
