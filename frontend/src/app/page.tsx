import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl px-6">
      {/* Hero */}
      <section className="pt-24 pb-16">
        <h1 className="font-serif text-4xl font-semibold leading-tight mb-6">
          Understand your genetic risk, backed by the latest research
        </h1>
        <p className="text-lg text-muted leading-relaxed mb-8 max-w-2xl">
          Upload your raw genotype data from 23andMe or AncestryDNA. GeneWizard computes
          polygenic risk scores and matches your variants against a curated knowledge base
          of important SNPs.
        </p>
        <Link
          href="/sign-up"
          className="inline-block bg-accent text-white px-6 py-3 text-sm font-medium hover:bg-accent-hover transition-colors"
        >
          Get started
        </Link>
      </section>

      {/* Brief explanation */}
      <section className="py-16 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-4">
          What is a polygenic risk score?
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          A polygenic risk score (PRS) combines the effects of many genetic variants to
          estimate your relative risk for a trait or disease. Each variant contributes a
          small amount — the PRS aggregates thousands of these effects into a single number.
        </p>
        <p className="text-muted leading-relaxed">
          GeneWizard uses scores from the{" "}
          <a
            href="https://www.pgscatalog.org"
            className="text-accent hover:text-accent-hover underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            PGS Catalog
          </a>
          , the largest open database of published polygenic scores, and normalizes your
          result against reference populations so you can see where you fall.
        </p>
      </section>
    </div>
  );
}
