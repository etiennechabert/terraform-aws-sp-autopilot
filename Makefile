.PHONY: help lint lint-check format test coverage install-hooks

help:
	@echo "Available targets:"
	@echo "  lint         - Run linting and auto-fix issues"
	@echo "  lint-check   - Check linting without fixing (CI mode)"
	@echo "  format       - Format Python code with ruff"
	@echo "  test         - Run all tests"
	@echo "  coverage     - Run all tests with aggregated coverage report (opens in browser)"
	@echo "  install-hooks - Install git pre-commit hooks"

# Lint Python code and auto-fix issues
lint:
	@echo "Running ruff linter..."
	uvx ruff check --fix lambda/
	@echo "Running ruff formatter..."
	uvx ruff format lambda/
	@echo "✓ Linting complete"

# Check linting without modifying files (for CI)
lint-check:
	@echo "Checking ruff linter..."
	uvx ruff check lambda/
	@echo "Checking ruff formatter..."
	uvx ruff format --check lambda/
	@echo "✓ Lint check complete"

# Format Python code
format:
	@echo "Formatting Python code..."
	uvx ruff format lambda/
	@echo "✓ Formatting complete"

# Run all tests
test:
	@echo "Running scheduler tests..."
	cd lambda/scheduler && python3 -m pytest tests/ -v
	@echo "Running purchaser tests..."
	cd lambda/purchaser && python3 -m pytest tests/ -v
	@echo "Running reporter tests..."
	cd lambda/reporter && python3 -m pytest tests/ -v
	@echo "✓ All tests passed"

# Run all tests with aggregated coverage and open HTML report
# Usage: make coverage
# Requires: .venv with pytest and coverage installed
coverage:
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║      AGGREGATED COVERAGE: ALL LAMBDAS + SHARED MODULES     ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@if [ ! -d ".venv" ]; then \
		echo "❌ Error: .venv not found. Please create a virtual environment first."; \
		exit 1; \
	fi
	@rm -f .coverage .coverage.* 2>/dev/null || true
	@rm -rf htmlcov 2>/dev/null || true
	@echo "📊 [1/3] Running scheduler tests..."
	@cd lambda/scheduler && ../../.venv/bin/python -m pytest tests/ --cov=. --cov=../shared --cov-append --cov-report= --no-cov-on-fail -q || true
	@echo "📊 [2/3] Running purchaser tests..."
	@cd lambda/purchaser && ../../.venv/bin/python -m pytest tests/ --cov=. --cov=../shared --cov-append --cov-report= --no-cov-on-fail -q || true
	@echo "📊 [3/3] Running reporter tests..."
	@cd lambda/reporter && ../../.venv/bin/python -m pytest tests/ --cov=. --cov=../shared --cov-append --cov-report= --no-cov-on-fail -q || true
	@echo ""
	@echo "📈 Combining coverage data..."
	@.venv/bin/python -m coverage combine lambda/scheduler/.coverage lambda/purchaser/.coverage lambda/reporter/.coverage 2>/dev/null || true
	@.venv/bin/python -m coverage html --directory=htmlcov
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║                  COVERAGE SUMMARY BY MODULE                ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "🎯 SHARED MODULES (lambda/shared/):"
	@.venv/bin/python -m coverage report --include="lambda/shared/*" --skip-covered
	@echo ""
	@echo "🎯 SCHEDULER (lambda/scheduler/):"
	@.venv/bin/python -m coverage report --include="lambda/scheduler/*" --skip-covered
	@echo ""
	@echo "🎯 PURCHASER (lambda/purchaser/):"
	@.venv/bin/python -m coverage report --include="lambda/purchaser/*" --skip-covered
	@echo ""
	@echo "🎯 REPORTER (lambda/reporter/):"
	@.venv/bin/python -m coverage report --include="lambda/reporter/*" --skip-covered
	@echo ""
	@echo "╔════════════════════════════════════════════════════════════╗"
	@echo "║                      TOTAL COVERAGE                        ║"
	@echo "╚════════════════════════════════════════════════════════════╝"
	@.venv/bin/python -m coverage report --skip-covered
	@echo ""
	@echo "✨ Coverage report generated!"
	@echo "📁 HTML report: htmlcov/index.html"
	@echo "🌐 Opening in browser..."
	@open htmlcov/index.html || xdg-open htmlcov/index.html || echo "Please open htmlcov/index.html manually"

# Install git pre-commit hooks
install-hooks:
	@echo "Installing pre-commit hooks..."
	@mkdir -p .git/hooks
	@cp -f .github/hooks/pre-commit .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "✓ Pre-commit hooks installed"
	@echo ""
	@echo "The pre-commit hook will run 'make lint' before each commit."
	@echo "To skip the hook temporarily, use: git commit --no-verify"
