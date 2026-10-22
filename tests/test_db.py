import json
from pathlib import Path

import duckdb
from scripts.build_db import build_database

ROOT = Path(__file__).resolve().parents[1]


def test_build_database(tmp_path):
    data_dir = ROOT / "data"
    db_path = tmp_path / "clmta.duckdb"
    build_database(db_path=db_path, data_dir=data_dir)

    meta = json.loads((data_dir / "metadata.json").read_text(encoding="utf-8"))
    expected_total = sum(int(item["rows"]) for item in meta["series"].values())

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        schemas = {
            row[0]
            for row in con.execute(
                "SELECT schema_name FROM information_schema.schemata"
            ).fetchall()
        }
        assert {"raw", "staging", "marts"} <= schemas

        assert (
            con.execute("SELECT COUNT(*) FROM raw.series_metadata").fetchone()[0]
            == len(meta["series"])
        )

        for table in ("raw.observations", "staging.observations", "marts.monthly_anomaly"):
            count = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            assert count == expected_total

        assert (
            con.execute(
                "SELECT COUNT(DISTINCT series) FROM marts.monthly_anomaly"
            ).fetchone()[0]
            == len(meta["series"])
        )

        assert (
            con.execute(
                """
                SELECT COUNT(*)
                FROM marts.monthly_anomaly
                WHERE anomaly IS NULL OR obs_date IS NULL
                """
            ).fetchone()[0]
            == 0
        )

        for series, item in meta["series"].items():
            count, first_date, last_date = con.execute(
                """
                SELECT COUNT(*), MIN(obs_date), MAX(obs_date)
                FROM marts.monthly_anomaly
                WHERE series = ?
                """,
                [series],
            ).fetchone()
            assert count == int(item["rows"])
            assert str(first_date) == f"{item['first_month']}-01"
            assert str(last_date) == f"{item['last_month']}-01"
    finally:
        con.close()
