import numpy as np
import pandas as pd
import pytest
from scripts.forecast import (
    direct_training_set,
    drift_path,
    evaluate_by_horizon,
    interval_coverage,
    mean_interval_width,
    seasonal_naive_path,
)


def test_seasonal_naive_recurses_without_actuals():
    index = pd.date_range("2000-01-01", periods=24, freq="MS")
    history = pd.Series(range(1, 25), index=index, dtype=float)
    path = seasonal_naive_path(history)

    assert path[1] == 13.0
    assert path[12] == 24.0
    assert path[13] == 13.0
    assert path[24] == 24.0


def test_drift_extrapolates_endpoint_slope():
    history = pd.Series([0.0, 1.0, 2.0, 3.0])
    path = drift_path(history)
    assert path[1] == 4.0
    assert path[3] == 6.0


def test_direct_training_uses_only_history_before_target():
    index = pd.date_range("2000-01-01", periods=36, freq="MS")
    history = pd.Series(range(1, 37), index=index, dtype=float)
    features, target = direct_training_set(history, horizon=3)

    first = features[0]
    assert first[0] == 12.0
    assert first[1] == 10.0
    assert first[2] == 7.0
    assert first[3] == 1.0
    assert first[4] == 6.5
    assert first[5] == 3.0
    assert target[0] == 15.0

    last = features[-1]
    assert last[0] == 33.0
    assert last[5] == 12.0
    assert target[-1] == 36.0


def test_evaluate_by_horizon_returns_metrics_and_coverage():
    predictions = pd.DataFrame(
        {
            "horizon": [1, 3],
            "actual": [1.0, 2.0],
            "scale": [1.0, 1.0],
            "seasonal_naive": [1.0, 1.0],
            "drift": [1.0, 1.0],
            "sarimax": [1.0, 1.0],
            "sarimax_lower_80": [0.0, 0.0],
            "sarimax_upper_80": [2.0, 2.0],
            "sarimax_lower_95": [0.0, 0.0],
            "sarimax_upper_95": [2.0, 2.0],
            "lightgbm": [1.0, 1.0],
        }
    )
    metrics = evaluate_by_horizon(predictions)

    assert set(metrics["horizon"]) == {1, 3}
    assert set(metrics["model"]) == {
        "Seasonal Naive",
        "Drift",
        "SARIMAX",
        "LightGBM",
    }
    horizon_3 = metrics[metrics["horizon"] == 3].set_index("model")
    assert horizon_3.loc["SARIMAX", "MASE"] == 1.0
    assert horizon_3.loc["SARIMAX", "RMSE"] == 1.0
    assert horizon_3.loc["SARIMAX", "Coverage80"] == 1.0


def test_interval_coverage_and_width():
    actual = pd.Series([0.0, 1.0, 2.0])
    lower = pd.Series([-1.0, -1.0, -1.0])
    upper = pd.Series([1.0, 1.0, 1.0])
    assert interval_coverage(actual, lower, upper) == 2 / 3
    assert mean_interval_width(lower, upper) == 2.0


def test_direct_training_requires_a_target_inside_history():
    index = pd.date_range("2000-01-01", periods=12, freq="MS")
    history = pd.Series(np.arange(12, dtype=float), index=index)
    with pytest.raises(ValueError, match="Not enough history"):
        direct_training_set(history, horizon=1)
