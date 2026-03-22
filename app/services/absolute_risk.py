"""Absolute risk conversion — translate PRS z-scores into disease probabilities.

Implements the Bayesian mixture model from GenoPred (Pain et al., 2021).
For a binary trait with population prevalence K and PRS AUC:

1. Convert AUC to Cohen's d (standardized mean difference between cases
   and controls): d = √2 * Φ⁻¹(AUC)
2. Model PRS as a mixture of case and control distributions, centered
   so the population mean is zero.
3. Apply Bayes' theorem to compute P(case | PRS = z).

This gives clinically meaningful output: instead of "72nd percentile",
users see "your estimated lifetime risk is ~15%".
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt, exp, pi, erf, log


@dataclass
class AbsoluteRiskResult:
    """Result of converting a PRS z-score to absolute risk."""
    absolute_risk: float       # user's estimated risk (0-1)
    population_risk: float     # baseline prevalence (0-1)
    relative_risk: float       # ratio: absolute_risk / population_risk
    risk_category: str         # human-readable category
    absolute_risk_lower: float | None = None  # 95% CI lower bound (0-1)
    absolute_risk_upper: float | None = None  # 95% CI upper bound (0-1)


def _norm_cdf(x: float) -> float:
    """Standard normal CDF using the error function."""
    return 0.5 * (1.0 + erf(x / sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return exp(-0.5 * x * x) / sqrt(2.0 * pi)


def _norm_ppf(p: float) -> float:
    """Approximate inverse normal CDF (probit function).

    Uses the rational approximation from Abramowitz and Stegun (26.2.23).
    Accurate to ~4.5e-4 for 0 < p < 1.
    """
    if p <= 0:
        return -10.0
    if p >= 1:
        return 10.0
    if p < 0.5:
        return -_norm_ppf(1.0 - p)

    t = sqrt(-2.0 * log(1.0 - p))
    c0, c1, c2 = 2.515517, 0.802853, 0.010328
    d1, d2, d3 = 1.432788, 0.189269, 0.001308
    return t - (c0 + c1 * t + c2 * t * t) / (1.0 + d1 * t + d2 * t * t + d3 * t * t * t)


def auc_to_cohens_d(auc: float) -> float:
    """Convert AUC to Cohen's d.

    The standard conversion: d = √2 * Φ⁻¹(AUC).
    AUC of 0.5 → d=0 (no discrimination), AUC of 1.0 → d=∞.
    """
    if auc <= 0.5:
        return 0.0
    if auc >= 1.0:
        return 10.0  # cap at practical maximum
    return sqrt(2.0) * _norm_ppf(auc)


def _bayes_risk(z: float, K: float, d: float) -> float | None:
    """Compute P(case | PRS = z) using the Bayesian mixture model."""
    mu_case = (1.0 - K) * d
    mu_control = -K * d
    pdf_case = _norm_pdf(z - mu_case)
    pdf_control = _norm_pdf(z - mu_control)
    denominator = K * pdf_case + (1.0 - K) * pdf_control
    if denominator <= 0:
        return None
    return K * pdf_case / denominator


def compute_absolute_risk(
    z_score: float,
    prevalence: float,
    auc: float | None = None,
    cohens_d: float | None = None,
    z_score_lower: float | None = None,
    z_score_upper: float | None = None,
) -> AbsoluteRiskResult | None:
    """Compute absolute disease risk for a user given their PRS z-score.

    Uses a Bayesian mixture model:
    - PRS for controls ~ N(-K*d, 1)
    - PRS for cases    ~ N((1-K)*d, 1)
    - Population PRS   ~ K * N((1-K)*d, 1) + (1-K) * N(-K*d, 1)
      (centered at 0 by construction)

    P(case | z) = K * φ(z - (1-K)*d) / [K * φ(z - (1-K)*d) + (1-K) * φ(z + K*d)]

    Model assumptions:
    - PRS is approximately normally distributed in cases and controls
    - Effect sizes are homogeneous across populations
    - No gene-environment interactions are modeled
    - Prevalence is population-average (not age/sex-stratified)

    Args:
        z_score: User's PRS z-score (standardized to reference population)
        prevalence: Population prevalence of the disease (0-1)
        auc: Reported AUC of the PRS (converted to Cohen's d)
        cohens_d: Direct Cohen's d (used if auc is None)
        z_score_lower: Lower 95% CI bound on z-score (for risk CI)
        z_score_upper: Upper 95% CI bound on z-score (for risk CI)

    Returns:
        AbsoluteRiskResult or None if inputs are insufficient.
    """
    if prevalence is None or prevalence <= 0 or prevalence >= 1:
        return None

    # Get Cohen's d
    if cohens_d is not None:
        d = max(0.0, cohens_d)
    elif auc is not None and auc > 0.5:
        d = auc_to_cohens_d(auc)
    else:
        return None

    if d <= 0:
        return None

    K = prevalence

    absolute_risk = _bayes_risk(z_score, K, d)
    if absolute_risk is None:
        return None

    relative_risk = absolute_risk / K

    # Categorize
    if relative_risk >= 2.0:
        category = "high"
    elif relative_risk >= 1.3:
        category = "elevated"
    elif relative_risk >= 0.7:
        category = "average"
    else:
        category = "reduced"

    # Compute CI bounds if z-score CI available
    risk_lower = None
    risk_upper = None
    if z_score_lower is not None and z_score_upper is not None:
        risk_lower = _bayes_risk(z_score_lower, K, d)
        risk_upper = _bayes_risk(z_score_upper, K, d)

    return AbsoluteRiskResult(
        absolute_risk=absolute_risk,
        population_risk=K,
        relative_risk=relative_risk,
        risk_category=category,
        absolute_risk_lower=risk_lower,
        absolute_risk_upper=risk_upper,
    )
