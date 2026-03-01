# PGS Catalog License Analysis

Scanned all **5,296** scores in the PGS Catalog REST API (`/rest/score/all`) on 2026-03-01.

## License Breakdown

| License | Count | Commercial Use? |
|---|---|---|
| Standard boilerplate | 5,204 | Ambiguous — defers to EBI terms (open) + author restrictions |
| CC-BY 4.0 | 51 | **Yes** |
| CC-BY-NC-ND 4.0 | 31 | **No** |
| CC0 (Public Domain) | 2 | **Yes** |
| Broad Institute (academic only) | 7 | Requires license from Broad (partnering@broadinstitute.org) |
| Research only (Japan, hum0014-v20) | 1 | **No** |

The standard boilerplate reads: *"PGS obtained from the Catalog should be cited appropriately, and used in accordance with any licensing restrictions set by the authors. See EBI Terms of Use for additional details."* EBI terms are generally permissive but defer to author terms, which are rarely stated explicitly.

---

## Scores Explicitly OK for Commercial Use

### CC0 — Public Domain (2 scores)

| ID | Trait | Variants | Publication |
|---|---|---|---|
| PGS000117 | Cardiovascular disease | 297,862 | Elliott J et al., JAMA (2020) |
| PGS000116 | Coronary artery disease | 40,079 | Elliott J et al., JAMA (2020) |

### CC-BY 4.0 — Commercial OK with Attribution (51 scores)

#### Disease Scores

| ID | Trait | Variants |
|---|---|---|
| PGS003860 | Refractive error | 767,867 |
| PGS000706 | Hypertension | 186,726 |
| PGS000713 | Type 2 diabetes (T2D) | 183,830 |
| PGS000712 | T2D (cases vs HbA1c filtered controls) | 183,695 |
| PGS000703 | Angina | 183,692 |
| PGS000710 | Myocardial infarction | 183,566 |
| PGS000705 | Gallstones | 183,458 |
| PGS000711 | Gout | 183,332 |
| PGS000707 | Cholecystitis | 183,329 |
| PGS000709 | Heart failure | 183,287 |
| PGS000708 | Kidney failure | 183,272 |
| PGS000704 | Alcoholic cirrhosis | 183,271 |
| PGS000730 | Basal cell carcinoma | 47 |
| PGS000732 | Melanoma | 18 |
| PGS000731 | Squamous cell carcinoma | 14 |

#### Biomarker / Lab Value Scores

| ID | Trait | Variants |
|---|---|---|
| PGS000686 | HDL cholesterol [mmol/L] | 25,069 |
| PGS000680 | Cystatin C [mg/L] | 24,487 |
| PGS000687 | IGF-1 [nmol/L] | 23,443 |
| PGS000678 | Creatinine [umol/L] | 21,027 |
| PGS000700 | Urate [umol/L] | 20,171 |
| PGS000694 | SHBG [nmol/L] | 19,328 |
| PGS000671 | Apolipoprotein A [g/L] | 19,324 |
| PGS000691 | Non-albumin protein [g/L] | 18,670 |
| PGS000672 | Apolipoprotein B [g/L] (statin adjusted) | 18,666 |
| PGS000670 | Alkaline phosphatase [U/L] | 18,328 |
| PGS000682 | eGFR [ml/min/1.73m2] | 17,467 |
| PGS000675 | C-reactive protein [mg/L] | 17,378 |
| PGS000683 | Gamma-glutamyl transferase [U/L] | 17,323 |
| PGS000677 | Cholesterol [mmol/L] (statin adjusted) | 17,204 |
| PGS000698 | Total protein [g/L] | 16,420 |
| PGS000688 | LDL cholesterol [mmol/L] (statin adjusted) | 16,184 |
| PGS000699 | Triglycerides [mmol/L] | 16,003 |
| PGS000674 | AST to ALT ratio | 15,548 |
| PGS000685 | HbA1c [mmol/mol] | 14,658 |
| PGS000673 | Aspartate aminotransferase [U/L] | 12,829 |
| PGS000692 | Phosphate [mmol/L] | 12,448 |
| PGS000701 | Urea [mmol/L] | 12,351 |
| PGS000676 | Calcium [mmol/L] | 12,334 |
| PGS000668 | Alanine aminotransferase [U/L] | 12,076 |
| PGS000669 | Albumin [g/L] | 11,912 |
| PGS000689 | Lipoprotein A [nmol/L] | 8,308 |
| PGS000696 | Testosterone [nmol/L] | 8,223 |
| PGS000702 | Vitamin D [nmol/L] | 8,012 |
| PGS000695 | Sodium in urine [mmol/L] | 5,833 |
| PGS000679 | Creatinine in urine [umol/L] | 5,469 |
| PGS000684 | Glucose [mmol/L] | 3,313 |
| PGS000681 | Direct bilirubin [umol/L] | 3,104 |
| PGS000693 | Potassium in urine [mmol/L] | 2,423 |
| PGS000697 | Total bilirubin [umol/L] | 1,159 |
| PGS000690 | Microalbumin in urine [mg/L] | 111 |

