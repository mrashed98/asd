.PHONY: help build up down logs restart clean

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build all Docker images
	docker-compose build

up: ## Start all services
	docker-compose up -d

down: ## Stop all services
	docker-compose down

logs: ## Show logs from all services
	docker-compose logs -f

restart: ## Restart all services
	docker-compose restart

clean: ## Stop and remove all containers, networks, and volumes
	docker-compose down -v

backend-shell: ## Open shell in backend container
	docker-compose exec backend /bin/sh

frontend-shell: ## Open shell in frontend container
	docker-compose exec frontend /bin/sh

redis-cli: ## Open Redis CLI
	docker-compose exec redis redis-cli

check-episodes: ## Manually trigger episode check
	curl -X POST http://localhost:8001/api/tasks/check-new-episodes

sync-downloads: ## Manually trigger download sync
	curl -X POST http://localhost:8001/api/tasks/sync-downloads

test-jdownloader: ## Test JDownloader connection
	curl -X POST http://localhost:8001/api/settings/jdownloader/test

status: ## Show status of all services
	docker-compose ps

init: ## Initialize project (create directories and .env)
	mkdir -p downloads media/english-series media/arabic-series media/movies data
	[ ! -f .env ] && cp .env.example .env || true
	@echo "Project initialized! Edit .env file and run 'make up'"

