# AI Alert Agent — Web Config UI

Next.js 14 dashboard for configuring and monitoring the alert agent. Talks to the Flask backend's `/api/*` endpoints.

## Pages

| Route | Purpose |
|---|---|
| `/dashboard` | Stat cards, MCP server status, Redis status |
| `/config/ai` | AI provider, model, API key, LLM enable toggle |
| `/config/mcp` | Direct service endpoints (Prometheus, Loki) + MCP server URLs, health checks |
| `/config/storage` | Logs dir, dedup TTL, allowed alertnames, catalog/routing paths |
| `/routing` | Visual editor for `routing.yaml` Slack routing rules |
| `/logs` | Browse and view RCA / incoming log files |
| `/reports` | Alert charts and tables (24h / 7d / 30d) from Redis stream |

## Stack

- **Next.js 14** (App Router) + TypeScript
- **Tailwind CSS** (`darkMode: "class"`, slate palette, indigo primary `#4F46E5`)
- **TanStack Query v5** for server state
- **Recharts** for charts
- **lucide-react** icons

## Local Development

```bash
npm install
npm run dev          # http://localhost:3000
```

Environment variables (set at build time — `NEXT_PUBLIC_*` are inlined):

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:5001` | Flask backend base URL |
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
├── logs/             # log browser
└── reports/          # charts + tables
components/
├── shell/Shell.tsx   # Top navbar, config dropdown, mobile drawer, theme toggle
└── ui/               # shared primitives
lib/
├── api.ts            # fetch client (injects Authorization header)
└── types.ts          # API response types
```
