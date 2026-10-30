# ClimateScope (CLMTA)

ClimateScope（项目名：CLMTA）是一个面向全球月度气候异常数据的可复现分析与预测工程，聚焦全球陆地—海洋温度异常的趋势识别、突变检测和可视化分析。

## 核心亮点

- 端到端数据工程：从 NOAA 官方数据源拉取原始 CSV，保留 raw 快照，并构建标准化的 `raw / staging / marts` 三层数据仓库。
- 自动化数据校验：覆盖基准期、连续月份、时序完整性和新鲜度等关键检查，确保数据管线稳定可靠。
- 可复现分析链路：使用 pandas、DuckDB、statsmodels、ruptures 和 seaborn 形成统一分析流程，便于扩展到预测和回测。
- 结果可视化：输出多种高质量图表，为全球变暖趋势、陆海差异和年代际变化提供直观证据。

## Quickstart

项目使用 Python 3.12 和 [uv](https://docs.astral.sh/uv/) 管理依赖。首次运行时，建议按顺序执行：

```bash
uv sync
make data
make db
make test
```

说明：

1. `uv sync`：创建并同步 Python 虚拟环境与依赖；
2. `make data`：从 NOAA 下载数据并保存原始快照；
3. `make db`：构建 DuckDB 数据仓库（raw → staging → marts）；
4. `make test`：运行 Ruff 和 pytest，确保代码与数据管线均正常。

## 核心数据洞察与可视化

### 1. STL 分解图：剥离季节性后，长期趋势呈现加速上升

![STL 分解图](outputs/figures/stl_decomposition.png)

从 STL 分解图可以看出，原始温度异常序列中包含明显的季节性周期，但在去除季节性波动后，趋势项呈现出明显的长期上升。尤其在 1980 年代之后，增温趋势明显增强，说明全球变暖并非线性缓慢推进，而是在近几十年中呈现出指数级加速的状态。Mann-Kendall 趋势检验结果显示 p < 0.05，表明上升趋势极度显著，具有强统计证据支持。

### 2. 海陆对比图：陆地升温速率明显快于海洋

![海陆对比图](outputs/figures/land_ocean_compare.png)

对比 120 个月滚动平均曲线可见，陆地温度异常的上升幅度明显高于海洋，二者的差异在近几十年中持续放大。这说明海洋作为巨大热容量缓冲体虽然也在变暖，但陆地受增温影响更强，表现出更明显的放大效应。该结果也解释了为什么全球平均温度变化中，陆地区域往往具有更强的变暖信号。

### 3. 月度热力图：从浅蓝到深红，全球变暖具有不可逆性

![月度热力图](outputs/figures/monthly_heatmap.png)

月度热力图从 1850s 到 2020s 逐步呈现出一个非常直观的变化：各月份的温度异常值由早期的浅蓝和偏冷色调，全面转变为后期的深红和强正异常。该图表明全球各月份在过去一个半世纪中普遍偏暖，且暖异常的强度在逐步增强，清晰体现了全球变暖的长期不可逆性。

### 4. 滚动回测预测对比 (Rolling-Origin Forecast)
![Forecast Comparison](outputs/figures/forecast_comparison.png)
构建了 Rolling-Origin 回测框架，对比了季节性朴素、Drift、SARIMAX 和 LightGBM。结果显示，在 24 个月的长期预测中，SARIMAX 更好地捕捉了季节性波动和置信区间，而 LightGBM 由于递归预测的误差累积，表现出过度平滑的现象。

## 项目结构与技术栈

### 项目结构

```text
CLMTA/
├── data/
│   ├── data.csv          # 全球陆海主数据
│   ├── land.csv          # 全球陆地数据
│   ├── ocean.csv         # 全球海洋数据
│   ├── clmta.duckdb      # make db 生成的 DuckDB 数据仓库
│   ├── metadata.json     # 数据来源、校验记录和版本信息
│   └── raw/              # NOAA 原始 CSV 快照
├── outputs/
│   └── figures/          # STL、热力图和对比图输出目录
├── scripts/
│   ├── update_data.py    # 数据下载与校验脚本
│   ├── build_db.py       # raw -> staging -> marts 构建脚本
│   ├── analyze.py        # 时间序列分析与绘图脚本
│   └── ...
├── tests/                # 自动化测试
├── Makefile              # 常用命令入口
├── README.md             # 项目说明
├── pyproject.toml        # Python 依赖与工具配置
├── PLAN.md               # 项目规划
├── docs/                 # 文档与架构说明
└── src/                  # 后续开发代码目录
```

### 技术栈

- Python 3.12：核心开发语言。
- uv：依赖与环境管理。
- pandas：数据读取与清洗。
- DuckDB：本地分析型数据库，支撑 `raw / staging / marts` 三层结构。
- statsmodels：STL 时间序列分解。
- scipy：趋势检验与统计计算。
- ruptures：变点检测。
- seaborn / matplotlib：数据可视化。
- pytest / ruff：自动化测试与代码规范检查。

## 数据范围

- 数据来源：NOAA Climate at a Glance（CAG）
- 时间范围：1850-01 至 2026-09
- 基准期：1901-2000
- 数据单位：摄氏度（℃）
- 指标含义：月度温度异常值，相较于 1901-2000 参考期的同期平均偏差
- 主要区域：`Land_Ocean`、`Land`、`Ocean`

## Roadmap

下一阶段计划重点围绕以下两个方面展开：

1. 滚动回测与预测建模：
   - 引入 LightGBM 作为基线预测模型；
   - 结合 Chronos 等时间序列模型进行对比实验；
   - 构建统一的滚动窗口回测流程与评估指标体系。

2. 交互式分析看板：
   - 使用 Streamlit 构建可视化仪表盘；
   - 支持趋势分析、突变点展示、区域对比和预测结果交互；
   - 提供可复现的研究与展示入口。

当前项目已完成数据管道、仓库构建和核心分析，可基于此继续扩展模型预测与交互式展示能力。

## 数据来源与许可

数据来自 [NOAA Climate at a Glance](https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series)。使用或再发布数据时，请保留 NOAA 的来源说明，并以官方页面为准。

代码和项目文档的许可信息仍在完善中，欢迎通过 Issue 或 Pull Request 交流问题和改进建议。
