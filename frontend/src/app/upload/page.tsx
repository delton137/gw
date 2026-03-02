"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter } from "next/navigation";
import { apiUpload, apiFetch } from "@/lib/api";

const ANCESTRY_OPTIONS = [
  { value: "EUR", label: "European" },
  { value: "AFR", label: "African" },
  { value: "EAS", label: "East Asian" },
  { value: "SAS", label: "South Asian" },
  { value: "AMR", label: "Americas / Latino" },
];

interface Analysis {
  id: string;
  status: string;
  error_message?: string;
  status_detail?: string;
}

export default function UploadPage() {
  const { getToken } = useAuth();
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [ancestry, setAncestry] = useState("EUR");
  const [status, setStatus] = useState<"idle" | "uploading" | "processing" | "error">("idle");
  const [analysisStage, setAnalysisStage] = useState("");
  const [statusDetail, setStatusDetail] = useState("");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) setFile(dropped);
  }, []);

  const handleUpload = async () => {
    if (!file) return;
    setStatus("uploading");
    setUploadProgress(0);
    setError("");

    try {
      const token = await getToken();
      const formData = new FormData();
      formData.append("file", file);
      formData.append("ancestry_group", ancestry);

      const analysis = await apiUpload<Analysis>(
        "/api/v1/upload/",
        formData,
        token,
        (pct) => setUploadProgress(pct)
      );

      setStatus("processing");

      // Poll for completion (fetch fresh token each time — Clerk tokens are short-lived)
      const poll = async (currentId: string) => {
        const freshToken = await getToken();
        try {
          const result = await apiFetch<Analysis>(
            `/api/v1/results/analysis/${currentId}`,
            {},
            freshToken
          );

          if (result.status === "done" || result.status === "scoring_prs" || result.status === "complete") {
            router.push("/dashboard");
          } else if (result.status === "failed") {
            setStatus("error");
            setError(result.error_message || "Analysis failed");
          } else {
            setAnalysisStage(result.status);
            if (result.status_detail) setStatusDetail(result.status_detail);
            setTimeout(() => poll(currentId), 2000);
          }
        } catch {
          setTimeout(() => poll(currentId), 5000);
        }
      };

      setTimeout(() => poll(analysis.id), 2000);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : "Upload failed");
    }
  };

  return (
    <div className="mx-auto max-w-2xl px-6 pt-8 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-2">Upload your genotype file</h1>
      <p className="text-muted mb-10">
        We support 23andMe, AncestryDNA, CGI .tsv, .vcf, and .vcf.gz formats. Your raw data is processed in
        memory and never stored.
      </p>

      {/* Drop zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed p-12 text-center mb-6 transition-colors ${dragOver ? "border-accent bg-blue-50/50" : "border-border"
          }`}
      >
        {file ? (
          <div>
            <p className="text-sm font-medium">{file.name}</p>
            <p className="text-xs text-muted mt-1">
              {(file.size / 1024 / 1024).toFixed(1)} MB
            </p>
            <button
              onClick={() => setFile(null)}
              className="text-xs text-accent mt-2 hover:underline"
            >
              Remove
            </button>
          </div>
        ) : (
          <div>
            <p className="text-sm text-muted mb-2">
              Drag and drop your genotype file here, or
            </p>
            <label className="text-sm text-accent hover:underline cursor-pointer">
              browse files
              <input
                type="file"
                className="hidden"
                accept=".txt,.csv,.tsv,.vcf,.vcf.gz,.gz,text/plain,text/csv,text/tab-separated-values"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
              />
            </label>
          </div>
        )}
      </div>

      {/* Ancestry selection */}
      <div className="mb-8">
        <label className="block text-sm font-medium mb-1.5">Ancestry Group</label>
        <p className="text-xs text-muted mb-2">
          Select the ancestry group that best represents your background. This is used to calibrate
          polygenic risk scores against the most relevant reference population.
        </p>
        <select
          value={ancestry}
          onChange={(e) => setAncestry(e.target.value)}
          disabled={status === "uploading" || status === "processing"}
          className="border border-border bg-white px-3 py-2 text-sm w-full max-w-xs disabled:opacity-50"
        >
          {ANCESTRY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.value} &mdash; {opt.label}
            </option>
          ))}
        </select>
      </div>

      {/* Upload button */}
      <button
        onClick={handleUpload}
        disabled={!file || status === "uploading" || status === "processing"}
        className="bg-accent text-white px-6 py-2.5 text-sm font-medium hover:bg-accent-hover transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {status === "uploading"
          ? "Uploading..."
          : status === "processing"
            ? "Analyzing..."
            : "Upload and analyze"}
      </button>

      {/* Progress bar */}
      {status === "uploading" && (
        <div className="mt-4">
          <div className="flex justify-between text-xs text-muted mb-1">
            <span>Uploading file...</span>
            <span>{uploadProgress}%</span>
          </div>
          <div className="w-full bg-gray-200 h-2 overflow-hidden">
            <div
              className="bg-accent h-full transition-all duration-300"
              style={{ width: `${uploadProgress}%` }}
            />
          </div>
        </div>
      )}

      {status === "processing" && (
        <div className="mt-4">
          <div className="flex items-center gap-2 text-sm text-muted">
            <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            {({
              pending: "Queued...",
              parsing: "Parsing genotype file...",
              matching_snpedia: "Matching SNPedia variants...",
              matching_fast: "Analyzing traits, pharmacogenes, blood type, carrier status...",
              matching_traits: "Analyzing trait associations...",
              matching_clinvar: "Cross-referencing ClinVar...",
              matching_pgx: "Calling pharmacogenes...",
              matching_blood: "Determining blood type...",
              matching_carrier: "Screening carrier status...",
              scoring_prs: "Computing polygenic risk scores...",
            } as Record<string, string>)[analysisStage] || "Processing..."}
          </div>
          {statusDetail && (
            <p className="text-xs text-muted mt-1.5 ml-6">{statusDetail}</p>
          )}
        </div>
      )}

      {status === "error" && (
        <p className="text-sm text-risk-high mt-4">{error}</p>
      )}
    </div>
  );
}
