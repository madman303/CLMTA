.PHONY: test data

test:
	@echo "==> Checking code style (Ruff)..."
	uv run ruff check .
	@echo "==> Running tests (Pytest)..."
	uv run pytest

data:
	@echo "==> Updating NOAA CAG data..."
	uv run python scripts/update_data.py
