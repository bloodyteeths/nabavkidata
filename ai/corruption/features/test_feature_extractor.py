"""
Test and demonstration script for FeatureExtractor

This script demonstrates:
1. Feature extraction for a single tender
2. Batch extraction
3. Feature analysis and interpretation
4. Integration with ML models

Usage:
    python test_feature_extractor.py <tender_id>
    python test_feature_extractor.py --batch 10
    python test_feature_extractor.py --stats
"""

import asyncio
import asyncpg
import sys
import os
import numpy as np
from typing import List
import logging

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from ai.corruption.features.feature_extractor import FeatureExtractor, FeatureVector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_URL = os.getenv(
    'DATABASE_URL',
    os.getenv('DATABASE_URL')
)


async def test_single_tender(tender_id: str):
    """Test feature extraction for a single tender"""
    print(f"\n{'='*80}")
    print(f"TESTING FEATURE EXTRACTION: {tender_id}")
    print(f"{'='*80}\n")

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2)

    try:
        extractor = FeatureExtractor(pool)

        # Extract features
        print("Extracting features...")
        features = await extractor.extract_features(tender_id, include_metadata=True)

        # Print metadata
        print(f"\n{'-'*80}")
        print("METADATA:")
        print(f"{'-'*80}")
        for key, value in features.metadata.items():
            print(f"  {key}: {value}")

        # Print feature summary
        print(f"\n{'-'*80}")
        print(f"FEATURES EXTRACTED: {len(features.features)}")
        print(f"{'-'*80}")

        # Print features by category
        categories = extractor.get_feature_categories()
        for category_name, feature_names in categories.items():
            print(f"\n{category_name.upper()} Features:")
            for fname in feature_names:
                value = features.get_feature(fname)
                if value and value != 0.0:  # Only show non-zero features
                    print(f"  {fname}: {value:.4f}")

        # Print feature array info
        print(f"\n{'-'*80}")
        print("FEATURE ARRAY (for ML models):")
        print(f"{'-'*80}")
        print(f"  Shape: {features.feature_array.shape}")
        print(f"  Dtype: {features.feature_array.dtype}")
        print(f"  Non-zero features: {np.count_nonzero(features.feature_array)}")
        print(f"  Mean: {np.mean(features.feature_array):.4f}")
        print(f"  Std: {np.std(features.feature_array):.4f}")
        print(f"  Min: {np.min(features.feature_array):.4f}")
        print(f"  Max: {np.max(features.feature_array):.4f}")

        # Highlight high-risk indicators
        print(f"\n{'-'*80}")
        print("HIGH-RISK INDICATORS:")
        print(f"{'-'*80}")

        risk_indicators = [
            ('single_bidder', 'Single bidder tender'),
            ('winner_very_high_win_rate', 'Winner has very high win rate (>80%)'),
            ('bid_very_low_variance', 'All bids suspiciously close (possible collusion)'),
            ('winner_extremely_low', 'Winner bid extremely low (>2 std dev)'),
            ('deadline_very_short', 'Very short deadline (<3 days)'),
            ('has_related_bidders', 'Bidders have known relationships'),
            ('winner_dominant_supplier', 'Winner is dominant supplier (>50% market share)'),
            ('price_exact_match_estimate', 'Price exactly matches estimate')
        ]

        found_risks = False
        for feature_name, description in risk_indicators:
            value = features.get_feature(feature_name)
            if value and value > 0.5:  # Feature is flagged
                print(f"  [!] {description}")
                found_risks = True

        if not found_risks:
            print("  No major risk indicators detected")

        print(f"\n{'='*80}\n")

    finally:
        await pool.close()


