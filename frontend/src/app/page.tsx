"use client";

import Link from "next/link";
import { useAuth } from "@clerk/nextjs";

export default function Home() {
  const { isSignedIn } = useAuth();

  return (
    <div className="mx-auto max-w-4xl px-6">
      {/* Hero */}
      <section className="pt-12 sm:pt-24 pb-16 flex flex-col sm:flex-row items-center gap-8 sm:gap-16">
        <div className="flex-shrink-0">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/gene_wizard_logo.jpg"
            alt="GeneWizard"
            width={280}
            height={280}
            className="rounded-2xl w-48 sm:w-[280px]"
          />
        </div>
        <div className="text-center sm:text-left">
          <h1 className="font-serif text-2xl sm:text-4xl font-semibold leading-tight mb-4 sm:mb-6">
            Pioneering the future of whole genome interpretation
          </h1>
          <p className="text-base sm:text-lg text-muted leading-relaxed mb-6 sm:mb-8">
            Become a beta tester today.
          </p>
          <div className="flex justify-center sm:justify-start gap-4">
            <Link
              href={isSignedIn ? "/upload" : "/sign-up"}
              className="inline-block bg-accent text-white px-6 py-3 text-sm font-medium hover:bg-accent-hover transition-colors"
            >
              {isSignedIn ? "Upload your genome" : "Get started"}
            </Link>
            <Link
              href="/demo"
              className="inline-block border border-border px-6 py-3 text-sm font-medium hover:bg-gray-50 transition-colors"
            >
              See demo results
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
