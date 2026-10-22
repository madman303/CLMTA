"""Build the ClimateScope DuckDB warehouse: raw -> staging -> marts."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "clmta.duckdb"
SERIES_ORDER = ("land_ocean", "land", "ocean")
LEGACY_TABLES = (
    "main.staging_land_ocean",
    "main.staging_land",
    "main.staging_ocean",
    "main.mart_monthly_anomaly",
)


def _quote(value: str) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _load_metadata(data_dir: Path) -> tuple[str, dict[str, dict]]:
    path = data_dir / "metadata.json"
    if not path.exists():
        raise FileNotFoundError(f"metadata not found: {path}; run `make data` first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    series = payload.get("series")
    if not isinstance(series, dict) or not series:
        raise ValueError("metadata.json has no series")
    missing = [name for name in SERIES_ORDER if name not in series]
    if missing:
        raise ValueError(f"metadata.json is missing series: {missing}")
    return payload.get("updated_at", ""), series


def _build_raw(
    con: duckdb.DuckDBPyConnection,
    data_dir: Path,
    updated_at: str,
    series_meta: dict[str, dict],
) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS raw")
    con.execute(
        """
        CREATE OR REPLACE TABLE raw.series_metadata (
            series VARCHAR PRIMARY KEY,
            sha256 VARCHAR NOT NULL,
            row_count INTEGER NOT NULL,
            first_month VARCHAR NOT NULL,
            last_month VARCHAR NOT NULL,
            base_period VARCHAR NOT NULL,
            source_url VARCHAR NOT NULL,
            raw_file VARCHAR NOT NULL,
            updated_at VARCHAR
        )
        """
    )

    rows: list[list[object]] = []
    selects: list[str] = []
    for series in SERIES_ORDER:
        meta = series_meta[series]
        raw_file = meta["raw_file"]
        raw_path = data_dir / "raw" / raw_file
        if not raw_path.exists():
            raise FileNotFoundError(f"raw file not found: {raw_path}; run `make data` first")

        rows.append(
            [
                series,
                meta["sha256"],
                int(meta["rows"]),
                meta["first_month"],
                meta["last_month"],
                meta["base_period"],
                meta["source_url"],
                raw_file,
                updated_at,
            ]
        )
        selects.append(
            f"""
            SELECT
                {_quote(series)} AS series,
                CAST(Date AS INTEGER) AS date_int,
                CAST("Departure from Average" AS DOUBLE) AS anomaly,
                {_quote(raw_file)} AS source_file
            FROM read_csv({_quote(str(raw_path))}, comment='#', header=true)
            """
        )

    con.executemany(
        "INSERT INTO raw.series_metadata VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.execute(
        "CREATE OR REPLACE TABLE raw.observations AS " + " UNION ALL ".join(selects)
    )


def _build_staging(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS staging")
    con.execute(
        """
        CREATE OR REPLACE TABLE staging.observations AS
        SELECT
            series,
            date_int,
            CAST(strptime(CAST(date_int AS VARCHAR), '%Y%m') AS DATE) AS obs_date,
            anomaly,
            source_file
        FROM raw.observations
        """
    )


def _build_marts(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS marts")
    con.execute(
        """
        CREATE OR REPLACE TABLE marts.monthly_anomaly AS
        SELECT
            series,
            date_int,
            obs_date,
            CAST(strftime(obs_date, '%Y') AS INTEGER) AS year,
            CAST(strftime(obs_date, '%m') AS INTEGER) AS month,
            anomaly
        FROM staging.observations
        """
    )


def _check(con: duckdb.DuckDBPyConnection, series_meta: dict[str, dict]) -> None:
    expected_total = sum(int(meta["rows"]) for meta in series_meta.values())

    for table in ("raw.observations", "staging.observations", "marts.monthly_anomaly"):
        count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if count != expected_total:
            raise RuntimeError(f"{table}: expected {expected_total} rows, got {count}")

    for series in SERIES_ORDER:
        expected = int(series_meta[series]["rows"])
        for table in ("raw.observations", "staging.observations", "marts.monthly_anomaly"):
            count = con.execute(
                f"SELECT COUNT(*) FROM {table} WHERE series = ?", [series]
            ).fetchone()[0]
            if count != expected:
                raise RuntimeError(f"{table}/{series}: expected {expected}, got {count}")

    nulls = con.execute(
        """
        SELECT COUNT(*)
        FROM marts.monthly_anomaly
        WHERE anomaly IS NULL OR obs_date IS NULL
        """
    ).fetchone()[0]
    if nulls:
        raise RuntimeError(f"marts.monthly_anomaly contains {nulls} null rows")

    for series in SERIES_ORDER:
        first_date, last_date = con.execute(
            """
            SELECT MIN(obs_date), MAX(obs_date)
            FROM marts.monthly_anomaly
            WHERE series = ?
            """,
            [series],
        ).fetchone()
        meta = series_meta[series]
        if str(first_date) != f"{meta['first_month']}-01":
            raise RuntimeError(f"{series}: first date {first_date} != {meta['first_month']}")
        if str(last_date) != f"{meta['last_month']}-01":
            raise RuntimeError(f"{series}: last date {last_date} != {meta['last_month']}")


def build_database(
    db_path: Path = DB_PATH,
    data_dir: Path = DATA_DIR,
) -> Path:
    """Build the warehouse and return the database path."""
    db_path = Path(db_path)
    data_dir = Path(data_dir)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    updated_at, series_meta = _load_metadata(data_dir)
    con = duckdb.connect(str(db_path))
    try:
        con.execute("BEGIN TRANSACTION")
        for table in LEGACY_TABLES:
            con.execute(f"DROP TABLE IF EXISTS {table}")
        _build_raw(con, data_dir, updated_at, series_meta)
        _build_staging(con)
        _build_marts(con)
        _check(con, series_meta)
        con.execute("COMMIT")
    except Exception:
        try:
            con.execute("ROLLBACK")
        except Exception:
            pass
        raise
    finally:
        con.close()

    total = sum(int(meta["rows"]) for meta in series_meta.values())
    print(
        f"✅ 数仓构建完成：{len(SERIES_ORDER)} 条序列，"
        f"raw / staging / marts 各 {total} 行"
    )
    return db_path


if __name__ == "__main__":
    build_database()
