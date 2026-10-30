"""Multi-horizon rolling-origin backtesting for global temperature anomalies.

For every origin, the model only sees data through that origin. Forecasts for
h=1, 3, 6, 12 and 24 months are made from that fixed history; actual values
inside the forecast window are never written back into the model history.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

DB_PATH = Path("data/clmta.duckdb")
OUTPUT_DIR = Path("outputs")
FIGURE_DIR = OUTPUT_DIR / "figures"
METRICS_PATH = OUTPUT_DIR / "forecast_horizon_metrics.csv"
PREDICTIONS_PATH = OUTPUT_DIR / "forecast_horizon_predictions.csv"
RMSE_PLOT = FIGURE_DIR / "forecast_horizon_rmse.png"
COVERAGE_PLOT = FIGURE_DIR / "forecast_horizon_coverage.png"

TRAIN_START = pd.Timestamp("2000-01-01")
FIRST_ORIGIN = pd.Timestamp("2020-09-01")
HORIZONS = (1, 3, 6, 12, 24)
MAX_HORIZON = max(HORIZONS)
ORIGIN_FREQ = "6MS"
SEASONAL_PERIOD = 12
FEATURE_COLUMNS = [
    "lag_1",
    "lag_3",
    "lag_6",
    "lag_12",
    "rolling_mean_12",
    "target_month",
]
MODEL_COLUMNS = {
    "Seasonal Naive": "seasonal_naive",
    "Drift": "drift",
    "SARIMAX": "sarimax",
    "LightGBM": "lightgbm",
}


def get_data() -> pd.DataFrame:
    """Load the Land_Ocean monthly series from the DuckDB mart."""
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
                SELECT obs_date, year, month, Anomaly
                FROM mart_monthly_anomaly
                WHERE region = ?
                ORDER BY obs_date
            """
            parameters = ["Land_Ocean"]
        elif ("marts", "monthly_anomaly") in table_names:
            query = """
                SELECT obs_date, year, month, anomaly AS Anomaly
                FROM marts.monthly_anomaly
                WHERE series = ?
                ORDER BY obs_date
            """
            parameters = ["land_ocean"]
        else:
            raise RuntimeError(
                "Could not find mart_monthly_anomaly or marts.monthly_anomaly"
            )

        frame = connection.execute(query, parameters).df()
    finally:
        connection.close()

    frame["obs_date"] = pd.to_datetime(frame["obs_date"])
    frame = frame.sort_values("obs_date").reset_index(drop=True)
    frame = frame[frame["obs_date"] >= TRAIN_START].reset_index(drop=True)
    expected_dates = pd.date_range(
        frame["obs_date"].min(),
        frame["obs_date"].max(),
        freq="MS",
    )
    if not frame["obs_date"].equals(pd.Series(expected_dates, name="obs_date")):
        raise ValueError("The series contains missing or duplicate months")
    return frame


def build_origins(data: pd.Series) -> list[pd.Timestamp]:
    """Build forecast origins with enough future data for the longest horizon."""
    latest_origin = data.index.max() - pd.DateOffset(months=MAX_HORIZON)
    origins = pd.date_range(FIRST_ORIGIN, latest_origin, freq=ORIGIN_FREQ)
    if len(origins) < 3:
        raise ValueError("Need at least three forecast origins")
    return [pd.Timestamp(origin) for origin in origins]


def seasonal_naive_path(history: pd.Series) -> dict[int, float]:
    """Recursive seasonal naive forecasts for every month up to MAX_HORIZON."""
    if len(history) < SEASONAL_PERIOD:
        raise ValueError("Seasonal naive needs at least 12 history months")

    path: dict[int, float] = {}
    for horizon in range(1, MAX_HORIZON + 1):
        if horizon <= SEASONAL_PERIOD:
            path[horizon] = float(history.iloc[horizon - SEASONAL_PERIOD - 1])
        else:
            path[horizon] = path[horizon - SEASONAL_PERIOD]
    return path


def drift_path(history: pd.Series) -> dict[int, float]:
    """Extrapolate the endpoint slope for every horizon up to MAX_HORIZON."""
    if len(history) < 2:
        raise ValueError("Drift needs at least two observations")
    slope = (float(history.iloc[-1]) - float(history.iloc[0])) / (len(history) - 1)
    last = float(history.iloc[-1])
    return {horizon: last + horizon * slope for horizon in range(1, MAX_HORIZON + 1)}


