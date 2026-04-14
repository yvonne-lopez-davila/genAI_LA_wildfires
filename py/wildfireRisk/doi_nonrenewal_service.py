"""
California DOI Non-Renewal service.

Loads the CDI residential property insurance non-renewal dataset
and returns ZIP-level renewal/non-renewal trends.

Source: California Department of Insurance
https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

DATASET_DIR = Path(__file__).resolve().parent / "insurance_datasets"
CSV_PATH = DATASET_DIR / "coverage.csv"

_rows_by_zip: Optional[Dict[str, List[Dict]]] = None


def _parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    cleaned = str(value).strip().replace(",", "").replace("-", "").strip()
    if not cleaned:
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _load_rows() -> Dict[str, List[Dict]]:
    global _rows_by_zip

    if _rows_by_zip is not None:
        return _rows_by_zip

    _rows_by_zip = {}

    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            zipcode = str(row.get("ZIP Code", "")).strip().zfill(5)
            if not zipcode or zipcode == "00000":
                continue

            year = _parse_int(row.get("Year"))
            if not year:
                continue

            entry = {
                "county": str(row.get("County", "")).strip(),
                "year": year,
                "new": _parse_int(row.get("New")),
                "renewed": _parse_int(row.get("Renewed")),
                "non_renewed": _parse_int(row.get("Non-Renewed")),
            }

            _rows_by_zip.setdefault(zipcode, []).append(entry)

    # Sort each ZIP's records by year
    for zipcode in _rows_by_zip:
        _rows_by_zip[zipcode].sort(key=lambda r: r["year"])

    return _rows_by_zip


def _nonrenewal_rate(renewed