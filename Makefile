.PHONY: help install install-dev test test-coverage test-unit test-integration lint format check clean run-scheduler run-purchaser run-reporter setup-local purge-queue list-reports

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python
PIP := pip
PYTEST := pytest
BLACK := black
FLAKE8 := flake8
MYPY := mypy

# Directories
LAMBDA_DIR := lambda
TEST_DIR := tests
LOCAL_DATA_DIR := local_data

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

help: ## Show this help message
	@echo "$(BLUE)AWS Savings Plans Autopilot - Development Makefile$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(GREEN)Examples:$(NC)"
	@echo "  make install-dev           # Install all dependencies"
	@echo "  make test                  # Run all tests"
	@echo "  make run-scheduler         # Run scheduler locally"
	@echo "  make lint                  # Check code quality"
	@echo "  make format                # Format code"

# Installation targets
venv: ## Create a Python virtual environment
	@if [ ! -d .venv ]; then \
		echo "$(BLUE)Creating virtual environment...$(NC)"; \
		$(PYTHON) -m venv .venv; \
		echo "$(GREEN)✓ Virtual environment created at .venv$(NC)"; \
		echo "$(YELLOW)Activate with: source .venv/bin/activate (Unix) or .venv\\Scripts\\activate (Windows)$(NC)"; \
	else \
		echo "$(YELLOW)Virtual environment already exists at .venv$(NC)"; \
	fi

install: ## Install production dependencies
	$(PIP) install -r lambda/scheduler/requirements.txt
	$(PIP) install -r lambda/purchaser/requirements.txt
	$(PIP) install -r lambda/reporter/requirements.txt

install-dev: ## Install development dependencies
	$(PIP) install -r requirements-dev.txt
	@echo "$(GREEN)✓ Development dependencies installed$(NC)"
	@if [ ! -f .env.local ]; then \
		echo "$(YELLOW)Creating .env.local from example...$(NC)"; \
		cp .env.local.example .env.local; \
		echo "$(YELLOW)⚠ Please edit .env.local with your AWS credentials$(NC)"; \
	fi

setup-local: install-dev ## Setup local development environment
	@mkdir -p $(LOCAL_DATA_DIR)/queue
	@mkdir -p $(LOCAL_DATA_DIR)/reports
	@mkdir -p $(LOCAL_DATA_DIR)/logs
	@echo "$(GREEN)✓ Local data directories created$(NC)"
	@echo "$(GREEN)✓ Local development environment ready$(NC)"

setup-venv: venv install-dev ## Create venv and install dev dependencies
	@echo "$(GREEN)✓ Virtual environment setup complete$(NC)"
	@echo "$(YELLOW)Activate with: source .venv/bin/activate (Unix) or .venv\\Scripts\\activate (Windows)$(NC)"

# Testing targets
test: ## Run all tests
	$(PYTEST) $(TEST_DIR) -v

test-unit: ## Run unit tests only
	$(PYTEST) $(TEST_DIR)/test_local_mode.py -v

test-integration: ## Run integration tests only
	$(PYTEST) $(TEST_DIR)/test_local_runner.py -v

test-coverage: ## Run tests with coverage report
	$(PYTEST) $(TEST_DIR) --cov=$(LAMBDA_DIR) --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ Coverage report generated in htmlcov/index.html$(NC)"

test-watch: ## Run tests in watch mode (requires pytest-watch)
	ptw $(TEST_DIR) -- -v

# Code quality targets
lint: ## Run all linters
	@echo "$(BLUE)Running flake8...$(NC)"
	$(FLAKE8) $(LAMBDA_DIR) --max-line-length=120 --exclude=__pycache__,*.pyc,*.zip
	@echo "$(BLUE)Running mypy...$(NC)"
	$(MYPY) $(LAMBDA_DIR)/shared --ignore-missing-imports
	@echo "$(GREEN)✓ Linting passed$(NC)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code with black...$(NC)"
	$(BLACK) $(LAMBDA_DIR) $(TEST_DIR) local_runner.py --line-length=100
	@echo "$(GREEN)✓ Code formatted$(NC)"

check: ## Check code formatting without making changes
	$(BLACK) $(LAMBDA_DIR) $(TEST_DIR) local_runner.py --check --line-length=100

# Local execution targets
run-scheduler: ## Run Scheduler Lambda locally (dry-run mode)
	@echo "$(BLUE)Running Scheduler Lambda in local mode...$(NC)"
	$(PYTHON) local_runner.py scheduler --dry-run

run-scheduler-real: ## Run Scheduler Lambda locally (real queueing)
	@echo "$(RED)⚠ Running Scheduler Lambda in REAL mode (will queue intents)$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		LOCAL_MODE=true DRY_RUN=false $(PYTHON) local_runner.py scheduler; \
	fi

run-purchaser: ## Run Purchaser Lambda locally
	@echo "$(BLUE)Running Purchaser Lambda in local mode...$(NC)"
	$(PYTHON) local_runner.py purchaser

run-reporter: ## Run Reporter Lambda locally (HTML format)
	@echo "$(BLUE)Running Reporter Lambda in local mode...$(NC)"
	$(PYTHON) local_runner.py reporter --format html

run-reporter-json: ## Run Reporter Lambda locally (JSON format)
	@echo "$(BLUE)Running Reporter Lambda in local mode (JSON)...$(NC)"
	$(PYTHON) local_runner.py reporter --format json

run-all: run-scheduler run-purchaser run-reporter ## Run all Lambdas in sequence

