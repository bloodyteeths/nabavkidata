"""
AutoML Pipeline for Corruption Detection

Automated hyperparameter optimization and model selection.
Uses Optuna for Bayesian optimization (lightweight, pure Python).
Includes data drift detection via Population Stability Index (PSI).

Key features:
- Bayesian hyperparameter search with Optuna (TPE sampler)
- Standardized model comparison with statistical significance tests
- Data drift detection using PSI for automated retraining triggers
- Memory-efficient design for 3.8GB RAM EC2 instance

Author: nabavkidata.com
"""

import os
import sys
import json
import logging
import hashlib
import time
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any

import numpy as np
import joblib

try:
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    _OPTUNA_AVAILABLE = True
except ImportError:
    _OPTUNA_AVAILABLE = False

from sklearn.model_selection import StratifiedKFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score
)
from sklearn.ensemble import RandomForestClassifier

try:
    from xgboost import XGBClassifier
    _XGBOOST_AVAILABLE = True
except ImportError:
    _XGBOOST_AVAILABLE = False

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from features.feature_extractor import FeatureExtractor

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"
MODELS_DIR.mkdir(exist_ok=True)


class AutoMLPipeline:
    """
    Automated hyperparameter optimization and model selection pipeline.

    Uses Optuna (TPE sampler) for efficient Bayesian optimization.
    Designed to run within 3.8GB RAM constraints.
    """

    SEARCH_SPACES = {
        'random_forest': {
            'n_estimators': (50, 500),
            'max_depth': (3, 20),
            'min_samples_split': (2, 20),
            'min_samples_leaf': (1, 10),
            'max_features': ['sqrt', 'log2', 0.5, 0.8],
            'class_weight': ['balanced', 'balanced_subsample', None],
        },
        'xgboost': {
            'n_estimators': (50, 500),
            'max_depth': (3, 12),
            'learning_rate': (0.01, 0.3),
            'subsample': (0.6, 1.0),
            'colsample_bytree': (0.5, 1.0),
            'scale_pos_weight': (1, 10),
            'min_child_weight': (1, 10),
            'gamma': (0.0, 5.0),
        },
    }

    def __init__(self):
        if not _OPTUNA_AVAILABLE:
            raise ImportError(
                "Optuna is required for AutoML. Install with: pip install optuna"
            )

    # ------------------------------------------------------------------
    # Data loading helpers (reuses logic from train_real_data.py)
    # ------------------------------------------------------------------

    async def _load_training_data(
        self, pool, positive_min_score: int = 30, max_samples_per_class: int = 5000
    ) -> Tuple[np.ndarray, np.ndarray, List[str]]:
        """
        Load labeled training data from the database.

        Returns (X, y, feature_names) with preprocessed features.
        """
        logger.info("Loading labeled training data from database...")

        async with pool.acquire() as conn:
            # Positive samples: tenders with reliable corruption flags
            positive_rows = await conn.fetch("""
                SELECT DISTINCT t.tender_id
                FROM tenders t
                JOIN corruption_flags cf ON t.tender_id = cf.tender_id
                WHERE cf.flag_type IN ('short_deadline', 'price_anomaly',
                                       'bid_clustering', 'repeat_winner')
                  AND cf.score >= $1
                  AND t.status IN ('awarded', 'closed', 'completed')
                ORDER BY RANDOM()
                LIMIT $2
            """, positive_min_score, max_samples_per_class)
            positive_ids = [r['tender_id'] for r in positive_rows]

            # Negative samples: clean tenders (3:1 ratio)
            neg_limit = len(positive_ids) * 3
            negative_rows = await conn.fetch("""
                SELECT t.tender_id
                FROM tenders t
                WHERE t.status IN ('awarded', 'closed', 'completed')
                  AND NOT EXISTS (
                      SELECT 1 FROM corruption_flags cf
                      WHERE cf.tender_id = t.tender_id
                        AND cf.flag_type IN ('short_deadline', 'price_anomaly',
                                             'bid_clustering', 'repeat_winner')
                  )
                ORDER BY RANDOM()
                LIMIT $1
            """, neg_limit)
            negative_ids = [r['tender_id'] for r in negative_rows]

        tender_ids = positive_ids + negative_ids
        labels = [1] * len(positive_ids) + [0] * len(negative_ids)

        logger.info(
            f"Dataset: {len(positive_ids)} positive + {len(negative_ids)} negative "
            f"= {len(tender_ids)} total"
        )

        # Extract features
        extractor = FeatureExtractor(pool)
        feature_names = extractor.feature_names
        all_features = []
        valid_labels = []

        for tid, lbl in zip(tender_ids, labels):
            try:
                fv = await extractor.extract_features(tid, include_metadata=False)
                all_features.append(fv.feature_array)
                valid_labels.append(lbl)
            except Exception:
                pass  # skip tenders that fail feature extraction

        X = np.array(all_features)
        y = np.array(valid_labels)

        # Preprocess: impute and scale
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
        imputer = SimpleImputer(strategy='median')
        X = imputer.fit_transform(X)
        scaler = StandardScaler()
        X = scaler.fit_transform(X)

        logger.info(f"Preprocessed dataset: {X.shape[0]} samples, {X.shape[1]} features")
        return X, y, feature_names

    def _compute_data_hash(self, X: np.ndarray, y: np.ndarray) -> str:
        """Compute a deterministic hash of the training data for reproducibility."""
        h = hashlib.sha256()
        h.update(X.tobytes())
        h.update(y.tobytes())
        return h.hexdigest()[:16]

    # ------------------------------------------------------------------
    # Hyperparameter Optimization
    # ------------------------------------------------------------------

    async def optimize(
        self,
        pool,
        model_type: str = 'xgboost',
        n_trials: int = 50,
        cv_folds: int = 3,
        triggered_by: str = 'manual',
    ) -> dict:
        """
        Run Optuna hyperparameter optimization.

        Objective: maximize AUC-ROC on stratified k-fold CV.

        Args:
            pool: asyncpg connection pool
            model_type: 'xgboost' or 'random_forest'
            n_trials: number of Optuna trials (default 50)
            cv_folds: number of CV folds (default 3 for speed)
            triggered_by: 'manual', 'drift', or 'schedule'

        Returns:
            {best_params, best_score, all_trials_summary, optimization_history,
             run_id, duration_seconds}
        """
        if model_type not in self.SEARCH_SPACES:
            raise ValueError(f"Unknown model type: {model_type}. Use 'xgboost' or 'random_forest'")

        if model_type == 'xgboost' and not _XGBOOST_AVAILABLE:
            raise ImportError("XGBoost not installed. Install with: pip install xgboost")

        logger.info(f"Starting Optuna optimization for {model_type} ({n_trials} trials, {cv_folds}-fold CV)")
        start_time = time.time()

        # Load data
        X, y, feature_names = await self._load_training_data(pool)

        # Create Optuna study
        objective = self._create_objective(X, y, model_type, cv_folds)
        study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=5),
        )
        study.optimize(objective, n_trials=n_trials, n_jobs=1, show_progress_bar=False)

        duration = time.time() - start_time

        # Collect results
        all_trials = []
        for trial in study.trials:
            all_trials.append({
                'trial': trial.number,
                'params': trial.params,
                'score': trial.value if trial.value is not None else None,
                'state': str(trial.state),
            })

        result = {
            'model_type': model_type,
            'best_params': study.best_params,
            'best_score': float(study.best_value),
            'n_trials': n_trials,
            'cv_folds': cv_folds,
            'all_trials_summary': all_trials,
            'optimization_history': [
                float(study.best_trials[0].value) if study.best_trials else None
            ],
            'duration_seconds': round(duration, 2),
        }

        # Persist to database
        try:
            async with pool.acquire() as conn:
                run_id = await conn.fetchval("""
                    INSERT INTO optimization_runs
                        (model_name, n_trials, best_params, best_score,
                         all_scores, duration_seconds, triggered_by)
                    VALUES ($1, $2, $3::jsonb, $4, $5::jsonb, $6, $7)
                    RETURNING run_id
                """,
                    model_type,
                    n_trials,
                    json.dumps(study.best_params),
                    float(study.best_value),
                    json.dumps(all_trials),
                    round(duration, 2),
                    triggered_by,
                )
                result['run_id'] = run_id
        except Exception as e:
            logger.warning(f"Failed to persist optimization run: {e}")
            result['run_id'] = None

        logger.info(
            f"Optimization complete: best AUC-ROC = {study.best_value:.4f} "
            f"in {duration:.1f}s"
        )
        return result

    def _create_objective(
        self, X: np.ndarray, y: np.ndarray, model_type: str, cv_folds: int
    ):
        """Create Optuna objective function for a given model type."""
        space = self.SEARCH_SPACES[model_type]

        def objective(trial: 'optuna.Trial') -> float:
            if model_type == 'random_forest':
                params = {
                    'n_estimators': trial.suggest_int(
                        'n_estimators', *space['n_estimators']
                    ),
                    'max_depth': trial.suggest_int('max_depth', *space['max_depth']),
                    'min_samples_split': trial.suggest_int(
                        'min_samples_split', *space['min_samples_split']
                    ),
                    'min_samples_leaf': trial.suggest_int(
                        'min_samples_leaf', *space['min_samples_leaf']
                    ),
                    'max_features': trial.suggest_categorical(
                        'max_features', space['max_features']
                    ),
                    'class_weight': trial.suggest_categorical(
                        'class_weight', space['class_weight']
                    ),
                    'random_state': 42,
                    'n_jobs': -1,
                }
                model = RandomForestClassifier(**params)

            elif model_type == 'xgboost':
                params = {
                    'n_estimators': trial.suggest_int(
                        'n_estimators', *space['n_estimators']
                    ),
                    'max_depth': trial.suggest_int('max_depth', *space['max_depth']),
                    'learning_rate': trial.suggest_float(
                        'learning_rate', *space['learning_rate'], log=True
                    ),
                    'subsample': trial.suggest_float('subsample', *space['subsample']),
                    'colsample_bytree': trial.suggest_float(
                        'colsample_bytree', *space['colsample_bytree']
                    ),
                    'scale_pos_weight': trial.suggest_float(
                        'scale_pos_weight', *space['scale_pos_weight']
                    ),
                    'min_child_weight': trial.suggest_int(
                        'min_child_weight', *space['min_child_weight']
                    ),
                    'gamma': trial.suggest_float('gamma', *space['gamma']),
                    'random_state': 42,
                    'n_jobs': -1,
                    'eval_metric': 'auc',
                }
                model = XGBClassifier(**params)
            else:
                raise ValueError(f"Unknown model type: {model_type}")

            # Stratified k-fold cross-validation
            skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
            scores = cross_val_score(
                model, X, y, cv=skf, scoring='roc_auc', n_jobs=1
            )
            return float(np.mean(scores))

        return objective

    # ------------------------------------------------------------------
    # Model Comparison
    # ------------------------------------------------------------------

    async def compare_models(
        self,
        pool,
        models: dict = None,
        cv_folds: int = 5,
    ) -> dict:
        """
        Standardized model comparison with stratified CV.

        Metrics: AUC-ROC, precision, recall, F1, accuracy.
        Statistical significance: paired t-test on fold scores.

        Args:
            pool: asyncpg connection pool
            models: {name: sklearn_estimator} dict. If None, uses default RF + XGB.
            cv_folds: number of CV folds (default 5)

        Returns:
            {models: [{name, metrics, fold_scores}], best_model, significance_tests}
        """
        from scipy import stats  # only import when needed

        X, y, feature_names = await self._load_training_data(pool)

        # Default models if none provided
        if models is None:
            models = {
                'random_forest': RandomForestClassifier(
                    n_estimators=200, max_depth=10, min_samples_split=5,
                    min_samples_leaf=2, max_features='sqrt',
                    class_weight='balanced', random_state=42, n_jobs=-1,
                ),
            }
            if _XGBOOST_AVAILABLE:
                models['xgboost'] = XGBClassifier(
                    n_estimators=200, max_depth=6, learning_rate=0.1,
                    subsample=0.8, colsample_bytree=0.8, random_state=42,
                    n_jobs=-1, eval_metric='auc',
                )

        skf = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)

        results = []
        all_fold_scores = {}  # name -> list of per-fold AUC-ROC scores

        for name, model in models.items():
            logger.info(f"Evaluating {name} with {cv_folds}-fold CV...")
            fold_metrics = {
                'auc_roc': [], 'precision': [], 'recall': [], 'f1': [], 'accuracy': []
            }

            for fold_idx, (train_idx, val_idx) in enumerate(skf.split(X, y)):
                X_train, X_val = X[train_idx], X[val_idx]
                y_train, y_val = y[train_idx], y[val_idx]

                model.fit(X_train, y_train)

                y_pred = model.predict(X_val)
                y_proba = model.predict_proba(X_val)[:, 1]

                fold_metrics['auc_roc'].append(float(roc_auc_score(y_val, y_proba)))
                fold_metrics['precision'].append(
                    float(precision_score(y_val, y_pred, zero_division=0))
                )
                fold_metrics['recall'].append(
                    float(recall_score(y_val, y_pred, zero_division=0))
                )
                fold_metrics['f1'].append(
                    float(f1_score(y_val, y_pred, zero_division=0))
                )
                fold_metrics['accuracy'].append(
                    float(accuracy_score(y_val, y_pred))
                )

            mean_metrics = {
                k: round(float(np.mean(v)), 4) for k, v in fold_metrics.items()
            }
            std_metrics = {
                f"{k}_std": round(float(np.std(v)), 4) for k, v in fold_metrics.items()
            }

            all_fold_scores[name] = fold_metrics['auc_roc']
            results.append({
                'name': name,
                'metrics': {**mean_metrics, **std_metrics},
                'fold_scores': fold_metrics,
            })

        # Find best model by mean AUC-ROC
        best_model = max(results, key=lambda r: r['metrics']['auc_roc'])

        # Pairwise significance tests (paired t-test on AUC-ROC fold scores)
        significance_tests = []
        model_names = list(all_fold_scores.keys())
        for i in range(len(model_names)):
            for j in range(i + 1, len(model_names)):
                n1, n2 = model_names[i], model_names[j]
                s1, s2 = all_fold_scores[n1], all_fold_scores[n2]
                if len(s1) == len(s2) and len(s1) >= 2:
                    t_stat, p_value = stats.ttest_rel(s1, s2)
                    significance_tests.append({
                        'model_a': n1,
                        'model_b': n2,
                        't_statistic': round(float(t_stat), 4),
                        'p_value': round(float(p_value), 4),
                        'significant': p_value < 0.05,
                    })

        return {
            'models': results,
            'best_model': best_model['name'],
            'significance_tests': significance_tests,
        }

    # ------------------------------------------------------------------
    # Data Drift Detection
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_psi(reference: np.ndarray, current: np.ndarray, n_bins: int = 10) -> float:
        """
        Compute Population Stability Index between two distributions.

        PSI < 0.1  -> no significant drift
        PSI 0.1-0.25 -> moderate drift
        PSI > 0.25 -> significant drift
        """
        # Bin edges from reference distribution
        eps = 1e-6
        edges = np.percentile(reference, np.linspace(0, 100, n_bins + 1))
        # Ensure unique edges
        edges = np.unique(edges)
        if len(edges) < 2:
            return 0.0

        ref_counts, _ = np.histogram(reference, bins=edges)
        cur_counts, _ = np.histogram(current, bins=edges)

        # Normalize to proportions
        ref_pct = (ref_counts + eps) / (ref_counts.sum() + eps * len(ref_counts))
        cur_pct = (cur_counts + eps) / (cur_counts.sum() + eps * len(cur_counts))

        psi = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
        return max(psi, 0.0)  # PSI is non-negative

    async def check_data_drift(
        self, pool, window_days: int = 30
    ) -> dict:
        """
        Detect data drift using Population Stability Index (PSI).

        Compares feature distributions of tenders from the last `window_days`
        against the reference training data (all older tenders).

        PSI > 0.1  = moderate drift
        PSI > 0.25 = significant drift

        Returns:
            {features: [{name, psi, drift_level}], overall_drift,
             drift_level, should_retrain, checked_at}
        """
        logger.info(f"Checking data drift (window={window_days} days)...")

        cutoff_date = datetime.utcnow() - timedelta(days=window_days)

        async with pool.acquire() as conn:
            # Get recent tender IDs
            recent_rows = await conn.fetch("""
                SELECT tender_id FROM tenders
                WHERE status IN ('awarded', 'closed', 'completed')
                  AND COALESCE(publication_date, created_at) >= $1
                ORDER BY RANDOM()
                LIMIT 1000
            """, cutoff_date)
            recent_ids = [r['tender_id'] for r in recent_rows]

            # Get reference (older) tender IDs
            reference_rows = await conn.fetch("""
                SELECT tender_id FROM tenders
                WHERE status IN ('awarded', 'closed', 'completed')
                  AND COALESCE(publication_date, created_at) < $1
                ORDER BY RANDOM()
                LIMIT 2000
            """, cutoff_date)
            reference_ids = [r['tender_id'] for r in reference_rows]

        if len(recent_ids) < 50 or len(reference_ids) < 50:
            logger.warning("Not enough data for drift analysis")
            return {
                'features': [],
                'overall_drift': 0.0,
                'drift_level': 'insufficient_data',
                'should_retrain': False,
                'checked_at': datetime.utcnow().isoformat(),
                'recent_count': len(recent_ids),
                'reference_count': len(reference_ids),
            }

        # Extract features for both populations
        extractor = FeatureExtractor(pool)
        feature_names = extractor.feature_names

        async def _extract_batch(ids: List[str]) -> np.ndarray:
            features_list = []
            for tid in ids:
                try:
                    fv = await extractor.extract_features(tid, include_metadata=False)
                    features_list.append(fv.feature_array)
                except Exception:
                    pass
            if not features_list:
                return np.array([])
            arr = np.array(features_list)
            return np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        ref_features = await _extract_batch(reference_ids)
        cur_features = await _extract_batch(recent_ids)

        if ref_features.size == 0 or cur_features.size == 0:
            return {
                'features': [],
                'overall_drift': 0.0,
                'drift_level': 'insufficient_data',
                'should_retrain': False,
                'checked_at': datetime.utcnow().isoformat(),
            }

        # Compute PSI per feature
        feature_drift = []
        psi_values = {}
        for i, name in enumerate(feature_names):
            if i >= ref_features.shape[1] or i >= cur_features.shape[1]:
                break

            ref_col = ref_features[:, i]
            cur_col = cur_features[:, i]

            # Skip constant features
            if np.std(ref_col) < 1e-10 and np.std(cur_col) < 1e-10:
                psi = 0.0
            else:
                psi = self._compute_psi(ref_col, cur_col)

            if psi > 0.25:
                level = 'significant'
            elif psi > 0.1:
                level = 'moderate'
            else:
                level = 'none'

            psi_values[name] = round(psi, 4)
            feature_drift.append({
                'name': name,
                'psi': round(psi, 4),
                'drift_level': level,
            })

        overall_psi = float(np.mean(list(psi_values.values()))) if psi_values else 0.0
        if overall_psi > 0.25:
            overall_level = 'significant'
        elif overall_psi > 0.1:
            overall_level = 'moderate'
        else:
            overall_level = 'none'

        should_retrain = overall_psi > 0.1 or any(
            f['psi'] > 0.25 for f in feature_drift
        )

        # Sort by PSI descending (most drifted first)
        feature_drift.sort(key=lambda f: f['psi'], reverse=True)

        result = {
            'features': feature_drift[:30],  # top 30 drifted features
            'overall_drift': round(overall_psi, 4),
            'drift_level': overall_level,
            'should_retrain': should_retrain,
            'checked_at': datetime.utcnow().isoformat(),
            'recent_count': len(recent_ids),
            'reference_count': len(reference_ids),
        }

        # Log to database
        try:
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO data_drift_log
                        (feature_psi, overall_drift, drift_level, should_retrain)
                    VALUES ($1::jsonb, $2, $3, $4)
                """,
                    json.dumps(psi_values),
                    round(overall_psi, 4),
                    overall_level,
                    should_retrain,
                )
        except Exception as e:
            logger.warning(f"Failed to persist drift log: {e}")

        logger.info(
            f"Drift check complete: overall PSI = {overall_psi:.4f} ({overall_level}), "
            f"retrain recommended = {should_retrain}"
        )
        return result

    # ------------------------------------------------------------------
    # Retrain Recommendation
    # ------------------------------------------------------------------

    async def should_retrain(self, pool) -> dict:
        """
        Check if retraining is needed based on:
        1. Data drift (PSI > 0.1 on key features)
        2. New labeled data (50+ new reviews since last training)
        3. Time since last training (> 30 days)

        Returns:
            {should_retrain, reasons, urgency}
        """
        reasons = []
        urgency = 'low'

        async with pool.acquire() as conn:
            # 1. Check latest drift log
            drift_row = await conn.fetchrow("""
                SELECT overall_drift, drift_level, should_retrain, checked_at
                FROM data_drift_log
                ORDER BY checked_at DESC
                LIMIT 1
            """)
            if drift_row and drift_row['should_retrain']:
                drift_level = drift_row['drift_level']
                reasons.append(
                    f"Data drift detected: {drift_level} "
                    f"(PSI = {drift_row['overall_drift']:.4f})"
                )
                if drift_level == 'significant':
                    urgency = 'high'
                elif drift_level == 'moderate':
                    urgency = max(urgency, 'medium', key=['low', 'medium', 'high'].index)

            # 2. Check new labeled data since last model training
            last_model = await conn.fetchrow("""
                SELECT created_at FROM model_registry
                WHERE is_active = TRUE
                ORDER BY created_at DESC
                LIMIT 1
            """)
            last_training_date = (
                last_model['created_at'] if last_model else datetime(2020, 1, 1)
            )

            new_reviews_count = await conn.fetchval("""
                SELECT COUNT(*) FROM corruption_flags
                WHERE reviewed = TRUE
                  AND reviewed_at > $1
            """, last_training_date)
            if new_reviews_count and new_reviews_count >= 50:
                reasons.append(
                    f"{new_reviews_count} new reviewed flags since last training"
                )
                urgency = max(urgency, 'medium', key=['low', 'medium', 'high'].index)

            # 3. Check time since last training
            days_since = (datetime.utcnow() - last_training_date).days
            if days_since > 30:
                reasons.append(f"{days_since} days since last model training")
                if days_since > 60:
                    urgency = max(urgency, 'high', key=['low', 'medium', 'high'].index)
                else:
                    urgency = max(urgency, 'medium', key=['low', 'medium', 'high'].index)

        should = len(reasons) > 0
        return {
            'should_retrain': should,
            'reasons': reasons,
            'urgency': urgency,
            'last_training': last_training_date.isoformat() if last_model else None,
            'days_since_training': days_since,
            'new_reviews': new_reviews_count or 0,
        }
