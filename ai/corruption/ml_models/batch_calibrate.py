"""
Batch Calibration Script for Conformal Prediction

Fits a conformal predictor on existing ML predictions + proxy labels,
calibrates all existing predictions, stores results, and checks
calibration quality.

Designed for monthly cron execution (after model retraining).

Usage:
    # Full calibration run
    python batch_calibrate.py

    # Calibration check only (no re-fit)
    python batch_calibrate.py --check-only

    # Custom alpha
    python batch_calibrate.py --alpha 0.05

    # Limit calibration set size (for memory)
    python batch_calibrate.py --max-cal-samples 5000

Author: nabavkidata.com
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import numpy as np
from dotenv import load_dotenv
load_dotenv()


# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_models.conformal import (
    ConformalPredictor,
    CalibrationMonitor,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)


async def fetch_calibration_data(
    pool: asyncpg.Pool,
    model_version: str = 'xgboost_rf_v1',
    max_samples: int = 10000,
) -> tuple:
    """
    Fetch existing ML predictions and proxy labels for calibration.

    Proxy labels are derived from corruption_flags:
    - Positive (1): tender has reliable flags with score >= 30
    - Negative (0): tender has no reliable flags

    This uses the same label strategy as train_real_data.py, excluding
    the unreliable single_bidder flag.

    Returns:
        (tender_ids, y_pred_proba, y_true) arrays
    """
    async with pool.acquire() as conn:
        rows = await conn.fetch("""
            SELECT
                mp.tender_id,
                mp.confidence as y_pred,
                CASE
                    WHEN EXISTS (
                        SELECT 1 FROM corruption_flags cf
                        WHERE cf.tender_id = mp.tender_id
                          AND cf.flag_type IN (
                              'short_deadline', 'price_anomaly',
                              'bid_clustering', 'repeat_winner'
                          )
                          AND cf.score >= 30
                    ) THEN 1
                    ELSE 0
                END as proxy_label
            FROM ml_predictions mp
            WHERE mp.model_version = $1
              AND mp.confidence IS NOT NULL
            ORDER BY RANDOM()
            LIMIT $2
        """, model_version, max_samples)

    if not rows:
        raise ValueError(f"No predictions found for model_version={model_version}")

    tender_ids = [r['tender_id'] for r in rows]
    y_pred = np.array([float(r['y_pred']) for r in rows])
    y_true = np.array([int(r['proxy_label']) for r in rows])

    logger.info(
        f"Fetched {len(rows)} predictions for calibration. "
        f"Positive rate: {y_true.mean():.3f} ({y_true.sum()} positives)"
    )

    return tender_ids, y_pred, y_true


async def fit_and_store_conformal(
    pool: asyncpg.Pool,
    y_pred: np.ndarray,
    y_true: np.ndarray,
    alpha: float = 0.10,
    model_name: str = 'xgboost_rf_v1',
) -> ConformalPredictor:
    """
    Fit conformal predictor and store parameters in database.

    Splits calibration data 50/50: half for fitting, half for validation.
    """
    from sklearn.model_selection import train_test_split

    # Split: 50% for conformal fitting, 50% for validation
    y_pred_fit, y_pred_val, y_true_fit, y_true_val = train_test_split(
        y_pred, y_true, test_size=0.5, random_state=42, stratify=y_true,
    )

    logger.info(
        f"Calibration split: {len(y_pred_fit)} fit, {len(y_pred_val)} validation"
    )

    # Fit conformal predictor
    cp = ConformalPredictor(alpha=alpha)
    cp.fit(y_pred_fit, y_true_fit)

    # Validate on held-out calibration data
    monitor = CalibrationMonitor()

    # Check raw (uncalibrated) metrics
    raw_metrics = monitor.compute_calibration_metrics(y_pred_val, y_true_val)
    logger.info(
        f"RAW model calibration (validation set): "
        f"ECE={raw_metrics['ece']:.4f}, MCE={raw_metrics['mce']:.4f}"
    )

    # Check calibrated metrics
    calibrated_preds = np.array([cp.calibrate_score(p) for p in y_pred_val])
    cal_metrics = monitor.compute_calibration_metrics(calibrated_preds, y_true_val)
    logger.info(
        f"CALIBRATED model (Platt scaling): "
        f"ECE={cal_metrics['ece']:.4f}, MCE={cal_metrics['mce']:.4f}"
    )

    # Check coverage on validation set
    coverage = monitor.compute_coverage(y_pred_val, y_true_val, cp.quantile)
    logger.info(
        f"Empirical coverage: {coverage['coverage_actual']:.4f} "
        f"(target: {1 - alpha:.2f})"
    )

    # Store parameters in database
    params = cp.get_parameters()
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO conformal_calibration (
                model_name, alpha, quantile_threshold,
                platt_a, platt_b, calibration_set_size,
                ece, mce, is_well_calibrated, fitted_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            ON CONFLICT (model_name, alpha)
            DO UPDATE SET
                quantile_threshold = EXCLUDED.quantile_threshold,
                platt_a = EXCLUDED.platt_a,
                platt_b = EXCLUDED.platt_b,
                calibration_set_size = EXCLUDED.calibration_set_size,
                ece = EXCLUDED.ece,
                mce = EXCLUDED.mce,
                is_well_calibrated = EXCLUDED.is_well_calibrated,
                fitted_at = NOW()
        """,
            model_name,
            params['alpha'],
            params['quantile_threshold'],
            params['platt_a'],
            params['platt_b'],
            params['calibration_set_size'],
            cal_metrics['ece'],
            cal_metrics['mce'],
            cal_metrics['is_well_calibrated'],
        )

    logger.info(f"Stored conformal parameters for model={model_name}, alpha={alpha}")

    # Store calibration check
    await monitor.store_calibration_check(pool, {
        'model_name': model_name,
        'ece': cal_metrics['ece'],
        'mce': cal_metrics['mce'],
        'coverage_actual': coverage['coverage_actual'],
        'coverage_target': 1 - alpha,
        'n_samples': len(y_pred_val),
        'drift_detected': not cal_metrics['is_well_calibrated'],
    })

    return cp


