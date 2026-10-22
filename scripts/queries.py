"""Example analytical queries against data/clmta.duckdb."""

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "clmta.duckdb"


def main() -> None:
    if not DB_PATH.exists():
        raise SystemExit(f"database not found: {DB_PATH}; run `make db` first")

    con = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        print("=== 最近 3 个月全球温度 ===")
        print(
            con.execute(
                """
                SELECT date_int, anomaly
                FROM marts.monthly_anomaly
                WHERE series = 'land_ocean'
                ORDER BY obs_date DESC
                LIMIT 3
                """
            ).df()
        )

        print("\n=== 最热年份 Top 5（只统计 12 个月的完整年份）===")
        print(
            con.execute(
                """
                SELECT year, ROUND(AVG(anomaly), 2) AS avg_anomaly
                FROM marts.monthly_anomaly
                WHERE series = 'land_ocean'
                GROUP BY year
                HAVING COUNT(*) = 12
                ORDER BY avg_anomaly DESC
                LIMIT 5
                """
            ).df()
        )

        print("\n=== 2015-2024 年 陆地 vs 海洋 ===")
        print(
            con.execute(
                """
                SELECT series, ROUND(AVG(anomaly), 2) AS avg_anomaly
                FROM marts.monthly_anomaly
                WHERE year BETWEEN 2015 AND 2024
                  AND series IN ('land', 'ocean')
                GROUP BY series
                ORDER BY series
                """
            ).df()
        )
    finally:
        con.close()


if __name__ == "__main__":
    main()
