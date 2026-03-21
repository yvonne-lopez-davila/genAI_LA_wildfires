## Client of LLM Proxy,
## Defines logic for homeowner risk analysis

"""
LA Wildfires: Homeowner Risk Analysis (Core logic)

TODO description

"""

import json
import re


from llmproxy import LLMProxy
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()


class HomeRiskReport():
    """
    Wraps LLMProxy to produce cohesive risk assessment 
    for prospective homeowners, considering wildfire proximity, market trends, and insurance trends

    """

    SYSTEM_PROMPT = """
You are a wildfire climate risk analyst specializing in California real estate.
 
Given a property's latitude and longitude, you will assess:
1. HOME VALUE IMPACT: How proximity to past and potential future wildfires may affect
   property values in the short term (1-2 years) and long term (5-10 years). Consider
   trends in nearby comparable properties that have been affected by fire events.
 
2. INSURANCE OUTLOOK: The likelihood of the homeowner maintaining private insurance
   coverage, the probability of being shifted to the California FAIR Plan, expected
   cost changes, and which insurers have withdrawn from the region.
 
3. AFFORDABILITY SCORE: A plain-language composite assessment of whether this property
   remains financially viable to own given fire risk, insurance costs, and value trends.
   Flag if the area is showing signs of systemic unaffordability.
 
4. CONFIDENCE: Rate your confidence in this assessment as "high", "medium", or "low"
   based on how much specific, verifiable data you have for this exact location.
 
Be direct and specific. Avoid generic disclaimers. If data is limited for the exact
coordinates, reason from the broader region and note this in your confidence rating.
 
You must respond ONLY with a valid JSON object in exactly this format, with no extra
text, explanation, or markdown before or after it:
 
{
  "home_value_impact": "...",
  "insurance_outlook": "...",
  "affordability_score": "...",
  "confidence": "high" or "medium" or "low"
}

"""

    def __init__(
        self,
        session_id: str = "LA_homeowner",
        model: str = "4o-mini",
        last_k: int = 5, ## TODO prob change this, setting low to start 
    ):

        """

        Iniitialize the wildfire risk client (homeowner)

        Args:
            session_id: used for RAG document scoping
            model: LLM model
            last_k: multiturn convo includes "k" turns

        """
        self.client = LLMProxy()
        self.session_id = session_id
        self.model = model
        self.last_k = last_k

        self.rag_threshold = 0.3 ## TODO adjust probably 
        self.rag_k = 3 ## TODO adjust 

        self.temperature = 0.2 ## TODO tune


    def analyze(self, lat:float, lon:float, extra_context: Optional[str] = None) -> Dict:
        """
        Analyze wildfire risk for a property at the given coordinates 

        Args:
            lat: Latitude of the property
            long: longitude of the property 
            extra_context: natural language query details (optional) ## TODO think about this more

        Returns: 
            Dict containing 
            -  report: dict with home_value_impact, insurance_outlook, affordability_score, confidence
            - raw_response: full proxy response for debugging
            error: set conditionally if errors

        """ 

        query = f"Analyze wildfire risk for the property at latitidue {lat}, longitude {lon}"

        if extra_context:
            query += f"\n\n Additional context: {extra_context}"

        response = self.client.generate(
            model=self.model,
            system= self.SYSTEM_PROMPT,
            query=query,
            temperature=self.temperature,
            session_id = self.session_id, 
            rag_usage=True,
            rag_threshold=self.rag_threshold,
            rag_k=self.rag_k,
            lastk=self.last_k,
        )

        if "error" in response:
            return {"error": response["error"], "raw_response": response}

        result = response.get("result", "")

        # Remove '''json ...''' if present 
        cleaned = re.sub(r"```json|```", "", result).strip()

        try:
            report_data = json.loads(cleaned)
        except(json.JSONDecodeError, TypeError):
            report_data = {"raw_text": result}

        return {
            "report": report_data,
            "raw_response": response
        }

# TODO delete below, just testing initial setup
# ---------------------------------------------------------------------------
# Quick test — run directly with: python wildfire_client.py
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    # Test coordinates: Paradise, CA (Camp Fire area)
    TEST_LAT = 39.7596
    TEST_LON = -121.6219
 
    print(f"Analyzing wildfire risk for ({TEST_LAT}, {TEST_LON})...\n")
 
    client = HomeRiskReport(session_id="test_session")
    result = client.analyze(TEST_LAT, TEST_LON)
 
    if "error" in result:
        print(f"Error: {result['error']}")
    else:
        report = result["report"]
        print("=" * 60)
        print("WILDFIRE RISK REPORT")
        print("=" * 60)
        if isinstance(report, dict):
            for key, value in report.items():
                print(f"\n{key.upper().replace('_', ' ')}:\n{value}")
        else:
            print(report)
        print("\n" + "=" * 60)

