"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch, API_URL } from "@/lib/api";
import { GENE_CATEGORIES, CATEGORY_ORDER } from "@/lib/geneCategories";

interface SnpResult {
  rsid: string;
  chrom: string | null;
  position: number | null;
  gene: string | null;
  ref_allele: string | null;
  alt_allele: string | null;
}

interface FeaturedSnp {
  rsid: string;
  gene: string | null;
  chrom: string | null;
  traits: {
    trait: string;
    summary: string;
    evidence_level: string;
  }[];
}

const CHROMOSOMES = [
  "1","2","3","4","5","6","7","8","9","10","11","12",
  "13","14","15","16","17","18","19","20","21","22","X","Y","MT",
];

export default function SnpBrowsePage() {
  const router = useRouter();
  const { userId, getToken } = useAuth();
  const [rsidLookup, setRsidLookup] = useState("");
  const [gene, setGene] = useState("");
  const [chrom, setChrom] = useState("");
  const [results, setResults] = useState<SnpResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [offset, setOffset] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [userVariantCount, setUserVariantCount] = useState<number | null>(null);
  const [snpediaTotal, setSnpediaTotal] = useState<number | null>(null);
  const [featured, setFeatured] = useState<FeaturedSnp[]>([]);
  const [featuredLoading, setFeaturedLoading] = useState(true);

  const LIMIT = 50;

  // Fetch featured SNPs (public, no auth)
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/snp/featured`);
        if (res.ok) {
          const data = await res.json();
          setFeatured(data.snps);
        }
      } catch {
        // API unavailable
      } finally {
        setFeaturedLoading(false);
      }
    })();
  }, []);

  // Fetch user's variant stats if signed in
  useEffect(() => {
    if (!userId) return;
    (async () => {
      try {
        const token = await getToken();
        const data = await apiFetch<{ total: number; snpedia_total: number }>(
          `/api/v1/results/variants/${userId}?limit=1`,
          {},
          token,
        );
        setUserVariantCount(data.total);
        setSnpediaTotal(data.snpedia_total);
      } catch {
        // No completed analysis or not authenticated — ignore
      }
    })();
  }, [userId, getToken]);

  function handleRsidLookup(e: React.FormEvent) {
    e.preventDefault();
    const val = rsidLookup.trim().toLowerCase();
    if (val.startsWith("rs") && val.length > 2) {
      router.push(`/snp/${val}`);
    }
  }

  async function doSearch(newOffset: number) {
    const params = new URLSearchParams();
    if (gene.trim()) params.set("gene", gene.trim());
    if (chrom) params.set("chrom", chrom);
    params.set("limit", String(LIMIT));
    params.set("offset", String(newOffset));

    if (!gene.trim() && !chrom) {
      setError("Enter a gene name or select a chromosome.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/snp/?${params}`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      if (newOffset === 0) {
        setResults(data.snps);
      } else {
        setResults((prev) => [...prev, ...data.snps]);
      }
      setOffset(newOffset);
      setHasMore(data.snps.length === LIMIT);
      setSearched(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    setOffset(0);
    doSearch(0);
  }

  // Group featured SNPs by category
  const groupedFeatured = CATEGORY_ORDER.map((category) => ({
    category,
    snps: featured.filter((s) => GENE_CATEGORIES[s.gene || ""] === category),
  })).filter((g) => g.snps.length > 0);

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-2">Browse SNPs</h1>
      <p className="text-muted text-sm mb-10">
        Look up a variant by rsid, or explore our curated collection of important genetic variants.
      </p>

      {/* Direct rsid lookup */}
      <form onSubmit={handleRsidLookup} className="mb-8">
        <label className="block text-sm font-medium mb-2">Go to variant</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={rsidLookup}
            onChange={(e) => setRsidLookup(e.target.value)}
            placeholder="rs429358"
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="submit"
            disabled={!rsidLookup.trim().toLowerCase().startsWith("rs")}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            Go
          </button>
        </div>
      </form>

      {/* Search filters */}
      <form onSubmit={handleSearch} className="mb-12">
        <label className="block text-sm font-medium mb-2">Search by gene or chromosome</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={gene}
            onChange={(e) => setGene(e.target.value)}
            placeholder="Gene (e.g. APOE)"
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <select
            value={chrom}
            onChange={(e) => setChrom(e.target.value)}
            className="rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          >
            <option value="">Chr</option>
            {CHROMOSOMES.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <button
            type="submit"
            disabled={loading}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            {loading ? "Searching\u2026" : "Search"}
          </button>
        </div>
      </form>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      {/* Search Results */}
      {results.length > 0 && (
        <div className="border border-border rounded-lg overflow-hidden mb-12">
          <table className="w-full text-sm">
            <thead className="bg-surface text-muted">
              <tr>
                <th className="text-left px-4 py-2 font-medium">rsid</th>
                <th className="text-left px-4 py-2 font-medium">Gene</th>
                <th className="text-left px-4 py-2 font-medium">Chr</th>
                <th className="text-left px-4 py-2 font-medium">Position</th>
                <th className="text-left px-4 py-2 font-medium">Alleles</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {results.map((snp) => (
                <tr key={snp.rsid} className="hover:bg-surface/50 transition-colors">
                  <td className="px-4 py-2">
                    <Link href={`/snp/${snp.rsid}`} className="text-accent hover:underline font-mono">
                      {snp.rsid}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-muted">{snp.gene || "\u2014"}</td>
                  <td className="px-4 py-2 text-muted">{snp.chrom || "\u2014"}</td>
                  <td className="px-4 py-2 text-muted">
                    {snp.position != null ? snp.position.toLocaleString() : "\u2014"}
                  </td>
                  <td className="px-4 py-2 font-mono text-muted">
                    {snp.ref_allele && snp.alt_allele
                      ? `${snp.ref_allele}/${snp.alt_allele}`
                      : "\u2014"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasMore && (
        <button
          onClick={() => doSearch(offset + LIMIT)}
          disabled={loading}
          className="mt-4 w-full rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-surface transition-colors disabled:opacity-40"
        >
          {loading ? "Loading\u2026" : "Load more"}
        </button>
      )}

      {searched && results.length === 0 && !loading && (
        <p className="text-muted text-sm mb-12">No SNPs found matching your search.</p>
      )}

      {/* Featured SNPs */}
      {!featuredLoading && featured.length > 0 && (
        <section>
          <h2 className="font-serif text-2xl font-semibold mb-2">Important SNPs</h2>
          <p className="text-sm text-muted mb-8">
            {featured.length} curated variants with known health associations.
          </p>

          <div className="space-y-10">
            {groupedFeatured.map(({ category, snps }) => (
              <div key={category}>
                <h3 className="text-sm font-semibold uppercase tracking-wide text-muted mb-3">
                  {category}
                </h3>
                <div className="space-y-1">
                  {snps.map((snp) => (
                    <Link
                      key={snp.rsid}
                      href={`/snp/${snp.rsid}`}
                      className="flex items-baseline gap-3 py-2 px-3 -mx-3 rounded hover:bg-surface/50 transition-colors group"
                    >
                      <span className="font-mono text-sm text-accent group-hover:underline shrink-0 w-28">
                        {snp.rsid}
                      </span>
                      <span className="text-sm font-medium shrink-0 w-20">
                        {snp.gene || "\u2014"}
                      </span>
                      <span className="text-sm text-muted truncate">
                        {snp.traits[0]?.trait}
                        {snp.traits.length > 1 && (
                          <span className="text-xs ml-1 opacity-60">+{snp.traits.length - 1} more</span>
                        )}
                      </span>
                    </Link>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
