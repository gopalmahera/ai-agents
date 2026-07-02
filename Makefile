.PHONY: dev prod down logs

# Development — hot reload
dev:
	docker compose -f docker-compose.dev.yml up --build

# Production
prod:
	docker compose up --build

down:
	docker compose -f docker-compose.dev.yml down 2>/dev/null || true
	docker compose down

logs:
	docker compose -f docker-compose.dev.yml logs -f api web agent 2>/dev/null || docker compose logs -f api web agent
