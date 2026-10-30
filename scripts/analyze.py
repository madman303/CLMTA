"""Run ClimateScope anomaly analyses and save the resulting figures."""

from __future__ import annotations

from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import pandas as pd
import ruptures as rpt
import seaborn as sns
from scipy.stats import kendalltau
from statsmodels.tsa.seasonal import STL

DB_PATH = Path("data/clmta.duckdb")
OUTPUT_DIR = Path("outputs/figures")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def get_data(region: str) -> pd.DataFrame:
    """Read one region from the DuckDB mart and return typed observations."""
    connection = duckdb.connect(str(DB_PATH), read_only=True)
    try:
        tables = connection.execute(
            """
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('main', 'marts')
            """
        ).fetchall()
        table_names = {(schema, name) for schema, name in tables}

        if ("main", "mart_monthly_anomaly") in table_names:
            query = """
                SELECT obs_date, year, month, "Anomaly"
                FROM mart_monthly_anomaly
                WHERE region = ?
                ORDER BY obs_date
            """
            parameters = [region]
        elif ("marts", "monthly_anomaly") in table_names:
            query = """
                SELECT obs_date, year, month, anomaly AS "Anomaly"
                FROM marts.monthly_anomaly
                WHERE series = ?
                ORDER BY obs_date
            """
            parameters = [region.lower()]
        else:
            raise RuntimeError(
                "Could not find mart_monthly_anomaly or marts.monthly_anomaly"
            )

        frame = connection.execute(query, parameters).df()
    finally:
        connection.close()

    frame["obs_date"] = pd.to_datetime(frame["obs_date"])
    return frame


def task1_stl_decomposition(df: pd.DataFrame) -> None:
    """Decompose the anomaly series into original, trend, seasonal, and residual."""
    print("==> 1. 正在做 STL 分解...")
    indexed = df.set_index("obs_date")
    result = STL(indexed["Anomaly"], period=12, robust=True).fit()
    figure, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)

    axes[0].plot(indexed.index, indexed["Anomaly"], color="black")
    axes[0].set_ylabel("Original")
    axes[1].plot(indexed.index, result.trend, color="red")
    axes[1].set_ylabel("Trend")
    axes[2].plot(indexed.index, result.seasonal, color="green")
    axes[2].set_ylabel("Seasonal")
    axes[3].plot(indexed.index, result.resid, color="blue")
    axes[3].set_ylabel("Residual")

    figure.suptitle("STL Decomposition of Global Land-Ocean Temperature Anomaly")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "stl_decomposition.png", dpi=300)
    plt.close(figure)


def task2_trend_test(df: pd.DataFrame) -> None:
    """Run and print a Kendall rank correlation trend test."""
    print("==> 2. 正在做 Mann-Kendall 趋势检验...")
    tau, p_value = kendalltau(range(len(df)), df["Anomaly"])
    print(f"Kendall's tau: {tau:.4f}")
    print(f"P-value: {p_value:.4e}")
    if p_value < 0.05:
        print("✅ 存在显著上升趋势")


def task3_change_point(df: pd.DataFrame) -> None:
    """Find change points in annual mean anomaly values."""
    print("==> 3. 正在做变点检测...")
    annual = df.groupby("year", as_index=False)["Anomaly"].mean()
    values = annual["Anomaly"].to_numpy().reshape(-1, 1)
    breakpoints = rpt.Pelt(model="rbf").fit(values).predict(pen=10)

    for breakpoint in breakpoints[:-1]:
        if breakpoint < len(annual):
            year = int(annual.iloc[breakpoint]["year"])
            print(f"突变发生的年份：{year}")


def task4_heatmap(df: pd.DataFrame) -> None:
    """Plot mean monthly anomalies grouped by decade."""
    print("==> 4. 正在画月度热力图...")
    heatmap_data = df.copy()
    heatmap_data["decade"] = (heatmap_data["year"] // 10) * 10
    pivot = heatmap_data.pivot_table(
        index="decade",
        columns="month",
        values="Anomaly",
        aggfunc="mean",
    )

    figure, axis = plt.subplots(figsize=(10, 8))
    sns.heatmap(
        pivot,
        ax=axis,
        cmap="coolwarm",
        center=0,
        cbar_kws={"label": "Temperature Anomaly"},
    )
    axis.set_title("Monthly Temperature Anomaly Heatmap (By Decade)")
    axis.set_xlabel("Month")
    axis.set_ylabel("Decade")
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "monthly_heatmap.png", dpi=300)
    plt.close(figure)


def task5_land_ocean_compare() -> None:
    """Compare 120-month rolling mean anomalies for land and ocean."""
    print("==> 5. 正在画海陆对比图...")
    land = get_data("Land").set_index("obs_date")["Anomaly"]
    ocean = get_data("Ocean").set_index("obs_date")["Anomaly"]
    land_rolling = land.rolling(window=120).mean()
    ocean_rolling = ocean.rolling(window=120).mean()

    figure, axis = plt.subplots(figsize=(12, 6))
    axis.plot(land_rolling.index, land_rolling, label="Land", color="red")
    axis.plot(ocean_rolling.index, ocean_rolling, label="Ocean", color="blue")
    axis.set_title("Land vs Ocean Temperature Anomaly Trend")
    axis.legend()
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "land_ocean_compare.png", dpi=300)
    plt.close(figure)


if __name__ == "__main__":
    main_data = get_data("Land_Ocean")
    task1_stl_decomposition(main_data)
    task2_trend_test(main_data)
    task3_change_point(main_data)
    task4_heatmap(main_data)
    task5_land_ocean_compare()
    print("🎉 所有分析与画图任务已完成！请去 outputs/figures/ 查看。")
