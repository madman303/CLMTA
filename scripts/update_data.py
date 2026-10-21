#!/usr/bin/env python3
"""Download and validate the NOAA CAG global land-ocean temperature series."""

from __future__ import annotations

import csv
import hashlib
import io
import re
import tempfile
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
OUTPUT_FILE = DATA_DIR / "data.csv"
URL = (
    "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance/"
    "global/time-series/globe/land_ocean/1/0/1850-2026/data.csv"
)
EXPECTED_BASE_PERIOD = "1901-2000"
EXPECTED_FIELDS = ["Date", "Departure from Average"]


def download() -> bytes:
    request = urllib.request.Request(
        URL,
        headers={"User-Agent": "CLMTA-data-updater/1.0"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def subtract_months(year: int, month: int, months: int) -> tuple[int, int]:
    month_index = year * 12 + month - 1 - months
    return month_index // 12, month_index % 12 + 1


def parse_and_validate(payload: bytes, today: date) -> list[list[str]]:
    text = payload.decode("utf-8-sig")
    if not re.search(
        rf"Base Period\s*:\s*{re.escape(EXPECTED_BASE_PERIOD)}\b",
        text,
        re.IGNORECASE,
    ):
        raise ValueError(
            f"invalid or missing base period; expected {EXPECTED_BASE_PERIOD}"
        )

    lines = text.splitlines()
    header = ",".join(EXPECTED_FIELDS)
    header_index = next(
        (index for index, line in enumerate(lines[:5]) if line.strip() == header),
        None,
    )
    if header_index is None or header_index == len(lines) - 1:
        raise ValueError("downloaded CSV has no data after its metadata header")

    reader = csv.DictReader(io.StringIO("\n".join(lines[header_index:])))
    if reader.fieldnames != EXPECTED_FIELDS:
        raise ValueError(
            f"unexpected CSV columns: {reader.fieldnames!r}; "
            f"expected {EXPECTED_FIELDS!r}"
        )

    rows: list[list[str]] = []
    previous_month: tuple[int, int] | None = None
    for record in reader:
        raw_date = (record.get("Date") or "").strip()
        value = (record.get("Departure from Average") or "").strip()
        if not re.fullmatch(r"\d{6}", raw_date):
            raise ValueError(f"invalid date value: {raw_date!r}")
        year, month = int(raw_date[:4]), int(raw_date[4:])
        if not 1 <= month <= 12:
            raise ValueError(f"invalid month in date: {raw_date!r}")
        if not value:
            raise ValueError(f"missing temperature anomaly at {raw_date}")

        current_month = (year, month)
        if previous_month is not None:
            expected_month = subtract_months(*current_month, 1)
            if previous_month != expected_month:
                raise ValueError(
                    f"non-contiguous dates: {previous_month[0]:04d}"
                    f"{previous_month[1]:02d} -> {raw_date}"
                )
        previous_month = current_month
        rows.append([raw_date, value])

    if not rows:
        raise ValueError("CSV contains no data rows")

    latest_year, latest_month = map(int, (rows[-1][0][:4], rows[-1][0][4:]))
    minimum_year, minimum_month = subtract_months(today.year, today.month, 3)
    if (latest_year, latest_month) < (minimum_year, minimum_month):
        raise ValueError(
            f"data is stale: latest month is {rows[-1][0]}, "
            f"which is earlier than {minimum_year:04d}{minimum_month:02d}"
        )
    return rows


def write_standard_csv(rows: list[list[str]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            newline="",
            dir=DATA_DIR,
            prefix=".data-",
            suffix=".csv",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            writer = csv.writer(temporary, lineterminator="\n")
            writer.writerow(EXPECTED_FIELDS)
            writer.writerows(rows)
        temporary_path.replace(OUTPUT_FILE)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main() -> None:
    today = date.today()
    payload = download()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_file = RAW_DIR / f"land_ocean_{today:%Y%m%d}.csv"
    raw_file.write_bytes(payload)

    digest = sha256(payload)
    print(f"sha256: {digest}")
    rows = parse_and_validate(payload, today)
    write_standard_csv(rows)
    print("更新成功")


if __name__ == "__main__":
    main()

