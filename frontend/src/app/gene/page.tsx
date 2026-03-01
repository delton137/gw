"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { API_URL } from "@/lib/api";

interface GeneResult {
  symbol: string;
  name: string | null;
  omim_number: string | null;
  clinvar_total_variants: number | null;
  clinvar_pathogenic_count: number | null;
}

interface FeaturedGene extends GeneResult {
  is_pharmacogene: boolean;
  in_carrier_panel: boolean;
}

export default function GeneBrowsePage() {
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<GeneResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searched, setSearched] = useState(false);
  const [featured, setFeatured] = useState<FeaturedGene[]>([]);
  const [featuredLoading, setFeaturedLoading] = useState(true);

  // Fetch featured genes
  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${API_URL}/api/v1/gene/featured`);
        if (res.ok) {
          const data = await res.json();
          setFeatured(data.genes);
        }
      } catch {
        // API unavailable
      } finally {
        setFeaturedLoading(false);
      }
    })();
  }, []);

  function handleDirectLookup(e: React.FormEvent) {
    e.preventDefault();
    const val = query.trim().toUpperCase();
    if (val.length >= 1) {
      router.push(`/gene/${val}`);
    }
  }

  async function doSearch() {
    const q = query.trim();
    if (!q) {
      setError("Enter a gene symbol or name to search.");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${API_URL}/api/v1/gene/search?q=${encodeURIComponent(q)}&limit=50`);
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.detail || `Error ${res.status}`);
      }
      const data = await res.json();
      setResults(data.genes);
      setSearched(true);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    doSearch();
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-2">Browse Genes</h1>
      <p className="text-muted text-sm mb-10">
        Look up a gene by symbol, or search by name. Gene pages include ClinVar variant
        statistics, associated conditions, and links to external databases.
      </p>

      {/* Search / direct lookup */}
      <form onSubmit={handleSearch} className="mb-12">
        <label className="block text-sm font-medium mb-2">Search genes</label>
        <div className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Gene symbol or name (e.g. BRCA1, apolipoprotein)"
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="submit"
            disabled={loading || !query.trim()}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-40 transition-colors"
          >
            {loading ? "Searching\u2026" : "Search"}
          </button>
          <button
            type="button"
            onClick={handleDirectLookup}
            disabled={!query.trim()}
            className="rounded-md border border-border px-4 py-2 text-sm font-medium text-muted hover:bg-surface disabled:opacity-40 transition-colors"
            title="Go directly to gene page"
          >
            Go
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
                <th className="text-left px-4 py-2 font-medium">Gene</th>
                <th className="text-left px-4 py-2 font-medium">Name</th>
                <th className="text-right px-4 py-2 font-medium">Total Variants</th>
                <th className="text-right px-4 py-2 font-medium">Pathogenic</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {results.map((g) => (
                <tr key={g.symbol} className="hover:bg-surface/50 transition-colors">
                  <td className="px-4 py-2">
                    <Link href={`/gene/${g.symbol}`} className="text-accent hover:underline font-medium">
                      {g.symbol}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-muted truncate max-w-xs" title={g.name || undefined}>
                    {g.name || "\u2014"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-muted">
                    {g.clinvar_total_variants?.toLocaleString() ?? "\u2014"}
                  </td>
                  <td className="px-4 py-2 text-right font-mono">
                    {g.clinvar_pathogenic_count != null && g.clinvar_pathogenic_count > 0 ? (
                      <span className="text-red-700">{g.clinvar_pathogenic_count.toLocaleString()}</span>
                    ) : (
                      <span className="text-muted">{g.clinvar_pathogenic_count ?? "\u2014"}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {searched && results.length === 0 && !loading && (
        <p className="text-muted text-sm mb-12">No genes found matching your search.</p>
      )}

      {/* Featured Genes */}
      {!featuredLoading && featured.length > 0 && (
        <section>
          <h2 className="font-serif text-2xl font-semibold mb-2">Clinically Important Genes</h2>
          <p className="text-sm text-muted mb-8">
            Genes with the most pathogenic variants in ClinVar.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {featured.map((g) => (
              <Link
                key={g.symbol}
                href={`/gene/${g.symbol}`}
                className="border border-border rounded-lg p-3 hover:bg-surface/50 transition-colors group"
              >
                <div className="flex items-baseline justify-between">
                  <span className="font-medium text-accent group-hover:underline">{g.symbol}</span>
                  <div className="flex gap-1.5">
                    {g.is_pharmacogene && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-violet-100 text-violet-800">
                        PGx
                      </span>
                    )}
                    {g.in_carrier_panel && (
                      <span className="px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800">
                        Carrier
                      </span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-muted truncate mt-0.5">{g.name || "\u2014"}</p>
                <div className="flex gap-4 mt-2 text-xs">
                  <span className="text-muted">
                    {g.clinvar_total_variants?.toLocaleString() ?? 0} variants
                  </span>
                  {g.clinvar_pathogenic_count != null && g.clinvar_pathogenic_count > 0 && (
                    <span className="text-red-700">
                      {g.clinvar_pathogenic_count.toLocaleString()} pathogenic
                    </span>
                  )}
                </div>
              </Link>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
