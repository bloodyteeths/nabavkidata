#!/usr/bin/env python3
"""
Create Labeled Dataset for ML Corruption Detection Model Validation

This script generates a balanced labeled dataset for training and validating
ML models (Random Forest, XGBoost) for corruption detection in public procurement.

The dataset combines:
1. POSITIVE LABELS:
   - Known corruption cases from ground truth (verified tender_ids)
   - High-score flagged tenders (anomaly_score >= 0.7)

2. NEGATIVE LABELS:
   - Low-risk tenders (score < 0.3) with multiple bidders (>= 3)
   - Clean awarded tenders with no corruption flags

Output: labeled_dataset.json with structure:
{
    "metadata": {...},
    "samples": [
        {
            "tender_id": "...",
            "label": 1 or 0,
            "label_source": "known_case" | "high_score_flag" | "low_risk_clean",
            "confidence": 0.0-1.0,
            "features": {...},
            "ground_truth_case_id": "MK-2023-001" (if applicable)
        }
    ]
}

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, asdict
import logging

# Add parent directories to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from ai.corruption.ground_truth.known_cases import (
    get_all_cases,
    get_all_convicted_cases,
    get_all_investigation_cases,
    SANCTIONED_ENTITIES,
    CorruptionCase
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    'DATABASE_URL',
    'postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com/nabavkidata'
)


@dataclass
class LabeledSample:
    """A single labeled sample for ML training/validation."""
    tender_id: str
    label: int  # 1 = corruption, 0 = clean
    label_source: str  # known_case, high_score_flag, low_risk_clean
    confidence: float  # 0.0-1.0, how confident in the label
    features: Dict[str, Any]
    ground_truth_case_id: Optional[str] = None
    ground_truth_case_name: Optional[str] = None
    corruption_types: Optional[List[str]] = None
    risk_score: Optional[float] = None
    flag_count: Optional[int] = None
    flag_types: Optional[List[str]] = None


class LabeledDatasetCreator:
    """Creates labeled datasets for ML model training and validation."""

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool
        self.known_tender_ids: Set[str] = set()
        self.case_to_tender_map: Dict[str, List[str]] = {}

    async def initialize(self):
        """Initialize by mapping known cases to tender IDs."""
        logger.info("Initializing dataset creator...")

        # Get known tender IDs from ground truth cases
        for case in get_all_cases():
            for tender_id in case.tender_ids:
                self.known_tender_ids.add(tender_id)
                if case.case_id not in self.case_to_tender_map:
                    self.case_to_tender_map[case.case_id] = []
                self.case_to_tender_map[case.case_id].append(tender_id)

        logger.info(f"Found {len(self.known_tender_ids)} known tender IDs from {len(get_all_cases())} cases")

    async def get_top_flagged_tenders(self, limit: int = 100) -> List[Dict]:
        """
        Get top flagged tenders by risk score.

        Uses tender_risk_scores table which aggregates corruption_flags.
        """
        async with self.pool.acquire() as conn:
            # Check if tender_risk_scores table exists and has data
            has_risk_scores = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'tender_risk_scores'
                )
            """)

            if has_risk_scores:
                count = await conn.fetchval("SELECT COUNT(*) FROM tender_risk_scores")
                if count > 0:
                    rows = await conn.fetch("""
                        SELECT
                            trs.tender_id,
                            trs.risk_score,
                            trs.risk_level,
                            trs.flag_count,
                            trs.flags_summary,
                            t.title,
                            t.procuring_entity,
                            t.winner,
                            t.estimated_value_mkd,
                            t.actual_value_mkd,
                            t.num_bidders,
                            t.status,
                            t.publication_date
                        FROM tender_risk_scores trs
                        JOIN tenders t ON trs.tender_id = t.tender_id
                        WHERE trs.risk_score > 0
                        ORDER BY trs.risk_score DESC
                        LIMIT $1
                    """, limit)

                    return [dict(row) for row in rows]

            # Fallback: Get tenders from corruption_flags directly
            logger.info("Using corruption_flags table directly...")
            rows = await conn.fetch("""
                SELECT
                    cf.tender_id,
                    AVG(cf.score) as risk_score,
                    COUNT(*) as flag_count,
                    array_agg(DISTINCT cf.flag_type) as flag_types,
                    MAX(cf.severity) as max_severity,
                    t.title,
                    t.procuring_entity,
                    t.winner,
                    t.estimated_value_mkd,
                    t.actual_value_mkd,
                    t.num_bidders,
                    t.status,
                    t.publication_date
                FROM corruption_flags cf
                JOIN tenders t ON cf.tender_id = t.tender_id
                WHERE cf.false_positive = FALSE
                GROUP BY cf.tender_id, t.title, t.procuring_entity, t.winner,
                         t.estimated_value_mkd, t.actual_value_mkd, t.num_bidders,
                         t.status, t.publication_date
                ORDER BY AVG(cf.score) DESC
                LIMIT $1
            """, limit)

            return [dict(row) for row in rows]

    async def get_low_risk_tenders(self, limit: int = 100) -> List[Dict]:
        """
        Get low-risk clean tenders for negative examples.

        Criteria:
        - Risk score < 30 (or no flags)
        - Multiple bidders (>= 3)
        - Awarded status
        - Has winner
        """
        async with self.pool.acquire() as conn:
            # Get tenders with no corruption flags and good competition
            rows = await conn.fetch("""
                SELECT
                    t.tender_id,
                    t.title,
                    t.procuring_entity,
                    t.winner,
                    t.estimated_value_mkd,
                    t.actual_value_mkd,
                    t.num_bidders,
                    t.status,
                    t.publication_date,
                    COALESCE(trs.risk_score, 0) as risk_score,
                    COALESCE(trs.flag_count, 0) as flag_count
                FROM tenders t
                LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                WHERE t.status = 'awarded'
                  AND t.winner IS NOT NULL
                  AND t.num_bidders >= 3
                  AND (trs.risk_score IS NULL OR trs.risk_score < 30)
                  AND NOT EXISTS (
                      SELECT 1 FROM corruption_flags cf
                      WHERE cf.tender_id = t.tender_id
                        AND cf.false_positive = FALSE
                        AND cf.score >= 50
                  )
                ORDER BY t.num_bidders DESC, t.publication_date DESC
                LIMIT $1
            """, limit)

            return [dict(row) for row in rows]

    async def get_tender_features(self, tender_id: str) -> Dict[str, Any]:
        """Extract features for a single tender for ML model input."""
        async with self.pool.acquire() as conn:
            # Get tender data
            tender = await conn.fetchrow("""
                SELECT
                    tender_id, title, procuring_entity, winner,
                    estimated_value_mkd, actual_value_mkd,
                    num_bidders, status, category,
                    publication_date, closing_date, opening_date,
                    cpv_code, amendment_count
                FROM tenders
                WHERE tender_id = $1
            """, tender_id)

            if not tender:
                return {}

            tender = dict(tender)

            # Get bidder data
            bidders = await conn.fetch("""
                SELECT company_name, bid_amount_mkd, is_winner, rank, disqualified
                FROM tender_bidders
                WHERE tender_id = $1
            """, tender_id)

            # Get document count
            doc_count = await conn.fetchval("""
                SELECT COUNT(*) FROM documents WHERE tender_id = $1
            """, tender_id)

            # Get corruption flags
            flags = await conn.fetch("""
                SELECT flag_type, severity, score
                FROM corruption_flags
                WHERE tender_id = $1 AND false_positive = FALSE
            """, tender_id)

            # Calculate features
            features = {
                # Basic info
                'tender_id': tender_id,
                'has_winner': 1 if tender['winner'] else 0,
                'status': tender['status'],

                # Competition
                'num_bidders': tender['num_bidders'] or 0,
                'single_bidder': 1 if (tender['num_bidders'] or 0) == 1 else 0,
                'bidder_count': len(bidders),

                # Price
                'estimated_value_mkd': float(tender['estimated_value_mkd'] or 0),
                'actual_value_mkd': float(tender['actual_value_mkd'] or 0),
                'has_price_data': 1 if tender['estimated_value_mkd'] else 0,
            }

            # Price deviation
            if tender['estimated_value_mkd'] and tender['actual_value_mkd']:
                est = float(tender['estimated_value_mkd'])
                act = float(tender['actual_value_mkd'])
                if est > 0:
                    features['price_deviation'] = (act - est) / est
                    features['price_ratio'] = act / est
                else:
                    features['price_deviation'] = 0
                    features['price_ratio'] = 0
            else:
                features['price_deviation'] = 0
                features['price_ratio'] = 0

            # Bid variance
            bid_amounts = [float(b['bid_amount_mkd']) for b in bidders if b['bid_amount_mkd']]
            if len(bid_amounts) >= 2:
                import statistics
                mean_bid = statistics.mean(bid_amounts)
                std_bid = statistics.stdev(bid_amounts)
                features['bid_mean'] = mean_bid
                features['bid_std'] = std_bid
                features['bid_cv'] = std_bid / mean_bid if mean_bid > 0 else 0
            else:
                features['bid_mean'] = bid_amounts[0] if bid_amounts else 0
                features['bid_std'] = 0
                features['bid_cv'] = 0

            # Timing
            if tender['publication_date'] and tender['closing_date']:
                deadline_days = (tender['closing_date'] - tender['publication_date']).days
                features['deadline_days'] = deadline_days
                features['short_deadline'] = 1 if deadline_days < 7 else 0
            else:
                features['deadline_days'] = 0
                features['short_deadline'] = 0

            # Documents
            features['num_documents'] = doc_count or 0

            # Amendments
            features['amendment_count'] = tender['amendment_count'] or 0
            features['has_amendments'] = 1 if (tender['amendment_count'] or 0) > 0 else 0

            # Flags
            features['flag_count'] = len(flags)
            features['max_flag_score'] = max([f['score'] for f in flags], default=0)
            features['avg_flag_score'] = sum([f['score'] for f in flags]) / len(flags) if flags else 0
            features['flag_types'] = [f['flag_type'] for f in flags]

            return features

    async def create_positive_samples_from_known_cases(self) -> List[LabeledSample]:
        """Create positive samples from known corruption cases."""
        samples = []

        for case in get_all_cases():
            for tender_id in case.tender_ids:
                # Verify tender exists in database
                async with self.pool.acquire() as conn:
                    exists = await conn.fetchval(
                        "SELECT EXISTS(SELECT 1 FROM tenders WHERE tender_id = $1)",
                        tender_id
                    )

                if not exists:
                    logger.warning(f"Known case tender {tender_id} not found in database")
                    continue

                features = await self.get_tender_features(tender_id)

                # Confidence based on case status
                if case.status == 'convicted':
                    confidence = 1.0
                elif case.status == 'prosecution':
                    confidence = 0.9
                elif case.status == 'investigation':
                    confidence = 0.8
                else:
                    confidence = 0.7

                sample = LabeledSample(
                    tender_id=tender_id,
                    label=1,
                    label_source='known_case',
                    confidence=confidence,
                    features=features,
                    ground_truth_case_id=case.case_id,
                    ground_truth_case_name=case.case_name,
                    corruption_types=case.corruption_type,
                    risk_score=features.get('avg_flag_score'),
                    flag_count=features.get('flag_count'),
                    flag_types=features.get('flag_types')
                )
                samples.append(sample)
                logger.info(f"Added known case sample: {tender_id} ({case.case_name})")

        return samples

    async def create_positive_samples_from_high_flags(
        self,
        limit: int = 100,
        min_score: float = 70.0,
        exclude_tender_ids: Set[str] = None
    ) -> List[LabeledSample]:
        """Create positive samples from high-score flagged tenders."""
        exclude_tender_ids = exclude_tender_ids or set()
        samples = []

        flagged_tenders = await self.get_top_flagged_tenders(limit=limit * 2)

        for tender in flagged_tenders:
            if len(samples) >= limit:
                break

            tender_id = tender['tender_id']
            risk_score = float(tender.get('risk_score') or 0)

            # Skip if already in known cases or low score
            if tender_id in exclude_tender_ids:
                continue
            if risk_score < min_score:
                continue

            features = await self.get_tender_features(tender_id)

            # Parse flag types from flags_summary or flag_types
            flag_types = []
            if tender.get('flag_types'):
                flag_types = tender['flag_types']
            elif tender.get('flags_summary'):
                summary = tender['flags_summary']
                if isinstance(summary, str):
                    summary = json.loads(summary)
                if isinstance(summary, list):
                    flag_types = [f.get('flag_type') for f in summary if f.get('flag_type')]

            # Confidence based on risk score
            confidence = min(0.95, risk_score / 100.0)

            sample = LabeledSample(
                tender_id=tender_id,
                label=1,
                label_source='high_score_flag',
                confidence=confidence,
                features=features,
                risk_score=risk_score,
                flag_count=tender.get('flag_count'),
                flag_types=flag_types
            )
            samples.append(sample)

        logger.info(f"Created {len(samples)} positive samples from high-score flags")
        return samples

    async def create_negative_samples(
        self,
        limit: int = 100,
        exclude_tender_ids: Set[str] = None
    ) -> List[LabeledSample]:
        """Create negative samples from low-risk clean tenders."""
        exclude_tender_ids = exclude_tender_ids or set()
        samples = []

        clean_tenders = await self.get_low_risk_tenders(limit=limit * 2)

        for tender in clean_tenders:
            if len(samples) >= limit:
                break

            tender_id = tender['tender_id']

            if tender_id in exclude_tender_ids:
                continue

            features = await self.get_tender_features(tender_id)

            # Higher confidence for more bidders (more competitive = more likely clean)
            num_bidders = tender.get('num_bidders') or 0
            confidence = min(0.95, 0.7 + (num_bidders - 3) * 0.05)

            sample = LabeledSample(
                tender_id=tender_id,
                label=0,
                label_source='low_risk_clean',
                confidence=confidence,
                features=features,
                risk_score=tender.get('risk_score', 0),
                flag_count=tender.get('flag_count', 0)
            )
            samples.append(sample)

        logger.info(f"Created {len(samples)} negative samples from clean tenders")
        return samples

    async def create_labeled_dataset(
        self,
        positive_limit: int = 100,
        balance_ratio: float = 1.0,
        min_flag_score: float = 70.0
    ) -> Dict[str, Any]:
        """
        Create a complete labeled dataset.

        Args:
            positive_limit: Maximum number of positive samples
            balance_ratio: Ratio of negative to positive samples (1.0 = balanced)
            min_flag_score: Minimum flag score for high-score positives

        Returns:
            Dict with metadata and samples
        """
        await self.initialize()

        all_samples = []
        used_tender_ids = set()

        # 1. Add known corruption cases (highest priority)
        known_samples = await self.create_positive_samples_from_known_cases()
        for sample in known_samples:
            all_samples.append(sample)
            used_tender_ids.add(sample.tender_id)

        # 2. Add high-score flagged tenders
        remaining_positive = max(0, positive_limit - len(known_samples))
        if remaining_positive > 0:
            flagged_samples = await self.create_positive_samples_from_high_flags(
                limit=remaining_positive,
                min_score=min_flag_score,
                exclude_tender_ids=used_tender_ids
            )
            for sample in flagged_samples:
                all_samples.append(sample)
                used_tender_ids.add(sample.tender_id)

        # Count positives for balance calculation
        positive_count = sum(1 for s in all_samples if s.label == 1)

        # 3. Add negative samples
        negative_limit = int(positive_count * balance_ratio)
        negative_samples = await self.create_negative_samples(
            limit=negative_limit,
            exclude_tender_ids=used_tender_ids
        )
        all_samples.extend(negative_samples)

        # Calculate statistics
        positive_samples = [s for s in all_samples if s.label == 1]
        negative_samples_final = [s for s in all_samples if s.label == 0]

        known_case_count = sum(1 for s in positive_samples if s.label_source == 'known_case')
        high_flag_count = sum(1 for s in positive_samples if s.label_source == 'high_score_flag')

        metadata = {
            'created_at': datetime.utcnow().isoformat(),
            'total_samples': len(all_samples),
            'positive_samples': len(positive_samples),
            'negative_samples': len(negative_samples_final),
            'balance_ratio': len(negative_samples_final) / len(positive_samples) if positive_samples else 0,
            'sources': {
                'known_cases': known_case_count,
                'high_score_flags': high_flag_count,
                'low_risk_clean': len(negative_samples_final)
            },
            'min_flag_score_threshold': min_flag_score,
            'known_corruption_cases_total': len(get_all_cases()),
            'known_tender_ids_total': len(self.known_tender_ids),
            'known_tender_ids_found_in_db': known_case_count,
            'confidence_stats': {
                'avg_positive_confidence': sum(s.confidence for s in positive_samples) / len(positive_samples) if positive_samples else 0,
                'avg_negative_confidence': sum(s.confidence for s in negative_samples_final) / len(negative_samples_final) if negative_samples_final else 0,
            }
        }

        # Convert samples to dict
        samples_list = []
        for sample in all_samples:
            sample_dict = asdict(sample)
            # Clean up None values
            sample_dict = {k: v for k, v in sample_dict.items() if v is not None}
            samples_list.append(sample_dict)

        return {
            'metadata': metadata,
            'samples': samples_list
        }


