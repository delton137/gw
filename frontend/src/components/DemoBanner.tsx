import Link from "next/link";

export default function DemoBanner() {
  return (
    <div className="bg-accent/5 border border-accent/20 rounded px-4 py-3 mb-6 flex items-center justify-between">
      <span className="text-sm text-muted">Viewing sample analysis results</span>
      <Link href="/demo" className="text-sm text-accent hover:underline">
        &larr; Back to demo dashboard
      </Link>
    </div>
  );
}
