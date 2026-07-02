# AI Alert Agent — Project Summary for Management

**Project:** AI-Powered Alert Investigation Agent
**Team:** Platform / Infrastructure
**Last Updated:** July 2026

---

## What Is This System?

When a production alert fires (e.g. a pod is consuming too much memory, a server is down, Kafka is lagging), the on-call engineer currently has to manually log into Grafana, Kubernetes, and Loki to find the root cause — often taking 15–30 minutes per alert.

The **AI Alert Agent** automates this investigation. It receives the alert, queries all relevant systems in parallel using AI, and posts a structured Root Cause Analysis (RCA) directly to the team's Slack channel — in under 2 minutes.

---

## What We Built

### Core System

| Component | What It Does |
|---|---|
| **Webhook Server** | Receives alerts from Alertmanager (the Prometheus alerting system) |
| **AI Investigation Agent** | Configurable via `AI_PROVIDER` (openai / anthropic / gemini / bedrock); default model `gpt-4o`, `info`-severity alerts use `gpt-4o-mini` |
| **Kubernetes Tool (k8s-mcp)** | Queries pod status, events, logs, deployment state |
| **Prometheus Tool (prometheus-mcp)** | Queries CPU, memory, disk, network, probe, and node metrics |
| **Loki Tool (loki-mcp)** | Queries application and infrastructure logs |
| **Kafka Tool (kafka-mcp)** | Queries consumer lag, broker throughput, topic health |
| **Slack Reporter** | Posts formatted RCA with color-coded severity to the right channel |
| **Web Config Dashboard** | Next.js UI (port 3000) — config editor, routing, logs browser, reports, MCP/Redis health |

Locally, three services run via `docker compose`: **alert-agent** (5001), **redis** (6379), and **web** (3000). The alert-agent container embeds four MCP servers and is backed by Redis for dedup, counters, and shared config.

---

## What We Delivered (This Phase)

### 1. Alert Coverage — 155 Rules in Catalog

The repo ships `config/alert_catalog.yaml` with **155 alert entries**, each with:
- A one-line human-readable description
- A runbook URL shown in the Slack RCA header
- Pattern-based fallbacks for dynamic `msk.*` alert names not listed explicitly

**Catalog breakdown:**

| Bucket | Approx. count | Source |
|---|---|---|
| Static rules (K8s, EC2, probe, TLS, throughput) | ~55 | Built-in catalog in `alert-agent/models/catalog.py` |
| MSK-expanded (`msk.kb.*`, `msk.kbc.*`, nomessage) | ~100 | 20 topics × 5 patterns in `alert-agent/data/msk_topics.yaml` |
| **Total** | **155** | `config/alert_catalog.yaml` |

**Alert types now covered:**

| Category | Count | Example Alerts |
|---|---|---|
| Kubernetes pod | ~20 | CPU/memory limits, OOM kill, eviction, anomalies, restarts, network |
| EC2 host infrastructure | ~27 | Host down, out of memory, swap, disk latency, clock skew, temperature, RAID |
| Kafka / MSK | ~100 | Consumer lag, no messages, broker throughput (per-topic expansion) |
| Blackbox probes | 3 | HTTP probe down, high latency, TCP probe failed |
| TLS certificates | 1 | Certificate expiring soon |
| Loki (log-based) | Pattern | Log error-rate and pattern alerts (`loki.*`, `Loki*`) |

---

### 2. Slack Channel Routing

Previously all alerts went to a single Slack webhook. We added a **routing configuration** (`routing.yaml`) that lets the team direct alerts to different Slack channels based on alert labels — without touching code or rebuilding the container.

**Routing rules support:**
- Exact label match (e.g. `severity: critical` AND `stage: prod`)
- Regex label match (e.g. all `EC2Host*` alerts → `#infra-alerts`)
- First-match-wins ordering (same as Alertmanager)
- A default fallback channel

**To update routing:** use the Web UI, `POST /api/config/routing`, or edit `routing.yaml` — changes propagate without a container restart when using the API/Redis path.

---

### 3. Rich Slack RCA Format

Each investigation now produces a two-part Slack message:

