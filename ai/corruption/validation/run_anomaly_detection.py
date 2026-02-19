#!/usr/bin/env python3
"""
Run Hybrid Anomaly Detection on Real Tender Data

This script:
1. Connects to the database
2. Extracts features for awarded tenders
3. Trains the HybridAnomalyDetector
4. Identifies top 50 most suspicious tenders
5. Saves results to CSV and generates a markdown report

Usage:
    python run_anomaly_detection.py
"""

import asyncio
import asyncpg
import numpy as np
import pandas as pd
import sys
import os
from pathlib import Path
from datetime import datetime
import logging
from dotenv import load_dotenv
load_dotenv()


# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ai.corruption.features.feature_extractor import FeatureExtractor
from ai.corruption.ml_models.hybrid_anomaly import HybridAnomalyDetector

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database configuration
DB_CONFIG = {
    'host': 'nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com',
    'user': 'nabavki_user',
    'password': os.getenv('DB_PASSWORD', ''),
    'database': 'nabavkidata',
    'port': 5432
}

OUTPUT_DIR = Path(__file__).parent


async def get_awarded_tenders(pool: asyncpg.Pool, limit: int = 1000) -> list:
    """Get list of awarded tender IDs with sufficient data."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.tender_id, t.title, t.procuring_entity, t.winner,
                   t.estimated_value_mkd, t.actual_value_mkd, t.num_bidders,
                   t.publication_date
            FROM tenders t
            WHERE t.status IN ('awarded', 'closed')
              AND t.winner IS NOT NULL
              AND t.procuring_entity IS NOT NULL
              AND (t.estimated_value_mkd > 0 OR t.actual_value_mkd > 0)
            ORDER BY t.publication_date DESC NULLS LAST
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]


async def get_tender_details(pool: asyncpg.Pool, tender_ids: list) -> dict:
    """Get detailed information for specific tenders."""
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                t.tender_id,
                t.title,
                t.procuring_entity,
                t.winner,
                t.estimated_value_mkd,
                t.actual_value_mkd,
                t.num_bidders,
                t.publication_date,
                t.status,
                t.cpv_code,
                t.category,
                COALESCE(cf.flags::text, '{}') as corruption_flags
            FROM tenders t
            LEFT JOIN (
                SELECT tender_id, jsonb_agg(flag_type) as flags
                FROM corruption_flags
                GROUP BY tender_id
            ) cf ON t.tender_id = cf.tender_id
            WHERE t.tender_id = ANY($1::text[])
        """, tender_ids)
        return {row['tender_id']: dict(row) for row in rows}


