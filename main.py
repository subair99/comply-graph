import os
import json
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from jinja2 import Template  # <-- ADDED: Local templating engine

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="ComplyGraph AI Orchestrator",
    description="Multi-agent compliance engine for e-invoicing",
    version="1.0.0"
)

# --- API KEY CONFIGURATION ---
DWS_PROCESSOR_API_KEY = os.getenv("DWS_PROCESSOR_API_KEY")
DWS_EXTRACTION_API_KEY = os.getenv("DWS_EXTRACTION_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
XANO_API_URL = os.getenv("XANO_API_URL")

# --- Pydantic Models for VAT Validation ---
class VATValidationRequest(BaseModel):
    vat_id: str
    supplier_name: Optional[str] = None
    country_code: Optional[str] = None

class SearchResult(BaseModel):
    title: str
    link: str
    snippet: str
    is_official_registry: bool

class VATValidationResponse(BaseModel):
    vat_id: str
    validation_status: str
    search_query_used: str
    top_results: List[SearchResult]
    recommended_action: str

# --- Pydantic Models for Document Generation ---
class DocumentGenerationRequest(BaseModel):
    extracted_data: Dict[str, Any]
    template_id: str = "factur_x_en16931"
    jurisdiction: str = "FR"
    approved_by_human: bool = True

class DocumentGenerationResponse(BaseModel):
    status: str
    document_id: str
    template_used: str
    jurisdiction_applied: str
    compliant_xml_payload: str  # <-- Changed from download_url to show the generated compliant structure
    message: str

@app.get("/")
def health_check():
    return {"status": "ComplyGraph Orchestrator is online", "version": "1.0.0"}

@app.post("/api/v1/ingest-and-extract")
async def ingest_document(file: UploadFile = File(...)):
    """MILESTONE 1: Ingest messy PDF and trigger Nutrient DWS Extraction."""
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    file_content = await file.read()

    extraction_schema = {
        "type": "object",
        "properties": {
            "supplier_name": {"type": "string", "description": "Name of the supplier"},
            "vat_id": {"type": "string", "description": "VAT identification number"},
            "total_amount": {"type": "number", "description": "Final total amount"},
            "invoice_date": {"type": "string", "format": "date", "description": "Invoice date"}
        },
        "required": ["supplier_name", "vat_id", "total_amount"]
    }

    instructions = {
        "schema": extraction_schema,
        "parseConfig": {"mode": "understand"},
        "options": {"includeCitations": True, "strict": False, "multimodal": False}
    }

    files = {"file": (file.filename, file_content, "application/pdf")}
    data = {"instructions": json.dumps(instructions)}
    headers = {"Authorization": f"Bearer {DWS_EXTRACTION_API_KEY}"}

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.nutrient.io/extraction/extract",
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Nutrient DWS API Error: {response.text}")
            
            result = response.json()
            extracted_data = result.get("output", {}).get("data", {})
            metadata = result.get("output", {}).get("metadata", {})
            
            confidence_scores = {}
            for field, field_meta in metadata.items():
                if isinstance(field_meta, dict) and "confidence" in field_meta:
                    confidence_scores[field] = field_meta["confidence"]
                else:
                    confidence_scores[field] = 0.0

            low_confidence_fields = [field for field, score in confidence_scores.items() if score < 0.85]
            next_step = f"Low confidence in: {', '.join(low_confidence_fields)}. Trigger SerpApi cross-check." if low_confidence_fields else "All fields exceed 0.85 confidence. Proceed to template generation."

            return {
                "message": "Document ingested successfully",
                "filename": file.filename,
                "extracted_data": extracted_data,
                "confidence_scores": confidence_scores,
                "next_step": next_step,
                "low_confidence_fields": low_confidence_fields
            }

    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Network error: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(exc)}")

@app.post("/api/v1/validate-vat", response_model=VATValidationResponse)
async def validate_vat(request: VATValidationRequest):
    """MILESTONE 2: Cross-reference extracted VAT ID against live web registries using SerpApi."""
    if not request.vat_id and not request.supplier_name:
        raise HTTPException(status_code=400, detail="Either vat_id or supplier_name is required")

    query_parts = []
    if request.vat_id: query_parts.append(f'"{request.vat_id}"')
    if request.supplier_name: query_parts.append(request.supplier_name)
    if request.country_code: query_parts.append(request.country_code)
    query_parts.append("VAT registration")
    search_query = " ".join(query_parts)

    params = {"engine": "google", "q": search_query, "api_key": SERPAPI_API_KEY, "num": 5}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"SerpApi Error: {response.text}")
            serp_data = response.json()

        organic_results = serp_data.get("organic_results", [])
        processed_results = []
        validation_status = "not_found"
        trusted_domains = ["ec.europa.eu", "vies", "impots.gouv.fr", "finanzamt", "gov."]

        for result in organic_results[:3]:
            title = result.get("title", "")
            link = result.get("link", "")
            snippet = result.get("snippet", "")
            is_official = any(domain in link.lower() for domain in trusted_domains)
            
            if is_official or "valid" in snippet.lower() or "active" in snippet.lower():
                validation_status = "likely_valid"
                
            processed_results.append(SearchResult(title=title, link=link, snippet=snippet, is_official_registry=is_official))

        if not processed_results:
            recommended_action = "No web registry found. Manual offline verification required."
        elif validation_status == "likely_valid":
            recommended_action = "Registry match found. Please review the snippet and confirm to proceed."
        else:
            validation_status = "requires_review"
            recommended_action = "Low confidence match. Human review required to verify VAT ID."

        return VATValidationResponse(
            vat_id=request.vat_id or "Not provided",
            validation_status=validation_status,
            search_query_used=search_query,
            top_results=processed_results,
            recommended_action=recommended_action
        )

    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Network error connecting to SerpApi: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error during validation: {str(exc)}")