**Header** (color-coded by severity — red for critical, yellow for warning):
- Alert name + severity
- Namespace / pod / region / started time
- One-line summary from Prometheus annotations
- Direct link to the Prometheus graph that triggered the alert
- Direct link to the alert runbook (when defined in the catalog)
- Recurring-alert flag when the same fingerprint fired 3+ times in 7 days

**Body:**
- Findings (bullet points of what the AI observed)
- Probable Root Cause
- Recommended Actions (numbered list)
- Auto-truncated if the report exceeds Slack's display limit

---

### 4. On-Call Test Endpoint

`POST /webhook/test` accepts a sample alert (full webhook payload or single alert object) and returns the generated RCA synchronously without posting to Slack — useful for validating investigations without waiting for a real incident.

---

### 5. Web Config Dashboard

Next.js dashboard (`web/`, port 3000) for configuring and monitoring the agent without editing env files:

| Page | Purpose |
|---|---|
| **Dashboard** | Stat cards (received / accepted / deduplicated / LLM outcomes), MCP + Redis health |
| **Config → AI Provider** | Provider, model, API key, LLM on/off |
| **Config → Service Endpoints** | Prometheus / Loki URLs with health checks |
| **Config → Storage** | Logs dir, dedup TTL, allowlist regex, catalog/routing paths |
| **Routing** | Visual editor for `routing.yaml` rules |
| **Logs** | Browse and view RCA / incoming log files |
| **Reports** | 24h / 7d / 30d alert charts from Redis stream (`/api/reports/summary`) |

Changes are saved to the shared Redis store, mirrored to `config/web_config.json`, and applied to every running agent replica within seconds via `config_sync.py` — no restart needed. Set `ADMIN_TOKEN` to require bearer auth on all `/api/*` endpoints.

---

### 6. New Diagnostic Tools

We added two new investigation tools to expand what the AI can query:

**`get_node_advanced` (Prometheus)** — fetches EC2 host signals in a single call:
swap usage, inode free space, disk read/write latency, failed systemd services, conntrack fill %, clock offset, hardware temperature, and RAID status.

**`get_broker_throughput` (Kafka)** — fetches bytes-in and bytes-out per second for a specific Kafka topic to investigate high-throughput alerts.

---

### 7. Reliability Improvements

| Improvement | Detail |
|---|---|
| **Metric prefetch** | Prometheus / K8s / Kafka metrics fetched before the LLM call to seed the investigation |
| **Deterministic fallback** | If OpenAI API is unavailable, quota exceeded, or a transient error occurs (timeout, 5xx), the agent falls back to a rule-based RCA using pre-fetched metrics — no silent failures |
| **Alert deduplication** | Same alert firing twice within 15 minutes is suppressed (configurable); backed by Redis so dedup survives container restarts |
| **Allowlist filter** | `ALLOWED_ALERTNAMES` regex skips alertnames that do not match |
| **Slack retry with backoff** | Failed Slack posts retry up to 3 times (2s → 4s → 8s delay) |
| **Body truncation** | RCA body capped at 3,800 characters with a truncation notice — prevents Slack API rejections |
| **k8s graceful degradation** | If no Kubernetes credentials are available (local dev), k8s tools return a clear error instead of crashing the container |
| **Alert storm protection** | Investigations run on a bounded `ThreadPoolExecutor` (default 8 workers) instead of unbounded threads |
| **Recurring alert detection** | Alerts with the same fingerprint 3+ times in 7 days are flagged in the Slack header |
| **Cost optimization** | `info`-severity alerts use `gpt-4o-mini` by default (`OPENAI_MODEL_INFO`) |
| **Structured JSON logs** | Webhook intake, investigation, config sync, and errors emit JSON logs to stdout |

---

### 8. Observability

The agent exposes Prometheus metrics at `/metrics` and a Web UI stats API at `/api/metrics/stats`:

| Metric | What It Measures |
|---|---|
| `alert_agent_alerts_received_total` | Total alerts received per alert name |
| `alert_agent_alerts_accepted_total` | Alerts that passed dedup and allowlist filters |
| `alert_agent_alerts_skipped_total` | Alerts skipped (non-firing status or allowlist filter) |
| `alert_agent_alerts_deduplicated_total` | Duplicate alerts suppressed |
| `alert_agent_llm_investigations_total` | LLM calls by outcome (success / fallback / error) |
| `alert_agent_slack_posts_total` | Slack posts by outcome (success / error) |

