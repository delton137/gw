import type { Metadata } from "next";
import Link from "next/link";
import { API_URL } from "@/lib/api";
import UserGeneVariants from "./UserGeneVariants";

interface ClinVarStats {
  total_variants: number | null;
  pathogenic_count: number | null;
  uncertain_count: number | null;
  conflicting_count: number | null;
  total_submissions: number | null;
}

interface GeneSnp {
  rsid: string;
  chrom: string | null;
  position: number | null;
  ref_allele: string | null;
  alt_allele: string | null;
  functional_class: string | null;
  clinvar_significance: string | null;
  maf_global: number | null;
}

interface GeneTrait {
  trait: string;
  snp_count: number;
}

interface GeneData {
  symbol: string;
  name: string | null;
  summary: string | null;
  ncbi_gene_id: number | null;
  omim_number: string | null;
  clinvar_stats: ClinVarStats;
  is_pharmacogene: boolean;
  in_carrier_panel: boolean;
  traits: GeneTrait[];
  snps: {
    total: number;
    offset: number;
    items: GeneSnp[];
  };
}

const CLINVAR_SIG_COLORS: Record<string, { bg: string; text: string }> = {
  pathogenic: { bg: "bg-red-100", text: "text-red-800" },
  likely_pathogenic: { bg: "bg-red-50", text: "text-red-700" },
  risk_factor: { bg: "bg-amber-100", text: "text-amber-800" },
  association: { bg: "bg-amber-50", text: "text-amber-700" },
  drug_response: { bg: "bg-blue-50", text: "text-blue-700" },
  uncertain_significance: { bg: "bg-gray-100", text: "text-gray-600" },
  likely_benign: { bg: "bg-green-50", text: "text-green-700" },
  benign: { bg: "bg-green-100", text: "text-green-800" },
};

