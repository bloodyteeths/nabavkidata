"""
Corruption Detection Module for Public Procurement Tenders

This module implements statistical pattern detection algorithms to identify
suspicious tender activity that may indicate corruption, bid rigging, or
specification manipulation.

Detection Algorithms:
 1. SingleBidderDetector - Find tenders with only one bidder
 2. RepeatWinnerDetector - Find companies winning >60% at same institution
 3. PriceAnomalyDetector - Detect suspicious price patterns
 4. BidderClusteringDetector - Find companies that always bid together
 5. ShortDeadlineDetector - Flag unreasonably short submission windows (stat thresholds)
 6. ProcedureTypeDetector - Flag non-competitive procedure types
 7. IdenticalBidDetector - Detect identical bid prices (R028 collusion signal)
 8. ProfessionalLoserDetector - Detect cover bidders with <5% win rate (R025)
 9. ContractSplittingDetector - Same buyer+winner splitting contracts below thresholds
10. ShortDecisionDetector - Abnormally fast evaluation/award decisions
11. StrategicDisqualificationDetector - Systematic disqualification (R035/R036)
12. ContractValueGrowthDetector - Actual value significantly exceeds estimate
13. BidRotationDetector - Companies taking turns winning at same institution
14. ThresholdManipulationDetector - Values clustering just below thresholds
15. LateAmendmentDetector - Amendments close to or after deadline

Scoring: Corruption Risk Index (CRI) - weighted indicator-based score (0-100)

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import logging
import os
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass
from datetime import datetime, date, timedelta
from decimal import Decimal
from collections import defaultdict
import json
import statistics
import math

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration from environment variables
DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise ValueError("DATABASE_URL environment variable is required but not set")
# Strip SQLAlchemy dialect prefix if present (asyncpg needs plain postgresql://)
DB_URL = DB_URL.replace("postgresql+asyncpg://", "postgresql://")


@dataclass
class CorruptionFlag:
    """Data class representing a corruption red flag"""
    tender_id: str
    flag_type: str
    severity: str  # low, medium, high, critical
    score: int  # 0-100
    evidence: Dict
    description: str


class SingleBidderDetector:
    """
    Detect tenders with only one bidder - a strong indicator of possible
    specification rigging or market manipulation.

    Scoring:
    - Base: 40 points
    - +20 if high value (>5M MKD)
    - +20 if repeat winner at same entity (>3 wins in past 12 months)
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find all tenders with single bidder and score them"""
        logger.info("Running single bidder detection...")

        # Optimized query using window function instead of correlated subquery
        # This is 100x faster on large datasets (274k+ tenders)
        query = """
            WITH winner_history AS (
                -- Pre-calculate cumulative wins per winner/entity combination
                SELECT
                    procuring_entity,
                    winner,
                    publication_date,
                    COUNT(*) OVER (
                        PARTITION BY procuring_entity, winner
                        ORDER BY publication_date
                        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
                    ) as cumulative_wins
                FROM tenders
                WHERE status IN ('awarded', 'completed')
                  AND winner IS NOT NULL
            )
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.estimated_value_mkd,
                t.num_bidders,
                t.winner,
                t.publication_date,
                COALESCE(wh.cumulative_wins, 0) as previous_wins
            FROM tenders t
            LEFT JOIN winner_history wh
                ON t.procuring_entity = wh.procuring_entity
                AND t.winner = wh.winner
                AND t.publication_date = wh.publication_date
            WHERE t.num_bidders = 1
              AND t.status IN ('awarded', 'completed')
              AND t.winner IS NOT NULL
              AND t.estimated_value_mkd > 500000
            ORDER BY t.estimated_value_mkd DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                score = 40  # Base score

                # High value bonus
                if row['estimated_value_mkd'] and row['estimated_value_mkd'] > 5000000:
                    score += 20

                # Repeat winner bonus
                if row['previous_wins'] and row['previous_wins'] >= 3:
                    score += 20

                # Determine severity
                if score >= 70:
                    severity = 'critical'
                elif score >= 60:
                    severity = 'high'
                elif score >= 45:
                    severity = 'medium'
                else:
                    severity = 'low'

                evidence = {
                    'num_bidders': row['num_bidders'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                    'previous_wins_at_entity': row['previous_wins']
                }

                description = f"Само еден понудувач на тендер вреден {row['estimated_value_mkd']:,.0f} МКД"
                if row['previous_wins'] and row['previous_wins'] >= 3:
                    description += f". Истата фирма добила {row['previous_wins']} пати претходно."

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='single_bidder',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} single-bidder tenders")
            return flags

        except Exception as e:
            logger.error(f"Error in single bidder detection: {e}")
            raise


class RepeatWinnerDetector:
    """
    Detect companies winning >60% of tenders at the same institution.

    Scoring:
    - Base: 50 points
    - +10 for each 10% above 60% threshold
    - +20 if >10 wins total
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find companies with suspiciously high win rates at specific institutions"""
        logger.info("Running repeat winner detection...")

        query = """
            WITH winner_stats AS (
                SELECT
                    t.procuring_entity,
                    t.winner,
                    COUNT(*) as wins,
                    SUM(t.actual_value_mkd) as total_value_mkd,
                    COUNT(*) * 100.0 /
                        (SELECT COUNT(*)
                         FROM tenders t2
                         WHERE t2.procuring_entity = t.procuring_entity
                           AND (t2.status = 'awarded' OR t2.status = 'completed')
                           AND t2.winner IS NOT NULL) as win_percentage,
                    array_agg(t.tender_id ORDER BY t.publication_date DESC) FILTER (WHERE t.tender_id IS NOT NULL) as tender_ids
                FROM tenders t
                WHERE (t.status = 'awarded' OR t.status = 'completed')
                  AND t.winner IS NOT NULL
                  AND t.winner != ''
                GROUP BY t.procuring_entity, t.winner
                HAVING COUNT(*) >= 5
                   AND COUNT(*) * 100.0 /
                       (SELECT COUNT(*)
                        FROM tenders t2
                        WHERE t2.procuring_entity = t.procuring_entity
                          AND (t2.status = 'awarded' OR t2.status = 'completed')
                          AND t2.winner IS NOT NULL) > 60
            )
            SELECT * FROM winner_stats
            ORDER BY win_percentage DESC, wins DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                win_pct = float(row['win_percentage'])
                wins = row['wins']

                score = 50  # Base score

                # Bonus for each 10% above 60% threshold
                score += int((win_pct - 60) / 10) * 10

                # Bonus for high number of wins
                if wins > 10:
                    score += 20

                score = min(100, score)  # Cap at 100

                # Determine severity
                if score >= 80:
                    severity = 'critical'
                elif score >= 70:
                    severity = 'high'
                elif score >= 60:
                    severity = 'medium'
                else:
                    severity = 'low'

                evidence = {
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                    'wins': wins,
                    'win_percentage': round(win_pct, 1),
                    'total_value_mkd': float(row['total_value_mkd']) if row['total_value_mkd'] else None,
                    'sample_tenders': row['tender_ids'][:5]  # First 5 tender IDs
                }

                description = f"{row['winner']} добива {win_pct:.1f}% од тендерите кај {row['procuring_entity']} ({wins} од последните тендери)"

                # Use the most recent tender_id for the flag
                tender_id = row['tender_ids'][0] if row['tender_ids'] else None

                if tender_id:
                    flags.append(CorruptionFlag(
                        tender_id=tender_id,
                        flag_type='repeat_winner',
                        severity=severity,
                        score=score,
                        evidence=evidence,
                        description=description
                    ))

            logger.info(f"Found {len(flags)} repeat winner patterns")
            return flags

        except Exception as e:
            logger.error(f"Error in repeat winner detection: {e}")
            raise


class PriceAnomalyDetector:
    """
    Detect suspicious pricing patterns in bids:
    1. All bids suspiciously close (stddev/avg < 0.05) - possible collusion
    2. Winner's bid >2 std deviations below average - possible info leak
    3. Bids exactly matching estimated value (<1% diff) - possible price fixing

    Scoring: 45 base + modifiers
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Analyze bid prices for anomalies"""
        logger.info("Running price anomaly detection...")

        query = """
            WITH bid_stats AS (
                SELECT
                    tb.tender_id,
                    t.title,
                    t.procuring_entity,
                    t.estimated_value_mkd,
                    COUNT(*) as num_bids,
                    AVG(tb.bid_amount_mkd) as avg_bid,
                    STDDEV(tb.bid_amount_mkd) as stddev_bid,
                    MIN(tb.bid_amount_mkd) FILTER (WHERE tb.is_winner = true) as winner_bid,
                    array_agg(tb.bid_amount_mkd ORDER BY tb.bid_amount_mkd) as all_bids,
                    array_agg(tb.company_name ORDER BY tb.bid_amount_mkd) as all_bidders
                FROM tender_bidders tb
                JOIN tenders t ON tb.tender_id = t.tender_id
                WHERE tb.bid_amount_mkd > 0
                  AND t.estimated_value_mkd > 0
                GROUP BY tb.tender_id, t.title, t.procuring_entity, t.estimated_value_mkd
                HAVING COUNT(*) >= 3
            )
            SELECT *,
                CASE
                    WHEN stddev_bid > 0 THEN stddev_bid / avg_bid
                    ELSE 0
                END as coefficient_of_variation,
                CASE
                    WHEN stddev_bid > 0 THEN (avg_bid - winner_bid) / stddev_bid
                    ELSE 0
                END as winner_z_score,
                CASE
                    WHEN estimated_value_mkd > 0 THEN ABS(winner_bid - estimated_value_mkd) / estimated_value_mkd
                    ELSE 1
                END as distance_from_estimate
            FROM bid_stats
            WHERE (
                (stddev_bid / NULLIF(avg_bid, 0) < 0.05 AND stddev_bid / NULLIF(avg_bid, 0) > 0)
                OR
                ((avg_bid - winner_bid) / NULLIF(stddev_bid, 0) > 2)
                OR
                (ABS(winner_bid - estimated_value_mkd) / NULLIF(estimated_value_mkd, 0) < 0.01)
            )
            ORDER BY coefficient_of_variation ASC, winner_z_score DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                cov = float(row['coefficient_of_variation']) if row['coefficient_of_variation'] else 0
                z_score = float(row['winner_z_score']) if row['winner_z_score'] else 0
                dist_estimate = float(row['distance_from_estimate']) if row['distance_from_estimate'] else 1

                score = 45  # Base score
                anomaly_types = []

                # Check for collusion (low variance)
                if 0 < cov < 0.05:
                    score += 25
                    anomaly_types.append('collusion_pattern')

                # Check for info leak (winner unusually low)
                if z_score > 2:
                    score += 20
                    anomaly_types.append('unusually_low_winner')

                # Check for price fixing (matches estimate)
                if dist_estimate < 0.01:
                    score += 15
                    anomaly_types.append('matches_estimate')

                score = min(100, score)

                # Determine severity
                if score >= 80:
                    severity = 'critical'
                elif score >= 65:
                    severity = 'high'
                elif score >= 50:
                    severity = 'medium'
                else:
                    severity = 'low'

                evidence = {
                    'num_bids': row['num_bids'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'avg_bid_mkd': float(row['avg_bid']) if row['avg_bid'] else None,
                    'stddev_mkd': float(row['stddev_bid']) if row['stddev_bid'] else None,
                    'winner_bid_mkd': float(row['winner_bid']) if row['winner_bid'] else None,
                    'coefficient_of_variation': round(cov, 4),
                    'winner_z_score': round(z_score, 2),
                    'distance_from_estimate': round(dist_estimate, 4),
                    'anomaly_types': anomaly_types,
                    'all_bids': [float(b) for b in row['all_bids']] if row['all_bids'] else [],
                    'all_bidders': row['all_bidders']
                }

                description = "Сомнителни цени: "
                if 'collusion_pattern' in anomaly_types:
                    description += "сите понуди се премногу блиски (можна договореност), "
                if 'unusually_low_winner' in anomaly_types:
                    description += "победникот е далеку под другите (можно протекување информации), "
                if 'matches_estimate' in anomaly_types:
                    description += "цената точно одговара на проценката (можна манипулација)"

                description = description.rstrip(', ')

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='price_anomaly',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} price anomalies")
            return flags

        except Exception as e:
            logger.error(f"Error in price anomaly detection: {e}")
            raise


