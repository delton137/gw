"use client";

import { useState } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { SUPERPOP_META } from "@/lib/populations";
import DemoBanner from "@/components/DemoBanner";
import { DEMO_ANALYSIS } from "../demoData";
import type { AncestryDetail } from "@/lib/types";

export default function DemoAncestryPage() {
  const [showInterpretation, setShowInterpretation] = useState(false);
  const analysis = DEMO_ANALYSIS;

  const ancestry = analysis.detected_ancestry as AncestryDetail;
  if (!ancestry || !("superpopulations" in ancestry)) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <DemoBanner />
        <p className="text-muted">No ancestry data in demo.</p>
      </div>
    );
  }

  const superChartData = Object.entries(ancestry.superpopulations)
    .filter(([, v]) => v >= 0.005)
    .sort(([, a], [, b]) => b - a)
    .map(([code, frac]) => ({
      name: SUPERPOP_META[code]?.name || code,
      code,
      value: Math.round(frac * 1000) / 10,
      color: SUPERPOP_META[code]?.color || "#6b7280",
    }));

  const sortedSuperPops = Object.entries(ancestry.superpopulations).sort(([, a], [, b]) => b - a);
  const bestSuper = sortedSuperPops[0];

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <DemoBanner />

      <h1 className="font-serif text-3xl font-semibold mb-1">
        Genetic Ancestry
        <span className="ml-2 align-middle inline-block text-xs font-sans font-semibold px-2 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
          Experimental
        </span>
      </h1>
      <p className="text-sm text-amber-700 mb-3">May not be very accurate!</p>
      <p className="text-xs text-muted mb-10 border border-border/50 bg-gray-50/50 p-3 rounded">
        This analysis uses techniques from the{" "}
        <a href="https://doi.org/10.1101/2024.06.18.599246" className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">
          AEon ancestry estimation tool
        </a>{" "}
        (Warren &amp; Pinese 2024), which estimates admixture fractions via maximum
        likelihood on 128,097 ancestry-informative loci from the{" "}
        <a href="https://doi.org/10.1038/nature15393" className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">
          1000 Genomes Project Phase 3
        </a>.
      </p>

      {/* Summary + Donut Chart */}
      <div className="border border-border p-6 mb-10 flex flex-col sm:flex-row gap-8 items-center">
        <div className="w-52 h-52 flex-shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={superChartData} cx="50%" cy="50%" innerRadius={50} outerRadius={85} paddingAngle={2} dataKey="value" stroke="none">
                {superChartData.map((entry) => <Cell key={entry.code} fill={entry.color} />)}
              </Pie>
              <Tooltip
                formatter={(value) => [`${value ?? 0}%`, ""]}
                labelFormatter={(_, payload) => payload?.[0]?.payload?.name || ""}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex-1">
          <div className="mb-4">
            <span className="text-sm text-muted">Primary ancestry</span>
            <p className="font-serif text-2xl font-semibold">
              {SUPERPOP_META[bestSuper[0]]?.name || bestSuper[0]}
              <span className="text-lg text-muted ml-2">{(bestSuper[1] * 100).toFixed(1)}%</span>
            </p>
            {ancestry.is_admixed && (
              <span className="inline-block mt-1 text-xs px-2 py-0.5 rounded-full bg-violet-50 text-violet-700">Admixed</span>
            )}
          </div>
          <div className="space-y-1.5">
            {sortedSuperPops.filter(([, v]) => v >= 0.01).map(([code, frac]) => (
              <div key={code} className="flex items-center gap-2 text-sm">
                <span className="inline-block w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: SUPERPOP_META[code]?.color || "#6b7280" }} />
                <span className="font-medium w-28">{SUPERPOP_META[code]?.name || code}</span>
                <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full rounded-full" style={{ width: `${Math.max(frac * 100, 1)}%`, backgroundColor: SUPERPOP_META[code]?.color || "#6b7280" }} />
                </div>
                <span className="text-muted font-mono text-xs w-12 text-right">{(frac * 100).toFixed(1)}%</span>
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
              <span className="text-muted font-normal"> / {ancestry.n_markers_total.toLocaleString()}</span>
            </p>
          </div>
          <div>
            <p className="text-xs text-muted mb-0.5">Coverage</p>
            <p className="font-medium">
              <span className={`inline-block px-2 py-0.5 text-xs rounded-full ${
                ancestry.coverage_quality === "high" ? "bg-emerald-50 text-emerald-700"
                : ancestry.coverage_quality === "medium" ? "bg-amber-50 text-amber-700"
                : "bg-red-50 text-red-700"
              }`}>{ancestry.coverage_quality}</span>
            </p>
          </div>
          <div>
            <p className="text-xs text-muted mb-0.5">Method</p>
            <p className="font-medium text-xs">
              {analysis.ancestry_method === "aeon_mle" ? "Maximum Likelihood Estimation" : analysis.ancestry_method || "Unknown"}
            </p>
          </div>
        </div>
      </div>

      {/* Interpretation Guide */}
      <div className="border border-border mb-10">
        <button onClick={() => setShowInterpretation(!showInterpretation)} className="w-full px-5 py-3 flex items-center justify-between text-left hover:bg-gray-50/50 transition-colors">
          <span className="font-serif text-lg font-semibold">How to interpret these results</span>
          <span className="text-muted text-sm">{showInterpretation ? "\u25B2" : "\u25BC"}</span>
        </button>
        {showInterpretation && (
          <div className="px-5 pb-5 text-sm text-muted space-y-3">
            <p>These estimates represent the statistical similarity between your genetic variants and 26 reference populations from the 1000 Genomes Project Phase 3.</p>
            <div>
              <p className="font-medium text-foreground mb-1">Score interpretation:</p>
              <ul className="list-disc list-inside space-y-0.5">
                <li><span className="font-medium">&gt; 10%</span> &mdash; Significant ancestry component</li>
                <li><span className="font-medium">5&ndash;10%</span> &mdash; Likely significant</li>
                <li><span className="font-medium">2&ndash;5%</span> &mdash; Possible but uncertain</li>
                <li><span className="font-medium">&lt; 2%</span> &mdash; Likely statistical noise</li>
              </ul>
            </div>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <div className="text-xs text-muted space-y-2 border-t border-border pt-6">
        <p>
          <strong>Important:</strong> Genetic ancestry estimation reflects statistical patterns in DNA,
          not ethnic, cultural, or national identity.
        </p>
      </div>
    </div>
  );
}
