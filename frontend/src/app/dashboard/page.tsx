"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch, apiDelete } from "@/lib/api";
import { useReportDownload } from "@/hooks/useReportDownload";
import DashboardContent from "@/components/DashboardContent";
import type {
  Analysis,
  CarrierStatusResult,
  ClinvarResponse,
  PgxResult,
  PrsResponse,
  TraitHit,
  TraitsResponse,
  VariantsResponse,
} from "@/lib/types";

export default function DashboardPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [traitHits, setTraitHits] = useState<TraitHit[]>([]);
  const [uniqueSnpsMatched, setUniqueSnpsMatched] = useState(0);
  const [totalSnpsInKb, setTotalSnpsInKb] = useState(0);
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

        const [prsData, traitsData, pgxData, csData, cvData] = await Promise.all([
          apiFetch<PrsResponse>(`/api/v1/results/prs/${userId}`, {}, token).catch(() => null),
          apiFetch<TraitsResponse>(`/api/v1/results/traits/${userId}`, {}, token).catch(() => null),
          apiFetch<{ results: PgxResult[] }>(`/api/v1/results/pgx/${userId}`, {}, token).catch(() => null),
          apiFetch<{ result: CarrierStatusResult | null }>(`/api/v1/results/carrier-status/${userId}`, {}, token).catch(() => null),
          apiFetch<ClinvarResponse>(`/api/v1/results/clinvar/${userId}?limit=1`, {}, token).catch(() => null),
        ]);

        setFetchError(null);
        if (prsData) {
          setPrsStatus(prsData.prs_status);
          setPrsCount(prsData.results.length);
        }
        if (traitsData) {
          setTraitHits(traitsData.hits);
          setUniqueSnpsMatched(traitsData.unique_snps_matched);
          setTotalSnpsInKb(traitsData.total_snps_in_kb);
        }
        if (pgxData) setPgxResults(pgxData.results);
        if (csData?.result) setCarrierStatus(csData.result);
        if (cvData) {
          setClinvarTotal(cvData.total);
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
          <DashboardContent
            analysis={analysis}
            traitHits={traitHits}
            uniqueSnpsMatched={uniqueSnpsMatched}
            totalSnpsInKb={totalSnpsInKb}
            pgxResults={pgxResults}
            carrierStatus={carrierStatus}
            clinvarTotal={clinvarTotal}
            prsStatus={prsStatus}
            prsCount={prsCount}
            prsDetail={prsDetail}
            prsError={prsError}
            variantsTotal={variantsTotal}
            snpediaTotal={snpediaTotal}
            onDownloadReport={() => downloadReport(analysis?.filename ?? undefined)}
            downloadingReport={downloading}
            onDownloadPgxReport={() => downloadPgxReport(analysis?.filename ?? undefined)}
            downloadingPgxReport={downloadingPgx}
            onDeleteData={() => setShowDeleteConfirm(true)}
          />

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