Redis also stores the same counters for the Web UI dashboard and HA replicas.

---

### 9. Test Coverage

96+ automated tests covering:
- Alert routing (match/regex/first-match/fallback)
- Slack formatting (header, body, truncation, color)
- Alert context classification (pod vs host vs Kafka vs probe vs loki)
- RCA formatting and deterministic fallback
- Webhook dedup and allowlist filtering
- Alert catalog (155 entries, runbook URLs, YAML overlay)
- Slack retry backoff
- Runbook + recurrence in report header
- Investigation worker pool (`ThreadPoolExecutor`)
- GPT-4o-mini model selection for `info` severity

---

## Deployment

| Environment | Status |
|---|---|
| Local (docker-compose) | Running — alert-agent (5001) + redis (6379) + web (3000) |
| Kubernetes (dozee-dev) | Manifests ready |
| Kubernetes (dozee-pro) | Manifests ready |

**Local:** `docker compose` runs three services. Logs saved to a mounted volume (`/app/logs`). Catalog ships at `/app/config/alert_catalog.yaml` (volume-mounted in compose, baked into the container image for K8s).

**Kubernetes:** `deploy/k8s/ai-alert-agent.yaml` includes the agent Deployment, logs PVC, **Redis Deployment + PVC + Service**, and `REDIS_URL` pointing at in-cluster Redis. No external queue.

**HA:** Run 2+ agent replicas behind a load balancer with one shared Redis. Dedup, counters, config, and routing sync across replicas via Redis pub/sub (`config_sync.py`). Routing and runtime settings can be updated via the Web UI or `POST /api/config/routing` without restarting containers.

---

## Future Improvements

The following improvements are recommended for the next phase, prioritized by business impact:

**Note:** Recurring alerts are partially addressed — fingerprint-based flag in the Slack header when the same alert fires 3+ times in 7 days. Full historical baseline comparison (e.g. metric vs 7-day average) remains future work.

### High Priority

| Improvement | Business Value |
|---|---|
| **Multi-alert correlation** | When 5 pods on the same node go down simultaneously, produce one grouped RCA instead of 5 separate ones |

### Medium Priority

| Improvement | Business Value |
|---|---|
| **Confidence score** | AI rates its certainty (Low / Medium / High) — low-confidence RCAs are flagged so engineers know to investigate manually |

### Lower Priority / Nice to Have

| Improvement | Business Value |
|---|---|
| **Grafana dashboard** | Visualize alert volume, LLM success rate, and Slack delivery reliability over time |
| **Helm chart** | Package as a Helm chart for GitOps-native deployment and easier version management across clusters |
| **Slack slash commands** | `/rca replay <alert>` — replay a past alert through the agent; `/rca status` — show current agent health from Slack |

---

## Cost Estimate (OpenAI)

Approximate per-investigation cost using GPT-4o:

| Alert type | Avg tokens (in + out) | Approx cost |
|---|---|---|
| Simple pod alert | ~4,000 | ~$0.02 |
| Complex EC2 host alert | ~8,000 | ~$0.04 |
| Kafka lag with logs | ~10,000 | ~$0.05 |

At 50 investigations/day: **~$1–2.50/day** depending on alert mix.
`info`-severity alerts use **gpt-4o-mini** (`OPENAI_MODEL_INFO`); critical and warning continue on `gpt-4o`, which can reduce overall cost for low-stakes alerts.

---

## Summary

| Area | Before | After |
|---|---|---|
| Alert investigation time | 15–30 min manual | < 2 min automated |
| Alert types covered | ~7 (basic pods only) | 155 catalog entries across 6 categories |
| Slack routing | Single channel | Per-channel by label rules |
| RCA quality | Manual, inconsistent | Structured, reproducible, severity-colored, runbook-linked |
| Reliability | No fallback | LLM fallback + retry + Redis-backed dedup + bounded worker pool |
| Observability | None | Prometheus `/metrics` + Web UI stats API + JSON logs |
| Operator UX | Env files only | Web UI + API config with hot-reload |
| Alert history | None | Redis stream + Reports page |
| Runbooks | Manual lookup | Linked in Slack header from catalog |
| Test coverage | 0 | 96+ automated tests |
| Config updates | Rebuild container | Web UI / API hot-reload via Redis |
