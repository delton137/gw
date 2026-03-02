"use client";

import { useState } from "react";
import { SUPERPOP_META } from "@/lib/populations";

interface PrsDistributionChartProps {
  rawScore: number;
  refMean: number;
  refStd: number;
  percentile: number;
  traitName: string;
  ancestryGroup: string;
  nMatched: number;
  nTotal: number;
  absoluteRisk?: number | null;
  populationRisk?: number | null;
  prevalenceSource?: string | null;
  percentileLower?: number | null;
  percentileUpper?: number | null;
  coverageQuality?: string | null;
  reportedAuc?: number | null;
  publicationPmid?: string | null;
  publicationDoi?: string | null;
  pgsId?: string | null;
}


function percentileLabel(p: number): string {
  const rounded = Math.round(p);
  if (rounded === 0) return "<1st";
  if (rounded === 100) return ">99th";
  const suffix =
    rounded % 10 === 1 && rounded !== 11
      ? "st"
      : rounded % 10 === 2 && rounded !== 12
        ? "nd"
        : rounded % 10 === 3 && rounded !== 13
          ? "rd"
          : "th";
  return `${rounded}${suffix}`;
}

/** Approximate inverse normal CDF (Abramowitz & Stegun 26.2.23). */
function normPpf(p: number): number {
  if (p <= 0) return -10;
  if (p >= 1) return 10;
  if (p < 0.5) return -normPpf(1 - p);
  const t = Math.sqrt(-2 * Math.log(1 - p));
  return t - (2.515517 + 0.802853 * t + 0.010328 * t * t) /
    (1 + 1.432788 * t + 0.189269 * t * t + 0.001308 * t * t * t);
}

function riskCategory(percentile: number): {
  label: string;
  color: string;
  bgColor: string;
} {
  if (percentile >= 90) return { label: "High", color: "#b91c1c", bgColor: "#fef2f2" };
  if (percentile >= 75) return { label: "Elevated", color: "#b45309", bgColor: "#fffbeb" };
  if (percentile >= 25) return { label: "Average", color: "#6b7280", bgColor: "#f9fafb" };
  return { label: "Below Average", color: "#15803d", bgColor: "#f0fdf4" };
}

