.PHONY: help setup test lint format docker-up docker-down docker-logs clean

help:
	@echo "TravelOps AI Platform Commands:"
	@echo "  make setup       Install backend dependencies and pre-commit hooks"
	@echo "  make test        Run test suite with pytest"
	@echo "  make lint        Run linting checks (ruff, mypy)"
	@echo "  make format      Format code with ruff"
	@echo "  make docker-up   Start all Docker Compose services"
	@echo "  make docker-down Stop all Docker Compose services"
	@echo "  make docker-logs View logs of running services"
	@echo "  make clean       Clean temporary files and caches"

setup:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev,ml,rag,agents]"
	pre-commit install

test:
	pytest backend/tests -v --cov=backend/app --cov-report=term-missing

lint:
	ruff check backend/
	mypy backend/app

format:
	ruff format backend/
	ruff check --fix backend/

docker-up:
	docker compose up -d --build

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
