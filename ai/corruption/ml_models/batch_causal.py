"""
Batch Causal Estimation Script

Runs propensity score matching for all treatment-outcome pairs,
stores results in causal_estimates table, and generates policy
recommendations in policy_recommendations table.

Designed to run as a monthly cron job:
    python3 batch_causal.py
    python3 batch_causal.py --treatments short_deadline,single_bidder
    python3 batch_causal.py --institution "Министерство за финансии"

Features:
- Estimates ATE for all 4 treatment-outcome pairs
- Bootstrap confidence intervals (500 iterations)
- Stores results in causal_estimates + policy_recommendations tables
- Ensures tables exist before inserting
- Memory-efficient: uses only sklearn + numpy (no heavy causal libraries)
- Suitable for EC2 with 3.8GB RAM

Author: nabavkidata.com
License: Proprietary
"""

import os
import sys
import json
import logging
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent))

from causal_analyzer import CausalAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://nabavki_user:9fagrPSDfQqBjrKZZLVrJY2Am@nabavkidata-db.cb6gi2cae02j.eu-central-1.rds.amazonaws.com:5432/nabavkidata"
)


async def ensure_tables(conn) -> bool:
    """
    Ensure causal_estimates and policy_recommendations tables exist.

    Returns:
        True if tables exist or were created successfully.
    """
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS causal_estimates (
                estimate_id SERIAL PRIMARY KEY,
                treatment_name TEXT NOT NULL,
                treatment_description TEXT,
                ate FLOAT NOT NULL,
                ci_lower FLOAT,
                ci_upper FLOAT,
                p_value FLOAT,
                n_treated INTEGER,
                n_control INTEGER,
                n_matched INTEGER,
                interpretation TEXT,
                recommendation TEXT,
                method TEXT DEFAULT 'propensity_score_matching',
                confounders_used TEXT[],
                computed_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(treatment_name)
            )
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS policy_recommendations (
                rec_id SERIAL PRIMARY KEY,
                institution TEXT,
                recommendation TEXT NOT NULL,
                estimated_impact FLOAT,
                confidence TEXT,
                evidence JSONB,
                treatment_name TEXT REFERENCES causal_estimates(treatment_name) ON DELETE CASCADE,
                generated_at TIMESTAMP DEFAULT NOW()
            )
        """)

        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_rec_institution
            ON policy_recommendations(institution)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_rec_treatment
            ON policy_recommendations(treatment_name)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_policy_rec_confidence
            ON policy_recommendations(confidence)
        """)

        logger.info("Causal analysis tables verified/created")
        return True

    except Exception as e:
        logger.error(f"Error creating tables: {e}")
        return False


async def store_causal_estimate(conn, effect: Dict) -> bool:
    """
    Upsert a single causal estimate into causal_estimates table.

    Args:
        conn: asyncpg connection
        effect: Result dict from CausalAnalyzer.estimate_treatment_effect()

    Returns:
        True on success.
    """
    try:
        treatment_name = effect.get('treatment', '')
        confounders = CausalAnalyzer.CONFOUNDERS

        await conn.execute("""
            INSERT INTO causal_estimates (
                treatment_name, treatment_description,
                ate, ci_lower, ci_upper, p_value,
                n_treated, n_control, n_matched,
                interpretation, recommendation,
                method, confounders_used, computed_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, NOW())
            ON CONFLICT (treatment_name) DO UPDATE SET
                treatment_description = EXCLUDED.treatment_description,
                ate = EXCLUDED.ate,
                ci_lower = EXCLUDED.ci_lower,
                ci_upper = EXCLUDED.ci_upper,
                p_value = EXCLUDED.p_value,
                n_treated = EXCLUDED.n_treated,
                n_control = EXCLUDED.n_control,
                n_matched = EXCLUDED.n_matched,
                interpretation = EXCLUDED.interpretation,
                recommendation = EXCLUDED.recommendation,
                method = EXCLUDED.method,
                confounders_used = EXCLUDED.confounders_used,
                computed_at = NOW()
        """,
            treatment_name,
            effect.get('treatment_description', ''),
            effect.get('ate', 0.0),
            effect.get('ci_lower', 0.0),
            effect.get('ci_upper', 0.0),
            effect.get('p_value', 1.0),
            effect.get('n_treated', 0),
            effect.get('n_control', 0),
            effect.get('n_matched', 0),
            effect.get('interpretation', ''),
            effect.get('recommendation', ''),
            'propensity_score_matching',
            confounders,
        )

        logger.info(f"Stored causal estimate for '{treatment_name}' (ATE={effect.get('ate', 0):.4f})")
        return True

    except Exception as e:
        logger.error(f"Error storing estimate for '{effect.get('treatment', '?')}': {e}")
        return False


