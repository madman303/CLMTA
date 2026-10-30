import pandas as pd
from scripts.analyze import annual_means, mann_kendall


def test_mann_kendall_detects_increasing_trend():
    values = [float(value) for value in range(20)]
    s, z, p_value = mann_kendall(values)
    assert s > 0
    assert z > 0
    assert p_value < 0.05


def test_mann_kendall_detects_decreasing_trend():
    values = [float(value) for value in range(20, 0, -1)]
    s, z, p_value = mann_kendall(values)
    assert s < 0
    assert z < 0
    assert p_value < 0.05


def test_mann_kendall_constant_series_is_not_significant():
    s, _, p_value = mann_kendall([1.0] * 20)
    assert s == 0
    assert p_value == 1.0


def test_annual_means_excludes_partial_final_year():
    rows = []
    for year in (2000, 2001):
        for month in range(1, 13):
            rows.append({"year": year, "month": month, "Anomaly": 1.0})
    for month in range(1, 10):
        rows.append({"year": 2002, "month": month, "Anomaly": 1.0})

    annual = annual_means(pd.DataFrame(rows))
    assert list(annual.index) == [2000, 2001]
