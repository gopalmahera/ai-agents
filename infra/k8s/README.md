# DAI — Kubernetes manifests

Deploy [Dozee Alert Intelligence (DAI)](../../README.md) to Kubernetes.

| File | Resource |
|------|----------|
| `api.yaml` | `dai-api` Deployment + Service |
| `web.yaml` | `dai-web` Deployment + Service |
| `agent.yaml` | `dai-agent` Deployment + Service |
| `mongo.yaml` | `dai-mongo` StatefulSet + Service |
| `redis.yaml` | `dai-redis` Deployment + Service |

Create secrets:

```bash
kubectl -n monitoring create secret generic dai-secrets \
  --from-literal=admin-token='...' \
  --from-literal=mongo-url='mongodb://dai-mongo:27017'
```

Alertmanager webhook URL: `https://<dai-api-host>/api/v1/webhook/<env>`

Legacy monolithic manifest: [`deploy/k8s/ai-alert-agent.yaml`](../../deploy/k8s/ai-alert-agent.yaml)
