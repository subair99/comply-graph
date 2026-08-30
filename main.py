import os
import httpx
import base64
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

# THIS IS THE EXACT ROUTE YOU NEED
@app.post("/api/v1/ingest-and-extract")
async def ingest_document(file: UploadFile = File(...)):
    """
    MILESTONE 1: Ingest messy PDF and trigger Nutrient DWS Extraction.
    """
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    # Read the uploaded file into memory
    file_content = await file.read()
    
    # --- MOCK RESPONSE FOR NOW (So you can test the UI immediately) ---
    # We will replace this with the real Nutrient API call in the next step.
    mock_extraction_result = {
        "status": "success",
        "data": {
            "supplier_name": "Acme Globex Ltd",
            "vat_id": "FR123456789",
            "total_amount": 15000.00,
            "invoice_date": "2026-08-30"
        },
        "confidence_scores": {
            "supplier_name": 0.95,
            "vat_id": 0.65,  # Low confidence to trigger SerpApi later!
            "total_amount": 0.88
        }
    }

    return {
        "message": "Document ingested and extracted successfully",
        "filename": file.filename,
        "extracted_data": mock_extraction_result["data"],
        "confidence_scores": mock_extraction_result["confidence_scores"],
        "next_step": "Evaluate confidence scores. If < 0.85, trigger SerpApi cross-check."
    }