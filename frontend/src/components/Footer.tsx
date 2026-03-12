import Link from "next/link";

export default function Footer() {
  return (
    <footer className="border-t border-border mt-24">
      <div className="mx-auto max-w-4xl px-6 py-8 flex items-center justify-between text-sm text-muted">
        <p>&copy; {new Date().getFullYear()} GeneWizard</p>
        <div className="flex gap-6">
          <Link href="/privacy" className="hover:text-foreground transition-colors">
            Privacy
          </Link>
        </div>
      </div>
    </footer>
  );
}
