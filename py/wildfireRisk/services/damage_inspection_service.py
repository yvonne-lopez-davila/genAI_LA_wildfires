"""
DINS (Damage Inspection) service.
Queries CAL FIRE structure damage inspection data for structures near a coordinate.

Provides:
- Damage rate of nearby inspected structures
- Most common vulnerable characteristics among damaged structures
- Optional: comparison against user-provided property characteristics

Data source: CAL FIRE Damage Inspection Program (DINS)
https://gis.data.cnra.ca.gov/datasets/CALFIRE-Forestry::cal-fire-damage-inspection-dins-data
Covers structures inspected since 2013.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent

DATASET_DIR = BASE_DIR / "static_datasets" / "property_datasets"
CSV_PATH = DATASET_DIR / "structure_fire_damage_dins.csv"

DEFAULT_RADIUS_MILES = 5
MIN_STRUCTURES = 5  # minimum nearby structures to report meaningful stats

# Damage categories → severity rank
DAMAGE_RANK = {
    "destroyed (>50%)": 3,
    "major (26-50%)": 2,
    "affected (>0-10%)": 1,
    "minor (11-25%)": 1,
    "no damage": 0,
}

_df: Optional[pd.DataFrame] = None


def _load_df() -> pd.DataFrame:
    global _df
    if _df is not None:
        return _df

    _df = pd.read_csv(
        CSV_PATH,
        encoding="utf-8-sig",  # handles BOM
        low_memory=False,
    )

    # Normalize column names — strip *, spaces, angle-bracket entities
    _df.columns = (
        _df.columns
        .str.replace(r"^\*\s*", "", regex=True)
        .str.strip()
        .str.replace("&gt;", ">")
        .str.replace("&lt;", "<")
    )

    # Drop rows without coordinates
    _df = _df.dropna(subset=["Latitude", "Longitude"])
    _df["Latitude"] = pd.to_numeric(_df["Latitude"], errors="coerce")
    _df["Longitude"] = pd.to_numeric(_df["Longitude"], errors="coerce")
    _df = _df.dropna(subset=["Latitude", "Longitude"])

    # Normalize damage field to lowercase for consistent matching
    _df["Damage_norm"] = _df["Damage"].str.strip().str.lower()

    return _df


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 3958.8
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _damage_rate(subset: pd.DataFrame) -> Dict[str, Any]:
    """Compute damage/destruction rates for a set of structures."""
    total = len(subset)
    if total == 0:
        return {}

    destroyed = subset["Damage_norm"].str.contains("destroyed", na=False).sum()
    damaged = subset["Damage_norm"].str.contains(
        "major|minor|affected", na=False
    ).sum()
    no_damage = subset["Damage_norm"].str.contains("no damage", na=False).sum()

    return {
        "total": total,
        "destroyed": int(destroyed),
        "damaged": int(damaged),
        "no_damage": int(no_damage),
        "destruction_rate_pct": round(destroyed / total * 100, 1),
        "damage_or_destroyed_rate_pct": round((destroyed + damaged) / total * 100, 1),
    }


def _top_values(series: pd.Series, n: int = 3) -> List[str]:
    """Return top n non-null values by frequency."""
    counts = series.dropna().value_counts()
    counts = counts[~counts.index.str.strip().str.lower().isin(["", "unknown", "n/a"])]
    return counts.head(n).index.tolist()


def _structural_vulnerability_profile(damaged: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Among damaged/destroyed structures, what structural characteristics
    are most common? These are the vulnerability signals.
    """
    if damaged.empty:
        return {}

    return {
        "roof_construction": _top_values(damaged["Roof Construction"]),
        "eaves": _top_values(damaged["Eaves"]),
        "vent_screen": _top_values(damaged["Vent Screen"]),
        "exterior_siding": _top_values(damaged["Exterior Siding"]),
        "window_pane": _top_values(damaged["Window Pane"]),
        "fence_attached": _top_values(damaged["Fence Attached to Structure"]),
    }


