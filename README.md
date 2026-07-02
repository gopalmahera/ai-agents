# Dozee Alert Intelligence (DAI)

**DAI** is Dozee's AI-powered alert investigation platform. It receives Alertmanager webhooks, investigates firing alerts using live data from Kubernetes, Prometheus, Loki, Kafka, and CloudWatch, then posts a structured Root Cause Analysis (RCA) to the right Slack channel.

## Architecture

| Part | Path | Role |
|------|------|------|
| **Web** | `apps/web` | Next.js admin UI only |
| **API** | `apps/api` | NestJS — settings, webhooks, BullMQ, Socket.IO gateway |
| **Agent** | `apps/agent` | Python worker — outbound WebSocket to API, embedded MCP, LLM investigations |
| **Mongo** | `infra/k8s/mongo.yaml` | Settings + alert event history |
| **Redis** | `infra/k8s/redis.yaml` | Dedup, counters, BullMQ, Socket.IO adapter |

```
Alertmanager → POST /api/v1/webhook/:env (DAI API)
                    → Redis dedup + BullMQ queue
                    → Socket.IO → DAI agent (investigate_alert + MCP)
                    → Slack + Mongo event history

Admin UI → REST /api/v1/settings/* → Mongo
        → config.updated → connected agents refresh cache
```

## Quick start (local)

```bash
cp .env.example .env
# Set OPENAI_API_KEY, SLACK_WEBHOOK_URL, PROMETHEUS_URL, LOKI_URL, ADMIN_TOKEN

docker compose up --build
```

| Service | URL |
|---------|-----|
| Web UI | http://localhost:3000 |
| API | http://localhost:4000 |
| Agent health | http://localhost:8080/health |
| Alertmanager webhook | `POST http://localhost:4000/api/v1/webhook/<env>` |

### Verify

```bash
curl http://localhost:4000/api/v1/health
curl -X POST http://localhost:4000/api/v1/webhook \
  -H "Content-Type: application/json" \
  -d @sample/network-pod-high-transmit-alert.json
curl http://localhost:8080/health
```

## Repository layout

```
├── apps/web/          # Next.js UI
├── apps/api/          # NestJS API
├── apps/agent/        # Python investigation worker
├── mcp-servers/       # Embedded MCP tools
├── config/            # Seed YAML for Mongo bootstrap
├── infra/docker/      # docker compose
├── infra/k8s/         # dai-api, dai-web, dai-agent, mongo, redis
├── packages/shared/   # Shared TS types + validators
└── Dockerfile.agent
```

## Web UI

| Page | Purpose |
|------|---------|
| **Dashboard** | Counters, MCP health, Redis/Mongo status |
| **Settings → Endpoints** | Named Prometheus / Loki / K8s / AWS endpoints |
| **Settings → Environments** | Per-env endpoint mapping + webhook path |
| **Routing** | Slack channel rules |
| **Time Intervals** | Route mute windows |
| **Silences** | Skip LLM + Slack for matching alerts |
| **Config → AI Provider** | LLM provider credentials |
| **Logs / Reports** | RCA files and alert analytics |

Settings live in **MongoDB**. Changes push `config.updated` to agents via Socket.IO.

## API surface

**v1:** `/api/v1/settings/*`, `/api/v1/webhook/:env`, `/api/v1/metrics/*`, `/api/v1/logs/*`, `/api/v1/reports/*`, `/api/v1/health/*`

**Legacy:** `/api/config/*` (bulk save during migration)

## Agent worker

1. Starts MCP servers on localhost 8001–8005
2. Connects outbound to `API_WS_URL` (`/agents` namespace)
3. Runs `investigate_alert` on `investigate` jobs
4. Returns `job.result` to the API

## Kubernetes

Manifests: [`infra/k8s/`](infra/k8s/) — `dai-api`, `dai-web`, `dai-agent`, `dai-mongo`, `dai-redis`

```bash
kubectl -n monitoring create secret generic dai-secrets \
  --from-literal=admin-token='...' \
  --from-literal=mongo-url='mongodb://dai-mongo:27017'
```

## Development

```bash
cd apps/api && npm run start:dev
cd apps/web && npm run dev
PYTHONPATH=apps/agent python3 -m pytest apps/agent/tests/ -v
```

## Build agent image

```bash
IMAGE=dai-agent ./deploy/build-push.sh
```

See [`.env.example`](.env.example) for all environment variables.
