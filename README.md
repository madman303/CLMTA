# CLMTA / ClimateScope

> 全球陆地—海洋月度温度异常（1850–2026）的可复现数据仓库，以及后续的统计分析与预测项目。

**当前状态**：数据层已完成，数据更新至 **2026-09**（2,121 条）。统计分析、预测基准、可视化与 AI 问答尚未开始，计划见 [路线图](#路线图)。

**文档**：[方案书 PDF](docs/CLMTA-方案-v3.pdf) · [方案书 Word](docs/CLMTA-方案-v3.docx) · [完整规划 PLAN.md](PLAN.md) · [系统架构图](docs/architecture.png)

**目录**

- [一分钟理解这个项目](#一分钟理解这个项目)
- [现在仓库里有什么](#现在仓库里有什么)
- [快速开始](#快速开始)
- [数据说明](#数据说明)
- [数据质量与版本](#数据质量与版本)
- [更新数据](#更新数据)
- [目录结构](#目录结构)
- [路线图](#路线图)
- [常见问题](#常见问题)
- [数据来源与许可](#数据来源与许可)
- [English](#english)

---

## 一分钟理解这个项目

把地球的平均气温想象成一条 175 年的“体温曲线”。这份数据记录的不是每个月的绝对温度，而是**每个月比“正常体温”高或低多少度**——这里的“正常体温”是 1901–2000 年的平均值，单位是 °C。

例如 `202609,1.33` 表示：2026 年 9 月，全球陆地与海洋的平均气温比 1901–2000 年同期平均高 **1.33 °C**。

项目分两个名字、两个阶段：

| 名字 | 阶段 | 负责什么 |
| --- | --- | --- |
| **CLMTA** | 现在 | 数据获取、校验、版本管理（本仓库已完成） |
| **ClimateScope** | 后续 | 统计分析、预测对比、可视化、LLM 问答（规划中） |

**为什么做这个项目**：

1. 175 年连续月度数据，趋势、季节性、极端事件都能练；
2. NOAA 公开数据、可程序化更新，适合练习“可复现数据管道”；
3. 作为数据 + AI 方向的作品集，后续可以接统计分析、时间序列预测和 LLM 工具调用。

**最终形态**：

```text
数据更新 → 质量校验 → 统计分析 → 预测对比 → 网页展示 → 对话式查询
```

**这个项目能练到什么**：数据工程（采集、校验、版本化）、统计诊断（趋势、季节、变点）、预测评估（回测、区间、显著性）、AI 应用（工具调用、评测）。

> 现在只完成了最左边两步：数据更新与质量校验。其余步骤见 [路线图](#路线图)。

## 现在仓库里有什么

| 内容 | 位置 | 状态 |
| --- | --- | --- |
| 主数据（全球陆海，2,121 条） | `data/data.csv` | 已完成 |
| 原始快照（陆地 / 海洋 / 旧版本） | `data/raw/` | 已完成 |
| 溯源信息（URL、sha256、行数、时间范围） | `data/metadata.json` | 已完成 |
| 数据更新与校验脚本 | `scripts/update_data.py` | 已完成 |
| 项目方案书（PDF / Word） | `docs/` | 已完成 |
| 统计分析（STL、趋势检验、变点、极值） | — | 计划中 |
| 预测基准（6 个模型 + 滚动回测） | — | 计划中 |
| Streamlit 可视化与公网 Demo | — | 计划中 |
| LLM 分析助手 | — | 计划中 |

> 仓库里目前**没有**分析代码、模型或网页。这不是遗漏，而是当前阶段只做数据层；先让数据可信、可复现，再往上搭。

## 快速开始

### 环境

- Python 3.9+
- 读取数据只需要标准库；用 pandas 更方便
- 画图需要 matplotlib（可选）

```bash
git clone <你的仓库地址>
cd CLMTA
python -m pip install pandas matplotlib   # 可选
```

### 用 pandas 读取

```python
import pandas as pd

df = pd.read_csv("data/data.csv", comment="#")
df["Date"] = pd.to_datetime(df["Date"].astype(str), format="%Y%m")
df = df.rename(columns={"Departure from Average": "anomaly"})

print(df.tail(3))
print(df["anomaly"].describe())

# 年度均值（pandas >= 2.2 用 "YE"；旧版本改成 "A"）
annual = df.set_index("Date")["anomaly"].resample("YE").mean()
print(annual.tail(10))

# 可选：画图
# annual.plot(title="Global land-ocean temperature anomaly", ylabel="°C vs 1901-2000")
# import matplotlib.pyplot as plt; plt.show()
```

### 不装 pandas 也能看

```python
import csv

with open("data/data.csv", encoding="utf-8") as f:
    rows = list(
        csv.DictReader(line for line in f if not line.startswith("#"))
    )

print(len(rows))      # 2121
print(rows[0])        # 1850-01
print(rows[-1])       # 2026-09
```

输出：

```text
2121
{'Date': '185001', 'Departure from Average': '-0.43'}
{'Date': '202609', 'Departure from Average': '1.33'}
```

## 数据说明

### 文件

| 文件 | 内容 |
| --- | --- |
| `data/data.csv` | 主序列：全球陆地 + 海洋月度温度异常，日常分析用这个 |
| `data/raw/noaa_cag_globe_land_ocean_monthly_1850-2026.csv` | 同上的原始快照，不可变 |
| `data/raw/noaa_cag_globe_land_monthly_1850-2026.csv` | 全球陆地序列 |
| `data/raw/noaa_cag_globe_ocean_monthly_1850-2026.csv` | 全球海洋序列 |
| `data/raw/noaa_cag_globe_land_ocean_monthly_1850-2024.csv` | 更新前的旧快照，用于版本对比 |
| `data/metadata.json` | 每个文件的来源、sha256、行数、时间范围、基准期 |

### 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `Date` | `YYYYMM` | 月份，例如 `202609` 表示 2026 年 9 月 |
| `Departure from Average` | float | 相对 1901–2000 基准期的温度异常，单位 °C |

> 注意列名是 `Departure from Average`，不是旧版 README 里写的 `Anomaly`。

### 关键事实

| 项目 | 数值 |
| --- | --- |
| 时间范围 | 1850-01 ~ 2026-09 |
| 记录数 | 2,121 |
| 缺失 / 重复 / 断月 | 0 / 0 / 0 |
| 数值范围 | −0.66 ~ 1.40 °C |
| 平均值 | 约 0.067 °C |
| 2025 年均值 | 1.12 °C |
| 2026 年 1–9 月均值 | 1.17 °C |
| 最新月份（2026-09） | 1.33 °C |
| 有记录以来最暖月份 | 2023-09（1.40 °C） |
| 1970–2026 线性趋势 | 约 +0.196 °C / 十年 |
| 2020–2026 年均值 | 1.06 °C |
| 1850 年代均值 | −0.10 °C |

### 使用注意

- **这是温度异常，不是绝对温度。** 负值表示比 1901–2000 年同期平均更冷，不代表“零下”。
- 1880 年以前海洋观测稀疏，早期数据的不确定性更大，做图表和结论时应标注。
- 2026 年只有 1–9 月，不能直接和完整年份做年度对比。
- 全球均值会掩盖区域差异；后续会加入陆地 / 海洋、南北半球和纬度带序列。
- NOAA 会回改历史值，所以仓库保留原始快照和更新时间。

## 数据质量与版本

`scripts/update_data.py` 在覆盖数据前会逐项检查：

- 表头必须是 `Date` 与 `Departure from Average`；
- 日期必须是 6 位 `YYYYMM`，月份在 1–12 之间；
- 月份必须连续，不能缺月或重复；
- 数值必须在 `[-4, 4]` 之间；
- 拒绝 `-999` 缺失标记；
- 行数不能少于 1000。

当前数据通过了全部检查。文件头仍保留 NOAA 的元数据（标题、单位、基准期），读取时用 `comment="#"` 跳过。

**为什么主数据和 raw 里有两份一样的文件？**

- `data/data.csv` 是稳定入口，后续分析和网页都读它；
- `data/raw/` 保存不可变的原始快照，用于回溯和对比；
- 更新时旧版本不会删除，而是归档成带年份的文件。

## 更新数据

```bash
python scripts/update_data.py            # 拉取最新并校验
python scripts/update_data.py --dry-run  # 只校验，不写文件
```

脚本只依赖 Python 标准库，执行流程：

1. 从 NOAA 拉取全球陆海、陆地、海洋三条月度序列；
2. 校验表头、日期连续性、值域和缺失标记；
3. 把旧的 `data/data.csv` 归档到 `data/raw/`；
4. 写入新的 `data/data.csv` 和 `data/metadata.json`。

NOAA 通常每月中旬发布上个月的数据；脚本可以随时重跑，重复执行结果一致。更新后如果数值有变化，先看 `metadata.json` 里的 `fetched_at` 和 `sha256`，再决定是否重新跑分析。

## 目录结构

```text
CLMTA/
├── README.md                  # 本文件
├── PLAN.md                    # 完整方案：调研、架构、六周计划、简历与面试
├── .gitignore
├── data/
│   ├── data.csv               # 主序列（分析用这个）
│   ├── metadata.json          # 来源、sha256、行数、时间范围
│   └── raw/                   # 原始快照，只增不删
├── docs/
│   ├── CLMTA-方案-v3.pdf      # 方案书 PDF（17 页）
│   ├── CLMTA-方案-v3.docx     # 方案书 Word
│   └── architecture.png       # 系统架构图
└── scripts/
    └── update_data.py         # 数据更新与校验（标准库实现）
```

## 路线图

| 阶段 | 内容 | 状态 |
| --- | --- | --- |
| 0. 数据层 | 多源采集、校验、溯源、增量更新 | 已完成 |
| 1. 统计分析 | STL 分解、Mann-Kendall、Theil-Sen、变点、极值 | 计划中（第 2 周） |
| 2. 预测基准 | 滚动回测、6 个模型、MASE / CRPS / 区间覆盖率 | 计划中（第 3–4 周） |
| 3. 可视化 | Streamlit 四页 + 公网部署 | 计划中（第 5 周） |
| 4. AI 助手 | DeepSeek 工具调用 + 评测集 | 计划中（第 6 周） |
| 5. 文档 | benchmark 报告、演示视频、英文 brief | 持续更新 |

### 技术栈

| 层 | 现在 | 后续计划 |
| --- | --- | --- |
| 数据获取 | Python 标准库 | 保持 |
| 数据处理 | `csv` / pandas | pandas + DuckDB + Parquet |
| 统计分析 | — | statsmodels、scipy、ruptures |
| 机器学习 | — | LightGBM |
| 基础模型 | — | Chronos-Bolt（零样本） |
| 可视化 | — | Streamlit + Plotly |
| LLM | — | DeepSeek function calling |
| 测试 / CI | — | pytest + ruff + GitHub Actions |

设计细节、技术选型、六周小时级计划和简历写法都在 [PLAN.md](PLAN.md)；也可以直接看 [方案书 PDF](docs/CLMTA-方案-v3.pdf)。

## 常见问题

**Q：温度异常为什么有负数？**
A：它是相对 1901–2000 年平均值的偏差。负值表示比基准期更冷，不是绝对温度为零下。

**Q：为什么 2026 年只有 9 个月？**
A：NOAA 按月发布，当前最新只到 2026-09；等官方更新后重跑脚本即可。

**Q：为什么 `data/data.csv` 和 raw 里的文件内容一样？**
A：一个是稳定入口，一个是不可变快照。分析只读 `data/data.csv`，回溯和对比看 `data/raw/`。

**Q：为什么现在没有分析代码和模型？**
A：当前阶段只做数据层。先把数据做成可复现、可追溯的，再往上搭统计分析和预测，避免“数据还没搞清楚就开始调模型”。

**Q：为什么不做深度学习？**
A：单变量 2,121 个点做深度学习容易过拟合，也很难讲清楚。后续会引入陆地 / 海洋、南北半球和 CO₂ / ENSO 协变量，再比较统计模型、LightGBM 和零样本基础模型。

**Q：为什么不用 Spark / Kafka？**
A：数据只有约 2 万行、月频更新，单机 DuckDB 足够；引入分布式组件只会增加运维成本。

**Q：NOAA 会修改历史数据吗？**
A：会。官方可能修订历史值，所以每次更新都保留原始快照，并在 `metadata.json` 里记录 sha256 和抓取时间。

**Q：我能直接用这份数据吗？**
A：可以。数据来自 NOAA，属于美国政府作品（公有领域），使用时注明来源即可，详见下一节。

**Q：旧版 README 里的 `global-temp-time-series.csv`、`Anomaly`、`-999` 是怎么回事？**
A：那是早期版本的说明，已经过时。当前文件名是 `data/data.csv`，列名是 `Departure from Average`；当前数据不含 `-999`，脚本仍会拒绝该标记。

## 数据来源与许可

| 序列 | 来源 | 文件 |
| --- | --- | --- |
| 全球陆海 | NOAA NCEI Climate at a Glance | `data/raw/noaa_cag_globe_land_ocean_monthly_1850-2026.csv` |
| 全球陆地 | NOAA NCEI Climate at a Glance | `data/raw/noaa_cag_globe_land_monthly_1850-2026.csv` |
| 全球海洋 | NOAA NCEI Climate at a Glance | `data/raw/noaa_cag_globe_ocean_monthly_1850-2026.csv` |

- 官方入口：<https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series>
- 基准期：1901–2000
- 数据许可：美国政府作品，公有领域（public domain），使用时需注明来源
- 抓取时间：2026-10-19（见 `data/metadata.json`）

**建议引用格式**：

```text
NOAA National Centers for Environmental Information, Climate at a Glance:
Global Time Series, retrieved 2026-10-19, from
https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series
```

后续计划接入（尚未完成）：NASA GISTEMP v4、NOAA Mauna Loa CO₂、NOAA CPC ONI、SILSO 太阳黑子。

> 代码部分暂未添加 `LICENSE` 文件；如需复用代码，请先联系仓库作者。

## English

CLMTA is a reproducible monthly global land–ocean temperature anomaly dataset covering 1850–2026, sourced from NOAA NCEI Climate at a Glance. The repository currently contains the data pipeline, provenance metadata, and the project plan; statistical analysis, forecasting benchmarks, a Streamlit app, and an LLM assistant are planned.

- `data/data.csv`: 2,121 monthly records, 1850-01 to 2026-09
- `data/raw/`: immutable source snapshots (land–ocean, land, ocean, and a 2024 snapshot)
- `scripts/update_data.py`: dependency-free fetch and validation
- `PLAN.md`: research notes, architecture, six-week roadmap, and resume/interview prep

Data are public domain (U.S. Government work); attribution to NOAA NCEI is required.
