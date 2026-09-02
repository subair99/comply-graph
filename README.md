#  ComplyGraph AI
**Autonomous Cross-Border Compliance & E-Invoicing Agent**

ComplyGraph AI is an agentic pipeline that transforms messy supplier invoices into jurisdiction-compliant e-invoices (Factur-X/ZUGFeRD) and securely hands them off for human signature. Built to solve the upcoming 2026 EU e-invoicing mandates, it combines intelligent document extraction, live regulatory validation, and secure human-in-the-loop (HITL) handoffs.

![ComplyGraph Dashboard](sample-docs/ComplyGraph AI Dashboard.png)
*(Replace the link above with a screenshot of your beautiful UI)*

---

## Key Features

1. **Intelligent Ingestion (Milestone 1):** Uses Nutrient DWS to extract structured data from messy PDFs, complete with confidence scoring.
2. **Live Regulatory Validation (Milestone 2):** Automatically detects low-confidence fields (like VAT IDs) and triggers SerpApi to cross-reference live web registries.
3. **Jurisdiction Branching Logic (Milestone 3):** Uses Jinja2 to dynamically generate Factur-X compliant XML payloads, applying specific tax rules (e.g., 20% VAT for France, 19% for Germany).
4. **Secure Agentic Handoff (Milestone 4):** Prepares the document via Foxit eSign API but **intentionally halts** execution, returning control to the human for the legally binding signature to maintain non-repudiation.

---

## Project Structure

Here is the complete project structure for your **ComplyGraph AI** application, organized by the backend and frontend we built. 

```text
comply-graph-project/
│
├── .env                         # API keys and Supabase credentials (DO NOT COMMIT to GitHub)
├── README.md                    # Professional project documentation for judges
│
├── comply-graph/                # 🐍 Python FastAPI Backend
│   ├── main.py                  # Core orchestration, 4 API endpoints, Jinja2 logic, and Supabase integration
│   ├── pyproject.toml           # Python dependencies (managed via uv)
│   └── sample-docs/             # Test files for the demo
│       └── messy_supplier_invoice.pdf
│
└── comply-graph-ui/             # ⚛️ Next.js Frontend
    ├── package.json             # Node dependencies (Next.js, React, Lucide icons)
    ├── tailwind.config.js       # Tailwind CSS v3 configuration
    ├── postcss.config.js        # PostCSS configuration for Tailwind
    └── src/
        └── app/
            ├── layout.tsx       # Root layout with metadata and Inter font
            ├── page.tsx         # Main dashboard UI, state management, and API fetch logic
            └── globals.css      # Tailwind directives (@tailwind base, etc.)
```

---

## System Architecture

```mermaid
graph TD
    A[User Uploads PDF] --> B(FastAPI Orchestrator)
    B --> C{Nutrient DWS}
    C -->|Extracted JSON + Confidence| D[Supabase Database]
    D --> E{Confidence < 0.85?}
    E -->|Yes| F{SerpApi Live Validation}
    E -->|No| G[Jinja2 Factur-X Generator]
    F -->|Human Approves| G
    G -->|Compliant XML| H[Foxit eSign API]
    H -->|Envelope Created| I[Agent HALTS]
    I --> J[Human Executes Signature]
```

---

## ️Tech Stack

- **Backend Orchestration:** Python, FastAPI, httpx
- **Frontend UI:** Next.js 14, React, Tailwind CSS, Lucide Icons
- **Database & State:** Supabase (PostgreSQL)
- **Document AI:** Nutrient DWS (Extraction API)
- **Live Web Search:** SerpApi (Google Search API)
- **Template Engine:** Jinja2 (Factur-X Branching Logic)
- **eSignature:** Foxit eSign API

---

## Sponsor Challenge Alignment

| Sponsor | Challenge Requirement | How ComplyGraph Solves It |
| :--- | :--- | :--- |
| **Nutrient** | Intelligent Document Processing | Extracts messy PDFs into structured JSON with granular confidence scores. |
| **SerpApi** | Live Data Enrichment | Validates low-confidence VAT IDs against live EU web registries. |
| **Foxit** | Secure Agent Handoff | Agent prepares the envelope via API but **halts before signing**, preserving human legal agency. |
| **Supabase** | State Management | Tracks the job lifecycle from `pending` → `extracted` → `under_review` → `ready_to_sign`. |

---

## ⚡ Quick Start Guide

### 1. Prerequisites
- Python 3.10+ and `uv` (or `pip`)
- Node.js 18+ and `npm`
- A Supabase project
- API Keys for Nutrient, SerpApi, and Foxit

### 2. Backend Setup (FastAPI)
```bash
# Clone the repository
git clone https://github.com/your-username/comply-graph.git
cd comply-graph

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install fastapi uvicorn httpx python-dotenv jinja2 supabase python-multipart

# Configure environment variables
cp .env.example .env
# Edit .env and add your API keys (DWS_EXTRACTION_API_KEY, SERPAPI_API_KEY, SUPABASE_URL, SUPABASE_KEY, FOXIT_CLIENT_ID, FOXIT_CLIENT_SECRET)

# Run the backend server
uvicorn main:app --reload --port 8000
```

### 3. Frontend Setup (Next.js)
```bash
cd comply-graph-ui

# Install dependencies
npm install

# Run the development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) to see the dashboard.

---

##  API Documentation

The backend exposes 4 core endpoints at `http://localhost:8000`:

### 1. Ingest & Extract
```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/ingest-and-extract' \
  -F 'file=@sample-docs/messy_supplier_invoice.pdf'
```
*Returns extracted JSON, confidence scores, and a `job_id`.*

### 2. Validate VAT (HITL)
```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/validate-vat' \
  -H 'Content-Type: application/json' \
  -d '{"vat_id": "", "supplier_name": "CONTOSO LTD.", "country_code": "US"}'
```
*Returns live search results from SerpApi.*

### 3. Generate Compliant Document
```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/generate-compliant-document' \
  -H 'Content-Type: application/json' \
  -d '{"extracted_data": {...}, "jurisdiction": "FR", "approved_by_human": true}'
```
*Returns a Factur-X compliant XML payload.*

### 4. Foxit Secure Handoff
```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/foxit-prepare-and-handoff' \
  -H 'Content-Type: application/json' \
  -d '{"job_id": 1, "document_id": "doc_1", "compliant_xml_payload": "...", "signer_email": "user@test.com", "human_approved_for_signing": true}'
```
*Creates the Foxit envelope and returns the signing URL. **The agent halts here.***

---

## Demo Video

[![Watch the Demo Video](https://via.placeholder.com/600x300.png?text=Click+to+Watch+Demo)](https://www.youtube.com/watch?v=YOUR_VIDEO_ID)
*(Replace with your actual Loom/YouTube link)*

---

##  License
MIT License. Built for the 2026 API & Cloud AI Hackathon.
