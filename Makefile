.PHONY: help install dev up down logs test clean fresh seed seed-reset seed-verify

help:
	@echo "Taxja - Austrian Tax Management System"
	@echo ""
	@echo "Available commands:"
	@echo "  make install    - Install dependencies"
	@echo "  make dev        - Start development environment"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo "  make logs       - View logs"
	@echo "  make test       - Run tests"
	@echo "  make clean      - Clean up containers and volumes"
	@echo "  make fresh      - Fresh DB: drop, recreate, init from init.sql"
	@echo "  make seed       - Run init.sql on existing DB (idempotent)"
	@echo "  make regen-init - Regenerate init.sql from current DB"

install:
	@echo "Installing backend dependencies..."
	cd backend && pip install -r requirements.txt
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

dev:
	@echo "Starting development environment..."
	docker-compose up -d postgres redis minio
	@echo "Services started. Run 'make logs' to view logs."

up:
	@echo "Starting all services..."
	docker-compose up -d
	@echo "All services started. Access:"
	@echo "  Frontend: http://localhost:5173"
	@echo "  Backend: http://localhost:8000"
	@echo "  API Docs: http://localhost:8000/docs"

down:
	@echo "Stopping all services..."
	docker-compose down

logs:
	docker-compose logs -f

test:
	@echo "Running backend tests..."
	cd backend && pytest
	@echo "Running frontend tests..."
	cd frontend && npm run test

clean:
	@echo "Cleaning up..."
	docker-compose down -v
	@echo "Cleanup complete."

fresh:
	@echo "Recreating database from scratch..."
	docker exec taxja-postgres psql -U taxja -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='taxja' AND pid <> pg_backend_pid();" || true
	docker exec taxja-postgres psql -U taxja -d postgres -c "DROP DATABASE IF EXISTS taxja;"
	docker exec taxja-postgres psql -U taxja -d postgres -c "CREATE DATABASE taxja OWNER taxja;"
	docker exec -i taxja-postgres psql -U taxja -d taxja < docker/init-db/init.sql
	@echo "Database recreated with schema + seed data."

seed:
	@echo "Running init.sql (seed data will be skipped if already exists)..."
	docker exec -i taxja-postgres psql -U taxja -d taxja < docker/init-db/init.sql
	@echo "Done."

regen-init:
	@echo "Regenerating init.sql from current database..."
	docker cp scripts/build_init_inside_container.sh taxja-postgres:/tmp/build_init.sh
	docker exec taxja-postgres sh /tmp/build_init.sh
	docker cp taxja-postgres:/tmp/init.sql docker/init-db/init.sql
	@echo "init.sql regenerated."
