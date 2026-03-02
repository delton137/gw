"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch, apiDownloadBlob, triggerBlobDownload } from "@/lib/api";

interface DefiningVariant {
  rsid: string;
  variant_allele: string;
}

interface DrugGuideline {
  drug: string;
  recommendation: string;
  implication: string | null;
  strength: string | null;
  pmid: string | null;
}

interface PgxResult {
  gene: string;
  diplotype: string | null;
  allele1: string | null;
  allele2: string | null;
  allele1_function: string | null;
  allele2_function: string | null;
  phenotype: string | null;
  activity_score: number | null;
  n_variants_tested: number;
  n_variants_total: number;
  calling_method: string;
  confidence: string;
  drugs_affected: string | null;
  clinical_note: string | null;
  gene_description: string | null;
  computed_at: string | null;
  defining_variants: Record<string, DefiningVariant[]> | null;
  guidelines: { cpic: DrugGuideline[]; dpwg: DrugGuideline[] } | null;
}

function isActionable(phenotype: string | null): boolean {
  if (!phenotype) return false;
  const p = phenotype.toLowerCase();
  return (
    p.includes("poor metabolizer") ||
    p.includes("ultra-rapid") ||
    p.includes("ultrarapid") ||
    p.includes("positive") ||
    p.includes("high warfarin sensitivity")
  );
}

function isModerate(phenotype: string | null): boolean {
  if (!phenotype) return false;
  const p = phenotype.toLowerCase();
  return (
    p.includes("intermediate") ||
    p.includes("decreased function")
  );
}

function phenotypeStyle(phenotype: string | null): string {
  if (isActionable(phenotype)) return "bg-red-50 text-red-800";
  if (isModerate(phenotype)) return "bg-amber-50 text-amber-800";
  return "";
}

function variantCoverageColor(tested: number, total: number): string {
  if (total === 0) return "text-red-600";
  const pct = tested / total;
  if (pct >= 1.0) return "text-green-700";
  if (pct >= 0.5) return "text-yellow-600";
  if (pct >= 0.25) return "text-orange-600";
  return "text-red-600";
}

