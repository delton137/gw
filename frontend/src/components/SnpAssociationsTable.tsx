"use client";


interface Association {
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
}

export default function SnpAssociationsTable({
  associations,
}: {
  associations: Association[];
}) {
  return (
    <div className="border border-border overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-left">
            <th className="px-4 py-2 font-medium text-muted">Trait</th>
            <th className="px-4 py-2 font-medium text-muted">Risk Allele</th>
            <th className="px-4 py-2 font-medium text-muted" title="Odds Ratio — how much this allele increases or decreases the likelihood of the trait">OR</th>
            <th className="px-4 py-2 font-medium text-muted">p-value</th>
            <th className="px-4 py-2 font-medium text-muted">Evidence</th>
            <th className="px-4 py-2 font-medium text-muted">Source</th>
          </tr>
        </thead>
        <tbody>
          {associations.map((assoc) => (
            <tr key={assoc.id} className="border-b border-border last:border-0 align-top">
              <td className="px-4 py-2">
                <p>{assoc.trait}</p>
                {assoc.effect_description && (
                  <p className="text-xs text-muted mt-0.5">
                    {assoc.effect_description}
                  </p>
                )}
              </td>
              <td className="px-4 py-2 font-mono">{assoc.risk_allele}</td>
              <td className="px-4 py-2">
                {assoc.odds_ratio?.toFixed(2) ?? "—"}
              </td>
              <td className="px-4 py-2">
                {assoc.p_value ? assoc.p_value.toExponential(1) : "—"}
              </td>
              <td className="px-4 py-2 capitalize">{assoc.evidence_level}</td>
              <td className="px-4 py-2">
                {assoc.source_pmid ? (
                  <a
                    href={`https://pubmed.ncbi.nlm.nih.gov/${assoc.source_pmid}`}
                    className="text-accent hover:underline"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    PubMed
                  </a>
                ) : (
                  "—"
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
