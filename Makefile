.PHONY: test data

test:
	@echo "==> Checking code style (Ruff)..."
	uv run ruff check .
	@echo "==> Running tests (Pytest)..."
	uv run pytest

data:
	@echo "==> Data script placeholder"
