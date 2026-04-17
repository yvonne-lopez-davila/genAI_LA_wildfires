"""
Zillow Home Value Index (ZHVI) lookup service.
Queries local CSV for historical home value data by zip code.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, Optional

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_DIR = BASE_DIR / "static_datasets" / "zillow_datasets"
CSV_PATH = DATASET_DIR / "zhvi_ca.csv"

# Cache the dataframe so we only read it once
_df: Optional[pd.DataFrame] = None


def _load_df() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = pd.read_csv(CSV_PATH, dtype={"RegionName": str})
    return _df


def get_home_value_timeseries(zipcode: str) -> Dict[str, Any]:
    """
    Look up ZHVI time series for a given zip code.

    Args:
        zipcode: 5-digit zip code string e.g. "90210"

    Returns:
        Dict containing:
            - zipcode: str
            - city: str
            - county: str
            - metro: str
            - timeseries: dict of {year: avg_annual_value}
            - found: bool
    """
    try:
        df = _load_df()
    except FileNotFoundError:
        return {"found": False, "error": f"CSV not found at {CSV_PATH}"}
    except Exception as e:
        return {"found": False, "error": str(e)}

    # Zip codes are stored as strings (e.g. "90210")
    zipcode = str(zipcode).strip().zfill(5)
    row = df[df["RegionName"] == zipcode]

    if row.empty:
        return {"found": False, "zipcode": zipcode}

    row = row.iloc[0]

    # Extract date columns (start with a digit)
    date_cols = [c for c in df.columns if c[0].isdigit()]

    # Aggregate to annual averages for cleaner charting
    annual = {}
    for col in date_cols:
        try:
            # col format: "1/31/2000"
            year = col.split("/")[-1]
            val = row[col]
            if pd.notna(val):
                if year not in annual:
                    annual[year] = []
                annual[year].append(float(val))
        except (ValueError, IndexError):
            continue

    # Average each year's monthly values
    timeseries = {
        year: round(sum(vals) / len(vals))
        for year, vals in sorted(annual.items())
        if vals
    }

    return {
        "found": True,
        "zipcode": zipcode,
        "city": row.get("City", ""),
        "county": row.get("CountyName", ""),
        "metro": row.get("Metro", ""),
        "timeseries": timeseries,
    }