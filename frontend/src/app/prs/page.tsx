"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import PrsDistributionChart from "@/components/PrsDistributionChart";
import { SUPERPOP_META } from "@/lib/populations";
import type { Analysis, PrsResponse, PrsResult } from "@/lib/types";

function formatPercentile(p: number): string {
  const rounded = Math.round(p);
  if (rounded === 0) return "<1";
  if (rounded === 100) return ">99";
  return String(rounded);
}

export default function PrsPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [prsData, setPrsData] = useState<PrsResponse | null>(null);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [loading, setLoading] = useState(true);
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
      setPrsData(data);
      if (data.prs_status === "computing") {
        pollRef.current = setTimeout(pollPrs, 5000);
      }
    } catch {
      // Not available yet
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

        const data = await apiFetch<PrsResponse>(
          `/api/v1/results/prs/${userId}`,
          {},
          token
        );
        setPrsData(data);

        // Fetch analysis for ancestry info
        if (data.analysis_id) {
          const analysisData = await apiFetch<Analysis>(
            `/api/v1/results/analysis/${data.analysis_id}`,
            {},
            token
          );
          setAnalysis(analysisData);
        }

        if (data.prs_status === "computing") {
          pollRef.current = setTimeout(pollPrs, 5000);
        }
      } catch {
        // Not available
      } finally {
        setLoading(false);
      }
    }
    if (user) load();
  }, [getToken, user, pollPrs]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (!prsData) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <h1 className="font-serif text-3xl font-semibold mb-4">Polygenic Risk Scores — EXPERIMENTAL — <span className="text-red-600">may have errors</span></h1>
        <p className="text-muted mb-4">No PRS results available yet.</p>
        <Link href="/dashboard" className="text-accent hover:underline text-sm">
          &larr; Back to dashboard
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <Link href="/dashboard" className="text-sm text-accent hover:underline mb-6 inline-block">
        &larr; Back to dashboard
      </Link>

      <h1 className="font-serif text-3xl font-semibold mb-8">Polygenic Risk Scores — EXPERIMENTAL — <span className="text-red-600">may have errors</span></h1>

      {/* Ancestry panel */}
      <div className="border border-border p-5 mb-8">
        <h2 className="text-sm font-medium mb-3">Ancestry Context</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {/* Selected ancestry */}
          <div>
            <p className="text-xs text-muted mb-1">Selected Ancestry (used for PRS)</p>
            <p className="text-sm font-semibold">
              {prsData.selected_ancestry || analysis?.selected_ancestry || "EUR"}
              {" \u2014 "}
              {SUPERPOP_META[prsData.selected_ancestry || analysis?.selected_ancestry || "EUR"]?.name || "Unknown"}
            </p>
          </div>

          {/* Estimated ancestry */}
          <div>
            <p className="text-xs text-muted mb-1">Estimated Ancestry (computed)</p>
            {analysis?.detected_ancestry?.superpopulations ? (
              <p className="text-sm">
                {Object.entries(analysis.detected_ancestry.superpopulations)
                  .filter(([, v]) => v >= 0.02)
                  .sort(([, a], [, b]) => b - a)
                  .map(([pop, pct]) => `${Math.round(pct * 100)}% ${SUPERPOP_META[pop]?.name || pop}`)
                  .join(", ")}
                {analysis.ancestry_confidence !== null && (
                  <span className="text-muted ml-1">
                    ({Math.round(analysis.ancestry_confidence * 100)}% confidence)
                  </span>
                )}
              </p>
            ) : analysis?.ancestry_method === "computed_failed" ? (
              <p className="text-sm text-muted italic">Could not estimate (too few markers)</p>
            ) : prsData.prs_status === "computing" ? (
              <p className="text-sm text-muted italic">Computing...</p>
            ) : (
              <p className="text-sm text-muted italic">Not available</p>
            )}
          </div>
        </div>
        <p className="text-xs text-muted mt-3">
          PRS scores are calibrated against reference distributions from the selected ancestry group.
          The estimated ancestry is shown for comparison and debugging purposes.
        </p>
      </div>

      {/* PRS status */}
      {prsData.prs_status === "computing" && (
        <div className="border border-border p-8 text-center mb-8">
          <div className="flex items-center justify-center gap-2 text-sm text-muted mb-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Computing polygenic risk scores...
          </div>
          <p className="text-xs text-muted">This may take a few minutes. This page will update automatically.</p>
        </div>
      )}

      {prsData.prs_status === "failed" && (
        <div className="border border-red-200 bg-red-50/50 p-5 mb-8">
          <p className="text-sm text-risk-high mb-1">PRS computation failed.</p>
          {analysis?.error_message && (
            <p className="text-xs text-muted">{analysis.error_message}</p>
          )}
        </div>
      )}

      {/* PRS Results */}
      {prsData.prs_status === "ready" && prsData.results.length > 0 && (
        <div className="space-y-4">
          {prsData.results.map((prs) =>
            prs.ref_mean != null && prs.ref_std != null && prs.ref_std > 0 ? (
              <PrsDistributionChart
                key={prs.pgs_id}
                rawScore={prs.raw_score}
                refMean={prs.ref_mean}
                refStd={prs.ref_std}
                percentile={prs.percentile}
                traitName={prs.trait_name}
                ancestryGroup={prs.ancestry_group_used}
                nMatched={prs.n_variants_matched}
                nTotal={prs.n_variants_total}
                absoluteRisk={prs.absolute_risk}
                populationRisk={prs.population_risk}
                prevalenceSource={prs.prevalence_source}
                percentileLower={prs.percentile_lower}
                percentileUpper={prs.percentile_upper}
                coverageQuality={prs.coverage_quality}
                reportedAuc={prs.reported_auc}
                publicationPmid={prs.publication_pmid}
                publicationDoi={prs.publication_doi}
                pgsId={prs.pgs_id}
              />
            ) : (
              <div key={prs.pgs_id} className="border border-border p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium">{prs.trait_name}</p>
                    <div className="flex gap-2 mt-0.5">
                      <span className="text-[10px] text-muted">{prs.pgs_id}</span>
                      {prs.publication_pmid && (
                        <a href={`https://pubmed.ncbi.nlm.nih.gov/${prs.publication_pmid}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-accent hover:underline">PubMed</a>
                      )}
                      {prs.publication_doi && (
                        <a href={`https://doi.org/${prs.publication_doi}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-accent hover:underline">DOI</a>
                      )}
                    </div>
                  </div>
                  <p className="text-sm font-semibold">
                    {Math.round(prs.percentile)}th percentile
                  </p>
                </div>
                <div className="h-1.5 bg-muted-bg w-full relative">
                  <div
                    className="h-full bg-accent absolute left-0 top-0"
                    style={{ width: `${prs.percentile}%` }}
                  />
                </div>
                <p className="text-xs text-muted mt-2">
                  {prs.n_variants_matched.toLocaleString()} /{" "}
                  {prs.n_variants_total.toLocaleString()} variants matched
                  &middot; {prs.ancestry_group_used}
                </p>
              </div>
            )
          )}
        </div>
      )}

      {/* Summary table */}
      {prsData.prs_status === "ready" && prsData.results.length > 0 && (
        <div className="mt-12 border border-border">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left text-xs text-muted">
                <th className="px-4 py-2 font-medium">ID</th>
                <th className="px-4 py-2 font-medium">Trait</th>
                <th className="px-4 py-2 font-medium text-right">Variants</th>
                <th className="px-4 py-2 font-medium text-right">Raw Score</th>
                <th className="px-4 py-2 font-medium text-right">Percentile</th>
              </tr>
            </thead>
            <tbody>
              {prsData.results.map((prs) => (
                <tr key={prs.pgs_id} className="border-b border-border last:border-b-0">
                  <td className="px-4 py-2">
                    <a href={`https://www.pgscatalog.org/score/${prs.pgs_id}/`} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">{prs.pgs_id}</a>
                  </td>
                  <td className="px-4 py-2">{prs.trait_name}</td>
                  <td className="px-4 py-2 text-right">{prs.n_variants_total.toLocaleString()}</td>
                  <td className="px-4 py-2 text-right font-mono">{prs.raw_score.toPrecision(4)}</td>
                  <td className="px-4 py-2 text-right">{formatPercentile(prs.percentile)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {prsData.prs_status === "ready" && prsData.results.length === 0 && (
        <div className="border border-border p-8 text-center">
          <p className="text-muted">No PRS scores were computed for this analysis.</p>
        </div>
      )}
    </div>
  );
}
