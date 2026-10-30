"""Run ClimateScope anomaly analyses and save the resulting figures."""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import ruptures as rpt
import seaborn as sns
from scipy.stats import norm, theilslopes
from statsmodels.tsa.seasonal import STL

DB_PATH = Path("data/clmta.duckdb")
OUTPUT_DIR = Path("outputs/figures")
SUMMARY_PATH = Path("outputs/analysis_summary.json")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
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


def annual_means(df: pd.DataFrame) -> pd.Series:
    """Return annual means, excluding a partially observed final year."""
    annual = df.groupby("year")["Anomaly"].mean()
    last_year = int(df["year"].max())
    observed_months = df.loc[df["year"] == last_year, "month"].nunique()
    if observed_months < 12:
        annual = annual[annual.index < last_year]
    return annual


def mann_kendall(values: np.ndarray) -> tuple[float, float, float]:
    """Compute the Mann-Kendall S statistic, Z score and two-sided p-value."""
    x = np.asarray(values, dtype=float)
    n = x.size
    if n < 3:
        raise ValueError("Mann-Kendall requires at least three observations")

    s = 0.0
    for index in range(n - 1):
        s += float(np.sign(x[index + 1 :] - x[index]).sum())

    _, counts = np.unique(x, return_counts=True)
    tie_term = sum(int(t) * (int(t) - 1) * (2 * int(t) + 5) for t in counts)
    variance = (n * (n - 1) * (2 * n + 5) - tie_term) / 18
    if variance <= 0:
        return s, 0.0, 1.0

    if s > 0:
        z = (s - 1) / np.sqrt(variance)
    elif s < 0:
        z = (s + 1) / np.sqrt(variance)
    else:
        z = 0.0
    p_value = 2 * (1 - norm.cdf(abs(z)))
    return float(s), float(z), float(p_value)


def task2_trend_test(df: pd.DataFrame) -> dict:
    """Run an annual Mann-Kendall test and a Theil-Sen slope estimate."""
    print("==> 2. 正在做年度 Mann-Kendall 检验与 Theil-Sen 斜率...")
    annual = annual_means(df)
    s, z, p_value = mann_kendall(annual.to_numpy())
    slope, _, lower, upper = theilslopes(
        annual.to_numpy(),
        annual.index.to_numpy(),
    )

    print(f"年度范围：{annual.index.min()}–{annual.index.max()}（{len(annual)} 个完整年份）")
    print(f"Mann-Kendall S={s:.1f}, Z={z:.3f}, p={p_value:.4e}")
    print(
        f"Theil-Sen 斜率：{slope * 10:.4f} °C/十年，"
        f"95% CI [{lower * 10:.4f}, {upper * 10:.4f}]"
    )
    if p_value < 0.05:
        print("✅ 年度尺度存在显著上升趋势")

    return {
        "method": "annual Mann-Kendall + Theil-Sen",
        "year_start": int(annual.index.min()),
        "year_end": int(annual.index.max()),
        "n_years": int(len(annual)),
        "S": s,
        "Z": z,
        "p_value": p_value,
        "slope_per_decade": float(slope * 10),
        "slope_ci95_per_decade": [float(lower * 10), float(upper * 10)],
    }


def task3_change_point(df: pd.DataFrame) -> dict:
    """Detect annual-mean change points and check penalty sensitivity."""
    print("==> 3. 正在做变点检测...")
    annual = annual_means(df)
    values = annual.to_numpy().reshape(-1, 1)

    sensitivity: dict[str, list[int]] = {}
    for penalty in (5, 10, 20):
        breakpoints = rpt.Pelt(model="rbf").fit(values).predict(pen=penalty)
        years = [
            int(annual.index[index])
            for index in breakpoints[:-1]
            if index < len(annual)
        ]
        sensitivity[str(penalty)] = years

    selected = sensitivity["10"]
    print(f"pen=10 的变点年份：{selected}")
    print(f"pen=5/10/20 敏感性：{sensitivity}")

    return {
        "method": "Pelt(rbf) on annual means",
        "selected_penalty": 10,
        "breakpoints": selected,
        "sensitivity": sensitivity,
    }


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
    axis.set_title(
        "Monthly Temperature Anomaly Heatmap (By Decade)\n"
        "2020s partial: 2020–2026"
    )
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
    axis.set_ylabel("Temperature anomaly (°C)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(OUTPUT_DIR / "land_ocean_compare.png", dpi=300)
    plt.close(figure)


def main() -> None:
    """Run all analyses, save figures and a compact JSON summary."""
    main_data = get_data("Land_Ocean")
    task1_stl_decomposition(main_data)
    trend = task2_trend_test(main_data)
    change_points = task3_change_point(main_data)
    task4_heatmap(main_data)
    task5_land_ocean_compare()

    summary = {
        "data_start": main_data["obs_date"].min().strftime("%Y-%m"),
        "data_end": main_data["obs_date"].max().strftime("%Y-%m"),
        "stl": {"period": 12, "robust": True},
        "trend": trend,
        "change_points": change_points,
    }
    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n分析摘要已保存至 {SUMMARY_PATH}")
    print("🎉 所有分析与画图任务已完成！请去 outputs/figures/ 查看。")


if __name__ == "__main__":
    main()
