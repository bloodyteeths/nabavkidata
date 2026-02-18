"""
CRI Weight Calibration via Review Feedback

Uses accumulated analyst reviews to adjust CRI flag weights.
Approach: logistic regression where each review provides a label
(fraud/not-fraud) and features are the per-flag-type max scores.

Constraints:
- Minimum 50 reviews before first update
- Weight changes capped at +/-20% per cycle
- Weights stored in cri_weight_history table
- Falls back to hardcoded CRI_WEIGHTS if no DB weights exist

Dependencies: sklearn (LogisticRegression), numpy
"""

import json
import logging
from typing import Dict, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Minimum number of reviews required before we attempt calibration
MIN_REVIEWS_FOR_CALIBRATION = 50

# Maximum relative change per calibration cycle (20%)
MAX_WEIGHT_CHANGE_RATIO = 0.20

# Hardcoded fallback weights (canonical source of truth)
DEFAULT_CRI_WEIGHTS: Dict[str, float] = {
    'single_bidder': 1.0,
    'procedure_type': 1.2,
    'contract_splitting': 1.3,
    'identical_bids': 1.5,
    'strategic_disqualification': 1.4,
    'bid_rotation': 1.2,
    'professional_loser': 0.8,
    'short_deadline': 0.9,
    'short_decision': 1.0,
    'contract_value_growth': 1.0,
    'late_amendment': 0.9,
    'threshold_manipulation': 0.8,
    'repeat_winner': 1.1,
    'price_anomaly': 1.1,
    'bid_clustering': 1.2,
}

# Ordered list of flag types (consistent feature order for ML)
FLAG_TYPE_ORDER = sorted(DEFAULT_CRI_WEIGHTS.keys())


async def get_current_weights(pool) -> Dict[str, float]:
    """
    Return CRI_WEIGHTS - from DB (latest applied) or fallback to hardcoded.

    Args:
        pool: asyncpg connection pool

    Returns:
        Dict mapping flag_type -> weight
    """
    try:
        row = await pool.fetchrow("""
            SELECT weights
            FROM cri_weight_history
            WHERE applied = TRUE
            ORDER BY computed_at DESC
            LIMIT 1
        """)
        if row and row['weights']:
            raw = row['weights']
            if isinstance(raw, str):
                weights = json.loads(raw)
            else:
                weights = dict(raw)
            # Validate: must have all flag types with positive values
            if all(ft in weights and weights[ft] > 0 for ft in FLAG_TYPE_ORDER):
                return weights
            else:
                logger.warning("DB weights incomplete, falling back to defaults")
    except Exception as e:
        logger.warning(f"Could not load weights from DB: {e}")

    return dict(DEFAULT_CRI_WEIGHTS)


async def get_current_weights_from_pool(pool) -> Dict[str, float]:
    """Alias for get_current_weights for clarity in imports."""
    return await get_current_weights(pool)


async def _fetch_training_data(pool) -> tuple:
    """
    Fetch reviews joined with flag scores to build training data.

    Returns:
        (X, y, num_reviews) where:
        - X: np.ndarray of shape (n_samples, n_flag_types) with per-type max scores
        - y: np.ndarray of shape (n_samples,) with binary labels (1=fraud, 0=not fraud)
        - num_reviews: total number of reviews used
    """
    # Get all reviews with their tender-level flag data
    rows = await pool.fetch("""
        SELECT
            cr.tender_id,
            cr.analyst_verdict,
            cf.flag_type,
            MAX(cf.score) as max_score
        FROM corruption_reviews cr
        JOIN corruption_flags cf ON cr.tender_id = cf.tender_id
        WHERE cr.analyst_verdict IN (
            'confirmed_fraud', 'likely_fraud', 'false_positive'
        )
        GROUP BY cr.tender_id, cr.analyst_verdict, cf.flag_type
    """)

    if not rows:
        return None, None, 0

    # Build per-tender feature vectors and labels
    tender_data: Dict[str, dict] = {}
    for row in rows:
        tid = row['tender_id']
        if tid not in tender_data:
            verdict = row['analyst_verdict']
            # Binary label: fraud (1) vs not-fraud (0)
            label = 1 if verdict in ('confirmed_fraud', 'likely_fraud') else 0
            tender_data[tid] = {
                'label': label,
                'scores': {ft: 0.0 for ft in FLAG_TYPE_ORDER},
            }
        ft = row['flag_type']
        if ft in tender_data[tid]['scores']:
            tender_data[tid]['scores'][ft] = max(
                tender_data[tid]['scores'][ft],
                float(row['max_score'] or 0),
            )

    num_reviews = len(tender_data)
    if num_reviews == 0:
        return None, None, 0

    X = np.array([
        [td['scores'][ft] for ft in FLAG_TYPE_ORDER]
        for td in tender_data.values()
    ])
    y = np.array([td['label'] for td in tender_data.values()])

    return X, y, num_reviews


def _clamp_weights(
    new_weights: Dict[str, float],
    old_weights: Dict[str, float],
) -> Dict[str, float]:
    """
    Clamp weight changes to MAX_WEIGHT_CHANGE_RATIO per cycle.
    Also ensures weights stay in [0.1, 3.0] range.
    """
    clamped = {}
    for ft in FLAG_TYPE_ORDER:
        old_w = old_weights.get(ft, 1.0)
        new_w = new_weights.get(ft, old_w)

        max_delta = old_w * MAX_WEIGHT_CHANGE_RATIO
        delta = new_w - old_w
        if abs(delta) > max_delta:
            new_w = old_w + (max_delta if delta > 0 else -max_delta)

        # Clamp to reasonable range
        clamped[ft] = round(max(0.1, min(3.0, new_w)), 3)

    return clamped