export default function PgxPage() {
  const { userId, getToken } = useAuth();
  const [results, setResults] = useState<PgxResult[]>([]);
  const [analysisFilename, setAnalysisFilename] = useState<string | null>(null);
  const [chipType, setChipType] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [downloading, setDownloading] = useState(false);
  const [expandedGene, setExpandedGene] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!userId) return;
      try {
        const token = await getToken();
        const data = await apiFetch<{ analysis_id: string; results: PgxResult[] }>(
          `/api/v1/results/pgx/${userId}`,
          {},
          token,
        );
        setResults(data.results);
        if (data.analysis_id) {
          const analysis = await apiFetch<{ filename: string | null; chip_type: string | null }>(
            `/api/v1/results/analysis/${data.analysis_id}`,
            {},
            token,
          );
          setAnalysisFilename(analysis.filename);
          setChipType(analysis.chip_type);
        }
      } catch {
        // API unavailable or no results
      } finally {
        setLoading(false);
      }
    }
    if (userId) load();
  }, [userId, getToken]);

  const handleDownloadPgxReport = async () => {
    setDownloading(true);
    try {
      const token = await getToken();
      const blob = await apiDownloadBlob("/api/v1/report/pgx/download", token);
      const suffix = analysisFilename ? `--${analysisFilename}` : "";
      triggerBlobDownload(blob, `genewizard-pgx-report${suffix}.pdf`);
    } catch {
      alert("Failed to download PGX report. Please try again.");
    } finally {
      setDownloading(false);
    }
  };

  if (!userId) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Please sign in to view your pharmacogenomics results.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <div className="flex items-start justify-between mb-2">
        <h1 className="font-serif text-3xl font-semibold">Pharmacogenomics</h1>
        <Link href="/dashboard" className="text-sm text-accent hover:underline mt-2">
          &larr; Dashboard
        </Link>
      </div>

      {results.length === 0 ? (
        <div className="border border-border p-12 text-center mt-8">
          <p className="text-muted mb-4">No pharmacogenomics results yet.</p>
          <Link href="/upload" className="text-accent hover:underline text-sm">
            Upload your genotype file to get started
          </Link>
        </div>
      ) : (
        <>
          {/* SNP chip warning */}
          {chipType && chipType !== "wgs" && (
            <div className="bg-amber-50 border border-amber-300 rounded-lg px-4 py-3 mb-4 mt-2">
              <p className="text-sm font-semibold text-amber-900">
                Your data is from a SNP chip ({chipType}), so pharmacogenomic results must be interpreted with caution. Pay close attention to the Variants Found column. When not all variants can be determined from your file, results will be unreliable. 
              </p>
              <p className="text-xs text-amber-800 mt-1">
                SNP chips only test a small subset of pharmacogenomic variants. Whole genome sequencing (WGS) data is required to test all variants. Consumer WGS is available for under $300 from companies like <a href="https://www.nebula.org/" target="_blank" rel="noopener noreferrer" className="underline hover:text-amber-950">Nebula Genomics</a> and <a href="https://www.dantelabs.com/" target="_blank" rel="noopener noreferrer" className="underline hover:text-amber-950">Dante Labs</a>.
              </p>
            </div>
          )}

          {/* Summary */}
          <p className="text-sm text-muted mb-3 mt-2">
            <span className="font-semibold text-foreground">{results.length}</span> genes analyzed
          </p>

          <div className="text-xs text-muted mb-8 leading-relaxed">
            <p className="font-semibold text-foreground mt-4">This report is for informational purposes only and is not a clinical pharmacogenomics test</p>
            <p className="mt-1">
              Results should be confirmed with a clinical-grade test and discussed with a healthcare provider before making prescribing decisions.
            </p>
            <p className="font-semibold text-foreground mt-4">SNP chips don&apos;t work well here!</p>
            <p className="mt-1">
              SNP chips (from 23andMe, AncestryDNA, etc.) only test a pre-selected subset of genomic positions. Many key pharmacogenomic variants are missing from consumer SNP chips. Pay close attention to the Variants Found column. When not all variants can be found using your file, results will be unreliable.
            </p>
            <p className="font-semibold text-foreground mt-4">Consumer WGS and SNP Chip data does not measure copy number variation</p>
            <p className="mt-1">
              We do not report on SULT1A1 and GSTM1 enzyme function since they are commonly affected by copy number variation (CNV), which standard consumer data does not detect. CNV in CYP2D6 is
              present in 12% of Americans and up to 29% in some East African populations.{" "}
              [<a href="https://pmc.ncbi.nlm.nih.gov/articles/PMC4704658/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">1</a>]{" "}
              [<a href="https://pubmed.ncbi.nlm.nih.gov/8764380/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">2</a>]{" "}
              However, in a study of 15,000 patients receiving clinical pharmacogenomic testing in the United States, CNV only changed CYP2D6 phenotype in only about 2% of patients.{" "}
              [<a href="https://www.nature.com/articles/s41380-024-02588-4" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">Bousman et al. 2024</a>]{" "} 
              This is why some consumer companies predict CYP2D6 function without measuring CNV. We also present a CYP2D6 prediction here, but bear in mind that you may be the subset of people where that prediction is inaccurate. CNV in CYP2A6 is very rare overall but appears in 15-20% of East Asians.{" "}
              [<a href="https://pubmed.ncbi.nlm.nih.gov/23164804/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">1</a>,{" "}
              <a href="https://pubmed.ncbi.nlm.nih.gov/32131765/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">2</a>,{" "}
              <a href="https://www.ncbi.nlm.nih.gov/pmc/articles/PMC5600063/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">3</a>]
              For CYP2B6, CYP2C19, CYP1A2, and CYP2E1, CNV is important in about 2% or less of cases. For the remaining genes in this report, significant CNV has not been reported in the scientific literature as far as we can tell. 
            </p>
            <p className="font-semibold text-foreground mt-4">Phenoconversion: when taking a medication changes your metabolizer status</p>
            <p className="mt-1">
              Genetic information can give you information about your inherited enzyme function, but medications can inhibit or induce those enzymes, shifting actual phenotype. For example, a CYP2D6 "Normal Metabolizer" taking fluoxetine (a strong CYP2D6 inhibitor) effectively becomes a
              Poor Metabolizer for other CYP2D6 substrates. In a study of 15,000 psychiatric patients, 42% had CYP2D6 phenoconversion from drug interactions.{" "}
              [<a href="https://www.nature.com/articles/s41380-024-02588-4" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">Bousman et al. 2024</a>]{" "}
              No genetic test — including clinical-grade tests — accounts for this.
            </p>
            <p className="font-semibold text-foreground mt-4">Pharmacogenomic prediction is a contintually improving field</p>
            <p className="mt-1">
              In pharmacogenomics, the "star alleles" that define pharmacogenomic haplotypes are defined using a fixed set of genomic positions. It is worth bearing in mind that panel-based calling has limitations -- variants that haven&apos;t been cataloged yet aren't considered. In 2018 researchers sequenced complete CYP2C genes and they discovered novel haplotypes not in any standard panel, leading to phenotype reassignment in ~20% of subjects.{" "}[<a href="https://pubmed.ncbi.nlm.nih.gov/29352760/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">Botton et al. 2018</a>]{" "} The limitations of panel-based calling are present in all current consumer pharmacogenomic tests (eg from 23andMe, Color, Nebula, Invitae). As pharmacogenomic variant databases grow and panel sizes increase, the accuracy of pharmacogenetic testing will improve.
            </p>
            <p className="font-semibold text-foreground mt-4">Data sources</p>
            <p className="mt-1">
              Star allele definitions and clinical function assignments were sourced from the scientific literature and from{" "}
              <a href="https://cpicpgx.org/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">CPIC</a> and{" "}
              <a href="https://www.knmp.nl/dossiers/pharmacogenetics" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">DPWG</a> guidelines.
            </p>
          </div>

          {/* Results table */}
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
                {results.map((r) => {
                  const isExpanded = expandedGene === r.gene;
                  const rowStyle = phenotypeStyle(r.phenotype);

                  return (
                    <tr key={r.gene} className="border-b border-border last:border-0">
                      <td colSpan={4} className="p-0">
                        {/* Clickable row */}
                        <button
                          onClick={() => setExpandedGene(isExpanded ? null : r.gene)}
                          className={`w-full text-left grid grid-cols-[1fr_1.5fr_1fr_0.75fr] items-center px-4 py-3 hover:bg-gray-50 transition-colors ${rowStyle}`}
                        >
                          <span className="font-medium">{r.gene}</span>
                          <span>{r.phenotype || "—"}</span>
                          <span className="font-mono text-xs">{r.diplotype || "—"}</span>
                          <span className={`text-center font-mono text-xs font-semibold ${variantCoverageColor(r.n_variants_tested, r.n_variants_total)}`}>
                            {r.n_variants_tested}/{r.n_variants_total}
                          </span>
                        </button>

                        {/* Expanded details */}
                        {isExpanded && (
                          <div className="px-4 pb-4 pt-1 bg-surface/50 border-t border-border/50">
                            {r.gene_description && (
                              <p className="text-sm text-muted mb-2">{r.gene_description}</p>
                            )}
                            {r.clinical_note && (
                              <p className="text-sm mb-2">{r.clinical_note}</p>
                            )}
                            {r.gene === "CYP2B6" && (
                              <div className="text-xs bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-2">
                                <span className="font-semibold text-amber-900">Phase ambiguity warning:</span>{" "}
                                <span className="text-amber-800">
                                  CYP2B6 *6 is defined by two SNPs (rs3745274 + rs2279343). Without phasing, unphased data cannot distinguish *1/*6 (both variants on one chromosome) from *4/*9 (one variant on each chromosome), which may give a different phenotype. In a study of 1,583 individuals, 1.5% of CYP2B6 phenotype assignments were corrected after experimental phasing.{" "}
                                  [<a href="https://pubmed.ncbi.nlm.nih.gov/31594036/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline" onClick={(e) => e.stopPropagation()}>van der Lee et al. 2020</a>]
                                </span>
                              </div>
                            )}
                            {r.drugs_affected && (
                              <p className="text-sm mb-2">
                                <span className="font-medium">Drugs affected:</span>{" "}
                                <span className="text-muted">{r.drugs_affected}</span>
                              </p>
                            )}
                            {r.guidelines && (r.guidelines.cpic?.length > 0 || r.guidelines.dpwg?.length > 0) && (
                              <div className="mt-3 mb-3 space-y-2">
                                {r.guidelines.cpic?.length > 0 && (
                                  <div className="text-sm border-l-2 border-blue-400 pl-3 py-1">
                                    <span className="font-semibold text-blue-700 text-xs uppercase tracking-wide">CPIC Guideline</span>
                                    {r.guidelines.cpic.map((g, i) => (
                                      <p key={`${g.drug}-${i}`} className="mt-1 text-sm leading-relaxed">
                                        <span className="font-medium capitalize">{g.drug}:</span>{" "}
                                        <span className="text-muted">{g.recommendation}</span>
                                        {g.strength && (
                                          <span className="text-xs text-blue-600 ml-1">({g.strength})</span>
                                        )}
                                        {g.pmid && (
                                          <a
                                            href={`https://pubmed.ncbi.nlm.nih.gov/${g.pmid}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-accent text-xs ml-1 hover:underline"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            [PMID]
                                          </a>
                                        )}
                                      </p>
                                    ))}
                                  </div>
                                )}
                                {r.guidelines.dpwg?.length > 0 && (
                                  <div className="text-sm border-l-2 border-emerald-400 pl-3 py-1">
                                    <span className="font-semibold text-emerald-700 text-xs uppercase tracking-wide">DPWG Guideline</span>
                                    {r.guidelines.dpwg.map((g, i) => (
                                      <p key={`${g.drug}-${i}`} className="mt-1 text-sm leading-relaxed">
                                        <span className="font-medium capitalize">{g.drug}:</span>{" "}
                                        <span className="text-muted">{g.recommendation}</span>
                                        {g.pmid && (
                                          <a
                                            href={`https://pubmed.ncbi.nlm.nih.gov/${g.pmid}`}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            className="text-accent text-xs ml-1 hover:underline"
                                            onClick={(e) => e.stopPropagation()}
                                          >
                                            [PMID]
                                          </a>
                                        )}
                                      </p>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}
                            {r.defining_variants && Object.keys(r.defining_variants).length > 0 && (
                              <div className="text-sm mb-2">
                                <span className="font-medium">Defining variants:</span>
                                {Object.entries(r.defining_variants).map(([allele, variants]) => (
                                  <div key={allele} className="ml-2 mt-0.5">
                                    <span className="font-mono text-xs">{allele}</span>
                                    <span className="text-muted">: </span>
                                    {variants.map((v, i) => (
                                      <span key={v.rsid}>
                                        {i > 0 && <span className="text-muted"> + </span>}
                                        <Link
                                          href={`/snp/${v.rsid}`}
                                          className="text-accent hover:underline"
                                          onClick={(e) => e.stopPropagation()}
                                        >
                                          {v.rsid}
                                        </Link>
                                        <span className="text-xs text-muted ml-0.5">({v.variant_allele})</span>
                                      </span>
                                    ))}
                                  </div>
                                ))}
                              </div>
                            )}
                            <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted mt-2">
                              <span>
                                Variants tested: {r.n_variants_tested} / {r.n_variants_total}
                              </span>
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

          {/* Actions */}
          <section className="mt-8">
            <button
              onClick={handleDownloadPgxReport}
              disabled={downloading}
              className="px-5 py-2.5 text-sm font-medium border border-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloading ? "Generating PDF..." : "Download PharmGen Report (PDF)"}
            </button>
          </section>




        </>
      )}
    </div>
  );
}