class BidderClusteringDetector:
    """
    Find pairs of companies that bid together >70% of the time.
    This may indicate bid rotation or cover bidding schemes.

    Scoring:
    - Base: 60 for >70% co-occurrence
    - +20 if one always wins when both bid (rotation pattern)
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find suspicious bidder clustering patterns"""
        logger.info("Running bidder clustering detection...")

        query = """
            WITH bidder_pairs AS (
                SELECT
                    t1.company_name as company_a,
                    t2.company_name as company_b,
                    COUNT(DISTINCT t1.tender_id) as co_occurrences,
                    array_agg(DISTINCT t1.tender_id) as tender_ids,
                    COUNT(DISTINCT t1.tender_id) FILTER (WHERE t1.is_winner = true) as a_wins_together,
                    COUNT(DISTINCT t2.tender_id) FILTER (WHERE t2.is_winner = true) as b_wins_together
                FROM tender_bidders t1
                JOIN tender_bidders t2 ON t1.tender_id = t2.tender_id
                    AND t1.company_name < t2.company_name
                WHERE t1.company_name != t2.company_name
                GROUP BY t1.company_name, t2.company_name
                HAVING COUNT(DISTINCT t1.tender_id) >= 5
            ),
            company_totals AS (
                SELECT
                    company_name,
                    COUNT(DISTINCT tender_id) as total_bids
                FROM tender_bidders
                GROUP BY company_name
            )
            SELECT
                bp.*,
                ca.total_bids as company_a_total,
                cb.total_bids as company_b_total,
                bp.co_occurrences * 100.0 / LEAST(ca.total_bids, cb.total_bids) as overlap_pct,
                CASE
                    WHEN bp.a_wins_together > bp.b_wins_together THEN bp.a_wins_together * 100.0 / bp.co_occurrences
                    ELSE bp.b_wins_together * 100.0 / bp.co_occurrences
                END as dominant_win_rate
            FROM bidder_pairs bp
            JOIN company_totals ca ON bp.company_a = ca.company_name
            JOIN company_totals cb ON bp.company_b = cb.company_name
            WHERE bp.co_occurrences * 100.0 / LEAST(ca.total_bids, cb.total_bids) > 70
            ORDER BY overlap_pct DESC, co_occurrences DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                overlap_pct = float(row['overlap_pct'])
                dominant_win_rate = float(row['dominant_win_rate']) if row['dominant_win_rate'] else 0

                score = 60  # Base score for high overlap

                # Bonus if one consistently wins (rotation pattern)
                if dominant_win_rate > 80:
                    score += 20

                score = min(100, score)

                # Determine severity
                if score >= 75:
                    severity = 'critical'
                elif score >= 65:
                    severity = 'high'
                else:
                    severity = 'medium'

                evidence = {
                    'company_a': row['company_a'],
                    'company_b': row['company_b'],
                    'co_occurrences': row['co_occurrences'],
                    'overlap_percentage': round(overlap_pct, 1),
                    'company_a_total_bids': row['company_a_total'],
                    'company_b_total_bids': row['company_b_total'],
                    'a_wins_when_together': row['a_wins_together'],
                    'b_wins_when_together': row['b_wins_together'],
                    'dominant_win_rate': round(dominant_win_rate, 1),
                    'sample_tenders': row['tender_ids'][:5]
                }

                description = f"{row['company_a']} и {row['company_b']} се натпреваруваат заедно во {overlap_pct:.1f}% од случаите ({row['co_occurrences']} тендери)"
                if dominant_win_rate > 80:
                    description += f" - еден секогаш добива ({dominant_win_rate:.0f}%)"

                # Use the most recent tender where they bid together
                tender_id = row['tender_ids'][0] if row['tender_ids'] else None

                if tender_id:
                    flags.append(CorruptionFlag(
                        tender_id=tender_id,
                        flag_type='bid_clustering',
                        severity=severity,
                        score=score,
                        evidence=evidence,
                        description=description
                    ))

            logger.info(f"Found {len(flags)} bidder clustering patterns")
            return flags

        except Exception as e:
            logger.error(f"Error in bidder clustering detection: {e}")
            raise


class ShortDeadlineDetector:
    """
    Detect tenders with unreasonably short submission windows.
    Short deadlines can prevent legitimate competition.

    Uses statistical thresholds from real data distribution:
    - P10 = 6 days (below this = CRITICAL)
    - P25 = 7 days (below this = HIGH)
    - P50 = 10 days (reference median)

    Scoring:
    - Base: 35 for days < P25 (7 days)
    - +25 if days < P10 (6 days) - CRITICAL zone
    - +30 if days < 3 (extreme outlier)
    - +20 if also single bidder
    """

    # Statistical thresholds computed from real data
    P10_DAYS = 6   # 10th percentile
    P25_DAYS = 7   # 25th percentile
    P50_DAYS = 10  # median

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with suspiciously short deadlines using statistical thresholds"""
        logger.info("Running short deadline detection (statistical thresholds)...")

        query = """
            SELECT
                tender_id,
                title,
                procuring_entity,
                publication_date,
                closing_date,
                closing_date - publication_date as days_open,
                estimated_value_mkd,
                num_bidders,
                status
            FROM tenders
            WHERE closing_date - publication_date < $1
              AND estimated_value_mkd > 500000
              AND status IN ('awarded', 'closed', 'completed')
              AND closing_date IS NOT NULL
              AND publication_date IS NOT NULL
            ORDER BY (closing_date - publication_date) ASC, estimated_value_mkd DESC
        """

        try:
            rows = await self.pool.fetch(query, self.P25_DAYS)
            flags = []

            for row in rows:
                days_open = row['days_open'].days if hasattr(row['days_open'], 'days') else int(row['days_open'])

                score = 35  # Base score for being below P25

                # Below P10 = critical zone
                if days_open < self.P10_DAYS:
                    score += 25

                # Extreme outlier
                if days_open < 3:
                    score += 30

                # Extra penalty if single bidder
                if row['num_bidders'] and row['num_bidders'] == 1:
                    score += 20

                score = min(100, score)

                # Determine severity based on statistical position
                if days_open < 3 or score >= 80:
                    severity = 'critical'
                elif days_open < self.P10_DAYS or score >= 60:
                    severity = 'high'
                elif score >= 45:
                    severity = 'medium'
                else:
                    severity = 'low'

                evidence = {
                    'publication_date': str(row['publication_date']),
                    'closing_date': str(row['closing_date']),
                    'days_open': days_open,
                    'percentile_position': 'below_P10' if days_open < self.P10_DAYS else 'below_P25',
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'num_bidders': row['num_bidders'],
                    'procuring_entity': row['procuring_entity'],
                    'thresholds': {'P10': self.P10_DAYS, 'P25': self.P25_DAYS, 'P50': self.P50_DAYS}
                }

                description = f"Премногу краток рок: само {days_open} дена за тендер вреден {row['estimated_value_mkd']:,.0f} МКД"
                if days_open < self.P10_DAYS:
                    description += f" (под P10={self.P10_DAYS} дена - статистички екстрем)"
                if row['num_bidders'] and row['num_bidders'] == 1:
                    description += " (само 1 понудувач)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='short_deadline',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} short deadline tenders")
            return flags

        except Exception as e:
            logger.error(f"Error in short deadline detection: {e}")
            raise


