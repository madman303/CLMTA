import duckdb
import pandas as pd
from pathlib import Path

# 路径定义
DATA_DIR = Path("data")
DB_PATH = DATA_DIR / "clmta.duckdb"

def build_database():
    print("==> 正在连接 DuckDB...")
    # 连接到本地数据库文件（如果不存在会自动创建）
    con = duckdb.connect(str(DB_PATH))
    
    # 1. 建立 staging 层（直接把干净的 CSV 读进来）
    print("==> 正在加载数据到 staging 层...")
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_land_ocean AS 
        SELECT * FROM read_csv_auto('{DATA_DIR}/data.csv')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_land AS 
        SELECT * FROM read_csv_auto('{DATA_DIR}/land.csv')
    """)
    con.execute(f"""
        CREATE OR REPLACE TABLE staging_ocean AS 
        SELECT * FROM read_csv_auto('{DATA_DIR}/ocean.csv')
    """)

    # 2. 建立 marts 层（清洗类型，增加日期维度）
    print("==> 正在构建 marts 分析表...")
    # 在 SQL 里把 185001 转换成真正的 DATE 格式 (1850-01-01)，并提取年和月
    query_mart = """
        CREATE OR REPLACE TABLE mart_monthly_anomaly AS
        WITH base AS (
            SELECT 'Land_Ocean' AS region, * FROM staging_land_ocean
            UNION ALL
            SELECT 'Land' AS region, * FROM staging_land
            UNION ALL
            SELECT 'Ocean' AS region, * FROM staging_ocean
        )
        SELECT 
            region,
            CAST(Date AS VARCHAR) AS date_int,
            strptime(CAST(Date AS VARCHAR), '%Y%m') AS obs_date,
            CAST(strftime(strptime(CAST(Date AS VARCHAR), '%Y%m'), '%Y') AS INT) AS year,
            CAST(strftime(strptime(CAST(Date AS VARCHAR), '%Y%m'), '%m') AS INT) AS month,
            Anomaly
        FROM base
    """
    con.execute(query_mart)
    
    print("✅ 数仓构建完成！")
    con.close()

if __name__ == "__main__":
    build_database()