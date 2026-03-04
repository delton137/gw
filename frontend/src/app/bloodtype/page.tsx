"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import Link from "next/link";
import { apiFetch } from "@/lib/api";
import type { BloodTypeResult } from "@/lib/types";

interface BloodTypeResponse {
  analysis_id: string;
  result: BloodTypeResult | null;
}

export default function BloodTypePage() {
  const { userId, getToken } = useAuth();
  const [bt, setBt] = useState<BloodTypeResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      if (!userId) return;
      try {
        const token = await getToken();
        const resp = await apiFetch<BloodTypeResponse>(
          `/api/v1/results/blood-type/${userId}`,
          {},
          token,
        );
        setBt(resp.result);
      } catch {
        // API unavailable or no results
      } finally {
        setLoading(false);
      }
    }
    if (userId) load();
  }, [userId, getToken]);

  if (!userId) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Please sign in to view your blood type results.</p>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <p className="text-muted">Loading...</p>
      </div>
    );
  }

  if (!bt) {
    return (
      <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
        <div className="flex items-start justify-between mb-2">
          <h1 className="font-serif text-3xl font-semibold">Blood Type</h1>
          <Link href="/dashboard" className="text-sm text-accent hover:underline mt-2">
            &larr; Dashboard
          </Link>
        </div>
        <div className="border border-border p-12 text-center mt-8">
          <p className="text-muted mb-4">No blood type results yet.</p>
          <Link href="/upload" className="text-accent hover:underline text-sm">
            Upload your genotype file to get started
          </Link>
        </div>
      </div>
    );
  }

  // Build systems list
  const systems: { label: string; value: string }[] = [];
  const coreKeys = new Set(["ABO"]);
  if (bt.systems) {
    for (const [name, data] of Object.entries(bt.systems)) {
      if (coreKeys.has(name)) continue;
      const val = data.phenotype || data.genotype;
      if (val) systems.push({ label: name, value: val });
    }
  } else {
    if (bt.rh_e_antigen) systems.push({ label: "Rh E/e", value: bt.rh_e_antigen });
    if (bt.rh_c_antigen) systems.push({ label: "Rh C/c", value: bt.rh_c_antigen });
    if (bt.rh_cw_antigen !== null) systems.push({ label: "Rh Cw", value: bt.rh_cw_antigen ? "+" : "-" });
    if (bt.kell_phenotype) systems.push({ label: "Kell", value: bt.kell_phenotype });
    if (bt.mns_phenotype) systems.push({ label: "MNS", value: bt.mns_phenotype });
    if (bt.duffy_phenotype) systems.push({ label: "Duffy", value: bt.duffy_phenotype });
    if (bt.kidd_phenotype) systems.push({ label: "Kidd", value: bt.kidd_phenotype });
    if (bt.secretor_status) systems.push({ label: "Secretor", value: bt.secretor_status });
  }

  return (
    <div className="mx-auto max-w-4xl px-6 pt-8 pb-16">
      <div className="flex items-start justify-between mb-2">
        <h1 className="font-serif text-3xl font-semibold">
          Blood Type
          <span className="ml-2 align-middle inline-block text-[10px] font-sans font-semibold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 uppercase tracking-wide">
            Experimental
          </span>
        </h1>
        <Link href="/dashboard" className="text-sm text-accent hover:underline mt-2">
          &larr; Dashboard
        </Link>
      </div>

      {/* Main result */}
      <div className="border border-border p-6 mt-6 mb-8">
        <div className="flex items-baseline gap-4 mb-3">
          <span className="font-serif text-5xl font-bold tracking-tight">{bt.display_type}</span>
          <span className={`text-xs px-2 py-0.5 rounded-full ${
            bt.confidence === "high"
              ? "bg-green-50 text-green-700"
              : bt.confidence === "medium"
              ? "bg-yellow-50 text-yellow-700"
              : "bg-red-50 text-red-700"
          }`}>
            {bt.confidence} confidence
          </span>
        </div>
        <p className="text-sm text-muted">
          ABO genotype: <span className="font-mono font-medium text-foreground">{bt.abo_genotype}</span>
        </p>
      </div>

      {/* Blood group systems */}
      {systems.length > 0 && (
        <section className="mb-8">
          <h2 className="font-serif text-xl font-semibold mb-3">Blood Group Systems</h2>
          <p className="text-sm text-muted mb-4">
            {bt.n_systems_determined > 0
              ? <><span className="font-semibold text-foreground">{bt.n_systems_determined}</span> blood group systems determined</>
              : "Blood group systems determined"
            }
          </p>
          <div className="border border-border overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left">
                  <th className="px-4 py-2 font-medium text-muted">System</th>
                  <th className="px-4 py-2 font-medium text-muted">Phenotype</th>
                </tr>
              </thead>
              <tbody>
                {systems.map((s) => (
                  <tr key={s.label} className="border-b border-border last:border-0">
                    <td className="px-4 py-2 font-medium">{s.label}</td>
                    <td className="px-4 py-2 font-mono">{s.value}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* Coverage & methodology */}
      <section className="mb-8">
        <h2 className="font-serif text-xl font-semibold mb-3">Methodology</h2>
        <div className="border border-border p-4 text-sm text-muted leading-relaxed space-y-2">
          <p>
            <strong className="text-foreground">Reference database:</strong>{" "}
            Allele definitions from{" "}
            <a href="https://github.com/limcintyre/RBCeq2" target="_blank" rel="noopener noreferrer" className="text-accent hover:underline">
              RBCeq2
            </a>{" "}
            v2.4.1 (Australian Red Cross Lifeblood, MIT License), a curated database of blood group
            allele definitions based on the ISBT (International Society of Blood Transfusion) classification.
            Blood group phenotypes are inferred by matching your genotype data against these allele definitions
            using position-based variant matching.
          </p>
          <p>
            <strong className="text-foreground">Coverage:</strong>{" "}
            {bt.n_variants_tested} of {bt.n_variants_total} blood group variant positions detected in your data.
          </p>
          <p>
            <strong className="text-foreground">Rh D status:</strong>{" "}
            Rh D +/- cannot be determined from SNP data &mdash; requires gene deletion testing (RHD whole-gene deletion).
          </p>
          {bt.computed_at && (
            <p>
              <strong className="text-foreground">Computed:</strong>{" "}
              {new Date(bt.computed_at).toLocaleDateString()}
            </p>
          )}
        </div>
      </section>

      {/* Disclaimer */}
      <div className="border border-amber-200 bg-amber-50/50 p-4 text-sm text-muted leading-relaxed mb-8">
        <p className="font-semibold text-foreground mb-1">Disclaimer</p>
        <p>
          Blood type estimation from genetic data is informational only and should not be used
          for medical decisions including transfusions. Always confirm blood type through
          standard serological testing performed by a qualified laboratory.
        </p>
      </div>

      <Link
        href="/dashboard"
        className="inline-block text-sm text-accent hover:underline"
      >
        &larr; Back to dashboard
      </Link>
    </div>
  );
}
