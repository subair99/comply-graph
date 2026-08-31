# 🚀 ComplyGraph
### Autonomous Cross-Border Compliance & E-Invoicing Agent

[![DevNetwork Hackathon 2026](https://img.shields.io/badge/DevNetwork%20Hackathon-2026-blue)](https://api-cloud-ai-hackathon-2026.devpost.com/)
[![Overall Winner Track](https://img.shields.io/badge/Track-Overall%20Winner-orange)]()
[![Sponsor Tracks](https://img.shields.io/badge/Sponsors-Nutrient%20%7C%20Foxit%20%7C%20SerpApi%20%7C%20Doctavian%20%7C%20Xano-green)]()

**ComplyGraph AI** transforms messy, unstructured cross-border trade documents into legally compliant, audit-ready e-invoices (e.g., France’s Sept 2026 Factur-X mandate). It combines real-time web validation, human-in-the-loop (HITL) review, and a secure, agent-orchestrated e-signature handoff to eliminate manual bottlenecks and prevent costly regulatory fines.

---

## 🎯 The Problem (Concept)
Starting **September 1, 2026**, France’s B2B e-invoicing mandate requires all businesses to issue and receive compliant e-invoices (Factur-X/ZUGFeRD). Simultaneously, cross-border trade faces intense scrutiny under GDPR and EU AI Act rules. 

SMEs currently rely on manual audits of messy PDF invoices, packing lists, and contracts. This creates severe operational latency, high error rates, and exposure to multi-million dollar regulatory fines. Existing tools are either dumb templates or overly complex, expensive enterprise ERPs.

## 💡 The Solution (Progress)
ComplyGraph AI is a fully functional, end-to-end agentic pipeline that meaningfully integrates 5 sponsor technologies to automate this exact workflow:

1. **Ingestion & Extraction:** User uploads a messy document bundle (PDF invoice + bill of lading).
2. **Deterministic Extraction (Nutrient DWS):** Parses documents into structured JSON with confidence scores and coordinate grounding.
3. **Live Regulatory Validation (SerpApi):** An AI agent cross-references extracted Supplier VAT IDs against live web registries to auto-fill or flag suspicious data.
4. **Human-in-the-Loop (Nutrient Viewer + Doctavian):** Low-confidence fields are paused for human review. Once approved, Doctavian’s branching logic templates generate the precise, jurisdiction-compliant document structure.
5. **Reversible Prep (Foxit MCP):** The agent uses Foxit’s 40+ MCP tools to merge cover letters, OCR scanned pages, and attach the Factur-X XML payload.
6. **The Secure Handoff (Foxit eSign):** The agent *stops*. Upon human approval, the agent makes the direct API call to Foxit eSign, but the *human* executes the actual signature.

### 🏗️ System Architecture
```text
┌──────────────┐       ┌──────────────────────────────────────┐       ┌──────────────────────┐
│  User / UI   │ <---- │      Xano (Backend & State Machine)  │ ----> |   Audit Log / DB     │
│  (React/TS)  │       │  - API Routing - Auth - Orchestration│       └──────────────────────┘
└──────────────┘       └──────────────────────────────────────┘
                                          │
                ┌─────────────────────────┼─────────────────────────┐
                ▼                         ▼                         ▼
        ┌───────────────┐       ┌───────────────────┐       ┌───────────────┐
        │ Nutrient DWS  │       │     SerpApi       │       │   Doctavian   │
        │ (Extract/HITL)│       │ (Live Web Verify) │       │ (Complex Gen) │
        └───────────────┘       └───────────────────┘       └───────────────┘
                                          │
                                          ▼
                               ┌─────────────────────┐
                               │   Foxit MCP Server  │
                               │ (Merge/OCR/Compress)│
                               └─────────────────────┘
                                         │
                                         ▼ (Human Authorized)
                               ┌─────────────────────┐
                               │    Foxit eSign API  │
                               │   (Secure Handoff)  │
                               └─────────────────────┘
```

---

## 🛡️ The "Handoff Defense" (Foxit Challenge Design)
*Why doesn't the agent just sign the document itself?*

In regulated document workflows, **non-repudiation and legal liability** are paramount. While our agent can autonomously generate, format, and prepare the document via the Foxit MCP server, the act of signing is intentionally designed as a **human-in-the-loop boundary**. 

The agent triggers the Foxit eSign API *only after* explicit user authorization in the UI. This ensures the human retains legal agency over the final commitment, perfectly satisfying Foxit's requirement that the agent handles the upstream reversible work, while the human handles the irreversible commitment.

---

## 🏆 Sponsor Alignment & Integration Depth

| Sponsor | Challenge Track | How We Used It Meaningfully |
| :--- | :--- | :--- |
| **Nutrient** | Turn Documents Into Trust | Used DWS Data Extraction for confidence-scored parsing, embedded the DWS Viewer for the HITL review loop, and generated a deterministic audit trail. |
| **Foxit** | Your Agent Shouldn't Sign That | Used the MCP server for reversible PDF prep (merge/OCR/compress). Designed the explicit "Stop & Handoff" UI for the eSign API. |
| **SerpApi** | Best AI Use Case | Used live web search to cross-reference extracted VAT IDs against official EU registries, surfacing deltas for the user to approve. |
| **Doctavian**| Generate It Right | Used branching logic templates to handle complex EU vs. Non-EU tax rules, turning messy JSON into a compliant Factur-X structure. |
| **Xano** | Rebuild a SaaS Tool You Hate | Xano is the central nervous system. It powers the state machine, API routing, database, and hosts the frontend via static hosting. |

---

## 💰 Business Model & Feasibility (Startup Potential)
ComplyGraph AI is positioned as **"Compliance-as-a-Service"** for EU/Global SMEs. 
*   **Target Market:** 23 million SMEs in the EU impacted by the 2026 e-invoicing mandates.
*   **Pricing:** $49/month base subscription (includes 50 documents) + $2 per additional document.
*   **Scalability:** Built on serverless infrastructure (Xano) and stateless API orchestration, allowing infinite horizontal scaling without backend refactoring.

---

## 🛠️ Tech Stack
*   **Frontend:** React, TypeScript, TailwindCSS (Hosted on Xano Static Hosting)
*   **Backend & Orchestration:** Xano (No-code/Pro-code hybrid backend, State Machine, Database)
*   **Document Intelligence:** Nutrient DWS API, Nutrient Web Viewer
*   **Live Data:** SerpApi (Google Search API)
*   **Document Generation:** Doctavian API
*   **PDF Manipulation:** Foxit PDF Services via MCP Server
*   **E-Signature:** Foxit eSign API

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
*   Node.js v18+
*   A Xano account (Essential Plan)
*   API Keys for Nutrient, SerpApi, Doctavian, and Foxit.

### 2. Backend Setup (Xano)
1. Create a new Workspace in Xano.
2. Import the database schema from `/xano-schema-export.json` (Creates `Jobs`, `Documents`, and `AuditLog` tables).
3. Create the API Endpoints for `Upload`, `Extract`, `Validate`, and `Trigger_eSign`.
4. Add your API keys to the Xano Environment Variables.
5. Deploy the Xano API and copy the base URL.

### 3. Frontend Setup
```bash
# Clone the repository
git clone https://github.com/subair99/comply-graph.git
cd comply-graph/frontend

# Install dependencies
uv sync

## Start your FastAPI server with hot-reloading:
uv run uvicorn main:app --reload

# Create .env.local file
cp .env.example .env

# Run the development server
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## 📂 Seed Data
To test the pipeline exactly as shown in the demo video, use the messy documents provided in the `/sample-docs` directory:
*   `messy_supplier_invoice.pdf` (Contains a slightly blurry VAT ID to trigger SerpApi validation)
*   `bill_of_lading_scan.jpg` (Requires OCR via Foxit MCP)
*   `approved_factur_x_template.json` (Expected output from Doctavian)

---

## 🎥 Demo Video
Watch our 2.5-minute end-to-end walkthrough here: **[Link to YouTube/Loom Video]**

---

*Built for the DevNetwork [API + Cloud + AI] Hackathon 2026.*
```
