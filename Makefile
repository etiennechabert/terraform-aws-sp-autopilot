.PHONY: help lint lint-check format test install-hooks

help:
	@echo "Available targets:"
	@echo "  lint         - Run linting and auto-fix issues"
	@echo "  lint-check   - Check linting without fixing (CI mode)"
	@echo "  format       - Format Python code with ruff"
	@echo "  test         - Run all tests"
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
