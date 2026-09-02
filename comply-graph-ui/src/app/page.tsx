"use client";

import { useState } from "react";
import { 
  Upload, FileText, ShieldCheck, AlertTriangle, CheckCircle, 
  ExternalLink, Loader2, Search, Database, Lock, FileCheck,
  ChevronRight, Sparkles, TrendingUp
} from "lucide-react";

const API_BASE = "http://127.0.0.1:8000";

export default function ComplyGraphDashboard() {
  const [step, setStep] = useState<"upload" | "review" | "processing" | "complete">("upload");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [jobId, setJobId] = useState<number | null>(null);
  const [extractedData, setExtractedData] = useState<any>(null);
  const [lowConfidenceFields, setLowConfidenceFields] = useState<string[]>([]);
  const [validationResult, setValidationResult] = useState<any>(null);
  const [signingUrl, setSigningUrl] = useState("");

  const handleUpload = async () => {
    if (!file) return;
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch(`${API_BASE}/api/v1/ingest-and-extract`, { 
        method: "POST", 
        body: formData 
      });
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
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 p-8 font-sans">
      <div className="mx-auto max-w-5xl space-y-8">
        {/* Header with Gradient */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-600 via-purple-600 to-indigo-600 p-8 shadow-2xl">
          <div className="absolute inset-0 bg-black opacity-10"></div>
          <div className="relative flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-xl bg-white/20 backdrop-blur-sm">
              <ShieldCheck className="h-10 w-10 text-white" />
            </div>
            <div>
              <h1 className="text-4xl font-bold tracking-tight text-white">
                ComplyGraph AI
              </h1>
              <p className="mt-1 text-indigo-100">
                Autonomous Cross-Border Compliance & E-Invoicing Agent
              </p>
            </div>
          </div>
        </div>

        {/* Progress Steps */}
        <div className="flex items-center justify-center gap-4">
          {["upload", "review", "processing", "complete"].map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`flex h-10 w-10 items-center justify-center rounded-full border-2 font-semibold transition-all ${
                step === s 
                  ? "border-indigo-500 bg-indigo-500 text-white shadow-lg shadow-indigo-500/50" 
                  : ["upload", "review", "processing", "complete"].indexOf(step) > i
                  ? "border-green-500 bg-green-500 text-white"
                  : "border-slate-600 bg-slate-800 text-slate-400"
              }`}>
                {["upload", "review", "processing", "complete"].indexOf(step) > i ? (
                  <CheckCircle className="h-5 w-5" />
                ) : (
                  i + 1
                )}
              </div>
              {i < 3 && (
                <ChevronRight className={`h-6 w-6 ${
                  ["upload", "review", "processing", "complete"].indexOf(step) > i
                    ? "text-green-500"
                    : "text-slate-600"
                }`} />
              )}
            </div>
          ))}
        </div>

        {/* Step 1: Upload */}
        {step === "upload" && (
          <div className="rounded-2xl border border-slate-700 bg-slate-800/50 p-8 backdrop-blur-sm shadow-xl">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-indigo-500/20">
                <FileText className="h-6 w-6 text-indigo-400" />
              </div>
              <div>
                <h2 className="text-2xl font-semibold text-white">Step 1: Ingest Document</h2>
                <p className="text-slate-400">Upload your invoice PDF for AI-powered extraction</p>
              </div>
            </div>
            
            <div className="space-y-6">
              <div className="rounded-xl border-2 border-dashed border-slate-600 bg-slate-900/50 p-8 text-center transition hover:border-indigo-500">
                <input 
                  type="file" 
                  accept=".pdf" 
                  onChange={(e) => setFile(e.target.files?.[0] || null)} 
                  className="hidden"
                  id="file-upload"
                />
                <label htmlFor="file-upload" className="cursor-pointer">
                  <Upload className="mx-auto h-12 w-12 text-slate-500" />
                  <p className="mt-4 text-lg font-medium text-slate-300">
                    {file ? file.name : "Drop your PDF here or click to browse"}
                  </p>
                  <p className="mt-2 text-sm text-slate-500">Supports PDF files up to 10MB</p>
                </label>
              </div>
              
              <button 
                onClick={handleUpload} 
                disabled={!file || loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-4 font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:scale-[1.02] hover:shadow-xl hover:shadow-indigo-500/40 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Extracting Data with Nutrient DWS...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-5 w-5" />
                    Process Document
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 2: Human-in-the-Loop Review */}
        {step === "review" && extractedData && (
          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-700 bg-slate-800/50 p-8 backdrop-blur-sm shadow-xl">
              <div className="mb-6 flex items-center gap-3">
                <div className="flex h-12 w-12 items-center justify-center rounded-lg bg-amber-500/20">
                  <AlertTriangle className="h-6 w-6 text-amber-400" />
                </div>
                <div>
                  <h2 className="text-2xl font-semibold text-white">Step 2: Human-in-the-Loop Review</h2>
                  <p className="text-slate-400">Review extracted data and validate low-confidence fields</p>
                </div>
              </div>

              <div className="mb-6 grid grid-cols-1 gap-4 md:grid-cols-2">
                {Object.entries(extractedData).map(([key, value]) => {
                  const isLowConfidence = lowConfidenceFields.includes(key);
                  return (
                    <div 
                      key={key} 
                      className={`relative overflow-hidden rounded-xl border-2 p-4 transition ${
                        isLowConfidence 
                          ? "border-red-500/50 bg-red-950/30" 
                          : "border-green-500/30 bg-green-950/20"
                      }`}
                    >
                      <div className="flex items-start justify-between">
                        <div>
                          <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                            {key.replace("_", " ")}
                          </p>
                          <p className={`mt-1 text-xl font-bold ${
                            isLowConfidence ? "text-red-400" : "text-green-400"
                          }`}>
                            {value || "Not Found"}
                          </p>
                        </div>
                        {isLowConfidence && (
                          <AlertTriangle className="h-5 w-5 text-red-500" />
                        )}
                      </div>
                      {isLowConfidence && (
                        <div className="mt-2 flex items-center gap-2 rounded-lg bg-red-900/40 px-3 py-2">
                          <TrendingUp className="h-4 w-4 text-red-400" />
                          <span className="text-xs text-red-300">Low confidence score - requires validation</span>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              {!validationResult && lowConfidenceFields.includes("vat_id") && (
                <button 
                  onClick={handleValidateVAT} 
                  disabled={loading}
                  className="mb-6 flex w-full items-center justify-center gap-2 rounded-xl border-2 border-indigo-500 bg-transparent px-6 py-4 font-semibold text-indigo-400 transition hover:bg-indigo-500/10 disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="h-5 w-5 animate-spin" />
                      Searching Live Registries...
                    </>
                  ) : (
                    <>
                      <Search className="h-5 w-5" />
                      Run Live SerpApi VAT Validation
                    </>
                  )}
                </button>
              )}

              {validationResult && (
                <div className="mb-6 rounded-xl border border-amber-500/50 bg-amber-950/30 p-6">
                  <div className="mb-4 flex items-center gap-2">
                    <Database className="h-5 w-5 text-amber-400" />
                    <h3 className="text-lg font-semibold text-amber-400">Live Registry Search Results</h3>
                  </div>
                  <ul className="space-y-4">
                    {validationResult.top_results.map((res: any, idx: number) => (
                      <li key={idx} className="rounded-lg bg-slate-900/50 p-4">
                        <a 
                          href={res.link} 
                          target="_blank" 
                          rel="noreferrer" 
                          className="group flex items-start gap-2"
                        >
                          <FileCheck className="mt-1 h-4 w-4 text-indigo-400 opacity-0 transition group-hover:opacity-100" />
                          <div>
                            <p className="font-medium text-indigo-400 hover:underline">
                              {res.title}
                              {res.is_official_registry && (
                                <span className="ml-2 rounded-full bg-green-500/20 px-2 py-0.5 text-xs text-green-400">
                                  Official
                                </span>
                              )}
                            </p>
                            <p className="mt-1 text-sm text-slate-400">{res.snippet}</p>
                          </div>
                        </a>
                      </li>
                    ))}
                  </ul>
                  <div className="mt-4 rounded-lg bg-amber-900/40 p-3">
                    <p className="text-sm font-medium text-amber-300">
                      <span className="font-bold">Recommendation:</span> {validationResult.recommended_action}
                    </p>
                  </div>
                </div>
              )}

              <button 
                onClick={handleApproveAndHandoff} 
                disabled={loading}
                className="flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 px-6 py-4 font-semibold text-white shadow-lg shadow-green-500/30 transition hover:scale-[1.02] hover:shadow-xl hover:shadow-green-500/40 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Processing...
                  </>
                ) : (
                  <>
                    <CheckCircle className="h-5 w-5" />
                    Approve Data & Generate Compliant Document
                  </>
                )}
              </button>
            </div>
          </div>
        )}

        {/* Step 3: Processing */}
        {step === "processing" && (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-slate-700 bg-slate-800/50 p-16 backdrop-blur-sm shadow-xl">
            <div className="relative mb-8">
              <div className="absolute inset-0 animate-ping rounded-full bg-indigo-500/30"></div>
              <Loader2 className="relative h-20 w-20 animate-spin text-indigo-500" />
            </div>
            <h2 className="mb-3 text-3xl font-bold text-white">Agent is Working...</h2>
            <p className="max-w-md text-center text-slate-400">
              Generating Factur-X XML with jurisdiction branching logic, 
              embedding via Foxit MCP, and preparing the secure handoff envelope.
            </p>
            <div className="mt-8 flex gap-4">
              <div className="flex items-center gap-2 rounded-lg bg-slate-900/50 px-4 py-2">
                <Database className="h-5 w-5 text-purple-400" />
                <span className="text-sm text-slate-300">Jinja2 Template Engine</span>
              </div>
              <div className="flex items-center gap-2 rounded-lg bg-slate-900/50 px-4 py-2">
                <Lock className="h-5 w-5 text-green-400" />
                <span className="text-sm text-slate-300">Foxit eSign API</span>
              </div>
            </div>
          </div>
        )}

        {/* Step 4: Secure Handoff Complete */}
        {step === "complete" && signingUrl && (
          <div className="rounded-2xl border-2 border-green-500/50 bg-gradient-to-br from-green-950/50 to-emerald-950/50 p-10 shadow-2xl">
            <div className="mb-6 flex items-center justify-center">
              <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-500/20 shadow-lg shadow-green-500/30">
                <CheckCircle className="h-12 w-12 text-green-400" />
              </div>
            </div>
            
            <div className="text-center">
              <h2 className="mb-3 text-3xl font-bold text-white">Secure Handoff Complete</h2>
              <p className="mx-auto mb-6 max-w-2xl text-lg text-slate-300">
                The AI agent has successfully prepared the compliant document and created the eSign envelope. 
                <span className="mx-1 rounded bg-red-500/20 px-2 py-1 font-bold text-red-400">
                  The agent has intentionally HALTED.
                </span>
              </p>
              
              <div className="mb-8 rounded-xl bg-slate-900/50 p-6">
                <div className="flex items-center justify-center gap-2 text-slate-400">
                  <Lock className="h-5 w-5 text-amber-400" />
                  <p className="text-sm">
                    To maintain <span className="font-semibold text-amber-400">non-repudiation</span> and legal liability, 
                    the human must execute the final signature.
                  </p>
                </div>
              </div>

              <a 
                href={signingUrl} 
                target="_blank" 
                rel="noreferrer"
                className="inline-flex items-center gap-3 rounded-xl bg-gradient-to-r from-green-600 to-emerald-600 px-8 py-5 font-bold text-white shadow-xl shadow-green-500/30 transition hover:scale-105 hover:shadow-2xl hover:shadow-green-500/40"
              >
                Execute Legally Binding Signature 
                <ExternalLink className="h-5 w-5" />
              </a>

              <div className="mt-8 flex items-center justify-center gap-4 text-sm text-slate-500">
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span>Envelope Created</span>
                </div>
                <div className="flex items-center gap-2">
                  <CheckCircle className="h-4 w-4 text-green-500" />
                  <span>Compliant XML Attached</span>
                </div>
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4 text-amber-500" />
                  <span>Agent Halted</span>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="rounded-xl border border-slate-700 bg-slate-800/30 p-6 text-center text-sm text-slate-500">
          <p>Powered by Nutrient DWS • SerpApi • Jinja2 • Foxit eSign • Supabase • FastAPI</p>
        </div>
      </div>
    </div>
  );
}