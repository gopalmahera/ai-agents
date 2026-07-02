# AI Alert Agent — Web Config UI

Next.js 14 dashboard for configuring and monitoring the alert agent. Talks to the Flask backend's `/api/*` endpoints.

## Pages

| Route | Purpose |
|---|---|
| `/dashboard` | Stat cards, MCP server status, Redis status |
| `/config/ai` | AI provider, model, API key, LLM enable toggle |
| `/config/mcp` | Direct service endpoints (Prometheus, Loki) + MCP server URLs, health checks |
| `/config/storage` | Logs dir, dedup TTL, allowed alertnames, catalog/routing paths |
| `/routing` | Visual editor for `routing.yaml` Slack routing rules (with mute time intervals per rule) |
| `/time-intervals` | Named schedules for routing mute windows (weekdays, times, timezone) |
| `/silences` | Active/disabled silence rules — skip LLM + Slack for matching alerts |
| `/logs` | Browse and view RCA / incoming log files |
| `/reports` | Alert charts and tables (24h / 7d / 30d) from Redis stream |

## Stack

- **Next.js 14** (App Router) + TypeScript
- **Tailwind CSS** (`darkMode: "class"`, slate palette, indigo primary `#4F46E5`)
- **TanStack Query v5** for server state
- **Recharts** for charts
- **lucide-react** icons
- **js-yaml** for YAML preview on routing, time intervals, and silences pages

## Local Development

```bash
cp .env.local.example .env.local   # API_URL=http://localhost:8080
npm install
npm run dev          # http://localhost:3000
```

| Variable | Default | Description |
|---|---|---|
| `API_URL` | `http://localhost:8080` | Flask backend for Next.js `/api/*` proxy (see `next.config.mjs`) |
| `NEXT_PUBLIC_API_URL` | _(empty)_ | Leave empty to use the proxy; set `http://localhost:8080` to call Flask directly from the browser |
| `NEXT_PUBLIC_ADMIN_TOKEN` | _(empty)_ | Bearer token sent to `/api/*` (must match backend `ADMIN_TOKEN`) |

## Docker

Multi-stage build ([Dockerfile](Dockerfile)) using Next.js `output: "standalone"`. Built and run automatically as the `web` service in the root `docker-compose.yml`:

```bash
docker compose up --build web
```

## Layout

```
app/
├── layout.tsx        # Root layout — Providers + Shell
├── providers.tsx     # TanStack Query client
├── dashboard/        # Stat cards + health
├── config/           # ai / mcp / storage pages
├── routing/          # routing.yaml editor
├── time-intervals/   # time_intervals.yaml editor
├── silences/         # silences.yaml editor
├── logs/             # log browser
└── reports/          # charts + tables
components/
├── shell/Shell.tsx   # Top navbar, config dropdown, mobile drawer, theme toggle
└── ui/               # shared primitives
lib/
├── api.ts            # fetch client (injects Authorization header)
├── routing-validation.ts
├── routing-yaml.ts
├── time-intervals-validation.ts
├── time-intervals-yaml.ts
├── silences-validation.ts
├── silences-yaml.ts
└── types.ts          # API response types
```

## Related API Endpoints

| Endpoint | Purpose |
|---|---|
| `GET/POST /api/config/routing` | Routing rules |
| `GET/POST /api/config/time-intervals` | Named time intervals |
| `GET/POST /api/config/mute` | Silences (active + disabled) |
| `POST /api/config/mute/silences/{id}/disable` | Manually disable a silence |
| `POST /api/config/mute/silences/{id}/enable` | Re-enable from disabled list |
