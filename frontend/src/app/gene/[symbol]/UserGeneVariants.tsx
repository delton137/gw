"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";

interface GeneVariant {
  rsid: string | null;
  chrom: string | null;
  position: number | null;
  user_genotype: string;
}

interface TraitHit {
  rsid: string;
  user_genotype: string;
  trait: string;
  effect_description: string | null;
  risk_level: string;
  evidence_level: string;
  risk_allele: string | null;
  effect_summary: string | null;
}

interface ClinVarHit {
  rsid: string;
  user_genotype: string;
  clinvar_significance: string;
  clinvar_conditions: string | null;
  functional_class: string | null;
}

interface PgxResult {
  gene: string;
  diplotype: string;
  phenotype: string | null;
  activity_score: number | null;
  confidence: string | null;
  drugs_affected: string[] | null;
  clinical_note: string | null;
  variant_genotypes: Record<string, string> | null;
  gene_description: string | null;
}

interface CarrierResult {
  status: string;
  variants?: Array<{ rsid: string; genotype: string; expected: string }>;
}

interface GeneCoverage {
  total_variants_tested: number;
  non_reference_count: number;
}

interface UserGeneData {
  gene: string;
  analysis_id: string;
  has_data: boolean;
  user_genotypes: Record<string, string>;
  all_variants: GeneVariant[];
  gene_coverage: GeneCoverage | null;
  trait_hits: TraitHit[];
  clinvar_hits: ClinVarHit[];
  pgx: PgxResult | null;
  carrier: CarrierResult | null;
}

const CLINVAR_SIG_COLORS: Record<string, string> = {
  pathogenic: "bg-red-100 text-red-800",
  likely_pathogenic: "bg-red-50 text-red-700",
  risk_factor: "bg-amber-100 text-amber-800",
  drug_response: "bg-blue-50 text-blue-700",
  uncertain_significance: "bg-gray-100 text-gray-600",
  likely_benign: "bg-green-50 text-green-700",
  benign: "bg-green-100 text-green-800",
};

function riskColor(level: string): string {
  switch (level) {
    case "increased": return "text-red-700";
    case "moderate": return "text-amber-700";
    default: return "text-muted";
  }
}

const DEFAULT_VARIANT_LIMIT = 20;

