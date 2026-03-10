import Link from "next/link";

export default function Home() {
  return (
    <div className="mx-auto max-w-3xl px-6">
      {/* Hero */}
      <section className="pt-24 pb-16">
        <h1 className="font-serif text-4xl font-semibold leading-tight mb-6">
          Pioneering the future of whole genome interpretation
        </h1>
        <p className="text-lg text-muted leading-relaxed mb-8 max-w-2xl">
          Become a beta tester today.
        </p>
        <div className="flex gap-4">
          <Link
            href="/sign-up"
            className="inline-block bg-accent text-white px-6 py-3 text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Get started
          </Link>
          <Link
            href="/demo"
            className="inline-block border border-border px-6 py-3 text-sm font-medium hover:bg-gray-50 transition-colors"
          >
            See demo results
          </Link>
        </div>
      </section>

    </div>
  );
}
