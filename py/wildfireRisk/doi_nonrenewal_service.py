"""
California DOI Non-Renewal service.

Loads the CDI residential property insurance non-renewal dataset
and returns ZIP-level renewal/non-renewal trends.

Source: California Department of Insurance
https://www.insurance.ca.gov/01-consumers/200-wrr/DataAnalysisOnWildfiresAndInsurance.cfm
"""

from __future__ import annotations
import pandas as pd

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional

DATASET_DIR = Path(__file__).resolve().parent / "insurance_datasets"
XLSX_PATH = DATASET_DIR / "insurance_renewal_DOI_data.xlsx"

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


import pandas as pd

def _load_rows():
    global _rows_by_zip

    if _rows_by_zip is not None:
        return _rows_by_zip

    df = pd.read_excel(XLSX_PATH, na_values=["-"])

    # Normalize columns
    df.columns = [c.strip() for c in df.columns]

    # Clean fields
    df["ZIP Code"] = df["ZIP Code"].astype(str).str.zfill(5)
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")

    for col in ["New", "Renewed", "Non-Renewed"]:
        df[col] = (
            df[col]
            .astype(str)
            .str.replace(",", "", regex=False)
        )
        df[col] = pd.to_numeric(df[col], errors="coerce")

    _rows_by_zip = {}

    for _, row in df.iterrows():
        zipcode = row["ZIP Code"]
        year = row["Year"]

        if pd.isna(zipcode) or pd.isna(year):
            continue

        entry = {
            "county": str(row.get("County", "")).strip(),
            "year": int(year),
            "new": row["New"],
            "renewed": row["Renewed"],
            "non_renewed": row["Non-Renewed"],
        }

        _rows_by_zip.setdefault(zipcode, []).append(entry)

    for zipcode in _rows_by_zip:
        _rows_by_zip[zipcode].sort(key=lambda r: r["year"])

    return _rows_by_zip

def _nonrenewal_rate(renewed: Optional[int], non_renewed: Optional[int]) -> Optional[float]:
    if renewed is None or non_renewed is None:
        return None
    total = renewed + non_renewed
    if total == 0:
        return None
    return round(non_renewed / total * 100, 1)


def get_nonrenewal_status(zipcode: str) -> Dict[str, Any]:
    """
    Return DOI non-renewal trend data for a ZIP code.

    Returns:
        found: bool
        zipcode: str
        county: str
        years: list of annual records with new/renewed/non_renewed counts and rate
        latest_year: int
        latest_nonrenewal_rate: float (%)
        trend_label: "worsening" | "improving" | "stable" | "insufficient data"
        five_year_rate_change: change in non-renewal rate from earliest to latest year (pp)
    """
    zipcode = str(zipcode).strip().zfill(5)

    try:
        rows = _load_rows()
    except FileNotFoundError:
        return {
            "found": False,
            "zipcode": zipcode,
            "error": f"DOI coverage dataset not found at {XLSX_PATH}",
        }
    except Exception as exc:
        return {"found": False, "zipcode": zipcode, "error": str(exc)}

    records = rows.get(zipcode)
    if not records:
        return {"found": False, "zipcode": zipcode}

    # Annotate each year with non-renewal rate
    years = []
    for r in records:
        rate = _nonrenewal_rate(r["renewed"], r["non_renewed"])
        years.append({**r, "nonrenewal_rate_pct": rate})

    # Trend: compare earliest vs latest non-renewal rate
    rates = [y["nonrenewal_rate_pct"] for y in years if y["nonrenewal_rate_pct"] is not None]

    if len(rates) >= 2:
        rate_change = round(rates[-1] - rates[0], 1)
        if rate_change > 3:
            trend_label = "worsening"
        elif rate_change < -3:
            trend_label = "improving"
        else:
            trend_label = "stable"
    else:
        rate_change = None
        trend_label = "insufficient data"

    latest = years[-1]

    return {
        "found": True,
        "zipcode": zipcode,
        "county": records[0]["county"] or None,
        "years": years,
        "latest_year": latest["year"],
        "latest_nonrenewal_rate": latest["nonrenewal_rate_pct"],
        "latest_new": latest["new"],
        "latest_renewed": latest["renewed"],
        "latest_non_renewed": latest["non_renewed"],
        "trend_label": trend_label,
        "rate_change_pp": rate_change,
    }


if __name__ == "__main__":
    import json
    result = get_nonrenewal_status("90001")
    print(json.dumps(result, indent=2))