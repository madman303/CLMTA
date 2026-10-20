from pathlib import Path

import pandas as pd


def test_root_dir():
    """检查项目根目录是否有pyproject.toml文件"""
    assert Path("pyproject.toml").exists(),"pyproject.toml文件不存在于项目根目录"

def test_data_dir():
    """检查数据目录是否存在"""
    assert Path("data").is_dir(), "数据目录不存在"
    assert Path("data").exists(), "数据目录不存在"
def test_pandas_import():
    """检查是否可以导入pandas"""
    assert pd.__version__ is not None, "无法导入pandas"