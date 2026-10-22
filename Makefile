.PHONY: test data db query pipeline

test:
	@echo "==> Checking code style (Ruff)..."
	uv run ruff check .
	@echo "==> Running tests (Pytest)..."
	uv run pytest

data:
	@echo "==> Updating NOAA CAG data..."
	uv run python scripts/update_data.py

db:
	@echo "==> Building DuckDB warehouse (raw -> staging -> marts)..."
	uv run python scripts/build_db.py

query:
	@echo "==> Running example queries..."
	uv run python scripts/queries.py

pipeline: data db
	@echo "==> Data and warehouse are up to date."