class ProcedureTypeDetector:
    """
    Flag non-competitive procedure types (negotiated, direct award, low-value).
    This is the #2 most validated corruption indicator globally.

    Normalizes Cyrillic procedure names to standard keys.

    Scoring:
    - Negotiated w/o prior publication: 60 (HIGH)
    - Low-value with estimated > 500K: 45 (MEDIUM, threshold gaming)
    - QualificationSystem: 35 (MEDIUM)
    - Open/SimplifiedOpen/RFP: no flag (normal competitive)
    """

    # Map Cyrillic procedure types to standard keys
    PROCEDURE_NORMALIZATION = {
        # Cyrillic -> standard
        'Набавки од мала вредност': 'LowEstimatedValueProcedure',
        'Поедноставена отворена постапка': 'SimplifiedOpenProcedure',
        'Отворена постапка': 'Open',
        'Барање за прибирање на понуди': 'RequestForProposal',
        # Already standard (pass through)
        'LowEstimatedValueProcedure': 'LowEstimatedValueProcedure',
        'SimplifiedOpenProcedure': 'SimplifiedOpenProcedure',
        'Open': 'Open',
        'RequestForProposal': 'RequestForProposal',
        'QualificationSystem': 'QualificationSystem',
        'BidForChoosingIdealSolution': 'BidForChoosingIdealSolution',
        'NegotiatedProcedureWithoutPriorPublication': 'NegotiatedProcedureWithoutPriorPublication',
        'ProcedureForTalkingWithPreviousAnnouncement': 'ProcedureForTalkingWithPreviousAnnouncement',
    }

    # Competitive procedures (no flag)
    COMPETITIVE_PROCEDURES = {
        'Open', 'SimplifiedOpenProcedure', 'RequestForProposal',
    }

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    def _normalize_procedure(self, raw_type: str) -> str:
        """Normalize procedure type, mapping Cyrillic to standard keys"""
        if not raw_type:
            return 'Unknown'
        return self.PROCEDURE_NORMALIZATION.get(raw_type.strip(), raw_type.strip())

    async def detect(self) -> List[CorruptionFlag]:
        """Flag tenders using non-competitive procedures"""
        logger.info("Running procedure type risk detection...")

        query = """
            SELECT
                tender_id,
                title,
                procuring_entity,
                procedure_type,
                estimated_value_mkd,
                num_bidders,
                winner
            FROM tenders
            WHERE procedure_type IS NOT NULL
              AND procedure_type != ''
              AND status IN ('awarded', 'completed')
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                normalized = self._normalize_procedure(row['procedure_type'])

                # Skip competitive procedures
                if normalized in self.COMPETITIVE_PROCEDURES:
                    continue

                score = 0
                severity = 'low'
                reason = ''

                # Negotiated without prior publication (highest risk)
                if normalized in ('NegotiatedProcedureWithoutPriorPublication',
                                  'ProcedureForTalkingWithPreviousAnnouncement'):
                    score = 60
                    severity = 'high'
                    reason = 'Преговарачка постапка без претходно објавување - ограничена конкуренција'

                # Low-value procedure with suspiciously high estimated value (threshold gaming)
                elif normalized == 'LowEstimatedValueProcedure':
                    est_val = row['estimated_value_mkd']
                    if est_val and float(est_val) > 500000:
                        score = 45
                        severity = 'medium'
                        reason = f'Набавка од мала вредност со проценка од {float(est_val):,.0f} МКД - можно избегнување на праг'
                    else:
                        continue  # Low-value with low estimate is normal

                # Qualification system
                elif normalized == 'QualificationSystem':
                    score = 35
                    severity = 'medium'
                    reason = 'Квалификационен систем - ограничен пристап за нови понудувачи'

                # BidForChoosingIdealSolution and other non-standard
                elif normalized == 'BidForChoosingIdealSolution':
                    score = 30
                    severity = 'low'
                    reason = 'Конкурс за избор на идејно решение - субјективно оценување'

                else:
                    # Unknown/non-standard procedure type
                    continue

                if score == 0:
                    continue

                evidence = {
                    'procedure_type_raw': row['procedure_type'],
                    'procedure_type_normalized': normalized,
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'num_bidders': row['num_bidders'],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                }

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='procedure_type',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=reason
                ))

            logger.info(f"Found {len(flags)} procedure type risk flags")
            return flags

        except Exception as e:
            logger.error(f"Error in procedure type detection: {e}")
            raise


class IdenticalBidDetector:
    """
    Detect identical bid prices from different companies (R028).
    Direct collusion signal with near-zero false positive rate.

    Scoring:
    - Base: 75 (HIGH)
    - +15 if identical amount matches estimated value (price fixing from estimate)
    - Severity: always 'high' or 'critical'
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders where multiple companies submitted identical bid amounts"""
        logger.info("Running identical bid detection (R028)...")

        query = """
            WITH identical_bids AS (
                SELECT
                    tb.tender_id,
                    tb.bid_amount_mkd,
                    ARRAY_AGG(tb.company_name ORDER BY tb.company_name) as companies,
                    COUNT(DISTINCT tb.company_name) as num_identical
                FROM tender_bidders tb
                WHERE tb.bid_amount_mkd > 0
                GROUP BY tb.tender_id, tb.bid_amount_mkd
                HAVING COUNT(DISTINCT tb.company_name) > 1
            )
            SELECT
                ib.tender_id,
                ib.bid_amount_mkd,
                ib.companies,
                ib.num_identical,
                t.title,
                t.procuring_entity,
                t.estimated_value_mkd,
                t.winner,
                t.num_bidders
            FROM identical_bids ib
            JOIN tenders t ON ib.tender_id = t.tender_id
            ORDER BY ib.num_identical DESC, ib.bid_amount_mkd DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                score = 75  # Base: very high confidence collusion signal

                # Check if identical amount matches estimated value
                est_val = row['estimated_value_mkd']
                bid_val = row['bid_amount_mkd']
                if est_val and bid_val and float(est_val) > 0:
                    diff_pct = abs(float(bid_val) - float(est_val)) / float(est_val)
                    if diff_pct < 0.01:  # Within 1% of estimate
                        score += 15

                score = min(100, score)

                severity = 'critical' if score >= 85 else 'high'

                evidence = {
                    'identical_bid_amount_mkd': float(bid_val) if bid_val else None,
                    'companies_with_identical_bid': list(row['companies']),
                    'num_identical_bidders': row['num_identical'],
                    'estimated_value_mkd': float(est_val) if est_val else None,
                    'matches_estimate': est_val and bid_val and abs(float(bid_val) - float(est_val)) / max(float(est_val), 1) < 0.01,
                    'winner': row['winner'],
                    'total_bidders': row['num_bidders'],
                }

                companies_str = ', '.join(row['companies'][:3])
                if len(row['companies']) > 3:
                    companies_str += f' (+{len(row["companies"]) - 3} други)'

                description = (
                    f"Идентични понуди од {row['num_identical']} фирми: {companies_str} "
                    f"- износ {float(bid_val):,.0f} МКД"
                )
                if evidence.get('matches_estimate'):
                    description += " (точно одговара на проценката - можна манипулација со цена)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='identical_bids',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} identical bid flags")
            return flags

        except Exception as e:
            logger.error(f"Error in identical bid detection: {e}")
            raise


