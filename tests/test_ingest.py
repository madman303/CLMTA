import pandas as pd
import pytest
from scripts.update_data import parse_and_validate

# 完全对齐真实 NOAA 的格式：3行注释 + 1行表头 + 数据
lines = [
    "# Title: Global Land and Ocean Temperature Anomalies",
    "# Units: Degrees Celsius",
    "# Base Period: 1901-2000",
    "Date,Departure from Average"
]
now = pd.Timestamp.now()
dates = pd.date_range(start="1850-01-01", end=now - pd.DateOffset(months=1), freq="MS")
for d in dates:
    lines.append(f"{d.strftime('%Y%m')},1.0")
VALID_CSV = "\n".join(lines) + "\n"

def test_valid_data_passes():
    df, last_month = parse_and_validate(VALID_CSV, "land_ocean")
    # 断言长度准确（1850至今大致是 2121 行）
    assert len(df) > 2000
    assert int(df["Date"].iloc[0]) == 185001

def test_missing_month_fails():
    broken_csv = VALID_CSV.replace("190005,1.0\n", "")
    with pytest.raises(ValueError, match="断月"):
        parse_and_validate(broken_csv, "land_ocean")

def test_999_value_fails():
    bad_value_csv = VALID_CSV.replace("190005,1.0", "190005,-999.0")
    with pytest.raises(ValueError, match="混入 -999"):
        parse_and_validate(bad_value_csv, "land_ocean")

def test_duplicate_month_fails():
    # 把 190006 改成和 190005 一样的月份
    dup_csv = VALID_CSV.replace("190006,1.0", "190005,1.0")
    with pytest.raises(ValueError, match="重复月份"):
        parse_and_validate(dup_csv, "land_ocean")