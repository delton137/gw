# Genetic Analysis Services — Feature Comparison

Research conducted March 2026. Information sourced from public websites, documentation, and third-party reviews. Features may change; verify with each service directly.

## Feature Matrix

| Feature | GeneWizard | Helix Sequencing | SelfDecode | ADNTRO | Promethease | LiveWello | Gene Inspector Pro | OpenCRAVAT | Sequencing.com | Xcode Life | Genetic Genie | Nebula Genomics |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **Input: 23andMe / AncestryDNA** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ own WGS only |
| **Input: VCF / WGS** | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ WGS + WES | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Ancestry analysis** | ✅ 26 pops, admixture fractions | ✅ 26 ancestries | ✅ | ✅ Y + mtDNA deep | ❌ | ❌ | ❌ | ❌ | ✅ 30+ pops | ❌ | ❌ | ✅ deep |
| **Polygenic Risk Scores (PRS)** | ✅ ancestry-aware, 95% CI | ✅ 1,261+ scores | ✅ | ⚠️ disease risk | ❌ | ⚠️ limited | ❌ | ❌ | ⚠️ limited | ❌ | ❌ | ✅ |
| **Ancestry-aware PRS normalization** | ✅ mixture model | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Pharmacogenomics (PGx)** | ✅ 76 genes, 1,916 alleles | ✅ CYP2D6-focused | ✅ 50+ meds | ✅ 50+ meds | ❌ | ❌ | ❌ | ❌ | ⚠️ limited | ✅ | ❌ | ✅ |
| **CPIC / DPWG clinical guidelines** | ✅ both | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **SNP trait associations** | ✅ curated KB, evidence-graded | ✅ ClinVar-based | ✅ 1,500+ reports | ✅ 300+ conditions | ✅ SNPedia (core) | ✅ 600K SNPs | ⚠️ metabolic focus | ✅ 150+ modules | ✅ | ✅ | ⚠️ methylation only | ✅ |
| **SNPedia integration** | ✅ 109K rsids | ❌ | ❌ | ❌ | ✅ core product | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Carrier screening** | ✅ 9 genes | ❌ | ✅ 40+ conditions | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ |
| **Methylation / pathway analysis** | ❌ | ❌ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ MTHFR focus | ❌ |
| **Raw data never stored** | ✅ deleted after parse | ✅ beta: zero retention | ❌ stored | ⚠️ GDPR, EU servers | ✅ 24–45 days | ⚠️ user-controlled | unknown | N/A self-hosted | ❌ stored | ❌ stored | ✅ deleted immediately | ❌ stored |
| **PDF reports** | ✅ general + clinical PGx | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ | ❌ | ✅ |
| **Public SNP / gene pages (SEO)** | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **Pricing** | Free | Free (beta) | $499–$899 | €109–€169 | $12–15/report | $6.95/mo | $11–22/mo | Free, open source | $30–$399 | $50–70/report | Free | $299–$3,000 |
| **Open source / self-hostable** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ |

**Key:** ✅ supported · ⚠️ partial/limited · ❌ not supported

---

## Service Profiles

### Helix Sequencing (helixsequencing.com)
Broadest PRS library (1,261+ scores) with an AI longevity protocol. Currently free in beta with zero data retention. PGx is limited to CYP2D6 star allele calling; no CPIC/DPWG guidelines. No VCF input.

### SelfDecode (selfdecode.com)
Most feature-complete paid platform: 1,500+ reports, PGx, carrier screening (40+ conditions), ancestry, pathway analysis. Highest price point ($499–$899). Raw data stored on their servers.

### ADNTRO (adntro.com)
Strong ancestry (Y + mtDNA lineage, Neanderthal/Denisovan) and broad disease risk. 50+ PGx medications. GDPR-compliant EU storage. Research use only; no clinical guidelines. One-time payment + optional updates.

### Promethease (promethease.com)
The original SNPedia report tool. Cheapest paid option ($12–15). Fast (<10 min). No ancestry, no PRS, no PGx. Acquired by MyHeritage in 2019.

### LiveWello (livewello.com)
Budget subscription ($6.95/mo). Covers 600K SNPs with pathway/methylation analysis and customizable gene templates. No ancestry, PRS, or PGx. Good for power users who want flexible SNP exploration.

### Gene Inspector Pro (gene-inspector.pro)
Accepts WGS, WES, and array data. Focused on metabolic pathways, vitamins, methylation. Subscription model ($11–22/mo). Limited health-risk breadth; no ancestry, PRS, or PGx guidelines.

### OpenCRAVAT (opencravat.org)
Research-grade, free, open-source variant annotation toolkit. Modular (150+ annotation modules). Not consumer-facing; requires bioinformatics knowledge. Self-hostable for maximum data control.

### Sequencing.com (sequencing.com)
DNA app marketplace ecosystem (100+ apps). Broad format support. Offers its own genotyping ($69) and WGS ($399). Individual health reports from $30. Raw data stored.

### Xcode Life (xcode.life)
Per-report pricing ($50–70, no subscription). Covers nutrition, fitness, skin, sleep, allergy, PGx, mental wellness. Fast (24h). No ancestry or PRS.

### Genetic Genie (geneticgenie.org)
Completely free. Focused on MTHFR methylation and detox pathways. No registration, data deleted immediately. Very narrow scope.

### Nebula Genomics (nebula.org)
Consumer WGS at 30x depth ($299). Most complete data (3 billion positions). Deep ancestry, carrier screening, PGx. Raw data stored; blockchain privacy infrastructure. Class-action filed Oct 2024 over alleged data sharing with Meta/Google.

---

## Notable Omissions

Two services from the original list could not be verified:
- **GeneUnveiled** (genesunveiled.com) — Wix-hosted site; content not indexable
- **PatientUser** (patientuser.com) — No public documentation found for a genetic analysis product

---

## GeneWizard Differentiators

- **Only service** offering ancestry-aware PRS normalization with a mixture model (handles admixed users)
- **Only service** providing both CPIC and DPWG clinical prescribing guidelines
- **Strongest raw-data privacy** among feature-complete platforms — data deleted during parsing, never reaches the database
- Combines SNPedia matching + curated trait KB + PGx + carrier + PRS in one free tool
- Public SEO-indexed SNP and gene pages (unique among all services)