class ProfessionalLoserDetector:
    """
    Detect professional losers / cover bidders (R025).
    Companies that bid frequently but rarely win (< 5% win rate with 10+ bids).

    Scoring:
    - Base: 40 (MEDIUM)
    - +20 if the professional loser also appears in a bidder cluster with the winner
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders where professional losers participated"""
        logger.info("Running professional loser detection (R025)...")

        query = """
            WITH company_stats AS (
                SELECT
                    company_name,
                    COUNT(*) as total_bids,
                    SUM(CASE WHEN is_winner THEN 1 ELSE 0 END) as wins,
                    ROUND(SUM(CASE WHEN is_winner THEN 1 ELSE 0 END)::numeric
                          / COUNT(*) * 100, 1) as win_pct
                FROM tender_bidders
                GROUP BY company_name
                HAVING COUNT(*) >= 10
            ),
            pro_losers AS (
                SELECT company_name, total_bids, wins, win_pct
                FROM company_stats
                WHERE wins::numeric / total_bids < 0.05
            )
            SELECT
                tb.tender_id,
                tb.company_name as loser_name,
                pl.total_bids as loser_total_bids,
                pl.wins as loser_wins,
                pl.win_pct as loser_win_pct,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd
            FROM tender_bidders tb
            JOIN pro_losers pl ON tb.company_name = pl.company_name
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE NOT tb.is_winner
              AND t.status IN ('awarded', 'completed')
              AND t.winner IS NOT NULL
            ORDER BY pl.total_bids DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            # Check for bidder clusters to apply bonus
            # Pre-load known cluster pairs
            cluster_pairs: Set[Tuple[str, str]] = set()
            try:
                cluster_query = """
                    SELECT DISTINCT evidence->>'company_a' as a, evidence->>'company_b' as b
                    FROM corruption_flags
                    WHERE flag_type = 'bid_clustering'
                """
                cluster_rows = await self.pool.fetch(cluster_query)
                for cr in cluster_rows:
                    if cr['a'] and cr['b']:
                        cluster_pairs.add((cr['a'], cr['b']))
                        cluster_pairs.add((cr['b'], cr['a']))
            except Exception:
                pass  # Clusters may not exist yet on first run

            # Deduplicate: one flag per (tender_id, loser_name)
            seen = set()
            for row in rows:
                key = (row['tender_id'], row['loser_name'])
                if key in seen:
                    continue
                seen.add(key)

                score = 40  # Base

                # Check if loser is in a cluster with the winner
                winner = row['winner']
                loser = row['loser_name']
                if winner and (loser, winner) in cluster_pairs:
                    score += 20

                score = min(100, score)

                severity = 'high' if score >= 55 else 'medium'

                evidence = {
                    'professional_loser': loser,
                    'loser_total_bids': row['loser_total_bids'],
                    'loser_wins': row['loser_wins'],
                    'loser_win_pct': float(row['loser_win_pct']) if row['loser_win_pct'] else 0,
                    'winner': winner,
                    'in_cluster_with_winner': winner and (loser, winner) in cluster_pairs,
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'procuring_entity': row['procuring_entity'],
                }

                description = (
                    f"Професионален губитник: {loser} (победува {row['loser_win_pct']}% од "
                    f"{row['loser_total_bids']} понуди) - можен покривач на {winner}"
                )
                if evidence.get('in_cluster_with_winner'):
                    description += " (во кластер со победникот)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='professional_loser',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} professional loser flags")
            return flags

        except Exception as e:
            logger.error(f"Error in professional loser detection: {e}")
            raise


class ContractSplittingDetector:
    """
    Detect contract splitting: same buyer + same winner + multiple contracts
    within a quarter + individual values below thresholds but total exceeds them.

    Scoring:
    - Base: 65 (HIGH)
    - +15 if all values in top 20% of sub-threshold band
    - +10 if 5+ contracts in same quarter
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find potential contract splitting patterns"""
        logger.info("Running contract splitting detection...")

        query = """
            WITH splitting_candidates AS (
                SELECT
                    procuring_entity,
                    winner,
                    DATE_TRUNC('quarter', publication_date) as quarter,
                    COUNT(*) as contract_count,
                    AVG(estimated_value_mkd) as avg_value,
                    MAX(estimated_value_mkd) as max_value,
                    MIN(estimated_value_mkd) as min_value,
                    MIN(publication_date) as first_date,
                    MAX(publication_date) as last_date,
                    SUM(estimated_value_mkd) as total_value,
                    array_agg(tender_id ORDER BY publication_date) as tender_ids,
                    array_agg(estimated_value_mkd ORDER BY publication_date) as values_list
                FROM tenders
                WHERE status IN ('awarded', 'completed')
                  AND winner IS NOT NULL AND winner != ''
                  AND estimated_value_mkd > 0
                  AND publication_date IS NOT NULL
                GROUP BY procuring_entity, winner, DATE_TRUNC('quarter', publication_date)
                HAVING COUNT(*) >= 3
                  AND MAX(estimated_value_mkd) < 1000000
                  AND SUM(estimated_value_mkd) > 1000000
            )
            SELECT * FROM splitting_candidates
            ORDER BY total_value DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                score = 65  # Base - high confidence indicator

                max_val = float(row['max_value']) if row['max_value'] else 0
                contract_count = row['contract_count']

                # Check if values cluster in top 20% of sub-threshold band
                # (i.e., 800K-1M range for the 1M threshold)
                if max_val > 800000:
                    score += 15

                # 5+ contracts in same quarter is more suspicious
                if contract_count >= 5:
                    score += 10

                score = min(100, score)

                severity = 'critical' if score >= 80 else 'high'

                evidence = {
                    'procuring_entity': row['procuring_entity'],
                    'winner': row['winner'],
                    'quarter': str(row['quarter']),
                    'contract_count': contract_count,
                    'total_value_mkd': float(row['total_value']) if row['total_value'] else None,
                    'max_individual_value_mkd': max_val,
                    'avg_value_mkd': float(row['avg_value']) if row['avg_value'] else None,
                    'first_date': str(row['first_date']),
                    'last_date': str(row['last_date']),
                    'tender_ids': list(row['tender_ids']),
                }

                description = (
                    f"Расцепкување на договор: {row['procuring_entity']} доделил {contract_count} "
                    f"договори на {row['winner']} во ист квартал - поединечно под 1М, "
                    f"вкупно {float(row['total_value']):,.0f} МКД"
                )

                # Flag each involved tender
                for tid in row['tender_ids']:
                    flags.append(CorruptionFlag(
                        tender_id=tid,
                        flag_type='contract_splitting',
                        severity=severity,
                        score=score,
                        evidence=evidence,
                        description=description
                    ))

            logger.info(f"Found {len(flags)} contract splitting flags")
            return flags

        except Exception as e:
            logger.error(f"Error in contract splitting detection: {e}")
            raise


