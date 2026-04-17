## API connection of live lookup for California fire hazard zone by lat/lon.
## Uses public ArcGIS query endpoint. 
## Currently, this works best with places that are only on fire hazard map --> typically excludes larger cities

from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple

import requests

# covering all 4 layers listed in https://services.gis.ca.gov/arcgis/rest/services/Environment/Fire_Severity_Zones/MapServer
# LRA and SRA are most important ones --> relevant to property and homeowner
# can get rid of unzoned/federal if we decide we do not need
LAYER_URLS = [
    ("SRA", "https://services.gis.ca.gov/arcgis/rest/services/Environment/Fire_Severity_Zones/MapServer/0/query"),
    ("LRA", "https://services.gis.ca.gov/arcgis/rest/services/Environment/Fire_Severity_Zones/MapServer/1/query"),
    ("UNZONED", "https://services.gis.ca.gov/arcgis/rest/services/Environment/Fire_Severity_Zones/MapServer/2/query"),
    ("FEDERAL", "https://services.gis.ca.gov/arcgis/rest/services/Environment/Fire_Severity_Zones/MapServer/3/query"),
]

def extract_zone_from_attributes(attrs: Dict[str, Any]) -> str:
    for key in ("HAZ_CLASS", "FHSZ_Descr"):
        value = attrs.get(key)
        if isinstance(value, str) and value.strip():
            return value

    for value in attrs.values():
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in ("moderate", "high", "very high"):
                return value

    return "Unknown"

#converts text hazard level into a number
#larger number = higher severity and vice versa
def _zone_rank(zone: str) -> int:
    z = (zone or "").strip().lower()
    if z == "very high":
        return 3
    if z == "high":
        return 2
    if z == "moderate":
        return 1
    return 0


# queries ArcGIS endpoint for fire hazard zone at given lat/lon
# can return unknown or key error if lookup fails
def query_fire_hazard_zone(lat: float, lon: float, radius_miles: Optional[float] = 1.0) -> Dict[str, Any]:
    """
    If radius_miles is provided, ArcGIS will return polygons that intersect the point buffered
    by that distance. When multiple features hit, we select the *highest severity* zone.
    """
    distance_meters: Optional[float] = None
    if radius_miles is not None:
        distance_meters = float(radius_miles) * 1609.34

    params = {
        "f": "json",
        "where": "1=1",
        "distance": distance_meters, #radius of approx 1 mile
        "units": "esriSRUnit_Meter" if distance_meters is not None else None,
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "geometry": json.dumps(
            {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}
        ),
        "outFields": "*",
        "returnGeometry": "false",
    }

    params = {k: v for k, v in params.items() if v is not None}

    for layer_name, url in LAYER_URLS:
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"error": f"hazard lookup failed: {e}"}

        features = data.get("features", [])
        if features:
            # multiple hits are possible when a radius is used; pick the highest severity zone.
            best: Tuple[int, str, Dict[str, Any]] = (0, "Unknown", {})
            for feat in features:
                attrs = feat.get("attributes", {}) or {}
                zone = extract_zone_from_attributes(attrs)
                rank = _zone_rank(zone)
                if rank > best[0]:
                    best = (rank, zone, attrs)

            return {
                "hazard_zone": best[1],
                "source_layer": layer_name,
                "attributes": best[2],
                "feature_count": len(features),
            }

    return {
        "hazard_zone": "Unknown",
        "source_layer": None,
        "attributes": {},
        "feature_count": 0,
    }
