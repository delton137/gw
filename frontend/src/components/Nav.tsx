"use client";

import { useState } from "react";
import Link from "next/link";
import { Show, UserButton } from "@clerk/nextjs";

export default function Nav() {
  const [open, setOpen] = useState(false);

  return (
    <nav className="border-b border-border">
      <div className="mx-auto max-w-4xl px-6 py-4 flex items-center justify-between">
        <Link href="/" className="font-serif text-xl font-semibold tracking-tight">
          Gene Wizard
        </Link>

        {/* Mobile hamburger */}
        <button
          onClick={() => setOpen(!open)}
          className="sm:hidden p-1 text-muted hover:text-foreground"
          aria-label="Toggle menu"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            {open
              ? <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              : <path strokeLinecap="round" strokeLinejoin="round" d="M4 6h16M4 12h16M4 18h16" />
            }
          </svg>
        </button>

        {/* Desktop links */}
        <div className="hidden sm:flex items-center gap-6 text-sm text-muted">
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

      {/* Mobile menu */}
      {open && (
        <div className="sm:hidden border-t border-border px-6 py-3 flex flex-col gap-3 text-sm text-muted">
          <Link href="/snp" className="hover:text-foreground" onClick={() => setOpen(false)}>Browse SNPs</Link>
          <Link href="/demo" className="hover:text-foreground" onClick={() => setOpen(false)}>Demo</Link>
          <Show
            when="signed-in"
            fallback={
              <>
                <Link href="/sign-in" className="hover:text-foreground" onClick={() => setOpen(false)}>Sign in</Link>
                <Link href="/sign-up" className="text-accent hover:text-accent-hover" onClick={() => setOpen(false)}>Get started</Link>
              </>
            }
          >
            <Link href="/dashboard" className="hover:text-foreground" onClick={() => setOpen(false)}>My Genome</Link>
            <Link href="/upload" className="hover:text-foreground" onClick={() => setOpen(false)}>Upload</Link>
            <UserButton />
          </Show>
        </div>
      )}
    </nav>
  );
}
