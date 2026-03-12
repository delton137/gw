"use client";

import { useState } from "react";
import Link from "next/link";
import DemoBanner from "@/components/DemoBanner";
import { DEMO_PGX, DEMO_ANALYSIS } from "../demoData";
import type { PgxResult } from "@/lib/types";

function isNonNormal(phenotype: string | null): boolean {
  if (!phenotype) return false;
  const p = phenotype.toLowerCase();
  return !p.includes("normal") && !p.includes("negative") && !p.includes("typical");
}

function phenotypeStyle(phenotype: string | null): string {
  if (isNonNormal(phenotype)) return "bg-amber-50 text-amber-800";
  return "";
}

const DRUG_RESPONSE_GENES = new Set([
  "HLA-B_5701", "HLA-B_5801", "HLA-A_3101",
  "SLCO1B1", "SLC15A2", "SLC22A2", "SLCO1B3", "SLCO2B1", "ABCB1", "ABCG2",
  "VKORC1", "MTHFR", "IFNL3", "IFNL4", "CYP2C_cluster",
  "OPRM1", "HTR2A", "HTR2C", "DRD2", "ANKK1", "ADRA2A", "ADRB1", "ADRB2",
  "GRK4", "GRK5", "GRIK4",
  "F5", "F2",
  "G6PD", "RYR1", "CACNA1S", "CFTR",
  "XPC",
]);

function variantCoverageColor(tested: number, total: number): string {
  if (total === 0) return "text-red-600";
  const pct = tested / total;
  if (pct >= 1.0) return "text-green-700";
  if (pct >= 0.5) return "text-yellow-600";
  if (pct >= 0.25) return "text-orange-600";
  return "text-red-600";
}

