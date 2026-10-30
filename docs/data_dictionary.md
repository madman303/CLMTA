# ClimateScope 数据字典

本文件描述 `data/clmta.duckdb` 中的数仓结构。数据库由 `make db` 从 `data/metadata.json` 和 `data/raw/` 中的原始 NOAA 快照构建。

```text
data/raw/*.csv  →  raw  →  staging  →  marts
```

- 数据来源：NOAA NCEI Climate at a Glance（全球陆海 / 陆地 / 海洋月度温度异常）
- 基准期：1901–2000
- 单位：°C（相对基准期的偏差，不是绝对温度）
- 当前覆盖：1850-01 ~ 2026-09，三条序列各 2,121 行
- 构建命令：`make db`

## 表总览

| 层 | 表 | 粒度 | 行数 | 说明 |
| --- | --- | --- | --- | --- |
| raw | `raw.series_metadata` | 每条序列一行 | 3 | 来源 URL、sha256、行数、时间范围、原始文件名 |
| raw | `raw.observations` | 序列 × 月 | 6,363 | 直接读取 `data/raw/` 中的 NOAA 原始快照 |
| staging | `staging.observations` | 序列 × 月 | 6,363 | 类型化：`date_int` 转成 `obs_date` |
| marts | `marts.monthly_anomaly` | 序列 × 月 | 6,363 | 分析主表，补充 `year`、`month`，字段统一为小写 |

三条序列：`land_ocean`（全球陆海）、`land`（陆地）、`ocean`（海洋）。

## raw.series_metadata

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `series` | VARCHAR | 序列 ID：`land_ocean` / `land` / `ocean`，主键 |
| `sha256` | VARCHAR | 原始 NOAA CSV 的 sha256 |
| `row_count` | INTEGER | 原始文件的数据行数 |
| `first_month` | VARCHAR | 起始月份，如 `1850-01` |
| `last_month` | VARCHAR | 最新月份，如 `2026-09` |
| `base_period` | VARCHAR | 基准期，固定为 `1901-2000` |
| `source_url` | VARCHAR | NOAA 官方下载地址 |
| `raw_file` | VARCHAR | `data/raw/` 下的原始文件名 |
| `updated_at` | VARCHAR | 最近一次 `make data` 的时间 |

## raw.observations

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `series` | VARCHAR | 序列 ID |
| `date_int` | INTEGER | `YYYYMM`，如 `202609` |
| `anomaly` | DOUBLE | 原始温度异常值（°C） |
| `source_file` | VARCHAR | 来源原始文件名 |

原始 NOAA 文件头部的 `#` 注释会被 DuckDB 的 `comment='#'` 跳过；列名 `Departure from Average` 在入库时改名为 `anomaly`。

## staging.observations

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `series` | VARCHAR | 序列 ID |
| `date_int` | INTEGER | `YYYYMM` |
| `obs_date` | DATE | 该月第一天，如 `2026-09-01` |
| `anomaly` | DOUBLE | 温度异常值（°C） |
| `source_file` | VARCHAR | 来源原始文件名 |

## marts.monthly_anomaly

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `series` | VARCHAR | 序列 ID：`land_ocean` / `land` / `ocean` |
| `date_int` | INTEGER | `YYYYMM` |
| `obs_date` | DATE | 该月第一天 |
| `year` | INTEGER | 年份 |
| `month` | INTEGER | 月份，1–12 |
| `anomaly` | DOUBLE | 温度异常值（°C） |

分析时优先使用 `marts.monthly_anomaly`；需要追溯来源时 join `raw.series_metadata`。

## 数据质量规则

`make db` 在提交事务前会检查以下条件，任一失败则回滚：

- `raw` / `staging` / `marts` 三层行数一致；
- 每条序列的行数与 `metadata.json` 的 `rows` 一致；
- `obs_date` 与 `anomaly` 无空值；
- 每条序列的起始月为 `1850-01`，结束月与 `metadata.json` 的 `last_month` 一致；
- 只加载 `metadata.json` 中登记的三条序列。

上游 `make data` 还会检查：基准期、起始月份、数值类型、`-999`、值域、断月、重复月份、倒序和新鲜度。

## 使用注意

- **2026 年只有 1–9 月**。做年度排名时要排除不完整年份：

```sql
SELECT year, ROUND(AVG(anomaly), 2) AS avg_anomaly
FROM marts.monthly_anomaly
WHERE series = 'land_ocean'
GROUP BY year
HAVING COUNT(*) = 12
ORDER BY avg_anomaly DESC
LIMIT 5;
```

- 温度异常有负值，表示比 1901–2000 年同期平均更冷，不代表绝对温度。
- 1880 年以前海洋观测稀疏，早期数据不确定性更大。
- 全球均值会掩盖区域差异；后续会加入半球和纬度带序列。

## 常用查询

```sql
-- 最近 3 个月
SELECT date_int, anomaly
FROM marts.monthly_anomaly
WHERE series = 'land_ocean'
ORDER BY obs_date DESC
LIMIT 3;

-- 2015–2024 年陆地 vs 海洋
SELECT series, ROUND(AVG(anomaly), 2) AS avg_anomaly
FROM marts.monthly_anomaly
WHERE year BETWEEN 2015 AND 2024
  AND series IN ('land', 'ocean')
GROUP BY series
ORDER BY series;

-- 数据来源追溯
SELECT series, sha256, row_count, first_month, last_month, source_url
FROM raw.series_metadata;
```

更多示例见 `scripts/queries.py`，运行 `make query`。

## 重建

```bash
make data   # 从 NOAA 更新 CSV、raw 快照和 metadata.json
make db     # 重建 data/clmta.duckdb（raw → staging → marts）
make query  # 运行示例查询
```
