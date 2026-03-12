"use client";

import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";

export default function Nav() {
  return (
    <nav className="border-b border-border">
      <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-serif text-xl font-semibold tracking-tight">
          GeneWizard
        </Link>
        <div className="flex items-center gap-6 text-sm text-muted">
          <Link href="/snp" className="hover:text-foreground transition-colors">
            Browse SNPs
          </Link>
          <Link href="/demo" className="hover:text-foreground transition-colors">
            Demo
          </Link>
          <Show
            when="signed-in"
            fallback={
              <>
                <Link href="/sign-in" className="hover:text-foreground transition-colors">
                  Sign in
                </Link>
                <Link
                  href="/sign-up"
                  className="text-accent hover:text-accent-hover transition-colors"
                >
                  Get started
                </Link>
              </>
            }
          >
            <Link href="/dashboard" className="hover:text-foreground transition-colors">
              My Genome
            </Link>
            <Link href="/upload" className="hover:text-foreground transition-colors">
              Upload
            </Link>
            <UserButton />
          </Show>
        </div>
      </div>
    </nav>
  );
}
