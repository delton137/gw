"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { CarrierGeneResult, CarrierStatusResult } from "@/lib/types";

interface CarrierStatusResponse {
  analysis_id: string;
  result: CarrierStatusResult | null;
}

const NOT_SCREENABLE = [
  {
    condition: "Spinal Muscular Atrophy",
    gene: "SMN1",
    reason:
      "Caused by copy number variation (SMN1 exon 7 deletion), not point mutations. SMN1 and SMN2 are 99.9% identical — SNP probes cannot distinguish them. Requires MLPA, qPCR, or dedicated copy number assays.",
    carrier_frequency: "1 in 50 (pan-ethnic)",
    pmids: [21301861, 32066871],
  },
  {
    condition: "Fragile X Syndrome",
    gene: "FMR1",
    reason:
      "Caused by CGG trinucleotide repeat expansion, not point mutations. SNP arrays cannot measure repeat length or methylation status. Requires triplet-repeat primed PCR or Southern blot.",
    carrier_frequency: "1 in 250 females (premutation)",
    pmids: [20301558, 34285390],
  },
];

function statusBadge(status: string) {
  switch (status) {
    case "carrier":
      return { bg: "bg-amber-50 text-amber-800", label: "Carrier" };
    case "likely_affected":
      return { bg: "bg-red-50 text-red-800", label: "Likely Affected" };
    case "potential_compound_het":
      return {
        bg: "bg-red-50 text-red-800",
        label: "Potential Compound Het",
      };
    case "not_detected":
      return { bg: "bg-emerald-50 text-emerald-700", label: "Not Detected" };
    default:
      return { bg: "bg-gray-50 text-gray-600", label: status };
  }
}

function severityLabel(severity: string) {
  switch (severity) {
    case "fatal":
      return { text: "Fatal if untreated", color: "text-red-700" };
    case "severe":
      return { text: "Severe", color: "text-red-600" };
    case "treatable":
      return { text: "Treatable", color: "text-emerald-700" };
    case "variable":
      return { text: "Variable severity", color: "text-amber-700" };
    case "non_lethal":
      return { text: "Non-lethal", color: "text-blue-700" };
    default:
      return { text: severity, color: "text-gray-600" };
  }
}

