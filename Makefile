.PHONY: help setup test lint format clean run-scheduler run-purchaser run-reporter

.DEFAULT_GOAL := help

PYTHON := python
PYTEST := pytest

help: ## Show available commands
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

setup: ## Setup local environment (install deps, create .env.local)
	$(PYTHON) -m venv .venv
	.venv/bin/pip install -r requirements-dev.txt || .venv/Scripts/pip install -r requirements-dev.txt
	@if [ ! -f .env.local ]; then cp .env.local.example .env.local; fi
	@mkdir -p local_data/queue local_data/reports local_data/logs
	@echo "Setup complete. Activate venv: source .venv/bin/activate (Unix) or .venv\\Scripts\\activate (Windows)"

test: ## Run all tests
	$(PYTEST) tests -v

lint: ## Check code quality
	ruff check lambda/
	ruff format --check lambda/

format: ## Format code
	ruff format lambda/

clean: ## Clean generated files
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .pytest_cache htmlcov/ .coverage 2>/dev/null || true

run-scheduler: ## Run Scheduler Lambda locally (dry-run)
	$(PYTHON) local_runner.py scheduler --dry-run

run-purchaser: ## Run Purchaser Lambda locally
	$(PYTHON) local_runner.py purchaser

run-reporter: ## Run Reporter Lambda locally
	$(PYTHON) local_runner.py reporter --format html
