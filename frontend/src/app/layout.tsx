import type { Metadata } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { Analytics } from "@vercel/analytics/next";
import Nav from "@/components/Nav";
import Footer from "@/components/Footer";
import "./globals.css";

export const metadata: Metadata = {
  title: "genewizard.net — Understand your genetic risk",
  description:
    "Analyze your raw genetic data with polygenic risk scores and important SNPs backed by the latest research.",
  icons: {
    icon: { url: "/favicon.jpg", type: "image/jpeg" },
    apple: { url: "/favicon.jpg", type: "image/jpeg" },
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <ClerkProvider>
      <html lang="en">
        <body className="antialiased min-h-screen flex flex-col">
          <Nav />
          <main className="flex-1">{children}</main>
          <Footer />
          <Analytics />
        </body>
      </html>
    </ClerkProvider>
  );
}