function inheritanceLabel(inheritance: string) {
  return inheritance.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function variantCoverageColor(tested: number, total: number): string {
  if (total === 0) return "text-red-600";
  const pct = tested / total;
  if (pct >= 1.0) return "text-green-700";
  if (pct >= 0.5) return "text-yellow-600";
  if (pct >= 0.25) return "text-orange-600";
  return "text-red-600";
}

function PmidLink({ pmid }: { pmid: number }) {
  return (
    <a
      href={`https://pubmed.ncbi.nlm.nih.gov/${pmid}`}
      target="_blank"
      rel="noopener noreferrer"
      className="text-accent hover:underline text-xs"
    >
      PMID:{pmid}
    </a>
  );
}

export default function CarrierPage() {
  const { userId, getToken } = useAuth();
  const [data, setData] = useState<CarrierStatusResponse["result"]>(null);
  const [loading, setLoading] = useState(true);
  const [expandedGene, setExpandedGene] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      if (!userId) return;
      try {
        const token = await getToken();
        const resp = await apiFetch<CarrierStatusResponse>(
          `/api/v1/results/carrier-status/${userId}`,
          {},
          token,
        );
        setData(resp.result);
      } catch {
        // API unavailable or no results
      } finally {
        setLoading(false);
      }
    }
    if (userId) load();
  }, [userId, getToken]);

  if (!userId) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">
          Please sign in to view your carrier screening results.
        </p>
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

  if (!data) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <div className="flex items-start justify-between mb-2">
          <h1 className="font-serif text-3xl font-semibold">
            Carrier Screening
          </h1>
          <Link
            href="/dashboard"
            className="text-sm text-accent hover:underline mt-2"
          >
            &larr; Dashboard
          </Link>
        </div>
        <div className="border border-border p-12 text-center mt-8">
          <p className="text-muted mb-4">No carrier screening results yet.</p>
          <Link href="/upload" className="text-accent hover:underline text-sm">
            Upload your genotype file to get started
          </Link>
        </div>
      </div>
    );
  }

  const genes = Object.values(data.results_json);
  const detectedGenes = genes.filter((g) => g.status !== "not_detected");
  const affectedGenes = genes.filter(
    (g) =>
      g.status === "likely_affected" || g.status === "potential_compound_het",
  );

  // Sort: affected first, then carriers, then not detected
  const sortedGenes = [...genes].sort((a, b) => {
    const order: Record<string, number> = {
      likely_affected: 0,
      potential_compound_het: 1,
      carrier: 2,
      not_detected: 3,
    };
    return (order[a.status] ?? 4) - (order[b.status] ?? 4);
  });

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <div className="flex items-start justify-between mb-2">
        <h1 className="font-serif text-3xl font-semibold">
          Carrier Screening
          <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
            Experimental
          </span>
        </h1>
        <Link
          href="/dashboard"
          className="text-sm text-accent hover:underline mt-2"
        >
          &larr; Dashboard
        </Link>
      </div>

      <div className="text-xs text-muted mb-8 mt-4 leading-relaxed">
        <p className="font-semibold text-foreground">This is not a clinical-grade genetic test</p>
        <p className="mt-1">
          Results are derived from consumer direct-to-consumer (DTC) SNP array data,
          which has limitations in variant detection accuracy, coverage, and
          validation.
        </p>
        <p className="font-semibold text-foreground mt-4">Not comprehensive — false negatives possible!</p>
        <p className="mt-1">
          Only a small subset of known pathogenic variants is tested per gene. Many disease-causing
          mutations — including large deletions, insertions, repeat
          expansions, and rare point mutations — are not detectable.
        </p>
        <p className="font-semibold text-foreground mt-4">Ancestry-dependent sensitivity</p>
        <p className="mt-1">
          Detection rates vary significantly by ancestral background. Carrier frequencies and
          variant coverage are highest for populations of European descent and
          may be substantially lower for other ancestries.
        </p>
        <p className="font-semibold text-foreground mt-4">Phase ambiguity</p>
        <p className="mt-1">
          When two different pathogenic variants are detected in the same gene, SNP array data cannot
          determine whether they are on the same chromosome (cis) or different
          chromosomes (trans). Only trans configuration (compound
          heterozygosity) causes disease.
        </p>
        <p className="font-semibold text-foreground mt-4">Confirm with a genetic counselor</p>
        <p className="mt-1">
          Any positive result should be confirmed with clinical-grade testing before making
          medical or reproductive decisions. Genetic counseling is recommended
          for interpretation of carrier screening results.
        </p>
        <p className="font-semibold text-foreground mt-4">Does not replace standard preconception carrier screening</p>
        <p className="mt-1">
          The ACMG recommends expanded carrier screening panels covering
          113+ genes for all individuals regardless of ethnicity (
          <PmidLink pmid={34285390} />
          ). This SNP-based screen is not a substitute for clinical carrier
          testing.
        </p>
      </div>

      {/* Summary banner */}
      <div
        className={`border p-5 mb-8 ${
          affectedGenes.length > 0
            ? "border-red-200 bg-red-50/50"
            : detectedGenes.length > 0
              ? "border-amber-200 bg-amber-50/50"
              : "border-emerald-200 bg-emerald-50/50"
        }`}
      >
        <p className="text-lg font-serif font-semibold mb-1">
          {detectedGenes.length === 0
            ? `No carrier variants detected across ${data.n_genes_screened} genes screened`
            : `You are a carrier for ${detectedGenes.length} of ${data.n_genes_screened} screened conditions`}
        </p>
        <p className="text-sm text-muted">
          {detectedGenes.length === 0
            ? "A negative result does not eliminate carrier risk — this panel tests only a subset of known variants per gene."
            : "Being a carrier typically means you do not have the condition but can pass the variant to children. See detailed results below."}
        </p>
        {affectedGenes.length > 0 && (
          <p className="text-sm text-red-700 font-medium mt-2">
            {affectedGenes.length} gene
            {affectedGenes.length !== 1 ? "s" : ""} flagged for possible
            affected status — clinical follow-up recommended.
          </p>
        )}
      </div>

      {/* Gene results table — all genes in one table like PGx */}
      <section className="mb-8">
        <h2 className="font-serif text-xl font-semibold mb-3">
          Screening Results
        </h2>
        <p className="text-xs text-muted mb-3">
          {data.n_genes_screened} genes screened for pathogenic variants associated with autosomal recessive and co-dominant conditions.
        </p>
        <div className="border border-border overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-left">
                <th className="px-4 py-2 font-medium text-muted">Gene</th>
                <th className="px-4 py-2 font-medium text-muted">Condition</th>
                <th className="px-4 py-2 font-medium text-muted">Status</th>
                <th className="px-4 py-2 font-medium text-muted text-center">Variants Found</th>
              </tr>
            </thead>
            <tbody>
              {sortedGenes.map((g) => {
                const isExpanded = expandedGene === g.gene;
                const badge = statusBadge(g.status);
                const rowBg =
                  g.status === "likely_affected" || g.status === "potential_compound_het"
                    ? "bg-red-50/30"
                    : g.status === "carrier"
                      ? "bg-amber-50/30"
                      : "";

                return (
                  <tr key={g.gene} className="border-b border-border last:border-0">
                    <td colSpan={4} className="p-0">
                      <button
                        onClick={() =>
                          setExpandedGene(isExpanded ? null : g.gene)
                        }
                        className={`w-full text-left grid grid-cols-[0.8fr_1.5fr_1fr_0.75fr] items-center px-4 py-3 hover:bg-gray-50 transition-colors ${rowBg}`}
                      >
                        <span className="font-medium">{g.gene}</span>
                        <span>{g.condition}</span>
                        <span>
                          <span
                            className={`inline-block px-2 py-0.5 text-xs rounded-full ${badge.bg}`}
                          >
                            {badge.label}
                          </span>
                        </span>
                        <span className={`text-center font-mono text-xs font-semibold ${variantCoverageColor(g.variants_tested, g.total_variants_screened)}`}>
                          {g.variants_tested}/{g.total_variants_screened}
                        </span>
                      </button>

                      {/* Expanded details */}
                      {isExpanded && (
                        <GeneDetails gene={g} />
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* Conditions not screenable from SNP arrays */}
      <section className="mb-8">
        <h2 className="font-serif text-xl font-semibold mb-4">
          Conditions Not Screenable from SNP Arrays
        </h2>
        <div className="border border-border p-4">
          <p className="text-sm text-muted mb-4">
            The following common carrier screening conditions{" "}
            <strong>cannot</strong> be detected from consumer SNP array data due
            to the nature of their causative mutations.
          </p>
          <div className="space-y-4">
            {NOT_SCREENABLE.map((c) => (
              <div key={c.gene} className="border-l-2 border-gray-300 pl-3">
                <p className="font-medium text-sm">
                  {c.condition}{" "}
                  <span className="font-mono text-xs text-muted">
                    ({c.gene})
                  </span>
                </p>
                <p className="text-sm text-muted mt-0.5">{c.reason}</p>
                <div className="flex items-center gap-3 mt-1 text-xs text-muted">
                  <span>Carrier frequency: {c.carrier_frequency}</span>
                  <span className="text-muted">&middot;</span>
                  {c.pmids.map((pmid, i) => (
                    <span key={pmid}>
                      {i > 0 && <span className="mr-1">,</span>}
                      <PmidLink pmid={pmid} />
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="mb-8">
        <h2 className="font-serif text-xl font-semibold mb-4">Methodology</h2>
        <div className="border border-border p-4 text-sm text-muted leading-relaxed space-y-2">
          <p>
            <strong className="text-foreground">Panel:</strong> Carrier
            screening panel v1.0 — {data.n_genes_screened} genes,{" "}
            {genes.reduce((sum, g) => sum + g.total_variants_screened, 0)}{" "}
            variants.
          </p>
          <p>
            <strong className="text-foreground">Approach:</strong> User genotype
            data is matched against a curated panel of pathogenic variants for
            autosomal recessive and co-dominant conditions. Carrier status is
            determined by counting pathogenic alleles per gene.
          </p>
          <p>
            <strong className="text-foreground">Classification:</strong>{" "}
            &ldquo;Not detected&rdquo; = no pathogenic alleles found.
            &ldquo;Carrier&rdquo; = one pathogenic allele (heterozygous).
            &ldquo;Likely affected&rdquo; = homozygous for a pathogenic variant.
            &ldquo;Potential compound heterozygote&rdquo; = two different
            pathogenic variants in the same gene — phase cannot be determined
            from SNP arrays.
          </p>
          <p>
            <strong className="text-foreground">Data sources:</strong> Variant
            classifications from ClinVar, ACMG guidelines (
            <PmidLink pmid={34285390} />
            ), and gene-specific literature. Carrier frequencies from published
            population studies.
          </p>
          {data.computed_at && (
            <p>
              <strong className="text-foreground">Computed:</strong>{" "}
              {new Date(data.computed_at).toLocaleDateString()}
            </p>
          )}
        </div>
      </section>

      <Link
        href="/dashboard"
        className="inline-block text-sm text-accent hover:underline"
      >
        &larr; Back to dashboard
      </Link>
    </div>
  );
}

/* ----- Gene detail panel (shown when row expanded) ----- */

function GeneDetails({ gene: g }: { gene: CarrierGeneResult }) {
  const sev = severityLabel(g.severity);

  return (
    <div className="px-4 pb-5 pt-2 bg-surface/50 border-t border-border/50 space-y-4">
      {/* Clinical interpretation */}
      {g.clinical_note && (
        <div
          className={`text-sm leading-relaxed p-3 border-l-2 ${
            g.status === "likely_affected" || g.status === "potential_compound_het"
              ? "border-red-400 bg-red-50/50"
              : g.status === "carrier"
                ? "border-amber-400 bg-amber-50/50"
                : "border-gray-300 bg-gray-50/50"
          }`}
        >
          {g.clinical_note}
        </div>
      )}

      {/* Condition description */}
      {g.condition_description && (
        <div className="text-sm">
          <span className="font-medium">About this condition:</span>{" "}
          <span className="text-muted">{g.condition_description}</span>
        </div>
      )}

      {/* Severity + Inheritance */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm">
        <span>
          <span className="font-medium">Severity:</span>{" "}
          <span className={sev.color}>{sev.text}</span>
        </span>
        <span>
          <span className="font-medium">Inheritance:</span>{" "}
          <span className="text-muted">{inheritanceLabel(g.inheritance)}</span>
        </span>
      </div>

      {/* Variants detected */}
      {g.variants_detected.length > 0 && (
        <div>
          <p className="font-medium text-sm mb-2">Pathogenic variants detected:</p>
          <div className="border border-border text-xs">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-gray-50/50 text-left">
                  <th className="px-3 py-1.5 font-medium text-muted">
                    Variant
                  </th>
                  <th className="px-3 py-1.5 font-medium text-muted">rsID</th>
                  <th className="px-3 py-1.5 font-medium text-muted">
                    Your Genotype
                  </th>
                  <th className="px-3 py-1.5 font-medium text-muted">
                    Risk Allele
                  </th>
                  <th className="px-3 py-1.5 font-medium text-muted text-center">
                    Copies
                  </th>
                  <th className="px-3 py-1.5 font-medium text-muted">
                    HGVS
                  </th>
                </tr>
              </thead>
              <tbody>
                {g.variants_detected.map((v) => (
                  <tr
                    key={v.rsid}
                    className="border-b border-border last:border-0"
                  >
                    <td className="px-3 py-1.5 font-medium">{v.name}</td>
                    <td className="px-3 py-1.5">
                      <Link
                        href={`/snp/${v.rsid}`}
                        className="text-accent hover:underline font-mono"
                        onClick={(e) => e.stopPropagation()}
                      >
                        {v.rsid}
                      </Link>
                    </td>
                    <td className="px-3 py-1.5 font-mono">{v.genotype}</td>
                    <td className="px-3 py-1.5 font-mono">
                      {v.pathogenic_allele}
                    </td>
                    <td className="px-3 py-1.5 text-center font-mono">
                      <span
                        className={
                          v.pathogenic_allele_count >= 2
                            ? "text-red-700 font-bold"
                            : "text-amber-700"
                        }
                      >
                        {v.pathogenic_allele_count}
                      </span>
                    </td>
                    <td className="px-3 py-1.5 text-muted">
                      {v.hgvs_p || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* SNPs in panel — like PGx panel_snps display */}
      {g.panel_rsids && g.panel_rsids.length > 0 && (
        <div className="text-sm mb-2">
          <span className="font-medium">SNPs in panel ({g.panel_rsids.length}):</span>
          <div className="flex flex-wrap gap-x-3 gap-y-0.5 mt-1 ml-2">
            {g.panel_rsids.map((rsid) => {
              const geno = g.variant_genotypes?.[rsid];
              return (
                <span key={rsid} className="text-xs font-mono">
                  <Link
                    href={`/snp/${rsid}`}
                    className="text-accent hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    {rsid}
                  </Link>
                  {geno ? (
                    <span className="text-muted ml-1">({geno})</span>
                  ) : (
                    <span className="text-red-400 ml-1">(—)</span>
                  )}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* Carrier frequencies by population */}
      {Object.keys(g.carrier_frequencies).length > 0 && (
        <div className="text-sm">
          <span className="font-medium">Carrier frequencies:</span>
          <div className="flex flex-wrap gap-x-4 gap-y-1 mt-1 text-xs text-muted">
            {Object.entries(g.carrier_frequencies).map(([pop, freq]) => (
              <span key={pop}>
                <span className="font-medium text-foreground">{pop}:</span>{" "}
                {freq}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Treatment info */}
      {g.treatment_summary && (
        <div className="text-sm">
          <span className="font-medium">Treatment &amp; management:</span>{" "}
          <span className="text-muted">{g.treatment_summary}</span>
        </div>
      )}

      {/* Penetrance note */}
      {g.penetrance_note && (
        <div className="text-sm">
          <span className="font-medium">Penetrance:</span>{" "}
          <span className="text-muted">{g.penetrance_note}</span>
        </div>
      )}

      {/* Limitations */}
      {g.limitations && (
        <div className="text-sm border-l-2 border-gray-300 pl-3">
          <span className="font-medium">Limitations:</span>{" "}
          <span className="text-muted">{g.limitations}</span>
        </div>
      )}

      {/* References */}
      {g.key_pmids.length > 0 && (
        <div className="text-sm">
          <span className="font-medium">References:</span>{" "}
          <span className="space-x-2">
            {g.key_pmids.map((pmid) => (
              <PmidLink key={pmid} pmid={pmid} />
            ))}
          </span>
        </div>
      )}

      {/* Metadata */}
      <div className="flex flex-wrap gap-x-6 gap-y-1 text-xs text-muted pt-1 border-t border-border/50">
        <span>
          Variants tested: {g.variants_tested}/{g.total_variants_screened}
        </span>
        <span>
          Pathogenic alleles found: {g.total_pathogenic_alleles}
        </span>
      </div>
    </div>
  );
}
