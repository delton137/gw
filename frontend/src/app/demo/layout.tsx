import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Demo Results — GeneWizard",
  description:
    "See what GeneWizard analysis results look like with real whole genome sequencing data. Ancestry, polygenic risk scores, pharmacogenomics, carrier screening, and trait associations.",
};

export default function DemoLayout({ children }: { children: React.ReactNode }) {
  return children;
}
