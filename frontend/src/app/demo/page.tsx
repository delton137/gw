import Link from "next/link";
import DashboardContent from "@/components/DashboardContent";
import {
  DEMO_ANALYSIS,
  DEMO_PRS,
  DEMO_TRAITS,
  DEMO_PGX,
  DEMO_CARRIER,
  DEMO_VARIANTS_SUMMARY,
  DEMO_CLINVAR_SUMMARY,
} from "./demoData";

export default function DemoPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      {/* Demo header */}
      <div className="mb-10">
        <h1 className="font-serif text-3xl font-semibold mb-2">
          Sample Analysis Results
        </h1>
        <p className="text-sm text-muted mb-4">
          Real results from a whole genome sequencing analysis of ~4 million variants.
          This is what your dashboard will look like after uploading your genetic data.
        </p>
        <Link
          href="/sign-up"
          className="inline-block px-5 py-2.5 text-sm font-medium bg-foreground text-background hover:opacity-90 transition-opacity"
        >
          Analyze your own genome
        </Link>
      </div>

      <DashboardContent
        analysis={DEMO_ANALYSIS}
        traitHits={DEMO_TRAITS.hits}
        uniqueSnpsMatched={DEMO_TRAITS.unique_snps_matched}
        totalSnpsInKb={DEMO_TRAITS.total_snps_in_kb}
        pgxResults={DEMO_PGX}
        carrierStatus={DEMO_CARRIER}
        clinvarTotal={DEMO_CLINVAR_SUMMARY.total}
        prsStatus="ready"
        prsCount={DEMO_PRS.results.length}
        prsDetail={null}
        prsError={null}
        variantsTotal={DEMO_VARIANTS_SUMMARY.total}
        snpediaTotal={DEMO_VARIANTS_SUMMARY.snpedia_total}
      />

      {/* CTA footer */}
      <section className="border-t border-border pt-10 mt-8 text-center">
        <h2 className="font-serif text-2xl font-semibold mb-3">Analyze Your Own Genome</h2>
        <p className="text-sm text-muted mb-6 max-w-lg mx-auto">
          Upload your 23andMe, AncestryDNA, or whole genome sequencing (VCF) file
          to get a comprehensive analysis like this one. Your raw genetic data is never stored.
        </p>
        <div className="flex gap-4 justify-center">
          <Link
            href="/sign-up"
            className="px-6 py-3 text-sm font-medium bg-foreground text-background hover:opacity-90 transition-opacity"
          >
            Sign up free
          </Link>
          <Link
            href="/"
            className="px-6 py-3 text-sm font-medium border border-border hover:bg-gray-50 transition-colors"
          >
            Learn more
          </Link>
        </div>
      </section>
    </div>
  );
}
