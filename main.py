import os
import json
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

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
    validation_status: str  # "likely_valid", "requires_review", or "not_found"
    search_query_used: str
    top_results: List[SearchResult]
    recommended_action: str

@app.get("/")
def health_check():
    return {"status": "ComplyGraph Orchestrator is online", "version": "1.0.0"}

@app.post("/api/v1/ingest-and-extract")
async def ingest_document(file: UploadFile = File(...)):
    """
    MILESTONE 1: Ingest messy PDF and trigger Nutrient DWS Extraction.
    """
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read the uploaded file into memory
    file_content = await file.read()

    # 1. Define the JSON schema for structured extraction
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

    # 2. Construct the instructions payload
    instructions = {
        "schema": extraction_schema,
        "parseConfig": {"mode": "understand"},
        "options": {"includeCitations": True, "strict": False, "multimodal": False}
    }

    files = {"file": (file.filename, file_content, "application/pdf")}
    data = {"instructions": json.dumps(instructions)}
    
    # 3. USE THE EXTRACTION KEY (DWS Extraction API)
    headers = {
        "Authorization": f"Bearer {DWS_EXTRACTION_API_KEY}"
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.nutrient.io/extraction/extract",
                headers=headers,
                files=files,
                data=data
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Nutrient DWS API Error: {response.text}"
                )
            
            result = response.json()
            extracted_data = result.get("output", {}).get("data", {})
            metadata = result.get("output", {}).get("metadata", {})
            
            # Extract confidence scores from metadata
            confidence_scores = {}
            for field, field_meta in metadata.items():
                if isinstance(field_meta, dict) and "confidence" in field_meta:
                    confidence_scores[field] = field_meta["confidence"]
                else:
                    confidence_scores[field] = 0.0

            # Evaluate confidence scores
            low_confidence_fields = [
                field for field, score in confidence_scores.items() if score < 0.85
            ]
            
            if low_confidence_fields:
                next_step = f"Low confidence in: {', '.join(low_confidence_fields)}. Trigger SerpApi cross-check."
            else:
                next_step = "All fields exceed 0.85 confidence. Proceed to Doctavian."

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
    """
    MILESTONE 2: Cross-reference extracted VAT ID against live web registries using SerpApi.
    Surfaces deltas and official registry links for Human-in-the-Loop (HITL) review.
    """
    if not request.vat_id and not request.supplier_name:
        raise HTTPException(status_code=400, detail="Either vat_id or supplier_name is required")

    # 1. Construct a targeted search query for EU VAT registries (VIES)
    query_parts = []
    
    if request.vat_id:
        query_parts.append(f'"{request.vat_id}"')
    if request.supplier_name:
        query_parts.append(request.supplier_name)
    if request.country_code:
        query_parts.append(request.country_code)
    
    query_parts.append("VAT registration")
    search_query = " ".join(query_parts)

    # 2. Prepare SerpApi request parameters
    params = {
        "engine": "google",
        "q": search_query,
        "api_key": SERPAPI_API_KEY,
        "num": 5  # Get top 5 results
    }

    try:
        # 3. Call SerpApi asynchronously
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://serpapi.com/search.json", params=params)
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"SerpApi Error: {response.text}"
                )
            
            serp_data = response.json()

        # 4. Process the organic search results
        organic_results = serp_data.get("organic_results", [])
        processed_results = []
        validation_status = "not_found"
        
        # Official domains we trust for EU VAT validation
        trusted_domains = ["ec.europa.eu", "vies", "impots.gouv.fr", "finanzamt", "gov."]

        for result in organic_results[:3]:  # Look at top 3 results
            title = result.get("title", "")
            link = result.get("link", "")
            snippet = result.get("snippet", "")
            
            # Heuristic: Check if the result is from an official registry
            is_official = any(domain in link.lower() for domain in trusted_domains)
            snippet_lower = snippet.lower()
            
            # If we find an official link or keywords like "valid" / "active", upgrade status
            if is_official or "valid" in snippet_lower or "active" in snippet_lower:
                validation_status = "likely_valid"
                
            processed_results.append(
                SearchResult(
                    title=title,
                    link=link,
                    snippet=snippet,
                    is_official_registry=is_official
                )
            )

        # 5. Determine the final status and recommended action
        if not processed_results:
            validation_status = "not_found"
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

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)