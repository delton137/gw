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
          When you upload a genotype file, it is parsed entirely in memory. Your
          raw genetic data is never written to disk, never stored in a database,
          and is discarded immediately after processing. However, results are saved to our 
          database. Your results can be deleted at any time by clicking the "Delete All My Data"
          button at the bottom of the <Link href="/dashboard" className="text-accent hover:underline">dashboard page</Link>.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Analysis Results We Store
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          After processing your upload, we store the following derived results
          linked to your account so you can access them later:
        </p>
        <ul className="list-disc pl-6 text-muted leading-relaxed space-y-2 mb-4">
          <li>Polygenic risk scores (PRS) with percentiles and confidence intervals</li>
          <li>Pharmacogenomic (PGx) diplotypes, phenotypes, and drug guidelines</li>
          <li>SNP-trait association matches</li>
          <li>Blood type determination</li>
          <li>Carrier screening results</li>
          <li>SNPedia variant matches</li>
          <li>Estimated genetic ancestry</li>
        </ul>
        <p className="text-muted leading-relaxed">
          These results are interpretive summaries, not raw genetic sequences.
          They are stored until you choose to delete them.
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
          , a third-party authentication provider. Clerk collects and manages
          your email address, name, and authentication credentials. We do not
          store passwords or authentication secrets directly. Please refer to
          Clerk&apos;s privacy policy for details on how they handle your account
          data.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Device &amp; Usage Information
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          We use a web analytics provider to collect anonymous usage data, including page
          views and general device information. This data does not include any
          genetic information and is used solely to understand how people use the
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
          results to any third party. Period.
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
          purposes. We may disclose information if required by law, but given
          that we do not retain raw genetic data, we are unlikely to be able to
          provide such data even if requested.
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
          All data in transit is encrypted via HTTPS/TLS. Our backend is HIPPA compliant.
           Authentication is handled by Clerk with  industry-standard security practices. 
           While no system is perfectly secure, we take reasonable measures to protect
           your information and minimize the data we store in the first place.
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
