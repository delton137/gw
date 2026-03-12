"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import DemoBanner from "@/components/DemoBanner";
import { DEMO_TRAITS, DEMO_VARIANTS_SUMMARY } from "../demoData";
import { CATEGORY_ORDER, getCategory, PGX_GENES } from "@/lib/geneCategories";
import type { TraitHit } from "@/lib/types";

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
  if (!riskAllele) return <span className="text-gray-400">{genotype}</span>;
  return (
    <>
      {genotype.split("").map((allele, i) => (
        <span key={i} className={allele === riskAllele ? "text-purple-600 font-semibold" : "text-gray-400"}>{allele}</span>
      ))}
    </>
  );
}

type SortKey = "rsid" | "gene" | "trait" | "risk_level" | "evidence_level";
type SortDir = "asc" | "desc";

export default function DemoMySnpsPage() {
  const hits = DEMO_TRAITS.hits;
  const totalSnpsInKb = DEMO_TRAITS.total_snps_in_kb;

  const [search, setSearch] = useState("");
  const [riskFilter, setRiskFilter] = useState("");
  const [evidenceFilter, setEvidenceFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("risk_level");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const availableCategories = useMemo(() => {
    const cats = new Set<string>();
    for (const h of hits) {
      const cat = getCategory(h.gene, h.trait);
      if (cat && cat !== "Other") cats.add(cat);
    }
    return Array.from(cats).sort();
  }, [hits]);

  const filteredHits = useMemo(() => {
    let result = hits;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((h) => h.rsid.toLowerCase().includes(q) || h.trait.toLowerCase().includes(q) || (h.gene && h.gene.toLowerCase().includes(q)));
    }
    if (riskFilter) result = result.filter((h) => h.risk_level === riskFilter);
    if (evidenceFilter) result = result.filter((h) => h.evidence_level === evidenceFilter);
    if (categoryFilter) result = result.filter((h) => getCategory(h.gene, h.trait) === categoryFilter);

    result = [...result].sort((a, b) => {
      let cmp = 0;
      switch (sortKey) {
        case "rsid": cmp = a.rsid.localeCompare(b.rsid); break;
        case "gene": cmp = (a.gene || "").localeCompare(b.gene || ""); break;
        case "trait": cmp = a.trait.localeCompare(b.trait); break;
        case "risk_level": cmp = (RISK_ORDER[a.risk_level] ?? 9) - (RISK_ORDER[b.risk_level] ?? 9); break;
        case "evidence_level": cmp = (EVIDENCE_ORDER[a.evidence_level] ?? 9) - (EVIDENCE_ORDER[b.evidence_level] ?? 9); break;
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
    return result;
  }, [hits, search, riskFilter, evidenceFilter, categoryFilter, sortKey, sortDir]);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) setSortDir(sortDir === "asc" ? "desc" : "asc");
    else { setSortKey(key); setSortDir("asc"); }
  };
  const sortIndicator = (key: SortKey) => sortKey !== key ? "" : sortDir === "asc" ? " \u25B2" : " \u25BC";

  const groupedHits = useMemo(() => {
    const groups: Record<string, TraitHit[]> = {};
    for (const hit of filteredHits) {
      const cat = getCategory(hit.gene, hit.trait);
      if (!groups[cat]) groups[cat] = [];
      groups[cat].push(hit);
    }
    const ordered: [string, TraitHit[]][] = [];
    for (const cat of CATEGORY_ORDER) {
      if (groups[cat]) { ordered.push([cat, groups[cat]]); delete groups[cat]; }
    }
    for (const [cat, catHits] of Object.entries(groups)) ordered.push([cat, catHits]);
    return ordered;
  }, [filteredHits]);

  const uniqueUserSnps = useMemo(() => new Set(hits.map((h) => h.rsid)).size, [hits]);

  return (
    <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
      <DemoBanner />

      <h1 className="font-serif text-3xl font-semibold mb-2">My SNPs</h1>

      <section className="mb-16">
        <p className="text-sm text-muted mb-6 mt-2">
          Found <span className="font-semibold text-foreground">{uniqueUserSnps}</span>
          {totalSnpsInKb > 0 && <> out of <span className="font-semibold text-foreground">{totalSnpsInKb}</span></>}{" "}
          important SNPs.
        </p>

        {/* Filters */}
        <div className="flex flex-wrap gap-3 mb-4">
          <input type="text" placeholder="Search rsID, gene, or trait..." value={search} onChange={(e) => setSearch(e.target.value)}
            className="border border-border bg-white px-3 py-1.5 text-sm w-64 focus:outline-none focus:ring-2 focus:ring-accent" />
          <select value={riskFilter} onChange={(e) => setRiskFilter(e.target.value)} className="border border-border bg-white px-3 py-1.5 text-sm">
            <option value="">All effect levels</option>
            <option value="increased">Increased</option>
            <option value="moderate">Moderate</option>
            <option value="typical">Typical</option>
          </select>
          <select value={evidenceFilter} onChange={(e) => setEvidenceFilter(e.target.value)} className="border border-border bg-white px-3 py-1.5 text-sm">
            <option value="">All evidence</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
          {availableCategories.length > 1 && (
            <select value={categoryFilter} onChange={(e) => setCategoryFilter(e.target.value)} className="border border-border bg-white px-3 py-1.5 text-sm">
              <option value="">All categories</option>
              {availableCategories.map((cat) => <option key={cat} value={cat}>{cat}</option>)}
            </select>
          )}
        </div>

        {filteredHits.length === 0 ? (
          <p className="text-sm text-muted py-8 text-center">No results match your filters.</p>
        ) : (
          <div className="space-y-8">
            {groupedHits.map(([category, catHits]) => {
              if (category === "Other") {
                catHits = catHits.filter(h => !PGX_GENES.has(h.gene || ""));
                if (catHits.length === 0) return null;
              }
              if (category === "Pharmacogenomics") {
                return (
                  <div key={category}>
                    <h2 className="font-serif text-lg font-semibold mb-2">Pharmacogenomics</h2>
                    <div className="border border-border px-4 py-6 text-center">
                      <p className="text-sm text-muted mb-2">Information on drug metabolism and drug response is consolidated on the pharmacogenomics page.</p>
                      <Link href="/demo/pgx" className="text-accent hover:underline font-medium text-sm">View Pharmacogenomics Results &rarr;</Link>
                    </div>
                  </div>
                );
              }
              return (
                <div key={category}>
                  <h2 className="font-serif text-lg font-semibold mb-2">{category}</h2>
                  <div className="border border-border overflow-x-auto">
                    <div className="grid grid-cols-[7rem_5rem_1fr_minmax(8rem,auto)_4.5rem_5.5rem] items-center px-4 py-2 border-b border-border text-sm">
                      <span className="font-medium text-muted cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("rsid")}>rsID{sortIndicator("rsid")}</span>
                      <span className="font-medium text-muted cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("gene")}>Gene{sortIndicator("gene")}</span>
                      <span className="font-medium text-muted cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("trait")}>Trait{sortIndicator("trait")}</span>
                      <span className="font-medium text-muted text-center cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("risk_level")}>Risk / Effect{sortIndicator("risk_level")}</span>
                      <span className="font-medium text-muted text-center" title="Purple alleles are effect alleles">Genotype</span>
                      <span className="font-medium text-muted text-center cursor-pointer hover:text-foreground select-none" onClick={() => handleSort("evidence_level")}>Evidence{sortIndicator("evidence_level")}</span>
                    </div>
                    {catHits.map((hit) => {
                      const isExpanded = expandedId === hit.id;
                      return (
                        <div key={hit.id} className="border-b border-border last:border-0">
                          <button onClick={() => setExpandedId(isExpanded ? null : hit.id)}
                            className="w-full text-left grid grid-cols-[7rem_5rem_1fr_minmax(8rem,auto)_4.5rem_5.5rem] items-center px-4 py-3 hover:bg-gray-50 transition-colors text-sm">
                            <Link href={`/snp/${hit.rsid}`} className="font-mono text-accent hover:underline" onClick={(e) => e.stopPropagation()}>{hit.rsid}</Link>
                            {hit.gene ? <Link href={`/gene/${hit.gene}`} className="truncate pr-1 text-accent hover:underline" onClick={(e) => e.stopPropagation()}>{hit.gene}</Link> : <span className="font-medium truncate pr-1">&mdash;</span>}
                            <span className="truncate pr-2">{hit.trait}</span>
                            <span className="text-center">
                              {hit.risk_level === "typical" ? (
                                <span className="text-xs text-gray-400">Typical</span>
                              ) : hit.effect_summary ? (
                                <span className={`text-xs ${riskColor(hit.risk_level)}`}>
                                  {hit.effect_summary}
                                  {hit.risk_level === "moderate" && <span className="text-gray-400 ml-1">(1 copy)</span>}
                                </span>
                              ) : (
                                <span className={`text-xs capitalize ${riskColor(hit.risk_level)}`}>{hit.risk_level}</span>
                              )}
                            </span>
                            <span className="font-mono text-xs text-center"><GenotypeDisplay genotype={hit.user_genotype} riskAllele={hit.risk_allele} /></span>
                            <span className="text-center"><span className={`inline-block px-2 py-0.5 text-xs rounded-full capitalize ${evidenceBadge(hit.evidence_level)}`}>{hit.evidence_level}</span></span>
                          </button>
                          {isExpanded && (
                            <div className="px-4 pb-4 pt-1 bg-surface/50 border-t border-border/50">
                              {hit.risk_allele && (
                                <p className="text-xs text-muted mb-2">
                                  Your genotype: <span className="font-mono font-semibold">{hit.user_genotype}</span>
                                  {" \u2014 "}
                                  {hit.risk_level === "increased" ? `two copies of the effect allele (${hit.risk_allele})`
                                    : hit.risk_level === "moderate" ? `one copy of the effect allele (${hit.risk_allele})`
                                    : `no copies of the effect allele (${hit.risk_allele})`}
                                </p>
                              )}
                              {hit.effect_description && <p className="text-sm text-muted leading-relaxed">{hit.effect_description}</p>}
                              <Link href={`/snp/${hit.rsid}`} className="text-xs text-accent hover:underline mt-2 inline-block">View full SNP details &rarr;</Link>
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
          <p className="text-xs text-muted mt-3">Showing {filteredHits.length} of {hits.length} results.</p>
        )}
      </section>

      {/* SNPedia summary */}
      <section>
        <h2 className="font-serif text-xl font-semibold mb-1">All SNPedia Variants</h2>
        <p className="text-sm text-muted mb-6">
          <span className="font-semibold text-foreground">{DEMO_VARIANTS_SUMMARY.total.toLocaleString()}</span>{" "}
          SNPs out of{" "}
          <span className="font-semibold text-foreground">{DEMO_VARIANTS_SUMMARY.snpedia_total.toLocaleString()}</span>{" "}
          on <a href="https://www.snpedia.com" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">SNPedia</a>.
        </p>
      </section>
    </div>
  );
}