class ShortDecisionDetector:
    """
    Detect abnormally fast evaluation decisions.
    decision_days = contract_signing_date - closing_date

    Scoring:
    - Base: 45 if decision_days < 3
    - +20 if decision_days = 0 or 1 (same day/next day = predetermined)
    - +15 if also single bidder
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with suspiciously fast award decisions"""
        logger.info("Running short decision period detection...")

        query = """
            SELECT
                tender_id,
                title,
                procuring_entity,
                closing_date,
                contract_signing_date,
                (contract_signing_date - closing_date) as decision_days,
                estimated_value_mkd,
                num_bidders,
                winner
            FROM tenders
            WHERE contract_signing_date IS NOT NULL
              AND closing_date IS NOT NULL
              AND (contract_signing_date - closing_date) < 3
              AND (contract_signing_date - closing_date) >= 0
              AND status IN ('awarded', 'completed')
            ORDER BY (contract_signing_date - closing_date) ASC, estimated_value_mkd DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                decision_days = row['decision_days']
                if hasattr(decision_days, 'days'):
                    decision_days = decision_days.days
                else:
                    decision_days = int(decision_days)

                score = 45  # Base

                # Same day or next day award = highly predetermined
                if decision_days <= 1:
                    score += 20

                # Also single bidder
                if row['num_bidders'] and row['num_bidders'] == 1:
                    score += 15

                score = min(100, score)

                if score >= 75:
                    severity = 'critical'
                elif score >= 60:
                    severity = 'high'
                else:
                    severity = 'medium'

                evidence = {
                    'closing_date': str(row['closing_date']),
                    'contract_signing_date': str(row['contract_signing_date']),
                    'decision_days': decision_days,
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'num_bidders': row['num_bidders'],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                }

                description = (
                    f"Ултра-брза одлука: само {decision_days} дена од затворање до потпишување на договор"
                )
                if decision_days <= 1:
                    description += " (ист/следен ден - можна предодредена одлука)"
                if row['num_bidders'] and row['num_bidders'] == 1:
                    description += " (само 1 понудувач)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='short_decision',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} short decision period flags")
            return flags

        except Exception as e:
            logger.error(f"Error in short decision detection: {e}")
            raise


class StrategicDisqualificationDetector:
    """
    Detect systematic disqualification of bidders (R035/R036).

    R035: All bids except winner disqualified
    R036: Lowest bid disqualified when evaluation is price-only

    Scoring:
    - 70 (HIGH) when all except winner disqualified
    - 55 (MEDIUM) when lowest bid disqualified with price-only evaluation
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with strategic disqualification patterns"""
        logger.info("Running strategic disqualification detection (R035/R036)...")

        flags = []

        # R035: All bids except winner disqualified
        r035_query = """
            SELECT
                tb.tender_id,
                COUNT(*) as total_bidders,
                SUM(CASE WHEN tb.disqualified THEN 1 ELSE 0 END) as disqualified_count,
                SUM(CASE WHEN tb.is_winner THEN 1 ELSE 0 END) as winner_count,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                ARRAY_AGG(tb.company_name) FILTER (WHERE tb.disqualified) as disqualified_companies
            FROM tender_bidders tb
            JOIN tenders t ON tb.tender_id = t.tender_id
            WHERE t.status IN ('awarded', 'completed')
            GROUP BY tb.tender_id, t.title, t.procuring_entity, t.winner, t.estimated_value_mkd
            HAVING SUM(CASE WHEN tb.disqualified THEN 1 ELSE 0 END) >= 2
              AND SUM(CASE WHEN tb.disqualified THEN 1 ELSE 0 END) =
                  COUNT(*) - SUM(CASE WHEN tb.is_winner THEN 1 ELSE 0 END)
        """

        try:
            rows = await self.pool.fetch(r035_query)
            for row in rows:
                score = 70
                severity = 'high'

                disq_companies = list(row['disqualified_companies']) if row['disqualified_companies'] else []

                evidence = {
                    'indicator': 'R035',
                    'total_bidders': row['total_bidders'],
                    'disqualified_count': row['disqualified_count'],
                    'disqualified_companies': disq_companies[:5],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                }

                description = (
                    f"Стратешка дисквалификација: {row['disqualified_count']} од {row['total_bidders']} "
                    f"понудувачи дисквалификувани - победи само {row['winner']}"
                )

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='strategic_disqualification',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

        except Exception as e:
            logger.error(f"Error in R035 detection: {e}")

        # R036: Lowest bid disqualified (price-only evaluation)
        r036_query = """
            WITH lowest_bidder AS (
                SELECT
                    tb.tender_id,
                    tb.company_name,
                    tb.bid_amount_mkd,
                    tb.disqualified,
                    tb.disqualification_reason,
                    ROW_NUMBER() OVER (
                        PARTITION BY tb.tender_id
                        ORDER BY tb.bid_amount_mkd ASC
                    ) as price_rank
                FROM tender_bidders tb
                WHERE tb.bid_amount_mkd > 0
            )
            SELECT
                lb.tender_id,
                lb.company_name as disqualified_lowest,
                lb.bid_amount_mkd as lowest_bid,
                lb.disqualification_reason,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.evaluation_method
            FROM lowest_bidder lb
            JOIN tenders t ON lb.tender_id = t.tender_id
            WHERE lb.price_rank = 1
              AND lb.disqualified = true
              AND t.status IN ('awarded', 'completed')
              AND (
                  t.evaluation_method ILIKE '%najniska cena%'
                  OR t.evaluation_method ILIKE '%lowest%'
                  OR t.evaluation_method ILIKE '%цена%'
                  OR t.evaluation_method ILIKE '%најниска%'
              )
        """

        try:
            rows = await self.pool.fetch(r036_query)
            for row in rows:
                score = 55
                severity = 'medium'

                evidence = {
                    'indicator': 'R036',
                    'disqualified_lowest_bidder': row['disqualified_lowest'],
                    'lowest_bid_mkd': float(row['lowest_bid']) if row['lowest_bid'] else None,
                    'disqualification_reason': row['disqualification_reason'],
                    'evaluation_method': row['evaluation_method'],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                }

                description = (
                    f"Дисквалификуван најевтин понудувач ({row['disqualified_lowest']}, "
                    f"{float(row['lowest_bid']):,.0f} МКД) при оценка по најниска цена"
                )

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='strategic_disqualification',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

        except Exception as e:
            logger.error(f"Error in R036 detection: {e}")

        logger.info(f"Found {len(flags)} strategic disqualification flags")
        return flags


class ContractValueGrowthDetector:
    """
    Detect contracts where actual value significantly exceeds estimated value.
    This indicates amendment/change order abuse.

    Scoring:
    - Base: 40 + MIN(40, overrun_pct / 5) (scales with severity)
    - +10 if also has amendments
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with significant contract value growth"""
        logger.info("Running contract value growth detection...")

        query = """
            SELECT
                tender_id,
                title,
                procuring_entity,
                winner,
                estimated_value_mkd,
                actual_value_mkd,
                (actual_value_mkd / estimated_value_mkd - 1) * 100 as overrun_pct,
                amendment_count
            FROM tenders
            WHERE actual_value_mkd IS NOT NULL
              AND estimated_value_mkd > 0
              AND actual_value_mkd > estimated_value_mkd * 1.2
              AND status IN ('awarded', 'completed')
            ORDER BY (actual_value_mkd / estimated_value_mkd) DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                overrun_pct = float(row['overrun_pct']) if row['overrun_pct'] else 0

                # Scaled score: 40 base + up to 40 more based on overrun severity
                score = 40 + min(40, int(overrun_pct / 5))

                # Bonus for amendments (confirms change order abuse pattern)
                if row['amendment_count'] and row['amendment_count'] > 0:
                    score += 10

                score = min(100, score)

                if score >= 75:
                    severity = 'critical'
                elif score >= 60:
                    severity = 'high'
                elif score >= 45:
                    severity = 'medium'
                else:
                    severity = 'low'

                evidence = {
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'actual_value_mkd': float(row['actual_value_mkd']) if row['actual_value_mkd'] else None,
                    'overrun_percentage': round(overrun_pct, 1),
                    'amendment_count': row['amendment_count'],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                }

                description = (
                    f"Раст на вредност на договор: реална вредност {float(row['actual_value_mkd']):,.0f} МКД "
                    f"наспроти проценка {float(row['estimated_value_mkd']):,.0f} МКД "
                    f"(+{overrun_pct:.1f}%)"
                )
                if row['amendment_count'] and row['amendment_count'] > 0:
                    description += f" ({row['amendment_count']} амандмани)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='contract_value_growth',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} contract value growth flags")
            return flags

        except Exception as e:
            logger.error(f"Error in contract value growth detection: {e}")
            raise


