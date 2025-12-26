"""
Prediction Pipeline for Corruption Detection

This module provides batch prediction capabilities:
1. Load trained models from disk or MLflow
2. Extract features for new/updated tenders
3. Generate predictions using ensemble
4. Update database tables (corruption_flags, tender_risk_scores)
5. Support incremental prediction (only new tenders)

Usage:
    python predict_pipeline.py --batch-size 1000 --incremental

Author: NabavkiData
License: Proprietary
"""

import os
import sys
import json
import asyncio
import logging
import argparse
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

import numpy as np
import asyncpg

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from ai.corruption.features.feature_extractor import FeatureExtractor, FeatureVector

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Result for a single tender prediction."""
    tender_id: str
    risk_score: float  # 0-100
    risk_level: str  # minimal, low, medium, high, critical
    model_scores: Dict[str, float]  # Individual model scores
    confidence: float  # 0-1
    feature_contributions: Optional[Dict[str, float]] = None


class CorruptionPredictor:
    """
    Batch prediction pipeline for corruption detection.

    Handles:
    - Loading trained models
    - Feature extraction for new tenders
    - Generating ensemble predictions
    - Updating database with results
    """

    def __init__(
        self,
        models_dir: str = "./models",
        db_url: Optional[str] = None
    ):
        """
        Initialize the predictor.

        Args:
            models_dir: Directory containing trained models
            db_url: PostgreSQL connection URL
        """
        self.models_dir = Path(models_dir)
        self.db_url = db_url or os.environ.get(
            'DATABASE_URL',
            'postgresql://postgres:password@localhost:5432/nabavkidata'
        )

        self.pool: Optional[asyncpg.Pool] = None
        self.feature_extractor: Optional[FeatureExtractor] = None

        # Models
        self.models: Dict[str, Any] = {}
        self.scaler = None
        self.feature_names: List[str] = []

        logger.info(f"Predictor initialized. Models dir: {self.models_dir}")

    async def initialize(self):
        """Initialize database connection and load models."""
        # Database connection
        self.pool = await asyncpg.create_pool(
            dsn=self.db_url,
            min_size=2,
            max_size=10,
            command_timeout=300
        )

        self.feature_extractor = FeatureExtractor(self.pool)

        # Load models
        self._load_models()

        logger.info("Predictor initialized with database connection and models")

    async def cleanup(self):
        """Close database connections."""
        if self.pool:
            await self.pool.close()

    def _load_models(self):
        """Load trained models from disk."""
        logger.info(f"Loading models from {self.models_dir}")

        # Load scaler
        scaler_path = self.models_dir / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, 'rb') as f:
                self.scaler = pickle.load(f)
            logger.info("Loaded scaler")
        else:
            logger.warning("No scaler found - predictions may be inaccurate")

        # Load feature names
        feature_names_path = self.models_dir / "feature_names.json"
        if feature_names_path.exists():
            with open(feature_names_path, 'r') as f:
                self.feature_names = json.load(f)
            logger.info(f"Loaded {len(self.feature_names)} feature names")

        # Load individual models
        model_files = {
            'random_forest': 'random_forest.pkl',
            'xgboost': 'xgboost.pkl',
            'neural_network': 'neural_network.pkl',
            'anomaly': 'anomaly_detector.pkl',
            'ensemble': 'ensemble.pkl'
        }

        for name, filename in model_files.items():
            path = self.models_dir / filename
            if path.exists():
                try:
                    with open(path, 'rb') as f:
                        self.models[name] = pickle.load(f)
                    logger.info(f"Loaded model: {name}")
                except Exception as e:
                    logger.error(f"Failed to load {name}: {e}")

        if not self.models:
            raise RuntimeError("No models found in models directory")

        logger.info(f"Loaded {len(self.models)} models")

    def _get_model_prediction(
        self,
        model_name: str,
        X: np.ndarray
    ) -> np.ndarray:
        """
        Get prediction probabilities from a single model.

        Args:
            model_name: Name of the model
            X: Feature array

        Returns:
            Array of probability scores (0-1)
        """
        model = self.models.get(model_name)
        if model is None:
            return np.zeros(len(X))

        try:
            if model_name == 'neural_network':
                import torch
                model.eval()
                with torch.no_grad():
                    device = next(model.parameters()).device
                    X_t = torch.FloatTensor(X).to(device)
                    proba = model(X_t).cpu().numpy().flatten()
                return proba

            elif model_name == 'anomaly':
                raw_scores = model.decision_function(X)
                # Normalize to 0-1 (higher = more anomalous)
                proba = 1 - (raw_scores - raw_scores.min()) / (raw_scores.max() - raw_scores.min() + 1e-10)
                return proba

            elif model_name == 'ensemble':
                # Ensemble uses base model predictions
                base_preds = []
                for base_name in model.get('base_model_types', []):
                    base_proba = self._get_model_prediction(base_name, X)
                    base_preds.append(base_proba)

                if base_preds:
                    stacked = np.column_stack(base_preds)
                    meta_model = model['meta_model']
                    return meta_model.predict_proba(stacked)[:, 1]
                return np.zeros(len(X))

            else:
                # Standard sklearn-style model
                return model.predict_proba(X)[:, 1]

        except Exception as e:
            logger.error(f"Error getting prediction from {model_name}: {e}")
            return np.zeros(len(X))

    def _calculate_risk_level(self, score: float) -> str:
        """Convert numeric score to risk level."""
        if score >= 80:
            return 'critical'
        elif score >= 60:
            return 'high'
        elif score >= 40:
            return 'medium'
        elif score >= 20:
            return 'low'
        else:
            return 'minimal'

    async def get_tenders_to_predict(
        self,
        limit: int = 1000,
        incremental: bool = True,
        start_date: Optional[str] = None,
        force_tender_ids: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get list of tender IDs that need predictions.

        Args:
            limit: Maximum tenders to process
            incremental: Only process new/updated tenders
            start_date: Only process tenders from this date
            force_tender_ids: Specific tenders to process

        Returns:
            List of tender IDs
        """
        if force_tender_ids:
            return force_tender_ids[:limit]

        async with self.pool.acquire() as conn:
            if incremental:
                # Get tenders without risk scores or with outdated scores
                query = """
                    SELECT t.tender_id
                    FROM tenders t
                    LEFT JOIN tender_risk_scores trs ON t.tender_id = trs.tender_id
                    WHERE t.status IN ('awarded', 'completed', 'closed')
                      AND t.winner IS NOT NULL
                      AND (
                          trs.tender_id IS NULL
                          OR trs.last_analyzed < t.scraped_at
                          OR trs.last_analyzed < NOW() - INTERVAL '7 days'
                      )
                """

                params = []
                if start_date:
                    query += " AND t.publication_date >= $1"
                    params.append(start_date)

                query += f" ORDER BY t.publication_date DESC LIMIT {limit}"

                rows = await conn.fetch(query, *params)
            else:
                # Get all awarded tenders
                query = """
                    SELECT tender_id
                    FROM tenders
                    WHERE status IN ('awarded', 'completed', 'closed')
                      AND winner IS NOT NULL
                """

                params = []
                if start_date:
                    query += " AND publication_date >= $1"
                    params.append(start_date)

                query += f" ORDER BY publication_date DESC LIMIT {limit}"

                rows = await conn.fetch(query, *params)

            tender_ids = [row['tender_id'] for row in rows]
            logger.info(f"Found {len(tender_ids)} tenders to predict")
            return tender_ids

    async def predict_batch(
        self,
        tender_ids: List[str],
        use_ensemble: bool = True
    ) -> List[PredictionResult]:
        """
        Generate predictions for a batch of tenders.

        Args:
            tender_ids: List of tender IDs
            use_ensemble: Whether to use ensemble (if available)

        Returns:
            List of PredictionResult objects
        """
        if not tender_ids:
            return []

        logger.info(f"Extracting features for {len(tender_ids)} tenders...")

        # Extract features
        feature_vectors = await self.feature_extractor.extract_features_batch(tender_ids)

        if not feature_vectors:
            logger.warning("No features extracted")
            return []

        # Convert to array
        X = np.stack([fv.feature_array for fv in feature_vectors])
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        # Scale if scaler available
        if self.scaler:
            X_scaled = self.scaler.transform(X)
        else:
            X_scaled = X

        logger.info(f"Generating predictions for {len(X_scaled)} tenders...")

        # Get predictions from all models
        model_scores = {}
        for model_name in self.models.keys():
            if model_name == 'ensemble' and not use_ensemble:
                continue
            scores = self._get_model_prediction(model_name, X_scaled)
            model_scores[model_name] = scores

        # Calculate final scores
        results = []

        for i, fv in enumerate(feature_vectors):
            # Collect scores from each model
            individual_scores = {
                name: float(scores[i]) * 100
                for name, scores in model_scores.items()
            }

            # Use ensemble if available, otherwise average
            if 'ensemble' in individual_scores:
                risk_score = individual_scores['ensemble']
            else:
                # Weighted average of available models
                weights = {
                    'xgboost': 1.2,
                    'random_forest': 1.0,
                    'neural_network': 0.9,
                    'anomaly': 0.7
                }

                weighted_sum = sum(
                    individual_scores.get(m, 0) * weights.get(m, 1.0)
                    for m in individual_scores
                )
                weight_total = sum(
                    weights.get(m, 1.0) for m in individual_scores
                )
                risk_score = weighted_sum / weight_total if weight_total > 0 else 0

            # Calculate confidence based on model agreement
            score_values = list(individual_scores.values())
            if len(score_values) >= 2:
                score_std = np.std(score_values)
                confidence = max(0.5, 1.0 - score_std / 50)  # Lower std = higher confidence
            else:
                confidence = 0.7

            result = PredictionResult(
                tender_id=fv.tender_id,
                risk_score=min(100, max(0, risk_score)),
                risk_level=self._calculate_risk_level(risk_score),
                model_scores=individual_scores,
                confidence=float(confidence)
            )

            results.append(result)

        logger.info(f"Generated {len(results)} predictions")
        return results

    async def update_database(
        self,
        predictions: List[PredictionResult],
        create_flags: bool = True
    ):
        """
        Update database with predictions.

        Updates:
        - tender_risk_scores table
        - corruption_flags table (optional)

        Args:
            predictions: List of predictions
            create_flags: Whether to create corruption_flags entries
        """
        if not predictions:
            return

        logger.info(f"Updating database with {len(predictions)} predictions...")

        async with self.pool.acquire() as conn:
            # Update tender_risk_scores
            for pred in predictions:
                # Upsert risk score
                await conn.execute("""
                    INSERT INTO tender_risk_scores (
                        tender_id, risk_score, risk_level, flag_count,
                        last_analyzed, flags_summary
                    ) VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (tender_id) DO UPDATE SET
                        risk_score = EXCLUDED.risk_score,
                        risk_level = EXCLUDED.risk_level,
                        last_analyzed = EXCLUDED.last_analyzed,
                        flags_summary = EXCLUDED.flags_summary
                """,
                    pred.tender_id,
                    int(pred.risk_score),
                    pred.risk_level,
                    0,  # flag_count will be updated by trigger
                    datetime.utcnow(),
                    json.dumps({
                        'model_scores': pred.model_scores,
                        'confidence': pred.confidence,
                        'prediction_source': 'ml_pipeline'
                    })
                )

                # Create ML-based corruption flag if high risk
                if create_flags and pred.risk_score >= 60:
                    # Check if ML flag already exists
                    existing = await conn.fetchval("""
                        SELECT flag_id FROM corruption_flags
                        WHERE tender_id = $1
                          AND flag_type = 'ml_prediction'
                          AND false_positive = FALSE
                    """, pred.tender_id)

                    if not existing:
                        await conn.execute("""
                            INSERT INTO corruption_flags (
                                tender_id, flag_type, severity, score,
                                evidence, description, detected_at
                            ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                            ON CONFLICT DO NOTHING
                        """,
                            pred.tender_id,
                            'ml_prediction',
                            'high' if pred.risk_score >= 80 else 'medium',
                            int(pred.risk_score),
                            json.dumps(pred.model_scores),
                            f"ML модел детектира висок ризик (скор: {pred.risk_score:.0f})",
                            datetime.utcnow()
                        )

        logger.info("Database update complete")

    async def run_predictions(
        self,
        limit: int = 1000,
        batch_size: int = 100,
        incremental: bool = True,
        start_date: Optional[str] = None,
        update_db: bool = True,
        force_tender_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Run the complete prediction pipeline.

        Args:
            limit: Maximum tenders to process
            batch_size: Tenders per batch
            incremental: Only process new/updated tenders
            start_date: Filter by publication date
            update_db: Whether to update database
            force_tender_ids: Specific tenders to process

        Returns:
            Summary dictionary
        """
        logger.info("=" * 60)
        logger.info("Starting Corruption Detection Prediction Pipeline")
        logger.info("=" * 60)

        summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'parameters': {
                'limit': limit,
                'batch_size': batch_size,
                'incremental': incremental,
                'start_date': start_date
            },
            'results': {
                'total_processed': 0,
                'high_risk_count': 0,
                'critical_count': 0,
                'average_score': 0.0
            }
        }

        try:
            # Get tenders to process
            tender_ids = await self.get_tenders_to_predict(
                limit=limit,
                incremental=incremental,
                start_date=start_date,
                force_tender_ids=force_tender_ids
            )

            if not tender_ids:
                logger.info("No tenders to process")
                return summary

            all_predictions = []

            # Process in batches
            for i in range(0, len(tender_ids), batch_size):
                batch_ids = tender_ids[i:i + batch_size]
                logger.info(f"Processing batch {i // batch_size + 1}/{(len(tender_ids) + batch_size - 1) // batch_size}")

                predictions = await self.predict_batch(batch_ids)
                all_predictions.extend(predictions)

                if update_db:
                    await self.update_database(predictions)

            # Calculate summary statistics
            if all_predictions:
                scores = [p.risk_score for p in all_predictions]
                high_risk = sum(1 for p in all_predictions if p.risk_level in ('high', 'critical'))
                critical = sum(1 for p in all_predictions if p.risk_level == 'critical')

                summary['results'] = {
                    'total_processed': len(all_predictions),
                    'high_risk_count': high_risk,
                    'critical_count': critical,
                    'average_score': float(np.mean(scores)),
                    'median_score': float(np.median(scores)),
                    'max_score': float(np.max(scores)),
                    'score_distribution': {
                        'minimal': sum(1 for p in all_predictions if p.risk_level == 'minimal'),
                        'low': sum(1 for p in all_predictions if p.risk_level == 'low'),
                        'medium': sum(1 for p in all_predictions if p.risk_level == 'medium'),
                        'high': sum(1 for p in all_predictions if p.risk_level == 'high'),
                        'critical': sum(1 for p in all_predictions if p.risk_level == 'critical')
                    }
                }

            logger.info("=" * 60)
            logger.info(f"Prediction complete! Processed {len(all_predictions)} tenders")
            logger.info(f"High risk: {summary['results'].get('high_risk_count', 0)}")
            logger.info(f"Critical: {summary['results'].get('critical_count', 0)}")
            logger.info("=" * 60)

            return summary

        except Exception as e:
            logger.error(f"Prediction pipeline failed: {e}")
            summary['error'] = str(e)
            raise

    async def predict_single(
        self,
        tender_id: str,
        update_db: bool = False
    ) -> Optional[PredictionResult]:
        """
        Generate prediction for a single tender.

        Args:
            tender_id: Tender ID
            update_db: Whether to update database

        Returns:
            PredictionResult or None if failed
        """
        predictions = await self.predict_batch([tender_id])

        if predictions:
            if update_db:
                await self.update_database(predictions)
            return predictions[0]

        return None


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Run corruption detection predictions")
    parser.add_argument('--limit', type=int, default=1000, help='Maximum tenders to process')
    parser.add_argument('--batch-size', type=int, default=100, help='Batch size')
    parser.add_argument('--incremental', action='store_true', default=True,
                       help='Only process new/updated tenders')
    parser.add_argument('--full', action='store_true', help='Process all tenders (not incremental)')
    parser.add_argument('--start-date', type=str, default=None, help='Filter by date (YYYY-MM-DD)')
    parser.add_argument('--models-dir', type=str, default='./models', help='Models directory')
    parser.add_argument('--db-url', type=str, default=None, help='Database URL')
    parser.add_argument('--no-update', action='store_true', help='Skip database update')
    parser.add_argument('--tender-id', type=str, default=None, help='Process single tender')
    parser.add_argument('--verbose', action='store_true', help='Verbose logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Initialize predictor
    predictor = CorruptionPredictor(
        models_dir=args.models_dir,
        db_url=args.db_url
    )

    try:
        await predictor.initialize()

        if args.tender_id:
            # Single tender prediction
            result = await predictor.predict_single(
                args.tender_id,
                update_db=not args.no_update
            )

            if result:
                print(f"\nPrediction for {args.tender_id}:")
                print(f"  Risk Score: {result.risk_score:.1f}")
                print(f"  Risk Level: {result.risk_level}")
                print(f"  Confidence: {result.confidence:.2f}")
                print(f"  Model Scores:")
                for model, score in result.model_scores.items():
                    print(f"    {model}: {score:.1f}")
            else:
                print(f"Failed to generate prediction for {args.tender_id}")
        else:
            # Batch prediction
            summary = await predictor.run_predictions(
                limit=args.limit,
                batch_size=args.batch_size,
                incremental=not args.full,
                start_date=args.start_date,
                update_db=not args.no_update
            )

            print("\n" + "=" * 60)
            print("PREDICTION SUMMARY")
            print("=" * 60)
            print(f"Total Processed: {summary['results']['total_processed']}")
            print(f"High Risk:       {summary['results']['high_risk_count']}")
            print(f"Critical:        {summary['results']['critical_count']}")
            print(f"Average Score:   {summary['results'].get('average_score', 0):.1f}")

            if 'score_distribution' in summary['results']:
                print("\nRisk Distribution:")
                for level, count in summary['results']['score_distribution'].items():
                    print(f"  {level}: {count}")

    finally:
        await predictor.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
