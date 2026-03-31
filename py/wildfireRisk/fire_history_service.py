"""
Fire history service.
Queries CalFire historical fire perimeters API for fires near a given coordinate.
Returns fire events with year, name, acreage, and distance from the queried point.

Data source: CAL FIRE / FRAP historical fire perimeters
Covers fires back to 1878, updated annually.
Fields used: FIRE_NAME, YEAR_, GIS_ACRES
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import requests

# CAL FIRE historical perimeters - public FeatureServer endpoint
FIRE_PERIMETERS_URL = (
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/"
    "California_Historic_Fire_Perimeters/FeatureServer/0/query"
)

# Search radius in miles — fires within this distance are returned
DEFAULT_RADIUS_MILES = 30

# Only return fires at least this large (acres) to filter out tiny incidents
MIN_ACRES = 100


def _miles_to_meters(miles: float) -> float:
    return miles * 1609.34


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate distance in miles between two lat/lon points.
    Used to compute distance from query point to fire centroid.
    """
    R = 3958.8  # Earth radius in miles
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def get_nearby_fires(
    lat: float,
    lon: float,
    radius_miles: float = DEFAULT_RADIUS_MILES,
    min_acres: float = MIN_ACRES,
) -> Dict[str, Any]:
    """
    Query CalFire perimeters API for historical fires near a coordinate.

    Args:
        lat: Latitude of the query point
        lon: Longitude of the query point
        radius_miles: Search radius in miles
        min_acres: Minimum fire size to include

    Returns:
        Dict containing:
            - fires: list of fire dicts sorted by year
            - query_point: {lat, lon}
            - radius_miles: search radius used
            - found: bool
            - error: set if something went wrong
    """
    
    # Bounding box in degrees (~69 miles per degree latitude)
    buffer = radius_miles / 69.0
    params = {
        "f": "json",
        "where": f"GIS_ACRES >= {min_acres}",
        "geometryType": "esriGeometryEnvelope",
        "geometry": f"{lon-buffer},{lat-buffer},{lon+buffer},{lat+buffer}",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "outFields": "FIRE_NAME,YEAR_,GIS_ACRES",
        "returnGeometry": "false",
        "returnCentroid": "true",
        "outSR": "4326",
        "resultRecordCount": 100,
    }

    try:
        print("Sending request...")
        resp = requests.get(FIRE_PERIMETERS_URL, params=params, timeout=10)
        print("Response status:", resp.status_code)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"found": False, "fires": [], "error": str(e)}

    if "error" in data:
        return {"found": False, "fires": [], "error": data["error"]}

    features = data.get("features", [])
    if not features:
        return {
            "found": False,
            "fires": [],
            "query_point": {"lat": lat, "lon": lon},
            "radius_miles": radius_miles,
        }

    fires = []
    for feature in features:
        attrs = feature.get("attributes", {})
        centroid = feature.get("centroid")

        fire_name = attrs.get("FIRE_NAME") or "Unknown"
        year = attrs.get("YEAR_")
        acres = attrs.get("GIS_ACRES")

        # Calculate distance from query point to fire centroid
        distance_miles = None
        if centroid:
            clat = centroid.get("y")
            clon = centroid.get("x")
            if clat and clon:
                distance_miles = round(_haversine_miles(lat, lon, clat, clon), 1)

        if year:
            fires.append({
                "fire_name": fire_name.title(),
                "year": int(year),
                "acres": round(acres) if acres else None,
                "distance_miles": distance_miles,
            })

    # Sort by year
    fires.sort(key=lambda f: f["year"])

    return {
        "found": True,
        "fires": fires,
        "query_point": {"lat": lat, "lon": lon},
        "radius_miles": radius_miles,
        "total": len(fires),
    }

if __name__ == "__main__":
    result = get_nearby_fires(34.0928, -118.5986)
    print("Full result:", result)
    for f in result.get("fires", []):
        print(f"{f['year']} — {f['fire_name']} ({f['acres']} acres, {f['distance_miles']} miles away)")