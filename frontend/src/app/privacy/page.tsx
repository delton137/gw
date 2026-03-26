"use client";

import Link from "next/link";
import ObfuscatedEmail from "@/components/ObfuscatedEmail";

export default function PrivacyPolicy() {
  return (
    <div className="mx-auto max-w-3xl px-6">
      <section className="pt-24 pb-16">
        <h1 className="font-serif text-4xl font-semibold leading-tight mb-6">
          Privacy Policy
        </h1>
        <p className="text-sm text-muted">Last updated: February 28, 2025</p>
      </section>

      <section className="py-10 border-t border-border">
        <p className="text-muted leading-relaxed mb-4">
          Gene Wizard (&ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;)
          analyzes raw genetic data from direct-to-consumer genomics companies
          (23andMe, AncestryDNA) and whole-genome sequencing VCF files. This
          Privacy Policy describes how we collect, use, and protect your
          information when you use genewizard.net (the &ldquo;Service&rdquo;).
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          The file you upload is never stored, but your results are
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          When you upload a genotype file, it is parsed entirely in memory. The file you upload is never written to disk, and is discarded immediately after processing. However, your results are saved to our 
          database, including your key SNPs, predicted pharmacogenomic phenotypes, and polygenic risk scores. Your results can be deleted at any time by clicking the "Delete All My Data" button at the bottom of the <Link href="/dashboard" className="text-accent hover:underline">dashboard page</Link>.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Account Information
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          Authentication is handled by{" "}
          <a
            href="https://clerk.com/privacy"
            className="text-accent hover:text-accent-hover underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            Clerk
          </a>
          , a third-party authentication provider. Clerk collects and manages your authentication credentials, which may include your email address, if you elect to provide it for account recovery. If you provide your email Gene Wizard is able to view it but we never share user's emails. 
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Device &amp; Usage Information
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          We use a web analytics provider to collect anonymous usage data, including page views and general device information. This data does not include any  genetic information and is used solely to understand how people use the
          service.
        </p>
        <p className="text-muted leading-relaxed">
          We do not use third-party advertising trackers or sell usage data.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          How We Use Your Information
        </h2>
        <ul className="list-disc pl-6 text-muted leading-relaxed space-y-2">
          <li>
            <strong>Generate your analysis results</strong> &mdash; the primary
            purpose of the Service
          </li>
          <li>
            <strong>Communicate with you</strong> &mdash; to respond to support
            requests, when given permission to look at your data.
          </li>
        </ul>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Data Sharing
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          We do not sell, share, or provide your genetic information or analysis
          results to any third party. 
        </p>
        <p className="text-muted leading-relaxed mb-4">
          We use the following service providers to operate the Service:
        </p>
        <ul className="list-disc pl-6 text-muted leading-relaxed space-y-2 mb-4">
          <li>
            <strong>Clerk</strong> &mdash; authentication and account management
          </li>
          <li>
            <strong>Vercel</strong> &mdash; frontend hosting and analytics
          </li>
          <li>
            <strong>Railway</strong> &mdash; backend hosting and database 
          </li>
        </ul>
        <p className="text-muted leading-relaxed">
          These providers process data only as necessary to deliver the Service
          and are contractually prohibited from using your data for their own
          purposes. 
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Data Retention &amp; Deletion
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          Your analysis results are retained until you delete them. You can
          permanently delete all of your data at any time from your dashboard.
          Deletion is immediate and irreversible &mdash; we do not retain backup
          copies of individual user data.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">Security</h2>
        <p className="text-muted leading-relaxed">
          All data in transit is encrypted via HTTPS/TLS. Authentication is handled by Clerk with industry-standard security practices. While no system is perfectly secure, we strive to make our platform as secure as possible.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">Children</h2>
        <p className="text-muted leading-relaxed">
          This service is not intended for individuals under the age of 18. We do
          not knowingly collect personal information from minors. If you believe
          a minor has provided us with personal information, contact us and we will delete it.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Changes to This Policy
        </h2>
        <p className="text-muted leading-relaxed">
          We may update this Privacy Policy from time to time. If we make
          material changes, we will notify you by updating the date at the top
          of this page. Your continued use of the Service after changes are
          posted constitutes acceptance of the updated policy.
        </p>
      </section>

      <section className="py-10 border-t border-border mb-16">
        <h2 className="font-serif text-2xl font-semibold mb-6">Contact Us</h2>
        <p className="text-muted leading-relaxed">
          If you have questions about this Privacy Policy or anything else, please
          contact us <ObfuscatedEmail />.
        </p>
      </section>
    </div>
  );
}
