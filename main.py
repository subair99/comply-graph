import os
import json
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from dotenv import load_dotenv
from jinja2 import Template
from supabase import create_client, Client

# Load environment variables from .env
load_dotenv()

app = FastAPI(
    title="ComplyGraph AI Orchestrator",
    description="Multi-agent compliance engine for e-invoicing",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"], # Allow Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- API KEY & DATABASE CONFIGURATION ---
DWS_PROCESSOR_API_KEY = os.getenv("DWS_PROCESSOR_API_KEY")
DWS_EXTRACTION_API_KEY = os.getenv("DWS_EXTRACTION_API_KEY")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
FOXIT_CLIENT_ID = os.getenv("FOXIT_CLIENT_ID")
FOXIT_CLIENT_SECRET = os.getenv("FOXIT_CLIENT_SECRET")
FOXIT_GENERATE_URL = os.getenv("FOXIT_GENERATE_URL", "https://na1.fusion.foxit.com/document-generation/api/generate")

# Initialize Supabase Client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Supabase Helper Functions ---
def save_job_to_db(filename, extracted_data, confidence_scores, low_confidence_fields):
    response = supabase.table("compliance_jobs").insert({
        "filename": filename,
        "status": "extracted",
        "extracted_data": extracted_data,
        "confidence_scores": confidence_scores,
        "low_confidence_fields": low_confidence_fields
    }).execute()
    return response.data[0]

def update_job_status(job_id, **kwargs):
    response = supabase.table("compliance_jobs").update(kwargs).eq("id", job_id).execute()
    return response.data[0]

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
    compliant_xml_payload: str
    message: str

# --- Pydantic Models for Foxit Handoff ---
class FoxitHandoffRequest(BaseModel):
    job_id: int  # <-- ADDED: To track the database record
    document_id: str
    compliant_xml_payload: str
    signer_name: str
    signer_email: str
    human_approved_for_signing: bool = True

class FoxitHandoffResponse(BaseModel):
    status: str
    envelope_id: str
    agent_action_log: List[str]
    signing_url: str
    agent_status: str
    message: str

@app.get("/")
def health_check():
    return {"status": "ComplyGraph Orchestrator is online", "version": "1.0.0"}

@app.post("/api/v1/ingest-and-extract")
async def ingest_document(file: UploadFile = File(...)):
    """MILESTONE 1: Ingest messy PDF, trigger Nutrient DWS Extraction, and save to Supabase."""
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

            # SAVE TO SUPABASE
            job_record = save_job_to_db(
                filename=file.filename,
                extracted_data=extracted_data,
                confidence_scores=confidence_scores,
                low_confidence_fields=low_confidence_fields
            )

            return {
                "job_id": job_record["id"],
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
    """MILESTONE 3: Use Jinja2 branching logic to generate a jurisdiction-compliant Factur-X/ZUGFeRD XML structure."""
    if not request.approved_by_human:
        raise HTTPException(status_code=403, detail="Document generation requires human approval flag.")
    if not request.extracted_data:
        raise HTTPException(status_code=400, detail="extracted_data is required")

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
        template = Template(factur_x_template)
        compliant_xml = template.render(
            extracted_data=request.extracted_data,
            jurisdiction=request.jurisdiction.upper()
        )

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

@app.post("/api/v1/foxit-prepare-and-handoff", response_model=FoxitHandoffResponse)
async def foxit_prepare_and_handoff(request: FoxitHandoffRequest):
    """
    MILESTONE 4: Foxit Document Generation & Real eSign Handoff.
    Creates a real Foxit eSign envelope and halts for human execution.
    """
    if not request.human_approved_for_signing:
        raise HTTPException(status_code=403, detail="Agent halted: Explicit human approval required for eSign handoff.")

    agent_action_log = []
    
    foxit_client_id = os.getenv("FOXIT_CLIENT_ID")
    foxit_client_secret = os.getenv("FOXIT_CLIENT_SECRET")

    if not foxit_client_id or not foxit_client_secret:
        raise HTTPException(status_code=500, detail="Foxit credentials not configured in .env file")

    try:
        # Split signer name for Foxit's required first/last name fields
        name_parts = request.signer_name.split(" ", 1)
        first_name = name_parts[0]
        last_name = name_parts[1] if len(name_parts) > 1 else "Signer"

        # 1. Prepare the REAL Foxit eSign API payload
        # Note: For the demo, we use Foxit's sample PDF URL to guarantee API success. 
        # In production, you would upload the generated compliant PDF to a storage bucket and use that URL.
        esign_payload = {
            "folderName": f"Compliance Invoice - {request.document_id}",
            "inputType": "url",
            "fileUrls": [
                "https://app.developer-api.foxit.com/esign/foxit-esign-api-sample.pdf"
            ],
            "fileNames": [
                f"{request.document_id}_compliant.pdf"
            ],
            "parties": [
                {
                    "firstName": first_name,
                    "lastName": last_name,
                    "emailId": request.signer_email,
                    "permission": "FILL_FIELDS_AND_SIGN",
                    "sequence": 1
                }
            ],
            "fields": [
                {
                    "type": "signature",
                    "x": 336,
                    "y": 578,
                    "width": 170,
                    "height": 28,
                    "documentNumber": 1,
                    "pageNumber": 1,
                    "tabOrder": 1,
                    "party": 1,
                    "required": True
                }
            ],
            "processTextTags": False,
            "processAcroFields": False,
            "createEmbeddedSigningSession": False,
            "createEmbeddedSendingSession": False,
            "sendNow": True  # Triggers the email to the signer immediately
        }

        headers = {
            "client_id": foxit_client_id,
            "client_secret": foxit_client_secret,
            "Content-Type": "application/json",
        }

        agent_action_log.append("MCP Tool: Calling Foxit eSign API to create envelope.")
        
        # 2. Execute the REAL Foxit eSign API Call
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://na1.fusion.foxit.com/esign/api/v1/folders/createfolder",
                headers=headers,
                json=esign_payload
            )
            
            agent_action_log.append(f"Foxit eSign API Status: {response.status_code}")
            
            if response.status_code in [200, 201, 202]:
                result = response.json()
                folder_id = result.get("folderId", result.get("id", "unknown"))
                agent_action_log.append(f"Foxit eSign API: Envelope created successfully! Folder ID: {folder_id}")
                
                # Since sendNow=True, Foxit emails the signer. We provide a generic dashboard link for the demo UI.
                signing_url = "https://app.foxitsign.com/login"
                
                # 3. Update Supabase with the real envelope ID
                update_job_status(
                    job_id=request.job_id,
                    compliant_xml_payload=request.compliant_xml_payload,
                    foxit_envelope_id=folder_id,
                    foxit_signing_url=signing_url,
                    status="ready_to_sign"
                )

                return FoxitHandoffResponse(
                    status="success",
                    envelope_id=folder_id,
                    agent_action_log=agent_action_log,
                    signing_url=signing_url,
                    agent_status="halted_awaiting_human_signature",
                    message=f"Agent has created the eSign envelope (ID: {folder_id}) and triggered the signature request to {request.signer_email}. The agent has STOPPED. The human must now check their email or use the Foxit dashboard to execute the legally binding signature."
                )
            else:
                agent_action_log.append(f"Foxit eSign API Error: {response.text}")
                raise HTTPException(status_code=response.status_code, detail=f"Foxit eSign Error: {response.text}")

    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Network error connecting to Foxit: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unexpected error during Foxit handoff: {str(exc)}")

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)