async def test_batch_extraction(limit: int = 10):
    """Test batch feature extraction"""
    print(f"\n{'='*80}")
    print(f"BATCH FEATURE EXTRACTION (limit: {limit})")
    print(f"{'='*80}\n")

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=3)

    try:
        # Get some tender IDs
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT tender_id
                FROM tenders
                WHERE status = 'awarded'
                  AND num_bidders > 0
                  AND estimated_value_mkd > 1000000
                ORDER BY publication_date DESC
                LIMIT $1
            """, limit)
            tender_ids = [row['tender_id'] for row in rows]

        print(f"Extracting features for {len(tender_ids)} tenders...")

        extractor = FeatureExtractor(pool)
        feature_vectors = await extractor.extract_features_batch(tender_ids, include_metadata=True)

        print(f"Successfully extracted: {len(feature_vectors)}/{len(tender_ids)}")

        # Create feature matrix
        X = np.array([fv.feature_array for fv in feature_vectors])
        print(f"\nFeature matrix shape: {X.shape}")
        print(f"  (rows=tenders, cols=features)")

        # Analyze feature distributions
        print(f"\n{'-'*80}")
        print("FEATURE STATISTICS:")
        print(f"{'-'*80}")

        # Most variable features (useful for ML)
        feature_stds = np.std(X, axis=0)
        top_variable_idx = np.argsort(feature_stds)[-10:][::-1]

        print("\nMost variable features (top 10):")
        for idx in top_variable_idx:
            fname = extractor.feature_names[idx]
            print(f"  {fname}: std={feature_stds[idx]:.4f}")

        # Count single bidder tenders
        single_bidder_idx = extractor.feature_names.index('single_bidder')
        single_bidder_count = int(np.sum(X[:, single_bidder_idx]))
        print(f"\nSingle bidder tenders: {single_bidder_count}/{len(feature_vectors)} ({single_bidder_count/len(feature_vectors)*100:.1f}%)")

        # Count high win rate winners
        high_win_rate_idx = extractor.feature_names.index('winner_very_high_win_rate')
        high_win_rate_count = int(np.sum(X[:, high_win_rate_idx]))
        print(f"Very high win rate winners: {high_win_rate_count}/{len(feature_vectors)} ({high_win_rate_count/len(feature_vectors)*100:.1f}%)")

        # Show a few examples
        print(f"\n{'-'*80}")
        print("SAMPLE TENDERS:")
        print(f"{'-'*80}")

        for i, fv in enumerate(feature_vectors[:5], 1):
            print(f"\n{i}. {fv.tender_id}")
            print(f"   {fv.metadata.get('title', 'N/A')[:70]}...")
            print(f"   Institution: {fv.metadata.get('procuring_entity', 'N/A')}")
            print(f"   Winner: {fv.metadata.get('winner', 'N/A')}")
            print(f"   Value: {fv.metadata.get('estimated_value_mkd', 0):,.0f} MKD")
            print(f"   Bidders: {fv.get_feature('num_bidders'):.0f}")
            print(f"   Single bidder: {'Yes' if fv.get_feature('single_bidder') else 'No'}")

        print(f"\n{'='*80}\n")

    finally:
        await pool.close()


async def show_feature_stats():
    """Show feature extractor statistics and info"""
    print(f"\n{'='*80}")
    print("FEATURE EXTRACTOR INFO")
    print(f"{'='*80}\n")

    pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=1)

    try:
        extractor = FeatureExtractor(pool)

        print(f"Total features: {extractor.get_feature_count()}")
        print(f"\nFeatures by category:")

        categories = extractor.get_feature_categories()
        for category_name, feature_names in categories.items():
            print(f"  {category_name.capitalize()}: {len(feature_names)} features")

        print(f"\n{'-'*80}")
        print("ALL FEATURES:")
        print(f"{'-'*80}")

        for i, fname in enumerate(extractor.feature_names, 1):
            print(f"  {i:3d}. {fname}")

        print(f"\n{'-'*80}")
        print("FEATURE CATEGORIES:")
        print(f"{'-'*80}")

        for category_name, feature_names in categories.items():
            print(f"\n{category_name.upper()}:")
            for fname in feature_names:
                print(f"  - {fname}")

        print(f"\n{'='*80}\n")

    finally:
        await pool.close()


async def main():
    """Main entry point"""
    if len(sys.argv) < 2:
        print("""
Feature Extractor Test Script
=============================

Usage:
  python test_feature_extractor.py <tender_id>     # Test single tender
  python test_feature_extractor.py --batch [N]     # Test batch extraction (default: 10)
  python test_feature_extractor.py --stats         # Show feature info

Examples:
  python test_feature_extractor.py "123456/2024"
  python test_feature_extractor.py --batch 20
  python test_feature_extractor.py --stats
        """)
        return

    command = sys.argv[1]

    if command == '--batch':
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        await test_batch_extraction(limit)
    elif command == '--stats':
        await show_feature_stats()
    else:
        # Treat as tender ID
        tender_id = command
        await test_single_tender(tender_id)


if __name__ == "__main__":
    asyncio.run(main())
