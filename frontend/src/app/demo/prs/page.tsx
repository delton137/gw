"use client";

import Link from "next/link";
import PrsDistributionChart from "@/components/PrsDistributionChart";
import { SUPERPOP_META } from "@/lib/populations";
import DemoBanner from "@/components/DemoBanner";
import { DEMO_PRS, DEMO_ANALYSIS } from "../demoData";

function formatPercentile(p: number): string {
  const rounded = Math.round(p);
  if (rounded === 0) return "<1";
  if (rounded === 100) return ">99";
  return String(rounded);
}

export default function DemoPrsPage() {
  const prsData = DEMO_PRS;
  const analysis = DEMO_ANALYSIS;

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <DemoBanner />

      <h1 className="font-serif text-3xl font-semibold mb-8">Polygenic Risk Scores &mdash; EXPERIMENTAL &mdash; <span className="text-red-600">currently has known issues!!</span></h1>

      {/* Ancestry panel */}
      <div className="border border-border p-5 mb-8">
        <h2 className="text-sm font-medium mb-3">Ancestry Context</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <p className="text-xs text-muted mb-1">Selected Ancestry (used for PRS)</p>
            <p className="text-sm font-semibold">
              {prsData.selected_ancestry || analysis.selected_ancestry || "EUR"}
              {" \u2014 "}
              {SUPERPOP_META[prsData.selected_ancestry || analysis.selected_ancestry || "EUR"]?.name || "Unknown"}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted mb-1">Estimated Ancestry (computed)</p>
            {analysis.detected_ancestry?.superpopulations ? (
              <p className="text-sm">
                {Object.entries(analysis.detected_ancestry.superpopulations)
                  .filter(([, v]) => v >= 0.02)
                  .sort(([, a], [, b]) => b - a)
                  .map(([pop, pct]) => `${Math.round(pct * 100)}% ${SUPERPOP_META[pop]?.name || pop}`)
                  .join(", ")}
              </p>
            ) : (
              <p className="text-sm text-muted italic">Not available</p>
            )}
          </div>
        </div>
        <p className="text-xs text-muted mt-3">
          PRS scores are calibrated against reference distributions from the selected ancestry group.
        </p>
      </div>

      {/* PRS Results */}
      {prsData.results.length > 0 && (
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
                absoluteRiskLower={prs.absolute_risk_lower}
                absoluteRiskUpper={prs.absolute_risk_upper}
              />
            ) : (
              <div key={prs.pgs_id} className="border border-border p-4">
                <div className="flex items-center justify-between mb-2">
                  <div>
                    <p className="text-sm font-medium">{prs.trait_name}</p>
                    <span className="text-[10px] text-muted">{prs.pgs_id}</span>
                  </div>
                  <p className="text-sm font-semibold">{Math.round(prs.percentile)}th percentile</p>
                </div>
                <div className="h-1.5 bg-muted-bg w-full relative">
                  <div className="h-full bg-accent absolute left-0 top-0" style={{ width: `${prs.percentile}%` }} />
                </div>
                <p className="text-xs text-muted mt-2">
                  {prs.n_variants_matched.toLocaleString()} / {prs.n_variants_total.toLocaleString()} variants matched &middot; {prs.ancestry_group_used}
                </p>
              </div>
            )
          )}
        </div>
      )}

      {/* Summary table */}
      {prsData.results.length > 0 && (
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

      {/* Explainer */}
      <section className="border-t border-border mt-12 pt-8">
        <h2 className="font-serif text-2xl font-semibold mb-4">What is a polygenic risk score?</h2>
        <p className="text-muted leading-relaxed mb-4">
          A polygenic risk score (PRS) combines the effects of many genetic variants to
          estimate your relative risk for a trait or disease. Each variant contributes a
          small amount &mdash; the PRS aggregates thousands of these effects into a single number.
        </p>
        <p className="text-muted leading-relaxed">
          Gene Wizard uses scores from the{" "}
          <a href="https://www.pgscatalog.org" className="text-accent hover:text-accent-hover underline" target="_blank" rel="noopener noreferrer">
            PGS Catalog
          </a>
          , the largest open database of published polygenic scores, and normalizes your
          result against reference populations so you can see where you fall.
        </p>
      </section>
    </div>
  );
}
