.PHONY: help install dev up down logs test clean

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
