import Link from "next/link";
import type {
  Analysis,
  CarrierStatusResult,
  PgxResult,
  TraitHit,
} from "@/lib/types";

interface DashboardContentProps {
  analysis: Analysis | null;
  traitHits: TraitHit[];
  uniqueSnpsMatched: number;
  totalSnpsInKb: number;
  pgxResults: PgxResult[];
  carrierStatus: CarrierStatusResult | null;
  clinvarTotal: number;
  prsStatus: "computing" | "failed" | "ready" | null;
  prsCount: number;
  prsDetail: string | null;
  prsError: string | null;
  variantsTotal: number;
  snpediaTotal: number;
  // Link prefix for demo mode — defaults to "" (e.g., "/demo" makes links go to /demo/pgx)
  linkPrefix?: string;
  // Dashboard-only actions — omit to hide the actions section
  onDownloadReport?: () => void;
  downloadingReport?: boolean;
  onDownloadPgxReport?: () => void;
  downloadingPgxReport?: boolean;
  onDeleteData?: () => void;
}

export default function DashboardContent({
  analysis,
  traitHits,
  uniqueSnpsMatched,
  totalSnpsInKb,
  pgxResults,
  carrierStatus,
  clinvarTotal,
  prsStatus,
  prsCount,
  prsDetail,
  prsError,
  variantsTotal,
  snpediaTotal,
  linkPrefix = "",
  onDownloadReport,
  downloadingReport,
  onDownloadPgxReport,
  downloadingPgxReport,
  onDeleteData,
}: DashboardContentProps) {
  return (
    <>
      {/* File summary */}
      <div className="border border-border p-5 mb-12 flex flex-wrap items-baseline gap-x-8 gap-y-2">
        {analysis?.filename && (
          <div>
            <p className="text-xs text-muted mb-0.5">Filename</p>
            <p className="text-sm font-medium truncate max-w-xs" title={analysis.filename}>{analysis.filename}</p>
          </div>
        )}
        <div>
          <p className="text-xs text-muted mb-0.5">File Type</p>
          <p className="text-sm font-medium">{analysis?.chip_type || "\u2014"}</p>
        </div>
        <div>
          <p className="text-xs text-muted mb-0.5">Variants Read From File</p>
          <p className="text-sm font-medium">{analysis?.variant_count?.toLocaleString() || "\u2014"}</p>
        </div>
        <div>
          <p className="text-xs text-muted mb-0.5">Genome Build</p>
          <p className="text-sm font-medium">{analysis?.genome_build || "\u2014"}</p>
        </div>
        {analysis?.is_imputed && (
          <div>
            <p className="text-xs text-muted mb-0.5">Data Type</p>
            <p className="text-sm font-medium">Imputed genome</p>
          </div>
        )}
        {analysis?.pipeline_fast_seconds != null && (
          <div>
            <p className="text-xs text-muted mb-0.5">Pipeline Runtime</p>
            <p className="text-sm font-medium">{analysis.pipeline_fast_seconds.toFixed(1)}s</p>
          </div>
        )}
      </div>

      {/* Card grid */}
      <div className="grid grid-cols-1 gap-6 mb-12">
        {/* SNP Summary */}
        {(traitHits.length > 0 || variantsTotal > 0) && (
          <div className="border border-border p-5">
            <h2 className="font-serif text-xl font-semibold mb-2">Curated SNPs</h2>
            {traitHits.length > 0 && (
              <p className="text-sm text-muted mb-2">
                Found <span className="font-semibold text-foreground">{uniqueSnpsMatched}</span> out of <span className="font-semibold text-foreground">{totalSnpsInKb}</span> important SNPs.
              </p>
            )}
            {variantsTotal > 0 && (
              <p className="text-sm text-muted mb-2">
                <span className="font-semibold text-foreground">{variantsTotal.toLocaleString()}</span>{" "}
                SNPedia variants found
                {snpediaTotal > 0 && (
                  <> out of <span className="font-semibold text-foreground">{snpediaTotal.toLocaleString()}</span></>
                )}
              </p>
            )}
            <Link
              href={`${linkPrefix}/mysnps`}
              className="inline-block text-sm font-medium text-accent hover:underline mt-1"
            >
              View all SNP results &rarr;
            </Link>
          </div>
        )}

        {/* Pharmacogenomics Summary */}
        {pgxResults.length > 0 && (
          <div className="border border-border p-5">
            <h2 className="font-serif text-xl font-semibold mb-2">
              Pharmacogenomics
            </h2>
            <p className="text-sm text-muted mb-3">
              <span className="font-semibold text-foreground">{pgxResults.length}</span> genes analyzed
            </p>
            <Link
              href={`${linkPrefix}/pgx`}
              className="inline-block text-sm font-medium text-accent hover:underline"
            >
              View pharmacogenomics results &rarr;
            </Link>
          </div>
        )}

        {/* ClinVar Summary */}
        {clinvarTotal > 0 && (
          <div className="border border-border p-5">
            <h2 className="font-serif text-xl font-semibold mb-2">ClinVar Annotations</h2>
            <p className="text-sm text-muted mb-2">
              <span className="font-semibold text-foreground">{clinvarTotal.toLocaleString()}</span> of your variants have ClinVar annotations
            </p>
            <Link
              href={`${linkPrefix}/clinvar`}
              className="inline-block text-sm font-medium text-accent hover:underline mt-1"
            >
              View ClinVar annotations &rarr;
            </Link>
          </div>
        )}

        {/* Carrier Status Card */}
        {carrierStatus && (
          <div className="border border-border p-5">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h2 className="font-serif text-xl font-semibold mb-1">
                  Carrier Screening
                  <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
                    Experimental
                  </span>
                </h2>
                <p className="text-sm text-muted">
                  {carrierStatus.n_genes_screened} genes analyzed
                  {carrierStatus.n_carrier_genes === 0 && carrierStatus.n_affected_flags === 0 && (
                    <span className="ml-2 text-gray-400">&mdash; no carrier variants detected</span>
                  )}
                </p>
              </div>
              {carrierStatus.n_carrier_genes === 0 && carrierStatus.n_affected_flags === 0 ? null
              : carrierStatus.n_affected_flags > 0 ? (
                <span className="text-xs px-2 py-0.5 rounded-full bg-red-50 text-red-700">
                  Action recommended
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded-full bg-amber-50 text-amber-700">
                  {carrierStatus.n_carrier_genes} carrier gene{carrierStatus.n_carrier_genes !== 1 ? "s" : ""}
                </span>
              )}
            </div>
            {(carrierStatus.n_carrier_genes > 0 || carrierStatus.n_affected_flags > 0) && (
              <div className="space-y-1 mb-3">
                {Object.values(carrierStatus.results_json)
                  .filter((g) => g.status !== "not_detected")
                  .map((g) => (
                    <div key={g.gene} className="flex items-center gap-2 text-sm">
                      <span className={`inline-block w-2 h-2 rounded-full ${
                        g.status === "carrier" ? "bg-amber-500"
                        : g.status === "likely_affected" ? "bg-red-500"
                        : "bg-red-500"
                      }`} />
                      <span className="font-mono text-xs text-foreground">{g.gene}</span>
                      <span className="text-muted">&mdash; {g.condition}</span>
                      <span className={`text-xs ${
                        g.status === "carrier" ? "text-amber-700"
                        : "text-red-700"
                      }`}>
                        ({g.status.replace(/_/g, " ")})
                      </span>
                    </div>
                  ))}
              </div>
            )}
            <Link
              href={`${linkPrefix}/carrier`}
              className="inline-block text-sm font-medium text-accent hover:underline"
            >
              View carrier status details &rarr;
            </Link>
          </div>
        )}

        {/* PRS Status Card */}
        <div className="border border-border p-5">
          <h2 className="font-serif text-xl font-semibold mb-2">
            Polygenic Risk Scores
            <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
              Experimental
            </span>
          </h2>
          {prsStatus === "computing" && (
            <div>
              <div className="flex items-center gap-2 text-sm text-muted">
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
                Computing PRS scores... This may take a few minutes.
              </div>
              {prsDetail && (
                <p className="text-xs text-muted mt-1.5 ml-6">{prsDetail}</p>
              )}
            </div>
          )}
          {prsStatus === "failed" && (
            <div className="text-sm">
              <p className="text-risk-high mb-1">PRS computation failed.</p>
              {prsError && <p className="text-xs text-muted">{prsError}</p>}
            </div>
          )}
          {prsStatus === "ready" && (
            <div>
              <p className="text-sm text-muted mb-3">
                <span className="font-semibold text-foreground">{prsCount}</span> polygenic risk score{prsCount !== 1 ? "s" : ""} computed
              </p>
              <Link
                href={`${linkPrefix}/prs`}
                className="inline-block text-sm font-medium text-accent hover:underline"
              >
                View PRS results &rarr;
              </Link>
            </div>
          )}
        </div>

      </div>

      {/* Actions: Download Report & Delete Data — only when callbacks provided */}
      {onDownloadReport && (
        <section className="border-t border-border pt-8 mt-8">
          <div className="flex flex-wrap gap-4 items-center">
            <button
              onClick={onDownloadReport}
              disabled={downloadingReport}
              className="px-5 py-2.5 text-sm font-medium border border-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {downloadingReport ? "Generating PDF..." : "Download Report"}
            </button>

            {pgxResults.length > 0 && onDownloadPgxReport && (
              <button
                onClick={onDownloadPgxReport}
                disabled={downloadingPgxReport}
                className="px-5 py-2.5 text-sm font-medium border border-border hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {downloadingPgxReport ? "Generating PDF..." : "Download PharmGen Report"}
              </button>
            )}

            {onDeleteData && (
              <button
                onClick={onDeleteData}
                className="px-5 py-2.5 text-sm font-medium text-red-600 border border-red-200 hover:bg-red-50 transition-colors"
              >
                Delete All My Data
              </button>
            )}
          </div>
          <p className="text-xs text-muted mt-3">
            Your raw genetic file was never stored. Deleting your data removes all
            analysis results, scores, and trait matches from our servers permanently.
          </p>
        </section>
      )}

      {/* Version info — only for authenticated dashboard */}
      {onDownloadReport && (
        <p className="mt-8 text-center text-[11px] text-gray-400">Gene Wizard v0.9.0 &middot; Updated {process.env.NEXT_PUBLIC_BUILD_DATE}</p>
      )}
    </>
  );
}