class BidRotationDetector:
    """
    Detect bid rotation: companies taking turns winning at same institution.
    Cartel behavior indicator.

    Analyzes institutions with 10+ tenders and 2-5 unique winners,
    checking for alternation patterns (A->B->A->B).

    Scoring:
    - Base: 55 (MEDIUM)
    - +20 if alternation pattern detected
    - +15 if combined value > 10M MKD
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find bid rotation patterns at institutions"""
        logger.info("Running bid rotation detection...")

        query = """
            WITH institution_tenders AS (
                SELECT
                    procuring_entity,
                    winner,
                    publication_date,
                    tender_id,
                    estimated_value_mkd,
                    ROW_NUMBER() OVER (
                        PARTITION BY procuring_entity
                        ORDER BY publication_date
                    ) as seq
                FROM tenders
                WHERE status IN ('awarded', 'completed')
                  AND winner IS NOT NULL AND winner != ''
                  AND publication_date IS NOT NULL
            ),
            institution_stats AS (
                SELECT
                    procuring_entity,
                    COUNT(DISTINCT winner) as unique_winners,
                    COUNT(*) as total_tenders,
                    SUM(estimated_value_mkd) as total_value_mkd,
                    array_agg(winner ORDER BY publication_date) as winner_sequence,
                    array_agg(tender_id ORDER BY publication_date) as tender_ids
                FROM institution_tenders
                GROUP BY procuring_entity
                HAVING COUNT(*) >= 10
                  AND COUNT(DISTINCT winner) BETWEEN 2 AND 5
            )
            SELECT * FROM institution_stats
            ORDER BY total_tenders DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                winner_seq = list(row['winner_sequence']) if row['winner_sequence'] else []
                if len(winner_seq) < 10:
                    continue

                score = 55  # Base

                # Detect alternation pattern
                has_alternation = self._detect_alternation(winner_seq)
                if has_alternation:
                    score += 20

                # High combined value bonus
                total_val = float(row['total_value_mkd']) if row['total_value_mkd'] else 0
                if total_val > 10_000_000:
                    score += 15

                score = min(100, score)

                if score >= 75:
                    severity = 'critical'
                elif score >= 65:
                    severity = 'high'
                else:
                    severity = 'medium'

                evidence = {
                    'procuring_entity': row['procuring_entity'],
                    'unique_winners': row['unique_winners'],
                    'total_tenders': row['total_tenders'],
                    'total_value_mkd': total_val,
                    'alternation_detected': has_alternation,
                    'winner_sequence_sample': winner_seq[:20],
                    'tender_ids_sample': list(row['tender_ids'])[:10] if row['tender_ids'] else [],
                }

                winners_str = ', '.join(set(winner_seq[:5]))
                description = (
                    f"Ротација на победници кај {row['procuring_entity']}: "
                    f"{row['unique_winners']} фирми наизменично добиваат "
                    f"{row['total_tenders']} тендери ({winners_str})"
                )
                if has_alternation:
                    description += " - детектиран A-B-A-B образец"

                # Flag the most recent tender
                tender_ids = list(row['tender_ids']) if row['tender_ids'] else []
                if tender_ids:
                    flags.append(CorruptionFlag(
                        tender_id=tender_ids[-1],
                        flag_type='bid_rotation',
                        severity=severity,
                        score=score,
                        evidence=evidence,
                        description=description
                    ))

            logger.info(f"Found {len(flags)} bid rotation flags")
            return flags

        except Exception as e:
            logger.error(f"Error in bid rotation detection: {e}")
            raise

    @staticmethod
    def _detect_alternation(winner_seq: List[str]) -> bool:
        """
        Detect if winners alternate in a pattern (A,B,A,B or A,B,C,A,B,C).
        Returns True if a repeating subsequence covers >50% of the sequence.
        """
        if len(winner_seq) < 6:
            return False

        # Check for period-2 alternation (A,B,A,B)
        for period in [2, 3]:
            if len(winner_seq) < period * 3:
                continue
            pattern = winner_seq[:period]
            matches = 0
            for i in range(len(winner_seq)):
                if winner_seq[i] == pattern[i % period]:
                    matches += 1
            if matches / len(winner_seq) > 0.6:
                return True

        return False


class ThresholdManipulationDetector:
    """
    Detect tender values clustering just below procurement thresholds.

    Key Macedonian thresholds: 500K, 1M, 2M, 5M, 10M, 20M MKD
    Flag if value is within 5% below a threshold.

    Scoring:
    - Base: 35 (LOW-MEDIUM)
    - +15 if same buyer has 3+ tenders just below same threshold
    - +20 if also single bidder or negotiated procedure
    """

    THRESHOLDS_MKD = [500_000, 1_000_000, 2_000_000, 5_000_000, 10_000_000, 20_000_000]

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with values clustering just below thresholds"""
        logger.info("Running threshold manipulation detection...")

        # Build WHERE clause for all threshold bands
        threshold_conditions = []
        for t in self.THRESHOLDS_MKD:
            lower = int(t * 0.95)
            threshold_conditions.append(
                f"(estimated_value_mkd >= {lower} AND estimated_value_mkd < {t})"
            )
        where_clause = " OR ".join(threshold_conditions)

        query = f"""
            SELECT
                tender_id,
                title,
                procuring_entity,
                estimated_value_mkd,
                num_bidders,
                procedure_type,
                winner
            FROM tenders
            WHERE ({where_clause})
              AND estimated_value_mkd > 0
              AND status IN ('awarded', 'completed', 'active', 'closed')
            ORDER BY estimated_value_mkd DESC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            # Count how many times each buyer is just below each threshold
            buyer_threshold_counts: Dict[Tuple[str, int], int] = defaultdict(int)
            for row in rows:
                val = float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else 0
                buyer = row['procuring_entity']
                for t in self.THRESHOLDS_MKD:
                    if t * 0.95 <= val < t:
                        buyer_threshold_counts[(buyer, t)] += 1
                        break

            for row in rows:
                val = float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else 0
                if val == 0:
                    continue

                # Find which threshold this is near
                near_threshold = None
                for t in self.THRESHOLDS_MKD:
                    if t * 0.95 <= val < t:
                        near_threshold = t
                        break

                if near_threshold is None:
                    continue

                score = 35  # Base

                # Same buyer has 3+ tenders near same threshold
                buyer = row['procuring_entity']
                if buyer_threshold_counts.get((buyer, near_threshold), 0) >= 3:
                    score += 15

                # Single bidder or negotiated procedure
                is_single = row['num_bidders'] and row['num_bidders'] == 1
                proc_type = row['procedure_type'] or ''
                is_negotiated = 'Negotiated' in proc_type or 'Преговарачка' in proc_type
                if is_single or is_negotiated:
                    score += 20

                score = min(100, score)

                if score >= 65:
                    severity = 'high'
                elif score >= 50:
                    severity = 'medium'
                else:
                    severity = 'low'

                pct_below = (1 - val / near_threshold) * 100

                evidence = {
                    'estimated_value_mkd': val,
                    'nearest_threshold_mkd': near_threshold,
                    'pct_below_threshold': round(pct_below, 2),
                    'buyer_count_at_threshold': buyer_threshold_counts.get((buyer, near_threshold), 0),
                    'num_bidders': row['num_bidders'],
                    'procedure_type': row['procedure_type'],
                    'procuring_entity': buyer,
                    'winner': row['winner'],
                }

                description = (
                    f"Вредност {val:,.0f} МКД е {pct_below:.1f}% под прагот од "
                    f"{near_threshold:,.0f} МКД - можно избегнување на построга постапка"
                )
                if buyer_threshold_counts.get((buyer, near_threshold), 0) >= 3:
                    description += f" (истиот купувач има {buyer_threshold_counts[(buyer, near_threshold)]} вакви тендери)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='threshold_manipulation',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} threshold manipulation flags")
            return flags

        except Exception as e:
            logger.error(f"Error in threshold manipulation detection: {e}")
            raise


class LateAmendmentDetector:
    """
    Detect amendments made close to or after the deadline.
    Late amendments can change specifications to favor specific bidders.

    Scoring:
    - Base: 45 (MEDIUM)
    - +25 if amendment is AFTER closing_date (retroactive change)
    - +15 if also has single bidder
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def detect(self) -> List[CorruptionFlag]:
        """Find tenders with late amendments"""
        logger.info("Running late amendment detection...")

        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.amendment_count,
                t.last_amendment_date,
                t.closing_date,
                (t.closing_date - t.last_amendment_date) as days_before_close,
                t.estimated_value_mkd,
                t.num_bidders,
                t.winner
            FROM tenders t
            WHERE t.amendment_count > 0
              AND t.last_amendment_date IS NOT NULL
              AND t.closing_date IS NOT NULL
              AND (t.closing_date - t.last_amendment_date) <= 3
              AND t.status IN ('awarded', 'completed', 'active', 'closed')
            ORDER BY (t.closing_date - t.last_amendment_date) ASC
        """

        try:
            rows = await self.pool.fetch(query)
            flags = []

            for row in rows:
                days_before = row['days_before_close']
                if hasattr(days_before, 'days'):
                    days_before = days_before.days
                else:
                    days_before = int(days_before)

                score = 45  # Base

                # Amendment AFTER closing date (retroactive)
                if days_before < 0:
                    score += 25

                # Single bidder compound risk
                if row['num_bidders'] and row['num_bidders'] == 1:
                    score += 15

                score = min(100, score)

                if score >= 75:
                    severity = 'critical'
                elif score >= 60:
                    severity = 'high'
                else:
                    severity = 'medium'

                evidence = {
                    'amendment_count': row['amendment_count'],
                    'last_amendment_date': str(row['last_amendment_date']),
                    'closing_date': str(row['closing_date']),
                    'days_before_close': days_before,
                    'is_retroactive': days_before < 0,
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'num_bidders': row['num_bidders'],
                    'winner': row['winner'],
                    'procuring_entity': row['procuring_entity'],
                }

                if days_before < 0:
                    description = (
                        f"Ретроактивен амандман: измена {abs(days_before)} дена ПО затворање на тендерот"
                    )
                else:
                    description = (
                        f"Доцен амандман: измена само {days_before} дена пред затворање"
                    )

                if row['num_bidders'] and row['num_bidders'] == 1:
                    description += " (само 1 понудувач)"

                flags.append(CorruptionFlag(
                    tender_id=row['tender_id'],
                    flag_type='late_amendment',
                    severity=severity,
                    score=score,
                    evidence=evidence,
                    description=description
                ))

            logger.info(f"Found {len(flags)} late amendment flags")
            return flags

        except Exception as e:
            logger.error(f"Error in late amendment detection: {e}")
            raise


class CorruptionScorer:
    """
    Compute Corruption Risk Index (CRI) per tender.

    The CRI is a weighted indicator-based score (0-100).
    Each flag type is treated as a binary indicator (present/not present).
    Weights reflect indicator reliability based on academic literature.

    CRI = weighted_count / max_possible_weighted * 100
    """

    # Reliability weights for each indicator type
    WEIGHTS = {
        'single_bidder': 1.0,
        'procedure_type': 1.2,         # Highly validated globally
        'contract_splitting': 1.3,
        'identical_bids': 1.5,         # Near-zero false positive
        'strategic_disqualification': 1.4,
        'bid_rotation': 1.2,
        'professional_loser': 0.8,     # Lower individual precision
        'short_deadline': 0.9,
        'short_decision': 1.0,
        'contract_value_growth': 1.0,
        'late_amendment': 0.9,
        'threshold_manipulation': 0.8,
        'repeat_winner': 1.1,
        'price_anomaly': 1.1,
        'bid_clustering': 1.2,
    }

    # Maximum possible weighted score (sum of all weights)
    MAX_WEIGHTED = sum(WEIGHTS.values())

    @staticmethod
    def calculate_score(flags: List[CorruptionFlag]) -> Tuple[int, str]:
        """
        Calculate Corruption Risk Index (CRI) for a tender.

        Uses weighted average of flag scores with multi-indicator bonus.
        Base = weighted average of individual flag scores (preserves severity).
        Bonus = +8 per additional distinct indicator type (rewards breadth).

        This produces meaningful scores:
        - 1 flag (score 40) → CRI 40 (medium)
        - 2 flags avg 45 → CRI 53 (medium)
        - 3 flags avg 50 → CRI 66 (high)
        - 5+ flags → CRI 80+ (critical)

        Returns:
            Tuple of (cri_score 0-100, risk_level)
        """
        if not flags:
            return 0, 'minimal'

        # Group flags by type, take max score per type
        type_scores: Dict[str, int] = {}
        for flag in flags:
            existing = type_scores.get(flag.flag_type, 0)
            if flag.score > existing:
                type_scores[flag.flag_type] = flag.score

        # Weighted average of per-type max scores
        total_weighted_score = 0.0
        total_weight = 0.0
        for ft, score in type_scores.items():
            w = CorruptionScorer.WEIGHTS.get(ft, 1.0)
            total_weighted_score += score * w
            total_weight += w

        base_score = total_weighted_score / total_weight if total_weight > 0 else 0

        # Multi-indicator bonus: +8 per additional distinct type (diminishing)
        num_types = len(type_scores)
        bonus = 8 * (num_types - 1) if num_types > 1 else 0

        cri = min(100, int(base_score + bonus))

        # Determine risk level
        if cri >= 80:
            risk_level = 'critical'
        elif cri >= 60:
            risk_level = 'high'
        elif cri >= 40:
            risk_level = 'medium'
        elif cri >= 20:
            risk_level = 'low'
        else:
            risk_level = 'minimal'

        return cri, risk_level

    @staticmethod
    def get_risk_emoji(risk_level: str) -> str:
        """Get emoji representation of risk level"""
        emojis = {
            'critical': '🔴',
            'high': '🟠',
            'medium': '🟡',
            'low': '🔵',
            'minimal': '🟢'
        }
        return emojis.get(risk_level, '⚪')


class CorruptionAnalyzer:
    """
    Main corruption detection analyzer.
    Coordinates all detection modules and manages database operations.
    """

    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or DB_URL
        if not self.db_url:
            raise ValueError("Database URL is required. Set DATABASE_URL environment variable.")
        self.pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize database connection pool"""
        logger.info("Initializing database connection pool...")
        try:
            self.pool = await asyncpg.create_pool(
                self.db_url,
                min_size=1,
                max_size=3,
                command_timeout=120
            )
            logger.info("Database pool created successfully")

        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
            logger.info("Database pool closed")

    async def run_full_analysis(self) -> Dict[str, int]:
        """
        Run all corruption detection algorithms and save results to database.

        Returns:
            Dictionary with counts of each flag type detected
        """
        logger.info("=" * 60)
        logger.info("Starting full corruption detection analysis")
        logger.info("=" * 60)

        all_flags = []
        stats = {}

        # Run all detectors (order matters: bid_clustering before professional_loser)
        detectors = [
            ('single_bidder', SingleBidderDetector(self.pool)),
            ('repeat_winner', RepeatWinnerDetector(self.pool)),
            ('price_anomaly', PriceAnomalyDetector(self.pool)),
            ('bid_clustering', BidderClusteringDetector(self.pool)),
            ('short_deadline', ShortDeadlineDetector(self.pool)),
            ('procedure_type', ProcedureTypeDetector(self.pool)),
            ('identical_bids', IdenticalBidDetector(self.pool)),
            ('professional_loser', ProfessionalLoserDetector(self.pool)),
            ('contract_splitting', ContractSplittingDetector(self.pool)),
            ('short_decision', ShortDecisionDetector(self.pool)),
            ('strategic_disqualification', StrategicDisqualificationDetector(self.pool)),
            ('contract_value_growth', ContractValueGrowthDetector(self.pool)),
            ('bid_rotation', BidRotationDetector(self.pool)),
            ('threshold_manipulation', ThresholdManipulationDetector(self.pool)),
            ('late_amendment', LateAmendmentDetector(self.pool)),
        ]

        for detector_name, detector in detectors:
            try:
                flags = await detector.detect()
                all_flags.extend(flags)
                stats[detector_name] = len(flags)
                logger.info(f"✓ {detector_name}: {len(flags)} flags")
            except Exception as e:
                logger.error(f"✗ {detector_name} failed: {e}")
                stats[detector_name] = 0

        # Clear old flags
        logger.info("Clearing old corruption flags...")
        async with self.pool.acquire() as conn:
            await conn.execute("DELETE FROM corruption_flags")
            await conn.execute("DELETE FROM tender_risk_scores")

        # Save all flags to database
        logger.info(f"Saving {len(all_flags)} flags to database...")
        await self._save_flags(all_flags)

        # Calculate and save risk scores
        logger.info("Calculating tender risk scores...")
        await self._calculate_risk_scores()

        logger.info("=" * 60)
        logger.info(f"Analysis complete! Total flags: {len(all_flags)}")
        logger.info("=" * 60)

        return stats

    async def _save_flags(self, flags: List[CorruptionFlag]):
        """Save corruption flags to database in batches"""
        if not flags:
            return

        query = """
            INSERT INTO corruption_flags
            (tender_id, flag_type, severity, score, evidence, description)
            VALUES ($1, $2, $3, $4, $5, $6)
        """

        batch_size = 500
        total_saved = 0

        try:
            async with self.pool.acquire() as conn:
                for i in range(0, len(flags), batch_size):
                    batch = flags[i:i + batch_size]
                    await conn.executemany(query, [
                        (
                            flag.tender_id,
                            flag.flag_type,
                            flag.severity,
                            flag.score,
                            json.dumps(flag.evidence),
                            flag.description
                        )
                        for flag in batch
                    ])
                    total_saved += len(batch)
                    logger.info(f"Saved batch {i // batch_size + 1}: {total_saved}/{len(flags)} flags")

            logger.info(f"Saved {len(flags)} flags to database")
        except Exception as e:
            logger.error(f"Error saving flags: {e}")
            raise

    async def _calculate_risk_scores(self):
        """Calculate aggregate risk scores for all flagged tenders"""
        query = """
            SELECT
                tender_id,
                json_agg(
                    json_build_object(
                        'flag_type', flag_type,
                        'severity', severity,
                        'score', score,
                        'description', description
                    )
                ) as flags,
                COUNT(*) as flag_count
            FROM corruption_flags
            WHERE false_positive = FALSE
            GROUP BY tender_id
        """

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query)

                for row in rows:
                    # Reconstruct flags for scoring
                    # Handle JSON parsing - asyncpg may return as string or list
                    flags_data = row['flags']
                    if isinstance(flags_data, str):
                        flags_data = json.loads(flags_data)

                    flags = [
                        CorruptionFlag(
                            tender_id=row['tender_id'],
                            flag_type=f['flag_type'],
                            severity=f['severity'],
                            score=f['score'],
                            evidence={},
                            description=f.get('description', '')
                        )
                        for f in flags_data if isinstance(f, dict)
                    ]

                    risk_score, risk_level = CorruptionScorer.calculate_score(flags)

                    # Save to database
                    await conn.execute("""
                        INSERT INTO tender_risk_scores
                        (tender_id, risk_score, risk_level, flag_count, flags_summary)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (tender_id) DO UPDATE SET
                            risk_score = $2,
                            risk_level = $3,
                            flag_count = $4,
                            flags_summary = $5,
                            last_analyzed = CURRENT_TIMESTAMP
                    """, row['tender_id'], risk_score, risk_level, row['flag_count'], json.dumps(flags_data))

            logger.info(f"Calculated risk scores for {len(rows)} tenders")

        except Exception as e:
            logger.error(f"Error calculating risk scores: {e}")
            raise

    async def analyze_tender(self, tender_id: str) -> Optional[Dict]:
        """
        Get corruption analysis for a specific tender.

        Args:
            tender_id: The tender ID to analyze

        Returns:
            Dictionary with risk score, flags, and tender details
        """
        query = """
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.winner,
                t.status,
                trs.risk_score,
                trs.risk_level,
                trs.flag_count,
                trs.flags_summary as flags
            FROM tenders t
            LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
            WHERE t.tender_id = $1
        """

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query, tender_id)

                if not row:
                    logger.warning(f"Tender {tender_id} not found")
                    return None

                return {
                    'tender_id': row['tender_id'],
                    'title': row['title'],
                    'procuring_entity': row['procuring_entity'],
                    'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                    'actual_value_mkd': float(row['actual_value_mkd']) if row['actual_value_mkd'] else None,
                    'winner': row['winner'],
                    'status': row['status'],
                    'risk_score': row['risk_score'],
                    'risk_level': row['risk_level'],
                    'flag_count': row['flag_count'],
                    'flags': row['flags']
                }

        except Exception as e:
            logger.error(f"Error analyzing tender {tender_id}: {e}")
            raise

    async def get_flagged_tenders(
        self,
        min_score: int = 50,
        limit: int = 100,
        severity: Optional[str] = None
    ) -> List[Dict]:
        """
        Get tenders with high corruption risk scores.

        Args:
            min_score: Minimum risk score (0-100)
            limit: Maximum number of results
            severity: Filter by severity (critical, high, medium, low)

        Returns:
            List of flagged tenders with their risk information
        """
        severity_filter = ""
        if severity:
            severity_filter = f"AND trs.risk_level = '{severity}'"

        query = f"""
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.estimated_value_mkd,
                t.winner,
                t.publication_date,
                trs.risk_score,
                trs.risk_level,
                trs.flag_count,
                trs.flags_summary as flags
            FROM tenders t
            JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
            WHERE trs.risk_score >= $1
              {severity_filter}
            ORDER BY trs.risk_score DESC, trs.flag_count DESC
            LIMIT $2
        """

        try:
            async with self.pool.acquire() as conn:
                rows = await conn.fetch(query, min_score, limit)

                return [
                    {
                        'tender_id': row['tender_id'],
                        'title': row['title'],
                        'procuring_entity': row['procuring_entity'],
                        'estimated_value_mkd': float(row['estimated_value_mkd']) if row['estimated_value_mkd'] else None,
                        'winner': row['winner'],
                        'publication_date': str(row['publication_date']) if row['publication_date'] else None,
                        'risk_score': row['risk_score'],
                        'risk_level': row['risk_level'],
                        'risk_emoji': CorruptionScorer.get_risk_emoji(row['risk_level']),
                        'flag_count': row['flag_count'],
                        'flags': row['flags']
                    }
                    for row in rows
                ]

        except Exception as e:
            logger.error(f"Error getting flagged tenders: {e}")
            raise

    async def get_statistics(self) -> Dict:
        """Get corruption detection statistics for all 15 indicator types"""
        query = """
            SELECT
                COUNT(DISTINCT tender_id) as flagged_tenders,
                COUNT(*) as total_flags,
                COUNT(*) FILTER (WHERE severity = 'critical') as critical_flags,
                COUNT(*) FILTER (WHERE severity = 'high') as high_flags,
                COUNT(*) FILTER (WHERE severity = 'medium') as medium_flags,
                COUNT(*) FILTER (WHERE severity = 'low') as low_flags,
                COUNT(*) FILTER (WHERE flag_type = 'single_bidder') as single_bidder_count,
                COUNT(*) FILTER (WHERE flag_type = 'repeat_winner') as repeat_winner_count,
                COUNT(*) FILTER (WHERE flag_type = 'price_anomaly') as price_anomaly_count,
                COUNT(*) FILTER (WHERE flag_type = 'bid_clustering') as bid_clustering_count,
                COUNT(*) FILTER (WHERE flag_type = 'short_deadline') as short_deadline_count,
                COUNT(*) FILTER (WHERE flag_type = 'procedure_type') as procedure_type_count,
                COUNT(*) FILTER (WHERE flag_type = 'identical_bids') as identical_bids_count,
                COUNT(*) FILTER (WHERE flag_type = 'professional_loser') as professional_loser_count,
                COUNT(*) FILTER (WHERE flag_type = 'contract_splitting') as contract_splitting_count,
                COUNT(*) FILTER (WHERE flag_type = 'short_decision') as short_decision_count,
                COUNT(*) FILTER (WHERE flag_type = 'strategic_disqualification') as strategic_disqualification_count,
                COUNT(*) FILTER (WHERE flag_type = 'contract_value_growth') as contract_value_growth_count,
                COUNT(*) FILTER (WHERE flag_type = 'bid_rotation') as bid_rotation_count,
                COUNT(*) FILTER (WHERE flag_type = 'threshold_manipulation') as threshold_manipulation_count,
                COUNT(*) FILTER (WHERE flag_type = 'late_amendment') as late_amendment_count
            FROM corruption_flags
            WHERE false_positive = FALSE
        """

        try:
            async with self.pool.acquire() as conn:
                row = await conn.fetchrow(query)
                return dict(row)
        except Exception as e:
            logger.error(f"Error getting statistics: {e}")
            raise


