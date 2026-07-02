# DAI — Docker Compose

## Production

Built images, optimized for deployment (no source bind mounts):

```bash
cp ../../.env.example ../../.env
docker compose up --build
```

Or explicitly:

```bash
docker compose -f docker-compose.yml up --build
```

| Service | Port | Mode |
|---------|------|------|
| `api` | 4000 | `node dist/main.js` |
| `web` | 3000 | Next.js standalone |
| `agent` | 8080 (health) | `worker.py` + MCP |

## Development (hot reload)

Source is bind-mounted; services restart on file changes:

```bash
docker compose -f docker-compose.dev.yml up --build
```

| Service | Hot reload |
|---------|------------|
| **api** | `nest start --watch` — edits under `apps/api/src` |
| **web** | `next dev` — edits under `apps/web` |
| **agent** | `watchfiles` — edits under `apps/agent` |

Polling is enabled (`CHOKIDAR_USEPOLLING` / `WATCHPACK_POLLING`) for reliable reload on Docker Desktop (macOS/Windows).

### Dev volume layout

- `apps/api/src` → API container
- `packages/shared` → shared validators/types
- `apps/web` → web container (with preserved `node_modules` volume)
- `apps/agent` + `mcp-servers` → agent container

## Files

| File | Purpose |
|------|---------|
| `docker-compose.base.yml` | Mongo + Redis |
| `docker-compose.prod.yml` | Production app services |
| `docker-compose.dev.yml` | Development app services |

Root wrappers: `docker-compose.yml` (prod), `docker-compose.dev.yml` (dev).
