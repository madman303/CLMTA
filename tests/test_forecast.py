import numpy as np
import pandas as pd
from scripts.forecast import (
    build_features,
    diebold_mariano,
    drift_forecast,
    interval_coverage,
    mae,
    mase,
    mean_interval_width,
    seasonal_naive_forecast,
)


def test_seasonal_naive_uses_same_month_last_year():
    history = pd.Series(range(1, 14), dtype=float)
    assert seasonal_naive_forecast(history) == 2.0


def test_drift_extrapolates_endpoint_slope():
    history = pd.Series([0.0, 1.0, 2.0, 3.0])
    assert drift_forecast(history) == 4.0


def test_build_features_does_not_use_future_values():
    index = pd.date_range("2000-01-01", periods=24, freq="MS")
    series = pd.Series(range(1, 25), index=index, dtype=float)
    features = build_features(series)

    assert np.isnan(features.loc[index[0], "lag_1"])
    assert features.loc[index[12], "lag_1"] == 12.0
    assert features.loc[index[12], "rolling_mean_12"] == 6.5
    assert features.loc[index[12], "month"] == 1


def test_mase_uses_training_seasonal_scale():
    training = pd.Series(range(1, 14), dtype=float)
    actual = pd.Series([2.0])
    predicted = pd.Series([1.0])
    assert mase(actual, predicted, training) == 1 / 12


def test_interval_coverage_and_width():
    actual = pd.Series([0.0, 1.0, 2.0])
    lower = pd.Series([-1.0, -1.0, -1.0])
    upper = pd.Series([1.0, 1.0, 1.0])
    assert interval_coverage(actual, lower, upper) == 2 / 3
    assert mean_interval_width(lower, upper) == 2.0


def test_diebold_mariano_detects_direction():
    actual = pd.Series([1.0, 2.0, 3.0, 4.0])
    perfect = pd.Series([1.0, 2.0, 3.0, 4.0])
    worse = pd.Series([0.0, 0.0, 0.0, 0.0])
    statistic, p_value = diebold_mariano(actual, perfect, worse)
    assert statistic < 0
    assert 0 <= p_value <= 1


def test_mae_known_value():
    actual = pd.Series([1.0, 2.0])
    predicted = pd.Series([2.0, 4.0])
    assert mae(actual, predicted) == 1.5
