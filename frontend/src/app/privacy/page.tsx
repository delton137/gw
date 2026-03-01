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
          GeneWizard (&ldquo;we,&rdquo; &ldquo;us,&rdquo; or &ldquo;our&rdquo;)
          analyzes raw genetic data from direct-to-consumer genomics companies
          (23andMe, AncestryDNA) and whole-genome sequencing VCF files. This
          Privacy Policy describes how we collect, use, and protect your
          information when you use genewizard.ai (the &ldquo;Service&rdquo;).
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">
          Genetic Data &mdash; Raw Files Are Never Stored
        </h2>
        <p className="text-muted leading-relaxed mb-4">
          When you upload a genotype file, it is parsed entirely in memory. Your
          raw genetic data is never written to disk, never stored in a database,
          and is discarded immediately after processing. We do not retain your
          raw genotype file at any point.
        </p>
        <p className="text-muted leading-relaxed">
          This is a core design principle of GeneWizard, not an afterthought. We
          believe raw genetic data is too sensitive to persist, so the system was
          built from the ground up to operate without storing it.
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
          We use Vercel Analytics to collect anonymous usage data, including page
          views and general device information. This data does not include any
          genetic information and is used solely to understand how people use the
          Service and improve the experience.
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
            <strong>Improve the Service</strong> &mdash; fix bugs, enhance
            features, and optimize performance using aggregate, non-identifying
            metrics
          </li>
          <li>
            <strong>Communicate with you</strong> &mdash; respond to support
            requests or notify you of significant changes to the Service
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
        <p className="text-muted leading-relaxed">
          Raw genetic data is never retained. It is discarded from memory as
          soon as your analysis completes or fails.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">Security</h2>
        <p className="text-muted leading-relaxed">
          All data in transit is encrypted via HTTPS/TLS. Our database is
          encrypted at rest. Authentication is handled by Clerk with
          industry-standard security practices. While no system is perfectly
          secure, we take reasonable measures to protect your information and
          minimize the data we store in the first place.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">Your Rights</h2>
        <p className="text-muted leading-relaxed mb-4">You have the right to:</p>
        <ul className="list-disc pl-6 text-muted leading-relaxed space-y-2 mb-4">
          <li>
            <strong>Delete all your data</strong> &mdash; available at any time
            from your dashboard
          </li>
          <li>
            <strong>Access your results</strong> &mdash; all of your analysis
            results are available to you through the Service
          </li>
          <li>
            <strong>Download your results</strong> &mdash; PDF reports can be
            downloaded from your dashboard
          </li>
        </ul>
        <p className="text-muted leading-relaxed">
          If you are a resident of the European Economic Area, the United
          Kingdom, or California, you may have additional rights under GDPR or
          CCPA, including the right to request access to, correction of, or
          deletion of your personal information. To exercise these rights, please
          contact us at the address below.
        </p>
      </section>

      <section className="py-10 border-t border-border">
        <h2 className="font-serif text-2xl font-semibold mb-6">Children</h2>
        <p className="text-muted leading-relaxed">
          The Service is not intended for individuals under the age of 18. We do
          not knowingly collect personal information from minors. If you believe
          a minor has provided us with personal information, please contact us
          and we will delete it.
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
          If you have questions about this Privacy Policy or your data, please
          contact us at{" "}
          <span className="text-foreground font-medium">[email]</span>.
        </p>
      </section>
    </div>
  );
}
