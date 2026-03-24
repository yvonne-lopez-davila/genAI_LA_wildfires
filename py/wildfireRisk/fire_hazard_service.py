## API connection of live lookup for California fire hazard zone by lat/lon.
## Uses public ArcGIS query endpoint. 
## Currently, this works best with places that are only on fire hazard map --> typically excludes larger cities
## TODO: adding radius and proximities instead of specific lat/lon

from __future__ import annotations

import json
from typing import Any, Dict

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

# queries ArcGIS endpoint for fire hazard zone at given lat/lon
# can return unknown or key error if lookup fails
def query_fire_hazard_zone(lat: float, lon: float) -> Dict[str, Any]:
    params = {
        "f": "json",
        "where": "1=1",
        "geometryType": "esriGeometryPoint",
        "inSR": "4326",
        "spatialRel": "esriSpatialRelIntersects",
        "geometry": json.dumps(
            {"x": lon, "y": lat, "spatialReference": {"wkid": 4326}}
        ),
        "outFields": "*",
        "returnGeometry": "false",
    }

    for layer_name, url in LAYER_URLS:
        try:
            resp = requests.get(url, params=params, timeout=20)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            return {"error": f"hazard lookup failed: {e}"}

        features = data.get("features", [])
        if features:
            attrs = features[0].get("attributes", {}) or {}
            zone = extract_zone_from_attributes(attrs)
            # returns dict with hazard zone, source layer, attributes, and feature count
            # right now only passing hazard zone to LLM call (others can potentially 
            # be used after figuring out database requirements)
            # attributes would have good information
            return {
                "hazard_zone": zone,
                "source_layer": layer_name,
                "attributes": attrs,
                "feature_count": len(features),
            }

    return {
        "hazard_zone": "Unknown",
        "source_layer": None,
        "attributes": {},
        "feature_count": 0,
    }
