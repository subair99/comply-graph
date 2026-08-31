import os
import json
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = FastAPI(
    title="ComplyGraph AI Orchestrator",
    description="Multi-agent compliance engine for e-invoicing",
    version="1.0.0"
)

NUTRIENT_API_KEY = os.getenv("NUTRIENT_API_KEY", "mock_key")
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY", "mock_key")

@app.get("/")
def health_check():
    return {"status": "ComplyGraph Orchestrator is online", "version": "1.0.0"}

@app.post("/api/v1/ingest-and-extract")
async def ingest_document(file: UploadFile = File(...)):
    """
    MILESTONE 1: Ingest messy PDF and trigger Nutrient DWS Extraction.
    Replaces mock data with real API calls and confidence-based routing.
    """
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read the uploaded file into memory
    file_content = await file.read()

    # 1. Define the JSON schema for structured extraction
    extraction_schema = {
        "type": "object",
        "properties": {
            "supplier_name": {
                "type": "string",
                "description": "Name of the supplier or company issuing the invoice"
            },
            "vat_id": {
                "type": "string",
                "description": "VAT identification number of the supplier (e.g., FR123456789)"
            },
            "total_amount": {
                "type": "number",
                "description": "Final total amount of the invoice"
            },
            "invoice_date": {
                "type": "string",
                "format": "date",
                "description": "Date the invoice was issued"
            }
        },
        "required": ["supplier_name", "vat_id", "total_amount"]
    }

    # 2. Construct the instructions payload for Nutrient DWS
    # "understand" mode provides OCR + AI-augmented layout analysis (ideal for messy invoices)
    # "includeCitations": true is required to get per-field confidence scores and bounding boxes
    instructions = {
        "schema": extraction_schema,
        "parseConfig": {"mode": "understand"},
        "options": {
            "includeCitations": True,
            "strict": False,
            "multimodal": False
        }
    }

    # 3. Prepare the multipart form data for the API request
    files = {
        "file": (file.filename, file_content, "application/pdf")
    }
    data = {
        "instructions": json.dumps(instructions)
    }
    headers = {
        "Authorization": f"Bearer {NUTRIENT_API_KEY}"
    }

    try:
        # 4. Call the Nutrient DWS Extraction API asynchronously
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.nutrient.io/extraction/extract",
                headers=headers,
                files=files,
                data=data
            )
            
            # Handle API errors gracefully
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Nutrient DWS API Error: {response.text}"
                )
            
            result = response.json()
            
            # 5. Extract the structured data and metadata (confidence scores)
            extracted_data = result.get("output", {}).get("data", {})
            metadata = result.get("output", {}).get("metadata", {})
            
            # Map metadata to a clean confidence_scores dictionary for the frontend
            confidence_scores = {}
            for field, field_meta in metadata.items():
                if isinstance(field_meta, dict) and "confidence" in field_meta:
                    confidence_scores[field] = field_meta["confidence"]
                else:
                    confidence_scores[field] = 0.0  # Default fallback

            # 6. Evaluate confidence scores to determine the next workflow step
            low_confidence_fields = [
                field for field, score in confidence_scores.items() if score < 0.85
            ]
            
            if low_confidence_fields:
                next_step = f"Low confidence detected in: {', '.join(low_confidence_fields)}. Trigger SerpApi cross-check and HITL review."
            else:
                next_step = "All fields exceed 0.85 confidence. Proceed directly to Doctavian template generation."

            return {
                "message": "Document ingested and extracted successfully",
                "filename": file.filename,
                "extracted_data": extracted_data,
                "confidence_scores": confidence_scores,
                "next_step": next_step,
                "low_confidence_fields": low_confidence_fields
            }

    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Network error connecting to Nutrient DWS: {str(exc)}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(exc)}")