# Local data management targets
purge-queue: ## Delete all messages from local queue
	@echo "$(YELLOW)Purging local queue...$(NC)"
	@rm -f $(LOCAL_DATA_DIR)/queue/*.json
	@echo "$(GREEN)✓ Queue purged$(NC)"

list-queue: ## List messages in local queue
	@echo "$(BLUE)Messages in local queue:$(NC)"
	@ls -lh $(LOCAL_DATA_DIR)/queue/*.json 2>/dev/null || echo "No messages in queue"

show-queue: ## Show content of queue messages
	@echo "$(BLUE)Queue message contents:$(NC)"
	@for file in $(LOCAL_DATA_DIR)/queue/*.json; do \
		if [ -f "$$file" ]; then \
			echo "$(YELLOW)$$file:$(NC)"; \
			cat "$$file" | $(PYTHON) -m json.tool; \
			echo ""; \
		fi \
	done

list-reports: ## List generated reports
	@echo "$(BLUE)Generated reports:$(NC)"
	@ls -lhtr $(LOCAL_DATA_DIR)/reports/*.html $(LOCAL_DATA_DIR)/reports/*.json 2>/dev/null | grep -v ".meta.json" || echo "No reports found"

show-latest-report: ## Open the latest report in browser
	@latest=$$(ls -t $(LOCAL_DATA_DIR)/reports/*.html 2>/dev/null | head -1); \
	if [ -n "$$latest" ]; then \
		echo "$(GREEN)Opening $$latest$(NC)"; \
		if command -v xdg-open > /dev/null; then \
			xdg-open "$$latest"; \
		elif command -v open > /dev/null; then \
			open "$$latest"; \
		elif command -v start > /dev/null; then \
			start "$$latest"; \
		else \
			echo "$(YELLOW)Please open manually: $$latest$(NC)"; \
		fi \
	else \
		echo "$(RED)No reports found$(NC)"; \
	fi

clean: ## Clean up generated files and caches
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@find . -type f -name "*.pyo" -delete 2>/dev/null || true
	@find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@rm -rf .pytest_cache .mypy_cache .coverage htmlcov/ 2>/dev/null || true
	@rm -f scheduler.zip purchaser.zip reporter.zip 2>/dev/null || true
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

clean-local: ## Clean local data directory
	@echo "$(RED)⚠ This will delete all local queue messages and reports$(NC)"
	@read -p "Are you sure? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		rm -rf $(LOCAL_DATA_DIR)/*; \
		mkdir -p $(LOCAL_DATA_DIR)/queue $(LOCAL_DATA_DIR)/reports $(LOCAL_DATA_DIR)/logs; \
		echo "$(GREEN)✓ Local data cleaned$(NC)"; \
	fi

# Package targets
package: ## Package Lambda functions (for manual deployment)
	@echo "$(BLUE)Packaging Lambda functions...$(NC)"
	@cd lambda/scheduler && zip -r ../../scheduler.zip . -x "*.pyc" -x "__pycache__/*"
	@cd lambda/purchaser && zip -r ../../purchaser.zip . -x "*.pyc" -x "__pycache__/*"
	@cd lambda/reporter && zip -r ../../reporter.zip . -x "*.pyc" -x "__pycache__/*"
	@echo "$(GREEN)✓ Lambda packages created$(NC)"

# Development workflow targets
dev: setup-local test lint ## Complete development setup and checks
	@echo "$(GREEN)✓ Development environment ready and validated$(NC)"

ci: test lint ## Run CI checks (tests + linting)
	@echo "$(GREEN)✓ CI checks passed$(NC)"

# Pre-commit checks
pre-commit: format test lint ## Run pre-commit checks
	@echo "$(GREEN)✓ Pre-commit checks passed$(NC)"

# Debugging targets
debug-scheduler: ## Run scheduler with debug logging
	LOG_LEVEL=DEBUG $(PYTHON) local_runner.py scheduler --dry-run

debug-purchaser: ## Run purchaser with debug logging
	LOG_LEVEL=DEBUG $(PYTHON) local_runner.py purchaser

debug-reporter: ## Run reporter with debug logging
	LOG_LEVEL=DEBUG $(PYTHON) local_runner.py reporter --format html

# Info targets
info: ## Show environment information
	@echo "$(BLUE)Environment Information:$(NC)"
	@echo "Python version: $$($(PYTHON) --version)"
	@echo "Pip version: $$($(PIP) --version)"
	@echo "LOCAL_MODE: $${LOCAL_MODE:-not set}"
	@echo "LOCAL_DATA_DIR: $${LOCAL_DATA_DIR:-./local_data}"
	@echo "AWS_PROFILE: $${AWS_PROFILE:-not set}"
	@echo "AWS_REGION: $${AWS_REGION:-not set}"
	@echo ""
	@echo "$(BLUE)Local Data:$(NC)"
	@echo "Queue messages: $$(ls -1 $(LOCAL_DATA_DIR)/queue/*.json 2>/dev/null | wc -l)"
	@echo "Reports: $$(ls -1 $(LOCAL_DATA_DIR)/reports/*.html $(LOCAL_DATA_DIR)/reports/*.json 2>/dev/null | grep -v ".meta.json" | wc -l)"

check-env: ## Check if .env.local is configured
	@if [ ! -f .env.local ]; then \
		echo "$(RED)✗ .env.local not found$(NC)"; \
		echo "$(YELLOW)Run: make setup-local$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ .env.local exists$(NC)"; \
		if grep -q "your-aws-profile-name" .env.local; then \
			echo "$(YELLOW)⚠ Please configure AWS credentials in .env.local$(NC)"; \
		else \
			echo "$(GREEN)✓ .env.local appears configured$(NC)"; \
		fi \
	fi