async def calibrate_all_predictions(
    pool: asyncpg.Pool,
    cp: ConformalPredictor,
    model_version: str = 'xgboost_rf_v1',
    batch_size: int = 500,
) -> int:
    """
    Calibrate all existing ML predictions and store in calibrated_predictions.

    Processes in batches to keep memory usage low on the 3.8GB EC2.

    Returns:
        Number of predictions calibrated.
    """
    total_calibrated = 0

    async with pool.acquire() as conn:
        # Count total predictions to calibrate
        total = await conn.fetchval("""
            SELECT COUNT(*) FROM ml_predictions
            WHERE model_version = $1 AND confidence IS NOT NULL
        """, model_version)

        logger.info(f"Calibrating {total:,} predictions in batches of {batch_size}")

        offset = 0
        while offset < total:
            rows = await conn.fetch("""
                SELECT tender_id, confidence
                FROM ml_predictions
                WHERE model_version = $1 AND confidence IS NOT NULL
                ORDER BY tender_id
                OFFSET $2 LIMIT $3
            """, model_version, offset, batch_size)

            if not rows:
                break

            # Calibrate batch
            records = []
            for row in rows:
                raw_score = float(row['confidence'])
                result = cp.predict_set(raw_score)

                records.append((
                    row['tender_id'],
                    raw_score,
                    result['calibrated_probability'],
                    result['prediction_set'][0],
                    result['prediction_set'][1],
                    result['set_width'],
                    model_version,
                ))

            # Upsert batch
            await conn.executemany("""
                INSERT INTO calibrated_predictions (
                    tender_id, raw_score, calibrated_probability,
                    prediction_lower, prediction_upper, set_width,
                    model_name, calibrated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                ON CONFLICT (tender_id)
                DO UPDATE SET
                    raw_score = EXCLUDED.raw_score,
                    calibrated_probability = EXCLUDED.calibrated_probability,
                    prediction_lower = EXCLUDED.prediction_lower,
                    prediction_upper = EXCLUDED.prediction_upper,
                    set_width = EXCLUDED.set_width,
                    model_name = EXCLUDED.model_name,
                    calibrated_at = NOW()
            """, records)

            total_calibrated += len(records)
            offset += batch_size

            if total_calibrated % 2000 == 0:
                logger.info(
                    f"Calibrated {total_calibrated:,}/{total:,} predictions "
                    f"({100 * total_calibrated / total:.1f}%)"
                )

    logger.info(f"Calibration complete: {total_calibrated:,} predictions calibrated")
    return total_calibrated


