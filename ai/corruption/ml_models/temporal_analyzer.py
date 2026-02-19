"""
Temporal Risk Analysis for Corruption Detection

Processes sequences of tenders per institution and company to detect:
1. Behavioral change points (sudden shifts in corruption patterns)
2. Risk escalation trajectories (gradual worsening)
3. Seasonal corruption patterns
4. Time-aware features (rolling averages, trends, volatility)

Uses lightweight numpy/sklearn -- no PyTorch (memory constraint on 3.8GB EC2).

Usage:
    from ai.corruption.ml_models.temporal_analyzer import TemporalAnalyzer

    analyzer = TemporalAnalyzer()
    profile = await analyzer.get_entity_risk_profile(pool, "Municipality of Bitola", "institution")
"""

import logging
from datetime import datetime, timedelta, date
from typing import Dict, List, Any, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration constants
# ---------------------------------------------------------------------------

# CUSUM detection thresholds
CUSUM_THRESHOLD_SIGMAS = 4.5   # cumulative deviation in std-devs to flag
CUSUM_DRIFT = 0.5              # allowable drift per step before accumulation

# Minimum number of tenders needed for meaningful temporal analysis
MIN_TENDERS_FOR_ANALYSIS = 5
MIN_TENDERS_FOR_CHANGE_POINTS = 10
MIN_TENDERS_FOR_TREND = 8

# Trajectory classification thresholds
ESCALATING_SLOPE_THRESHOLD = 0.5
DECLINING_SLOPE_THRESHOLD = -0.5
STABLE_HIGH_AVG = 60.0
STABLE_LOW_AVG = 30.0
VOLATILITY_HIGH_THRESHOLD = 20.0
VOLATILITY_LOW_THRESHOLD = 10.0
NEW_PATTERN_DAYS = 90

# Rolling window sizes (in days)
WINDOW_30D = 30
WINDOW_90D = 90
WINDOW_365D = 365


