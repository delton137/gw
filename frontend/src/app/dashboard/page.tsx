"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch, apiDelete } from "@/lib/api";
import { SUPERPOP_COLORS, SUPERPOP_NAMES } from "@/lib/populations";
import { useReportDownload } from "@/hooks/useReportDownload";
import type {
  Analysis,
  AncestryDetail,
  CarrierStatusResult,
  ClinvarResponse,
  GwasResponse,
  PgxResult,
  PrsResponse,
  TraitHit,
  VariantsResponse,
} from "@/lib/types";

export default function DashboardPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [traitHits, setTraitHits] = useState<TraitHit[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [variantsTotal, setVariantsTotal] = useState(0);
  const [snpediaTotal, setSnpediaTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [pgxResults, setPgxResults] = useState<PgxResult[]>([]);
  const [carrierStatus, setCarrierStatus] = useState<CarrierStatusResult | null>(null);
  const [clinvarTotal, setClinvarTotal] = useState(0);
  const [prsStatus, setPrsStatus] = useState<"computing" | "failed" | "ready" | null>(null);
  const [prsCount, setPrsCount] = useState(0);
  const [prsError, setPrsError] = useState<string | null>(null);
  const [prsDetail, setPrsDetail] = useState<string | null>(null);
  const [gwasStatus, setGwasStatus] = useState<"computing" | "failed" | "ready" | null>(null);
  const [gwasCount, setGwasCount] = useState(0);
  const [gwasElevated, setGwasElevated] = useState(0);
  const { download: downloadReport, loading: downloading } = useReportDownload("/api/v1/report/download", "genewizard-report");
  const { download: downloadPgxReport, loading: downloadingPgx } = useReportDownload("/api/v1/report/pgx/download", "genewizard-pgx-report");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pollPrs = useCallback(async () => {
    if (!user?.id) return;
    try {
      const token = await getToken();
      const data = await apiFetch<PrsResponse>(
        `/api/v1/results/prs/${user.id}`,
        {},
        token
      );
      setPrsStatus(data.prs_status);
      setPrsCount(data.results.length);
      setPrsDetail(data.prs_status_detail);
      if (data.prs_status === "computing") {
        pollRef.current = setTimeout(pollPrs, 5000);
      }
    } catch {
      // PRS endpoint not available yet
    }
  }, [getToken, user]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearTimeout(pollRef.current);
    };
  }, []);

  useEffect(() => {
    async function load() {
      try {
        const token = await getToken();
        const userId = user?.id;
        if (!userId) return;

        const [prsData, traitsData, pgxData, csData, cvData, gwasData] = await Promise.all([
          apiFetch<PrsResponse>(`/api/v1/results/prs/${userId}`, {}, token).catch(() => null),
          apiFetch<{ hits: TraitHit[] }>(`/api/v1/results/traits/${userId}`, {}, token).catch(() => null),
          apiFetch<{ results: PgxResult[] }>(`/api/v1/results/pgx/${userId}`, {}, token).catch(() => null),
          apiFetch<{ result: CarrierStatusResult | null }>(`/api/v1/results/carrier-status/${userId}`, {}, token).catch(() => null),
          apiFetch<ClinvarResponse>(`/api/v1/results/clinvar/${userId}?limit=1`, {}, token).catch(() => null),
          apiFetch<GwasResponse>(`/api/v1/results/gwas/${userId}`, {}, token).catch(() => null),
        ]);

        setFetchError(null);
        if (prsData) {
          setPrsStatus(prsData.prs_status);
          setPrsCount(prsData.results.length);
        }
        if (traitsData) setTraitHits(traitsData.hits);
        if (pgxData) setPgxResults(pgxData.results);
        if (csData?.result) setCarrierStatus(csData.result);
        if (cvData) {
          setClinvarTotal(cvData.total);
        }
        if (gwasData) {
          setGwasStatus(gwasData.gwas_status);
          setGwasCount(gwasData.total_scores);
          const allScores = Object.values(gwasData.categories).flat();
          setGwasElevated(allScores.filter((s) => s.percentile !== null && s.percentile >= 80).length);
        }
        // Start polling if PRS still computing
        if (prsData?.prs_status === "computing") {
          pollRef.current = setTimeout(pollPrs, 5000);
        }

        // Fetch analysis metadata and initial variants in parallel
        if (prsData?.analysis_id) {
          try {
            const [analysisData, variantsData] = await Promise.all([
              apiFetch<Analysis>(
                `/api/v1/results/analysis/${prsData!.analysis_id}`,
                {},
                token
              ),
              apiFetch<VariantsResponse>(
                `/api/v1/results/variants/${userId}?limit=1`,
                {},
                token
              ).catch(() => null),
            ]);
            setAnalysis(analysisData);
            if (analysisData.status === "done" && analysisData.error_message) {
              setPrsError(analysisData.error_message);
            }
            if (variantsData) {
              setVariantsTotal(variantsData.total);
              setSnpediaTotal(variantsData.snpedia_total);
            }
          } catch {
            // Analysis metadata unavailable — non-critical
          }
        }
      } catch {
        setFetchError("Unable to connect to the server. Please check your connection and try again.");
      } finally {
        setLoading(false);
      }
    }
    if (user) load();
  }, [getToken, user, pollPrs]);

  const handleDeleteData = async () => {
    setDeleting(true);
    try {
      const token = await getToken();
      await apiDelete("/api/v1/account/data", token);
      window.location.href = "/upload";
    } catch {
      alert("Failed to delete data. Please try again.");
      setDeleting(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  const hasResults = traitHits.length > 0 || pgxResults.length > 0 || prsStatus !== null;
  const pgxActionableCount = pgxResults.filter((r) => {
    if (!r.phenotype) return false;
    const p = r.phenotype.toLowerCase();
    return p.includes("poor metabolizer") || p.includes("ultra-rapid") || p.includes("ultrarapid") || p.includes("positive") || p.includes("high warfarin sensitivity");
  }).length;

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-8">My Genome Dashboard</h1>

      {fetchError && !hasResults ? (
        <div className="border border-red-300 bg-red-50 p-12 text-center">
          <p className="text-red-700 mb-4">{fetchError}</p>
          <button
            onClick={() => window.location.reload()}
            className="text-accent hover:underline text-sm"
          >
            Retry
          </button>
        </div>
      ) : !hasResults ? (
        <div className="border border-border p-12 text-center">
          <p className="text-muted mb-4">No analysis results yet.</p>
          <Link href="/upload" className="text-accent hover:underline text-sm">
            Upload your genotype file to get started
          </Link>
        </div>
      ) : (
        <>
          {/* File summary */}
          <div className="border border-border p-5 mb-12 flex flex-wrap items-baseline gap-x-8 gap-y-2">
            {analysis?.filename && (
              <div>
                <p className="text-xs text-muted mb-0.5">Filename</p>
                <p className="text-sm font-medium truncate max-w-xs" title={analysis.filename}>{analysis.filename}</p>
              </div>
            )}
            <div>
              <p className="text-xs text-muted mb-0.5">File Type</p>
              <p className="text-sm font-medium">{analysis?.chip_type || "\u2014"}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-0.5">Variants Read From File</p>
              <p className="text-sm font-medium">{analysis?.variant_count?.toLocaleString() || "\u2014"}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-0.5">Genome Build</p>
              <p className="text-sm font-medium">{analysis?.genome_build || "\u2014"}</p>
            </div>
            {analysis?.pipeline_fast_seconds != null && (
              <div>
                <p className="text-xs text-muted mb-0.5">Pipeline Runtime</p>
                <p className="text-sm font-medium">{analysis.pipeline_fast_seconds.toFixed(1)}s</p>
              </div>
            )}
          </div>

          {/* Card grid */}
          <div className="grid grid-cols-1 gap-6 mb-12">
            {/* SNP Summary */}
            {(traitHits.length > 0 || variantsTotal > 0) && (
              <div className="border border-border p-5">
                <h2 className="font-serif text-xl font-semibold mb-2">Curated SNPs</h2>
                {traitHits.length > 0 && (
                  <p className="text-sm text-muted mb-2">
                    <span className="font-semibold text-foreground">{traitHits.length}</span> trait associations found
                  </p>
                )}
                {variantsTotal > 0 && (
                  <p className="text-sm text-muted mb-2">
                    <span className="font-semibold text-foreground">{variantsTotal.toLocaleString()}</span>{" "}
                    SNPedia variants found
                    {snpediaTotal > 0 && (
                      <> out of <span className="font-semibold text-foreground">{snpediaTotal.toLocaleString()}</span></>
                    )}
                  </p>
                )}
                <Link
                  href="/mysnps"
                  className="inline-block text-sm font-medium text-accent hover:underline mt-1"
                >
                  View all SNP results &rarr;
                </Link>
              </div>
            )}

            {/* Pharmacogenomics Summary */}
            {pgxResults.length > 0 && (
              <div className="border border-border p-5">
                <h2 className="font-serif text-xl font-semibold mb-2">
                  Pharmacogenomics
                </h2>
                <p className="text-sm text-muted mb-3">
                  <span className="font-semibold text-foreground">{pgxResults.length}</span> genes analyzed
                </p>
                <Link
                  href="/pgx"
                  className="inline-block text-sm font-medium text-accent hover:underline"
                >
                  View pharmacogenomics results &rarr;
                </Link>
              </div>
            )}

            {/* ClinVar Summary */}
            {clinvarTotal > 0 && (
              <div className="border border-border p-5">
                <h2 className="font-serif text-xl font-semibold mb-2">ClinVar Annotations</h2>
                <p className="text-sm text-muted mb-2">
                  <span className="font-semibold text-foreground">{clinvarTotal.toLocaleString()}</span> of your variants have ClinVar annotations
                </p>
                <Link
                  href="/clinvar"
                  className="inline-block text-sm font-medium text-accent hover:underline mt-1"
                >
                  View ClinVar annotations &rarr;
                </Link>
              </div>
            )}

            {/* Carrier Status Card */}
            {carrierStatus && (
              <div className="border border-border p-5">
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h2 className="font-serif text-xl font-semibold mb-1">
                      Carrier Screening
                      <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
                        Experimental
                      </span>
                    </h2>
                    <p className="text-sm text-muted">
                      {carrierStatus.n_genes_screened} genes analyzed
                      {carrierStatus.n_carrier_genes === 0 && carrierStatus.n_affected_flags === 0 && (
                        <span className="ml-2 text-gray-400">&mdash; no carrier variants detected</span>
                      )}
                    </p>
                  </div>
                  {carrierStatus.n_carrier_genes === 0 && carrierStatus.n_affected_flags === 0 ? null
                  : carrierStatus.n_affected_flags > 0 ? (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700">
                      Action recommended
                    </span>
                  ) : (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                      {carrierStatus.n_carrier_genes} carrier gene{carrierStatus.n_carrier_genes !== 1 ? "s" : ""}
                    </span>
                  )}
                </div>
                {(carrierStatus.n_carrier_genes > 0 || carrierStatus.n_affected_flags > 0) && (
                  <div className="space-y-1 mb-3">
                    {Object.values(carrierStatus.results_json)
                      .filter((g) => g.status !== "not_detected")
                      .map((g) => (
                        <div key={g.gene} className="flex items-center gap-2 text-sm">
                          <span className={`inline-block w-2 h-2 rounded-full ${
                            g.status === "carrier" ? "bg-amber-500"
                            : g.status === "likely_affected" ? "bg-red-500"
                            : "bg-red-500"
                          }`} />
                          <span className="font-mono text-xs text-foreground">{g.gene}</span>
                          <span className="text-muted">&mdash; {g.condition}</span>
                          <span className={`text-xs ${
                            g.status === "carrier" ? "text-amber-700"
                            : "text-red-700"
                          }`}>
                            ({g.status.replace(/_/g, " ")})
                          </span>
                        </div>
                      ))}
                  </div>
                )}
                <Link
                  href="/carrier"
                  className="inline-block text-sm font-medium text-accent hover:underline"
                >
                  View carrier status details &rarr;
                </Link>
              </div>
            )}

            {/* PRS Status Card */}
            <div className="border border-border p-5">
              <h2 className="font-serif text-xl font-semibold mb-2">
                Polygenic Risk Scores
                <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
                  Experimental
                </span>
              </h2>
              {prsStatus === "computing" && (
                <div>
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Computing PRS scores... This may take a few minutes.
                  </div>
                  {prsDetail && (
                    <p className="text-xs text-muted mt-1.5 ml-6">{prsDetail}</p>
                  )}
                </div>
              )}
              {prsStatus === "failed" && (
                <div className="text-sm">
                  <p className="text-risk-high mb-1">PRS computation failed.</p>
                  {prsError && <p className="text-xs text-muted">{prsError}</p>}
                </div>
              )}
              {prsStatus === "ready" && (
                <div>
                  <p className="text-sm text-muted mb-3">
                    <span className="font-semibold text-foreground">{prsCount}</span> polygenic risk score{prsCount !== 1 ? "s" : ""} computed
                  </p>
                  <Link
                    href="/prs"
                    className="inline-block text-sm font-medium text-accent hover:underline"
                  >
                    View PRS results &rarr;
                  </Link>
                </div>
              )}
            </div>

            {/* GWAS Risk Scores Card */}
            {(gwasStatus === "ready" || gwasStatus === "computing") && (
              <div className="border border-border p-5">
                <h2 className="font-serif text-xl font-semibold mb-2">
                  GWAS Risk Scores
                  <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
                    Experimental
                  </span>
                </h2>
                {gwasStatus === "computing" && (
                  <div className="flex items-center gap-2 text-sm text-muted">
                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Computing GWAS risk scores...
                  </div>
                )}
                {gwasStatus === "ready" && (
                  <div>
                    <p className="text-sm text-muted mb-3">
                      <span className="font-semibold text-foreground">{gwasCount}</span> GWAS risk score{gwasCount !== 1 ? "s" : ""} computed
                    </p>
                    <Link
                      href="/gwas"
                      className="inline-block text-sm font-medium text-accent hover:underline"
                    >
                      View GWAS risk scores &rarr;
                    </Link>
                  </div>
                )}
              </div>
            )}

            {/* Ancestry Card */}
            {analysis?.detected_ancestry && (
              <div className="border border-border p-5">
              <h2 className="font-serif text-xl font-semibold mb-2">
                Genetic Ancestry
                <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
                  Experimental
                </span>
              </h2>
              {(() => {
                const data = analysis.detected_ancestry;
                const isNew = "superpopulations" in data;
                const superPops = isNew
                  ? (data as AncestryDetail).superpopulations
                  : (data as Record<string, number>);
                const sorted = Object.entries(superPops)
                  .sort(([, a], [, b]) => b - a)
                  .filter(([, v]) => v >= 0.02);
                const superColors = SUPERPOP_COLORS;
                const superNames = SUPERPOP_NAMES;
                const nMarkers = isNew ? (data as AncestryDetail).n_markers_used : 0;
                return (
                  <>
                    <div className="space-y-1.5 mb-3">
                      {sorted.map(([code, frac]) => (
                        <div key={code} className="flex items-center gap-2 text-sm">
                          <span className={`inline-block w-2.5 h-2.5 rounded-full ${superColors[code] || "bg-gray-400"}`} />
                          <span className="font-medium w-24">{superNames[code] || code}</span>
                          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                            <div
                              className={`h-full rounded-full ${superColors[code] || "bg-gray-400"}`}
                              style={{ width: `${Math.max(frac * 100, 1)}%` }}
                            />
                          </div>
                          <span className="text-xs font-mono text-muted w-12 text-right">
                            {(frac * 100).toFixed(1)}%
                          </span>
                        </div>
                      ))}
                    </div>
                    <Link
                      href="/ancestry"
                      className="inline-block text-sm font-medium text-accent hover:underline"
                    >
                      View full ancestry breakdown &rarr;
                    </Link>
                  </>
                );
              })()}
              </div>
            )}
          </div>

          {/* Actions: Download Report & Delete Data */}
          <section className="border-t border-border pt-8 mt-8">
            <div className="flex flex-wrap gap-4 items-center">
              <button
                onClick={() => downloadReport(analysis?.filename ?? undefined)}
                disabled={downloading}
                className="px-5 py-2.5 text-sm font-medium border border-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {downloading ? "Generating PDF..." : "Download Report"}
              </button>

              {pgxResults.length > 0 && (
                <button
                  onClick={() => downloadPgxReport(analysis?.filename ?? undefined)}
                  disabled={downloadingPgx}
                  className="px-5 py-2.5 text-sm font-medium border border-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {downloadingPgx ? "Generating PDF..." : "Download PharmGen Report"}
                </button>
              )}

              <button
                onClick={() => setShowDeleteConfirm(true)}
                className="px-5 py-2.5 text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
              >
                Delete All My Data
              </button>
            </div>
            <p className="text-xs text-muted mt-3">
              Your raw genetic file was never stored. Deleting your data removes all
              analysis results, scores, and trait matches from our servers permanently.
            </p>
          </section>

          {/* Version info */}
          <p className="mt-8 text-center text-[11px] text-gray-400">GeneWizard v0.9.0 &middot; Updated {process.env.NEXT_PUBLIC_BUILD_DATE}</p>

          {/* Delete confirmation modal */}
          {showDeleteConfirm && (
            <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
              <div className="bg-white max-w-md w-full mx-4 p-6 shadow-lg">
                <h3 className="font-serif text-lg font-semibold mb-3">
                  Delete all your data?
                </h3>
                <p className="text-sm text-muted mb-2">
                  This will permanently delete:
                </p>
                <ul className="text-sm text-muted mb-4 list-disc list-inside space-y-1">
                  <li>All analysis records</li>
                  <li>All polygenic risk scores</li>
                  <li>All trait association results</li>
                  <li>Your variant list</li>
                </ul>
                <p className="text-sm font-medium mb-6">
                  This action cannot be undone.
                </p>
                <div className="flex gap-3 justify-end">
                  <button
                    onClick={() => setShowDeleteConfirm(false)}
                    disabled={deleting}
                    className="px-4 py-2 text-sm border border-border hover:bg-gray-50"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleDeleteData}
                    disabled={deleting}
                    className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 disabled:opacity-50"
                  >
                    {deleting ? "Deleting..." : "Yes, delete everything"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
