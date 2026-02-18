"""
Confidence interval and uncertainty quantification for CRI scores.

Provides:
- Bootstrap confidence intervals for the Corruption Risk Index (CRI)
- Data completeness scoring (fraction of 112 ML features with real values)
- Uncertainty level classification (low / medium / high)

Performance: 1000 bootstrap iterations complete in < 50ms using vectorized numpy.
"""

import numpy as np
from typing import Tuple, Dict, Any, Optional


def bootstrap_cri_confidence(
    flag_scores: Dict[str, float],
    cri_weights: Dict[str, float],
    n_bootstrap: int = 1000,
    confidence_level: float = 0.90,
    multi_indicator_bonus_per_type: float = 8.0,
) -> Tuple[float, float, float]:
    """
    Compute CRI score with bootstrap confidence interval.

    The CRI formula (mirrored from corruption.py get_tender_analysis):
        base = weighted_mean(per-type max scores)
        bonus = 8 * (num_types - 1)   if num_types > 1 else 0
        cri   = min(100, round(base + bonus))

    Measurement uncertainty is simulated by adding uniform noise
    of +/-10% of each flag score on every bootstrap iteration,
    then recomputing CRI.

    Args:
        flag_scores: {flag_type: max_score} where score is 0-100.
                     Only non-false-positive, per-type max scores.
        cri_weights: {flag_type: weight} -- the CRI_WEIGHTS dict.
        n_bootstrap: Number of bootstrap iterations (default 1000).
        confidence_level: Confidence level for the interval (default 0.90).
        multi_indicator_bonus_per_type: Bonus points per extra flag type
                                        beyond the first (default 8).

    Returns:
        (cri_score, ci_lower, ci_upper)
        cri_score is the point estimate (no noise).
        ci_lower and ci_upper bound the confidence interval.
    """
    if not flag_scores:
        return (0.0, 0.0, 0.0)

    # Build aligned arrays for vectorized computation
    types = list(flag_scores.keys())
    scores = np.array([flag_scores[t] for t in types], dtype=np.float64)
    weights = np.array([cri_weights.get(t, 1.0) for t in types], dtype=np.float64)
    n_types = len(types)

    # --- Point estimate (deterministic, matches corruption.py logic) ---
    total_ws = float(np.sum(scores * weights))
    total_w = float(np.sum(weights))
    base_score = total_ws / total_w if total_w > 0 else 0.0
    bonus = multi_indicator_bonus_per_type * (n_types - 1) if n_types > 1 else 0.0
    cri_score = min(100.0, round(base_score + bonus))

    # --- Bootstrap CI ---
    # Generate noise: uniform in [-0.10*score, +0.10*score] per flag per iteration
    # Shape: (n_bootstrap, n_types)
    rng = np.random.default_rng()
    noise_frac = rng.uniform(-0.10, 0.10, size=(n_bootstrap, n_types))
    # Perturbed scores, clipped to [0, 100]
    perturbed = np.clip(scores[np.newaxis, :] * (1.0 + noise_frac), 0.0, 100.0)

    # Weighted mean for each bootstrap sample (vectorized)
    # numerator: sum(perturbed * weights) along axis=1
    numerators = perturbed @ weights  # shape (n_bootstrap,)
    base_scores = numerators / total_w if total_w > 0 else np.zeros(n_bootstrap)

    # Add multi-indicator bonus (constant across bootstrap since types don't change)
    cri_samples = np.minimum(100.0, np.round(base_scores + bonus))

    # Percentile CI
    alpha = (1.0 - confidence_level) / 2.0
    ci_lower = float(np.percentile(cri_samples, 100.0 * alpha))
    ci_upper = float(np.percentile(cri_samples, 100.0 * (1.0 - alpha)))

    return (cri_score, ci_lower, ci_upper)


def compute_data_completeness(
    feature_values: Dict[str, Any],
    total_features: int = 112,
) -> float:
    """
    Compute what fraction of the ML features have real (non-default) values.

    A feature is considered "present" (non-default) if its value is:
    - Not None
    - Not NaN (for floats)
    - Not 0 or 0.0 (these are the typical default/missing sentinel)
    - Not an empty string

    Args:
        feature_values: {feature_name: value} dict. May have fewer than
                        total_features keys if some features were never
                        extracted.
        total_features: Total number of possible ML features (default 112).

    Returns:
        Float in [0.0, 1.0]. 1.0 means all features have real data.
    """
    if total_features <= 0:
        return 0.0

    present = 0
    for _name, val in feature_values.items():
        if val is None:
            continue
        if isinstance(val, float) and np.isnan(val):
            continue
        if isinstance(val, (int, float)) and val == 0:
            continue
        if isinstance(val, str) and val == "":
            continue
        present += 1

    return min(1.0, present / total_features)


def classify_uncertainty(
    ci_width: float,
    data_completeness: float,
) -> str:
    """
    Classify overall uncertainty into 'low', 'medium', or 'high'.

    Decision matrix (CI width thresholds are on the 0-100 CRI scale):

    +-----------------------+----------------------------+
    |                       | data_completeness          |
    | ci_width              | >= 0.70     | < 0.70       |
    +-----------------------+-------------+--------------+
    | <= 10                 | low         | medium       |
    | 10 < width <= 25      | medium      | high         |
    | > 25                  | high        | high         |
    +-----------------------+-------------+--------------+

    Args:
        ci_width: Upper bound minus lower bound of the confidence interval
                  (on the 0-100 scale).
        data_completeness: Float in [0.0, 1.0] from compute_data_completeness.

    Returns:
        'low', 'medium', or 'high'
    """
    if ci_width <= 10.0:
        return "low" if data_completeness >= 0.70 else "medium"
    elif ci_width <= 25.0:
        return "medium" if data_completeness >= 0.70 else "high"
    else:
        return "high"
