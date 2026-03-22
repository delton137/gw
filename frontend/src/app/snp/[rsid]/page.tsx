import type { Metadata } from "next";
import Link from "next/link";
import SnpAssociationsTable from "@/components/SnpAssociationsTable";
import SnpInfobox, { ClinVarBadge } from "@/components/SnpInfobox";
import { API_URL } from "@/lib/api";

// Map 3-letter amino acid codes to full names
const AA_NAMES: Record<string, string> = {
  Ala: "alanine", Arg: "arginine", Asn: "asparagine", Asp: "aspartate",
  Cys: "cysteine", Gln: "glutamine", Glu: "glutamate", Gly: "glycine",
  His: "histidine", Ile: "isoleucine", Leu: "leucine", Lys: "lysine",
  Met: "methionine", Phe: "phenylalanine", Pro: "proline", Ser: "serine",
  Thr: "threonine", Trp: "tryptophan", Tyr: "tyrosine", Val: "valine",
  Ter: "stop codon",
};

function parseAminoAcidChange(hgvsProtein: string): { from: string; to: string } | null {
  // e.g. "NP_000782.2:p.Cys130Arg" → { from: "cysteine", to: "arginine" }
  const match = hgvsProtein.match(/p\.([A-Z][a-z]{2})\d+([A-Z][a-z]{2})/);
  if (!match) return null;
  const from = AA_NAMES[match[1]];
  const to = AA_NAMES[match[2]];
  if (!from || !to) return null;
  return { from, to };
}

function buildInterpretationLine(data: SnpData): string | null {
  const parts: string[] = [];
  const gene = data.gene;
  const fc = data.functional_class?.toLowerCase();

  // What the variant is
  if (gene && fc === "non_synonymous") {
    const aaChange = data.hgvs?.protein ? parseAminoAcidChange(data.hgvs.protein) : null;
    if (aaChange) {
      parts.push(`This is a variant in the ${gene} gene that changes a ${aaChange.from} to an ${aaChange.to}`);
    } else {
      parts.push(`This is a protein-altering variant in the ${gene} gene`);
    }
  } else if (gene && fc === "synonymous") {
    parts.push(`This is a synonymous variant in the ${gene} gene — it does not change the protein's amino acid sequence`);
  } else if (gene && fc) {
    const fcHuman = fc.replace(/_/g, " ");
    parts.push(`This is a ${fcHuman} variant in the ${gene} gene`);
  } else if (gene) {
    parts.push(`This variant is located in the ${gene} gene`);
  } else if (fc) {
    parts.push(`This is a ${fc.replace(/_/g, " ")} variant`);
  }


  if (parts.length === 0) return null;

  // Join: first part is a sentence start, rest are appended with commas
  let line = parts[0];
  for (let i = 1; i < parts.length; i++) {
    line += ", " + parts[i];
  }
  return line + ".";
}

interface GeneInfo {
  symbol: string;
  name: string | null;
  summary: string | null;
  omim_number: string | null;
  ncbi_gene_id: number | null;
  clinvar_total_variants: number | null;
  clinvar_pathogenic_count: number | null;
}

interface SnpData {
  rsid: string;
  chrom: string | null;
  position: number | null;
  ref_allele: string | null;
  alt_allele: string | null;
  gene: string | null;
  functional_class: string | null;
  maf_global: number | null;
  in_database: boolean;
  gene_info: GeneInfo | null;
  trait_associations: {
    id: string;
    trait: string;
    risk_allele: string;
    odds_ratio: number | null;
    beta: number | null;
    p_value: number | null;
    effect_description: string;
    evidence_level: string;
    source_pmid: string | null;
    source_title: string | null;
    trait_prevalence: number | null;
  }[];

  pathogenicity: {
    cadd_phred: number | null;
    sift: { category: string; score: number } | null;
    polyphen: { category: string; score: number } | null;
    revel_score: number | null;
  } | null;
  clinvar: {
    significance: string;
    conditions: string | null;
    review_stars: number | null;
    allele_id: number | null;
    submitter_count: number | null;
    citation_count: number | null;
  } | null;
  hgvs: {
    coding: string | null;
    protein: string | null;
  } | null;
  population_frequencies: {
    african: number | null;
    east_asian: number | null;
    european: number | null;
    south_asian: number | null;
    latino: number | null;
    finnish: number | null;
    ashkenazi_jewish: number | null;
  } | null;
}

