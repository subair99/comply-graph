"use client";

import { useState } from "react";
import { Upload, FileText, ShieldCheck, AlertTriangle, CheckCircle, ExternalLink, Loader2, Search } from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

export default function ComplyGraphDashboard() {
  const [step, setStep] = useState<"upload" | "review" | "processing" | "complete">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  
  const [jobId, setJobId] = useState<number | null>(null);
  const [extractedData, setExtractedData] = useState<any>(null);
  const [lowConfidenceFields, setLowConfidenceFields] = useState<string[]>([]);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [signingUrl, setSigningUrl] = useState<string>("");

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest-and-extract`, { method: "POST", body: formData });
      const data = await res.json();
      setJobId(data.job_id);
      setExtractedData(data.extracted_data);
      setLowConfidenceFields(data.low_confidence_fields || []);
      setStep("review");
    } catch (err) {
      alert("Upload failed. Check console.");
    } finally {
      setLoading(false);
    }
  };

  const handleValidateVAT = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/v1/validate-vat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          vat_id: extractedData.vat_id || "",
          supplier_name: extractedData.supplier_name,
          country_code: "US",
        }),
      });
      const data = await res.json();
      setValidationResult(data);
    } catch (err) {
      alert("Validation failed.");
    } finally {
      setLoading(false);
    }
  };

  const handleApproveAndHandoff = async () => {
    setLoading(true);
    setStep("processing");
    try {
      // Milestone 3: Generate Compliant Document
      const genRes = await fetch(`${API_BASE}/api/v1/generate-compliant-document`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          extracted_data: extractedData,
          template_id: "factur_x_en16931",
          jurisdiction: "FR",
          approved_by_human: true,
        }),
      });
      const genData = await genRes.json();

      // Milestone 4: Foxit Prepare & Handoff
      const handoffRes = await fetch(`${API_BASE}/api/v1/foxit-prepare-and-handoff`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          job_id: jobId,
          document_id: genData.document_id,
          compliant_xml_payload: genData.compliant_xml_payload,
          signer_name: "Human Reviewer",
          signer_email: "reviewer@company.com",
          human_approved_for_signing: true,
        }),
      });
      const handoffData = await handoffRes.json();
      
      setSigningUrl(handoffData.signing_url);
      setStep("complete");
    } catch (err) {
      alert("Handoff failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 p-8 font-sans text-slate-900">
      <div className="mx-auto max-w-3xl space-y-8">
        {/* Header */}
        <div className="flex items-center gap-3 border-b border-slate-200 pb-6">
          <ShieldCheck className="h-10 w-10 text-indigo-600" />
          <div>
            <h1 className="text-3xl font-bold tracking-tight text-slate-900">ComplyGraph AI</h1>
            <p className="text-slate-500">Autonomous Cross-Border Compliance & E-Invoicing Agent</p>
          </div>
        </div>

        {/* Step 1: Upload */}
        {step === "upload" && (
          <div className="rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
            <h2 className="mb-4 text-xl font-semibold flex items-center gap-2">
              <FileText className="h-5 w-5 text-indigo-600" /> Step 1: Ingest Document
            </h2>
            <div className="space-y-4">
              <input 
                type="file" 
                accept=".pdf" 
                onChange={(e) => setFile(e.target.files?.[0] || null)} 
                className="block w-full text-sm text-slate-500 file:mr-4 file:rounded-full file:border-0 file:bg-indigo-50 file:px-4 file:py-2 file:text-sm file:font-semibold file:text-indigo-700 hover:file:bg-indigo-100"
              />
              <button 
                onClick={handleUpload} 
                disabled={!file || loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-3 font-semibold text-white transition hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Upload className="h-5 w-5" />}
                {loading ? "Extracting Data..." : "Process Document"}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Human-in-the-Loop Review */}
        {step === "review" && extractedData && (
          <div className="space-y-6">
            <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="mb-4 text-xl font-semibold flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-amber-500" /> Step 2: Human-in-the-Loop Review
              </h2>
              <div className="grid grid-cols-2 gap-4 mb-6">
                {Object.entries(extractedData).map(([key, value]) => (
                  <div key={key} className={`rounded-lg border p-3 ${lowConfidenceFields.includes(key) ? 'border-red-200 bg-red-50' : 'border-slate-200 bg-slate-50'}`}>
                    <p className="text-xs font-medium uppercase text-slate-500">{key.replace('_', ' ')}</p>
                    <p className={`text-lg font-semibold ${lowConfidenceFields.includes(key) ? 'text-red-700' : 'text-slate-900'}`}>
                      {value || "Not Found"}
                    </p>
                    {lowConfidenceFields.includes(key) && (
                      <p className="mt-1 text-xs text-red-600 flex items-center gap-1">
                        <AlertTriangle className="h-3 w-3" /> Low confidence score
                      </p>
                    )}
                  </div>
                ))}
              </div>

              {!validationResult && lowConfidenceFields.includes("vat_id") && (
                <button 
                  onClick={handleValidateVAT} 
                  disabled={loading}
                  className="mb-4 flex w-full items-center justify-center gap-2 rounded-lg border border-indigo-600 bg-white px-4 py-3 font-semibold text-indigo-600 transition hover:bg-indigo-50 disabled:opacity-50"
                >
                  {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <Search className="h-5 w-5" />}
                  Run Live SerpApi VAT Validation
                </button>
              )}

              {validationResult && (
                <div className="mb-6 rounded-lg border border-amber-200 bg-amber-50 p-4">
                  <h3 className="font-semibold text-amber-800 mb-2">Live Registry Search Results:</h3>
                  <ul className="space-y-3">
                    {validationResult.top_results.map((res: any, idx: number) => (
                      <li key={idx} className="text-sm">
                        <a href={res.link} target="_blank" rel="noreferrer" className="font-medium text-indigo-600 hover:underline flex items-center gap-1">
                          {res.title} {res.is_official_registry && <CheckCircle className="h-3 w-3 text-green-600" />}
                        </a>
                        <p className="text-slate-600 mt-1">{res.snippet}</p>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 text-sm font-medium text-amber-800">Recommendation: {validationResult.recommended_action}</p>
                </div>
              )}

              <button 
                onClick={handleApproveAndHandoff} 
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-lg bg-green-600 px-4 py-3 font-semibold text-white transition hover:bg-green-700 disabled:opacity-50"
              >
                {loading ? <Loader2 className="h-5 w-5 animate-spin" /> : <CheckCircle className="h-5 w-5" />}
                Approve Data & Generate Compliant Document
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Processing */}
        {step === "processing" && (
          <div className="flex flex-col items-center justify-center rounded-xl border border-slate-200 bg-white p-12 shadow-sm text-center">
            <Loader2 className="h-12 w-12 animate-spin text-indigo-600 mb-4" />
            <h2 className="text-2xl font-bold text-slate-900">Agent is Working...</h2>
            <p className="mt-2 text-slate-500 max-w-md">
              Generating Factur-X XML with jurisdiction branching logic, embedding via Foxit MCP, and preparing the secure handoff envelope.
            </p>
          </div>
        )}

        {/* Step 4: Secure Handoff Complete */}
        {step === "complete" && signingUrl && (
          <div className="rounded-xl border-2 border-green-200 bg-green-50 p-8 shadow-sm text-center">
            <CheckCircle className="h-16 w-16 text-green-600 mx-auto mb-4" />
            <h2 className="text-2xl font-bold text-green-900">Secure Handoff Complete</h2>
            <p className="mt-2 text-green-800 max-w-lg mx-auto">
              The AI agent has successfully prepared the compliant document and created the eSign envelope. 
              <strong> The agent has intentionally HALTED.</strong>
            </p>
            <p className="mt-4 text-sm text-green-700 font-medium">
              To maintain non-repudiation and legal liability, the human must execute the final signature.
            </p>
            <a 
              href={signingUrl} 
              target="_blank" 
              rel="noreferrer"
              className="mt-6 inline-flex items-center gap-2 rounded-lg bg-green-600 px-6 py-4 font-bold text-white shadow-lg transition hover:bg-green-700 hover:shadow-xl"
            >
              Execute Legally Binding Signature <ExternalLink className="h-5 w-5" />
            </a>
          </div>
        )}
      </div>
    </div>
  );
}