export default function DemoPgxPage() {
  const results = DEMO_PGX;
  const chipType = DEMO_ANALYSIS.chip_type;
  const [expandedGene, setExpandedGene] = useState<string | null>(null);
  const [guidelinesGene, setGuidelinesGene] = useState<string | null>(null);

  const metabolismResults = results.filter((r) => !DRUG_RESPONSE_GENES.has(r.gene));
  const responseResults = results.filter((r) => DRUG_RESPONSE_GENES.has(r.gene));

  const renderTable = (rows: PgxResult[]) => (
    <div className="border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-4 py-2 font-medium text-muted">Gene</th>
            <th className="px-4 py-2 font-medium text-muted">Phenotype</th>
            <th className="px-4 py-2 font-medium text-muted">Diplotype</th>
            <th className="px-4 py-2 font-medium text-muted text-center">Variants Found</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const isExpanded = expandedGene === r.gene;
            const rowStyle = phenotypeStyle(r.phenotype);
            const hasGuidelines = r.guidelines && (r.guidelines.cpic?.length > 0 || r.guidelines.dpwg?.length > 0);
            const guidelinesOpen = guidelinesGene === r.gene;

            return (
              <tr key={r.gene} className="border-b border-border last:border-0">
                <td colSpan={4} className="p-0">
                  <button
                    onClick={() => setExpandedGene(isExpanded ? null : r.gene)}
                    className={`w-full text-left grid grid-cols-[1fr_1.5fr_1fr_0.75fr] items-center px-4 py-3 hover:bg-gray-50 transition-colors ${rowStyle}`}
                  >
                    <span className="font-medium">{r.gene}</span>
                    <span>{r.phenotype || "\u2014"}</span>
                    <span className="font-mono text-xs">{r.diplotype || "\u2014"}</span>
                    <span className={`text-center font-mono text-xs font-semibold ${variantCoverageColor(r.n_variants_tested, r.n_variants_total)}`}>
                      {r.n_variants_tested}/{r.n_variants_total}
                    </span>
                  </button>

                  {isExpanded && (
                    <div className="px-4 pb-4 pt-1 bg-surface/50 border-t border-border/50">
                      {r.gene_description && <p className="text-sm text-muted mb-2">{r.gene_description}</p>}
                      {r.clinical_note && <p className="text-sm mb-2">{r.clinical_note}</p>}
                      {r.gene === "CYP3A5" && (
                        <div className="text-xs bg-blue-50 border border-blue-200 rounded px-3 py-2 mb-2">
                          <span className="font-semibold text-blue-900">Understanding &ldquo;Expressor&rdquo;:</span>{" "}
                          <span className="text-blue-800">
                            CYP3A5 uses &ldquo;Expressor&rdquo; terminology instead of the usual &ldquo;Normal/Poor Metabolizer&rdquo; because the non-functional *3 allele is actually the most common variant in many populations.
                          </span>
                        </div>
                      )}
                      {r.gene === "CYP2B6" && (
                        <div className="text-xs border border-border rounded px-3 py-2 mb-2">
                          <span className="font-semibold text-foreground">A note on phase ambiguity:</span>{" "}
                          <span className="text-muted">
                            CYP2B6 *6 is defined by two SNPs (rs3745274 + rs2279343). Without phasing, unphased data cannot distinguish *1/*6 from *4/*9.
                          </span>
                        </div>
                      )}
                      {r.drugs_affected && (
                        <p className="text-sm mb-2"><span className="font-medium">Drugs affected:</span> <span className="text-muted">{r.drugs_affected}</span></p>
                      )}
                      {hasGuidelines && (
                        <div className="mt-3 mb-3">
                          <button
                            onClick={(e) => { e.stopPropagation(); setGuidelinesGene(guidelinesOpen ? null : r.gene); }}
                            className="flex items-center gap-1.5 text-xs font-medium text-accent hover:underline"
                          >
                            <span className={`text-[10px] transition-transform ${guidelinesOpen ? "rotate-90" : ""}`}>&#9654;</span>
                            {guidelinesOpen ? "Hide" : "Show"} CPIC/DPWG Guidelines
                          </button>
                          {guidelinesOpen && (
                            <div className="mt-2 space-y-2">
                              {r.guidelines!.cpic?.length > 0 && (
                                <div className="text-sm border-l-2 border-blue-400 pl-3 py-1">
                                  <span className="font-semibold text-blue-700 text-xs uppercase tracking-wide">CPIC Guideline</span>
                                  {r.guidelines!.cpic.map((g, i) => (
                                    <p key={`${g.drug}-${i}`} className="mt-1 text-sm leading-relaxed">
                                      <span className="font-medium capitalize">{g.drug}:</span>{" "}
                                      <span className="text-muted">{g.recommendation}</span>
                                      {g.strength && <span className="text-xs text-blue-600 ml-1">({g.strength})</span>}
                                      {g.pmid && (
                                        <a href={`https://pubmed.ncbi.nlm.nih.gov/${g.pmid}`} target="_blank" rel="noopener noreferrer" className="text-accent text-xs ml-1 hover:underline">[PMID]</a>
                                      )}
                                    </p>
                                  ))}
                                </div>
                              )}
                              {r.guidelines!.dpwg?.length > 0 && (
                                <div className="text-sm border-l-2 border-emerald-400 pl-3 py-1">
                                  <span className="font-semibold text-emerald-700 text-xs uppercase tracking-wide">DPWG Guideline</span>
                                  {r.guidelines!.dpwg.map((g, i) => (
                                    <p key={`${g.drug}-${i}`} className="mt-1 text-sm leading-relaxed">
                                      <span className="font-medium capitalize">{g.drug}:</span>{" "}
                                      <span className="text-muted">{g.recommendation}</span>
                                      {g.pmid && (
                                        <a href={`https://pubmed.ncbi.nlm.nih.gov/${g.pmid}`} target="_blank" rel="noopener noreferrer" className="text-accent text-xs ml-1 hover:underline">[PMID]</a>
                                      )}
                                    </p>
                                  ))}
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      )}
                      {r.defining_variants && Object.keys(r.defining_variants).length > 0 && (
                        <div className="text-sm mb-2">
                          <span className="font-medium">The specific SNPs that led to your function call:</span>
                          {Object.entries(r.defining_variants).map(([allele, variants]) => (
                            <div key={allele} className="ml-2 mt-0.5">
                              <span className="font-mono text-xs">{allele}</span>
                              <span className="text-muted">: </span>
                              {variants.map((v, i) => (
                                <span key={v.rsid}>
                                  {i > 0 && <span className="text-muted"> + </span>}
                                  <Link href={`/snp/${v.rsid}`} className="text-accent hover:underline">{v.rsid}</Link>
                                </span>
                              ))}
                            </div>
                          ))}
                        </div>
                      )}
                      {r.panel_snps && r.panel_snps.length > 0 && (
                        <div className="text-sm mb-2">
                          <span className="font-medium">SNPs in panel ({r.panel_snps.length}):</span>
                          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 ml-2">
                            {r.panel_snps.map((rsid) => {
                              const geno = r.variant_genotypes?.[rsid];
                              return (
                                <span key={rsid} className="text-xs font-mono">
                                  <Link href={`/snp/${rsid}`} className="text-accent hover:underline">{rsid}</Link>
                                  {geno ? <span className="text-muted ml-1">({geno})</span> : <span className="text-red-400 ml-1">(&mdash;)</span>}
                                </span>
                              );
                            })}
                          </div>
                        </div>
                      )}
                      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted mt-2">
                        <span>Variants tested: {r.n_variants_tested} / {r.n_variants_total}</span>
                        <span>Calling method: {r.calling_method}</span>
                      </div>
                    </div>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <DemoBanner />

      <h1 className="font-serif text-3xl font-semibold mb-2">Pharmacogenomics</h1>

      {chipType && chipType !== "wgs" && (
        <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 mb-4 mt-2">
          <p className="text-sm font-semibold text-amber-900">
            Your data is from a SNP chip ({chipType}), so pharmacogenomic results must be interpreted with caution.
          </p>
        </div>
      )}

      <p className="text-sm text-muted mb-3 mt-2">
        <span className="font-semibold text-foreground">{results.length}</span> genes analyzed
      </p>

      <div className="text-xs text-muted mb-8 leading-relaxed">
        <p className="font-semibold text-foreground mt-4">This report is for informational purposes only and is not a clinical pharmacogenomics test</p>
        <p className="mt-1">Results should be confirmed with a clinical-grade test and discussed with a healthcare provider before making prescribing decisions.</p>
      </div>

      {metabolismResults.length > 0 && (
        <section>
          <h2 className="font-serif text-xl font-semibold mb-3">Drug Metabolism</h2>
          <p className="text-xs text-muted mb-3">Enzymes that break down or activate medications in your body.</p>
          {renderTable(metabolismResults)}
        </section>
      )}
      {responseResults.length > 0 && (
        <section className="mt-10">
          <h2 className="font-serif text-xl font-semibold mb-3">Drug Response</h2>
          <p className="text-xs text-muted mb-3">Receptors, transporters, immune markers, and other genes that affect how you respond to medications.</p>
          {renderTable(responseResults)}
        </section>
      )}
    </div>
  );
}
