"""
Uploads CAL FIRE Home Hardening content to LLMProxy RAG.
Content sourced from https://www.fire.ca.gov/home-hardening
One-time ingest script.
"""

import time
from llmproxy import LLMProxy
from dotenv import load_dotenv

load_dotenv()

SESSION_ID = "LA_risk_analysis"

CHUNKS = [
    {
        "component": "Roof and Roof Attachments",
        "text": """CAL FIRE Home Hardening — Roof and Roof Attachments
Source: https://www.fire.ca.gov/home-hardening

Your roof is one of the most vulnerable areas of your home due to its large surface area and susceptibility to embers and flame.

Vulnerabilities:
- Combustible roof coverings such as non-fire-retardant wood shake or shingle. California requires Class A-rated roof coverings.
- Gaps or openings in roof assembly exposing unprotected components.
- Debris accumulation, especially near combustible wall intersections.

Recommendations:
- Keep roof clear of debris and vegetation.
- Fill gaps between roof covering and sheathing to prevent ember intrusion.
- When replacing, install Class A-rated covering: asphalt fiberglass shingles, tile, cement shingles, or metal panels.
- Replace combustible siding at roof-to-wall intersections with noncombustible siding.
- Keep areas around roof attachments (e.g. solar panels) free of debris.
- Ensure skylights have noncombustible metal mesh screen (max 1/8 inch) and multipaned glazing with one tempered layer.
- Install metal flashing around exposed wood frame skylights."""
    },
    {
        "component": "Gutters",
        "text": """CAL FIRE Home Hardening — Gutters
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Gutters without covers accumulate debris, making them susceptible to embers. Ignited debris exposes combustible roof assembly areas.
- Combustible gutters (e.g. vinyl) can catch fire and expose roof assembly.

Recommendations:
- Install noncombustible gutter cover to reduce debris buildup.
- When replacing, use noncombustible gutters such as metal.
- Ensure roof has metal drip edge that completely covers the space above the gutter system."""
    },
    {
        "component": "Vents",
        "text": """CAL FIRE Home Hardening — Vents
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Attic and crawlspace vents are entry points for embers or flames that can ignite interior combustibles.
- Ridge or off-ridge vents on roofs are more susceptible.
- Vents made of flammable materials (e.g. plastic) are highly vulnerable.

Recommendations:
- Replace vents with CA State Fire Marshal-approved flame and ember-resistant vents, or cover with noncombustible corrosion-resistant metal mesh (1/16 to 1/8 inch diameter).
- Note: fire protection modifications may reduce airflow — consult local building official before replacing.
- Keep debris away from all vents.
- Seal all openings around blocking in vent areas."""
    },
    {
        "component": "Eaves",
        "text": """CAL FIRE Home Hardening — Eaves
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Open eave construction with gaps between rafter tails and blocking are ember entry points.
- Wide overhangs and combustible fuel sources near home create fire pathways to eaves.

Recommendations:
- Remove vegetation and combustibles directly below eaves.
- Create a soffit or enclosed eave using noncombustible material.
- Inspect and caulk gaps around rafter roof tails and blocking."""
    },
    {
        "component": "Exterior Siding",
        "text": """CAL FIRE Home Hardening — Exterior Siding
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Combustible siding can provide flame pathways to windows, eave areas, and vents.
- Gaps or penetrations larger than 1/8 inch in exterior covering.
- Roof-to-wall areas with combustible siding present.

Recommendations:
- Plug or repair all gaps, holes, or rot in exterior siding.
- Replace combustible siding with noncombustible or ignition-resistant material.
- If full replacement isn't possible, replace the bottom 2 feet with noncombustible material and add metal flashing at bottom edge."""
    },
    {
        "component": "Windows",
        "text": """CAL FIRE Home Hardening — Windows
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Single-pane and large windows are vulnerable to radiant heat breakage even before fire arrives.
- Combustible framing can ignite, causing glass to fall and opening a path for embers.
- Vinyl windows without internal reinforcement bar prone to deformation from radiant heat.

Recommendations:
- Install double-pane tempered glass windows (4x more resistant to breakage during wildfire).
- Use noncombustible metal framing where possible.
- Create 0-5 foot ember-resistant zone by removing vegetation around all windows.
- Install metal mesh window screens to improve radiant heat performance."""
    },
    {
        "component": "Exterior Doors and Garage",
        "text": """CAL FIRE Home Hardening — Exterior Doors and Garage
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Doors with rot, decay, or gaps greater than 1/8 inch allow ember intrusion.
- Combustible door framing where embers accumulate at thresholds and sides.
- Garage doors lacking gasketing or with gaps that allow ember intrusion.
- Combustibles stored near ignition sources inside garage.

Recommendations:
- Replace non-compliant wood screen or sliding doors with noncombustible option.
- Install metal mesh screens in sliding or screen doors.
- Add metal flashing at garage door jambs and headers.
- Add gasketing (weather-stripping) to garage doors to prevent ember intrusion.
- Relocate combustibles inside garage away from ignition sources."""
    },
    {
        "component": "Decks, Porches, Balconies, and Stairs",
        "text": """CAL FIRE Home Hardening — Decks, Porches, Balconies, and Stairs
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Combustible or rotting deck boards are easily ignitable.
- Deck-to-wall intersections with combustible siding and no metal flashing.
- Combustibles within 0-5 feet zone (patio furniture, planter boxes, door mats).
- Decks overhanging slopes exposed to flames from vegetation downslope.

Recommendations:
- Create ember-resistant zone under deck extending 5 feet outward using hardscapes (gravel, pavers, concrete).
- Replace deck boards with ignition-resistant, noncombustible, or fire-retardant-treated material.
- Install minimum 6-inch metal flashing vertically at deck-to-wall intersections.
- If full replacement not possible, replace the first 1 foot of walking surface nearest the residence with noncombustible material.
- Remove combustibles stored under deck and clear debris regularly."""
    },
    {
        "component": "Fences",
        "text": """CAL FIRE Home Hardening — Fences
Source: https://www.fire.ca.gov/home-hardening

Vulnerabilities:
- Combustible fences attached to home create a direct fire pathway.
- Vegetative debris accumulating at fence base, especially climbing plants.
- Privacy fences provide ledge and backstop where embers accumulate.

Recommendations:
- Replace attached combustible fencing or gates with noncombustible option for the first 8 feet from home.
- Parallel combustible fences should be at least 10 feet from residence (20 feet if double/neighboring fences).
- Clean vegetative debris from base and surface of fence.
- When replacing, use noncombustible or ignition-resistant fencing materials."""
    },
    {
        "component": "Defensible Space and Accessory Structures",
        "text": """CAL FIRE Home Hardening — Defensible Space and Accessory Structures
Source: https://www.fire.ca.gov/home-hardening

Accessory building vulnerabilities:
- Outbuildings (sheds, carports) when ignited burn longer and can project embers toward home.
- Plastic sheds are the most hazardous.

Recommended distances for combustible sheds:
- Larger than 120 sq ft: 50 feet from home
- 120 to 64 sq ft: 40 feet from home
- Smaller than 64 sq ft: 30 feet from home

Recommended distances for Chapter 7A compliant sheds:
- Noncombustible steel sheds under 64 sq ft: 10 feet
- Combustible sheds under 16 sq ft: 10 feet
- Combustible sheds 20-64 sq ft: 15 feet

General defensible space actions:
- Create 10-foot ember-resistant zone around all accessory buildings.
- Ensure accessory building door does not face the home.
- Remove dead vegetation within 30 feet of all structures.
- Store firewood at least 30 feet from structures with 10 feet clearance around wood piles.
- Remove combustibles within 5 feet of decks, windows, and doors.
- Replace wood mulch within 5 feet of structures with noncombustible alternatives (gravel, stone, dirt)."""
    },
]


def main():
    proxy = LLMProxy()
    success, failed = 0, 0

    print(f"Uploading {len(CHUNKS)} home hardening sections...")

    for chunk in CHUNKS:
        result = proxy.upload_text(
            text=chunk["text"],
            session_id=SESSION_ID,
            description=f"CAL FIRE Home Hardening: {chunk['component']}",
            strategy="smart",
        )
        if "error" in result:
            print(f"  FAILED [{chunk['component']}]: {result['error']}")
            failed += 1
        else:
            print(f"  Uploaded: {chunk['component']}")
            success += 1
        time.sleep(0.5)

    print(f"\nDone. {success} uploaded, {failed} failed.")


if __name__ == "__main__":
    main()