async function getSnpData(rsid: string): Promise<SnpData | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/snp/${rsid}`, {
      next: { revalidate: 3600 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ rsid: string }>;
}): Promise<Metadata> {
  const { rsid } = await params;
  const data = await getSnpData(rsid);
  const gene = data?.gene ? ` (${data.gene})` : "";
  const traits = data?.trait_associations?.map((a) => a.trait).slice(0, 3).join(", ") || "";

  return {
    title: `${rsid}${gene} — genewizard.net`,
    description: traits
      ? `${rsid}${gene} is associated with ${traits}. View genetic variant details and trait associations.`
      : `View details for genetic variant ${rsid}${gene} including trait associations and clinical annotations.`,
  };
}

export default async function SnpPage({
  params,
}: {
  params: Promise<{ rsid: string }>;
}) {
  const { rsid } = await params;
  const data = await getSnpData(rsid);

  if (!data) {
    return (
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-16">
        <h1 className="font-serif text-3xl font-semibold mb-4">{rsid}</h1>
        <p className="text-muted mb-4">
          No data available for this variant yet. The backend API may not be running.
        </p>
        <div className="flex gap-4">
          <a
            href={`https://www.snpedia.com/index.php/Rs${rsid.slice(2)}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline text-sm"
          >
            View on SNPedia &rarr;
          </a>
          <Link href="/" className="text-accent hover:underline text-sm">
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* JSON-LD structured data */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "MedicalEntity",
            name: data.rsid,
            description: `Genetic variant ${data.rsid}${data.gene ? ` in gene ${data.gene}` : ""}${data.chrom && data.position ? ` at chromosome ${data.chrom}:${data.position}` : ""}`,
            code: {
              "@type": "MedicalCode",
              codeValue: data.rsid,
              codingSystem: "dbSNP",
            },
          }).replace(/</g, "\\u003c"),
        }}
      />

      <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
        {/* Header */}
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold">
            {data.rsid}
            {data.gene && (
              <Link href={`/gene/${data.gene}`} className="text-muted font-normal text-2xl ml-2 hover:text-accent">
                ({data.gene})
              </Link>
            )}
          </h1>
          {(() => {
            const interp = buildInterpretationLine(data);
            if (interp) {
              return <p className="text-muted mt-2 text-sm leading-relaxed">{interp}</p>;
            }
            return null;
          })()}
          {!data.in_database && (
            <p className="text-sm text-muted mt-2">
              This variant is not yet in our knowledge base. Check external resources for more information.
            </p>
          )}
        </div>

        {/* Two-column layout: infobox + main content */}
        <div className="flex flex-col md:flex-row gap-8">
          {/* Infobox sidebar */}
          <SnpInfobox
            rsid={data.rsid}
            chrom={data.chrom}
            position={data.position}
            ref_allele={data.ref_allele}
            alt_allele={data.alt_allele}
            gene={data.gene}
            gene_name={data.gene_info?.name}
            functional_class={data.functional_class}
            maf_global={data.maf_global}
            in_database={data.in_database}
            pathogenicity={data.pathogenicity}
            clinvar={data.clinvar}
            hgvs={data.hgvs}
            population_frequencies={data.population_frequencies}
          />

          {/* Main content */}
          <div className="min-w-0 flex-1">
            {/* Trait Associations */}
            {data.trait_associations.length > 0 && (
              <section className="mb-12">
                <h2 className="font-serif text-xl font-semibold mb-4">Trait Associations</h2>
                <SnpAssociationsTable associations={data.trait_associations} />
              </section>
            )}

            {/* ClinVar */}
            {data.clinvar && (
              <section className="mb-12">
                <h2 className="font-serif text-xl font-semibold mb-4">ClinVar</h2>
                <div className="border border-border p-5">
                  <ClinVarBadge significance={data.clinvar.significance} reviewStars={data.clinvar.review_stars} />
                  {(data.clinvar.submitter_count || data.clinvar.citation_count) && (
                    <div className="flex gap-3 mt-2 text-sm text-muted">
                      {data.clinvar.submitter_count != null && data.clinvar.submitter_count > 0 && (
                        <span>{data.clinvar.submitter_count} submitter{data.clinvar.submitter_count !== 1 ? "s" : ""}</span>
                      )}
                      {data.clinvar.citation_count != null && data.clinvar.citation_count > 0 && (
                        <span>{data.clinvar.citation_count} publication{data.clinvar.citation_count !== 1 ? "s" : ""}</span>
                      )}
                    </div>
                  )}
                  {data.clinvar.conditions && (
                    <p className="text-sm text-muted mt-2 leading-relaxed">{data.clinvar.conditions}</p>
                  )}
                  {data.clinvar.allele_id && (
                    <a
                      href={`https://www.ncbi.nlm.nih.gov/clinvar/?term=${data.clinvar.allele_id}[alleleid]`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent text-sm hover:underline mt-2 inline-block"
                    >
                      View on ClinVar &rarr;
                    </a>
                  )}
                </div>
              </section>
            )}


            {/* Gene summary for ClinVar-only pages without trait associations */}
            {data.gene_info?.summary && data.trait_associations.length === 0 && (
              <section className="mb-12">
                <h2 className="font-serif text-xl font-semibold mb-4">
                  About {data.gene_info.symbol}
                </h2>
                <p className="text-sm leading-relaxed text-secondary">{data.gene_info.summary}</p>
                <Link
                  href={`/gene/${data.gene_info.symbol}`}
                  className="text-accent text-sm hover:underline mt-2 inline-block"
                >
                  View all {data.gene_info.symbol} variants &rarr;
                </Link>
              </section>
            )}

            {/* Empty state */}
            {data.in_database && data.trait_associations.length === 0 && !data.gene_info?.summary && (
              <p className="text-sm text-muted">
                This variant is in our database but has no known associations or PRS memberships yet.
              </p>
            )}

            {/* Attribution */}
            {data.in_database && (
              <p className="text-xs text-muted mt-8 border-t border-border pt-4">
                Gene information from{" "}
                <a href="https://www.ncbi.nlm.nih.gov/gene/" target="_blank" rel="noopener noreferrer" className="hover:underline">NCBI Gene</a>.
                Variant classifications from{" "}
                <a href="https://www.ncbi.nlm.nih.gov/clinvar/" target="_blank" rel="noopener noreferrer" className="hover:underline">ClinVar</a>.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