class TemporalAnalyzer:
    """
    Analyzes temporal sequences of tenders per entity to detect
    behavioral shifts and risk escalation patterns.
    """

    # ------------------------------------------------------------------
    # 1. Build Entity Timeline
    # ------------------------------------------------------------------

    async def build_entity_timeline(
        self,
        pool,
        entity_name: str,
        entity_type: str = "institution",
        window_days: int = 730,
    ) -> dict:
        """
        Build ordered timeline of tenders for an institution or company.

        For each tender: date, risk_score, flags, value, bidder_count.

        Args:
            pool: asyncpg connection pool
            entity_name: Name of the institution or company
            entity_type: 'institution' or 'company'
            window_days: How far back to look (default 2 years)

        Returns:
            {
                entity, entity_type,
                tenders: [{date, tender_id, risk_score, flags, flag_types,
                           value_mkd, bidder_count, single_bidder}],
                period_start, period_end, total_tenders
            }
        """
        async with pool.acquire() as conn:
            cutoff = datetime.utcnow() - timedelta(days=window_days)

            if entity_type == "institution":
                field = "t.procuring_entity"
            else:
                field = "t.winner"

            rows = await conn.fetch(
                f"""
                SELECT
                    t.tender_id,
                    COALESCE(t.publication_date, t.opening_date, t.created_at::date) AS tender_date,
                    COALESCE(trs.risk_score, 0) AS risk_score,
                    COALESCE(trs.flag_count, 0) AS flag_count,
                    t.estimated_value_mkd,
                    t.status,
                    (
                        SELECT COUNT(*)
                        FROM tender_bidders tb
                        WHERE tb.tender_id = t.tender_id
                    ) AS bidder_count,
                    (
                        SELECT ARRAY_AGG(DISTINCT cf.flag_type)
                        FROM corruption_flags cf
                        WHERE cf.tender_id = t.tender_id
                          AND cf.false_positive = FALSE
                    ) AS flag_types
                FROM tenders t
                LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                WHERE {field} ILIKE $1
                  AND COALESCE(t.publication_date, t.opening_date, t.created_at::date) >= $2
                ORDER BY tender_date ASC
                """,
                entity_name,
                cutoff.date(),
            )

            tenders = []
            for row in rows:
                flag_types_raw = row["flag_types"]
                flag_types_list = list(flag_types_raw) if flag_types_raw else []
                bidder_count = int(row["bidder_count"]) if row["bidder_count"] else 0

                tenders.append(
                    {
                        "date": row["tender_date"].isoformat()
                        if row["tender_date"]
                        else None,
                        "tender_id": row["tender_id"],
                        "risk_score": int(row["risk_score"]),
                        "flag_count": int(row["flag_count"]),
                        "flag_types": flag_types_list,
                        "value_mkd": float(row["estimated_value_mkd"])
                        if row["estimated_value_mkd"]
                        else None,
                        "bidder_count": bidder_count,
                        "single_bidder": bidder_count == 1 and bidder_count > 0,
                        "status": row["status"],
                    }
                )

            period_start = tenders[0]["date"] if tenders else None
            period_end = tenders[-1]["date"] if tenders else None

            return {
                "entity": entity_name,
                "entity_type": entity_type,
                "tenders": tenders,
                "period_start": period_start,
                "period_end": period_end,
                "total_tenders": len(tenders),
            }

    # ------------------------------------------------------------------
    # 2. Compute Temporal Features
    # ------------------------------------------------------------------

    def compute_temporal_features(self, timeline: list) -> dict:
        """
        Compute 15 temporal features from a tender timeline.

        Each element in `timeline` should be a dict with at least:
            date (ISO str), risk_score (int), flag_count (int),
            bidder_count (int), single_bidder (bool), value_mkd (float|None)

        Returns dict of feature_name -> value (all floats or None).
        """
        n = len(timeline)
        if n < MIN_TENDERS_FOR_ANALYSIS:
            return self._empty_temporal_features()

        # Parse dates and scores into arrays
        dates = []
        risk_scores = []
        flag_counts = []
        bidder_counts = []
        single_bidder_flags = []
        values = []

        for t in timeline:
            d = _parse_date(t["date"])
            if d is None:
                continue
            dates.append(d)
            risk_scores.append(float(t["risk_score"]))
            flag_counts.append(float(t["flag_count"]))
            bidder_counts.append(float(t["bidder_count"]))
            single_bidder_flags.append(1.0 if t.get("single_bidder") else 0.0)
            values.append(float(t["value_mkd"]) if t.get("value_mkd") else 0.0)

        if len(dates) < MIN_TENDERS_FOR_ANALYSIS:
            return self._empty_temporal_features()

        risk_arr = np.array(risk_scores, dtype=np.float64)
        flag_arr = np.array(flag_counts, dtype=np.float64)
        bidder_arr = np.array(bidder_counts, dtype=np.float64)
        sb_arr = np.array(single_bidder_flags, dtype=np.float64)
        value_arr = np.array(values, dtype=np.float64)
        n_valid = len(dates)

        now = datetime.utcnow().date()

        # --- Rolling averages of risk scores ---
        rolling_avg_30d = self._rolling_avg_by_days(dates, risk_arr, now, WINDOW_30D)
        rolling_avg_90d = self._rolling_avg_by_days(dates, risk_arr, now, WINDOW_90D)
        rolling_avg_365d = self._rolling_avg_by_days(dates, risk_arr, now, WINDOW_365D)

        # --- Risk trend slope (linear regression over last 20 tenders) ---
        window_size = min(20, n_valid)
        recent_risk = risk_arr[-window_size:]
        if len(recent_risk) >= MIN_TENDERS_FOR_TREND:
            x = np.arange(len(recent_risk), dtype=np.float64)
            risk_trend_slope = float(np.polyfit(x, recent_risk, 1)[0])
        else:
            risk_trend_slope = 0.0

        # --- Risk volatility (std dev of last 20 risk scores) ---
        risk_volatility = float(np.std(recent_risk)) if len(recent_risk) >= 2 else 0.0

        # --- Risk acceleration (slope of slope) ---
        # Split the last 20 into two halves, compute slope of each, take difference
        risk_acceleration = 0.0
        if len(recent_risk) >= 10:
            half = len(recent_risk) // 2
            first_half = recent_risk[:half]
            second_half = recent_risk[half:]
            x1 = np.arange(len(first_half), dtype=np.float64)
            x2 = np.arange(len(second_half), dtype=np.float64)
            slope1 = float(np.polyfit(x1, first_half, 1)[0])
            slope2 = float(np.polyfit(x2, second_half, 1)[0])
            risk_acceleration = slope2 - slope1

        # --- Seasonality score ---
        # Compare current quarter's average risk to same quarter last year
        seasonality_score = self._compute_seasonality(dates, risk_arr, now)

        # --- Days since last flag ---
        flagged_dates = [d for d, fc in zip(dates, flag_counts) if fc > 0]
        if flagged_dates:
            days_since_last_flag = float((now - flagged_dates[-1]).days)
        else:
            days_since_last_flag = None

        # --- Flag frequency (30d, 90d) ---
        flag_frequency_30d = self._count_in_window(dates, flag_arr, now, WINDOW_30D, count_nonzero=True)
        flag_frequency_90d = self._count_in_window(dates, flag_arr, now, WINDOW_90D, count_nonzero=True)

        # --- Single bidder rate (30d, 90d) ---
        single_bidder_rate_30d = self._rate_in_window(dates, sb_arr, now, WINDOW_30D)
        single_bidder_rate_90d = self._rate_in_window(dates, sb_arr, now, WINDOW_90D)

        # --- Average bidders trend ---
        if len(bidder_arr) >= MIN_TENDERS_FOR_TREND:
            x = np.arange(len(bidder_arr[-window_size:]), dtype=np.float64)
            avg_bidders_trend = float(np.polyfit(x, bidder_arr[-window_size:], 1)[0])
        else:
            avg_bidders_trend = 0.0

        # --- Value concentration (are contracts getting larger?) ---
        # Trend of non-zero values over time
        nonzero_vals = value_arr[value_arr > 0]
        if len(nonzero_vals) >= MIN_TENDERS_FOR_TREND:
            x = np.arange(len(nonzero_vals[-window_size:]), dtype=np.float64)
            value_concentration = float(
                np.polyfit(x, nonzero_vals[-window_size:], 1)[0]
            )
        else:
            value_concentration = 0.0

        # --- Procurement pace (tenders per month, trend) ---
        if len(dates) >= 2:
            span_days = max((dates[-1] - dates[0]).days, 1)
            procurement_pace = float(n_valid) / (span_days / 30.0)
        else:
            procurement_pace = 0.0

        return {
            "rolling_avg_risk_30d": _safe_round(rolling_avg_30d),
            "rolling_avg_risk_90d": _safe_round(rolling_avg_90d),
            "rolling_avg_risk_365d": _safe_round(rolling_avg_365d),
            "risk_trend_slope": _safe_round(risk_trend_slope, 4),
            "risk_volatility": _safe_round(risk_volatility, 2),
            "risk_acceleration": _safe_round(risk_acceleration, 4),
            "seasonality_score": _safe_round(seasonality_score, 2),
            "days_since_last_flag": days_since_last_flag,
            "flag_frequency_30d": flag_frequency_30d,
            "flag_frequency_90d": flag_frequency_90d,
            "single_bidder_rate_30d": _safe_round(single_bidder_rate_30d, 3),
            "single_bidder_rate_90d": _safe_round(single_bidder_rate_90d, 3),
            "avg_bidders_trend": _safe_round(avg_bidders_trend, 4),
            "value_concentration": _safe_round(value_concentration, 2),
            "procurement_pace": _safe_round(procurement_pace, 2),
        }

    # ------------------------------------------------------------------
    # 3. Detect Change Points (CUSUM)
    # ------------------------------------------------------------------

    def detect_change_points(
        self,
        risk_scores: list,
        dates: list,
    ) -> list:
        """
        CUSUM-based change point detection on risk score timeline.

        Detects both upward shifts (increasing corruption) and downward shifts
        using a two-sided cumulative sum control chart.

        Args:
            risk_scores: list of float risk scores (0-100)
            dates: list of date objects (same length as risk_scores)

        Returns:
            list of {date, direction, magnitude, confidence, before_avg, after_avg}
        """
        n = len(risk_scores)
        if n < MIN_TENDERS_FOR_CHANGE_POINTS:
            return []

        scores = np.array(risk_scores, dtype=np.float64)
        mean = float(np.mean(scores))
        std = float(np.std(scores))

        if std < 1e-6:
            # All scores are identical -- no change points
            return []

        # Normalized deviations
        z = (scores - mean) / std

        # Two-sided CUSUM
        threshold = CUSUM_THRESHOLD_SIGMAS
        drift = CUSUM_DRIFT

        # Upward CUSUM (detects increases)
        s_pos = np.zeros(n)
        # Downward CUSUM (detects decreases)
        s_neg = np.zeros(n)

        change_points = []
        last_cp_idx = -10  # avoid overlapping detections

        for i in range(1, n):
            s_pos[i] = max(0, s_pos[i - 1] + z[i] - drift)
            s_neg[i] = max(0, s_neg[i - 1] - z[i] - drift)

            if i - last_cp_idx < 5:
                # Require at least 5 tenders between detected change points
                continue

            direction = None
            magnitude = 0.0

            if s_pos[i] > threshold:
                direction = "increasing"
                magnitude = float(s_pos[i])
                s_pos[i] = 0  # reset after detection
            elif s_neg[i] > threshold:
                direction = "decreasing"
                magnitude = float(s_neg[i])
                s_neg[i] = 0  # reset after detection

            if direction:
                last_cp_idx = i
                before_scores = scores[max(0, i - 10): i]
                after_scores = scores[i: min(n, i + 10)]
                before_avg = float(np.mean(before_scores)) if len(before_scores) > 0 else 0.0
                after_avg = float(np.mean(after_scores)) if len(after_scores) > 0 else 0.0

                # Confidence based on magnitude relative to threshold
                confidence = min(1.0, magnitude / (threshold * 1.5))

                change_points.append(
                    {
                        "date": dates[i].isoformat() if hasattr(dates[i], "isoformat") else str(dates[i]),
                        "index": i,
                        "direction": direction,
                        "magnitude": _safe_round(magnitude, 2),
                        "confidence": _safe_round(confidence, 3),
                        "before_avg": _safe_round(before_avg, 1),
                        "after_avg": _safe_round(after_avg, 1),
                    }
                )

        return change_points

    # ------------------------------------------------------------------
    # 4. Classify Risk Trajectory
    # ------------------------------------------------------------------

    def classify_risk_trajectory(self, temporal_features: dict, change_points: list = None) -> dict:
        """
        Classify the entity's risk trajectory based on temporal features.

        Trajectories:
        - 'escalating': risk trend slope > threshold AND recent avg > historical avg
        - 'stable_high': avg risk > 60 AND low volatility
        - 'stable_low': avg risk < 30 AND low volatility
        - 'declining': risk trend slope < -threshold
        - 'volatile': high volatility regardless of trend
        - 'new_pattern': change point detected in last 90 days

        Returns:
            {trajectory, confidence, description, recommendation}
        """
        slope = temporal_features.get("risk_trend_slope", 0.0) or 0.0
        volatility = temporal_features.get("risk_volatility", 0.0) or 0.0
        avg_30d = temporal_features.get("rolling_avg_risk_30d") or 0.0
        avg_90d = temporal_features.get("rolling_avg_risk_90d") or 0.0
        avg_365d = temporal_features.get("rolling_avg_risk_365d") or 0.0
        acceleration = temporal_features.get("risk_acceleration", 0.0) or 0.0

        # Check for recent change points
        recent_change = False
        if change_points:
            now = datetime.utcnow().date()
            for cp in change_points:
                cp_date = _parse_date(cp.get("date"))
                if cp_date and (now - cp_date).days <= NEW_PATTERN_DAYS:
                    recent_change = True
                    break

        # Classification logic (order matters -- first match wins)

        # 1. New pattern detected recently
        if recent_change:
            latest_cp = change_points[-1] if change_points else {}
            direction = latest_cp.get("direction", "unknown")
            conf = min(0.9, float(latest_cp.get("confidence", 0.5)))
            return {
                "trajectory": "new_pattern",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Детектирана е неодамнешна промена во однесувањето "
                    f"({direction}). Просечен ризик пред: {latest_cp.get('before_avg', '?')}, "
                    f"после: {latest_cp.get('after_avg', '?')}."
                ),
                "recommendation": "Потребна е итна ревизија на последните тендери за оваа институција.",
            }

        # 2. Escalating
        if slope > ESCALATING_SLOPE_THRESHOLD and avg_30d > avg_365d:
            conf = min(0.95, 0.5 + abs(slope) / 5.0 + (avg_30d - avg_365d) / 100.0)
            return {
                "trajectory": "escalating",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Ризикот се зголемува (наклон={slope:.2f}). "
                    f"Просек 30д: {avg_30d:.1f} vs 365д: {avg_365d:.1f}."
                ),
                "recommendation": "Приоритетно следење. Ризикот се влошува -- потребна е интервенција.",
            }

        # 3. Volatile
        if volatility > VOLATILITY_HIGH_THRESHOLD:
            conf = min(0.85, 0.4 + volatility / 50.0)
            return {
                "trajectory": "volatile",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Високо варијабилен ризик (волатилност={volatility:.1f}). "
                    f"Наклон={slope:.2f}, просек 90д={avg_90d:.1f}."
                ),
                "recommendation": "Нестабилно однесување -- потребен е мониторинг.",
            }

        # 4. Stable high
        if avg_90d > STABLE_HIGH_AVG and volatility < VOLATILITY_LOW_THRESHOLD:
            conf = min(0.9, 0.6 + avg_90d / 200.0)
            return {
                "trajectory": "stable_high",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Стабилно висок ризик (просек 90д={avg_90d:.1f}, волатилност={volatility:.1f})."
                ),
                "recommendation": "Систематски висок ризик -- потребна е длабока ревизија.",
            }

        # 5. Declining
        if slope < DECLINING_SLOPE_THRESHOLD:
            conf = min(0.9, 0.5 + abs(slope) / 5.0)
            return {
                "trajectory": "declining",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Ризикот опаѓа (наклон={slope:.2f}). "
                    f"Просек 30д: {avg_30d:.1f} vs 365д: {avg_365d:.1f}."
                ),
                "recommendation": "Позитивен тренд. Продолжете со мониторинг.",
            }

        # 6. Stable low
        if avg_90d < STABLE_LOW_AVG and volatility < VOLATILITY_LOW_THRESHOLD:
            conf = min(0.9, 0.7 + (STABLE_LOW_AVG - avg_90d) / 100.0)
            return {
                "trajectory": "stable_low",
                "confidence": _safe_round(conf, 3),
                "description": (
                    f"Стабилно низок ризик (просек 90д={avg_90d:.1f})."
                ),
                "recommendation": "Нормално однесување. Рутински мониторинг.",
            }

        # 7. Default: moderate / mixed
        return {
            "trajectory": "moderate",
            "confidence": 0.5,
            "description": (
                f"Умерен ризик без јасен тренд "
                f"(просек 90д={avg_90d:.1f}, наклон={slope:.2f}, волатилност={volatility:.1f})."
            ),
            "recommendation": "Стандарден мониторинг.",
        }

    # ------------------------------------------------------------------
    # 5. Full Entity Risk Profile (main entry point)
    # ------------------------------------------------------------------

    async def get_entity_risk_profile(
        self,
        pool,
        entity_name: str,
        entity_type: str = "institution",
        window_days: int = 730,
    ) -> dict:
        """
        Full temporal risk profile combining timeline, features,
        change points, and trajectory classification.

        This is the main entry point for the API endpoint.

        Args:
            pool: asyncpg connection pool
            entity_name: Name of the institution or company
            entity_type: 'institution' or 'company'
            window_days: Lookback window in days

        Returns:
            {
                entity, entity_type, total_tenders,
                period_start, period_end,
                temporal_features: {...},
                change_points: [...],
                trajectory: {trajectory, confidence, description, recommendation},
                summary_stats: {avg_risk, max_risk, total_flags, ...},
                computed_at
            }
        """
        timeline_data = await self.build_entity_timeline(
            pool, entity_name, entity_type, window_days
        )

        tenders = timeline_data["tenders"]
        n = len(tenders)

        if n < MIN_TENDERS_FOR_ANALYSIS:
            return {
                "entity": entity_name,
                "entity_type": entity_type,
                "total_tenders": n,
                "period_start": timeline_data["period_start"],
                "period_end": timeline_data["period_end"],
                "temporal_features": self._empty_temporal_features(),
                "change_points": [],
                "trajectory": {
                    "trajectory": "insufficient_data",
                    "confidence": 0.0,
                    "description": f"Недоволно тендери за анализа ({n} од потребни {MIN_TENDERS_FOR_ANALYSIS}).",
                    "recommendation": "Потребни се повеќе податоци.",
                },
                "summary_stats": self._compute_summary(tenders),
                "computed_at": datetime.utcnow().isoformat(),
            }

        # Compute temporal features
        temporal_features = self.compute_temporal_features(tenders)

        # Detect change points
        risk_scores = [float(t["risk_score"]) for t in tenders]
        dates = [_parse_date(t["date"]) for t in tenders]
        # Filter out None dates
        valid_pairs = [(d, s) for d, s in zip(dates, risk_scores) if d is not None]
        if valid_pairs:
            valid_dates, valid_scores = zip(*valid_pairs)
            change_points = self.detect_change_points(list(valid_scores), list(valid_dates))
        else:
            change_points = []

        # Classify trajectory
        trajectory = self.classify_risk_trajectory(temporal_features, change_points)

        return {
            "entity": entity_name,
            "entity_type": entity_type,
            "total_tenders": n,
            "period_start": timeline_data["period_start"],
            "period_end": timeline_data["period_end"],
            "temporal_features": temporal_features,
            "change_points": change_points,
            "trajectory": trajectory,
            "summary_stats": self._compute_summary(tenders),
            "computed_at": datetime.utcnow().isoformat(),
        }

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    def _empty_temporal_features(self) -> dict:
        """Return empty feature dict when data is insufficient."""
        return {
            "rolling_avg_risk_30d": None,
            "rolling_avg_risk_90d": None,
            "rolling_avg_risk_365d": None,
            "risk_trend_slope": None,
            "risk_volatility": None,
            "risk_acceleration": None,
            "seasonality_score": None,
            "days_since_last_flag": None,
            "flag_frequency_30d": None,
            "flag_frequency_90d": None,
            "single_bidder_rate_30d": None,
            "single_bidder_rate_90d": None,
            "avg_bidders_trend": None,
            "value_concentration": None,
            "procurement_pace": None,
        }

    def _rolling_avg_by_days(
        self,
        dates: list,
        scores: np.ndarray,
        reference_date,
        window_days: int,
    ) -> Optional[float]:
        """Compute average of scores within the last `window_days` from reference_date."""
        cutoff = reference_date - timedelta(days=window_days)
        mask = np.array([d >= cutoff for d in dates])
        window_scores = scores[mask]
        if len(window_scores) == 0:
            return None
        return float(np.mean(window_scores))

    def _count_in_window(
        self,
        dates: list,
        values: np.ndarray,
        reference_date,
        window_days: int,
        count_nonzero: bool = False,
    ) -> int:
        """Count tenders (or flagged tenders if count_nonzero) in a time window."""
        cutoff = reference_date - timedelta(days=window_days)
        count = 0
        for d, v in zip(dates, values):
            if d >= cutoff:
                if count_nonzero:
                    if v > 0:
                        count += 1
                else:
                    count += 1
        return count

    def _rate_in_window(
        self,
        dates: list,
        binary_values: np.ndarray,
        reference_date,
        window_days: int,
    ) -> Optional[float]:
        """Compute rate (fraction of 1s) of a binary array within a time window."""
        cutoff = reference_date - timedelta(days=window_days)
        mask = np.array([d >= cutoff for d in dates])
        window_vals = binary_values[mask]
        if len(window_vals) == 0:
            return None
        return float(np.mean(window_vals))

    def _compute_seasonality(
        self,
        dates: list,
        risk_arr: np.ndarray,
        now,
    ) -> Optional[float]:
        """
        Compare current quarter's average risk to the same quarter last year.
        Returns ratio (>1 means higher risk this year, <1 means lower).
        """
        current_quarter = (now.month - 1) // 3 + 1
        current_year = now.year

        current_q_scores = []
        last_year_q_scores = []

        for d, score in zip(dates, risk_arr):
            q = (d.month - 1) // 3 + 1
            if q == current_quarter:
                if d.year == current_year:
                    current_q_scores.append(score)
                elif d.year == current_year - 1:
                    last_year_q_scores.append(score)

        if not current_q_scores or not last_year_q_scores:
            return None

        current_avg = np.mean(current_q_scores)
        last_avg = np.mean(last_year_q_scores)

        if last_avg < 1e-6:
            return None

        return float(current_avg / last_avg)

    def _compute_summary(self, tenders: list) -> dict:
        """Compute summary statistics from a list of tenders."""
        if not tenders:
            return {
                "avg_risk": 0.0,
                "max_risk": 0,
                "min_risk": 0,
                "total_flags": 0,
                "total_value_mkd": 0.0,
                "avg_bidders": 0.0,
                "single_bidder_rate": 0.0,
            }

        risks = [t["risk_score"] for t in tenders]
        flags = sum(t["flag_count"] for t in tenders)
        bidders = [t["bidder_count"] for t in tenders]
        sb_count = sum(1 for t in tenders if t.get("single_bidder"))
        total_value = sum(t["value_mkd"] for t in tenders if t.get("value_mkd"))
        n = len(tenders)

        return {
            "avg_risk": _safe_round(np.mean(risks), 1),
            "max_risk": int(np.max(risks)),
            "min_risk": int(np.min(risks)),
            "total_flags": int(flags),
            "total_value_mkd": _safe_round(total_value, 2),
            "avg_bidders": _safe_round(np.mean(bidders), 2) if bidders else 0.0,
            "single_bidder_rate": _safe_round(sb_count / n, 3) if n > 0 else 0.0,
        }


# ---------------------------------------------------------------------------
# Module-level helper functions
# ---------------------------------------------------------------------------

def _parse_date(date_val) -> Optional[date]:
    """Parse various date formats to a date object."""
    if date_val is None:
        return None
    if isinstance(date_val, datetime):
        return date_val.date()
    if isinstance(date_val, date):
        return date_val
    if isinstance(date_val, str):
        try:
            return datetime.fromisoformat(date_val).date()
        except (ValueError, TypeError):
            pass
        # Try common formats
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d.%m.%Y"):
            try:
                return datetime.strptime(date_val, fmt).date()
            except (ValueError, TypeError):
                continue
    return None


def _safe_round(value, decimals: int = 2):
    """Safely round a value, returning None if input is None or NaN."""
    if value is None:
        return None
    try:
        f = float(value)
        if np.isnan(f) or np.isinf(f):
            return None
        return round(f, decimals)
    except (TypeError, ValueError):
        return None
