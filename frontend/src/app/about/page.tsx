"use client";

import Link from "next/link";
import ObfuscatedEmail from "@/components/ObfuscatedEmail";

export default function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-6 pt-12 pb-16">
      <h1 className="font-serif text-3xl font-semibold mb-8">About</h1>

      <div className="space-y-6 text-sm text-foreground leading-relaxed">
        <p>
          Hello! My name is Dan Elton. I originally studied physics (Ph.D., 2016), and later
          was a Staff Scientist at the National Human Genome Research Institute.
        </p>
        <p>
          I was first inspired to create Gene Wizard after realizing that{" "}
          <a href="https://www.promethease.com" className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">Promethease</a>
          {" "}and{" "}
          <a href="https://www.snpedia.com" className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">SNPedia</a>
          {" "}have not been updated since late 2019. My long term vision for Gene Wizard is to create a
          replacement for both. In addition, Gene Wizard moves beyond SNPs to polygenic analysis,
          including polygenic scores from the{" "}
          <a href="https://www.pgscatalog.org/" className="text-accent hover:underline" target="_blank" rel="noopener noreferrer">Polygenic Score Catalog</a>.
        </p>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">Core values</h2>

        <h3 className="font-serif text-lg font-medium text-foreground pt-2">Honesty</h3>
        <p>
          I strive to be honest about what consumer genetics and current science can and can&apos;t
          do. Caveats and limitations are not buried in fine print, but are headlined. The way that
          Gene Wizard presents genetic information is informed by six years working on AI systems in
          healthcare, where I learned the importance of how data is presented and contextualized.
        </p>

        <h3 className="font-serif text-lg font-medium text-foreground pt-2">Scientific rigor</h3>
        <p>
          Unfortunately, many scientific findings that are linked to by Promethease have failed to
          replicate, usually due to small sample sizes and poor statistical methods. We seek to
          perform rigorous literature reviews and meta-analyses, informed by my work at{" "}
          <a
            href="https://metascience.info"
            className="text-accent hover:underline"
            target="_blank"
            rel="noopener noreferrer"
          >
            The Metascience Observatory
          </a>
          .
        </p>

        <h3 className="font-serif text-lg font-medium text-foreground pt-2">Human health</h3>
        <p>
          Learning about genetics is great, but at the end of the day most of us want to know how
          we can use genetics to live longer, healthier lives. It is my hope that the resources on
          this site will help further human health, both at an individual and societal level.
        </p>

        <h2 className="font-serif text-xl font-semibold text-foreground pt-4">Contact</h2>
        <p>
          Questions or feedback? Click <ObfuscatedEmail /> to get in touch.
        </p>
      </div>
    </div>
  );
}
