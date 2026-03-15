"use client";

import { useState } from "react";
import Link from "next/link";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function Footer() {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "submitting" | "success" | "error">("idle");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setState("submitting");
    try {
      const res = await fetch(`${API_URL}/api/v1/newsletter/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim() }),
      });
      if (res.ok) {
        setState("success");
        setEmail("");
      } else if (res.status === 429) {
        setState("error");
      } else {
        setState("error");
      }
    } catch {
      setState("error");
    }
  }

  return (
    <footer className="border-t border-border mt-24">
      <div className="mx-auto max-w-4xl px-6 py-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          <div className="text-sm text-muted">
            <p>&copy; {new Date().getFullYear()} Gene Wizard</p>
          </div>

          <form onSubmit={handleSubmit} className="flex items-center gap-2">
            {state === "success" ? (
              <p className="text-sm text-muted">Thanks! We&apos;ll be in touch.</p>
            ) : (
              <>
                <input
                  type="email"
                  required
                  placeholder="Get occasional updates"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (state === "error") setState("idle");
                  }}
                  className="h-8 w-48 rounded border border-border bg-transparent px-3 text-sm text-foreground placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-border"
                />
                <button
                  type="submit"
                  disabled={state === "submitting"}
                  className="h-8 rounded bg-foreground px-3 text-sm text-background transition-opacity hover:opacity-80 disabled:opacity-50"
                >
                  {state === "submitting" ? "..." : "Subscribe"}
                </button>
                {state === "error" && (
                  <span className="text-sm text-red-500">Try again later.</span>
                )}
              </>
            )}
          </form>

          <div className="flex gap-6 text-sm text-muted">
            <Link href="/privacy" className="hover:text-foreground transition-colors">
              Privacy Policy
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
