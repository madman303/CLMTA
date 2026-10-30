"""Download CO2 and ENSO covariates from their public NOAA sources."""

from io import StringIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "covariates"
CO2_URL = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_mm_mlo.csv"
ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"


def download_text(url: str) -> str:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def download_co2() -> pd.DataFrame:
    return pd.read_csv(StringIO(download_text(CO2_URL)), comment="#")


def download_oni() -> pd.DataFrame:
    return pd.read_csv(
        StringIO(download_text(ONI_URL)),
        sep=r"\s+",
        skiprows=1,
        names=["SEAS", "YR", "TOTAL", "ANOM"],
    )


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    co2 = download_co2()
    oni = download_oni()

    co2_path = OUTPUT_DIR / "co2_mm_mlo.csv"
    oni_path = OUTPUT_DIR / "oni.csv"
    co2.to_csv(co2_path, index=False)
    oni.to_csv(oni_path, index=False)

    print(f"Saved {len(co2)} CO2 rows to {co2_path}")
    print(f"Saved {len(oni)} ONI rows to {oni_path}")


if __name__ == "__main__":
    main()
  