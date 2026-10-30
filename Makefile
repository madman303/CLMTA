.PHONY: test data db query analyze forecast pipeline

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

analyze:
	@echo "==> Running statistical analysis and figures..."
	uv run python scripts/analyze.py

forecast:
	@echo "==> Running one-step rolling-origin backtest..."
	uv run python scripts/forecast.py

pipeline: data db
	@echo "==> Data and warehouse are up to date."
