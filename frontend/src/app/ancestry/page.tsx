"use client";

import { useEffect, useState } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { SUPERPOP_META } from "@/lib/populations";
import type { Analysis, AncestryDetail } from "@/lib/types";

interface PrsResponse {
  analysis_id: string;
  prs_status: string;
}

function isNewFormat(data: AncestryDetail | Record<string, number>): data is AncestryDetail {
  return "populations" in data && "superpopulations" in data;
}

export default function AncestryPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [ancestry, setAncestry] = useState<AncestryDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [method, setMethod] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const token = await getToken();
        const userId = user?.id;
        if (!userId) return;

        // Get analysis ID from PRS endpoint (same pattern as dashboard)
        const prsData = await apiFetch<PrsResponse>(
          `/api/v1/results/prs/${userId}`,
          {},
          token
        );
        if (!prsData.analysis_id) return;

        const analysisData = await apiFetch<Analysis>(
          `/api/v1/results/analysis/${prsData.analysis_id}`,
          {},
          token
        );

        setMethod(analysisData.ancestry_method);

        if (analysisData.detected_ancestry) {
          if (isNewFormat(analysisData.detected_ancestry)) {
            setAncestry(analysisData.detected_ancestry);
          } else {
            // Legacy format: flat 5-superpopulation dict
            const legacy = analysisData.detected_ancestry as Record<string, number>;
            setAncestry({
              populations: legacy,
              superpopulations: legacy,
              n_markers_used: 0,
              n_markers_total: 0,
              coverage_quality: "unknown",
              is_admixed: (analysisData.ancestry_confidence ?? 0) < 0.8,
            });
          }
        }
      } catch {
        // API not available
      } finally {
        setLoading(false);
      }
    }
    if (user) load();
  }, [getToken, user]);

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading ancestry data...</p>
      </div>
    );
  }

  if (!ancestry) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <h1 className="font-serif text-3xl font-semibold mb-4">Genetic Ancestry</h1>
        <div className="border border-border p-12 text-center">
          <p className="text-muted mb-4">
            No ancestry data available yet. Ancestry is estimated during the background analysis phase.
          </p>
          <Link href="/dashboard" className="text-accent hover:underline text-sm">
            Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  // Prepare donut chart data (superpopulations)
  const superChartData = Object.entries(ancestry.superpopulations)
    .filter(([, v]) => v >= 0.005)
    .sort(([, a], [, b]) => b - a)
    .map(([code, frac]) => ({
      name: SUPERPOP_META[code]?.name || code,
      code,
      value: Math.round(frac * 1000) / 10,
      color: SUPERPOP_META[code]?.color || "#6b7280",
    }));

  // Sort superpopulations by total fraction
  const sortedSuperPops = Object.entries(ancestry.superpopulations)
    .sort(([, a], [, b]) => b - a);

  const bestSuper = sortedSuperPops[0];

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <div className="mb-8">
        <Link href="/dashboard" className="text-xs text-muted hover:text-foreground">
          &larr; Dashboard
        </Link>
      </div>

      <h1 className="font-serif text-3xl font-semibold mb-1">
        Genetic Ancestry
        <span className="ml-2 align-middle inline-block text-xs font-sans font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
          Experimental
        </span>
      </h1>
      <p className="text-sm text-amber-700 mb-3">
        May not be very accurate!
      </p>
      <div className="text-xs text-muted mb-10 border border-border/50 bg-gray-50/50 p-3 rounded space-y-2">
        <p>
          This analysis uses techniques from the{" "}
          <a
            href="https://doi.org/10.1101/2024.06.18.599246"
            className="text-accent hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            AEon ancestry estimation tool
          </a>{" "}
          (Warren &amp; Pinese 2024), which estimates admixture fractions via maximum
          likelihood on 128,097 ancestry-informative loci from the{" "}
          <a
            href="https://doi.org/10.1038/nature15393"
            className="text-accent hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            1000 Genomes Project Phase 3
          </a>{" "}
          (2,504 unrelated individuals across 26 populations).
        </p>
        <p>
          Genetic ancestry estimation reflects statistical patterns in DNA, not ethnic, cultural,
          or national identity. These results should not be used for medical decisions or legal
          purposes. The 1000 Genomes reference populations represent specific sampled groups, not
          entire regions or ethnicities.
        </p>
      </div>

      {/* Summary + Donut Chart */}
      <div className="border border-border p-6 mb-10 flex flex-col sm:flex-row gap-8 items-center">
        <div className="w-52 h-52 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={superChartData}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={85}
                paddingAngle={2}
                dataKey="value"
                stroke="none"
              >
                {superChartData.map((entry) => (
                  <Cell key={entry.code} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip
                formatter={(value) => [`${value ?? 0}%`, ""]}
                labelFormatter={(_, payload) =>
                  payload?.[0]?.payload?.name || ""
                }
              />
            </PieChart>
          </ResponsiveContainer>
        </div>

        <div className="flex-1">
          <div className="mb-4">
            <span className="text-sm text-muted">Primary ancestry</span>
            <p className="font-serif text-2xl font-semibold">
              {SUPERPOP_META[bestSuper[0]]?.name || bestSuper[0]}
              <span className="text-lg text-muted ml-2">
                {(bestSuper[1] * 100).toFixed(1)}%
              </span>
            </p>
            {ancestry.is_admixed && (
              <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-700">
                Admixed
              </span>
            )}
          </div>

          {/* Superpopulation legend */}
          <div className="space-y-1.5">
            {sortedSuperPops
              .filter(([, v]) => v >= 0.01)
              .map(([code, frac]) => (
                <div key={code} className="flex items-center gap-2 text-sm">
                  <span
                    className="inline-block w-3 h-3 rounded-full flex-shrink-0"
                    style={{ backgroundColor: SUPERPOP_META[code]?.color || "#6b7280" }}
                  />
                  <span className="font-medium w-28">
                    {SUPERPOP_META[code]?.name || code}
                  </span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full rounded-full"
                      style={{
                        width: `${Math.max(frac * 100, 1)}%`,
                        backgroundColor: SUPERPOP_META[code]?.color || "#6b7280",
                      }}
                    />
                  </div>
                  <span className="text-muted font-mono text-xs w-12 text-right">
                    {(frac * 100).toFixed(1)}%
                  </span>
                </div>
              ))}
          </div>
        </div>
      </div>

      {/* Coverage Metrics */}
      <div className="border border-border p-5 mb-10">
        <h2 className="font-serif text-lg font-semibold mb-2">Analysis Quality</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 text-sm">
          <div>
            <p className="text-xs text-muted mb-0.5">Markers Used</p>
            <p className="font-medium">
              {ancestry.n_markers_used.toLocaleString()}
              <span className="text-muted font-normal">
                {" "}/ {ancestry.n_markers_total.toLocaleString()}
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-muted mb-0.5">Coverage</p>
            <p className="font-medium">
              <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                ancestry.coverage_quality === "high"
                  ? "bg-emerald-50 text-emerald-700"
                  : ancestry.coverage_quality === "medium"
                  ? "bg-amber-50 text-amber-700"
                  : "bg-red-50 text-red-700"
              }`}>
                {ancestry.coverage_quality}
              </span>
            </p>
          </div>
          <div>
            <p className="text-xs text-muted mb-0.5">Method</p>
            <p className="font-medium text-xs">
              {method === "aeon_mle"
                ? "Maximum Likelihood Estimation"
                : method || "Unknown"}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