---

## Scores with Non-Commercial Restrictions

### CC-BY-NC-ND 4.0 (31 scores)

| ID | Trait | Variants |
|---|---|---|
| PGS005199 | Body mass index (BMI) | 1,296,245 |
| PGS005200 | Body mass index (BMI) | 1,223,921 |
| PGS005204 | Body mass index (BMI) | 1,129,666 |
| PGS005203 | Body mass index (BMI) | 1,091,375 |
| PGS005202 | Body mass index (BMI) | 1,022,487 |
| PGS005201 | Body mass index (BMI) | 1,020,295 |
| PGS002780 | Incident type 2 diabetes | 419,209 |
| PGS002776 | Incident coronary artery disease | 390,782 |
| PGS002778 | Incident hypertension | 309,759 |
| PGS002774 | Incident atrial fibrillation | 216,837 |
| PGS002777 | Incident hypertension | 61,669 |
| PGS002779 | Incident type 2 diabetes | 46,353 |
| PGS000758 | Adult standing height | 33,938 |
| PGS000657 | Heel quantitative ultrasound SOS | 21,716 |
| PGS002775 | Incident coronary artery disease | 1,059 |
| PGS000831 | Total cholesterol | 1,032 |
| PGS000825 | HDL cholesterol | 883 |
| PGS000824 | LDL cholesterol | 809 |
| PGS000826 | Triglycerides | 769 |
| PGS000804–PGS000808 | Type 2 diabetes (T2D) | 582 each |
| PGS000830 | BMI (female) | 372 |
| PGS000829 | BMI (male) | 290 |
| PGS002773 | Incident atrial fibrillation | 265 |
| PGS000828 | Waist circumference (female) | 149 |
| PGS000827 | Waist circumference (male) | 113 |
| PGS000348 | Prostate cancer | 72 |
| PGS003430 | Melanoma | 68 |

### Broad Institute — Academic Only, Commercial License Required (7 scores)

Contact: partnering@broadinstitute.org

| ID | Trait | Variants |
|---|---|---|
| PGS000014 | Type 2 diabetes (T2D) | 6,917,436 |
| PGS000017 | Inflammatory bowel disease | 6,907,112 |
| PGS000016 | Atrial fibrillation | 6,730,541 |
| PGS000013 | Coronary artery disease | 6,630,150 |
| PGS000296 | Coronary artery disease | 6,630,150 |
| PGS000015 | Breast cancer | 5,218 |
| PGS000027 | Body mass index (BMI) | 2,100,302 |

### Research Only — Japan (1 score)

| ID | Trait | Variants |
|---|---|---|
| PGS000337 | Coronary artery disease | 75,028 |

---

## Notes

- The 5,204 standard-boilerplate scores are governed by [EBI Terms of Use](https://www.ebi.ac.uk/about/terms-of-use/) which are generally permissive, but defer to author-set restrictions that are rarely cataloged. Use at your own risk assessment.
- The PGS Catalog infrastructure itself is CC-BY 4.0. The pgsc_calc software is Apache 2.0.
- More variants generally improves discrimination, but depends on GWAS methodology, LD structure, and validation cohort.
- Scan performed with `scripts/scan_pgs_licenses.py`. Full CSV at `pgs_license_scan.csv`.
