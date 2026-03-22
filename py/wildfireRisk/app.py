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

from risk_client import HomeRiskClient 


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


## ENDPOINTS

# Calls risk client class analyze method for 
# coord input
@app.post("/analyzeFireRisk")
def analyze(body: AnalysisRequest):
    result = client.analyze(body.lat, body.lon)

    if "error" in result:
        return {"error": result["error"]}

    return result["report"]




## serve html UI file
app.mount("/", StaticFiles(directory="static", html=True), name="static")