async def store_policy_recommendations(conn, recommendations: List[Dict]) -> int:
    """
    Store policy recommendations in the policy_recommendations table.

    Clears old recommendations before inserting new ones to avoid stale data.

    Args:
        conn: asyncpg connection
        recommendations: List from CausalAnalyzer.generate_policy_recommendations()

    Returns:
        Number of recommendations stored.
    """
    if not recommendations:
        return 0

    # Determine institution scope (all recs have the same institution or None)
    institution = recommendations[0].get('institution')

    try:
        # Clear old recommendations for this scope
        if institution:
            await conn.execute(
                "DELETE FROM policy_recommendations WHERE institution = $1",
                institution
            )
        else:
            await conn.execute(
                "DELETE FROM policy_recommendations WHERE institution IS NULL"
            )

        stored = 0
        for rec in recommendations:
            try:
                evidence = rec.get('evidence', {})
                if isinstance(evidence, dict):
                    evidence_json = json.dumps(evidence)
                else:
                    evidence_json = json.dumps({})

                await conn.execute("""
                    INSERT INTO policy_recommendations (
                        institution, recommendation, estimated_impact,
                        confidence, evidence, treatment_name, generated_at
                    ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, NOW())
                """,
                    rec.get('institution'),
                    rec.get('recommendation', ''),
                    rec.get('estimated_impact', 0.0),
                    rec.get('confidence', 'low'),
                    evidence_json,
                    rec.get('treatment_name', ''),
                )
                stored += 1
            except Exception as e:
                logger.error(f"Error storing recommendation: {e}")

        logger.info(f"Stored {stored} policy recommendations" +
                     (f" for institution '{institution}'" if institution else " (global)"))
        return stored

    except Exception as e:
        logger.error(f"Error storing recommendations: {e}")
        return 0


async def run_batch_causal_analysis(
    treatments: Optional[List[str]] = None,
    institution: Optional[str] = None,
) -> Dict:
    """
    Run the full batch causal analysis pipeline.

    Steps:
    1. Ensure tables exist
    2. Run propensity score matching for each treatment
    3. Store causal estimates
    4. Generate and store policy recommendations

    Args:
        treatments: Optional list of treatment names to analyze.
                    If None, analyzes all 4 treatments.
        institution: Optional institution name for scoped recommendations.

    Returns:
        Summary dict with counts and results.
    """
    logger.info("=" * 60)
    logger.info("Starting batch causal analysis")
    logger.info("=" * 60)

    start_time = datetime.utcnow()
    analyzer = CausalAnalyzer()

    # Connect to database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Step 1: Ensure tables exist
        if not await ensure_tables(conn):
            logger.error("Could not create/verify tables. Aborting.")
            return {'success': False, 'error': 'Table creation failed'}

        # Step 2: Determine which treatments to analyze
        if treatments:
            treatment_names = [t for t in treatments if t in analyzer.TREATMENTS]
            if not treatment_names:
                logger.error(f"No valid treatments in: {treatments}")
                return {'success': False, 'error': f'Invalid treatments: {treatments}'}
        else:
            treatment_names = list(analyzer.TREATMENTS.keys())

        logger.info(f"Analyzing treatments: {treatment_names}")

        # Step 3: Create a pool-like wrapper for the analyzer
        # The analyzer expects a pool, so we create a minimal pool
        pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=3)

        try:
            # Step 4: Run estimation for each treatment
            effects = []
            for treatment_name in treatment_names:
                try:
                    logger.info(f"Estimating causal effect of '{treatment_name}'...")
                    effect = await analyzer.estimate_treatment_effect(pool, treatment_name)
                    effects.append(effect)

                    # Store immediately
                    await store_causal_estimate(conn, effect)

                    logger.info(
                        f"  -> ATE={effect['ate']:.4f}, "
                        f"p={effect['p_value']:.4f}, "
                        f"matched={effect['n_matched']}"
                    )
                except Exception as e:
                    logger.error(f"Failed for '{treatment_name}': {e}")

            # Step 5: Generate and store policy recommendations
            logger.info("Generating policy recommendations...")
            recommendations = await analyzer.generate_policy_recommendations(
                pool, institution=institution
            )
            n_recs = await store_policy_recommendations(conn, recommendations)

            # Step 6: Summary
            elapsed = (datetime.utcnow() - start_time).total_seconds()
            summary = {
                'success': True,
                'treatments_analyzed': len(effects),
                'significant_effects': sum(
                    1 for e in effects if e.get('p_value', 1) < 0.05
                ),
                'recommendations_generated': n_recs,
                'elapsed_seconds': round(elapsed, 1),
                'effects': effects,
            }

            logger.info("=" * 60)
            logger.info(f"Batch causal analysis complete in {elapsed:.1f}s")
            logger.info(f"  Treatments analyzed: {summary['treatments_analyzed']}")
            logger.info(f"  Significant effects: {summary['significant_effects']}")
            logger.info(f"  Recommendations: {summary['recommendations_generated']}")
            logger.info("=" * 60)

            return summary

        finally:
            await pool.close()

    finally:
        await conn.close()


async def main():
    """Main entry point for CLI execution."""
    parser = argparse.ArgumentParser(
        description='Batch causal analysis for procurement corruption detection'
    )
    parser.add_argument(
        '--treatments',
        type=str,
        default=None,
        help='Comma-separated list of treatments to analyze (default: all). '
             'Available: short_deadline, single_bidder, high_value, weekend_publication'
    )
    parser.add_argument(
        '--institution',
        type=str,
        default=None,
        help='Institution name for scoped recommendations (default: global)'
    )

    args = parser.parse_args()

    treatments = None
    if args.treatments:
        treatments = [t.strip() for t in args.treatments.split(',')]

    result = await run_batch_causal_analysis(
        treatments=treatments,
        institution=args.institution,
    )

    if result.get('success'):
        # Print summary of effects
        for effect in result.get('effects', []):
            sig = "*" if effect.get('p_value', 1) < 0.05 else " "
            print(
                f"  {sig} {effect.get('treatment', '?'):25s} "
                f"ATE={effect.get('ate', 0):+.4f}  "
                f"p={effect.get('p_value', 1):.4f}  "
                f"n_matched={effect.get('n_matched', 0):5d}"
            )
    else:
        print(f"FAILED: {result.get('error', 'Unknown error')}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