async def main():
    """Main function to create and save the labeled dataset."""
    print("=" * 70)
    print("CREATING LABELED DATASET FOR ML CORRUPTION DETECTION")
    print("=" * 70)
    print(f"\nStarted at: {datetime.now().isoformat()}")

    # Connect to database
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    print("\nConnected to database.")

    try:
        creator = LabeledDatasetCreator(pool)

        # Create dataset with 100+ positive samples, balanced with negatives
        dataset = await creator.create_labeled_dataset(
            positive_limit=150,  # Allow up to 150 positives
            balance_ratio=1.0,   # 1:1 positive:negative ratio
            min_flag_score=70.0  # Only high-confidence flags
        )

        # Print summary
        meta = dataset['metadata']
        print("\n" + "=" * 70)
        print("DATASET SUMMARY")
        print("=" * 70)
        print(f"\nTotal samples: {meta['total_samples']}")
        print(f"Positive samples: {meta['positive_samples']}")
        print(f"  - From known cases: {meta['sources']['known_cases']}")
        print(f"  - From high-score flags: {meta['sources']['high_score_flags']}")
        print(f"Negative samples: {meta['negative_samples']}")
        print(f"  - From low-risk clean: {meta['sources']['low_risk_clean']}")
        print(f"\nBalance ratio: {meta['balance_ratio']:.2f}")
        print(f"Avg positive confidence: {meta['confidence_stats']['avg_positive_confidence']:.2f}")
        print(f"Avg negative confidence: {meta['confidence_stats']['avg_negative_confidence']:.2f}")

        # Save to JSON
        output_path = os.path.join(os.path.dirname(__file__), 'labeled_dataset.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False, default=str)

        print(f"\nDataset saved to: {output_path}")

        # Print sample breakdown
        print("\n" + "=" * 70)
        print("SAMPLE BREAKDOWN")
        print("=" * 70)

        # Known cases
        known_samples = [s for s in dataset['samples'] if s.get('label_source') == 'known_case']
        if known_samples:
            print("\nKnown Corruption Cases:")
            for s in known_samples[:10]:
                print(f"  {s['tender_id']}: {s.get('ground_truth_case_name', 'N/A')} "
                      f"(confidence: {s['confidence']:.2f})")
            if len(known_samples) > 10:
                print(f"  ... and {len(known_samples) - 10} more")

        # High-score flags
        flag_samples = [s for s in dataset['samples'] if s.get('label_source') == 'high_score_flag']
        if flag_samples:
            print("\nHigh-Score Flagged Tenders (top 10):")
            for s in sorted(flag_samples, key=lambda x: x.get('risk_score', 0), reverse=True)[:10]:
                print(f"  {s['tender_id']}: score={s.get('risk_score', 0):.0f}, "
                      f"flags={s.get('flag_count', 0)}")

        # Clean tenders
        clean_samples = [s for s in dataset['samples'] if s.get('label_source') == 'low_risk_clean']
        if clean_samples:
            print(f"\nLow-Risk Clean Tenders: {len(clean_samples)} samples")
            print(f"  Average bidders: {sum(s.get('features', {}).get('num_bidders', 0) for s in clean_samples) / len(clean_samples):.1f}")

        print("\n" + "=" * 70)
        print("DATASET CREATED SUCCESSFULLY")
        print("=" * 70)

        return dataset

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
