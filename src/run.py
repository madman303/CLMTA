# 查看表格数据的基本信息
import pandas as pd
import numpy as np 
import os

# 读取 CSV 文件
df = pd.read_csv("data/global-temp-time-series.csv",comment = "#")
df["Date"] = pd.to_datetime(df["Date"].astype(str),format="%Y%m")

# 查看数据基本信息
print(df.info())

#数据体检
print("数据的体检报告：")
print("数据的行数：",df.shape[0])
print("数据的列数：",df.shape[1])
print("数据的列名：",df.columns.tolist())
print("数据的缺失值情况：",df.isnull().sum().to_dict())
print("数据的描述性统计：",df.describe())