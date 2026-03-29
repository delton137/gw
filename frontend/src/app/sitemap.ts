import type { MetadataRoute } from "next";
import { API_URL } from "@/lib/api";

const BASE_URL = "https://genewizard.net";
const PAGE_SIZE = 50_000;

// ID ranges:
//   0      = static pages
//   1–50   = SNP pages    (id 1 → SNP page 0, id 2 → SNP page 1, …)
//   51–100 = gene pages   (id 51 → gene page 0, id 52 → gene page 1, …)

export const revalidate = 86400; // regenerate daily

export async function generateSitemaps() {
  try {
    const [snpRes, geneRes] = await Promise.all([
      fetch(`${API_URL}/api/v1/sitemap/snps?page=0&size=1`, { cache: "no-store" }),
      fetch(`${API_URL}/api/v1/sitemap/genes?page=0&size=1`, { cache: "no-store" }),
    ]);
    const { total: snpTotal } = await snpRes.json();
    const { total: geneTotal } = await geneRes.json();

    const snpPages = Math.ceil(snpTotal / PAGE_SIZE);
    const genePages = Math.ceil(geneTotal / PAGE_SIZE);

    const ids: { id: number }[] = [{ id: 0 }];
    for (let i = 0; i < snpPages; i++) ids.push({ id: 1 + i });
    for (let i = 0; i < genePages; i++) ids.push({ id: 51 + i });
    return ids;
  } catch {
    return [{ id: 0 }]; // static pages only if backend unavailable
  }
}

export default async function sitemap({
  id,
}: {
  id: number;
}): Promise<MetadataRoute.Sitemap> {
  // --- Static pages ---
  if (id === 0) {
    return [
      { url: `${BASE_URL}/`, changeFrequency: "weekly", priority: 1.0 },
      { url: `${BASE_URL}/snp`, changeFrequency: "weekly", priority: 0.8 },
      { url: `${BASE_URL}/gene`, changeFrequency: "weekly", priority: 0.8 },
      { url: `${BASE_URL}/clinvar`, changeFrequency: "weekly", priority: 0.7 },
      { url: `${BASE_URL}/gwas`, changeFrequency: "weekly", priority: 0.7 },
      { url: `${BASE_URL}/about`, changeFrequency: "monthly", priority: 0.7 },
      { url: `${BASE_URL}/donate`, changeFrequency: "monthly", priority: 0.5 },
      { url: `${BASE_URL}/privacy`, changeFrequency: "monthly", priority: 0.3 },
      { url: `${BASE_URL}/demo`, changeFrequency: "monthly", priority: 0.6 },
      { url: `${BASE_URL}/demo/ancestry`, changeFrequency: "monthly", priority: 0.5 },
      { url: `${BASE_URL}/demo/prs`, changeFrequency: "monthly", priority: 0.5 },
      { url: `${BASE_URL}/demo/pgx`, changeFrequency: "monthly", priority: 0.5 },
      { url: `${BASE_URL}/demo/carrier`, changeFrequency: "monthly", priority: 0.5 },
      { url: `${BASE_URL}/demo/mysnps`, changeFrequency: "monthly", priority: 0.5 },
    ];
  }

  // --- SNP pages ---
  if (id >= 1 && id <= 50) {
    try {
      const res = await fetch(
        `${API_URL}/api/v1/sitemap/snps?page=${id - 1}&size=${PAGE_SIZE}`,
        { next: { revalidate: 86400 } }
      );
      if (!res.ok) return [];
      const { rsids }: { rsids: string[] } = await res.json();
      return rsids.map((rsid) => ({
        url: `${BASE_URL}/snp/${rsid}`,
        changeFrequency: "monthly" as const,
        priority: 0.6,
      }));
    } catch {
      return [];
    }
  }

  // --- Gene pages ---
  if (id >= 51 && id <= 100) {
    try {
      const res = await fetch(
        `${API_URL}/api/v1/sitemap/genes?page=${id - 51}&size=${PAGE_SIZE}`,
        { next: { revalidate: 86400 } }
      );
      if (!res.ok) return [];
      const { symbols }: { symbols: string[] } = await res.json();
      return symbols.map((symbol) => ({
        url: `${BASE_URL}/gene/${symbol}`,
        changeFrequency: "monthly" as const,
        priority: 0.5,
      }));
    } catch {
      return [];
    }
  }

  return [];
}
