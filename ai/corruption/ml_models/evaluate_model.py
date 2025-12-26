#!/usr/bin/env python3
"""
Model Evaluation Script for Corruption Detection Models

This script provides comprehensive evaluation of trained corruption detection
models including:

1. Load saved model and preprocessing artifacts
2. Evaluate on test set with multiple metrics
3. Generate ROC and Precision-Recall curves
4. Analyze feature importance
5. Produce threshold analysis
6. Create human-readable evaluation report

Usage:
    python evaluate_model.py --model-path ./models/corruption_rf_20251226.joblib

Author: NabavkiData
License: Proprietary
"""

import os
import sys
import json
import asyncio
import logging
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
import pickle
import warnings
warnings.filterwarnings('ignore')

import numpy as np
import pandas as pd
import joblib

from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    average_precision_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    roc_curve,
    matthews_corrcoef,
    balanced_accuracy_score,
    log_loss
)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ai.corruption.ml_models.random_forest import CorruptionRandomForest

logger = logging.getLogger(__name__)


class ModelEvaluator:
    """
    Comprehensive evaluation for corruption detection models.

    This class provides:
    - Standard classification metrics (accuracy, precision, recall, F1, AUC-ROC)
    - Threshold analysis and optimal threshold selection
    - Feature importance analysis
    - Per-class performance breakdown
    - Detailed evaluation reports
    """

    def __init__(self, model_path: str):
        """
        Initialize evaluator with a trained model.

        Args:
            model_path: Path to saved model (.joblib file)
        """
        self.model_path = Path(model_path)
        self.model: Optional[CorruptionRandomForest] = None
        self.preprocessing: Optional[Dict] = None
        self.feature_names: Optional[List[str]] = None

        self._load_model()

    def _load_model(self):
        """Load model and preprocessing artifacts."""
        logger.info(f"Loading model from {self.model_path}")

        # Load model
        self.model = CorruptionRandomForest.load(str(self.model_path).replace('.joblib', ''))

        # Load preprocessing
        preprocessing_path = str(self.model_path).replace('.joblib', '_preprocessing.pkl')
        if os.path.exists(preprocessing_path):
            with open(preprocessing_path, 'rb') as f:
                self.preprocessing = pickle.load(f)
                self.feature_names = self.preprocessing.get('feature_names')
        else:
            logger.warning(f"Preprocessing file not found: {preprocessing_path}")
            self.feature_names = self.model.feature_names

        logger.info(f"Model loaded. Features: {len(self.feature_names) if self.feature_names else 'unknown'}")

    def preprocess(self, X: np.ndarray) -> np.ndarray:
        """
        Apply preprocessing to features.

        Args:
            X: Raw features

        Returns:
            Preprocessed features
        """
        if self.preprocessing is None:
            logger.warning("No preprocessing available, returning raw features")
            return X

        # Replace infinities
        X = np.where(np.isinf(X), np.nan, X)

        # Impute missing values
        if 'imputer' in self.preprocessing and self.preprocessing['imputer'] is not None:
            X = self.preprocessing['imputer'].transform(X)

        # Scale features
        if 'scaler' in self.preprocessing and self.preprocessing['scaler'] is not None:
            X = self.preprocessing['scaler'].transform(X)

        return X

    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        y_proba: np.ndarray
    ) -> Dict[str, float]:
        """
        Compute comprehensive classification metrics.

        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_proba: Predicted probabilities for positive class

        Returns:
            Dictionary of metrics
        """
        metrics = {
            # Standard metrics
            'accuracy': accuracy_score(y_true, y_pred),
            'balanced_accuracy': balanced_accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),

            # Probability-based metrics
            'roc_auc': roc_auc_score(y_true, y_proba),
            'average_precision': average_precision_score(y_true, y_proba),
            'log_loss': log_loss(y_true, y_proba),

            # Additional metrics
            'matthews_corrcoef': matthews_corrcoef(y_true, y_pred),

            # Class-specific metrics
            'specificity': recall_score(y_true, y_pred, pos_label=0, zero_division=0),
            'negative_predictive_value': precision_score(y_true, y_pred, pos_label=0, zero_division=0),
        }

        # Confusion matrix values
        tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
        metrics['true_positives'] = int(tp)
        metrics['true_negatives'] = int(tn)
        metrics['false_positives'] = int(fp)
        metrics['false_negatives'] = int(fn)

        # Rates
        metrics['false_positive_rate'] = fp / (fp + tn) if (fp + tn) > 0 else 0
        metrics['false_negative_rate'] = fn / (fn + tp) if (fn + tp) > 0 else 0

        return metrics

    def threshold_analysis(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        thresholds: Optional[np.ndarray] = None
    ) -> pd.DataFrame:
        """
        Analyze model performance at different decision thresholds.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            thresholds: Thresholds to evaluate (default: 0.1 to 0.9)

        Returns:
            DataFrame with metrics at each threshold
        """
        if thresholds is None:
            thresholds = np.arange(0.1, 1.0, 0.05)

        results = []
        for threshold in thresholds:
            y_pred = (y_proba >= threshold).astype(int)
            metrics = self.compute_metrics(y_true, y_pred, y_proba)
            metrics['threshold'] = threshold
            results.append(metrics)

        df = pd.DataFrame(results)
        df = df[['threshold', 'precision', 'recall', 'f1', 'accuracy',
                 'specificity', 'false_positive_rate', 'false_negative_rate']]

        return df

    def find_optimal_threshold(
        self,
        y_true: np.ndarray,
        y_proba: np.ndarray,
        metric: str = 'f1'
    ) -> Tuple[float, float]:
        """
        Find optimal classification threshold for a given metric.

        Args:
            y_true: True labels
            y_proba: Predicted probabilities
            metric: Metric to optimize ('f1', 'precision', 'recall', 'balanced_accuracy')

        Returns:
            Tuple of (optimal_threshold, best_score)
        """
        precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)

        best_threshold = 0.5
        best_score = 0.0

        for i, threshold in enumerate(thresholds):
            y_pred = (y_proba >= threshold).astype(int)

            if metric == 'f1':
                if precisions[i] + recalls[i] > 0:
                    score = 2 * precisions[i] * recalls[i] / (precisions[i] + recalls[i])
                else:
                    score = 0
            elif metric == 'precision':
                score = precisions[i]
            elif metric == 'recall':
                score = recalls[i]
            elif metric == 'balanced_accuracy':
                score = balanced_accuracy_score(y_true, y_pred)
            else:
                score = f1_score(y_true, y_pred, zero_division=0)

            if score > best_score:
                best_score = score
                best_threshold = threshold

        return best_threshold, best_score

    def analyze_feature_importance(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> pd.DataFrame:
        """
        Analyze feature importance using both MDI and permutation methods.

        Args:
            X: Features (preprocessed)
            y: True labels

        Returns:
            DataFrame with feature importance scores
        """
        importance = self.model.get_feature_importance(
            feature_names=self.feature_names,
            X=X,
            y=y,
            compute_permutation=True,
            n_repeats=10
        )

        return importance.to_dataframe()

    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        preprocess: bool = True
    ) -> Dict[str, Any]:
        """
        Perform comprehensive model evaluation.

        Args:
            X: Features
            y: True labels
            preprocess: Whether to apply preprocessing

        Returns:
            Evaluation report dictionary
        """
        logger.info("Starting comprehensive model evaluation...")

        if preprocess:
            X = self.preprocess(X)

        # Get predictions
        y_pred = self.model.predict(X)
        y_proba = self.model.predict_proba(X)[:, 1]

        # Compute metrics at default threshold
        metrics = self.compute_metrics(y, y_pred, y_proba)

        # Threshold analysis
        threshold_df = self.threshold_analysis(y, y_proba)

        # Find optimal thresholds
        optimal_f1_threshold, optimal_f1 = self.find_optimal_threshold(y, y_proba, 'f1')
        optimal_precision_threshold, optimal_precision = self.find_optimal_threshold(y, y_proba, 'precision')
        optimal_recall_threshold, optimal_recall = self.find_optimal_threshold(y, y_proba, 'recall')

        # Classification report
        class_report = classification_report(y, y_pred, target_names=['Clean', 'Flagged'], output_dict=True)

        # Feature importance
        importance_df = self.analyze_feature_importance(X, y)

        # Build evaluation report
        report = {
            'timestamp': datetime.utcnow().isoformat(),
            'model_path': str(self.model_path),
            'dataset': {
                'total_samples': len(y),
                'positive_samples': int(y.sum()),
                'negative_samples': int((~y.astype(bool)).sum()),
                'positive_rate': float(y.mean())
            },
            'metrics': metrics,
            'optimal_thresholds': {
                'f1': {'threshold': optimal_f1_threshold, 'score': optimal_f1},
                'precision': {'threshold': optimal_precision_threshold, 'score': optimal_precision},
                'recall': {'threshold': optimal_recall_threshold, 'score': optimal_recall}
            },
            'threshold_analysis': threshold_df.to_dict('records'),
            'classification_report': class_report,
            'feature_importance': {
                'top_10_mdi': importance_df.head(10)[['feature', 'mdi_importance']].to_dict('records'),
                'top_10_permutation': importance_df.sort_values(
                    'permutation_importance', ascending=False
                ).head(10)[['feature', 'permutation_importance']].to_dict('records')
                if 'permutation_importance' in importance_df.columns else None
            },
            'confusion_matrix': confusion_matrix(y, y_pred).tolist()
        }

        return report

    def print_report(self, report: Dict[str, Any]):
        """
        Print a formatted evaluation report.

        Args:
            report: Evaluation report dictionary
        """
        print("\n" + "=" * 70)
        print("CORRUPTION DETECTION MODEL EVALUATION REPORT")
        print("=" * 70)

        print(f"\nModel: {report['model_path']}")
        print(f"Evaluated at: {report['timestamp']}")

        print("\n" + "-" * 40)
        print("DATASET SUMMARY")
        print("-" * 40)
        ds = report['dataset']
        print(f"Total samples:    {ds['total_samples']:,}")
        print(f"Positive samples: {ds['positive_samples']:,} ({ds['positive_rate']*100:.1f}%)")
        print(f"Negative samples: {ds['negative_samples']:,}")

        print("\n" + "-" * 40)
        print("CLASSIFICATION METRICS (threshold=0.5)")
        print("-" * 40)
        m = report['metrics']
        print(f"Accuracy:             {m['accuracy']:.4f}")
        print(f"Balanced Accuracy:    {m['balanced_accuracy']:.4f}")
        print(f"Precision:            {m['precision']:.4f}")
        print(f"Recall (Sensitivity): {m['recall']:.4f}")
        print(f"Specificity:          {m['specificity']:.4f}")
        print(f"F1 Score:             {m['f1']:.4f}")
        print(f"ROC-AUC:              {m['roc_auc']:.4f}")
        print(f"Average Precision:    {m['average_precision']:.4f}")
        print(f"Matthews Corr. Coef:  {m['matthews_corrcoef']:.4f}")
        print(f"Log Loss:             {m['log_loss']:.4f}")

        print("\n" + "-" * 40)
        print("CONFUSION MATRIX")
        print("-" * 40)
        cm = report['confusion_matrix']
        print(f"                  Predicted")
        print(f"               Clean   Flagged")
        print(f"Actual Clean  {cm[0][0]:>6}   {cm[0][1]:>6}")
        print(f"Actual Flagged{cm[1][0]:>6}   {cm[1][1]:>6}")
        print(f"\nTrue Positives:  {m['true_positives']}")
        print(f"True Negatives:  {m['true_negatives']}")
        print(f"False Positives: {m['false_positives']} (Type I Error)")
        print(f"False Negatives: {m['false_negatives']} (Type II Error)")

        print("\n" + "-" * 40)
        print("OPTIMAL THRESHOLDS")
        print("-" * 40)
        ot = report['optimal_thresholds']
        print(f"For max F1 Score:   threshold={ot['f1']['threshold']:.3f}, F1={ot['f1']['score']:.4f}")
        print(f"For max Precision:  threshold={ot['precision']['threshold']:.3f}, precision={ot['precision']['score']:.4f}")
        print(f"For max Recall:     threshold={ot['recall']['threshold']:.3f}, recall={ot['recall']['score']:.4f}")

        print("\n" + "-" * 40)
        print("TOP 10 MOST IMPORTANT FEATURES (MDI)")
        print("-" * 40)
        for i, feat in enumerate(report['feature_importance']['top_10_mdi'], 1):
            print(f"{i:2}. {feat['feature']:<35} {feat['mdi_importance']:.4f}")

        if report['feature_importance']['top_10_permutation']:
            print("\n" + "-" * 40)
            print("TOP 10 MOST IMPORTANT FEATURES (Permutation)")
            print("-" * 40)
            for i, feat in enumerate(report['feature_importance']['top_10_permutation'], 1):
                print(f"{i:2}. {feat['feature']:<35} {feat['permutation_importance']:.4f}")

        print("\n" + "-" * 40)
        print("PER-CLASS METRICS")
        print("-" * 40)
        cr = report['classification_report']
        print(f"{'Class':<12} {'Precision':>10} {'Recall':>10} {'F1-Score':>10} {'Support':>10}")
        print("-" * 52)
        for cls in ['Clean', 'Flagged']:
            c = cr[cls]
            print(f"{cls:<12} {c['precision']:>10.4f} {c['recall']:>10.4f} {c['f1-score']:>10.4f} {c['support']:>10.0f}")
        print("-" * 52)
        w = cr['weighted avg']
        print(f"{'Weighted Avg':<12} {w['precision']:>10.4f} {w['recall']:>10.4f} {w['f1-score']:>10.4f} {w['support']:>10.0f}")

        print("\n" + "=" * 70)
        print("EVALUATION COMPLETE")
        print("=" * 70)


