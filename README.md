# CLMTA

## Monthly Time-Series Analysis of Global Land–Ocean Mean Temperature Anomalies

**CLMTA**（Global Land and Ocean Mean Temperature Anomalies）是一个面向气候数据分析的月度时间序列项目，聚焦于全球陆地和海洋平均温度异常的变化趋势、季节性和长期模式。

当前仓库提供了可用于探索和建模的月度温度异常数据集。项目后续可在此基础上开展数据清洗、可视化、趋势分析及时间序列预测。

## 项目内容

- 整理全球陆地和海洋平均温度异常的月度观测数据；
- 支持长期变暖趋势和月度季节性变化的探索；
- 为统计分析、时间序列建模和气候变化研究提供基础数据。

## 数据说明

数据文件位于 [`data/global-temp-time-series.csv`](data/global-temp-time-series.csv)，包含 **1850 年 1 月至 2024 年 12 月** 的 2,100 条月度记录。

| 字段 | 说明 |
| --- | --- |
| `Date` | 月份，格式为 `YYYYMM`，例如 `185001` 表示 1850 年 1 月 |
| `Anomaly` | 相对于基准期的温度异常值，单位为摄氏度（°C） |

数据文件头部元数据说明：

- 基准期：1901–2000 年；
- 缺失值标记：`-999`；
- 数据频率：月度。

使用数据前应将 `-999` 转换为缺失值，并确认时间列按月份解析。

## 快速开始

本项目目前以数据集为核心，不包含固定的运行入口。可以使用 Python 和 pandas 快速读取数据：

```python
import pandas as pd

df = pd.read_csv("data/global-temp-time-series.csv", comment="#")
df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m")
df["Anomaly"] = df["Anomaly"].replace(-999, pd.NA)

print(df.head())
print(df["Anomaly"].describe())
```

如果尚未安装 pandas，可执行：

```bash
pip install pandas
```

## 目录结构

```text
CLMTA/
├── data/
│   └── global-temp-time-series.csv
└── README.md
```

## 分析建议

可以围绕以下方向扩展项目：

1. 绘制温度异常的月度和年度变化曲线；
2. 分解长期趋势、季节性和随机波动；
3. 使用移动平均、线性回归或 ARIMA 等方法进行趋势分析；
4. 评估不同时间窗口下的温度异常变化；
5. 对异常值处理和模型结果进行不确定性分析。

## 注意事项

温度异常表示相对于基准期的偏差，并不等同于绝对气温。分析结果应结合数据的基准期、缺失值标记和数据来源进行解释；本项目不应单独作为气候政策或风险判断的依据。