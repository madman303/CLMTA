"""Rolling-origin backtesting for global land-ocean temperature anomalies."""

from __future__ import annotations

from pathlib import Path

import duckdb
import lightgbm as lgb
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX

DB_PATH = Path("data/clmta.duckdb")
FIGURE_PATH = Path("outputs/figures/forecast_comparison.png")
TEST_START = pd.Timestamp("2024-10-01")
TEST_END = pd.Timestamp("2026-09-01")
SEASONAL_PERIOD = 12
FEATURE_COLUMNS = [
    "lag_1",
    "lag_3",
    "lag_6",
    "lag_12",
    "rolling_mean_12",
    "month",
]


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
                SELECT
                    obs_date,
                    year,
                    month,
                    anomaly AS Anomaly
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
    frame = frame[frame["obs_date"] >= pd.Timestamp("2000-01-01")].reset_index(
        drop=True
    )
    expected_dates = pd.date_range(
        frame["obs_date"].min(),
        frame["obs_date"].max(),
        freq="MS",
    )
    if not frame["obs_date"].equals(pd.Series(expected_dates, name="obs_date")):
        raise ValueError("The 2000-to-present series contains missing or duplicate months")
    return frame


def seasonal_naive_forecast(history: pd.Series) -> float:
    """Predict one month using the value from the same month one year earlier."""
    if len(history) < SEASONAL_PERIOD:
        raise ValueError("Seasonal naive forecasting requires 12 history months")
    return float(history.iloc[-SEASONAL_PERIOD])


def drift_forecast(history: pd.Series) -> float:
    """Predict one month by extrapolating the slope between the endpoints."""
    if len(history) < 2:
        raise ValueError("Drift forecasting requires at least two observations")
    slope = (history.iloc[-1] - history.iloc[0]) / (len(history) - 1)
    return float(history.iloc[-1] + slope)


def sarimax_forecast(
    history: pd.Series,
) -> tuple[float, float, float, float, float]:
    """Fit SARIMAX and return the forecast plus 80% and 95% intervals."""
    model = SARIMAX(
        history,
        order=(1, 0, 0),
        seasonal_order=(1, 1, 1, SEASONAL_PERIOD),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    fitted = model.fit(disp=False)
    forecast = fitted.get_forecast(steps=1)
    mean = float(forecast.predicted_mean.iloc[0])
    intervals_80 = forecast.conf_int(alpha=0.20).iloc[0]
    intervals_95 = forecast.conf_int(alpha=0.05).iloc[0]
    lower_80 = float(intervals_80.iloc[0])
    upper_80 = float(intervals_80.iloc[1])
    lower_95 = float(intervals_95.iloc[0])
    upper_95 = float(intervals_95.iloc[1])
    return mean, lower_80, upper_80, lower_95, upper_95


def build_features(series: pd.Series) -> pd.DataFrame:
    """Build lag, rolling-mean, and calendar features without forward filling."""
    features = pd.DataFrame(index=series.index)
    features["lag_1"] = series.shift(1)
    features["lag_3"] = series.shift(3)
    features["lag_6"] = series.shift(6)
    features["lag_12"] = series.shift(12)
    features["rolling_mean_12"] = series.shift(1).rolling(12).mean()
    features["month"] = series.index.month
    return features


def train_lightgbm(train: pd.Series) -> lgb.LGBMRegressor:
    """Fit LightGBM on features derived only from the training history."""
    features = build_features(train)
    training = features.assign(target=train).dropna()
    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=200,
        learning_rate=0.03,
        num_leaves=15,
        max_depth=5,
        random_state=42,
        verbosity=-1,
    )
    model.fit(training[FEATURE_COLUMNS], training["target"])
    return model


def lightgbm_forecast(
    model: lgb.LGBMRegressor,
    history: pd.Series,
    timestamp: pd.Timestamp,
) -> float:
    """Predict one month from a history that may contain prior predictions."""
    series = pd.concat([history, pd.Series(index=[timestamp], dtype=float)])
    feature_row = build_features(series).loc[[timestamp], FEATURE_COLUMNS]
    return float(model.predict(feature_row)[0])


def rolling_backtest(
    train: pd.Series,
    test: pd.Series,
) -> pd.DataFrame:
    """Run one-step-ahead rolling-origin predictions across the test set."""
    history = train.copy()
    lightgbm_model = train_lightgbm(train)
    predictions: list[dict[str, float | pd.Timestamp]] = []

    for timestamp, actual in test.items():
        seasonal_naive = seasonal_naive_forecast(history)
        drift = drift_forecast(history)
        sarimax = sarimax_forecast(history)
        lightgbm_prediction = lightgbm_forecast(
            lightgbm_model,
            history,
            timestamp,
        )
        predictions.append(
            {
                "obs_date": timestamp,
                "actual": float(actual),
                "seasonal_naive": seasonal_naive,
                "drift": drift,
                "sarimax": sarimax[0],
                "sarimax_lower_80": sarimax[1],
                "sarimax_upper_80": sarimax[2],
                "sarimax_lower_95": sarimax[3],
                "sarimax_upper_95": sarimax[4],
                "lightgbm": lightgbm_prediction,
            }
        )
        history.loc[timestamp] = actual

    return pd.DataFrame(predictions).set_index("obs_date")