export default function UserGeneVariants({ symbol }: { symbol: string }) {
  const { userId, getToken } = useAuth();
  const [data, setData] = useState<UserGeneData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(false);
  const [showAllVariants, setShowAllVariants] = useState(false);

  useEffect(() => {
    if (!userId) return;

    let cancelled = false;
    async function load() {
      setLoading(true);
      try {
        const token = await getToken();
        const result = await apiFetch<UserGeneData>(
          `/api/v1/results/gene/${userId}/${encodeURIComponent(symbol)}`,
          {},
          token,
        );
        if (!cancelled) setData(result);
      } catch {
        if (!cancelled) setError(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [userId, getToken, symbol]);

  if (!userId) return null;

  if (loading) {
    return (
      <div className="border border-border rounded-lg p-4 mb-8 animate-pulse">
        <div className="h-4 bg-surface rounded w-48" />
      </div>
    );
  }

  if (error || !data) return null;

  if (!data.has_data) {
    return (
      <div className="border border-dashed border-border rounded-lg p-4 mb-8 text-sm text-muted">
        No variants from your genetic data match this gene.{" "}
        <Link href="/upload" className="text-accent hover:underline">
          Upload a new file
        </Link>{" "}
        to analyze more variants.
      </div>
    );
  }

  const hasAllVariants = data.all_variants.length > 0;
  const displayVariants = showAllVariants
    ? data.all_variants
    : data.all_variants.slice(0, DEFAULT_VARIANT_LIMIT);
  const hiddenCount = data.all_variants.length - DEFAULT_VARIANT_LIMIT;

  return (
    <section className="border border-accent/20 bg-accent/[0.03] rounded-lg p-5 mb-8">
      <h2 className="font-serif text-lg font-semibold mb-1">
        Your Variants
      </h2>

      {/* Coverage summary */}
      {data.gene_coverage ? (
        <p className="text-xs text-muted mb-4">
          Your file covers {data.gene_coverage.total_variants_tested.toLocaleString()} position{data.gene_coverage.total_variants_tested !== 1 ? "s" : ""} in this gene
          {data.gene_coverage.non_reference_count > 0 && (
            <> — <span className="font-medium text-secondary">{data.gene_coverage.non_reference_count} non-reference</span></>
          )}
        </p>
      ) : (
        <p className="text-xs text-muted mb-4">
          {Object.keys(data.user_genotypes).length} variant{Object.keys(data.user_genotypes).length !== 1 ? "s" : ""} detected in this gene.
        </p>
      )}

      {/* All variants table */}
      {hasAllVariants && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
            Non-Reference Variants ({data.all_variants.length})
          </h3>
          <div className="border border-border rounded-lg overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  <th className="text-left px-3 py-1.5 font-medium text-xs">rsid</th>
                  <th className="text-left px-3 py-1.5 font-medium text-xs">Position</th>
                  <th className="text-left px-3 py-1.5 font-medium text-xs">Genotype</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {displayVariants.map((v, i) => (
                  <tr key={i} className="hover:bg-surface/50 transition-colors">
                    <td className="px-3 py-1.5">
                      {v.rsid ? (
                        <Link href={`/snp/${v.rsid}`} className="font-mono text-xs text-accent hover:underline">
                          {v.rsid}
                        </Link>
                      ) : (
                        <span className="font-mono text-xs text-muted">&mdash;</span>
                      )}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs text-muted">
                      {v.chrom && v.position != null
                        ? `${v.chrom}:${v.position.toLocaleString()}`
                        : "\u2014"}
                    </td>
                    <td className="px-3 py-1.5 font-mono text-xs font-semibold">
                      {v.user_genotype}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!showAllVariants && hiddenCount > 0 && (
            <button
              onClick={() => setShowAllVariants(true)}
              className="text-xs text-accent hover:underline mt-1.5"
            >
              Show {hiddenCount} more variant{hiddenCount !== 1 ? "s" : ""}
            </button>
          )}
          {showAllVariants && data.all_variants.length > DEFAULT_VARIANT_LIMIT && (
            <button
              onClick={() => setShowAllVariants(false)}
              className="text-xs text-accent hover:underline mt-1.5"
            >
              Show fewer
            </button>
          )}
        </div>
      )}

      {/* Genotype chips (fallback when no all_variants but has genotype map) */}
      {!hasAllVariants && Object.keys(data.user_genotypes).length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">Genotypes</h3>
          <div className="flex flex-wrap gap-2">
            {Object.entries(data.user_genotypes).map(([rsid, gt]) => (
              <Link
                key={rsid}
                href={`/snp/${rsid}`}
                className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-surface border border-border text-xs hover:border-accent/40 transition-colors"
              >
                <span className="font-mono text-accent">{rsid}</span>
                <span className="font-mono font-semibold">{gt}</span>
              </Link>
            ))}
          </div>
        </div>
      )}

      {/* Trait hits */}
      {data.trait_hits.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
            Trait Associations ({data.trait_hits.length})
          </h3>
          <div className="space-y-1.5">
            {data.trait_hits.map((hit, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <Link href={`/snp/${hit.rsid}`} className="font-mono text-xs text-accent hover:underline shrink-0">
                  {hit.rsid}
                </Link>
                <span className="font-mono text-xs font-medium shrink-0">{hit.user_genotype}</span>
                <span className="text-secondary flex-1">
                  {hit.effect_summary || hit.effect_description || hit.trait}
                </span>
                <span className={`text-xs capitalize shrink-0 ${riskColor(hit.risk_level)}`}>
                  {hit.risk_level}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ClinVar hits */}
      {data.clinvar_hits.length > 0 && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
            ClinVar Variants ({data.clinvar_hits.length})
          </h3>
          <div className="space-y-1.5">
            {data.clinvar_hits.map((hit, i) => (
              <div key={i} className="flex items-center gap-2 text-sm">
                <Link href={`/snp/${hit.rsid}`} className="font-mono text-xs text-accent hover:underline shrink-0">
                  {hit.rsid}
                </Link>
                <span className="font-mono text-xs font-medium shrink-0">{hit.user_genotype}</span>
                {hit.clinvar_significance && (
                  <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium ${CLINVAR_SIG_COLORS[hit.clinvar_significance] || "bg-gray-100 text-gray-600"}`}>
                    {hit.clinvar_significance.replace(/_/g, " ")}
                  </span>
                )}
                {hit.clinvar_conditions && (
                  <span className="text-xs text-muted truncate" title={hit.clinvar_conditions}>
                    {hit.clinvar_conditions}
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* PGx result */}
      {data.pgx && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">Pharmacogenomics</h3>
          <div className="bg-surface border border-border rounded p-3 text-sm">
            <div className="flex items-center gap-3 mb-1">
              <span className="font-medium">{data.pgx.gene}</span>
              <span className="font-mono text-xs">{data.pgx.diplotype}</span>
              {data.pgx.phenotype && (
                <span className="text-xs px-1.5 py-0.5 rounded bg-violet-50 text-violet-700">
                  {data.pgx.phenotype}
                </span>
              )}
            </div>
            {data.pgx.drugs_affected && data.pgx.drugs_affected.length > 0 && (
              <p className="text-xs text-muted">
                Drugs affected: {data.pgx.drugs_affected.join(", ")}
              </p>
            )}
            <Link href={`/pgx/${data.pgx.gene}`} className="text-xs text-accent hover:underline mt-1 inline-block">
              View full PGx details &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Carrier status */}
      {data.carrier && (
        <div className="mb-4">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">Carrier Screening</h3>
          <div className="bg-surface border border-border rounded p-3 text-sm">
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
              data.carrier.status === "not_detected"
                ? "bg-green-50 text-green-700"
                : data.carrier.status === "carrier"
                  ? "bg-amber-100 text-amber-800"
                  : "bg-red-100 text-red-800"
            }`}>
              {data.carrier.status.replace(/_/g, " ")}
            </span>
            <Link href="/carrier" className="text-xs text-accent hover:underline ml-3">
              View carrier details &rarr;
            </Link>
          </div>
        </div>
      )}

      {/* Link to full results */}
      <div className="pt-2 border-t border-border/50 flex gap-4">
        <Link href="/dashboard" className="text-xs text-accent hover:underline">
          View full dashboard &rarr;
        </Link>
        <Link href="/mysnps" className="text-xs text-accent hover:underline">
          All your SNPs &rarr;
        </Link>
      </div>
    </section>
  );
}