async def main():
    """Main function to run anomaly detection."""
    logger.info("=" * 60)
    logger.info("Starting Hybrid Anomaly Detection on Real Tender Data")
    logger.info("=" * 60)

    # Connect to database
    logger.info("Connecting to database...")
    pool = await asyncpg.create_pool(
        **DB_CONFIG,
        min_size=2,
        max_size=10
    )

    try:
        # Step 1: Get awarded tenders
        logger.info("Fetching awarded tenders...")
        tenders = await get_awarded_tenders(pool, limit=1000)
        logger.info(f"Found {len(tenders)} awarded tenders with sufficient data")

        if len(tenders) < 100:
            logger.error("Not enough tenders for analysis. Need at least 100.")
            return

        tender_ids = [t['tender_id'] for t in tenders]

        # Step 2: Extract features
        logger.info("Extracting features (this may take a few minutes)...")
        extractor = FeatureExtractor(pool)

        feature_vectors = []
        batch_size = 50
        for i in range(0, len(tender_ids), batch_size):
            batch = tender_ids[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(len(tender_ids)-1)//batch_size + 1}")
            batch_results = await extractor.extract_features_batch(batch, include_metadata=True)
            feature_vectors.extend(batch_results)

        logger.info(f"Successfully extracted features for {len(feature_vectors)} tenders")

        if len(feature_vectors) < 100:
            logger.error("Not enough valid feature vectors. Need at least 100.")
            return

        # Build feature matrix
        X = np.array([fv.feature_array for fv in feature_vectors])
        ids = [fv.tender_id for fv in feature_vectors]
        feature_names = feature_vectors[0].feature_names

        logger.info(f"Feature matrix shape: {X.shape}")

        # Step 3: Train the HybridAnomalyDetector
        logger.info("Training HybridAnomalyDetector with contamination=0.05...")
        detector = HybridAnomalyDetector(
            contamination=0.05,
            threshold=0.5,
            random_state=42
        )

        detector.fit(X, feature_names=feature_names, verbose=True)

        # Step 4: Score all tenders
        logger.info("Scoring all tenders...")
        anomaly_scores = detector.score_tenders(X, ids)

        # Sort by anomaly score (highest first)
        anomaly_scores.sort(key=lambda x: -x.anomaly_score)

        # Step 5: Get top 50 anomalies
        top_50 = anomaly_scores[:50]
        top_50_ids = [s.tender_id for s in top_50]

        logger.info(f"Identified top 50 most suspicious tenders")

        # Step 6: Get detailed information for top 50
        logger.info("Fetching detailed information for top anomalies...")
        tender_details = await get_tender_details(pool, top_50_ids)

        # Step 7: Build results dataframe
        results = []
        for score in top_50:
            details = tender_details.get(score.tender_id, {})

            # Get top 5 contributing features
            top_features = sorted(
                score.feature_contributions.items(),
                key=lambda x: -x[1]
            )[:5]

            results.append({
                'rank': len(results) + 1,
                'tender_id': score.tender_id,
                'anomaly_score': round(score.anomaly_score, 4),
                'confidence': round(score.confidence, 4),
                'title': (details.get('title') or '')[:100],
                'institution': details.get('procuring_entity', ''),
                'winner': details.get('winner', ''),
                'estimated_value_mkd': details.get('estimated_value_mkd', 0),
                'actual_value_mkd': details.get('actual_value_mkd', 0),
                'num_bidders': details.get('num_bidders', 0),
                'publication_date': str(details.get('publication_date', '')),
                'corruption_flags': details.get('corruption_flags', '{}'),
                'isolation_forest_score': round(score.method_scores.get('isolation_forest', 0), 4),
                'autoencoder_score': round(score.method_scores.get('autoencoder', 0), 4),
                'lof_score': round(score.method_scores.get('lof', 0), 4),
                'ocsvm_score': round(score.method_scores.get('ocsvm', 0), 4),
                'top_contributing_features': ', '.join([f"{f}={v:.3f}" for f, v in top_features])
            })

        df = pd.DataFrame(results)

        # Step 8: Save to CSV
        csv_path = OUTPUT_DIR / 'top_anomalies.csv'
        df.to_csv(csv_path, index=False)
        logger.info(f"Saved results to {csv_path}")

        # Step 9: Generate markdown report
        await generate_report(anomaly_scores, tender_details, feature_vectors, detector)

        # Print summary
        logger.info("\n" + "=" * 60)
        logger.info("SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total tenders analyzed: {len(feature_vectors)}")
        logger.info(f"Anomalies detected (>0.5 threshold): {sum(1 for s in anomaly_scores if s.is_anomaly)}")
        logger.info(f"Top anomaly score: {anomaly_scores[0].anomaly_score:.4f}")
        logger.info(f"Average anomaly score: {np.mean([s.anomaly_score for s in anomaly_scores]):.4f}")
        logger.info(f"\nTop 10 Most Suspicious Tenders:")

        for i, score in enumerate(top_50[:10]):
            details = tender_details.get(score.tender_id, {})
            logger.info(f"  {i+1}. {score.tender_id} (score: {score.anomaly_score:.4f}) - {details.get('winner', 'N/A')}")

        logger.info(f"\nResults saved to:")
        logger.info(f"  - {OUTPUT_DIR / 'top_anomalies.csv'}")
        logger.info(f"  - {OUTPUT_DIR / 'anomaly_report.md'}")

    finally:
        await pool.close()


async def generate_report(anomaly_scores, tender_details, feature_vectors, detector):
    """Generate markdown report."""

    report_path = OUTPUT_DIR / 'anomaly_report.md'

    # Calculate statistics
    scores = np.array([s.anomaly_score for s in anomaly_scores])
    num_anomalies = sum(1 for s in anomaly_scores if s.is_anomaly)

    # Get feature importances
    feature_importances = detector.get_isolation_forest_importances()
    top_features = sorted(feature_importances.items(), key=lambda x: -x[1])[:15]

    # Analyze patterns in flagged tenders
    flagged_tenders = [s for s in anomaly_scores if s.is_anomaly]

    # Common patterns
    single_bidder_count = 0
    high_win_rate_count = 0
    price_deviation_count = 0

    for fv in feature_vectors:
        if fv.tender_id in [s.tender_id for s in flagged_tenders]:
            if fv.features.get('single_bidder', 0) > 0.5:
                single_bidder_count += 1
            if fv.features.get('winner_very_high_win_rate', 0) > 0.5:
                high_win_rate_count += 1
            if fv.features.get('price_deviation_large', 0) > 0.5:
                price_deviation_count += 1

    with open(report_path, 'w') as f:
        f.write("# Hybrid Anomaly Detection Report\n\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

        f.write("## Summary Statistics\n\n")
        f.write("| Metric | Value |\n")
        f.write("|--------|-------|\n")
        f.write(f"| Total Tenders Analyzed | {len(anomaly_scores)} |\n")
        f.write(f"| Anomalies Detected (>0.5) | {num_anomalies} ({100*num_anomalies/len(anomaly_scores):.1f}%) |\n")
        f.write(f"| Mean Anomaly Score | {np.mean(scores):.4f} |\n")
        f.write(f"| Median Anomaly Score | {np.median(scores):.4f} |\n")
        f.write(f"| Std Dev | {np.std(scores):.4f} |\n")
        f.write(f"| Min Score | {np.min(scores):.4f} |\n")
        f.write(f"| Max Score | {np.max(scores):.4f} |\n")
        f.write(f"| 95th Percentile | {np.percentile(scores, 95):.4f} |\n\n")

        f.write("## Detection Methods Performance\n\n")
        f.write("The hybrid detector combines four unsupervised methods:\n\n")
        f.write("1. **Isolation Forest** (25% weight): Tree-based outlier detection\n")
        f.write("2. **Autoencoder** (30% weight): Neural network reconstruction error\n")
        f.write("3. **Local Outlier Factor** (20% weight): Density-based local anomalies\n")
        f.write("4. **One-Class SVM** (25% weight): Boundary-based detection\n\n")

        f.write("### Method Agreement\n\n")
        high_agreement = sum(1 for s in anomaly_scores if s.confidence > 0.7)
        f.write(f"- High confidence predictions (>0.7): {high_agreement} ({100*high_agreement/len(anomaly_scores):.1f}%)\n")

        f.write("\n## Top 15 Most Important Features\n\n")
        f.write("Features most influential in detecting anomalies:\n\n")
        f.write("| Rank | Feature | Importance |\n")
        f.write("|------|---------|------------|\n")
        for i, (feat, imp) in enumerate(top_features):
            f.write(f"| {i+1} | {feat} | {imp:.4f} |\n")

        f.write("\n## Common Patterns in Flagged Tenders\n\n")
        if num_anomalies > 0:
            f.write(f"Among the {num_anomalies} flagged anomalies:\n\n")
            f.write(f"- **Single bidder tenders:** {single_bidder_count} ({100*single_bidder_count/num_anomalies:.1f}%)\n")
            f.write(f"- **High winner win rate:** {high_win_rate_count} ({100*high_win_rate_count/num_anomalies:.1f}%)\n")
            f.write(f"- **Large price deviation:** {price_deviation_count} ({100*price_deviation_count/num_anomalies:.1f}%)\n")

        f.write("\n## Top 20 Most Suspicious Tenders\n\n")

        for i, score in enumerate(anomaly_scores[:20]):
            details = tender_details.get(score.tender_id, {})

            f.write(f"### {i+1}. {score.tender_id}\n\n")
            f.write(f"**Anomaly Score:** {score.anomaly_score:.4f} | **Confidence:** {score.confidence:.4f}\n\n")

            f.write("| Field | Value |\n")
            f.write("|-------|-------|\n")
            f.write(f"| Title | {(details.get('title') or 'N/A')[:80]}... |\n")
            f.write(f"| Institution | {details.get('procuring_entity', 'N/A')} |\n")
            f.write(f"| Winner | {details.get('winner', 'N/A')} |\n")

            est_val = details.get('estimated_value_mkd', 0)
            act_val = details.get('actual_value_mkd', 0)
            f.write(f"| Estimated Value (MKD) | {est_val:,.0f} |\n")
            f.write(f"| Actual Value (MKD) | {act_val:,.0f} |\n")

            if est_val and act_val:
                deviation = (act_val - est_val) / est_val * 100
                f.write(f"| Price Deviation | {deviation:+.1f}% |\n")

            f.write(f"| Number of Bidders | {details.get('num_bidders', 'N/A')} |\n")
            f.write(f"| Publication Date | {details.get('publication_date', 'N/A')} |\n")
            f.write(f"| Existing Flags | {details.get('corruption_flags', '{}')} |\n\n")

            f.write("**Method Scores:**\n")
            f.write(f"- Isolation Forest: {score.method_scores.get('isolation_forest', 0):.4f}\n")
            f.write(f"- Autoencoder: {score.method_scores.get('autoencoder', 0):.4f}\n")
            f.write(f"- LOF: {score.method_scores.get('lof', 0):.4f}\n")
            f.write(f"- One-Class SVM: {score.method_scores.get('ocsvm', 0):.4f}\n\n")

            top_contribs = sorted(score.feature_contributions.items(), key=lambda x: -x[1])[:5]
            f.write("**Top Contributing Features:**\n")
            for feat, val in top_contribs:
                f.write(f"- {feat}: {val:.4f}\n")
            f.write("\n---\n\n")

        f.write("## Recommendations\n\n")
        f.write("Based on the analysis, the following tenders warrant further investigation:\n\n")
        f.write("1. **High Priority** (Score > 0.8): Immediate review recommended\n")
        high_priority = sum(1 for s in anomaly_scores if s.anomaly_score > 0.8)
        f.write(f"   - Count: {high_priority} tenders\n\n")

        f.write("2. **Medium Priority** (Score 0.6-0.8): Review when possible\n")
        medium_priority = sum(1 for s in anomaly_scores if 0.6 <= s.anomaly_score <= 0.8)
        f.write(f"   - Count: {medium_priority} tenders\n\n")

        f.write("3. **Low Priority** (Score 0.5-0.6): Monitor for patterns\n")
        low_priority = sum(1 for s in anomaly_scores if 0.5 <= s.anomaly_score < 0.6)
        f.write(f"   - Count: {low_priority} tenders\n\n")

        f.write("## Methodology Notes\n\n")
        f.write("- The detector was trained in **unsupervised mode** assuming 5% contamination\n")
        f.write("- No ground truth labels were used; all patterns are learned from data distribution\n")
        f.write("- Higher anomaly scores indicate statistical deviation from typical tender patterns\n")
        f.write("- A high score does not prove corruption - only that the tender is unusual\n")
        f.write("- Human review is essential for final determination\n")

    logger.info(f"Report saved to {report_path}")


if __name__ == '__main__':
    asyncio.run(main())