@app.post("/api/v1/generate-compliant-document", response_model=DocumentGenerationResponse)
async def generate_compliant_document(request: DocumentGenerationRequest):
    """
    MILESTONE 3: Use Jinja2 branching logic to generate a jurisdiction-compliant 
    Factur-X/ZUGFeRD XML structure from approved extracted data (Replaces Doctavian).
    """
    if not request.approved_by_human:
        raise HTTPException(status_code=403, detail="Document generation requires human approval flag.")
    if not request.extracted_data:
        raise HTTPException(status_code=400, detail="extracted_data is required")

    # 1. Define the Factur-X / EN16931 compliant XML template with BRANCHING LOGIC
    factur_x_template = """<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                          xmlns:qdt="urn:un:unece:uncefact:data:standard:QualifiedDataType:100"
                          xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
                          xmlns:xs="http://www.w3.org/2001/XMLSchema"
                          xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
  <rsm:ExchangedDocumentContext>
    <ram:GuidelineSpecifiedDocumentContextParameter>
      <ram:ID>urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:{{ jurisdiction | lower }}</ram:ID>
    </ram:GuidelineSpecifiedDocumentContextParameter>
  </rsm:ExchangedDocumentContext>
  <rsm:ExchangedDocument>
    <ram:ID>INV-{{ extracted_data.invoice_date | replace('-', '') }}</ram:ID>
    <ram:TypeCode>380</ram:TypeCode>
    <ram:IssueDateTime>
      <udt:DateTimeString format="102">{{ extracted_data.invoice_date | replace('-', '') }}</udt:DateTimeString>
    </ram:IssueDateTime>
  </rsm:ExchangedDocument>
  <rsm:SupplyChainTradeTransaction>
    <ram:ApplicableHeaderTradeAgreement>
      <ram:SellerTradeParty>
        <ram:Name>{{ extracted_data.supplier_name }}</ram:Name>
        <ram:SpecifiedTaxRegistration>
          <ram:ID schemeID="VA">{{ extracted_data.vat_id }}</ram:ID>
        </ram:SpecifiedTaxRegistration>
      </ram:SellerTradeParty>
    </ram:ApplicableHeaderTradeAgreement>
    <ram:ApplicableHeaderTradeSettlement>
      <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
      <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        <ram:TaxBasisTotalAmount>{{ extracted_data.total_amount }}</ram:TaxBasisTotalAmount>
        <ram:GrandTotalAmount>{{ extracted_data.total_amount }}</ram:GrandTotalAmount>
      </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
      {% if jurisdiction == 'FR' %}
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{{ (extracted_data.total_amount * 0.20) | round(2) }}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>{{ extracted_data.total_amount }}</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>20.0</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      {% elif jurisdiction == 'DE' %}
      <ram:ApplicableTradeTax>
        <ram:CalculatedAmount>{{ (extracted_data.total_amount * 0.19) | round(2) }}</ram:CalculatedAmount>
        <ram:TypeCode>VAT</ram:TypeCode>
        <ram:BasisAmount>{{ extracted_data.total_amount }}</ram:BasisAmount>
        <ram:CategoryCode>S</ram:CategoryCode>
        <ram:RateApplicablePercent>19.0</ram:RateApplicablePercent>
      </ram:ApplicableTradeTax>
      {% endif %}
    </ram:ApplicableHeaderTradeSettlement>
  </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
    """

    try:
        # 2. Render the template with the extracted data (This is the "Branching Logic")
        template = Template(factur_x_template)
        compliant_xml = template.render(
            extracted_data=request.extracted_data,
            jurisdiction=request.jurisdiction.upper()
        )

        # 3. Return the successfully generated compliant structure
        return DocumentGenerationResponse(
            status="success",
            document_id=f"doc_{request.extracted_data.get('supplier_name', 'unknown').replace(' ', '_').lower()}_{request.jurisdiction}",
            template_used=request.template_id,
            jurisdiction_applied=request.jurisdiction.upper(),
            compliant_xml_payload=compliant_xml,
            message=f"Successfully generated {request.jurisdiction.upper()}-compliant Factur-X XML. Ready for Foxit MCP prep."
        )

    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error during template generation: {str(exc)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)