def _compare_property(
    nearby: pd.DataFrame,
    property_chars: Dict[str, str],
) -> Dict[str, Any]:
    """
    Compare user-provided property characteristics against damage outcomes
    of nearby structures with matching characteristics.
    """
    comparisons = {}

    field_map = {
        "roof_construction": "Roof Construction",
        "eaves": "Eaves",
        "vent_screen": "Vent Screen",
        "exterior_siding": "Exterior Siding",
        "window_pane": "Window Pane",
    }

    for prop_key, col_name in field_map.items():
        user_val = property_chars.get(prop_key)
        if not user_val or col_name not in nearby.columns:
            continue

        # Case-insensitive match
        matches = nearby[
            nearby[col_name].str.strip().str.lower() == user_val.strip().lower()
        ]

        if len(matches) < 3:  # too few to be meaningful
            continue

        rates = _damage_rate(matches)
        comparisons[prop_key] = {
            "user_value": user_val,
            "matched_structures": rates["total"],
            "destruction_rate_pct": rates["destruction_rate_pct"],
            "damage_or_destroyed_rate_pct": rates["damage_or_destroyed_rate_pct"],
        }

    return comparisons


def get_dins_risk(
    lat: float,
    lon: float,
    radius_miles: float = DEFAULT_RADIUS_MILES,
    property_chars: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Query DINS data for structures near a coordinate.

    Args:
        lat: Latitude of query point
        lon: Longitude of query point
        radius_miles: Search radius in miles
        property_chars: Optional dict of user property characteristics:
            {
                "roof_construction": "Asphalt",
                "eaves": "Unenclosed",
                "vent_screen": "Mesh Screen <= 1/8\"",
                "exterior_siding": "Wood",
                "window_pane": "Single Pane",
                "year_built": "1987",
            }

    Returns:
        Dict with damage rates, vulnerability profile, and optional property comparison
    """
    try:
        df = _load_df()
    except FileNotFoundError:
        return {"found": False, "error": f"DINS dataset not found at {CSV_PATH}"}
    except Exception as e:
        return {"found": False, "error": str(e)}

    # Filter by bounding box first for performance, then exact haversine
    buffer = radius_miles / 69.0
    bbox = df[
        (df["Latitude"].between(lat - buffer, lat + buffer)) &
        (df["Longitude"].between(lon - buffer, lon + buffer))
    ].copy()

    if bbox.empty:
        return {
            "found": False,
            "query_point": {"lat": lat, "lon": lon},
            "radius_miles": radius_miles,
            "message": "No inspected structures found within search radius.",
        }

    bbox["distance_miles"] = bbox.apply(
        lambda r: _haversine_miles(lat, lon, r["Latitude"], r["Longitude"]),
        axis=1,
    )
    nearby = bbox[bbox["distance_miles"] <= radius_miles].copy()

    if len(nearby) < MIN_STRUCTURES:
        return {
            "found": False,
            "query_point": {"lat": lat, "lon": lon},
            "radius_miles": radius_miles,
            "structure_count": len(nearby),
            "message": f"Too few inspected structures nearby ({len(nearby)}) for meaningful analysis.",
        }

    # Damaged/destroyed subset
    damaged = nearby[
        nearby["Damage_norm"].str.contains("destroyed|major|minor|affected", na=False)
    ]

    rates = _damage_rate(nearby)
    vuln_profile = _structural_vulnerability_profile(damaged)

    # Incident breakdown
    incidents = (
        nearby.groupby("Incident Name")
        .size()
        .sort_values(ascending=False)
        .head(5)
        .to_dict()
    )

    result = {
        "found": True,
        "query_point": {"lat": lat, "lon": lon},
        "radius_miles": radius_miles,
        "damage_rates": rates,
        "vulnerability_profile": vuln_profile,
        "top_incidents": incidents,
        "year_range": f"{nearby['Incident Start Date'].dropna().min()[:4] if not nearby['Incident Start Date'].dropna().empty else 'unknown'}–present",
    }

    # Optional property comparison
    if property_chars:
        comparison = _compare_property(nearby, property_chars)
        result["property_comparison"] = comparison

    return result


if __name__ == "__main__":
    import json

    # Test: Topanga area
    result = get_dins_risk(
        lat=34.0928,
        lon=-118.5986,
        radius_miles=5,
        property_chars={
            "roof_construction": "Asphalt",
            "eaves": "Unenclosed",
            "exterior_siding": "Wood",
            "window_pane": "Single Pane",
        }
    )
    print(json.dumps(result, indent=2))