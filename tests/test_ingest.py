import pytest
from scripts.update_data import parse_and_validate

#伪造一段“完美”的原始NOAA文本
VALID_CSV = """Title,Global Land and Ocean Temperature Anomalies
Units,Degrees Celsius
Base Period,1901-2000
Missing,-999.0
Date,Anomaly
202601,1.10
202602,1.12
202603,1.15
"""

def test_valid_data_passes():
    """测试：正常合法的数据应该顺利通过校验"""
    df,last_month = parse_and_validate(VALID_CSV,"land_ocean")
    assert last_month == "2026-03"
    assert len(df) == 3
    
def test_missing_month_fails():
    """测试：如果中间断月了，必须抛出ValueError"""
    #把202602删掉，制造断月
    broken_csv = VALID_CSV.replace("202602,1.12\n","")
    with pytest.raises(ValueError,math="断月"):
        parse_and_validate(broken_csv,"land_ocean")
        
def test_999_value_fails():
    """测试：如果混入了 -999，必须抛出ValueError"""
    #把1.12改成-999
    bad_value_csv = VALID_CSV.replace("202602,1.12", "202602,-999.0")
    with pytest.raises(ValueError,math="混入 -999"):
        parse_and_validate(bad_value_csv,"land_ocean")