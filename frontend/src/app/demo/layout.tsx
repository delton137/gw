import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Demo Results — Gene Wizard",
  description:
    "See what Gene Wizard analysis results look like with real whole genome sequencing data. Ancestry, polygenic risk scores, pharmacogenomics, carrier screening, and trait associations.",
};

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
