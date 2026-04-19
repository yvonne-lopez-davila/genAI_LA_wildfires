"""
Zillow ZIP-level overlay service.
Uses ZIP-level Zillow rent dataset (ZORI) and aggregates to annual values for chart overlays.
"""

from pathlib import Path
import re
from typing import Any, Dict, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DATASET_DIR = BASE_DIR / "static_datasets" / "zillow_datasets"
ZORI_CSV_PATH = DATASET_DIR / "Zip_zori_uc_sfrcondomfr_sm_month.csv"

_df: Optional[pd.DataFrame] = None
_loaded_path: Optional[Path] = None


def _load_df(csv_path: Path) -> pd.DataFrame:
    global _df, _loaded_path
    if _df is None or _loaded_path != csv_path:
        _df = pd.read_csv(csv_path, dtype={"RegionName": str})
        _loaded_path = csv_path
    return _df


def get_zip_rent_timeseries(zipcode: str) -> Dict[str, Any]:
    """
    Returns annual average Zillow rent (ZORI) values for a CA ZIP code.
    """
    try:
        df = _load_df(ZORI_CSV_PATH)
    except FileNotFoundError:
        return {"found": False, "error": f"CSV not found at {ZORI_CSV_PATH}"}
    except Exception as exc:
        return {"found": False, "error": str(exc)}

    raw_zip = str(zipcode or "").strip()
    m = re.search(r"\d{5}", raw_zip)
    zipcode = m.group(0) if m else raw_zip.zfill(5)

    state_series = None
    if "StateName" in df.columns:
        state_series = df["StateName"].astype(str).str.upper()
    elif "State" in df.columns:
        state_series = df["State"].astype(str).str.upper()

    zip_mask = (df["RegionType"].astype(str).str.lower() == "zip") & (df["RegionName"] == zipcode)
    row = df[zip_mask & (state_series == "CA")] if state_series is not None else df[zip_mask]

    if row.empty:
        return {"found": False, "zipcode": zipcode}

    row = row.iloc[0]
    date_cols = [c for c in df.columns if c[:4].isdigit()]

    annual: Dict[str, list[float]] = {}
    for col in date_cols:
        try:
            year = col.split("-")[0]
            val = row[col]
            if pd.notna(val):
                annual.setdefault(year, []).append(float(val))
        except (ValueError, IndexError):
            continue

    timeseries = {
        year: round(sum(values) / len(values), 1)
        for year, values in sorted(annual.items())
        if values
    }

    return {
        "found": bool(timeseries),
        "metric": "Zillow Rent (ZORI, annual avg)",
        "zipcode": zipcode,
        "region_type": "zip",
        "timeseries": timeseries,
    }
