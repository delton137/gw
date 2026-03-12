# PGS Catalog Licensing Summary

*Research conducted 2026-02-28*

## Overview

The PGS Catalog (pgscatalog.org) contains **5,296 polygenic scores** as of this date.

## Default License (EBI Terms of Use)

The vast majority of scores (~5,289) carry the generic EMBL-EBI license:

> "PGS obtained from the Catalog should be cited appropriately, and used in accordance with any licensing restrictions set by the authors. See EBI Terms of Use (https://www.ebi.ac.uk/about/terms-of-use/) for additional details."

The standard EBI Terms of Use **permit commercial use**, requiring only:
- Appropriate citation/attribution
- Respect for third-party intellectual property rights
- Compliance with any author-specified restrictions

## Scores with Commercial Use Restrictions

**7 scores** have a custom license restricting commercial use. All originate from the Broad Institute:

> "Freely available to the academic community for research use. Parties interested in using the scores for commercial purposes should contact the Broad Office of Strategic Alliances and Partnering (partnering@broadinstitute.org)"

| PGS ID | Name | Trait | Publication |
|---------|------|-------|-------------|
| PGS000013 | GPS_CAD | Coronary artery disease | Khera AV et al., *Nat Genet* (2018) |
| PGS000014 | GPS_T2D | Type 2 diabetes | Khera AV et al., *Nat Genet* (2018) |
| PGS000015 | GPS_BC | Breast cancer | Khera AV et al., *Nat Genet* (2018) |
| PGS000016 | GPS_AF | Atrial fibrillation | Khera AV et al., *Nat Genet* (2018) |
| PGS000017 | GPS_IBD | Inflammatory bowel disease | Khera AV et al., *Nat Genet* (2018) |
| PGS000027 | GPS_BMI | Body mass index | Khera AV et al., *Cell* (2019) |
| PGS000296 | GPS_CAD_SA | Coronary artery disease (South Asian) | Wang M et al., *JACC* (2020) |

All 7 are "GPS" (Genome-wide Polygenic Score) series scores from the Broad Institute.

## How to Check Licensing

- **Individual score API**: `https://www.pgscatalog.org/rest/score/PGS000XXX` — the `license` field shows custom text for restricted scores
- **Browse page**: Restricted scores show a "Check Terms/Licenses" badge at https://www.pgscatalog.org/browse/all/
- **Scoring file headers**: License details are embedded in the downloaded `.txt.gz` files
- **FAQ**: https://www.pgscatalog.org/docs/faq/#access_how

## Impact on Gene Wizard

PGS000013 and PGS000296 were removed from `scripts/ingest_pgs.py` PRIORITY_SCORES on 2026-02-28. Both were CAD scores redundant with PGS000001 (which is unrestricted). Current priority scores are all commercially licensed under EBI Terms of Use:

| PGS ID | Trait | License |
|--------|-------|---------|
| PGS000001 | Coronary artery disease | EBI (commercial OK) |
| PGS000002 | Breast cancer | EBI (commercial OK) |
| PGS000003 | Type 2 diabetes | EBI (commercial OK) |
| PGS000004 | Prostate cancer | EBI (commercial OK) |
| PGS000018 | Atrial fibrillation | EBI (commercial OK) |
| PGS000039 | Alzheimer's disease | EBI (commercial OK) |
