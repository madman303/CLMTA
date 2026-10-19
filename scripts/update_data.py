#!/usr/bin/env python3
"""Update CLMTA climate series from NOAA NCEI Climate at a Glance.

Design goals:
- Standard library only: runs even before the project environment exists.
- Idempotent: re-running produces the same files (network permitting).
- Auditable: keeps the raw bytes, sha256, retrieval time and row count.
- Safe: validates schema, contiguity, value range before overwriting data/data.csv.

Usage:
    python scripts/update_data.py            # fetch latest and update data/
    python scripts/update_data.py --dry-run  # validate only, write nothing
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
BASE_URL = (
    "https://www.ncei.noaa.gov/access/monitoring/climate-at-a-glance"
    "/global/time-series"
)
# series_id -> (path segment, human label)
SERIES = {
    "globe_land_ocean": ("globe/land_ocean", "Global land and ocean"),
    "globe_land": ("globe/land", "Global land"),
    "globe_ocean": ("globe/ocean", "Global ocean"),
}
HEADER_PREFIX = "# Title:"
VALUE_COLUMN = "Departure from Average"
MIN_VALUE, MAX_VALUE = -4.0, 4.0


def log(message: str) -> None:
    print(f"[update_data] {message}", flush=True)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(url: str, retries: int = 3, timeout: int = 60) -> bytes:
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(
            url,
            headers={"User-Agent": "CLMTA-data-bot/0.1 (educational project)"},
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"HTTP {response.status}")
                return response.read()
        except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
            last_error = exc
            if attempt < retries:
                wait = 2**attempt
                log(f"  retry {attempt}/{retries - 1} in {wait}s ({exc})")
                time.sleep(wait)
    raise RuntimeError(f"failed to fetch {url}: {last_error}")


def parse(text: str) -> tuple[list[tuple[int, int, float]], dict[str, str]]:
    """Return (year, month, value) rows plus the '#' metadata header."""
    lines = text.splitlines()
    meta: dict[str, str] = {}
    for line in lines:
        if not line.startswith("#"):
            continue
        body = line.lstrip("#").strip()
        if ":" in body:
            key, _, value = body.partition(":")
            meta[key.strip()] = value.strip().strip('"')
    data_lines = [line for line in lines if line and not line.startswith("#")]
    reader = csv.DictReader(data_lines)
    if reader.fieldnames is None or reader.fieldnames[0] != "Date":
        raise ValueError(f"unexpected columns: {reader.fieldnames}")

    rows: list[tuple[int, int, float]] = []
    for record in reader:
        raw_date = (record.get("Date") or "").strip()
        raw_value = (record.get(VALUE_COLUMN) or "").strip()
        if len(raw_date) != 6 or not raw_date.isdigit():
            raise ValueError(f"bad date: {raw_date!r}")
        year, month = int(raw_date[:4]), int(raw_date[4:])
        value = float(raw_value)
        if not 1 <= month <= 12:
            raise ValueError(f"bad month: {raw_date!r}")
        if value == -999:
            raise ValueError(f"missing-value sentinel found at {raw_date}")
        if not MIN_VALUE <= value <= MAX_VALUE:
            raise ValueError(f"value out of range at {raw_date}: {value}")
        rows.append((year, month, value))

    if len(rows) < 1000:
        raise ValueError(f"suspiciously few rows: {len(rows)}")

    expected = []
    year, month = rows[0][0], rows[0][1]
    last_year, last_month = rows[-1][0], rows[-1][1]
    while (year, month) <= (last_year, last_month):
        expected.append((year, month))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    actual = [(y, m) for y, m, _ in rows]
    if actual != expected:
        missing = sorted(set(expected) - set(actual))[:5]
        duplicated = len(actual) - len(set(actual))
        raise ValueError(f"non-contiguous series, missing={missing}, dup={duplicated}")

    return rows, meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="validate without writing")
    args = parser.parse_args()

    end_year = datetime.now(timezone.utc).year
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    # Keep the superseded snapshot for provenance (never delete source data).
    # This must happen before data/data.csv is overwritten.
    legacy = DATA_DIR / "data.csv"
    if legacy.exists() and not args.dry_run:
        legacy_bytes = legacy.read_bytes()
        legacy_rows, _ = parse(legacy_bytes.decode("utf-8-sig"))
        archive = (
            RAW_DIR
            / f"noaa_cag_globe_land_ocean_monthly_1850-{legacy_rows[-1][0]}.csv"
        )
        if not archive.exists():
            archive.write_bytes(legacy_bytes)
            log(f"archived previous snapshot -> {archive.relative_to(ROOT)}")

    manifest: dict[str, dict] = {
        "generated_by": "scripts/update_data.py",
        "source": "NOAA NCEI Climate at a Glance",
        "source_url": BASE_URL,
        "license": "Public domain (U.S. Government work); attribution required",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "series": {},
    }

    for series_id, (path, label) in SERIES.items():
        url = f"{BASE_URL}/{path}/1/0/1850-{end_year}/data.csv"
        log(f"fetching {label}: {url}")
        payload = fetch(url)
        text = payload.decode("utf-8-sig")
        rows, meta = parse(text)

        first = f"{rows[0][0]}-{rows[0][1]:02d}"
        last = f"{rows[-1][0]}-{rows[-1][1]:02d}"
        raw_name = f"noaa_cag_{series_id}_monthly_1850-{rows[-1][0]}.csv"
        log(f"  {len(rows)} rows, {first} .. {last}, base={meta.get('Base Period')}")

        if not args.dry_run:
            (RAW_DIR / raw_name).write_bytes(payload)
            if series_id == "globe_land_ocean":
                (DATA_DIR / "data.csv").write_bytes(payload)

        manifest["series"][series_id] = {
            "label": label,
            "url": url,
            "raw_file": f"data/raw/{raw_name}",
            "sha256": sha256(payload),
            "rows": len(rows),
            "first_month": first,
            "last_month": last,
            "base_period": meta.get("Base Period"),
            "units": meta.get("Units", "Degrees Celsius"),
        }

    # Keep the superseded snapshot for provenance (never delete source data).
    if args.dry_run:
        log("dry-run: validation passed, nothing written")
        return 0

    (DATA_DIR / "metadata.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    log(f"wrote data/data.csv and data/metadata.json ({len(manifest['series'])} series)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - CLI entry point
        log(f"ERROR: {exc}")
        sys.exit(1)
