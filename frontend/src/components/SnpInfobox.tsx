interface PathogenicityData {
  cadd_phred: number | null;
  sift: { category: string; score: number } | null;
  polyphen: { category: string; score: number } | null;
  revel_score: number | null;
}

interface ClinVarData {
  significance: string;
  conditions: string | null;
  review_stars: number | null;
  allele_id: number | null;
  submitter_count?: number | null;
  citation_count?: number | null;
}

interface HgvsData {
  coding: string | null;
  protein: string | null;
}

interface PopulationFrequencies {
  african: number | null;
  east_asian: number | null;
  european: number | null;
  south_asian: number | null;
  latino: number | null;
  finnish: number | null;
  ashkenazi_jewish: number | null;
}

export interface SnpInfoboxProps {
  rsid: string;
  chrom: string | null;
  position: number | null;
  ref_allele: string | null;
  alt_allele: string | null;
  gene: string | null;
  gene_name?: string | null;
  functional_class: string | null;
  maf_global: number | null;
  in_database: boolean;
  pathogenicity?: PathogenicityData | null;
  clinvar?: ClinVarData | null;
  hgvs?: HgvsData | null;
  population_frequencies?: PopulationFrequencies | null;
}

const CLINVAR_COLORS: Record<string, { bg: string; text: string; label: string }> = {
  pathogenic:              { bg: "bg-red-100",    text: "text-red-800",    label: "Pathogenic" },
  likely_pathogenic:       { bg: "bg-red-50",     text: "text-red-700",    label: "Likely Pathogenic" },
  risk_factor:             { bg: "bg-amber-100",  text: "text-amber-800",  label: "Risk Factor" },
  association:             { bg: "bg-amber-50",   text: "text-amber-700",  label: "Association" },
  drug_response:           { bg: "bg-blue-50",    text: "text-blue-700",   label: "Drug Response" },
  uncertain_significance:  { bg: "bg-gray-100",   text: "text-gray-600",   label: "Uncertain Significance" },
  likely_benign:           { bg: "bg-green-50",   text: "text-green-700",  label: "Likely Benign" },
  benign:                  { bg: "bg-green-100",  text: "text-green-800",  label: "Benign" },
};

