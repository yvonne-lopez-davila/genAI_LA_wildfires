from llmproxy import LLMProxy
from dotenv import load_dotenv

load_dotenv()

client = LLMProxy()

result = client.upload_file(
    file_path="./RAG-sources/wildfire-action/FAQ-Safer-from-Wildfire-Regulation.pdf",
    session_id="LA_risk_analysis",  # matches your HomeRiskClient session_id
    mime_type="application/pdf",
    description="Safer from Wildfires FAQ — California DOI guidance on wildfire mitigation and insurability",
    strategy="smart",
)

print(result)