def sarimax_path(history: pd.Series) -> dict[int, dict[str, float]]:
    """Fit one SARIMAX per origin and return its multi-step forecast path."""
    model = SARIMAX(
        history,
        order=(1, 0, 0),
        seasonal_order=(1, 1, 1, SEASONAL_PERIOD),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    forecast = fitted.get_forecast(steps=MAX_HORIZON)
    mean = np.asarray(forecast.predicted_mean, dtype=float)
    interval_80 = np.asarray(forecast.conf_int(alpha=0.20), dtype=float)
    interval_95 = np.asarray(forecast.conf_int(alpha=0.05), dtype=float)

    return {
        horizon: {
            "mean": float(mean[horizon - 1]),
            "lower_80": float(interval_80[horizon - 1, 0]),
            "upper_80": float(interval_80[horizon - 1, 1]),
            "lower_95": float(interval_95[horizon - 1, 0]),
            "upper_95": float(interval_95[horizon - 1, 1]),
        }
        for horizon in range(1, MAX_HORIZON + 1)
    }


def feature_row(values: np.ndarray, index: int, target_date: pd.Timestamp) -> list[float]:
    """Build a direct-forecast feature row using only data through `index`."""
    if index < SEASONAL_PERIOD - 1:
        raise ValueError("Not enough history for lag features")
    return [
        float(values[index]),
        float(values[index - 2]),
        float(values[index - 5]),
        float(values[index - 11]),
        float(values[index - 11 : index + 1].mean()),
        float(target_date.month),
    ]


def direct_training_set(
    history: pd.Series,
    horizon: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Build leakage-free direct training data for one forecast horizon."""
    values = history.to_numpy(dtype=float)
    dates = history.index
    rows: list[list[float]] = []
    targets: list[float] = []

    for index in range(SEASONAL_PERIOD - 1, len(values)):
        target_date = dates[index] + pd.DateOffset(months=horizon)
        if target_date > dates[-1]:
            continue
        target_position = dates.get_indexer([target_date])[0]
        if target_position < 0:
            continue
        rows.append(feature_row(values, index, target_date))
        targets.append(float(values[target_position]))

    if not rows:
        raise ValueError(f"Not enough history for LightGBM horizon {horizon}")
    return np.asarray(rows, dtype=float), np.asarray(targets, dtype=float)


def lightgbm_direct_forecast(history: pd.Series, horizon: int) -> float:
    """Fit a horizon-specific LightGBM model and forecast from the origin."""
    features, target = direct_training_set(history, horizon)
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=200,
        learning_rate=0.03,
        num_leaves=15,
        max_depth=5,
        random_state=42,
        verbosity=-1,
    )
    model.fit(features, target)

    target_date = history.index[-1] + pd.DateOffset(months=horizon)
    row = np.asarray(
        [feature_row(history.to_numpy(dtype=float), len(history) - 1, target_date)],
        dtype=float,
    )
    return float(model.predict(row)[0])


def backtest(data: pd.Series) -> pd.DataFrame:
    """Run multi-horizon forecasts from fixed origins without backfilling."""
    origins = build_origins(data)
    records: list[dict[str, object]] = []

    for origin in origins:
        history = data.loc[data.index <= origin]
        scale = float(history.diff(SEASONAL_PERIOD).abs().dropna().mean())
        if not np.isfinite(scale) or scale == 0:
            raise ValueError(f"Invalid MASE scale at origin {origin.date()}")

        sarimax = sarimax_path(history)
        seasonal_naive = seasonal_naive_path(history)
        drift = drift_path(history)

        for horizon in HORIZONS:
            target_date = origin + pd.DateOffset(months=horizon)
            if target_date not in data.index:
                continue
            actual = float(data.loc[target_date])
            interval = sarimax[horizon]
            records.append(
                {
                    "origin": origin,
                    "horizon": horizon,
                    "target_date": target_date,
                    "actual": actual,
                    "scale": scale,
                    "seasonal_naive": seasonal_naive[horizon],
                    "drift": drift[horizon],
                    "sarimax": interval["mean"],
                    "sarimax_lower_80": interval["lower_80"],
                    "sarimax_upper_80": interval["upper_80"],
                    "sarimax_lower_95": interval["lower_95"],
                    "sarimax_upper_95": interval["upper_95"],
                    "lightgbm": lightgbm_direct_forecast(history, horizon),
                }
            )

    return pd.DataFrame(records)


def interval_coverage(
    actual: pd.Series,
    lower: pd.Series,
    upper: pd.Series,
) -> float:
    """Return the share of actual values inside the prediction interval."""
    covered = (actual >= lower) & (actual <= upper)
    return float(covered.mean())


def mean_interval_width(lower: pd.Series, upper: pd.Series) -> float:
    """Return the average width of a prediction interval."""
    return float((upper - lower).mean())


def evaluate_by_horizon(predictions: pd.DataFrame) -> pd.DataFrame:
    """Calculate MASE, RMSE, MAE and interval metrics for each horizon."""
    results: list[dict[str, object]] = []
    for horizon in HORIZONS:
        subset = predictions[predictions["horizon"] == horizon]
        if subset.empty:
            continue
        actual = subset["actual"]
        for model_name, column in MODEL_COLUMNS.items():
            error = actual - subset[column]
            row: dict[str, object] = {
                "horizon": horizon,
                "model": model_name,
                "n": int(len(subset)),
                "MASE": float((error.abs() / subset["scale"]).mean()),
                "RMSE": float(np.sqrt((error**2).mean())),
                "MAE": float(error.abs().mean()),
            }
            if model_name == "SARIMAX":
                row["Coverage80"] = interval_coverage(
                    actual,
                    subset["sarimax_lower_80"],
                    subset["sarimax_upper_80"],
                )
                row["Width80"] = mean_interval_width(
                    subset["sarimax_lower_80"],
                    subset["sarimax_upper_80"],
                )
                row["Coverage95"] = interval_coverage(
                    actual,
                    subset["sarimax_lower_95"],
                    subset["sarimax_upper_95"],
                )
                row["Width95"] = mean_interval_width(
                    subset["sarimax_lower_95"],
                    subset["sarimax_upper_95"],
                )
            results.append(row)
    return pd.DataFrame(results)


def plot_rmse(metrics: pd.DataFrame) -> None:
    """Plot RMSE as a function of forecast horizon."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(9, 5.5))
    for model_name in MODEL_COLUMNS:
        subset = metrics[metrics["model"] == model_name].sort_values("horizon")
        axis.plot(
            subset["horizon"],
            subset["RMSE"],
            marker="o",
            linewidth=1.8,
            label=model_name,
        )
    axis.set_xticks(HORIZONS)
    axis.set_xlabel("Forecast horizon (months)")
    axis.set_ylabel("RMSE (°C)")
    axis.set_title("Multi-Horizon Forecast Error")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(RMSE_PLOT, dpi=300)
    plt.close(figure)


def plot_coverage(metrics: pd.DataFrame) -> None:
    """Plot SARIMAX interval coverage as a function of forecast horizon."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    sarimax = metrics[metrics["model"] == "SARIMAX"].sort_values("horizon")
    figure, axis = plt.subplots(figsize=(9, 5.5))
    axis.plot(
        sarimax["horizon"],
        sarimax["Coverage80"],
        marker="o",
        linewidth=1.8,
        label="80% interval",
    )
    axis.plot(
        sarimax["horizon"],
        sarimax["Coverage95"],
        marker="s",
        linewidth=1.8,
        label="95% interval",
    )
    axis.axhline(0.80, color="tab:blue", linestyle="--", alpha=0.4)
    axis.axhline(0.95, color="tab:orange", linestyle="--", alpha=0.4)
    axis.set_xticks(HORIZONS)
    axis.set_ylim(0, 1.05)
    axis.set_xlabel("Forecast horizon (months)")
    axis.set_ylabel("Empirical coverage")
    axis.set_title("SARIMAX Interval Coverage by Horizon")
    axis.grid(alpha=0.25)
    axis.legend()
    figure.tight_layout()
    figure.savefig(COVERAGE_PLOT, dpi=300)
    plt.close(figure)


def main() -> None:
    """Run the complete multi-horizon backtest and save metrics/figures."""
    data = get_data().set_index("obs_date")["Anomaly"].asfreq("MS")
    if data.isna().any():
        raise ValueError("The monthly series contains missing anomaly values")

    origins = build_origins(data)
    predictions = backtest(data)
    metrics = evaluate_by_horizon(predictions)
    if metrics.empty:
        raise ValueError("No backtest metrics were produced")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    predictions.to_csv(PREDICTIONS_PATH, index=False)
    metrics.to_csv(METRICS_PATH, index=False)
    plot_rmse(metrics)
    plot_coverage(metrics)

    print(
        "口径：每个 origin 固定历史，只做 h=1/3/6/12/24 的多步预测；"
        "窗口内不回填真实值。"
    )
    print(f"origins：{len(origins)} 个（{origins[0].date()} 至 {origins[-1].date()}）")
    print(f"horizons：{HORIZONS}；每个 horizon 有 {metrics['n'].max()} 个 origin 样本。")
    print("\nRMSE by horizon:")
    print(metrics.pivot(index="horizon", columns="model", values="RMSE").round(4).to_string())
    print("\nMASE by horizon:")
    print(metrics.pivot(index="horizon", columns="model", values="MASE").round(4).to_string())
    sarimax = metrics[metrics["model"] == "SARIMAX"]
    print("\nSARIMAX coverage:")
    print(
        sarimax[
            ["horizon", "Coverage80", "Width80", "Coverage95", "Width95"]
        ].round(4).to_string(index=False)
    )
    print(f"\n指标已保存至 {METRICS_PATH}")
    print(f"预测已保存至 {PREDICTIONS_PATH}")
    print(f"RMSE 图已保存至 {RMSE_PLOT}")
    print(f"覆盖图已保存至 {COVERAGE_PLOT}")


if __name__ == "__main__":
    main()
