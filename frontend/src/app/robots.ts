import type { MetadataRoute } from "next";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: {
      userAgent: "*",
      allow: "/",
      disallow: [
        "/dashboard",
        "/upload",
        "/ancestry",
        "/prs",
        "/pgx",
        "/carrier",
        "/mysnps",
        "/auth-redirect",
        "/sign-in",
        "/sign-up",
      ],
    },
    sitemap: "https://genewizard.net/sitemap.xml",
  };
}
