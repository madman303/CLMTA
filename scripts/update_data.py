import requests
import pandas as pd
import hashlib
import json
import argparse
from pathlib import Path
from datetime import datetime
from io import StringIO

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
TARGET_FILE = DATA_DIR / "data.csv"
METADATA_FILE = DATA_DIR / "metadata.json"

# 动态获取当前年份，URL 不会因为到了 2027 年而失效
CURRENT_YEAR = datetime.now().year
BASE_URL = f"https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/global/time-series/globe/{{}}/1/0/1850-{CURRENT_YEAR}/data.csv"
SERIES = ["land_ocean", "land", "ocean"]

RAW_DIR.mkdir(parents=True, exist_ok=True)

def get_sha256(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def parse_and_validate(raw_text, series_name):
    """解析并执行严格的数据校验"""
    # 1. 提取并校验基准期
    if "1901-2000" not in raw_text.split("\n")[2]:
        raise ValueError("❌ 校验失败：基准期不是 1901-2000")
        
    # 2. 解析数据 (使用 comment="#"，自动忽略所有 # 开头的行，第一行非注释自动作为表头)
    df = pd.read_csv(StringIO(raw_text), comment="#", names=["Date", "Anomaly"])
    
    # 3. 显式检查空值（替代 .dropna()）
    if df.isna().any().any():
        raise ValueError(f"❌ 校验失败：包含空值 (NaN)")
        
    # 4. 基础行数与起始月校验
    if len(df) < 1000:
        raise ValueError(f"❌ 校验失败：行数异常({len(df)})，可能下载不完整")
    if int(df["Date"].iloc[0]) != 185001:
        raise ValueError("❌ 校验失败：起始月份不是 1850-01")
        
    # 5. 数值类型与 -999 校验
    try:
        df["Anomaly"] = df["Anomaly"].astype(float)
    except ValueError:
        raise ValueError("❌ 校验失败：包含无法转换为数字的异常值")
    if (df["Anomaly"] == -999.0).any():
        raise ValueError("❌ 校验失败：数据中混入 -999 缺失值标记")
    if not df["Anomaly"].between(-5, 5).all():
        raise ValueError("❌ 校验失败：温度值域超出正常范围 [-5, 5]")

    # 6. 断月、重复与倒序校验
    dates = pd.to_datetime(df["Date"].astype(str), format="%Y%m")
    if not dates.is_monotonic_increasing:
        raise ValueError("❌ 校验失败：日期不是递增的（存在倒序）！")
    if dates.duplicated().any():
        raise ValueError("❌ 校验失败：存在重复月份！")
    if not (dates.diff().dropna().dt.days <= 31).all():
        raise ValueError("❌ 校验失败：数据存在断月！")
        
    # 7. 新鲜度校验
    latest_date = dates.iloc[-1]
    if (pd.Timestamp.now() - latest_date).days > 90:
        raise ValueError(f"❌ 校验失败：数据太旧，最新只到 {latest_date.strftime('%Y-%m')}")

    return df, latest_date.strftime("%Y-%m")

def run(dry_run=False):
    metadata = {}
    print(f"==> 开始处理，{'[DRY RUN] ' if dry_run else ''}正在下载数据...")
    
    # 先读取旧 metadata 用于防回退校验
    old_meta = {}
    if METADATA_FILE.exists():
        old_meta = json.loads(METADATA_FILE.read_text(encoding="utf-8")).get("series", {})

    # 阶段一：下载并校验所有数据（只放内存，不落盘）
    downloaded_data = {}
    for series in SERIES:
        url = BASE_URL.format(series)
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        raw_text = response.text
        new_hash = get_sha256(raw_text)
        
        print(f"[{series}] 下载完成，SHA256: {new_hash[:8]}...")
        df, last_month = parse_and_validate(raw_text, series)
        
        # 防回退校验（无论是 dry-run 还是正式跑，都要校验）
        if series in old_meta:
            old_last = old_meta[series]["last_month"]
            if last_month < old_last:
                raise ValueError(f"❌ 校验失败：新数据({last_month})比旧数据({old_last})还旧，拒绝回退！")

        metadata[series] = {
            "sha256": new_hash,
            "rows": len(df),
            "first_month": "1850-01",
            "last_month": last_month,
            "base_period": "1901-2000",
            "source_url": url,
            "raw_file": f"noaa_{series}_{datetime.now().strftime('%Y%m%d')}.csv"
        }
        downloaded_data[series] = (df, raw_text)

    # 阶段二：全部校验通过后，统一落盘（保证事务性）
    if not dry_run:
        print("==> 所有校验通过，正在写入本地...")
        for series in SERIES:
            df, raw_text = downloaded_data[series]
            # 存 raw
            (RAW_DIR / metadata[series]["raw_file"]).write_text(raw_text, encoding='utf-8')
            # 存数据
            if series == "land_ocean":
                df.to_csv(TARGET_FILE, index=False)
            else:
                df.to_csv(DATA_DIR / f"{series}.csv", index=False)

        # 写入 metadata
        final_meta = {
            "updated_at": datetime.now().isoformat(),
            "series": metadata
        }
        METADATA_FILE.write_text(json.dumps(final_meta, indent=4), encoding="utf-8")
        print("✅ 数据更新与元数据记录全部完成！")
    else:
        print("✅ [DRY RUN] 校验全部通过，未写入任何文件。")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="更新并校验 NOAA 气候数据")
    parser.add_argument("--dry-run", action="store_true", help="只校验不落盘")
    args = parser.parse_args()
    
    run(dry_run=args.dry_run)