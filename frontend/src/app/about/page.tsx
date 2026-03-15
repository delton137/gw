import Link from "next/link";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 pt-12 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-8">About Gene Wizard</h1>

      <div className="space-y-6 text-sm text-muted leading-relaxed">
        <p>
          Gene Wizard is a free, independent tool for interpreting raw genetic data from
          direct-to-consumer genomics companies like 23andMe and AncestryDNA, as well as
          whole genome sequencing (WGS) VCF files.
        </p>

        <p>
          Upload your raw data and Gene Wizard will auto-detect your file format and genotyping
          platform, estimate your genetic ancestry, compute polygenic risk scores with
          ancestry-aware normalization, match your variants against a curated SNP-trait knowledge
          base, infer pharmacogenomic star alleles with clinical drug guidelines, and screen for
          recessive carrier status.
        </p>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">Privacy</h2>
        <p>
          Your raw genetic data is never stored. Files are parsed in memory, analysis results
          are saved, and the raw genotype data is discarded immediately after processing. You can
          delete all of your data at any time from your account settings. See our{" "}
          <Link href="/privacy" className="text-accent hover:underline">
            privacy policy
          </Link>{" "}
          for full details.
        </p>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">How it works</h2>
        <ul className="list-disc list-inside space-y-1.5">
          <li>
            <strong className="text-foreground">Ancestry estimation</strong> — Maximum likelihood
            admixture analysis across 26 reference populations from the 1000 Genomes Project Phase 3,
            using techniques from the{" "}
            <a
              href="https://doi.org/10.1101/2024.06.18.599246"
              className="text-accent hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              AEon ancestry estimation tool
            </a>
          </li>
          <li>
            <strong className="text-foreground">Polygenic risk scores</strong> — Published scores
            from the{" "}
            <a
              href="https://www.pgscatalog.org"
              className="text-accent hover:underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              PGS Catalog
            </a>
            , normalized against ancestry-matched reference distributions
          </li>
          <li>
            <strong className="text-foreground">Pharmacogenomics</strong> — Star allele calling for
            76 genes with clinical prescribing guidelines from CPIC and DPWG
          </li>
          <li>
            <strong className="text-foreground">Trait associations</strong> — Curated SNP-trait
            associations from published GWAS and clinical literature
          </li>
          <li>
            <strong className="text-foreground">Carrier screening</strong> — Recessive carrier
            status for common genetic conditions
          </li>
        </ul>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">Limitations</h2>
        <p>
          Gene Wizard is an educational and research tool, not a clinical diagnostic.
          Results should not be used for medical decisions without consulting a healthcare
          professional. Polygenic risk scores and ancestry estimates are statistical
          approximations that depend on the coverage of your genotyping platform and the
          populations represented in current reference data.
        </p>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">Contact</h2>
        <p>
          Questions or feedback? Reach us at{" "}
          <a
            href="mailto:info@genewizard.net"
            className="text-accent hover:underline"
          >
            info@genewizard.net
          </a>
          .
        </p>
      </div>
    </div>
  );
}
