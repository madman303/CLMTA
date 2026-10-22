# ClimateScope (CLMTA)

ClimateScope（项目名：CLMTA）是一个面向月度全球气候指标的可复现数据分析与预测项目。项目当前围绕全球陆地—海洋月度温度异常数据，先建设可靠的数据管道和数仓，再逐步加入统计分析、预测回测和可视化功能。

这是一个仍在持续开发中的开源项目。当前已完成数据获取、校验、版本记录和 DuckDB 数仓分层，后续功能会在数据基础稳定后逐步实现。

## 当前数据范围

- **数据来源**：NOAA Climate at a Glance（CAG）
- **时间范围**：1850-01 至 2026-09
- **基准期**：1901-2000
- **数据单位**：摄氏度（℃）
- **指标含义**：相对于基准期同期平均值的月度温度异常，而不是绝对温度
- **序列**：全球陆海（`land_ocean`）、陆地（`land`）、海洋（`ocean`）

当前主数据位于 [`data/data.csv`](data/data.csv)，陆地/海洋数据位于 [`data/land.csv`](data/land.csv) 和 [`data/ocean.csv`](data/ocean.csv)，原始快照和元数据位于 [`data/raw/`](data/raw/) 与 [`data/metadata.json`](data/metadata.json)。

## Quickstart

项目使用 Python 3.12 和 [uv](https://docs.astral.sh/uv/) 管理环境与依赖。克隆项目并进入仓库目录后，依次运行：

```bash
uv sync
make test
make data
make db
make query
```

命令说明：

1. `uv sync`：同步项目依赖和虚拟环境；
2. `make test`：运行 Ruff 代码规范检查和 pytest 测试；
3. `make data`：从 NOAA 更新 CSV、raw 快照和 `metadata.json`；
4. `make db`：重建 `data/clmta.duckdb`（raw → staging → marts）；
5. `make query`：运行示例 SQL 查询。

也可以运行 `make pipeline` 一次完成 `data` + `db`。

## 数据仓库

`make db` 会构建三层结构：

| 层 | 表 | 说明 |
| --- | --- | --- |
| raw | `raw.series_metadata`、`raw.observations` | 来源、sha256、原始快照数据 |
| staging | `staging.observations` | 类型化，生成 `obs_date` |
| marts | `marts.monthly_anomaly` | 分析主表，含 `year`、`month`、`anomaly` |

三条序列各 2,121 行，`marts.monthly_anomaly` 共 6,363 行。字段、类型和数据质量规则见 [`docs/data_dictionary.md`](docs/data_dictionary.md)。

```sql
SELECT year, ROUND(AVG(anomaly), 2) AS avg_anomaly
FROM marts.monthly_anomaly
WHERE series = 'land_ocean'
GROUP BY year
HAVING COUNT(*) = 12
ORDER BY avg_anomaly DESC
LIMIT 5;
```

> 2026 年只有 1–9 月，做年度排名时用 `HAVING COUNT(*) = 12` 排除不完整年份。

## 技术栈

| 技术 | 用途 | 状态 |
| --- | --- | --- |
| Python 3.12 | 项目开发语言 | 当前使用 |
| uv | 环境与依赖管理 | 当前使用 |
| Makefile | 常用开发命令入口 | 当前使用 |
| pandas | 数据读取与处理 | 当前使用 |
| DuckDB | 分析型数据处理与数仓 | 当前使用 |
| pytest | 自动化测试 | 当前使用 |
| ruff | 代码规范检查 | 当前使用 |
| Streamlit | 交互式数据可视化 | 规划中 |

## 项目进度（Roadmap）

当前已完成**第一阶段：数据管道 + 数仓分层**：从 NOAA CAG 获取数据，完成校验，保存原始快照，记录来源和版本信息，并构建 raw / staging / marts 三层 DuckDB 数仓。

后续计划包括：

1. **STL 分析**：对月度温度异常进行趋势和季节性分解；
2. **预测模型回测**：对比 6 个候选模型，并建立统一的滚动回测流程；
3. **Streamlit 可视化**：提供数据概览、趋势分析和预测结果展示；
4. **LLM 问答助手**：在数据和分析结果的基础上，探索面向项目数据的问答功能。

以上功能尚未全部实现，项目不会在当前阶段预先给出模型准确率或其他尚未验证的指标。

## 项目结构

```text
CLMTA/
├── data/
│   ├── data.csv          # 全球陆海主数据
│   ├── land.csv          # 全球陆地数据
│   ├── ocean.csv         # 全球海洋数据
│   ├── metadata.json     # 来源、sha256、行数、时间范围
│   ├── clmta.duckdb      # make db 生成的数仓
│   └── raw/              # NOAA 原始快照
├── docs/
│   ├── data_dictionary.md
│   └── ...               # 方案书与架构图
├── scripts/
│   ├── update_data.py    # 数据更新与校验
│   ├── build_db.py       # raw → staging → marts
│   └── queries.py        # 示例 SQL
├── src/                  # 项目源代码
├── tests/                # 自动化测试
├── Makefile              # 常用命令
├── PLAN.md               # 项目规划
└── pyproject.toml        # Python 项目配置
```

## 数据说明

数据记录的是全球陆地与海洋的月度温度异常。例如，某个月的值为 `1.33`，表示该月温度比 1901-2000 年基准期的同期平均值高 1.33 ℃。

温度异常不能直接当作绝对气温使用。早期观测资料相对有限，使用数据进行分析时也应注意数据覆盖范围和历史数据修订的影响。NOAA 可能会调整历史数据，因此项目会保留原始快照，并记录更新后的元数据。

## 数据来源与许可

数据来自 [NOAA Climate at a Glance](https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series)。使用或再发布数据时，请保留 NOAA 的来源说明，并以官方页面为准。

代码和项目文档的许可信息仍在完善中。欢迎通过 Issue 或 Pull Request 交流问题和改进建议。