# CLI interface for running analysis
async def main():
    """Main entry point for running corruption detection"""
    import sys

    analyzer = CorruptionAnalyzer()

    try:
        await analyzer.initialize()

        if len(sys.argv) > 1:
            command = sys.argv[1]

            if command == 'analyze':
                # Run full analysis
                stats = await analyzer.run_full_analysis()
                print("\n" + "=" * 60)
                print("CORRUPTION DETECTION RESULTS")
                print("=" * 60)
                for flag_type, count in stats.items():
                    print(f"  {flag_type}: {count} flags")

            elif command == 'tender' and len(sys.argv) > 2:
                # Analyze specific tender
                tender_id = sys.argv[2]
                result = await analyzer.analyze_tender(tender_id)
                if result:
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print(f"Tender {tender_id} not found")

            elif command == 'flagged':
                # Get flagged tenders
                min_score = int(sys.argv[2]) if len(sys.argv) > 2 else 50
                results = await analyzer.get_flagged_tenders(min_score=min_score, limit=20)
                print(f"\nFound {len(results)} high-risk tenders:\n")
                for r in results:
                    print(f"{r['risk_emoji']} {r['tender_id']} - {r['title'][:60]} (Score: {r['risk_score']})")

            elif command == 'stats':
                # Get statistics
                stats = await analyzer.get_statistics()
                print(json.dumps(stats, indent=2))

            else:
                print("Unknown command")
        else:
            print("Usage:")
            print("  python corruption_detector.py analyze          # Run full analysis")
            print("  python corruption_detector.py tender <id>      # Analyze specific tender")
            print("  python corruption_detector.py flagged [score]  # Get high-risk tenders")
            print("  python corruption_detector.py stats            # Get statistics")

    finally:
        await analyzer.close()


if __name__ == "__main__":
    asyncio.run(main())
