"use client";

import { useEffect, useState, useRef, useCallback } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { GwasResponse, GwasScore } from "@/lib/types";

const CATEGORY_ORDER = [
  "cardiovascular",
  "cancer",
  "metabolic",
  "autoimmune",
  "neuropsychiatric",
];

const CATEGORY_LABELS: Record<string, string> = {
  cardiovascular: "Cardiovascular",
  cancer: "Cancer",
  metabolic: "Metabolic",
  autoimmune: "Autoimmune & Inflammatory",
  neuropsychiatric: "Neuropsychiatric",
};

function percentileColor(pct: number): string {
  if (pct >= 80) return "text-risk-high";
  if (pct >= 60) return "text-risk-moderate";
  return "text-risk-typical";
}

function percentileBarColor(pct: number): string {
  if (pct >= 80) return "bg-red-500";
  if (pct >= 60) return "bg-amber-500";
  return "bg-green-600";
}

function percentileLabel(pct: number): string {
  if (pct >= 90) return "High";
  if (pct >= 75) return "Above average";
  if (pct >= 25) return "Average";
  if (pct >= 10) return "Below average";
  return "Low";
}

export default function GwasPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [data, setData] = useState<GwasResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [collapsedCategories, setCollapsedCategories] = useState<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const pollGwas = useCallback(async () => {
    if (!user?.id) return;
    try {
      const token = await getToken();
      const resp = await apiFetch<GwasResponse>(
        `/api/v1/results/gwas/${user.id}`,
        {},
        token
      );
      setData(resp);
      if (resp.gwas_status === "computing") {
        pollRef.current = setTimeout(pollGwas, 5000);
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

        const resp = await apiFetch<GwasResponse>(
          `/api/v1/results/gwas/${userId}`,
          {},
          token
        );
        setData(resp);

        if (resp.gwas_status === "computing") {
          pollRef.current = setTimeout(pollGwas, 5000);
        }
      } catch {
        // Not available
      } finally {
        setLoading(false);
      }
    }
    if (user) load();
  }, [getToken, user, pollGwas]);

  const toggleCategory = (cat: string) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev);
      if (next.has(cat)) next.delete(cat);
      else next.add(cat);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <h1 className="font-serif text-3xl font-semibold mb-4">
          GWAS Risk Scores
        </h1>
        <p className="text-muted mb-4">No GWAS risk scores available yet.</p>
        <Link
          href="/dashboard"
          className="text-accent hover:underline text-sm"
        >
          &larr; Back to dashboard
        </Link>
      </div>
    );
  }

  const sortedCategories = CATEGORY_ORDER.filter(
    (cat) => data.categories[cat]?.length > 0
  );
  // Include any unexpected categories at the end
  for (const cat of Object.keys(data.categories)) {
    if (!sortedCategories.includes(cat)) sortedCategories.push(cat);
  }

  // Count elevated scores
  const allScores = Object.values(data.categories).flat();
  const elevatedCount = allScores.filter(
    (s) => s.percentile !== null && s.percentile >= 80
  ).length;

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <Link
        href="/dashboard"
        className="text-sm text-accent hover:underline mb-6 inline-block"
      >
        &larr; Back to dashboard
      </Link>

      <h1 className="font-serif text-3xl font-semibold mb-2">
        GWAS Risk Scores
        <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
          Experimental
        </span>
      </h1>

      <p className="text-sm text-muted mb-8 max-w-2xl">
        These scores are computed from published genome-wide association studies (GWAS),
        each using 10&ndash;200 curated SNPs. They provide an independent perspective on
        genetic risk, separate from the genome-wide polygenic risk scores on the{" "}
        <Link href="/prs" className="text-accent hover:underline">
          PRS page
        </Link>
        . Percentiles compare your score to a reference population.
      </p>

      {/* Computing state */}
      {data.gwas_status === "computing" && (
        <div className="border border-border p-8 text-center mb-8">
          <div className="flex items-center justify-center gap-2 text-sm text-muted mb-2">
            <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
                fill="none"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            Computing GWAS risk scores...
          </div>
          <p className="text-xs text-muted">
            This may take a few minutes. This page will update automatically.
          </p>
        </div>
      )}

      {/* Failed state */}
      {data.gwas_status === "failed" && (
        <div className="border border-red-200 bg-red-50/50 p-5 mb-8">
          <p className="text-sm text-risk-high mb-1">
            GWAS score computation failed.
          </p>
          <p className="text-xs text-muted">
            This is non-fatal and does not affect your other results.
          </p>
        </div>
      )}

      {/* Ready state with results */}
      {data.gwas_status === "ready" && data.total_scores > 0 && (
        <>
          {/* Summary bar */}
          <div className="border border-border p-4 mb-8 flex flex-wrap items-baseline gap-x-8 gap-y-2">
            <div>
              <p className="text-xs text-muted mb-0.5">Scores Computed</p>
              <p className="text-sm font-semibold">{data.total_scores}</p>
            </div>
            <div>
              <p className="text-xs text-muted mb-0.5">Disease Categories</p>
              <p className="text-sm font-semibold">{sortedCategories.length}</p>
            </div>
            {elevatedCount > 0 && (
              <div>
                <p className="text-xs text-muted mb-0.5">Elevated (&ge;80th)</p>
                <p className="text-sm font-semibold text-risk-high">
                  {elevatedCount}
                </p>
              </div>
            )}
          </div>

          {/* Categories */}
          {sortedCategories.map((cat) => {
            const scores = data.categories[cat];
            const isCollapsed = collapsedCategories.has(cat);
            const catElevated = scores.filter(
              (s) => s.percentile !== null && s.percentile >= 80
            ).length;

            return (
              <section key={cat} className="mb-8">
                <button
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  className="w-full flex items-center justify-between py-2 group text-left"
                >
                  <div className="flex items-center gap-3">
                    <h2 className="font-serif text-xl font-semibold">
                      {CATEGORY_LABELS[cat] || cat}
                    </h2>
                    <span className="text-xs text-muted">
                      {scores.length} score{scores.length !== 1 ? "s" : ""}
                    </span>
                    {catElevated > 0 && (
                      <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700">
                        {catElevated} elevated
                      </span>
                    )}
                  </div>
                  <span className="text-muted text-xs group-hover:text-accent transition-colors">
                    {isCollapsed ? "Show \u2193" : "Hide \u2191"}
                  </span>
                </button>

                {!isCollapsed && (
                  <div className="space-y-3 mt-2">
                    {scores.map((score) => (
                      <div
                        key={score.study_id}
                        className="border border-border p-4"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-medium">{score.trait}</p>
                            {score.citation && (
                              <p className="text-xs text-muted mt-0.5 truncate">
                                {score.citation}
                                {score.pmid && (
                                  <>
                                    {" "}
                                    &middot;{" "}
                                    <a
                                      href={`https://pubmed.ncbi.nlm.nih.gov/${score.pmid}/`}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="text-accent hover:underline"
                                    >
                                      PubMed
                                    </a>
                                  </>
                                )}
                              </p>
                            )}
                          </div>
                          {score.percentile !== null && (
                            <div className="text-right ml-4 flex-shrink-0">
                              <p
                                className={`text-lg font-semibold tabular-nums ${percentileColor(
                                  score.percentile
                                )}`}
                              >
                                {Math.round(score.percentile)}
                                <span className="text-xs font-normal ml-0.5">
                                  th
                                </span>
                              </p>
                              <p className="text-[10px] text-muted">
                                {percentileLabel(score.percentile)}
                              </p>
                            </div>
                          )}
                        </div>

                        {/* Percentile bar */}
                        {score.percentile !== null ? (
                          <div className="h-1.5 bg-muted-bg w-full relative mb-2">
                            <div
                              className={`h-full absolute left-0 top-0 ${percentileBarColor(
                                score.percentile
                              )}`}
                              style={{
                                width: `${score.percentile}%`,
                              }}
                            />
                          </div>
                        ) : (
                          <p className="text-xs text-muted italic mb-2">
                            Percentile unavailable (insufficient reference data)
                          </p>
                        )}

                        {/* Metadata row */}
                        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
                          <span>
                            {score.n_variants_matched} / {score.n_variants_total}{" "}
                            variants matched
                          </span>
                          <span>
                            {score.ancestry_group_used} reference
                          </span>
                          {score.raw_score !== null && (
                            <span className="font-mono">
                              raw: {score.raw_score.toFixed(4)}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            );
          })}

          {/* Disclaimer */}
          <div className="border-t border-border pt-6 mt-4">
            <p className="text-xs text-muted">
              These scores are derived from published GWAS studies and reflect genetic
              predisposition only. They do not account for lifestyle, environment, family
              history, or other non-genetic factors. A high percentile does not mean you
              will develop the condition, and a low percentile does not guarantee
              protection. These results are for informational and educational purposes only
              and should not be used for medical decision-making. Consult a healthcare
              provider or genetic counselor for clinical interpretation.
            </p>
          </div>
        </>
      )}

      {/* Ready but no results */}
      {data.gwas_status === "ready" && data.total_scores === 0 && (
        <div className="border border-border p-8 text-center">
          <p className="text-muted">
            No GWAS risk scores were computed for this analysis.
          </p>
        </div>
      )}
    </div>
  );
}
