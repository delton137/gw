"use client";

import { useEffect, useState } from "react";
import { useAuth, useUser } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { ClinvarHit, ClinvarResponse } from "@/lib/types";

function getZygosity(genotype: string, ref: string | null, alt: string | null): string | null {
  if (!ref || !alt || genotype.length !== 2) return null;
  const [a1, a2] = [genotype[0], genotype[1]];
  // Direct strand
  if (a1 === alt && a2 === alt) return "Hom";
  if ((a1 === ref && a2 === alt) || (a1 === alt && a2 === ref)) return "Het";
  if (a1 === ref && a2 === ref) return "Hom Ref";
  // Complement strand (some chips report opposite strand)
  const comp: Record<string, string> = { A: "T", T: "A", C: "G", G: "C" };
  const cRef = comp[ref], cAlt = comp[alt];
  if (cRef && cAlt) {
    if (a1 === cAlt && a2 === cAlt) return "Hom";
    if ((a1 === cRef && a2 === cAlt) || (a1 === cAlt && a2 === cRef)) return "Het";
    if (a1 === cRef && a2 === cRef) return "Hom Ref";
  }
  return null;
}

const SIG_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  pathogenic:              { bg: "bg-red-100",    text: "text-red-800",    label: "Pathogenic" },
  likely_pathogenic:       { bg: "bg-red-50",     text: "text-red-700",    label: "Likely Pathogenic" },
  risk_factor:             { bg: "bg-amber-100",  text: "text-amber-800",  label: "Risk Factor" },
  likely_risk_allele:      { bg: "bg-amber-50",   text: "text-amber-700",  label: "Likely Risk Allele" },
  drug_response:           { bg: "bg-blue-50",    text: "text-blue-700",   label: "Drug Response" },
  association:             { bg: "bg-amber-50",    text: "text-amber-700",  label: "Association" },
  uncertain_significance:  { bg: "bg-gray-100",   text: "text-gray-600",   label: "VUS" },
  conflicting_classifications_of_pathogenicity: { bg: "bg-gray-100", text: "text-gray-600", label: "Conflicting" },
  likely_benign:           { bg: "bg-green-50",   text: "text-green-700",  label: "Likely Benign" },
  benign:                  { bg: "bg-green-100",  text: "text-green-800",  label: "Benign" },
};

const SIG_ORDER = [
  "pathogenic", "likely_pathogenic", "risk_factor", "likely_risk_allele",
  "drug_response", "association", "uncertain_significance",
  "conflicting_classifications_of_pathogenicity",
  "likely_benign", "benign",
];

