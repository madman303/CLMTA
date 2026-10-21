import pytest
import pandas as pd
from scripts.update_data import parse_and_validate

# 动态生成一段合法的长数据，满足 >= 1000 行，且最新月份在 90 天内
lines = [
    "Title,Global Land and Ocean Temperature Anomalies",
    "Units,Degrees Celsius",
    "Base Period,1901-2000",
    "Missing,-999.0",
    "Date,Anomaly"
]
now = pd.Timestamp.now()
# 生成从 1850-01 到上个月的连续月份
dates = pd.date_range(start="1850-01-01", end=now - pd.DateOffset(months=1), freq="MS")
for d in dates:
    lines.append(f"{d.strftime('%Y%m')},1.0")
VALID_CSV = "\n".join(lines) + "\n"

def test_valid_data_passes():
    """测试：正常合法的数据应该顺利通过校验"""
    df, last_month = parse_and_validate(VALID_CSV, "land_ocean")
    assert len(df) > 1000
    # 验证最后一个月是不是上个月
    expected_month = (now - pd.DateOffset(months=1)).strftime("%Y-%m")
    assert last_month == expected_month

def test_missing_month_fails():
    """测试：如果中间断月了，必须抛出 ValueError"""
    # 删掉 1900 年的 5 月，制造断月
    broken_csv = VALID_CSV.replace("190005,1.0\n", "")
    # 注意：这里把 math 改成了正确的 match
    with pytest.raises(ValueError, match="断月"):
        parse_and_validate(broken_csv, "land_ocean")

def test_999_value_fails():
    """测试：如果混入了 -999，必须抛出 ValueError"""
    # 把 1900 年 5 月的数据改成 -999
    bad_value_csv = VALID_CSV.replace("190005,1.0", "190005,-999.0")
    with pytest.raises(ValueError, match="混入 -999"):
        parse_and_validate(bad_value_csv, "land_ocean")