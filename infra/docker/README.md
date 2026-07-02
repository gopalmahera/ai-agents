# DAI — Docker Compose

Local stack for [Dozee Alert Intelligence (DAI)](../../README.md).

```bash
cp ../../.env.example ../../.env
docker compose -f docker-compose.yml up --build
```

| Service | Port | Image |
|---------|------|-------|
| `api` | 4000 | `apps/api` |
| `web` | 3000 | `apps/web` |
| `agent` | 8080 (health) | `Dockerfile.agent` |
| `mongo` | 27017 | `mongo:7` |
| `redis` | 6379 | `redis:7-alpine` |

From repo root: `docker compose up` (uses root wrapper).