async function getGeneData(symbol: string): Promise<GeneData | null> {
  try {
    const res = await fetch(`${API_URL}/api/v1/gene/${encodeURIComponent(symbol)}?snp_limit=100`, {
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
  params: Promise<{ symbol: string }>;
}): Promise<Metadata> {
  const { symbol } = await params;
  const data = await getGeneData(symbol);
  const name = data?.name ? ` — ${data.name}` : "";
  const pathCount = data?.clinvar_stats?.pathogenic_count;
  const totalCount = data?.clinvar_stats?.total_variants;

  return {
    title: `${symbol.toUpperCase()}${name} — genewizard.net`,
    description: pathCount
      ? `${symbol.toUpperCase()} gene${name}. ${pathCount} pathogenic variants out of ${totalCount} total ClinVar variants. View all variants, disease associations, and external references.`
      : `View genetic variants and disease associations for the ${symbol.toUpperCase()} gene on genewizard.net.`,
  };
}

function StatCard({ label, value, color }: { label: string; value: number | null; color?: string }) {
  if (value == null) return null;
  return (
    <div className="text-center">
      <div className={`text-2xl font-semibold font-mono ${color || ""}`}>
        {value.toLocaleString()}
      </div>
      <div className="text-xs text-muted mt-0.5">{label}</div>
    </div>
  );
}

export default async function GenePage({
  params,
}: {
  params: Promise<{ symbol: string }>;
}) {
  const { symbol } = await params;
  const data = await getGeneData(symbol);

  if (!data) {
    return (
      <div className="mx-auto max-w-3xl px-6 pt-8 pb-16">
        <h1 className="font-serif text-3xl font-semibold mb-4">{symbol.toUpperCase()}</h1>
        <p className="text-muted mb-4">
          Gene not found in our database. It may not yet have ClinVar annotations.
        </p>
        <div className="flex gap-4">
          <a
            href={`https://www.ncbi.nlm.nih.gov/gene/?term=${symbol}`}
            target="_blank"
            rel="noopener noreferrer"
            className="text-accent hover:underline text-sm"
          >
            Search NCBI Gene &rarr;
          </a>
          <Link href="/gene" className="text-accent hover:underline text-sm">
            Browse genes
          </Link>
        </div>
      </div>
    );
  }

  const { clinvar_stats } = data;

  // External links
  const links: { label: string; url: string }[] = [
    {
      label: "Wikipedia",
      url: `https://en.wikipedia.org/wiki/${data.symbol}`,
    },
    {
      label: "NCBI Gene",
      url: data.ncbi_gene_id
        ? `https://www.ncbi.nlm.nih.gov/gene/${data.ncbi_gene_id}`
        : `https://www.ncbi.nlm.nih.gov/gene/?term=${data.symbol}`,
    },
    ...(data.omim_number
      ? [{ label: "OMIM", url: `https://omim.org/entry/${data.omim_number}` }]
      : []),
    {
      label: "GeneCards",
      url: `https://www.genecards.org/cgi-bin/carddisp.pl?gene=${data.symbol}`,
    },
    {
      label: "UniProt",
      url: `https://www.uniprot.org/uniprotkb?query=gene:${data.symbol}+AND+organism_id:9606`,
    },
    {
      label: "ClinVar",
      url: `https://www.ncbi.nlm.nih.gov/clinvar/?term=${data.symbol}%5Bgene%5D`,
    },
    {
      label: "Google Scholar",
      url: `https://scholar.google.com/scholar?q=${data.symbol}+gene&as_subj=bio`,
    },
  ];

  return (
    <>
      {/* JSON-LD */}
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{
          __html: JSON.stringify({
            "@context": "https://schema.org",
            "@type": "MedicalEntity",
            name: data.symbol,
            alternateName: data.name,
            description: data.summary || `${data.symbol} gene — ${data.name || "human gene"}`,
            code: {
              "@type": "MedicalCode",
              codeValue: data.symbol,
              codingSystem: "HGNC",
            },
          }).replace(/</g, "\\u003c"),
        }}
      />

      <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
        {/* Header */}
        <div className="mb-8">
          <h1 className="font-serif text-3xl font-semibold">
            {data.symbol}
          </h1>
          {data.name && (
            <p className="text-muted text-lg mt-1">{data.name}</p>
          )}

          {/* Badges */}
          <div className="flex gap-2 mt-3 flex-wrap">
            {data.is_pharmacogene && (
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-violet-100 text-violet-800">
                Pharmacogene
              </span>
            )}
            {data.in_carrier_panel && (
              <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-amber-100 text-amber-800">
                Carrier Screening
              </span>
            )}
            {data.omim_number && (
              <a
                href={`https://omim.org/entry/${data.omim_number}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-blue-50 text-blue-700 hover:underline"
              >
                OMIM {data.omim_number}
              </a>
            )}
          </div>
        </div>

        <div className="flex flex-col md:flex-row gap-8">
          {/* Sidebar */}
          <aside className="border border-border bg-surface/50 p-4 text-sm md:w-[280px] md:shrink-0">
            {/* ClinVar Stats */}
            <h2 className="font-serif text-base font-semibold mb-3">ClinVar Summary</h2>
            <ul className="space-y-1 text-sm mb-5">
              <li className="flex justify-between"><span className="text-muted">Total Variants</span><span className="font-medium">{clinvar_stats.total_variants?.toLocaleString() ?? "—"}</span></li>
              <li className="flex justify-between"><span className="text-muted">Pathogenic</span><span className="font-medium">{clinvar_stats.pathogenic_count?.toLocaleString() ?? "—"}</span></li>
              <li className="flex justify-between"><span className="text-muted">Uncertain</span><span className="font-medium">{clinvar_stats.uncertain_count?.toLocaleString() ?? "—"}</span></li>
              <li className="flex justify-between"><span className="text-muted">Conflicting</span><span className="font-medium">{clinvar_stats.conflicting_count?.toLocaleString() ?? "—"}</span></li>
            </ul>

            {clinvar_stats.total_submissions != null && (
              <p className="text-xs text-muted mb-5">
                {clinvar_stats.total_submissions.toLocaleString()} total ClinVar submissions
              </p>
            )}

            {/* Trait Associations */}
            {data.traits.length > 0 && (
              <div className="mb-5">
                <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
                  Associated Traits
                </h3>
                <ul className="space-y-1">
                  {data.traits.map((t) => (
                    <li key={t.trait} className="flex justify-between text-xs">
                      <span className="truncate mr-2" title={t.trait}>{t.trait}</span>
                      <span className="text-muted shrink-0">{t.snp_count} SNP{t.snp_count !== 1 ? "s" : ""}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* External Links */}
            <h3 className="text-xs uppercase tracking-wide text-muted mb-2">External Resources</h3>
            <ul className="space-y-1">
              {links.map((link) => (
                <li key={link.label}>
                  <a
                    href={link.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-accent hover:underline inline-flex items-center gap-1"
                  >
                    {link.label}
                    <svg className="w-3 h-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                      <path strokeLinecap="round" strokeLinejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                </li>
              ))}
            </ul>
          </aside>

          {/* Main content */}
          <div className="min-w-0 flex-1">
            {/* Gene Summary */}
            {data.summary && (
              <section className="mb-10">
                <h2 className="font-serif text-xl font-semibold mb-3">Summary</h2>
                <p className="text-sm leading-relaxed text-secondary">{data.summary}</p>
              </section>
            )}

            {/* User's variants (client component — renders only for authenticated users) */}
            <UserGeneVariants symbol={data.symbol} />

            {/* SNP Table */}
            <section className="mb-10">
              <h2 className="font-serif text-xl font-semibold mb-3">
                Variants
                <span className="text-muted text-sm font-normal ml-2">
                  {data.snps.total.toLocaleString()} total
                </span>
              </h2>

              {data.snps.items.length > 0 ? (
                <div className="border border-border rounded-lg overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-surface text-muted">
                      <tr>
                        <th className="text-left px-3 py-2 font-medium">rsid</th>
                        <th className="text-left px-3 py-2 font-medium">Position</th>
                        <th className="text-left px-3 py-2 font-medium">Alleles</th>
                        <th className="text-left px-3 py-2 font-medium">Class</th>
                        <th className="text-left px-3 py-2 font-medium">ClinVar</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-border">
                      {data.snps.items.map((snp) => {
                        const sig = snp.clinvar_significance;
                        const sigStyle = sig ? CLINVAR_SIG_COLORS[sig] : null;
                        return (
                          <tr key={snp.rsid} className="hover:bg-surface/50 transition-colors">
                            <td className="px-3 py-2">
                              <Link href={`/snp/${snp.rsid}`} className="text-accent hover:underline font-mono text-xs">
                                {snp.rsid}
                              </Link>
                            </td>
                            <td className="px-3 py-2 font-mono text-xs text-muted">
                              {snp.chrom && snp.position != null
                                ? `${snp.chrom}:${snp.position.toLocaleString()}`
                                : "\u2014"}
                            </td>
                            <td className="px-3 py-2 font-mono text-xs text-muted">
                              {snp.ref_allele && snp.alt_allele
                                ? `${snp.ref_allele}/${snp.alt_allele}`
                                : "\u2014"}
                            </td>
                            <td className="px-3 py-2 text-xs text-muted capitalize">
                              {snp.functional_class?.replace(/_/g, " ") || "\u2014"}
                            </td>
                            <td className="px-3 py-2">
                              {sig && sigStyle ? (
                                <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium ${sigStyle.bg} ${sigStyle.text}`}>
                                  {sig.replace(/_/g, " ")}
                                </span>
                              ) : sig ? (
                                <span className="text-xs text-muted capitalize">{sig.replace(/_/g, " ")}</span>
                              ) : (
                                <span className="text-xs text-muted">&mdash;</span>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-sm text-muted">No variants found for this gene.</p>
              )}

              {data.snps.total > data.snps.items.length && (
                <p className="text-xs text-muted mt-2">
                  Showing {data.snps.items.length} of {data.snps.total.toLocaleString()} variants.
                  Use the{" "}
                  <Link href={`/snp?gene=${data.symbol}`} className="text-accent hover:underline">
                    SNP search
                  </Link>{" "}
                  for the full list.
                </p>
              )}
            </section>

            {/* Attribution */}
            <p className="text-xs text-muted border-t border-border pt-4">
              Gene information from{" "}
              <a href="https://www.ncbi.nlm.nih.gov/gene/" target="_blank" rel="noopener noreferrer" className="hover:underline">NCBI Gene</a>.
              Variant classifications from{" "}
              <a href="https://www.ncbi.nlm.nih.gov/clinvar/" target="_blank" rel="noopener noreferrer" className="hover:underline">ClinVar</a>.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
