"""
Adversarial Training Pipeline

Retrains models with adversarial examples injected into training data.
This hardens models against small feature perturbations that corrupt actors
might use to evade detection.

Uses only numpy and sklearn -- no torch or adversarial ML libraries.
Memory-efficient for 3.8GB EC2 instances.

Author: nabavkidata.com
"""

import os
import sys
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional

import asyncpg
import numpy as np
import joblib
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score
)

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feature_extractor import FeatureExtractor
from ai.corruption.ml_models.adversarial import (
    AdversarialAnalyzer,
    FEATURE_CONSTRAINTS,
    BINARY_FEATURES,
)

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    os.getenv("DATABASE_URL")
)


class AdversarialTrainer:
    """
    Adversarial training pipeline for corruption detection models.

    Generates adversarial examples from existing flagged tenders and
    retrains models with augmented data to improve robustness.
    """

    def __init__(self):
        self.analyzer = AdversarialAnalyzer()
        self.feature_names: List[str] = []

    async def generate_augmented_dataset(
        self,
        pool: asyncpg.Pool,
        n_adversarial: int = 1000,
        model_name: str = 'xgboost',
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Generate adversarial training data:
        1. Take existing flagged tenders (positive class)
        2. Generate adversarial perturbations that try to make them look clean
        3. Add these to training set with original (flagged) labels

        This teaches the model that even slightly perturbed flagged tenders
        should still be classified as flagged.

        Args:
            pool: AsyncPG connection pool
            n_adversarial: Number of adversarial examples to generate
            model_name: Which model to base adversarial examples on

        Returns:
            (X_augmented, y_augmented, feature_names)
        """
        logger.info(f"Generating adversarial augmented dataset ({n_adversarial} examples)...")

        # Load the model for adversarial generation
        self.analyzer.load_model(model_name)
        self.feature_names = self.analyzer.feature_names

        # Get flagged tenders to generate adversarial examples from
        async with pool.acquire() as conn:
            flagged_rows = await conn.fetch("""
                SELECT DISTINCT cf.tender_id
                FROM corruption_flags cf
                JOIN tenders t ON cf.tender_id = t.tender_id
                WHERE cf.flag_type IN ('short_deadline', 'price_anomaly', 'bid_clustering', 'repeat_winner')
                  AND cf.score >= 30
                  AND t.status IN ('awarded', 'closed', 'completed')
                ORDER BY RANDOM()
                LIMIT $1
            """, min(n_adversarial * 2, 5000))

        flagged_ids = [row['tender_id'] for row in flagged_rows]
        logger.info(f"Found {len(flagged_ids)} flagged tenders for adversarial generation")

        if len(flagged_ids) == 0:
            logger.warning("No flagged tenders found. Cannot generate adversarial examples.")
            return np.array([]), np.array([]), self.feature_names

        # Extract features for flagged tenders
        extractor = FeatureExtractor(pool)
        original_features = []
        valid_ids = []

        for tender_id in flagged_ids:
            try:
                fv = await extractor.extract_features(tender_id, include_metadata=False)
                original_features.append(fv.feature_array)
                valid_ids.append(tender_id)
            except Exception as e:
                logger.debug(f"Skipping {tender_id}: {e}")

            if len(valid_ids) >= n_adversarial:
                break

        if len(original_features) == 0:
            logger.warning("Could not extract features for any flagged tenders.")
            return np.array([]), np.array([]), self.feature_names

        logger.info(f"Extracted features for {len(original_features)} tenders")

        # Generate adversarial examples from each flagged tender
        adversarial_features = []
        adversarial_labels = []

        for i, fv in enumerate(original_features):
            try:
                # Generate adversarial examples that try to look clean
                adv_examples = self.analyzer.generate_adversarial_examples(
                    fv,
                    n_examples=3,  # 3 adversarial variants per tender
                    epsilon=0.15,  # moderate perturbation
                    target_direction='reduce_risk',
                )

                for ex in adv_examples:
                    adv_vector = np.array(ex['feature_vector'], dtype=np.float32)
                    adversarial_features.append(adv_vector)
                    # Keep the original label (flagged = 1)
                    # This teaches the model: even after perturbation, still flagged
                    adversarial_labels.append(1)

            except Exception as e:
                logger.debug(f"Failed adversarial generation for tender {i}: {e}")

            if len(adversarial_features) >= n_adversarial:
                break

        # Trim to requested size
        adversarial_features = adversarial_features[:n_adversarial]
        adversarial_labels = adversarial_labels[:n_adversarial]

        logger.info(f"Generated {len(adversarial_features)} adversarial examples")

        X_adv = np.array(adversarial_features, dtype=np.float32)
        y_adv = np.array(adversarial_labels, dtype=np.int32)

        return X_adv, y_adv, self.feature_names

    async def retrain_with_adversarial(
        self,
        pool: asyncpg.Pool,
        augmentation_ratio: float = 0.2,
        model_name: str = 'xgboost',
        n_adversarial: int = 1000,
        save_models: bool = True,
    ) -> dict:
        """
        Retrain RF + XGBoost with adversarial augmentation.
        A fraction of training data is adversarial examples.

        Compare performance before/after.

        Args:
            pool: Database connection pool
            augmentation_ratio: Fraction of training data that is adversarial
            model_name: Base model for adversarial example generation
            n_adversarial: Number of adversarial examples to generate
            save_models: Whether to save retrained models

        Returns:
            {
                model_name: {
                    accuracy_before, accuracy_after,
                    auc_before, auc_after,
                    robustness_before, robustness_after
                }
            }
        """
        logger.info("=" * 60)
        logger.info("ADVERSARIAL RETRAINING PIPELINE")
        logger.info(f"Augmentation ratio: {augmentation_ratio}")
        logger.info(f"Target adversarial examples: {n_adversarial}")
        logger.info("=" * 60)

        # Step 1: Load original training data
        logger.info("Step 1: Creating original labeled dataset...")

        async with pool.acquire() as conn:
            # Get positive samples (flagged tenders)
            positive_rows = await conn.fetch("""
                SELECT DISTINCT t.tender_id
                FROM tenders t
                JOIN corruption_flags cf ON t.tender_id = cf.tender_id
                WHERE cf.flag_type IN ('short_deadline', 'price_anomaly', 'bid_clustering', 'repeat_winner')
                  AND cf.score >= 30
                  AND t.status IN ('awarded', 'closed', 'completed')
                ORDER BY RANDOM()
                LIMIT 5000
            """)
            positive_ids = [r['tender_id'] for r in positive_rows]

            # Get negative samples
            neg_limit = len(positive_ids) * 3
            negative_rows = await conn.fetch("""
                SELECT t.tender_id
                FROM tenders t
                WHERE t.status IN ('awarded', 'closed', 'completed')
                  AND NOT EXISTS (
                      SELECT 1 FROM corruption_flags cf
                      WHERE cf.tender_id = t.tender_id
                        AND cf.flag_type IN ('short_deadline', 'price_anomaly', 'bid_clustering', 'repeat_winner')
                  )
                ORDER BY RANDOM()
                LIMIT $1
            """, neg_limit)
            negative_ids = [r['tender_id'] for r in negative_rows]

        tender_ids = positive_ids + negative_ids
        labels = [1] * len(positive_ids) + [0] * len(negative_ids)

        logger.info(f"Dataset: {len(positive_ids)} positive, {len(negative_ids)} negative")

        # Step 2: Extract features
        logger.info("Step 2: Extracting features...")
        extractor = FeatureExtractor(pool)
        all_features = []
        valid_labels = []

        for i, tender_id in enumerate(tender_ids):
            try:
                fv = await extractor.extract_features(tender_id, include_metadata=False)
                all_features.append(fv.feature_array)
                valid_labels.append(labels[i])
            except Exception:
                pass

            if (i + 1) % 500 == 0:
                logger.info(f"  Extracted {i + 1}/{len(tender_ids)} features...")

        X_original = np.array(all_features, dtype=np.float32)
        y_original = np.array(valid_labels, dtype=np.int32)
        feature_names = extractor.feature_names

        logger.info(f"Original dataset: {X_original.shape[0]} samples, {X_original.shape[1]} features")

        # Step 3: Train/test split (BEFORE augmentation -- test set stays clean)
        X_train_orig, X_test, y_train_orig, y_test = train_test_split(
            X_original, y_original, test_size=0.2, random_state=42, stratify=y_original
        )

        logger.info(f"Train: {len(y_train_orig)}, Test: {len(y_test)}")

        # Step 4: Evaluate BEFORE adversarial augmentation
        logger.info("Step 3: Evaluating models BEFORE adversarial augmentation...")
        results_before = self._train_and_evaluate(
            X_train_orig, y_train_orig, X_test, y_test, feature_names, prefix="before"
        )

        # Step 5: Generate adversarial examples
        logger.info("Step 4: Generating adversarial examples...")
        X_adv, y_adv, _ = await self.generate_augmented_dataset(
            pool, n_adversarial=n_adversarial, model_name=model_name
        )

        if len(X_adv) == 0:
            logger.warning("No adversarial examples generated. Returning original results.")
            return {
                'xgboost': {**results_before['xgboost'], 'adversarial_count': 0},
                'random_forest': {**results_before['random_forest'], 'adversarial_count': 0},
            }

        # Step 6: Augment training set
        # Limit adversarial examples to augmentation_ratio of original training data
        max_adv = int(len(X_train_orig) * augmentation_ratio)
        X_adv_limited = X_adv[:max_adv]
        y_adv_limited = y_adv[:max_adv]

        X_train_aug = np.vstack([X_train_orig, X_adv_limited])
        y_train_aug = np.concatenate([y_train_orig, y_adv_limited])

        logger.info(
            f"Augmented training set: {len(X_train_orig)} original + "
            f"{len(X_adv_limited)} adversarial = {len(X_train_aug)} total"
        )

        # Step 7: Retrain and evaluate AFTER augmentation
        logger.info("Step 5: Evaluating models AFTER adversarial augmentation...")
        results_after = self._train_and_evaluate(
            X_train_aug, y_train_aug, X_test, y_test, feature_names, prefix="after"
        )

        # Step 8: Robustness comparison
        logger.info("Step 6: Computing robustness metrics...")
        robustness_before = self._compute_robustness_sample(
            X_test, y_test, results_before, feature_names, sample_size=50
        )
        robustness_after = self._compute_robustness_sample(
            X_test, y_test, results_after, feature_names, sample_size=50
        )

        # Step 9: Save hardened models
        if save_models:
            logger.info("Step 7: Saving adversarially-hardened models...")
            self._save_hardened_models(
                results_after, feature_names, len(X_adv_limited)
            )

        # Compile results
        final_results = {}
        for model_key in ['xgboost', 'random_forest']:
            final_results[model_key] = {
                'accuracy_before': results_before[model_key]['accuracy'],
                'accuracy_after': results_after[model_key]['accuracy'],
                'auc_before': results_before[model_key]['roc_auc'],
                'auc_after': results_after[model_key]['roc_auc'],
                'f1_before': results_before[model_key]['f1'],
                'f1_after': results_after[model_key]['f1'],
                'robustness_before': robustness_before.get(model_key, 0.0),
                'robustness_after': robustness_after.get(model_key, 0.0),
                'adversarial_count': len(X_adv_limited),
                'augmentation_ratio': augmentation_ratio,
            }

        logger.info("\n" + "=" * 60)
        logger.info("ADVERSARIAL RETRAINING COMPLETE")
        logger.info("=" * 60)
        for model_key, res in final_results.items():
            logger.info(f"\n{model_key}:")
            logger.info(f"  Accuracy: {res['accuracy_before']:.4f} -> {res['accuracy_after']:.4f}")
            logger.info(f"  AUC:      {res['auc_before']:.4f} -> {res['auc_after']:.4f}")
            logger.info(f"  F1:       {res['f1_before']:.4f} -> {res['f1_after']:.4f}")
            logger.info(f"  Robustness: {res['robustness_before']:.4f} -> {res['robustness_after']:.4f}")

        return final_results

    def _train_and_evaluate(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_test: np.ndarray,
        y_test: np.ndarray,
        feature_names: List[str],
        prefix: str = "",
    ) -> dict:
        """
        Train XGBoost + RandomForest and evaluate on test set.

        Returns dict with model objects and metrics.
        """
        # Preprocess
        imputer = SimpleImputer(strategy='median')
        X_train_imp = imputer.fit_transform(np.nan_to_num(X_train, nan=0, posinf=0, neginf=0))
        X_test_imp = imputer.transform(np.nan_to_num(X_test, nan=0, posinf=0, neginf=0))

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train_imp)
        X_test_scaled = scaler.transform(X_test_imp)

        results = {}

        # Train XGBoost
        try:
            from xgboost import XGBClassifier
            xgb = XGBClassifier(
                n_estimators=200,
                max_depth=6,
                learning_rate=0.1,
                subsample=0.8,
                colsample_bytree=0.8,
                reg_alpha=0.1,
                reg_lambda=1.0,
                random_state=42,
                n_jobs=-1,
                eval_metric='auc',
                early_stopping_rounds=20,
            )
            X_tr, X_val, y_tr, y_val = train_test_split(
                X_train_scaled, y_train, test_size=0.2, random_state=42,
                stratify=y_train
            )
            xgb.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

            y_pred = xgb.predict(X_test_scaled)
            y_proba = xgb.predict_proba(X_test_scaled)[:, 1]

            results['xgboost'] = {
                'model': xgb,
                'imputer': imputer,
                'scaler': scaler,
                'accuracy': float(accuracy_score(y_test, y_pred)),
                'precision': float(precision_score(y_test, y_pred, zero_division=0)),
                'recall': float(recall_score(y_test, y_pred, zero_division=0)),
                'f1': float(f1_score(y_test, y_pred, zero_division=0)),
                'roc_auc': float(roc_auc_score(y_test, y_proba)),
            }
            logger.info(
                f"  XGBoost ({prefix}): AUC={results['xgboost']['roc_auc']:.4f}, "
                f"F1={results['xgboost']['f1']:.4f}"
            )
        except ImportError:
            logger.warning("XGBoost not available, skipping.")
            results['xgboost'] = {
                'model': None, 'imputer': imputer, 'scaler': scaler,
                'accuracy': 0, 'precision': 0, 'recall': 0, 'f1': 0, 'roc_auc': 0,
            }

        # Train Random Forest
        from sklearn.ensemble import RandomForestClassifier
        rf = RandomForestClassifier(
            n_estimators=200,
            max_depth=10,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features='sqrt',
            class_weight='balanced',
            random_state=42,
            n_jobs=-1,
        )
        rf.fit(X_train_scaled, y_train)

        y_pred_rf = rf.predict(X_test_scaled)
        y_proba_rf = rf.predict_proba(X_test_scaled)[:, 1]

        results['random_forest'] = {
            'model': rf,
            'imputer': imputer,
            'scaler': scaler,
            'accuracy': float(accuracy_score(y_test, y_pred_rf)),
            'precision': float(precision_score(y_test, y_pred_rf, zero_division=0)),
            'recall': float(recall_score(y_test, y_pred_rf, zero_division=0)),
            'f1': float(f1_score(y_test, y_pred_rf, zero_division=0)),
            'roc_auc': float(roc_auc_score(y_test, y_proba_rf)),
        }
        logger.info(
            f"  RandomForest ({prefix}): AUC={results['random_forest']['roc_auc']:.4f}, "
            f"F1={results['random_forest']['f1']:.4f}"
        )

        return results

    def _compute_robustness_sample(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        train_results: dict,
        feature_names: List[str],
        sample_size: int = 50,
    ) -> dict:
        """
        Compute average robustness score on a sample of test predictions.
        Uses a temporary AdversarialAnalyzer with the trained model.
        """
        robustness_scores = {}

        for model_key in ['xgboost', 'random_forest']:
            model_data = train_results.get(model_key, {})
            model = model_data.get('model')
            imputer = model_data.get('imputer')
            scaler = model_data.get('scaler')

            if model is None:
                robustness_scores[model_key] = 0.0
                continue

            # Create a temporary analyzer with this model
            temp_analyzer = AdversarialAnalyzer()
            temp_analyzer.model = model
            temp_analyzer.imputer = imputer
            temp_analyzer.scaler = scaler
            temp_analyzer.feature_names = feature_names
            temp_analyzer.model_name = model_key
            temp_analyzer._loaded = True

            # Sample test points
            rng = np.random.RandomState(42)
            indices = rng.choice(
                len(X_test), size=min(sample_size, len(X_test)), replace=False
            )

            scores = []
            for idx in indices:
                try:
                    result = temp_analyzer.assess_prediction_robustness(X_test[idx])
                    scores.append(result['robustness_score'])
                except Exception:
                    pass

            avg_robustness = float(np.mean(scores)) if scores else 0.0
            robustness_scores[model_key] = avg_robustness
            logger.info(f"  {model_key} avg robustness: {avg_robustness:.4f} (n={len(scores)})")

        return robustness_scores

    def _save_hardened_models(
        self,
        results: dict,
        feature_names: List[str],
        adversarial_count: int,
    ) -> None:
        """Save adversarially-hardened models to disk."""
        timestamp = datetime.utcnow().isoformat()

        for model_key in ['xgboost', 'random_forest']:
            model_data = results.get(model_key, {})
            model = model_data.get('model')
            if model is None:
                continue

            package = {
                'model': model,
                'imputer': model_data['imputer'],
                'scaler': model_data['scaler'],
                'feature_names': feature_names,
                'n_features': len(feature_names),
                'trained_on': 'real_data_adversarial',
                'is_synthetic': False,
                'adversarial_augmented': True,
                'adversarial_count': adversarial_count,
                'trained_at': timestamp,
            }

            # Save as _hardened variant (not overwriting original)
            filename = f"{model_key}_real_hardened.joblib"
            save_path = MODELS_DIR / filename
            joblib.dump(package, save_path)
            logger.info(f"Saved hardened {model_key} to {save_path}")

        # Save preprocessing separately
        if results.get('xgboost', {}).get('imputer') is not None:
            preprocessing = {
                'imputer': results['xgboost']['imputer'],
                'scaler': results['xgboost']['scaler'],
                'feature_names': feature_names,
                'n_features': len(feature_names),
            }
            joblib.dump(preprocessing, MODELS_DIR / "preprocessing_real_hardened.joblib")

        # Save training metrics
        metrics = {
            'training_timestamp': timestamp,
            'adversarial_augmented': True,
            'adversarial_count': adversarial_count,
        }
        for model_key in ['xgboost', 'random_forest']:
            model_data = results.get(model_key, {})
            metrics[model_key] = {
                k: v for k, v in model_data.items()
                if k not in ('model', 'imputer', 'scaler')
            }

        metrics_path = MODELS_DIR / "training_metrics_real_hardened.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
        logger.info(f"Saved training metrics to {metrics_path}")


async def main():
    """Run adversarial training pipeline."""
    import argparse

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    parser = argparse.ArgumentParser(description='Adversarial training for corruption detection')
    parser.add_argument('--augmentation-ratio', type=float, default=0.2,
                        help='Fraction of training data that is adversarial')
    parser.add_argument('--n-adversarial', type=int, default=1000,
                        help='Number of adversarial examples to generate')
    parser.add_argument('--model', type=str, default='xgboost',
                        choices=['xgboost', 'random_forest'],
                        help='Base model for adversarial generation')
    parser.add_argument('--no-save', action='store_true',
                        help='Do not save retrained models')

    args = parser.parse_args()

    pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=5)

    try:
        trainer = AdversarialTrainer()
        results = await trainer.retrain_with_adversarial(
            pool,
            augmentation_ratio=args.augmentation_ratio,
            model_name=args.model,
            n_adversarial=args.n_adversarial,
            save_models=not args.no_save,
        )

        print("\nResults:")
        print(json.dumps(results, indent=2))
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
