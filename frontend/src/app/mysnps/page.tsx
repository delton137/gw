"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import { CATEGORY_ORDER, getCategory, PGX_GENES } from "@/lib/geneCategories";
import type { TraitHit, TraitsResponse, VariantsResponse } from "@/lib/types";

const RISK_ORDER: Record<string, number> = { increased: 0, moderate: 1, typical: 2 };
const EVIDENCE_ORDER: Record<string, number> = { high: 0, medium: 1, low: 2 };

function riskColor(level: string): string {
  switch (level) {
    case "increased": return "text-red-700";
    case "moderate": return "text-amber-700";
    default: return "text-muted";
  }
}

function evidenceBadge(level: string): string {
  switch (level) {
    case "high": return "bg-green-50 text-green-700";
    case "medium": return "bg-blue-50 text-blue-700";
    default: return "bg-gray-50 text-gray-600";
  }
}

function GenotypeDisplay({ genotype, riskAllele }: { genotype: string; riskAllele: string | null }) {
  if (!riskAllele) {
    return <span className="text-gray-400">{genotype}</span>;
  }
  return (
    <>
      {genotype.split("").map((allele, i) => (
        <span
          key={i}
          className={allele === riskAllele ? "text-purple-600 font-semibold" : "text-gray-400"}
        >
          {allele}
        </span>
      ))}
    </>
  );
}

type SortKey = "rsid" | "gene" | "trait" | "risk_level" | "evidence_level";
type SortDir = "asc" | "desc";

const SNPEDIA_LIMIT = 200;

