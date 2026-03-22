export default function DonatePage() {
  return (
    <div className="mx-auto max-w-3xl px-6 pt-12 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-8">Support Gene Wizard</h1>

      <div className="space-y-6 text-sm text-foreground leading-relaxed">
        <p>
          Gene Wizard is a free, independent project built and maintained by a single developer.
          If you find it useful, please consider supporting its continued development.
        </p>

        <div className="border border-border bg-surface p-8 text-center">
          <h2 className="font-serif text-xl font-semibold mb-3">Buy Me a Coffee</h2>
          <p className="text-muted mb-6">
            One-time or recurring contributions help cover server costs and fund new features.
          </p>
          <a
            href="https://www.buymeacoffee.com/moreisdifferent"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block bg-accent text-white px-6 py-2.5 text-sm font-medium hover:bg-accent-hover transition-colors"
          >
            Buy me a coffee
          </a>
        </div>
      </div>
    </div>
  );
}
