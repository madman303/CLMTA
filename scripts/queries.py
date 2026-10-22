import duckdb
con = duckdb.connect("data/clmta.duckdb")

# 核心 SQL 1：最近的全球陆海温度异常是多少？
print("=== 最近 3 个月全球温度 ===")
print(con.execute("""
    SELECT date_int, Anomaly 
    FROM mart_monthly_anomaly 
    WHERE region = 'Land_Ocean' 
    ORDER BY obs_date DESC LIMIT 3
""").df())

# 核心 SQL 2：2023年是有记录以来最热的年份吗？（看前5名）
print("\n=== 最热年份 Top 5 ===")
print(con.execute("""
    SELECT year, ROUND(AVG(Anomaly), 2) as avg_temp
    FROM mart_monthly_anomaly 
    WHERE region = 'Land_Ocean' 
    GROUP BY year 
    ORDER BY avg_temp DESC LIMIT 5
""").df())

# 核心 SQL 3：陆地 vs 海洋 近10年的平均升温差异
print("\n=== 2015-2024年 陆地与海洋平均温度 ===")
print(con.execute("""
    SELECT region, ROUND(AVG(Anomaly), 2) as avg_temp
    FROM mart_monthly_anomaly 
    WHERE year >= 2015 AND region IN ('Land', 'Ocean')
    GROUP BY region
""").df())