export default function MySnpsPage() {
  const { userId, getToken } = useAuth();

  // Trait hits state
  const [hits, setHits] = useState<TraitHit[]>([]);
  const [totalSnpsInKb, setTotalSnpsInKb] = useState(0);
  const [hitsLoading, setHitsLoading] = useState(true);

  // Filters
  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [evidenceFilter, setEvidenceFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");

  // Sort
  const [sortKey, setSortKey] = useState<SortKey>("risk_level");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  // Expanded row
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // SNPedia variants state
  const [variants, setVariants] = useState<{ rsid: string }[]>([]);
  const [variantsTotal, setVariantsTotal] = useState(0);
  const [snpediaTotal, setSnpediaTotal] = useState(0);
  const [filename, setFilename] = useState<string | null>(null);
  const [variantsLoading, setVariantsLoading] = useState(true);
  const [variantsLoadingMore, setVariantsLoadingMore] = useState(false);
  const [variantsSearch, setVariantsSearch] = useState("");

  // Load trait hits
  useEffect(() => {
    async function load() {
      if (!userId) return;
      try {
        const token = await getToken();
        const data = await apiFetch<TraitsResponse>(
          `/api/v1/results/traits/${userId}?limit=1000`,
          {},
          token,
        );
        setHits(data.hits);
        setTotalSnpsInKb(data.total_snps_in_kb);
      } catch {
        // No results
      } finally {
        setHitsLoading(false);
      }
    }
    if (userId) load();
  }, [userId, getToken]);

  // Load SNPedia variants
  const loadVariants = useCallback(
    async (searchTerm: string, offset: number, append: boolean) => {
      if (!userId) return;
      if (offset === 0) setVariantsLoading(true);
      else setVariantsLoadingMore(true);
      try {
        const token = await getToken();
        const params = new URLSearchParams({
          limit: String(SNPEDIA_LIMIT),
          offset: String(offset),
        });
        if (searchTerm) params.set("search", searchTerm);
        const data = await apiFetch<VariantsResponse>(
          `/api/v1/results/variants/${userId}?${params}`,
          {},
          token,
        );
        setVariants(append ? (prev) => [...prev, ...data.variants] : data.variants);
        setVariantsTotal(data.total);
        setSnpediaTotal(data.snpedia_total);
        if (data.filename) setFilename(data.filename);
      } catch {
        // no results
      } finally {
        setVariantsLoading(false);
        setVariantsLoadingMore(false);
      }
    },
    [userId, getToken],
  );

  useEffect(() => {
    if (userId) loadVariants("", 0, false);
  }, [userId, loadVariants]);

  // Derive available categories from hits
  const availableCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const h of hits) {
      const cat = getCategory(h.gene, h.trait);
      if (cat && cat !== "Other") cats.add(cat);
    }
    return Array.from(cats).sort();
  }, [hits]);

  // Filter + sort hits
  const filteredHits = useMemo(() => {
    let result = hits;

    if (search) {
      const q = search.toLowerCase();
      result = result.filter(
        (h) =>
          h.rsid.toLowerCase().includes(q) ||
          h.trait.toLowerCase().includes(q) ||
          (h.gene && h.gene.toLowerCase().includes(q)),
      );
    }
    if (riskFilter) {
      result = result.filter((h) => h.risk_level === riskFilter);
    }
    if (evidenceFilter) {
      result = result.filter((h) => h.evidence_level === evidenceFilter);
    }
    if (categoryFilter) {
      result = result.filter((h) => getCategory(h.gene, h.trait) === categoryFilter);
    }

    // Sort
    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "rsid":
          cmp = a.rsid.localeCompare(b.rsid);
          break;
        case "gene":
          cmp = (a.gene || "").localeCompare(b.gene || "");
          break;
        case "trait":
          cmp = a.trait.localeCompare(b.trait);
          break;
        case "risk_level":
          cmp = (RISK_ORDER[a.risk_level] ?? 9) - (RISK_ORDER[b.risk_level] ?? 9);
          break;
        case "evidence_level":
          cmp = (EVIDENCE_ORDER[a.evidence_level] ?? 9) - (EVIDENCE_ORDER[b.evidence_level] ?? 9);
          break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });

    return result;
  }, [hits, search, riskFilter, evidenceFilter, categoryFilter, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir(sortDir === "asc" ? "desc" : "asc");
    } else {
      setSortKey(key);
      setSortDir(key === "risk_level" || key === "evidence_level" ? "asc" : "asc");
    }
  };

  const sortIndicator = (key: SortKey) => {
    if (sortKey !== key) return "";
    return sortDir === "asc" ? " ▲" : " ▼";
  };

  // Group filtered hits by category
  const groupedHits = useMemo(() => {
    const groups: Record<string, TraitHit[]> = {};
    for (const hit of filteredHits) {
      const cat = getCategory(hit.gene, hit.trait);
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(hit);
    }
    // Sort groups by CATEGORY_ORDER, with "Other" at end
    const ordered: [string, TraitHit[]][] = [];
    for (const cat of CATEGORY_ORDER) {
      if (groups[cat]) {
        ordered.push([cat, groups[cat]]);
        delete groups[cat];
      }
    }
    // Remaining categories not in CATEGORY_ORDER
    for (const [cat, hits] of Object.entries(groups)) {
      ordered.push([cat, hits]);
    }
    return ordered;
  }, [filteredHits]);

  // Count unique SNPs the user matched
  const uniqueUserSnps = useMemo(() => new Set(hits.map((h) => h.rsid)).size, [hits]);

  if (!userId) {
    return (
      <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
        <p className="text-muted">Please sign in to view your SNPs.</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
      <div className="flex items-start justify-between mb-2">
        <h1 className="font-serif text-3xl font-semibold">My SNPs</h1>
        <Link href="/dashboard" className="text-sm text-accent hover:underline mt-2">
          &larr; Dashboard
        </Link>
      </div>

      {/* Trait Hits Section */}
      {hitsLoading ? (
        <p className="text-muted mt-4">Loading...</p>
      ) : hits.length === 0 ? (
        <div className="border border-border p-12 text-center mt-8">
          <p className="text-muted mb-4">No trait associations found yet.</p>
          <Link href="/upload" className="text-accent hover:underline text-sm">
            Upload your genotype file to get started
          </Link>
        </div>
      ) : (
        <section className="mb-16">
          {/* Summary */}
          <p className="text-sm text-muted mb-6 mt-2">
            Found{" "}
            <span className="font-semibold text-foreground">{uniqueUserSnps}</span>
            {totalSnpsInKb > 0 && (
              <>
                {" "}out of{" "}
                <span className="font-semibold text-foreground">{totalSnpsInKb}</span>
              </>
            )}{" "}
            important SNPs.
          </p>

          {/* Filters */}
          <div className="flex flex-wrap gap-3 mb-4">
            <input
              type="text"
              placeholder="Search rsID, gene, or trait..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="border border-border bg-white px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-accent"
            />
            <select
              value={riskFilter}
              onChange={(e) => setRiskFilter(e.target.value)}
              className="border border-border bg-white px-3 py-1.5 text-sm"
            >
              <option value="">All effect levels</option>
              <option value="increased">Increased</option>
              <option value="moderate">Moderate</option>
              <option value="typical">Typical</option>
            </select>
            <select
              value={evidenceFilter}
              onChange={(e) => setEvidenceFilter(e.target.value)}
              className="border border-border bg-white px-3 py-1.5 text-sm"
            >
              <option value="">All evidence</option>
              <option value="high">High</option>
              <option value="medium">Medium</option>
              <option value="low">Low</option>
            </select>
            {availableCategories.length > 1 && (
              <select
                value={categoryFilter}
                onChange={(e) => setCategoryFilter(e.target.value)}
                className="border border-border bg-white px-3 py-1.5 text-sm"
              >
                <option value="">All categories</option>
                {availableCategories.map((cat) => (
                  <option key={cat} value={cat}>{cat}</option>
                ))}
              </select>
            )}
          </div>

          {filteredHits.length === 0 ? (
            <p className="text-sm text-muted py-8 text-center">No results match your filters.</p>
          ) : (
            <div className="space-y-8">
              {groupedHits.map(([category, catHits]) => {
                // Hide PGx-panel genes from "Other" — they belong on /pgx
                if (category === "Other") {
                  catHits = catHits.filter(h => !PGX_GENES.has(h.gene || ""));
                  if (catHits.length === 0) return null;
                }

                if (category === "Pharmacogenomics") {
                  return (
                    <div key={category}>
                      <h2 className="font-serif text-lg font-semibold mb-2">Pharmacogenomics</h2>
                      <div className="border border-border px-4 py-6 text-center">
                        <p className="text-sm text-muted mb-2">
                          Information on drug metabolism and drug response is consolidated on the pharmacogenomics page. For many genes, we utilize star alleles or a panel of snps to make a gene function call.
                        </p>
                        <Link href="/pgx" className="text-accent hover:underline font-medium text-sm">
                          View Pharmacogenomics Results &rarr;
                        </Link>
                      </div>
                    </div>
                  );
                }

                return (
                <div key={category}>
                  <h2 className="font-serif text-lg font-semibold mb-2">
                    {category}
                  </h2>
                  <div className="border border-border overflow-x-auto">
                    {/* Header */}
                    <div className="grid grid-cols-[7rem_5rem_1fr_minmax(8rem,auto)_4.5rem_5.5rem] items-center px-4 py-2 border-b border-border text-sm">
                      <span
                        className="font-medium text-muted cursor-pointer hover:text-foreground select-none"
                        onClick={() => handleSort("rsid")}
                      >
                        rsID{sortIndicator("rsid")}
                      </span>
                      <span
                        className="font-medium text-muted cursor-pointer hover:text-foreground select-none"
                        onClick={() => handleSort("gene")}
                      >
                        Gene{sortIndicator("gene")}
                      </span>
                      <span
                        className="font-medium text-muted cursor-pointer hover:text-foreground select-none"
                        onClick={() => handleSort("trait")}
                      >
                        Trait{sortIndicator("trait")}
                      </span>
                      <span
                        className="font-medium text-muted text-center cursor-pointer hover:text-foreground select-none"
                        onClick={() => handleSort("risk_level")}
                      >
                        Risk / Effect{sortIndicator("risk_level")}
                      </span>
                      <span className="font-medium text-muted text-center" title="Purple alleles are effect alleles associated with the trait">Genotype</span>
                      <span
                        className="font-medium text-muted text-center cursor-pointer hover:text-foreground select-none"
                        onClick={() => handleSort("evidence_level")}
                      >
                        Evidence{sortIndicator("evidence_level")}
                      </span>
                    </div>
                    {/* Rows */}
                    {catHits.map((hit) => {
                      const isExpanded = expandedId === hit.id;

                      return (
                        <div key={hit.id} className="border-b border-border last:border-0">
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : hit.id)}
                            className="w-full text-left grid grid-cols-[7rem_5rem_1fr_minmax(8rem,auto)_4.5rem_5.5rem] items-center px-4 py-3 hover:bg-gray-50 transition-colors text-sm"
                          >
                            <Link
                              href={`/snp/${hit.rsid}`}
                              className="font-mono text-accent hover:underline"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {hit.rsid}
                            </Link>
                            {hit.gene ? (
                              <Link
                                href={`/gene/${hit.gene}`}
                                className="truncate pr-1 text-accent hover:underline"
                                onClick={(e) => e.stopPropagation()}
                              >
                                {hit.gene}
                              </Link>
                            ) : (
                              <span className="font-medium truncate pr-1">—</span>
                            )}
                            <span className="truncate pr-2">{hit.trait}</span>
                            <span className="text-center">
                              {hit.risk_level === "typical" ? (
                                <span className="text-xs text-gray-400">Typical</span>
                              ) : hit.effect_summary ? (
                                <span className={`text-xs ${riskColor(hit.risk_level)}`}>
                                  {hit.effect_summary}
                                  {hit.risk_level === "moderate" && (
                                    <span className="text-gray-400 ml-1">(1 copy)</span>
                                  )}
                                </span>
                              ) : (
                                <span className={`text-xs capitalize ${riskColor(hit.risk_level)}`}>
                                  {hit.risk_level}
                                </span>
                              )}
                            </span>
                            <span className="font-mono text-xs text-center">
                              <GenotypeDisplay genotype={hit.user_genotype} riskAllele={hit.risk_allele} />
                            </span>
                            <span className="text-center">
                              <span className={`inline-block px-2 py-0.5 text-xs rounded-full capitalize ${evidenceBadge(hit.evidence_level)}`}>
                                {hit.evidence_level}
                              </span>
                            </span>
                          </button>

                          {isExpanded && (
                            <div className="px-4 pb-4 pt-1 bg-surface/50 border-t border-border/50">
                              {hit.risk_allele && (
                                <p className="text-xs text-muted mb-2">
                                  Your genotype: <span className="font-mono font-semibold">{hit.user_genotype}</span>
                                  {" — "}
                                  {hit.risk_level === "increased"
                                    ? `two copies of the effect allele (${hit.risk_allele})`
                                    : hit.risk_level === "moderate"
                                    ? `one copy of the effect allele (${hit.risk_allele})`
                                    : `no copies of the effect allele (${hit.risk_allele})`}
                                </p>
                              )}
                              {hit.effect_description && (
                                <p className="text-sm text-muted leading-relaxed">{hit.effect_description}</p>
                              )}
                              <Link
                                href={`/snp/${hit.rsid}`}
                                className="text-xs text-accent hover:underline mt-2 inline-block"
                              >
                                View full SNP details &rarr;
                              </Link>
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
                );
              })}
            </div>
          )}

          {(search || riskFilter || evidenceFilter || categoryFilter) && (
            <p className="text-xs text-muted mt-3">
              Showing {filteredHits.length} of {hits.length} results. Clear filters to see all.
            </p>
          )}
        </section>
      )}

      {/* All SNPedia variants */}
      <section>
        <h2 className="font-serif text-xl font-semibold mb-1">All SNPedia Variants</h2>

        {variantsLoading ? (
          <p className="text-muted">Loading...</p>
        ) : variantsTotal === 0 && !variantsSearch ? (
          <div className="border border-border p-12 text-center">
            <p className="text-muted mb-4">No variant data yet.</p>
            <Link href="/upload" className="text-accent hover:underline text-sm">
              Upload your genotype file to get started
            </Link>
          </div>
        ) : (
          <>
            <p className="text-sm text-muted mb-6">
              <span className="font-semibold text-foreground">{variantsTotal.toLocaleString()}</span>{" "}
              SNPs
              {filename && (
                <> in <span className="font-semibold text-foreground">{filename}</span></>
              )}{" "}
              out of{" "}
              <span className="font-semibold text-foreground">{snpediaTotal.toLocaleString()}</span>{" "}
              on{" "}
              <a
                href="https://www.snpedia.com"
                target="_blank"
                rel="noopener noreferrer"
                className="text-accent hover:underline"
              >
                SNPedia
              </a>
              .
            </p>

            <div className="mb-6">
              <input
                type="text"
                placeholder="Filter by rsid (e.g. rs429)"
                value={variantsSearch}
                onChange={(e) => {
                  setVariantsSearch(e.target.value);
                  loadVariants(e.target.value, 0, false);
                }}
                className="w-full max-w-sm border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
              />
            </div>

            <div className="border border-border rounded-lg p-4">
              <div className="grid grid-cols-3 sm:grid-cols-4 md:grid-cols-5 lg:grid-cols-6 gap-x-2 gap-y-1">
                {variants.map((v) => (
                  <Link
                    key={v.rsid}
                    href={`/snp/${v.rsid}`}
                    className="text-xs font-mono text-accent hover:underline py-0.5 truncate"
                  >
                    {v.rsid}
                  </Link>
                ))}
              </div>

              {variants.length < variantsTotal && (
                <button
                  onClick={() => loadVariants(variantsSearch, variants.length, true)}
                  disabled={variantsLoadingMore}
                  className="mt-4 w-full border border-border px-4 py-2 text-sm text-muted hover:bg-surface transition-colors disabled:opacity-40"
                >
                  {variantsLoadingMore
                    ? "Loading..."
                    : `Load more (showing ${variants.length.toLocaleString()} of ${variantsTotal.toLocaleString()})`}
                </button>
              )}
            </div>
          </>
        )}
      </section>
    </div>
  );
}
