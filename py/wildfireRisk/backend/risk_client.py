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

If California DOI non-renewal data is provided in context, use it to strengthen or 
qualify your insurance outlook assessment. Reference the non-renewal rate, trend direction, 
and rate change in percentage points where relevant. A worsening trend with a high 
non-renewal rate is a strong signal of insurance market withdrawal from the area.

You must respond ONLY with a valid JSON object in exactly this format, with no extra
text, explanation, or markdown before or after it:
 
{
  "home_value_impact": "...",
  "insurance_outlook": "...",
  "affordability_score": "...",
  "confidence": "high" or "medium" or "low"
}

"""

    HOMEOWNER_SYSTEM_PROMPT = """
You are a wildfire risk advisor helping a current California homeowner understand 
and act on their property's risk.

Frame all analysis around: what is their situation RIGHT NOW, and what can they DO about it.

Given a property location, assess:
1. HOME VALUE IMPACT: How wildfire risk is currently affecting or likely to affect 
   their property value. Reference recent comparable fire events if available.

2. INSURANCE OUTLOOK: Their likelihood of maintaining private coverage, probability 
   of being shifted to the FAIR Plan, and which carriers have withdrawn from the area.
   Be specific about what predicts non-renewal in this ZIP. If California DOI non-renewal
   data is provided in context, reference the non-renewal rate and trend direction 
   explicitly — a worsening trend is a concrete warning sign the homeowner should act on.

3. AFFORDABILITY SCORE: Whether continuing to own this property remains financially 
   viable given current and projected insurance costs, fire risk, and value trends.