export function ClinVarBadge({ significance, reviewStars }: { significance: string; reviewStars: number | null }) {
  const style = CLINVAR_COLORS[significance] ?? { bg: "bg-gray-100", text: "text-gray-600", label: significance };
  const stars = reviewStars ?? 0;
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${style.bg} ${style.text}`}>
        {style.label}
      </span>
      {stars > 0 && (
        <span className="text-xs text-muted" title={`ClinVar review: ${stars} star${stars > 1 ? "s" : ""}`}>
          {"★".repeat(stars)}{"☆".repeat(4 - stars)}
        </span>
      )}
    </div>
  );
}

function CaddBar({ score }: { score: number }) {
  // CADD PHRED: 0-50 typical range; ≥20 = top 1%, ≥30 = top 0.1%
  const pct = Math.min(score / 40, 1) * 100;
  const color = score >= 30 ? "bg-red-500" : score >= 20 ? "bg-amber-500" : score >= 10 ? "bg-yellow-400" : "bg-green-400";
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono w-8 text-right">{score.toFixed(1)}</span>
    </div>
  );
}

function PopFreqRow({ label, freq }: { label: string; freq: number }) {
  const pct = freq * 100;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs w-20 truncate" title={label}>{label}</span>
      <div className="flex-1 h-1.5 bg-gray-200 rounded-full overflow-hidden">
        <div className="h-full rounded-full bg-accent/60" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
      <span className="text-xs font-mono w-12 text-right">{pct < 0.01 ? "<0.01" : pct.toFixed(1)}%</span>
    </div>
  );
}

function externalLinks(props: SnpInfoboxProps) {
  const { rsid, chrom, position, ref_allele, alt_allele, in_database, clinvar } = props;
  const rsidNum = rsid.slice(2);

  const links: { label: string; url: string; available: boolean }[] = [
    {
      label: "dbSNP",
      url: `https://www.ncbi.nlm.nih.gov/snp/${rsid}`,
      available: true,
    },
    {
      label: "gnomAD",
      url: `https://gnomad.broadinstitute.org/variant/${chrom}-${position}-${ref_allele}-${alt_allele}?dataset=gnomad_r4`,
      available: in_database && !!chrom && !!position && !!ref_allele && !!alt_allele,
    },
    {
      label: "ClinVar",
      url: clinvar?.allele_id
        ? `https://www.ncbi.nlm.nih.gov/clinvar/?term=${clinvar.allele_id}[alleleid]`
        : `https://www.ncbi.nlm.nih.gov/clinvar/?term=${rsid}`,
      available: true,
    },
    {
      label: "VarSome",
      url: `https://varsome.com/variant/hg19/${rsid}`,
      available: true,
    },
    {
      label: "LitVar",
      url: `https://www.ncbi.nlm.nih.gov/research/litvar2/docsum?variant=litvar@${rsid}%23%23`,
      available: true,
    },
    {
      label: "PheGenI",
      url: `https://www.ncbi.nlm.nih.gov/gap/phegeni?tab=2&rs=${rsidNum}`,
      available: true,
    },
    {
      label: "GWAS Catalog",
      url: `https://www.ebi.ac.uk/gwas/search?query=${rsid}`,
      available: true,
    },
    {
      label: "GGV Browser",
      url: `https://popgen.uchicago.edu/ggv/?data=%221000genomes%22&chr=${chrom}&pos=${position}`,
      available: in_database && !!chrom && !!position,
    },
    {
      label: "SNPedia",
      url: `https://www.snpedia.com/index.php/Rs${rsidNum}`,
      available: true,
    },
    {
      label: "Google Scholar",
      url: `https://scholar.google.com/scholar?q=${rsid}&as_subj=bio`,
      available: true,
    },
  ];

  return links.filter((l) => l.available);
}

