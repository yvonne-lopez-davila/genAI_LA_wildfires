import requests

lat = 34.0928
lon = -118.5986
radius_miles = 30
min_acres = 100
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
    "resultRecordCount": 5,
}

resp = requests.get(
    "https://services1.arcgis.com/jUJYIo9tSA7EHvfZ/arcgis/rest/services/California_Historic_Fire_Perimeters/FeatureServer/0/query",
    params=params,
    timeout=10
)
print("status:", resp.status_code)
print("response:", resp.text[:1000])

