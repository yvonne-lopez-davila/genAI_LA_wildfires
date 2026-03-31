## API layer flask api to connect bw front end javascript
## and backend 

"""
FastAPI server for wildfire risk database

Endpoints:

    GET /           frontend HTML page (TODO)
    POST /analyze   takes in {lat, lon} query and returns risk report


"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
from typing import Optional

from risk_client import HomeRiskClient 
from fire_hazard_service import query_fire_hazard_zone

## Home value data
from zhvi_service import get_home_value_timeseries

app = FastAPI()


# TODO maybe differentiate user sessions later, hardcoding for now
client = HomeRiskClient(session_id="LA_risk_analysis")


# Define request struct
# for now, just takes in coordinates, 
# TODO update this to be more user friendly (maybe take in nat lang address and extract coords automatically)
## TODO maybe support multiple input formats
class AnalysisRequest(BaseModel):
    lat: float
    lon: float
    zipcode: Optional[str] = None


## ENDPOINTS

# Calls risk client class analyze method for 
# coord input
@app.post("/analyzeFireRisk")
def analyze(body: AnalysisRequest):
    # query fire hazard zone from GIS database 
    hazard = query_fire_hazard_zone(body.lat, body.lon)
    hazard_zone = hazard.get("hazard_zone", "Unknown")
    hazard_error = hazard.get("error")
    extra_context = None
    if hazard_zone and not hazard_error and hazard_zone != "Unknown":
        # this gets passed into LLM call so it has extra content from official fire hazard source
        extra_context = (
            f"Official hazard lookup for these coordinates indicates zone: {hazard_zone}."
        )

    # Query zillow home value for zipcode associated with location
    zhvi = get_home_value_timeseries(body.zipcode) if body.zipcode else {"found": False}

    result = client.analyze(body.lat, body.lon, extra_context=extra_context)

    if "error" in result:
        return {
            "error": result["error"],
            "hazard_zone": hazard_zone,
            "hazard_lookup_error": hazard_error,
        }

    report = result.get("report", {})
    if isinstance(report, dict):
        response: dict = {
            **report,
            "hazard_zone": hazard_zone,
            "hazard_lookup_error": hazard_error,
            "hazard_attributes": hazard.get("attributes", {}),
            "source_layer": hazard.get("source_layer"),
            "zhvi": zhvi,
        }
    else:
        response = {
            "report": report,
            "hazard_zone": hazard_zone,
            "hazard_lookup_error": hazard_error,
            "hazard_attributes": hazard.get("attributes", {}),
            "source_layer": hazard.get("source_layer"),
            "zhvi": zhvi,
        }

    return response


app.mount("/", StaticFiles(directory="static", html=True), name="static")

