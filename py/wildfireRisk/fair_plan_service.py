"""
FAIR Plan ZIP lookup service.

Loads a pre-parsed local CSV derived from the California FAIR Plan
"Exposure Growth by Fiscal Year (Residential Line) - Data by ZIP Code" PDF.
https://www.cfpnet.com/wp-content/uploads/2025/11/CFP-5-yr-TIV-Zip-FY25-DWE-251114.pdf
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, Optional

DATASET_DIR = Path(__file__).resolve().parent / "insurance_datasets"
CSV_PATH = DATASET_DIR / "fair_plan_residential_exposure_zip.csv"
SOURCE_URL = (
    "https://www.cfpnet.com/wp-content/uploads/2025/11/"
    "CFP-5-yr-TIV-Zip-FY25-DWE-251114.pdf"
)
REPORT_AS_OF_DATE = "2025-09-30"

_rows_by_zip: Optional[Dict[str, Dict[str, str]]] = None


def _load_rows() -> Dict[str, Dict[str, str]]:
    global _rows_by_zip

    if _rows_by_zip is None:
        with CSV_PATH.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            _rows_by_zip = {
                str(row["zipcode"]).strip().zfill(5): row
                for row in reader
                if row.get("zipcode")
            }

    return _rows_by_zip


def _parse_amount(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None

    cleaned = str(value).strip().replace(",", "")
    if not cleaned or cleaned == "-":
        return None

    return int(cleaned)


def _pct_change(old: Optional[int], new: Optional[int]) -> Optional[float]:
    if old in (None, 0) or new is None:
        return None
    return round(((new - old) / old) * 100, 1)


def get_fair_plan_status(zipcode: str) -> Dict[str, Any]:
    """
    Return FAIR Plan residential exposure status for a ZIP code.

    Important caveat:
    This dataset shows observed FAIR Plan residential exposure in a ZIP, not a
    legal eligibility determination for an individual property.
    """
    zipcode = str(zipcode).strip().zfill(5)

    try:
        rows = _load_rows()
    except FileNotFoundError:
        return {
            "found": False,
            "zipcode": zipcode,
            "error": f"FAIR Plan dataset not found at {CSV_PATH}",
            "source_url": SOURCE_URL,
        }
    except Exception as exc:
        return {
            "found": False,
            "zipcode": zipcode,
            "error": str(exc),
            "source_url": SOURCE_URL,
        }

    row = rows.get(zipcode)
    if not row:
        return {
            "found": False,
            "zipcode": zipcode,
            "covered_by_fair_plan": False,
            "source_url": SOURCE_URL,
            "report_as_of": REPORT_AS_OF_DATE,
            "notes": (
                "ZIP not present in the current FAIR Plan residential exposure report. "
                "Treat this as no reported FAIR Plan residential exposure in the dataset, "
                "not a definitive eligibility denial."
            ),
        }

    exposure_history = {
        "2021": _parse_amount(row.get("fy2021_exposure")),
        "2022": _parse_amount(row.get("fy2022_exposure")),
        "2023": _parse_amount(row.get("fy2023_exposure")),
        "2024": _parse_amount(row.get("fy2024_exposure")),
        "2025": _parse_amount(row.get("fy2025_exposure")),
    }
    yoy_growth = {
        "2022": row.get("fy2022_yoy_growth"),
        "2023": row.get("fy2023_yoy_growth"),
        "2024": row.get("fy2024_yoy_growth"),
        "2025": row.get("fy2025_yoy_growth"),
    }

    latest_total_exposure = exposure_history["2025"]
    earliest_total_exposure = exposure_history["2021"]
    # returns structured FAIR Plan residential exposure info for the ZIP,
    # including whether any exposure is reported in the latest fiscal year
    return {
        "found": True,
        "zipcode": zipcode,
        "covered_by_fair_plan": bool(latest_total_exposure and latest_total_exposure > 0),
        "latest_fiscal_year": 2025,
        "latest_total_exposure": latest_total_exposure,
        "exposure_history": exposure_history,
        "yoy_growth": yoy_growth,
        "five_year_pct_change": _pct_change(earliest_total_exposure, latest_total_exposure),
        "report_as_of": REPORT_AS_OF_DATE,
        "source_url": SOURCE_URL,
        "notes": (
            "This indicates FAIR Plan residential exposure was reported in the ZIP. "
            "It is useful as an insurance-market signal, but it is not a property-level "
            "coverage guarantee."
        ),
    }
