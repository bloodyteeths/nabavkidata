"""
Causal Inference for Procurement Corruption

Estimates causal effects of procurement design choices on corruption probability.
Uses propensity score matching and bootstrap confidence intervals implemented
with sklearn (no econml/dowhy dependency).

Key questions answered:
- Does extending deadlines reduce corruption?
- Does the procedure type causally affect corruption probability?
- Does having only a single bidder causally increase corruption risk?
- Which design choices have the largest causal impact?

Method:
    1. Compute propensity scores P(treatment | confounders) via LogisticRegression
    2. Match treated/control units by propensity score (nearest neighbor, caliper=0.1)
    3. Compute ATE = mean(Y_treated) - mean(Y_control) on matched sample
    4. Bootstrap confidence interval (500 iterations)

Memory-efficient: uses only sklearn + numpy, no heavy causal libraries.
Suitable for EC2 with 3.8GB RAM.

Author: nabavkidata.com
License: Proprietary
"""

import logging
import json
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime

from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)


class CausalAnalyzer:
    """
    Estimates causal effects of procurement design choices on corruption probability
    using propensity score matching.

    Uses only sklearn (LogisticRegression for propensity scores, NearestNeighbors
    for matching) and numpy for bootstrap confidence intervals. No econml or dowhy.

    Usage:
        analyzer = CausalAnalyzer()
        effect = await analyzer.estimate_treatment_effect(pool, 'short_deadline')
        all_effects = await analyzer.estimate_all_effects(pool)
        recs = await analyzer.generate_policy_recommendations(pool)
    """

    # Treatment-outcome pairs to analyze
    TREATMENTS = {
        'short_deadline': {
            'description': 'Deadline < 15 days',
            'feature': 'deadline_days',
            'threshold': 15,
            'direction': 'below',  # treated if below threshold
        },
        'single_bidder': {
            'description': 'Only one bidder submitted',
            'feature': 'num_bidders',
            'threshold': 2,
            'direction': 'below',
        },
        'high_value': {
            'description': 'Estimated value > 10M MKD',
            'feature': 'estimated_value_mkd',
            'threshold': 10_000_000,
            'direction': 'above',
        },
        'weekend_publication': {
            'description': 'Published on weekend or holiday',
            'feature': 'pub_weekend',
            'threshold': 0.5,
            'direction': 'above',
        },
    }

    # Confounders to control for in propensity score model.
    # These are features that plausibly affect both treatment assignment
    # and the outcome (corruption flagging).
    CONFOUNDERS = [
        'estimated_value_mkd',
        'institution_total_tenders',
        'num_bidders',
        'deadline_days',
        'has_lots',
    ]

    # Number of bootstrap iterations for confidence intervals
    N_BOOTSTRAP = 500

    # Caliper for propensity score matching (in SD of propensity scores)
    CALIPER = 0.1

    async def _fetch_analysis_data(self, pool) -> List[Dict]:
        """
        Fetch tender data with features and corruption outcome from the database.

        Joins tenders with corruption_flags to get outcome variable (flagged or not).
        Computes derived features like pub_weekend and institution_total_tenders.

        Returns:
            List of dicts, each representing one tender with features and outcome.
        """
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                WITH institution_stats AS (
                    SELECT
                        procuring_entity,
                        COUNT(*) as total_tenders
                    FROM tenders
                    WHERE procuring_entity IS NOT NULL
                    GROUP BY procuring_entity
                ),
                tender_flags AS (
                    SELECT
                        tender_id,
                        COUNT(*) as flag_count,
                        MAX(score) as max_flag_score
                    FROM corruption_flags
                    GROUP BY tender_id
                )
                SELECT
                    t.tender_id,
                    t.num_bidders,
                    t.estimated_value_mkd,
                    t.actual_value_mkd,
                    t.has_lots,
                    t.procuring_entity,
                    -- Compute deadline_days from publication and closing dates
                    CASE
                        WHEN t.publication_date IS NOT NULL AND t.closing_date IS NOT NULL
                        THEN EXTRACT(DAY FROM (t.closing_date - t.publication_date))
                        ELSE NULL
                    END AS deadline_days,
                    -- Weekend publication flag
                    CASE
                        WHEN t.publication_date IS NOT NULL
                             AND EXTRACT(DOW FROM t.publication_date) IN (0, 6)
                        THEN 1
                        ELSE 0
                    END AS pub_weekend,
                    -- Institution total tenders (confounder)
                    COALESCE(ist.total_tenders, 0) AS institution_total_tenders,
                    -- Outcome: was the tender flagged for corruption?
                    CASE
                        WHEN tf.flag_count > 0 THEN 1
                        ELSE 0
                    END AS is_flagged,
                    COALESCE(tf.flag_count, 0) AS flag_count
                FROM tenders t
                LEFT JOIN institution_stats ist
                    ON t.procuring_entity = ist.procuring_entity
                LEFT JOIN tender_flags tf
                    ON t.tender_id = tf.tender_id
                WHERE t.status = 'awarded'
                  AND t.estimated_value_mkd IS NOT NULL
                  AND t.estimated_value_mkd > 0
                  AND t.num_bidders IS NOT NULL
                  AND t.publication_date IS NOT NULL
                  AND t.closing_date IS NOT NULL
            """)

        data = []
        for row in rows:
            record = dict(row)
            # Convert Decimal types to float
            for key in ('estimated_value_mkd', 'actual_value_mkd'):
                if record.get(key) is not None:
                    record[key] = float(record[key])
                else:
                    record[key] = 0.0
            # Convert deadline_days
            if record.get('deadline_days') is not None:
                record['deadline_days'] = float(record['deadline_days'])
            else:
                record['deadline_days'] = 30.0  # Default
            # Boolean to int
            record['has_lots'] = 1 if record.get('has_lots') else 0
            record['institution_total_tenders'] = int(record.get('institution_total_tenders', 0))
            record['num_bidders'] = int(record.get('num_bidders', 0))
            record['pub_weekend'] = int(record.get('pub_weekend', 0))
            record['is_flagged'] = int(record.get('is_flagged', 0))
            data.append(record)

        logger.info(f"Fetched {len(data)} tenders for causal analysis")
        return data

    def _build_treatment_vector(
        self,
        data: List[Dict],
        treatment_name: str
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Build treatment (T), confounder (X), and outcome (Y) arrays from data.

        Args:
            data: List of tender dicts
            treatment_name: Key in TREATMENTS dict

        Returns:
            Tuple of (treatment_array, confounder_matrix, outcome_array)
        """
        treatment_config = self.TREATMENTS[treatment_name]
        feature = treatment_config['feature']
        threshold = treatment_config['threshold']
        direction = treatment_config['direction']

        T = []
        X = []
        Y = []

        # Remove the treatment feature from confounders to avoid collinearity
        confounders = [c for c in self.CONFOUNDERS if c != feature]

        for record in data:
            feat_val = record.get(feature)
            if feat_val is None:
                continue

            feat_val = float(feat_val)

            # Determine treatment assignment
            if direction == 'below':
                treated = 1 if feat_val < threshold else 0
            else:
                treated = 1 if feat_val > threshold else 0

            T.append(treated)
            Y.append(record['is_flagged'])

            # Build confounder vector
            confounder_vals = []
            for c in confounders:
                val = record.get(c, 0)
                confounder_vals.append(float(val) if val is not None else 0.0)
            X.append(confounder_vals)

        return np.array(T), np.array(X), np.array(Y)

    def _propensity_score_matching(
        self,
        T: np.ndarray,
        X: np.ndarray,
        Y: np.ndarray,
        caliper: float = 0.1
    ) -> Tuple[np.ndarray, np.ndarray, int]:
        """
        Propensity score matching implementation.

        Steps:
        1. Fit LogisticRegression on treatment ~ confounders to get propensity scores
        2. For each treated unit, find nearest control unit within caliper
        3. Return matched outcome arrays for ATE computation

        Args:
            T: Treatment assignment vector (0/1)
            X: Confounder matrix (n_samples x n_confounders)
            Y: Outcome vector (0/1)
            caliper: Maximum allowed propensity score distance for a match

        Returns:
            Tuple of (y_treated_matched, y_control_matched, n_matched)
        """
        # Standardize confounders for stable logistic regression
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # Fit propensity score model: P(T=1 | X)
        ps_model = LogisticRegression(
            max_iter=1000,
            solver='lbfgs',
            C=1.0,
            random_state=42
        )
        ps_model.fit(X_scaled, T)
        propensity_scores = ps_model.predict_proba(X_scaled)[:, 1]

        # Split into treated and control
        treated_idx = np.where(T == 1)[0]
        control_idx = np.where(T == 0)[0]

        if len(treated_idx) == 0 or len(control_idx) == 0:
            logger.warning("No treated or no control units found")
            return np.array([]), np.array([]), 0

        # Get propensity scores for each group
        ps_treated = propensity_scores[treated_idx].reshape(-1, 1)
        ps_control = propensity_scores[control_idx].reshape(-1, 1)

        # Use NearestNeighbors to find closest control for each treated unit
        nn = NearestNeighbors(n_neighbors=1, metric='euclidean')
        nn.fit(ps_control)
        distances, indices = nn.kneighbors(ps_treated)

        # Apply caliper: only keep matches within caliper SD of propensity scores
        ps_std = np.std(propensity_scores)
        if ps_std == 0:
            ps_std = 1.0  # Avoid division by zero
        caliper_abs = caliper * ps_std

        y_treated_matched = []
        y_control_matched = []
        used_control = set()  # For matching without replacement

        for i in range(len(treated_idx)):
            dist = distances[i, 0]
            ctrl_local_idx = indices[i, 0]

            # Skip if distance exceeds caliper or control already used
            if dist > caliper_abs:
                continue
            if ctrl_local_idx in used_control:
                continue

            used_control.add(ctrl_local_idx)
            y_treated_matched.append(Y[treated_idx[i]])
            y_control_matched.append(Y[control_idx[ctrl_local_idx]])

        n_matched = len(y_treated_matched)
        return np.array(y_treated_matched), np.array(y_control_matched), n_matched

    def _bootstrap_ate(
        self,
        y_treated: np.ndarray,
        y_control: np.ndarray,
        n_bootstrap: int = 500,
        alpha: float = 0.05
    ) -> Tuple[float, float, float, float]:
        """
        Compute ATE with bootstrap confidence interval and permutation p-value.

        Args:
            y_treated: Matched treated outcomes
            y_control: Matched control outcomes
            n_bootstrap: Number of bootstrap iterations
            alpha: Significance level for CI (default 0.05 for 95% CI)

        Returns:
            Tuple of (ate, ci_lower, ci_upper, p_value)
        """
        n = len(y_treated)
        if n == 0:
            return 0.0, 0.0, 0.0, 1.0

        # Point estimate of ATE
        ate = float(np.mean(y_treated) - np.mean(y_control))

        # Bootstrap confidence interval
        rng = np.random.RandomState(42)
        bootstrap_ates = []
        for _ in range(n_bootstrap):
            boot_idx = rng.choice(n, size=n, replace=True)
            boot_ate = np.mean(y_treated[boot_idx]) - np.mean(y_control[boot_idx])
            bootstrap_ates.append(boot_ate)

        bootstrap_ates = np.array(bootstrap_ates)
        ci_lower = float(np.percentile(bootstrap_ates, 100 * alpha / 2))
        ci_upper = float(np.percentile(bootstrap_ates, 100 * (1 - alpha / 2)))

        # Permutation test for p-value
        # Under null: treatment has no effect, so shuffle treatment labels
        combined = np.concatenate([y_treated, y_control])
        n_perm = min(n_bootstrap, 1000)
        null_ates = []
        for _ in range(n_perm):
            perm = rng.permutation(combined)
            perm_ate = np.mean(perm[:n]) - np.mean(perm[n:])
            null_ates.append(perm_ate)

        null_ates = np.array(null_ates)
        # Two-sided p-value: fraction of null ATEs at least as extreme as observed
        p_value = float(np.mean(np.abs(null_ates) >= np.abs(ate)))
        # Ensure p-value is not exactly 0 (bounded below by 1/n_perm)
        p_value = max(p_value, 1.0 / n_perm)

        return ate, ci_lower, ci_upper, p_value

    def _generate_interpretation(
        self,
        treatment_name: str,
        ate: float,
        ci_lower: float,
        ci_upper: float,
        p_value: float,
        n_matched: int
    ) -> Tuple[str, str]:
        """
        Generate human-readable interpretation and recommendation from ATE.

        Args:
            treatment_name: Name of the treatment
            ate: Average Treatment Effect
            ci_lower: CI lower bound
            ci_upper: CI upper bound
            p_value: P-value from permutation test
            n_matched: Number of matched pairs

        Returns:
            Tuple of (interpretation_text, recommendation_text)
        """
        config = self.TREATMENTS[treatment_name]
        desc = config['description']
        ate_pct = abs(ate * 100)
        direction = "increases" if ate > 0 else "decreases"
        significant = p_value < 0.05

        if not significant:
            interpretation = (
                f"'{desc}' shows a {direction} in corruption probability "
                f"of {ate_pct:.1f} percentage points, but this effect is NOT "
                f"statistically significant (p={p_value:.3f}, n={n_matched} matched pairs). "
                f"95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]."
            )
            recommendation = (
                f"Insufficient evidence to conclude that {desc.lower()} causally "
                f"affects corruption risk. More data or alternative approaches needed."
            )
        elif ate > 0:
            # Treatment increases corruption
            interpretation = (
                f"'{desc}' causally INCREASES corruption probability by "
                f"{ate_pct:.1f} percentage points (p={p_value:.3f}, n={n_matched} matched pairs). "
                f"95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]."
            )
            # Generate specific recommendation
            if treatment_name == 'short_deadline':
                recommendation = (
                    f"Extending tender deadlines beyond 15 days could reduce corruption "
                    f"risk by approximately {ate_pct:.0f}%. Consider enforcing minimum "
                    f"21-day deadlines for tenders above 1M MKD."
                )
            elif treatment_name == 'single_bidder':
                recommendation = (
                    f"Single-bidder tenders show {ate_pct:.0f}% higher corruption risk. "
                    f"Consider requiring re-tendering when only one bid is received, "
                    f"or implementing mandatory market consultation."
                )
            elif treatment_name == 'high_value':
                recommendation = (
                    f"High-value tenders (>10M MKD) show {ate_pct:.0f}% higher corruption "
                    f"risk. Consider mandatory multi-stage evaluation and independent "
                    f"oversight for high-value procurements."
                )
            elif treatment_name == 'weekend_publication':
                recommendation = (
                    f"Weekend-published tenders show {ate_pct:.0f}% higher corruption risk. "
                    f"Consider restricting tender publication to business days only."
                )
            else:
                recommendation = (
                    f"Avoiding '{desc.lower()}' could reduce corruption risk by "
                    f"approximately {ate_pct:.0f}%."
                )
        else:
            # Treatment decreases corruption (protective effect)
            interpretation = (
                f"'{desc}' causally DECREASES corruption probability by "
                f"{ate_pct:.1f} percentage points (p={p_value:.3f}, n={n_matched} matched pairs). "
                f"95% CI: [{ci_lower*100:.1f}%, {ci_upper*100:.1f}%]."
            )
            recommendation = (
                f"'{desc}' appears to have a protective effect against corruption. "
                f"Consider encouraging this practice."
            )

        return interpretation, recommendation

    async def estimate_treatment_effect(
        self,
        pool,
        treatment_name: str
    ) -> Dict[str, Any]:
        """
        Estimate the Average Treatment Effect (ATE) of a procurement design choice
        on corruption probability using propensity score matching.

        Method:
        1. Compute propensity scores P(treatment | confounders) via LogisticRegression
        2. Match treated/control units by propensity score (nearest neighbor, caliper=0.1)
        3. Compute ATE = mean(Y_treated) - mean(Y_control) on matched sample
        4. Bootstrap confidence interval (500 iterations)

        Args:
            pool: asyncpg connection pool
            treatment_name: Key in TREATMENTS dict (e.g. 'short_deadline')

        Returns:
            Dictionary with:
                treatment, ate, ci_lower, ci_upper, p_value,
                n_treated, n_control, n_matched,
                interpretation, recommendation
        """
        if treatment_name not in self.TREATMENTS:
            raise ValueError(
                f"Unknown treatment '{treatment_name}'. "
                f"Available: {list(self.TREATMENTS.keys())}"
            )

        logger.info(f"Estimating causal effect of '{treatment_name}'")

        # Fetch data
        data = await self._fetch_analysis_data(pool)
        if len(data) < 100:
            logger.warning(f"Only {len(data)} tenders available for causal analysis")
            return {
                'treatment': treatment_name,
                'treatment_description': self.TREATMENTS[treatment_name]['description'],
                'ate': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0,
                'p_value': 1.0,
                'n_treated': 0,
                'n_control': 0,
                'n_matched': 0,
                'interpretation': 'Insufficient data for causal analysis (need at least 100 tenders).',
                'recommendation': 'Collect more data before running causal analysis.',
            }

        # Build treatment, confounder, outcome arrays
        T, X, Y = self._build_treatment_vector(data, treatment_name)

        n_treated = int(np.sum(T == 1))
        n_control = int(np.sum(T == 0))

        logger.info(
            f"Treatment '{treatment_name}': {n_treated} treated, "
            f"{n_control} control, {len(T)} total"
        )

        if n_treated < 20 or n_control < 20:
            logger.warning(
                f"Too few units in one group for '{treatment_name}': "
                f"treated={n_treated}, control={n_control}"
            )
            return {
                'treatment': treatment_name,
                'treatment_description': self.TREATMENTS[treatment_name]['description'],
                'ate': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0,
                'p_value': 1.0,
                'n_treated': n_treated,
                'n_control': n_control,
                'n_matched': 0,
                'interpretation': (
                    f"Insufficient group sizes for causal analysis "
                    f"(treated={n_treated}, control={n_control}). "
                    f"Need at least 20 in each group."
                ),
                'recommendation': 'Collect more data in the underrepresented group.',
            }

        # Run propensity score matching
        y_treated_matched, y_control_matched, n_matched = self._propensity_score_matching(
            T, X, Y, caliper=self.CALIPER
        )

        if n_matched < 10:
            logger.warning(f"Only {n_matched} matched pairs for '{treatment_name}'")
            return {
                'treatment': treatment_name,
                'treatment_description': self.TREATMENTS[treatment_name]['description'],
                'ate': 0.0,
                'ci_lower': 0.0,
                'ci_upper': 0.0,
                'p_value': 1.0,
                'n_treated': n_treated,
                'n_control': n_control,
                'n_matched': n_matched,
                'interpretation': (
                    f"Only {n_matched} matched pairs found (caliper={self.CALIPER}). "
                    f"Consider relaxing the caliper or checking data quality."
                ),
                'recommendation': 'Relax matching caliper or collect more comparable data.',
            }

        # Compute ATE with bootstrap CI
        ate, ci_lower, ci_upper, p_value = self._bootstrap_ate(
            y_treated_matched,
            y_control_matched,
            n_bootstrap=self.N_BOOTSTRAP
        )

        # Generate interpretation and recommendation
        interpretation, recommendation = self._generate_interpretation(
            treatment_name, ate, ci_lower, ci_upper, p_value, n_matched
        )

        logger.info(
            f"Treatment '{treatment_name}': ATE={ate:.4f}, "
            f"CI=[{ci_lower:.4f}, {ci_upper:.4f}], p={p_value:.4f}, "
            f"n_matched={n_matched}"
        )

        return {
            'treatment': treatment_name,
            'treatment_description': self.TREATMENTS[treatment_name]['description'],
            'ate': round(ate, 6),
            'ci_lower': round(ci_lower, 6),
            'ci_upper': round(ci_upper, 6),
            'p_value': round(p_value, 4),
            'n_treated': n_treated,
            'n_control': n_control,
            'n_matched': n_matched,
            'interpretation': interpretation,
            'recommendation': recommendation,
        }

    async def estimate_all_effects(self, pool) -> List[Dict[str, Any]]:
        """
        Run estimation for all defined treatments.

        Returns:
            List of effect dicts, sorted by absolute ATE (largest first).
        """
        logger.info("Estimating causal effects for all treatments")
        results = []

        for treatment_name in self.TREATMENTS:
            try:
                effect = await self.estimate_treatment_effect(pool, treatment_name)
                results.append(effect)
            except Exception as e:
                logger.error(f"Failed to estimate effect for '{treatment_name}': {e}")
                results.append({
                    'treatment': treatment_name,
                    'treatment_description': self.TREATMENTS[treatment_name]['description'],
                    'ate': 0.0,
                    'ci_lower': 0.0,
                    'ci_upper': 0.0,
                    'p_value': 1.0,
                    'n_treated': 0,
                    'n_control': 0,
                    'n_matched': 0,
                    'interpretation': f'Estimation failed: {str(e)}',
                    'recommendation': 'Check data and retry.',
                })

        # Sort by absolute ATE descending (most impactful first)
        results.sort(key=lambda x: abs(x.get('ate', 0)), reverse=True)
        return results

    async def generate_policy_recommendations(
        self,
        pool,
        institution: str = None
    ) -> List[Dict[str, Any]]:
        """
        Generate actionable policy recommendations based on causal estimates.

        For each treatment with a significant causal effect, generates a specific
        recommendation with estimated impact and confidence level.

        Args:
            pool: asyncpg connection pool
            institution: Optional institution name to scope recommendations.
                         If provided, also checks institution-specific patterns.

        Returns:
            List of {recommendation, estimated_impact, confidence, evidence, treatment_name}
        """
        logger.info(
            f"Generating policy recommendations"
            + (f" for institution: {institution}" if institution else " (global)")
        )

        # First try to read cached estimates from database
        recommendations = []
        cached_estimates = []

        try:
            async with pool.acquire() as conn:
                # Check if causal_estimates table exists
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'causal_estimates'
                    )
                """)

                if table_exists:
                    cached_rows = await conn.fetch("""
                        SELECT treatment_name, treatment_description,
                               ate, ci_lower, ci_upper, p_value,
                               n_treated, n_control, n_matched,
                               interpretation, recommendation
                        FROM causal_estimates
                        ORDER BY ABS(ate) DESC
                    """)
                    cached_estimates = [dict(r) for r in cached_rows]
        except Exception as e:
            logger.warning(f"Could not read cached estimates: {e}")

        # If no cached estimates, compute them fresh
        if not cached_estimates:
            logger.info("No cached estimates found, computing fresh...")
            effects = await self.estimate_all_effects(pool)
        else:
            effects = cached_estimates

        for effect in effects:
            ate = effect.get('ate', 0)
            p_value = effect.get('p_value', 1.0)
            n_matched = effect.get('n_matched', 0)
            treatment_name = effect.get('treatment', effect.get('treatment_name', ''))

            # Determine confidence level
            if p_value < 0.01 and n_matched >= 100:
                confidence = 'high'
            elif p_value < 0.05 and n_matched >= 50:
                confidence = 'medium'
            elif p_value < 0.10 and n_matched >= 20:
                confidence = 'low'
            else:
                continue  # Skip non-significant results

            estimated_impact = round(ate * 100, 2)  # Convert to percentage points

            rec_text = effect.get('recommendation', '')
            if not rec_text:
                desc = effect.get('treatment_description', treatment_name)
                if ate > 0:
                    rec_text = (
                        f"Avoiding '{desc}' could reduce corruption risk "
                        f"by approximately {abs(estimated_impact):.1f} percentage points."
                    )
                else:
                    rec_text = (
                        f"Encouraging '{desc}' could reduce corruption risk "
                        f"by approximately {abs(estimated_impact):.1f} percentage points."
                    )

            evidence = {
                'ate': round(ate, 6),
                'ci_lower': round(effect.get('ci_lower', 0), 6),
                'ci_upper': round(effect.get('ci_upper', 0), 6),
                'p_value': round(p_value, 4),
                'n_matched': n_matched,
                'n_treated': effect.get('n_treated', 0),
                'n_control': effect.get('n_control', 0),
                'method': 'propensity_score_matching',
            }

            recommendations.append({
                'institution': institution,
                'recommendation': rec_text,
                'estimated_impact': estimated_impact,
                'confidence': confidence,
                'evidence': evidence,
                'treatment_name': treatment_name,
            })

        # If institution is specified, add institution-specific context
        if institution and recommendations:
            try:
                async with pool.acquire() as conn:
                    inst_stats = await conn.fetchrow("""
                        SELECT
                            COUNT(*) as total_tenders,
                            COUNT(*) FILTER (WHERE num_bidders = 1) as single_bidder_count,
                            AVG(EXTRACT(DAY FROM (closing_date - publication_date)))
                                FILTER (WHERE publication_date IS NOT NULL
                                        AND closing_date IS NOT NULL)
                                as avg_deadline_days
                        FROM tenders
                        WHERE procuring_entity = $1
                    """, institution)

                    if inst_stats and inst_stats['total_tenders'] > 0:
                        total = inst_stats['total_tenders']
                        sb_pct = (inst_stats['single_bidder_count'] / total * 100) if total > 0 else 0
                        avg_dd = float(inst_stats['avg_deadline_days'] or 30)

                        # Add institution context to recommendations
                        for rec in recommendations:
                            if rec['treatment_name'] == 'single_bidder' and sb_pct > 30:
                                rec['recommendation'] += (
                                    f" NOTE: This institution has {sb_pct:.0f}% single-bidder "
                                    f"tenders ({inst_stats['single_bidder_count']}/{total}), "
                                    f"well above average."
                                )
                            elif rec['treatment_name'] == 'short_deadline' and avg_dd < 15:
                                rec['recommendation'] += (
                                    f" NOTE: This institution's average deadline is only "
                                    f"{avg_dd:.0f} days, below the 15-day threshold."
                                )
            except Exception as e:
                logger.warning(f"Could not fetch institution stats: {e}")

        # Sort: high confidence first, then by absolute impact
        confidence_order = {'high': 0, 'medium': 1, 'low': 2}
        recommendations.sort(
            key=lambda x: (confidence_order.get(x['confidence'], 3), -abs(x['estimated_impact']))
        )

        return recommendations

    async def get_causal_vs_correlational_report(self, pool) -> Dict[str, Any]:
        """
        Compare SHAP (correlational) feature importance vs causal feature importance.

        Identifies confounders (correlated but not causal) vs true causes.
        Reads SHAP importances from ml_shap_cache or batch_shap results,
        and compares with ATE from causal estimates.

        Returns:
            {
                features: [{name, shap_importance, causal_effect, is_confounder, explanation}],
                methodology_note: str
            }
        """
        logger.info("Generating causal vs correlational comparison report")

        # Step 1: Get causal effects (from DB or compute)
        causal_effects = {}
        try:
            async with pool.acquire() as conn:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'causal_estimates'
                    )
                """)

                if table_exists:
                    rows = await conn.fetch("""
                        SELECT treatment_name, ate, p_value, n_matched
                        FROM causal_estimates
                    """)
                    for r in rows:
                        causal_effects[r['treatment_name']] = {
                            'ate': float(r['ate']),
                            'p_value': float(r['p_value']),
                            'n_matched': int(r['n_matched']),
                        }
        except Exception as e:
            logger.warning(f"Could not read causal estimates: {e}")

        if not causal_effects:
            # Compute fresh
            effects = await self.estimate_all_effects(pool)
            for eff in effects:
                causal_effects[eff['treatment']] = {
                    'ate': eff['ate'],
                    'p_value': eff['p_value'],
                    'n_matched': eff['n_matched'],
                }

        # Step 2: Get SHAP importances (aggregated from cache)
        shap_importances = {}
        try:
            async with pool.acquire() as conn:
                shap_table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables
                        WHERE table_name = 'ml_shap_cache'
                    )
                """)

                if shap_table_exists:
                    # Get average absolute SHAP values across all cached tenders
                    rows = await conn.fetch("""
                        SELECT shap_values
                        FROM ml_shap_cache
                        ORDER BY computed_at DESC
                        LIMIT 500
                    """)

                    if rows:
                        all_shap = {}
                        count = 0
                        for r in rows:
                            sv = r['shap_values']
                            if isinstance(sv, str):
                                sv = json.loads(sv) if sv else {}
                            elif sv is None:
                                sv = {}
                            for feat, val in sv.items():
                                if feat not in all_shap:
                                    all_shap[feat] = 0.0
                                all_shap[feat] += abs(float(val))
                            count += 1

                        if count > 0:
                            shap_importances = {
                                k: v / count for k, v in all_shap.items()
                            }
        except Exception as e:
            logger.warning(f"Could not read SHAP cache: {e}")

        # Step 3: Map treatment names to feature names
        treatment_to_feature = {
            'short_deadline': 'deadline_days',
            'single_bidder': 'num_bidders',
            'high_value': 'estimated_value_mkd',
            'weekend_publication': 'pub_weekend',
        }

        # Step 4: Build comparison report
        features_report = []

        # Include all treatment features
        for treatment_name, feature_name in treatment_to_feature.items():
            causal = causal_effects.get(treatment_name, {})
            shap_imp = shap_importances.get(feature_name, 0.0)
            ate = causal.get('ate', 0.0)
            p_value = causal.get('p_value', 1.0)

            # Determine if this is a confounder or true cause
            significant_causal = p_value < 0.05
            high_shap = shap_imp > np.percentile(
                list(shap_importances.values()), 50
            ) if shap_importances else False

            if high_shap and not significant_causal:
                is_confounder = True
                explanation = (
                    f"'{feature_name}' has high SHAP importance ({shap_imp:.4f}) "
                    f"but NO significant causal effect (ATE={ate:.4f}, p={p_value:.3f}). "
                    f"This suggests it is a CONFOUNDER: correlated with corruption "
                    f"but not a direct cause."
                )
            elif significant_causal and high_shap:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' has both high SHAP importance ({shap_imp:.4f}) "
                    f"AND significant causal effect (ATE={ate:.4f}, p={p_value:.3f}). "
                    f"This is likely a TRUE CAUSE of corruption risk."
                )
            elif significant_causal and not high_shap:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' has significant causal effect (ATE={ate:.4f}, "
                    f"p={p_value:.3f}) but low SHAP importance ({shap_imp:.4f}). "
                    f"Causal effect may be masked by confounders in SHAP analysis."
                )
            else:
                is_confounder = False
                explanation = (
                    f"'{feature_name}' shows neither strong SHAP importance "
                    f"({shap_imp:.4f}) nor significant causal effect "
                    f"(ATE={ate:.4f}, p={p_value:.3f})."
                )

            features_report.append({
                'name': feature_name,
                'treatment_name': treatment_name,
                'shap_importance': round(shap_imp, 6),
                'causal_effect': round(ate, 6),
                'p_value': round(p_value, 4),
                'is_confounder': is_confounder,
                'explanation': explanation,
            })

        # Sort by absolute causal effect
        features_report.sort(key=lambda x: abs(x['causal_effect']), reverse=True)

        return {
            'features': features_report,
            'n_shap_samples': len(shap_importances),
            'n_treatments_analyzed': len(causal_effects),
            'methodology_note': (
                "SHAP values measure correlational feature importance: how much each "
                "feature contributes to the model's prediction. Causal effects (ATE) "
                "measure the actual impact of changing a feature on the outcome, "
                "controlling for confounders via propensity score matching. "
                "Features with high SHAP but no causal effect are likely confounders. "
                "Features with significant causal effects are actionable targets for "
                "policy intervention."
            ),
        }
