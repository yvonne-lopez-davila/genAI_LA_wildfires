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

## Proximity to fire events via zipcode
from fire_history_service import get_nearby_fires

## Analyze historical trends (statistical analysis) 
from trend_analysis import analyze_trends

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

    # Query zillow home value for zipcode associated with location
    zhvi = get_home_value_timeseries(body.zipcode) if body.zipcode else {"found": False}
    
    # Query CalFire perimeters API 
    fire_history = get_nearby_fires(body.lat, body.lon)
    
    # Analyze trends from services' data
    trends = analyze_trends(fire_history, zhvi, hazard_zone=hazard_zone)

    context_parts = []

    if hazard_zone and not hazard_error and hazard_zone != "Unknown":
        context_parts.append(f"Official fire hazard zone: {hazard_zone}.")

    if fire_history.get("found") and fire_history.get("fires"):
        total = fire_history.get("total", 0)
        context_parts.append(f"{total} fires recorded within 30 miles historically.")
        
        # Add closest recent fire
        recent = [f for f in fire_history["fires"] if f["year"] >= 2015]
        if recent:
            closest = min(recent, key=lambda f: f.get("distance_miles") or 999)
            context_parts.append(
                f"Most notable recent fire: {closest['fire_name']} ({closest['year']}, "
                f"{closest['acres']} acres, {closest['distance_miles']} miles away)."
            )

    if trends.get("composite"):
        composite = trends["composite"]
        context_parts.append(f"Risk trend assessment: {composite['composite_label']}.")
        for signal in composite.get("signals", []):
            text = signal["text"] if isinstance(signal, dict) else signal
            context_parts.append(text)

    if zhvi.get("found"):
        traj = trends.get("price_trajectory", {})
        if traj.get("current_value"):
            context_parts.append(
                f"Current median home value: ${traj['current_value']:,}. "
                f"5-year change: {traj.get('pct_change_5yr', 'N/A')}% ({traj.get('trend_label', '')})."
            )

    gauge_explanation = client.explain_gauge(
        composite_label=trends["composite"]["composite_label"],
        signals=trends["composite"]["signals"],
        risk_factor_count=trends["composite"]["risk_factor_count"],
    )

    extra_context = "\n".join(context_parts) if context_parts else None

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
            "fire_history": fire_history,
            "trends": trends,
            "gauge_explanation": gauge_explanation,
        }
    else:
        response = {
            "report": report,
            "hazard_zone": hazard_zone,
            "hazard_lookup_error": hazard_error,
            "hazard_attributes": hazard.get("attributes", {}),
            "source_layer": hazard.get("source_layer"),
            "zhvi": zhvi,
            "fire_history": fire_history,
            "trends": trends,
            "gauge_explanation": gauge_explanation,
        }

    return response


app.mount("/", StaticFiles(directory="static", html=True), name="static")

