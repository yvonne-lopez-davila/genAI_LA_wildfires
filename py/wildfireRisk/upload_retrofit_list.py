"""
Fetches and uploads CAL FIRE Low-Cost Retrofit List (Jan 2026) to LLMProxy RAG.
One-time ingest script.

Source: https://www.fire.ca.gov/home-hardening
"""

import time
from llmproxy import LLMProxy
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = "LA_risk_analysis"

RETROFIT_CONTENT = """CAL FIRE Low-Cost Retrofit List — Updated January 2026
Source: https://www.fire.ca.gov/home-hardening

This list was developed as a best practices guide to assist homeowners in making their home more ignition-resistant from wildfires. "Low cost" is subjective — some items apply when a feature is due for replacement during normal maintenance.

SECTION 1: Low-Cost Ways to Harden Your Home

1. When replacing your roof, use a Class A fire-rated roof covering (e.g. asphalt fiberglass shingles, tile, metal panels).
2. Block spaces between roof covering and sheathing with noncombustible materials (bird stops).
3. Install a noncombustible gutter cover to prevent debris accumulation.
4. Cover chimney and stovepipe outlets with noncombustible corrosion-resistant metal mesh (3/8 to 1/2 inch openings — spark arrestor).
5. Install ember and flame-resistant vents (consult local building official — modifications may reduce airflow).
6. Caulk and plug gaps greater than 1/8 inch around exposed rafters and blocking to prevent ember intrusion into attic.
7. Inspect exterior siding for dry rot, gaps, cracks, and warping. Caulk or plug gaps greater than 1/8 inch; replace damaged boards.
8. Install weather-stripping compliant with UL Standard 10C to garage door gaps greater than 1/8 inch.
9. When replacing windows, use multi-paned windows with at least one pane of tempered glass.
10. When replacing siding or deck, use noncombustible, ignition-resistant, or OSFM WUI-listed products.
11. Cover operable skylight openings with noncombustible metal mesh screen (openings not exceeding 1/8 inch).
12. Install minimum 6-inch metal flashing vertically on exterior wall at deck-to-wall intersection to protect combustible siding.

SECTION 2: Low-Cost Ways to Create Defensible Space

1. Regularly clean roof, gutters, decks, and base of walls to remove fallen leaves, needles, and flammable debris.
2. Remove all combustible materials from underneath, on top of, or within five feet of a deck.
3. Remove vegetation or combustibles within five feet of windows and glass doors.
4. Replace wood mulch within five feet of all structures with noncombustible alternatives (dirt, stone, gravel).
5. Remove dead or dying grass, plants, shrubs, trees, branches, leaves, weeds, and pine needles within 30 feet of all structures or to the property line.
6. Store exposed firewood at least 30 feet from structures or cover in fire-resistant material; maintain 10 feet clearance around wood piles.
7. Store combustible outdoor furnishings away from home when not in use.
8. Properly store retractable awnings and umbrellas when not in use to prevent ember and leaf accumulation.
"""


def main():
    proxy = LLMProxy()

    result = proxy.upload_text(
        text=RETROFIT_CONTENT,
        session_id=SESSION_ID,
        description="CAL FIRE Low-Cost Retrofit List — home hardening and defensible space actions (Jan 2026)",
        strategy="smart",
    )

    if "error" in result:
        print(f"FAILED: {result['error']}")
    else:
        print("Uploaded: CAL FIRE Low-Cost Retrofit List")


if __name__ == "__main__":
    main()