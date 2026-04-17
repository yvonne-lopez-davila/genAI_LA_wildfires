from llmproxy import LLMProxy
from dotenv import load_dotenv

load_dotenv()

client = LLMProxy()

result = client.upload_file(
    file_path="./RAG-sources/insurance-trends/CDI-Fact-Sheet-Summary-on-Residential-Insurance-Policies-and-the-FAIR-Plan.pdf",
    session_id="LA_risk_analysis",  # matches your HomeRiskClient session_id
    mime_type="application/pdf",
    description="FAIR Plan fact sheet gives context to Fair Plan growth trends",
    strategy="smart",
)

print(result)