export default function SnpInfobox(props: SnpInfoboxProps) {
  const {
    rsid,
    chrom,
    position,
    ref_allele,
    alt_allele,
    gene,
    functional_class,
    maf_global,
    pathogenicity,
    clinvar,
    hgvs,
    population_frequencies,
  } = props;

  const links = externalLinks(props);

  const popEntries = population_frequencies
    ? ([
        ["African", population_frequencies.african],
        ["European", population_frequencies.european],
        ["East Asian", population_frequencies.east_asian],
        ["South Asian", population_frequencies.south_asian],
        ["Latino", population_frequencies.latino],
        ["Finnish", population_frequencies.finnish],
        ["Ashkenazi", population_frequencies.ashkenazi_jewish],
      ] as [string, number | null][]).filter(([, v]) => v != null)
    : [];

  return (
    <aside className="border border-border bg-surface/50 p-4 text-sm md:w-[280px] md:shrink-0">
      <h2 className="font-serif text-base font-semibold mb-3">Info</h2>

      <dl className="space-y-2 mb-5">
        {gene && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">Gene</dt>
            <dd>
              <a href={`/gene/${gene}`} className="font-medium text-accent hover:underline">{gene}</a>
              {props.gene_name && (
                <span className="block text-xs text-muted mt-0.5">{props.gene_name}</span>
              )}
            </dd>
          </div>
        )}
        {chrom && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">Chromosome</dt>
            <dd>{chrom}</dd>
          </div>
        )}
        {position != null && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">Position (GRCh37)</dt>
            <dd className="font-mono text-xs">{position.toLocaleString()}</dd>
          </div>
        )}
        {ref_allele && alt_allele && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">Alleles</dt>
            <dd className="font-mono">
              {ref_allele} / {alt_allele}
            </dd>
          </div>
        )}
        {maf_global !== null && maf_global !== undefined && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide" title="Minor Allele Frequency — how common the less frequent allele is across all populations worldwide (source: gnomAD)">
              Global MAF
            </dt>
            <dd>{maf_global.toFixed(3)}</dd>
          </div>
        )}
        {functional_class && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">
              Functional Class
            </dt>
            <dd className="capitalize">{functional_class.replace(/_/g, " ")}</dd>
          </div>
        )}
        {hgvs && (
          <div>
            <dt className="text-muted text-xs uppercase tracking-wide">HGVS Notation</dt>
            <dd className="font-mono text-xs break-all leading-relaxed">
              {hgvs.coding && <div>{hgvs.coding}</div>}
              {hgvs.protein && <div className="text-muted">{hgvs.protein}</div>}
            </dd>
          </div>
        )}
      </dl>

      {/* Pathogenicity Scores */}
      {pathogenicity && (
        <div className="mb-5">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
            Pathogenicity Scores
          </h3>
          <div className="space-y-2">
            {pathogenicity.cadd_phred != null && (
              <div>
                <div className="flex justify-between text-xs mb-0.5">
                  <a href="https://cadd.gs.washington.edu/" target="_blank" rel="noopener noreferrer" className="hover:text-accent underline decoration-dotted">CADD</a>
                  <span className="text-muted">
                    {pathogenicity.cadd_phred >= 20 ? "top 1%" : pathogenicity.cadd_phred >= 10 ? "top 10%" : "benign range"}
                  </span>
                </div>
                <CaddBar score={pathogenicity.cadd_phred} />
              </div>
            )}
            {pathogenicity.sift && (
              <div className="flex justify-between text-xs">
                <a href="https://sift.bii.a-star.edu.sg/" target="_blank" rel="noopener noreferrer" className="hover:text-accent underline decoration-dotted">SIFT</a>
                <span className={pathogenicity.sift.category === "deleterious" ? "text-red-700 font-medium" : "text-green-700"}>
                  {pathogenicity.sift.category} ({pathogenicity.sift.score.toFixed(3)})
                </span>
              </div>
            )}
            {pathogenicity.polyphen && (
              <div className="flex justify-between text-xs">
                <a href="http://genetics.bwh.harvard.edu/pph2/" target="_blank" rel="noopener noreferrer" className="hover:text-accent underline decoration-dotted">PolyPhen</a>
                <span className={
                  pathogenicity.polyphen.category === "probably_damaging" ? "text-red-700 font-medium" :
                  pathogenicity.polyphen.category === "possibly_damaging" ? "text-amber-700" : "text-green-700"
                }>
                  {pathogenicity.polyphen.category.replace(/_/g, " ")} ({pathogenicity.polyphen.score.toFixed(3)})
                </span>
              </div>
            )}
            {pathogenicity.revel_score != null && (
              <div className="flex justify-between text-xs">
                <a href="https://sites.google.com/site/revelgenomics/" target="_blank" rel="noopener noreferrer" className="hover:text-accent underline decoration-dotted">REVEL</a>
                <span className={
                  pathogenicity.revel_score >= 0.75 ? "text-red-700 font-medium" :
                  pathogenicity.revel_score >= 0.5 ? "text-amber-700" : "text-green-700"
                }>
                  {pathogenicity.revel_score.toFixed(3)}
                  {pathogenicity.revel_score >= 0.75 ? " (likely pathogenic)" :
                   pathogenicity.revel_score >= 0.5 ? " (uncertain)" : " (likely benign)"}
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Population Frequencies */}
      {popEntries.length > 0 && (
        <div className="mb-5">
          <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
            Population Frequencies
          </h3>
          <div className="space-y-1.5">
            {popEntries.map(([label, freq]) => (
              <PopFreqRow key={label} label={label} freq={freq!} />
            ))}
          </div>
          <p className="text-[10px] text-muted mt-1">Source: gnomAD v3</p>
        </div>
      )}

      {/* External Links */}
      <h3 className="text-xs uppercase tracking-wide text-muted mb-2">
        External Resources
      </h3>
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
              <svg
                className="w-3 h-3 opacity-50"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                strokeWidth={2}
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                />
              </svg>
            </a>
          </li>
        ))}
      </ul>
    </aside>
  );
}
