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
from typing import Optional, Dict

from backend.risk_client import HomeRiskClient 
from services.fire_hazard_service import query_fire_hazard_zone

## Home value data
from services.zhvi_service import get_home_value_timeseries

## Proximity to fire events via zipcode
from services.fire_history_service import get_nearby_fires

## FAIR Plan ZIP-level residential exposure
from services.fair_plan_service import get_fair_plan_status

## Analyze historical trends (statistical analysis) 
from services.trend_analysis import analyze_trends

## CAL FIRE structure damage inspection data
from services.damage_inspection_service import get_dins_risk
 
## California DOI insurance non-renewal data
from services.doi_nonrenewal_service import get_nonrenewal_status

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
    user_type: Optional[str] = None
    property_chars: Optional[Dict[str, str]] = None  # DINS property characteristics (homeowner only)


## ENDPOINTS

# Calls risk client class analyze method for 
# coord input
@app.post("/analyzeFireRisk")
def analyze(body: AnalysisRequest):
    # debug
    print(f"user_type received: {body.user_type}")
    print(f"property_chars received: {body.property_chars}")

    # query fire hazard zone from GIS database 
    hazard = query_fire_hazard_zone(body.lat, body.lon)
    hazard_zone = hazard.get("hazard_zone", "Unknown")
    hazard_error = hazard.get("error")

    # Query zillow home value for zipcode associated with location
    zhvi = get_home_value_timeseries(body.zipcode) if body.zipcode else {"found": False}

    # Query FAIR Plan residential exposure by zipcode
    fair_plan = get_fair_plan_status(body.zipcode) if body.zipcode else {"found": False}
    
    # Query CalFire perimeters API 
    fire_history = get_nearby_fires(body.lat, body.lon)
    
    # Query DINS structure damage data (always run, pass property_chars if provided)
    dins = get_dins_risk(body.lat, body.lon, property_chars=body.property_chars)
 
    # Query DOI non-renewal data by ZIP
    doi = get_nonrenewal_status(body.zipcode) if body.zipcode else {"found": False}

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
    
    # DOI non-renewal context
    if doi.get("found"):
        doi_context = (
            f"Insurance non-renewal data for ZIP {body.zipcode}: "
            f"latest non-renewal rate is {doi.get('latest_nonrenewal_rate', 'N/A')}% "
            f"({doi.get('latest_year', 'N/A')}). "
            f"Trend: {doi.get('trend_label', 'N/A')}. "
            f"Rate change over available period: {doi.get('rate_change_pp', 'N/A')} percentage points."
        )
        context_parts.append(doi_context)

    # risk meter gauge signals llm plain text explanation 
    gauge_explanation = client.explain_gauge(
        composite_label=trends["composite"]["composite_label"],
        signals=trends["composite"]["signals"],
        risk_factor_count=trends["composite"]["risk_factor_count"],
    )

    # charts llm analysis bullets
    chart_observations = client.generate_chart_observations(
        zipcode=body.zipcode or "unknown",
        price_trajectory=trends.get("price_trajectory", {}),
        fire_proximity=trends.get("fire_proximity", {}),
        fire_frequency=trends.get("fire_frequency", {}),
    ) 


    if body.zipcode:
    # add FAIR Plan context if ZIP code to the LLM
        if fair_plan.get("found") and fair_plan.get("covered_by_fair_plan"):
            latest_exposure = fair_plan.get("latest_total_exposure")
            latest_exposure_text = (
                f"${latest_exposure:,}" if isinstance(latest_exposure, int) else "unavailable"
            )
            context_parts.append(
                f"FAIR Plan residential exposure is reported in ZIP {body.zipcode}. "
                f"FY2025 total insured value in the ZIP: {latest_exposure_text}. "
                f"Five-year exposure change from FY2021 to FY2025: "
                f"{fair_plan.get('five_year_pct_change', 'N/A')}%."
            )
        elif fair_plan.get("found"):
            context_parts.append(
                f"ZIP {body.zipcode} appears in the FAIR Plan residential report historically, "
                f"but no FY2025 exposure is reported for that ZIP."
            )
        elif not fair_plan.get("error"):
            context_parts.append(
                f"ZIP {body.zipcode} does not appear in the current FAIR Plan "
                f"residential exposure report."
            )
   
    extra_context = "\n".join(context_parts) if context_parts else None

    result = client.analyze(body.lat, body.lon, extra_context=extra_context, user_type=body.user_type)

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
            "fair_plan": fair_plan,
            "fire_history": fire_history,
            "trends": trends,
            "gauge_explanation": gauge_explanation,
            "chart_observations": chart_observations,
            "dins": dins,
            "doi": doi,
        }
    else:
        response = {
            "report": report,
            "hazard_zone": hazard_zone,
            "hazard_lookup_error": hazard_error,
            "hazard_attributes": hazard.get("attributes", {}),
            "source_layer": hazard.get("source_layer"),
            "zhvi": zhvi,
            "fair_plan": fair_plan,
            "fire_history": fire_history,
            "trends": trends,
            "gauge_explanation": gauge_explanation,
            "chart_observations": chart_observations,
            "dins": dins,
            "doi": doi,
        }

    return response


app.mount("/", StaticFiles(directory="static", html=True), name="static")