export default function ClinvarPage() {
  const { getToken } = useAuth();
  const { user } = useUser();
  const [hits, setHits] = useState<ClinvarHit[]>([]);
  const [total, setTotal] = useState(0);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sigFilter, setSigFilter] = useState<string>("");
  const [geneFilter, setGeneFilter] = useState("");
  const [conditionFilter, setConditionFilter] = useState("");
  const [offset, setOffset] = useState(0);
  const LIMIT = 100;

  async function fetchData(newOffset: number, append: boolean = false) {
    if (!user?.id) return;
    const setLoadFn = append ? setLoadingMore : setLoading;
    setLoadFn(true);
    setError(null);

    try {
      const token = await getToken();
      const params = new URLSearchParams();
      params.set("limit", String(LIMIT));
      params.set("offset", String(newOffset));
      if (sigFilter) params.set("significance", sigFilter);
      if (geneFilter.trim()) params.set("gene", geneFilter.trim().toUpperCase());
      if (conditionFilter.trim()) params.set("condition", conditionFilter.trim());

      const data = await apiFetch<ClinvarResponse>(
        `/api/v1/results/clinvar/${user.id}?${params}`,
        {},
        token,
      );

      if (append) {
        setHits((prev) => [...prev, ...data.hits]);
      } else {
        setHits(data.hits);
        setCounts(data.counts);
      }
      setTotal(data.total);
      setOffset(newOffset);
    } catch {
      setError("Failed to load ClinVar results.");
    } finally {
      setLoadFn(false);
    }
  }

  useEffect(() => {
    if (user) fetchData(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user]);

  function handleFilter(e: React.FormEvent) {
    e.preventDefault();
    fetchData(0);
  }

  // Summary badges from counts
  const orderedCounts = SIG_ORDER
    .filter((sig) => (counts[sig] || 0) > 0)
    .map((sig) => ({ sig, count: counts[sig] }));

  // Also include any counts not in SIG_ORDER
  const extraCounts = Object.entries(counts)
    .filter(([sig]) => !SIG_ORDER.includes(sig) && sig)
    .map(([sig, count]) => ({ sig, count }));
  const allCounts = [...orderedCounts, ...extraCounts];

  return (
    <div className="mx-auto max-w-5xl px-6 pt-8 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-2">ClinVar Annotations</h1>
      <p className="text-muted text-sm mb-3">
        This page displays variants in your genotype file that have clinical annotations in the{" "}
        <a href="https://www.ncbi.nlm.nih.gov/clinvar/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
          ClinVar database
        </a>{" "}maintained by NCBI, as of February 2026. The classifications reported here reflect current scientific understanding and may change. This page is for informational purposes only. Discuss findings with a genetic counselor or healthcare provider to get a clinical interpretation.
      </p>
      <p className="text-muted text-sm mb-8">
        <strong className="text-foreground">Important - ClinVar classifications are almost useless for predicting individual health outcomes. If you are unfamiliar with ClinVar, please read this paragraph for important context: </strong> A {"\u201C"}pathogenic{"\u201D"} classification means the variant has been assessed by ClinVar submitters as causally contributing to a disease, not that a person has or will develop that condition. Many pathogenic variants are recessive (they require two copies to have an effect). ClinVar does not consistently provide information on whether variants are recessive or dominant. However, we have provided a zygosity column so users can tell if they are have one copy (heterozygous) or two copies (homozygous). The presence of a pathogenic variant says almost nothing about the likelihood of developing a disease, because ClinVar classifications are orthogonal to penetrance, which is the probability that a carrier actually develops an associated condition. A{" "}<a href="https://jamanetwork.com/journals/jama/fullarticle/2788347" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">2022 study</a> published in <em>JAMA</em> found that mean penetrance across ClinVar pathogenic variants was only 6.9%. A variant can break a critical protein yet have no effect due to genetic modifiers, environmental factors, and/or compensatory mechanisms. (For more information on this see{" "}<a href="https://www.nature.com/articles/s41525-023-00386-5" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">Ciesielski et al.</a>, 2024.)  Additionally, ClinVar pathogenicity classifications are unrelated to the severity of the associated condition. A "pathogenic" variant may be associated with a slight change in skin pigmentation that has no practical import on wellbeing, or it may be associated with a severe disease that results in a newborn dying shortly after birth. All of this makes ClinVar classifications almost useless for predicting individual health outcomes. Most people carry many {"\u201C"}pathogenic{"\u201D"} variants with no health impact. Similarly, ClinVar reporting only {"\u201C"}benign{"\u201D"} variants for a gene does not rule out any conditions associated with that gene, which may arise through other variants or through non-genetic factors. Where ClinVar becomes useful is when someone has an undiagnosed condition. In the case of an undiagnosed condition, trained clinicians may be able to use ClinVar information to link a patient's symptoms to a rare Mendelian disorder.
      </p>
      <div className="text-sm mb-8">
        <p className="text-muted mb-2">
          <strong className="text-foreground">Stars column:</strong> ClinVar{" "}<a href="https://www.ncbi.nlm.nih.gov/clinvar/docs/review_status/" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">uses a scheme with stars</a> to try to communicate the confidence level for a classification. So, confusingly, a "likely pathogenic" classification with only one star may actually be rather unlikely to be correct! 
        </p>
        <table className="text-xs text-muted">
          <tbody>
            <tr><td className="pr-3 py-0.5">★★★★</td><td>Practice guideline</td></tr>
            <tr><td className="pr-3 py-0.5">★★★☆</td><td>Reviewed by expert panel</td></tr>
            <tr><td className="pr-3 py-0.5">★☆☆☆</td><td>Single submitter provided assertion criteria and evidence</td></tr>
            <tr><td className="pr-3 py-0.5">{"\u2014"}</td><td>No assertion criteria or no classification provided</td></tr>
          </tbody>
        </table>
      </div>

      {/* Summary badges */}
      {allCounts.length > 0 && (
        <div className="flex flex-wrap gap-2 mb-6">
          <button
            onClick={() => { setSigFilter(""); fetchData(0); }}
            className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
              !sigFilter ? "bg-accent text-white" : "bg-gray-100 text-gray-600 hover:bg-gray-200"
            }`}
          >
            All ({total.toLocaleString()})
          </button>
          {allCounts.map(({ sig, count }) => {
            const style = SIG_COLORS[sig];
            const isActive = sigFilter === sig;
            return (
              <button
                key={sig}
                onClick={() => { setSigFilter(isActive ? "" : sig); setTimeout(() => fetchData(0), 0); }}
                className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                  isActive
                    ? "bg-accent text-white"
                    : style
                    ? `${style.bg} ${style.text} hover:opacity-80`
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {style?.label || sig.replace(/_/g, " ")} ({count.toLocaleString()})
              </button>
            );
          })}
        </div>
      )}

      {/* Gene filter */}
      <form onSubmit={handleFilter} className="mb-6">
        <div className="flex flex-wrap gap-2">
          <input
            type="text"
            value={geneFilter}
            onChange={(e) => setGeneFilter(e.target.value)}
            placeholder="Filter by gene (e.g. BRCA1)"
            className="flex-1 min-w-[160px] max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <input
            type="text"
            value={conditionFilter}
            onChange={(e) => setConditionFilter(e.target.value)}
            placeholder="Filter by condition (e.g. diabetes)"
            className="flex-1 min-w-[160px] max-w-xs rounded-md border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-accent"
          />
          <button
            type="submit"
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover transition-colors"
          >
            Filter
          </button>
          {(geneFilter || conditionFilter) && (
            <button
              type="button"
              onClick={() => { setGeneFilter(""); setConditionFilter(""); setTimeout(() => fetchData(0), 0); }}
              className="rounded-md border border-border px-3 py-2 text-sm text-muted hover:bg-surface transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      </form>

      {error && <p className="text-red-500 text-sm mb-4">{error}</p>}

      {loading ? (
        <p className="text-muted text-sm">Loading ClinVar results...</p>
      ) : hits.length > 0 ? (
        <>
          <div className="border border-border rounded-lg overflow-hidden mb-4">
            <table className="w-full text-sm">
              <thead className="bg-surface text-muted">
                <tr>
                  <th className="text-left px-3 py-2 font-medium">rsid</th>
                  <th className="text-left px-3 py-2 font-medium">Gene</th>
                  <th className="text-left px-3 py-2 font-medium">Genotype</th>
                  <th className="text-left px-3 py-2 font-medium">Zygosity</th>
                  <th className="text-left px-3 py-2 font-medium">Classification</th>
                  <th className="text-left px-3 py-2 font-medium">Conditions</th>
                  <th className="text-center px-3 py-2 font-medium">Stars</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {hits.map((hit) => {
                  const style = SIG_COLORS[hit.clinvar_significance];
                  return (
                    <tr key={hit.rsid} className="hover:bg-surface/50 transition-colors">
                      <td className="px-3 py-2">
                        <Link href={`/snp/${hit.rsid}`} className="text-accent hover:underline font-mono text-xs">
                          {hit.rsid}
                        </Link>
                      </td>
                      <td className="px-3 py-2">
                        {hit.gene ? (
                          <Link href={`/gene/${hit.gene}`} className="text-accent hover:underline text-xs">
                            {hit.gene}
                          </Link>
                        ) : (
                          <span className="text-muted text-xs">&mdash;</span>
                        )}
                      </td>
                      <td className="px-3 py-2 font-mono text-xs">{hit.user_genotype}</td>
                      <td className="px-3 py-2 font-mono text-xs">
                        {getZygosity(hit.user_genotype, hit.ref_allele, hit.alt_allele) || "\u2014"}
                      </td>
                      <td className="px-3 py-2">
                        {style ? (
                          <span className={`inline-block px-1.5 py-0.5 rounded text-[11px] font-medium ${style.bg} ${style.text}`}>
                            {style.label}
                          </span>
                        ) : (
                          <span className="text-xs text-muted capitalize">
                            {hit.clinvar_significance.replace(/_/g, " ")}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted max-w-xs truncate" title={hit.clinvar_conditions || undefined}>
                        {hit.clinvar_conditions || "\u2014"}
                      </td>
                      <td className="px-3 py-2 text-center text-xs">
                        {hit.review_stars != null && hit.review_stars > 0
                          ? <span title={`${hit.review_stars} star${hit.review_stars > 1 ? "s" : ""}`}>{"★".repeat(hit.review_stars)}{"☆".repeat(4 - hit.review_stars)}</span>
                          : <span className="text-muted">&mdash;</span>
                        }
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {hits.length < total && (
            <button
              onClick={() => fetchData(offset + LIMIT, true)}
              disabled={loadingMore}
              className="w-full rounded-md border border-border px-4 py-2 text-sm text-muted hover:bg-surface transition-colors disabled:opacity-40"
            >
              {loadingMore ? "Loading\u2026" : `Load more (${hits.length.toLocaleString()} of ${total.toLocaleString()})`}
            </button>
          )}
        </>
      ) : (
        <p className="text-muted text-sm">No ClinVar-annotated variants found{sigFilter || geneFilter || conditionFilter ? " matching your filters" : ""}.</p>
      )}

      {/* Attribution */}
      <p className="text-xs text-muted mt-8 border-t border-border pt-4">
        Variant classifications from{" "}
        <a href="https://www.ncbi.nlm.nih.gov/clinvar/" target="_blank" rel="noopener noreferrer" className="hover:underline">ClinVar</a>{" "}
        (NCBI). ClinVar is a freely accessible, public archive of reports of the relationships among human variations and phenotypes.
        Classifications may change as new evidence emerges.
      </p>
    </div>
  );
}