4. MITIGATION RECOMMENDATIONS: Provide 1-3 specific, actionable recommendations
   formatted as a numbered list: "1. ... 2. ... 3. ..."
   Do not use bullet points or dashes.
   Only include this section if the hazard zone is High or Very High.
   If RAG sources are referenced, link the source in the text.

   Order recommendations by urgency and impact: the action with the greatest combined
   effect on fire survivability AND insurability should be #1.
   If a property characteristic is known, state directly why it is a risk factor.
   If it is inferred or unknown, tell the homeowner exactly what to check or verify
   (e.g. "Verify whether your asphalt shingles are rated Class A — if not, replacement
   is the single highest-impact upgrade for fire survivability and insurability").
   Never hedge with "may not meet standards" without giving the homeowner a concrete
   next step to find out.
   
    When referencing a specific home hardening component (eaves, vents, roof, siding, 
    windows, fences, defensible space), wrap the term in double brackets like [[eaves]] 
    or [[ember-resistant vents]]. Do not include URLs yourself.

   Each recommendation should consider the following where data is available:

   - PROPERTY CHARACTERISTICS: roof material, eaves, siding, vents, windows, fencing,
     and any other homeowner-provided inputs. Name the specific characteristic
     (e.g. "Your unenclosed eaves and wood siding are among the highest-risk
     combinations in nearby destroyed structures").

   - LOCATION & FIRE BEHAVIOR: the property's geographic context — slope, prevailing
     wind patterns, proximity to wildland interface, local fire history, and how
     these amplify or moderate risk for this specific address.

   - DESTRUCTION RATE DATA: reference the nearby structure statistics where relevant
     (e.g. "70.3% of homes with asphalt roofs in this area were damaged or destroyed").
     Make the data feel personal, not generic.

   - FINANCIAL & INSURABILITY IMPACT: for each recommendation, note whether it is
     likely to improve insurability, qualify for a discount, or satisfy a specific
     insurer requirement (e.g. ember-resistant vents per Safer from Wildfires Tier 1).
     Mention cost tier where meaningful (low/medium/high effort).

   - RAG SOURCES: ground each recommendation in CalFire home hardening guidelines
     and/or the Safer from Wildfires program, but only where directly applicable
     to this property's actual vulnerabilities. Do not cite guidelines generically.

   GUARDRAILS (these are hard rules, not suggestions):
   - Quality over quantity. Return only recommendations you can fully ground in the
     provided data. 1 strong recommendation is better than 3 generic ones.
   - Never invent property characteristics, destruction rates, or insurer requirements
     that were not provided in the context.
   - If you have insufficient data to produce even 1 grounded recommendation, set
     "mitigation_recommendations" to exactly the string "INSUFFICIENT_DATA" — 
     no explanation, no apology, just that string.

    If a homeowner's property characteristic is notably protective compared to nearby
    destroyed structures (e.g. their roof or siding material appears in significantly
    fewer destroyed homes), you may open with a single sentence acknowledging this
    before the recommendations. Only do this if the data clearly supports it.
    Do not manufacture encouragement.

5. CONFIDENCE: "high", "medium", or "low" based on data availability.

Be direct. The homeowner already lives here — do not frame this as a purchase decision.
Focus on what they can control. Use <strong> tags for 3-5 key terms per section.

If additional context is provided, factor it into all assessments.

If California DOI non-renewal data is provided in context, use it to strengthen or 
qualify your insurance outlook assessment. Reference the non-renewal rate, trend direction, 
and rate change in percentage points where relevant. A worsening trend with a high 
non-renewal rate is a strong signal of insurance market withdrawal from the area.

You must respond ONLY with a valid JSON object in exactly this format:
{
  "home_value_impact": "...",
  "insurance_outlook": "...",
  "affordability_score": "...",
  "mitigation_recommendations": "...",
  "confidence": "high" or "medium" or "low"
}
"""

    BUYER_SYSTEM_PROMPT = """
You are a wildfire risk analyst helping a prospective buyer evaluate whether a 
California property is a sound investment given wildfire risk.

Frame all analysis around: should they buy, and what are the financial risks if they do.

Given a property location, assess:
1. HOME VALUE IMPACT: How wildfire risk may affect property value short-term (1-2 years)
   and long-term (5-10 years). Flag if the area shows signs of systemic devaluation 
   driven by fire risk or insurance market withdrawal.

2. INSURANCE OUTLOOK: The likelihood of obtaining private insurance coverage as a new 
   buyer, probability of being forced onto the FAIR Plan immediately, expected costs,
   and which insurers have withdrawn from the region. If California DOI non-renewal
   data is provided in context, reference the non-renewal rate and trend — a high or
   worsening non-renewal rate means new buyers may struggle to obtain private coverage
   at all, which should factor heavily into the purchase decision.

3. AFFORDABILITY SCORE: A plain-language assessment of whether this property is 
   financially viable to own given fire risk, insurance costs, and value trends. 
   Flag systemic unaffordability risks explicitly.

4. CONFIDENCE: "high", "medium", or "low" based on data availability.

Be direct. The buyer has not yet committed — give them the information they need 
to make an informed decision. Use <strong> tags for 3-5 key terms per section.

If additional context is provided, factor it into all assessments.

If California DOI non-renewal data is provided in context, use it to strengthen or 
qualify your insurance outlook assessment. Reference the non-renewal rate, trend direction, 
and rate change in percentage points where relevant. A worsening trend with a high 
non-renewal rate is a strong signal of insurance market withdrawal from the area.

You must respond ONLY with a valid JSON object in exactly this format:
{
  "home_value_impact": "...",
  "insurance_outlook": "...",
  "affordability_score": "...",
  "mitigation_recommendations": null,
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
        self.rag_k = 6 ## TODO adjust 

        self.temperature = 0.2 ## TODO tune


    def analyze(self, lat:float, lon:float, extra_context: Optional[str] = None, user_type: Optional[str] = None) -> Dict:
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

        if user_type == "homeowner":
            query += (
                "\n\nAlso retrieve home hardening and mitigation guidance relevant to this property, "
                "including CalFire home hardening recommendations, Safer from Wildfires program requirements, "
                "and retrofit or defensible space guidelines."
                "\n\nKnown guideline sources to cite inline when relevant:"
                "\n- CAL FIRE Home Hardening (eaves, vents, siding, roof, fences, defensible space): https://www.fire.ca.gov/home-hardening"
                "\n- CAL FIRE Low-Cost Retrofit List: https://www.fire.ca.gov/home-hardening"
                "\n- Safer from Wildfires program: https://www.insuranceca.gov/saferfromwildfires"
                "\n- Defensible Space guide: https://www.readyforwildfire.org/prepare-for-wildfire/get-ready/defensible-space/"
            )

        if extra_context:
            query += f"\n\n Additional context: {extra_context}"

        if user_type == "homeowner":
            system_prompt = self.HOMEOWNER_SYSTEM_PROMPT
        elif user_type == "buyer":
            system_prompt = self.BUYER_SYSTEM_PROMPT
        else:
            system_prompt = self.SYSTEM_PROMPT  

        ## debug print
        print("QUERY : ")    
        print(query)

        response = self.client.generate(
            model=self.model,
            system= system_prompt,
            query=query,
            temperature=self.temperature,
            session_id = self.session_id, 
            rag_usage=True,
            rag_threshold=self.rag_threshold,
            rag_k=self.rag_k,
            lastk=self.last_k,
        )

        # debug print checking RAG
        print(json.dumps(response, indent=2))

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
    
    def explain_gauge(self, composite_label: str, signals: list, risk_factor_count: int) -> dict:
        signal_texts = [s["text"] if isinstance(s, dict) else s for s in signals]
        signal_data = []
        for i, s in enumerate(signals):
            signal_data.append({
                "index": i,
                "text": s["text"] if isinstance(s, dict) else s,
                "direction": s.get("direction", "neutral") if isinstance(s, dict) else "neutral"
            })

        query = f"""
    Risk score: {composite_label}
    Risk factors triggered: {risk_factor_count} of 4

    Signals:
    {chr(10).join(f'{i}. {s["text"]}' for i, s in enumerate(signal_data))}

    Return a JSON object with exactly these two keys:

    "methodology": A 2-sentence static explanation of what the 4 risk indicators are and how they combine into a score. Do not reference specific data values. This should be the same for any property.

    "signal_explanations": A list of objects, one per signal, in the same order as the signals above. Each object has:
    - "index": the signal number (0-based)
    - "explanation": one sentence explaining the magnitude or significance of this specific signal. Use specific numbers where available. Do not restate the signal text. Focus on what the magnitude means — is this value high, low, or typical? What does it imply about risk level?

    Return only valid JSON, no markdown.
    """
        response = self.client.generate(
            model=self.model,
            system="You are a wildfire risk analyst. Return only valid JSON.",
            query=query,
            temperature=0.2,
            session_id=self.session_id,
            rag_usage=False,
            lastk=0,
        )
        
        raw = response.get("result", "").strip()
        cleaned = re.sub(r"```json|```", "", raw).strip()
        
        try:
            return json.loads(cleaned)
        except (json.JSONDecodeError, TypeError):
            return {
                "methodology": "This score is computed from 4 objective indicators: fire proximity trend, fire frequency trend, official hazard zone classification, and recent fire distances.",
                "signal_explanations": []
            }
            
    def generate_chart_observations(
        self,
        zipcode: str,
        price_trajectory: dict,
        rent_trajectory: dict,
        fire_proximity: dict,
        fire_frequency: dict,
        cross_signals: dict,
    ) -> str:
        
        query = f"""
    You are analyzing home value and wildfire data for ZIP code {zipcode}.

    Home value data:
    - Current median value: ${price_trajectory.get('current_value', 'N/A')}
    - 5-year change: {price_trajectory.get('pct_change_5yr', 'N/A')}% ({price_trajectory.get('trend_label', 'N/A')})
    - Full date range: {price_trajectory.get('year_range', 'N/A')}

    Rent data (Zillow ZIP-level):
    - Current median rent: ${rent_trajectory.get('current_value', 'N/A')}
    - 5-year change: {rent_trajectory.get('pct_change_5yr', 'N/A')}% ({rent_trajectory.get('trend_label', 'N/A')})
    - Full date range: {rent_trajectory.get('year_range', 'N/A')}
    - Data available: {rent_trajectory.get('available', False)}

    Wildfire proximity data:
    - Total fires within 30 miles: {fire_frequency.get('total_fires', 0)}
    - Fire frequency trend: {fire_frequency.get('trend_label', 'N/A')}
    - Proximity trend: {fire_proximity.get('trend_label', 'N/A')}
    - Historical avg distance: {fire_proximity.get('historical_avg_distance_miles', 'N/A')} miles
    - Recent avg distance (last 5 years): {fire_proximity.get('recent_avg_distance_miles', 'N/A')} miles
    - Closest recorded fire: {fire_proximity.get('closest_fire', {}).get('fire_name', 'N/A')} ({fire_proximity.get('closest_fire', {}).get('year', 'N/A')}, {fire_proximity.get('closest_fire', {}).get('distance_miles', 'N/A')} miles)

    Cross-signal stats (distance vs market metrics):
    - Data available: {cross_signals.get('available', False)}
    - Home overlap years: {cross_signals.get('home_overlap_years', 'N/A')}
    - Rent overlap years: {cross_signals.get('rent_overlap_years', 'N/A')}
    - Corr(home values, fire distance): {cross_signals.get('home_fire_distance_corr', 'N/A')}
    - Corr(rent, fire distance): {cross_signals.get('rent_fire_distance_corr', 'N/A')}

    Generate concise bullet points in exactly these four sections:
    HOME TRENDS: (1-2 bullets about what the price chart shows)
    RENT TRENDS: (1-2 bullets about what the rent chart shows; if unavailable, say "Rent data unavailable for this ZIP.")
    WILDFIRE TRENDS: (1-2 bullets about what the fire proximity chart shows)
    CROSS-OBSERVATIONS: (1-2 bullets connecting fire activity to price behavior, if any pattern exists)

    Rules:
    - Be specific, use numbers
    - Do not give advice or recommendations  
    - Do not repeat data verbatim, interpret it
    - CROSS-OBSERVATIONS must reference at least one numeric cross-signal when available
    - Only claim "no clear relationship" if both correlations are unavailable or both are between -0.2 and 0.2
    - Return only the bullets, no extra text
    """
        response = self.client.generate(
            model=self.model,
            system="You are a data analyst summarizing charts for a homeowner.",
            query=query,
            temperature=0.2,
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