async def compute_updated_weights(pool) -> Optional[Dict]:
    """
    Fetch all reviews, compute optimal weights via logistic regression.

    Returns dict with:
        - weights: new CRI_WEIGHTS dict
        - num_reviews: number of reviews used
        - avg_agreement_rate: model accuracy on training data
        - error: error message if calibration failed

    Returns None if not enough reviews exist.
    """
    X, y, num_reviews = await _fetch_training_data(pool)

    if X is None or num_reviews < MIN_REVIEWS_FOR_CALIBRATION:
        return {
            'weights': None,
            'num_reviews': num_reviews or 0,
            'avg_agreement_rate': None,
            'error': f'Need at least {MIN_REVIEWS_FOR_CALIBRATION} reviews, have {num_reviews or 0}',
        }

    # Check we have both classes
    if len(set(y)) < 2:
        return {
            'weights': None,
            'num_reviews': num_reviews,
            'avg_agreement_rate': None,
            'error': 'Need reviews with both fraud and non-fraud verdicts',
        }

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import StandardScaler

        # Normalize features for stable coefficient extraction
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Fit logistic regression
        model = LogisticRegression(
            penalty='l2',
            C=1.0,
            max_iter=1000,
            random_state=42,
        )
        model.fit(X_scaled, y)

        # Compute agreement rate (accuracy on training data)
        predictions = model.predict(X_scaled)
        agreement_rate = float(np.mean(predictions == y))

        # Extract coefficients as importance weights
        # Positive coef = more indicative of fraud = higher weight
        coefs = model.coef_[0]

        # Normalize coefficients to be centered around 1.0
        # Use softmax-like scaling: exp(coef) / mean(exp(coef))
        exp_coefs = np.exp(coefs)
        normalized = exp_coefs / np.mean(exp_coefs)

        # Build raw weights dict
        raw_weights = {
            FLAG_TYPE_ORDER[i]: float(normalized[i])
            for i in range(len(FLAG_TYPE_ORDER))
        }

        # Clamp changes relative to current weights
        current = await get_current_weights(pool)
        clamped_weights = _clamp_weights(raw_weights, current)

        return {
            'weights': clamped_weights,
            'num_reviews': num_reviews,
            'avg_agreement_rate': round(agreement_rate, 4),
            'error': None,
        }

    except ImportError:
        logger.error("sklearn not installed, cannot calibrate weights")
        return {
            'weights': None,
            'num_reviews': num_reviews,
            'avg_agreement_rate': None,
            'error': 'sklearn not installed on server',
        }
    except Exception as e:
        logger.error(f"Weight calibration failed: {e}")
        return {
            'weights': None,
            'num_reviews': num_reviews,
            'avg_agreement_rate': None,
            'error': str(e),
        }


async def apply_weight_update(
    pool,
    new_weights: Dict[str, float],
    num_reviews: int = 0,
    avg_agreement_rate: float = None,
    notes: str = "",
) -> bool:
    """
    Store new weights in cri_weight_history and mark as applied.
    Unmarks any previously applied weights.

    Args:
        pool: asyncpg connection pool
        new_weights: the new CRI weight dictionary
        num_reviews: number of reviews that went into this calibration
        avg_agreement_rate: model accuracy
        notes: optional notes about this calibration run

    Returns:
        True if weights were stored and applied successfully
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Unmark all previously applied weights
            await conn.execute("""
                UPDATE cri_weight_history SET applied = FALSE WHERE applied = TRUE
            """)

            # Insert new weights as applied
            await conn.execute("""
                INSERT INTO cri_weight_history
                    (weights, num_reviews_used, avg_agreement_rate, applied, notes)
                VALUES ($1, $2, $3, TRUE, $4)
            """,
                json.dumps(new_weights),
                num_reviews,
                avg_agreement_rate,
                notes or f"Calibration from {num_reviews} reviews",
            )

    logger.info(
        f"Applied new CRI weights from {num_reviews} reviews "
        f"(agreement={avg_agreement_rate})"
    )
    return True


async def get_weight_history(pool, limit: int = 20) -> list:
    """
    Fetch recent weight calibration history.

    Returns list of dicts with history_id, weights, num_reviews_used,
    avg_agreement_rate, computed_at, applied, notes.
    """
    rows = await pool.fetch("""
        SELECT history_id, weights, num_reviews_used, avg_agreement_rate,
               computed_at, applied, notes
        FROM cri_weight_history
        ORDER BY computed_at DESC
        LIMIT $1
    """, limit)

    result = []
    for row in rows:
        raw_weights = row['weights']
        if isinstance(raw_weights, str):
            weights = json.loads(raw_weights)
        else:
            weights = dict(raw_weights) if raw_weights else {}

        result.append({
            'history_id': row['history_id'],
            'weights': weights,
            'num_reviews_used': row['num_reviews_used'],
            'avg_agreement_rate': row['avg_agreement_rate'],
            'computed_at': row['computed_at'].isoformat() if row['computed_at'] else None,
            'applied': row['applied'],
            'notes': row['notes'],
        })

    return result