export default function PrsDistributionChart({
  rawScore,
  refMean,
  refStd,
  percentile,
  traitName,
  ancestryGroup,
  nMatched,
  nTotal,
  absoluteRisk,
  populationRisk,
  prevalenceSource,
  percentileLower,
  percentileUpper,
  coverageQuality,
  reportedAuc,
  publicationPmid,
  publicationDoi,
  pgsId,
}: PrsDistributionChartProps) {
  const [showDist, setShowDist] = useState(false);
  const risk = riskCategory(percentile);
  const relativeRisk =
    absoluteRisk != null && populationRisk != null && populationRisk > 0
      ? absoluteRisk / populationRisk
      : null;

  return (
    <div className="border border-border p-5">
      {/* Header row */}
      <div className="mb-1">
        <h3 className="text-base font-medium">{traitName}</h3>
        <div className="flex gap-2 mt-0.5">
          {pgsId && <a href={`https://www.pgscatalog.org/score/${pgsId}/`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-accent hover:underline">{pgsId}</a>}
          {reportedAuc != null && <span className="text-[10px] text-muted">AUC {reportedAuc.toFixed(2)}</span>}
          <span className="text-[10px] text-muted">{nTotal.toLocaleString()} variants</span>
          {publicationPmid && (
            <a href={`https://pubmed.ncbi.nlm.nih.gov/${publicationPmid}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-accent hover:underline">PubMed</a>
          )}
          {publicationDoi && (
            <a href={`https://doi.org/${publicationDoi}`} target="_blank" rel="noopener noreferrer" className="text-[10px] text-accent hover:underline">DOI</a>
          )}
        </div>
      </div>


      {relativeRisk != null && (
        <p className="text-lg font-semibold mb-0.5" style={{ color: risk.color }}>
          {relativeRisk >= 1
            ? `${relativeRisk.toFixed(1)}× higher risk than average`
            : `${(1 / relativeRisk).toFixed(1)}× lower risk than average`}
        </p>
      )}

      {/* ── Absolute Risk ── (only when data available) */}
      {absoluteRisk != null && populationRisk != null && (
        <div className="mt-6">
          <div className="flex justify-around">
            {/* Your genetics */}
            <div className="text-center">
              <p className="text-sm font-semibold mb-2">Of people with your genetics,</p>
              <div className="flex items-end gap-3">
                <div className="w-16 h-[106px] border border-gray-200 flex flex-col overflow-hidden">
                  <div
                    className="w-full"
                    style={{
                      height: `${(1 - absoluteRisk) * 100}%`,
                      backgroundColor: "#22c55e",
                    }}
                  />
                  <div
                    className="w-full"
                    style={{
                      height: `${absoluteRisk * 100}%`,
                      backgroundColor: "#1d4ed8",
                    }}
                  />
                </div>
                <div className="text-left text-sm">
                  <p style={{ color: "#22c55e" }} className="font-medium">
                    {((1 - absoluteRisk) * 100).toFixed(1)}%
                  </p>
                  <p className="text-muted text-xs">do not have trait</p>
                  <div className="mt-3" />
                  <p style={{ color: "#1d4ed8" }} className="font-medium">
                    {(absoluteRisk * 100).toFixed(1)}%
                  </p>
                  <p className="text-muted text-xs">have trait</p>
                </div>
              </div>
            </div>

            {/* General population */}
            <div className="text-center">
              <p className="text-sm font-semibold mb-2">In the general population,</p>
              <div className="flex items-end gap-3">
                <div className="w-16 h-[106px] border border-gray-200 flex flex-col overflow-hidden">
                  <div
                    className="w-full"
                    style={{
                      height: `${(1 - populationRisk) * 100}%`,
                      backgroundColor: "#22c55e",
                    }}
                  />
                  <div
                    className="w-full"
                    style={{
                      height: `${populationRisk * 100}%`,
                      backgroundColor: "#1d4ed8",
                    }}
                  />
                </div>
                <div className="text-left text-sm">
                  <p style={{ color: "#22c55e" }} className="font-medium">
                    {((1 - populationRisk) * 100).toFixed(1)}%
                  </p>
                  <p className="text-muted text-xs">do not have trait</p>
                  <div className="mt-3" />
                  <p style={{ color: "#1d4ed8" }} className="font-medium">
                    {(populationRisk * 100).toFixed(1)}%
                  </p>
                  <p className="text-muted text-xs">have trait</p>
                </div>
              </div>
            </div>
          </div>
          {prevalenceSource && (() => {
            const urlMatch = prevalenceSource.match(/(https?:\/\/\S+)/);
            const url = urlMatch ? urlMatch[1] : null;
            const label = prevalenceSource.replace(/(https?:\/\/\S+)/, "").trim();
            return (
              <p className="text-xs text-muted mt-3 text-center">
                Population prevalence: {label}
                {url && (
                  <>
                    {" "}
                    <a href={url} target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
                      Source
                    </a>
                  </>
                )}
              </p>
            );
          })()}
        </div>
      )}


      {/* Footer metadata */}
      <div className="flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-muted mt-4">
        <span>
          Normalized against 1000 Genomes {SUPERPOP_META[ancestryGroup]?.name || ancestryGroup}. {percentileLabel(percentile)} percentile{percentileLower != null && percentileUpper != null && ` (${percentileLabel(percentileLower)}\u2013${percentileLabel(percentileUpper)})`}. Raw score: {rawScore.toPrecision(4)}.
        </span>
        {reportedAuc != null && reportedAuc > 0.5 && populationRisk != null && populationRisk > 0 && (
          <button
            onClick={() => setShowDist(!showDist)}
            className="text-accent hover:underline"
          >
            {showDist ? "Hide distributions" : "Show distributions"}
          </button>
        )}
      </div>

      {/* Case/control distribution chart */}
      {showDist && reportedAuc != null && reportedAuc > 0.5 && populationRisk != null && populationRisk > 0 && (() => {
        const d = Math.SQRT2 * normPpf(reportedAuc);
        const K = populationRisk;
        const muCase = (1 - K) * d;
        const muControl = -K * d;
        const zUser = refStd > 0 ? (rawScore - refMean) / refStd : 0;

        const W = 500, H = 160, PAD_L = 10, PAD_R = 10, PAD_T = 10, PAD_B = 30;
        const plotW = W - PAD_L - PAD_R;
        const plotH = H - PAD_T - PAD_B;

        const xMin = Math.min(muControl - 3.5, zUser - 1);
        const xMax = Math.max(muCase + 3.5, zUser + 1);
        const steps = 200;

        const normPdf = (x: number, mu: number) =>
          Math.exp(-0.5 * (x - mu) ** 2) / Math.sqrt(2 * Math.PI);

        let maxY = 0;
        const controlPts: [number, number][] = [];
        const casePts: [number, number][] = [];
        const overallPts: [number, number][] = [];
        for (let i = 0; i <= steps; i++) {
          const x = xMin + (i / steps) * (xMax - xMin);
          const yCtrl = (1 - K) * normPdf(x, muControl);
          const yCase = K * normPdf(x, muCase);
          const yAll = yCtrl + yCase;
          controlPts.push([x, yCtrl]);
          casePts.push([x, yCase]);
          overallPts.push([x, yAll]);
          maxY = Math.max(maxY, yCtrl, yCase, yAll);
        }

        const toSvg = (x: number, y: number): [number, number] => [
          PAD_L + ((x - xMin) / (xMax - xMin)) * plotW,
          PAD_T + plotH - (y / maxY) * plotH,
        ];

        const pathD = (pts: [number, number][]) => {
          const svgPts = pts.map(([x, y]) => toSvg(x, y));
          return "M " + svgPts.map(([sx, sy]) => `${sx.toFixed(1)},${sy.toFixed(1)}`).join(" L ");
        };

        const [userSvgX] = toSvg(zUser, 0);

        return (
          <svg viewBox={`0 0 ${W} ${H}`} className="w-full max-w-lg mt-3 mx-auto" style={{ height: "auto" }}>
            <path d={pathD(overallPts)} fill="none" stroke="#9ca3af" strokeWidth="1.5" strokeDasharray="4,3" />
            <path d={pathD(controlPts)} fill="none" stroke="#22c55e" strokeWidth="2" />
            <path d={pathD(casePts)} fill="none" stroke="#1d4ed8" strokeWidth="2" />
            <line
              x1={userSvgX} y1={PAD_T}
              x2={userSvgX} y2={PAD_T + plotH}
              stroke={risk.color} strokeWidth="2" strokeDasharray="4,3"
            />
            <line
              x1={PAD_L} y1={PAD_T + plotH}
              x2={PAD_L + plotW} y2={PAD_T + plotH}
              stroke="#d1d5db" strokeWidth="1"
            />
            <text x={userSvgX} y={PAD_T + plotH + 14} textAnchor="middle" fontSize="10" fill={risk.color}>You</text>
            <g style={{ cursor: "help" }}>
              <title>{"Scores for people who haven\u2019t gotten this condition"}</title>
              <line x1={PAD_L} y1={H - 6} x2={PAD_L + 16} y2={H - 6} stroke="#22c55e" strokeWidth="2" />
              <text x={PAD_L + 20} y={H - 2} fontSize="10" fill="#6b7280">Controls</text>
            </g>
            <g style={{ cursor: "help" }}>
              <title>{"Scores for people who got this condition"}</title>
              <line x1={PAD_L + 80} y1={H - 6} x2={PAD_L + 96} y2={H - 6} stroke="#1d4ed8" strokeWidth="2" />
              <text x={PAD_L + 100} y={H - 2} fontSize="10" fill="#6b7280">Cases</text>
            </g>
            <g style={{ cursor: "help" }}>
              <title>{"Combined distribution of all scores"}</title>
              <line x1={PAD_L + 148} y1={H - 6} x2={PAD_L + 164} y2={H - 6} stroke="#9ca3af" strokeWidth="1.5" strokeDasharray="4,3" />
              <text x={PAD_L + 168} y={H - 2} fontSize="10" fill="#6b7280">Overall</text>
            </g>
          </svg>
        );
      })()}
    </div>
  );
}