async def evaluate_from_database(
    model_path: str,
    limit: Optional[int] = None,
    output_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Evaluate model on data from database.

    Args:
        model_path: Path to saved model
        limit: Maximum samples to use
        output_path: Path to save evaluation report

    Returns:
        Evaluation report dictionary
    """
    from ai.corruption.ml_models.training_data import (
        TrainingDataExtractor,
        create_connection_pool
    )
    from sklearn.model_selection import train_test_split

    logger.info("Loading test data from database...")

    # Create evaluator
    evaluator = ModelEvaluator(model_path)

    # Get data
    pool = await create_connection_pool()

    try:
        extractor = TrainingDataExtractor(pool)

        # Get flagged and clean tenders
        flagged_ids = await extractor.get_flagged_tenders(min_flags=1, limit=limit)
        clean_ids = await extractor.get_clean_tenders(len(flagged_ids), exclude_tender_ids=flagged_ids)

        # Combine
        all_ids = flagged_ids + clean_ids
        y = np.array([1] * len(flagged_ids) + [0] * len(clean_ids))

        # Extract features
        X, _, successful_ids = await extractor.extract_features_for_tenders(all_ids)

        # Filter labels
        id_to_label = dict(zip(all_ids, y))
        y = np.array([id_to_label[tid] for tid in successful_ids])

        # Use 20% for testing (simulate held-out test set)
        _, X_test, _, y_test = train_test_split(
            X, y,
            test_size=0.2,
            stratify=y,
            random_state=42
        )

        logger.info(f"Evaluating on {len(y_test)} test samples...")

    finally:
        await pool.close()

    # Evaluate
    report = evaluator.evaluate(X_test, y_test, preprocess=True)
    evaluator.print_report(report)

    # Save report
    if output_path:
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        logger.info(f"Report saved to: {output_path}")

    return report


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Evaluate corruption detection model")
    parser.add_argument('--model-path', type=str, required=True,
                       help='Path to saved model (.joblib file)')
    parser.add_argument('--limit', type=int, default=None,
                       help='Maximum samples to use')
    parser.add_argument('--output', type=str, default=None,
                       help='Path to save evaluation report (JSON)')
    parser.add_argument('--verbose', action='store_true',
                       help='Verbose logging')

    args = parser.parse_args()

    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    report = await evaluate_from_database(
        model_path=args.model_path,
        limit=args.limit,
        output_path=args.output
    )

    return report


if __name__ == '__main__':
    asyncio.run(main())