async def run_calibration_check(
    pool: asyncpg.Pool,
    model_name: str = 'xgboost_rf_v1',
    window_days: int = 30,
) -> dict:
    """
    Run a calibration check and store results.

    Returns calibration drift analysis.
    """
    monitor = CalibrationMonitor()
    drift_result = await monitor.check_calibration_drift(
        pool, window_days=window_days,
    )
    drift_result['model_name'] = model_name

    # Store check
    await monitor.store_calibration_check(pool, drift_result)

    return drift_result


async def main():
    """Main calibration pipeline."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Batch calibrate corruption risk scores with conformal prediction'
    )
    parser.add_argument(
        '--alpha', type=float, default=0.10,
        help='Miscoverage rate (0.10 = 90%% coverage). Default: 0.10'
    )
    parser.add_argument(
        '--model-version', type=str, default='xgboost_rf_v1',
        help='Model version to calibrate. Default: xgboost_rf_v1'
    )
    parser.add_argument(
        '--max-cal-samples', type=int, default=10000,
        help='Max calibration samples (for memory). Default: 10000'
    )
    parser.add_argument(
        '--batch-size', type=int, default=500,
        help='Batch size for prediction calibration. Default: 500'
    )
    parser.add_argument(
        '--check-only', action='store_true',
        help='Only run calibration check, do not re-fit'
    )
    parser.add_argument(
        '--window-days', type=int, default=30,
        help='Lookback window for drift check in days. Default: 30'
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CONFORMAL PREDICTION CALIBRATION PIPELINE")
    logger.info("=" * 60)
    logger.info(f"Alpha: {args.alpha} (coverage: {1 - args.alpha:.0%})")
    logger.info(f"Model: {args.model_version}")
    logger.info(f"Max calibration samples: {args.max_cal_samples}")

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    try:
        if args.check_only:
            # Just check calibration quality
            logger.info("Running calibration check only...")
            result = await run_calibration_check(
                pool,
                model_name=args.model_version,
                window_days=args.window_days,
            )
            logger.info(f"Drift detected: {result.get('drift_detected', 'N/A')}")
            logger.info(f"ECE: {result.get('ece', 'N/A')}")
            logger.info(f"MCE: {result.get('mce', 'N/A')}")
            return

        # Step 1: Fetch calibration data
        logger.info("\nStep 1: Fetching calibration data...")
        tender_ids, y_pred, y_true = await fetch_calibration_data(
            pool,
            model_version=args.model_version,
            max_samples=args.max_cal_samples,
        )

        # Step 2: Fit conformal predictor
        logger.info("\nStep 2: Fitting conformal predictor...")
        cp = await fit_and_store_conformal(
            pool, y_pred, y_true,
            alpha=args.alpha,
            model_name=args.model_version,
        )

        # Step 3: Calibrate all existing predictions
        logger.info("\nStep 3: Calibrating all predictions...")
        n_calibrated = await calibrate_all_predictions(
            pool, cp,
            model_version=args.model_version,
            batch_size=args.batch_size,
        )

        # Step 4: Run calibration check
        logger.info("\nStep 4: Running calibration quality check...")
        drift_result = await run_calibration_check(
            pool,
            model_name=args.model_version,
            window_days=args.window_days,
        )

        # Summary
        params = cp.get_parameters()
        logger.info("\n" + "=" * 60)
        logger.info("CALIBRATION COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Conformal quantile: {params['quantile_threshold']:.4f}")
        logger.info(f"Platt scaling: a={params['platt_a']:.4f}, b={params['platt_b']:.4f}")
        logger.info(f"Predictions calibrated: {n_calibrated:,}")
        logger.info(f"Drift detected: {drift_result.get('drift_detected', 'N/A')}")
        logger.info(f"ECE: {drift_result.get('ece', 'N/A')}")

    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
