## Client of LLM Proxy,
## Defines logic for homeowner risk analysis

"""
LA Wildfires: Homeowner Risk Analysis (Core logic)

TODO more detailed description

"""

import json

import re

from llmproxy import LLMProxy
from dotenv import load_dotenv
from typing import Dict, Optional

load_dotenv()


class HomeRiskClient():
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

5. FIRE HAZARD ZONE CLASSIFICATION (if available): briefly state fire hazard zone classification ONLY if provided by extra query content. If not, say, "no data at the moment"
    Do NOT make up data.
 
Be direct and specific. Avoid generic disclaimers. If data is limited for the exact
coordinates, reason from the broader region and note this in your confidence rating.
 
If additional context is provided (such as an official fire hazard zone classification), 
factor it into all four assessments accordingly. 
Official fire hazard zone classification may be particularly relevant to home value impact and insurance outlook.
A "Very High" hazard zone should significantly influence insurance outlook and affordability score.

Use the provided context data to inform your analysis, but do not simply restate 
the numbers. Instead, interpret what they mean for the homeowner — draw conclusions, 
identify patterns, and explain implications. The data points should support your 
analysis, not replace it.

When writing assessments, wrap the 3-5 most important terms or conclusions per section 
in <strong> tags. For example: "properties in <strong>Very High</strong> zones face 
<strong>significant insurance risk</strong>". Keep bolding sparse and meaningful.

If Zillow Home Value Index data is provided in context, cite specific values 
and trends from it when assessing home value impact. Reference the time period 
and percentage changes where possible.

If nearby fire history is provided, reference specific fire events, years, and distances 
when relevant. Note if fires have been trending closer over time.

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
    
    def explain_gauge(self, composite_label: str, signals: list, risk_factor_count: int) -> str:
        signal_texts = [s["text"] if isinstance(s, dict) else s for s in signals]
        
        query = f"""
    Risk score: {composite_label}
    Risk factors triggered: {risk_factor_count} of 4
    Signals:
    {chr(10).join(f'- {s}' for s in signal_texts)}

    Write short explanations that ADD new meaning beyond the signals.

    Output format:
    - One bullet per signal
    - Each bullet MUST be on its own line
    - Insert a newline character between each bullet (\\n)
    - Do not place multiple bullets on the same line

    Instructions:
    - Do NOT restate or paraphrase the signal
    - Explain what the signal implies (trend strength, severity, or significance)
    - Focus on magnitude, comparison, or why it matters relative to other signals
    - Use specific numbers when helpful, but don’t repeat full phrases from the signal

    Hard rules:
    - No advice or recommendations
    - No filler phrases (e.g., "this means", "indicating that")
    - No combining multiple signals into one bullet
    - Keep each bullet to one sentence
    - One sentence per bullet

    Goal:
    Each bullet should tell the user something they would NOT already know just by reading the signal text.

    Return ONLY the bullets.

    """
        response = self.client.generate(
            model=self.model,
            system="You are a wildfire risk analyst explaining a risk score to a homeowner in plain, direct language.",
            query=query,
            temperature=0.3,
            session_id=self.session_id,
            rag_usage=False,
            lastk=0,
        )
        return response.get("result", "").strip()

    def generate_chart_observations(
        self,
        zipcode: str,
        price_trajectory: dict,
        fire_proximity: dict,
        fire_frequency: dict,
    ) -> str:
        
        query = f"""
    You are analyzing home value and wildfire data for ZIP code {zipcode}.

    Home value data:
    - Current median value: ${price_trajectory.get('current_value', 'N/A'):,}
    - 5-year change: {price_trajectory.get('pct_change_5yr', 'N/A')}% ({price_trajectory.get('trend_label', 'N/A')})
    - Full date range: {price_trajectory.get('year_range', 'N/A')}

    Wildfire proximity data:
    - Total fires within 30 miles: {fire_frequency.get('total_fires', 0)}
    - Fire frequency trend: {fire_frequency.get('trend_label', 'N/A')}
    - Proximity trend: {fire_proximity.get('trend_label', 'N/A')}
    - Historical avg distance: {fire_proximity.get('historical_avg_distance_miles', 'N/A')} miles
    - Recent avg distance (last 5 years): {fire_proximity.get('recent_avg_distance_miles', 'N/A')} miles
    - Closest recorded fire: {fire_proximity.get('closest_fire', {}).get('fire_name', 'N/A')} ({fire_proximity.get('closest_fire', {}).get('year', 'N/A')}, {fire_proximity.get('closest_fire', {}).get('distance_miles', 'N/A')} miles)

    Generate concise bullet points in exactly these three sections:
    HOME TRENDS: (1-2 bullets about what the price chart shows)
    WILDFIRE TRENDS: (1-2 bullets about what the fire proximity chart shows)
    CROSS-OBSERVATIONS: (1-2 bullets connecting fire activity to price behavior, if any pattern exists)

    Rules:
    - Be specific, use numbers
    - Do not give advice or recommendations  
    - Do not repeat data verbatim, interpret it
    - If no meaningful cross-observation exists, say so briefly
    - Return only the bullets, no extra text
    """
        response = self.client.generate(
            model=self.model,
            system="You are a data analyst summarizing charts for a homeowner.",
            query=query,
            temperature=0.3,
            session_id=self.session_id,
            rag_usage=False,
            lastk=0,
        )
        return response.get("result", "").strip()


# TODO delete below, just testing initial setup
# ---------------------------------------------------------------------------
# Quick test — run directly with: python wildfire_client.py
# ---------------------------------------------------------------------------
 
if __name__ == "__main__":
    # Test coordinates: Paradise, CA (Camp Fire area)
    TEST_LAT = 39.7596
    TEST_LON = -121.6219
 
    print(f"Analyzing wildfire risk for ({TEST_LAT}, {TEST_LON})...\n")
 
    client = HomeRiskClient(session_id="test_session")
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