def mase(actual: pd.Series, predicted: pd.Series, training: pd.Series) -> float:
    """Calculate seasonal MASE using one-year seasonal differences."""
    scale = training.diff(SEASONAL_PERIOD).abs().dropna().mean()
    if not np.isfinite(scale) or scale == 0:
        raise ValueError("MASE scale is zero or non-finite")
    return float((actual - predicted).abs().mean() / scale)


def rmse(actual: pd.Series, predicted: pd.Series) -> float:
    """Calculate root mean squared error."""
    return float(np.sqrt(((actual - predicted) ** 2).mean()))


def mae(actual: pd.Series, predicted: pd.Series) -> float:
    """Calculate mean absolute error."""
    return float((actual - predicted).abs().mean())


def evaluate(
    predictions: pd.DataFrame,
    training: pd.Series,
) -> pd.DataFrame:
    """Calculate MASE and RMSE for each backtested model."""
    model_columns = {
        "Seasonal Naive": "seasonal_naive",
        "Drift": "drift",
        "SARIMAX": "sarimax",
        "LightGBM": "lightgbm",
    }
    results = []
    actual = predictions["actual"]
    for model_name, column in model_columns.items():
        forecast = predictions[column]
        results.append(
            {
                "model": model_name,
                "MASE": mase(actual, forecast, training),
                "RMSE": rmse(actual, forecast),
                "MAE": mae(actual, forecast),
            }
        )
    return pd.DataFrame(results).set_index("model")


def plot_results(predictions: pd.DataFrame) -> None:
    """Plot actuals, forecasts, and SARIMAX prediction intervals."""
    FIGURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    figure, axis = plt.subplots(figsize=(14, 7))
    axis.plot(predictions.index, predictions["actual"], label="Actual", color="black")
    axis.plot(
        predictions.index,
        predictions["seasonal_naive"],
        label="Seasonal Naive",
        color="tab:green",
    )
    axis.plot(
        predictions.index,
        predictions["drift"],
        label="Drift",
        color="tab:orange",
    )
    axis.plot(
        predictions.index,
        predictions["sarimax"],
        label="SARIMAX",
        color="tab:blue",
    )
    axis.plot(
        predictions.index,
        predictions["lightgbm"],
        label="LightGBM",
        color="purple",
    )
    axis.fill_between(
        predictions.index,
        predictions["sarimax_lower_95"],
        predictions["sarimax_upper_95"],
        color="tab:blue",
        alpha=0.12,
        label="SARIMAX 95% interval",
    )
    axis.fill_between(
        predictions.index,
        predictions["sarimax_lower_80"],
        predictions["sarimax_upper_80"],
        color="tab:blue",
        alpha=0.22,
        label="SARIMAX 80% interval",
    )
    axis.set_title("Rolling-Origin Forecast Comparison")
    axis.set_xlabel("Date")
    axis.set_ylabel("Temperature anomaly")
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(FIGURE_PATH, dpi=300)
    plt.close(figure)


def main() -> None:
    """Run the complete rolling-origin backtest."""
    data = get_data()
    data = data.set_index("obs_date").asfreq("MS")
    if data["Anomaly"].isna().any():
        raise ValueError("The monthly series contains missing anomaly values")
    test = data.loc[TEST_START:TEST_END, "Anomaly"]
    train = data.loc[data.index < TEST_START, "Anomaly"]

    if len(test) != 24:
        raise ValueError(f"Expected 24 test months, got {len(test)}")
    if test.index[-1] != TEST_END:
        raise ValueError(
            f"Expected test data through {TEST_END.date()}, "
            f"got {test.index[-1].date()}"
        )

    predictions = rolling_backtest(train, test)
    metrics = evaluate(predictions, train)
    print(f"训练集：{train.index[0].date()} 至 {train.index[-1].date()}（{len(train)} 个月）")
    print(f"测试集：{test.index[0].date()} 至 {test.index[-1].date()}（{len(test)} 个月）")
    print(metrics.to_string(float_format=lambda value: f"{value:.4f}"))
    plot_results(predictions)
    print(f"图表已保存至 {FIGURE_PATH}")


if __name__ == "__main__":
    main()
