"""
Random Forest Classifier for Corruption Detection

This module provides a Random Forest implementation optimized for detecting
procurement corruption patterns. Features include:

- Stratified K-Fold cross-validation
- GridSearchCV hyperparameter tuning
- Feature importance extraction (MDI, permutation)
- Prediction with confidence scores
- Model persistence (save/load)
- Class imbalance handling

The Random Forest serves as a robust baseline model and performs well on
tabular data with mixed feature types.

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import pandas as pd
import logging
import joblib
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime

from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import (
    StratifiedKFold,
    GridSearchCV,
    cross_val_score,
    cross_val_predict
)
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    roc_auc_score,
    classification_report,
    confusion_matrix,
    precision_recall_curve,
    average_precision_score
)
from sklearn.inspection import permutation_importance

logger = logging.getLogger(__name__)


@dataclass
class ModelMetrics:
    """Container for model evaluation metrics."""
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    average_precision: float
    confusion_matrix: np.ndarray
    classification_report: str
    cv_scores: Optional[np.ndarray] = None
    cv_mean: Optional[float] = None
    cv_std: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1': self.f1,
            'roc_auc': self.roc_auc,
            'average_precision': self.average_precision,
            'confusion_matrix': self.confusion_matrix.tolist(),
            'classification_report': self.classification_report,
            'cv_scores': self.cv_scores.tolist() if self.cv_scores is not None else None,
            'cv_mean': self.cv_mean,
            'cv_std': self.cv_std
        }


@dataclass
class FeatureImportance:
    """Container for feature importance scores."""
    feature_names: List[str]
    mdi_importance: np.ndarray  # Mean Decrease Impurity
    permutation_importance: Optional[np.ndarray] = None
    permutation_std: Optional[np.ndarray] = None

    def get_top_features(self, n: int = 20, method: str = 'mdi') -> List[Tuple[str, float]]:
        """Get top N most important features."""
        if method == 'mdi':
            importance = self.mdi_importance
        elif method == 'permutation' and self.permutation_importance is not None:
            importance = self.permutation_importance
        else:
            importance = self.mdi_importance

        indices = np.argsort(importance)[::-1][:n]
        return [(self.feature_names[i], importance[i]) for i in indices]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        data = {
            'feature': self.feature_names,
            'mdi_importance': self.mdi_importance
        }
        if self.permutation_importance is not None:
            data['permutation_importance'] = self.permutation_importance
            data['permutation_std'] = self.permutation_std

        df = pd.DataFrame(data)
        return df.sort_values('mdi_importance', ascending=False).reset_index(drop=True)


class CorruptionRandomForest:
    """
    Random Forest classifier for procurement corruption detection.

    This class implements:
    - Training with class imbalance handling
    - Stratified cross-validation
    - Hyperparameter tuning with GridSearchCV
    - Multiple feature importance methods
    - Prediction with probability/confidence scores
    - Model persistence

    Example usage:
        from training_data import extract_training_data

        # Prepare data
        dataset = await extract_training_data()

        # Train model
        rf = CorruptionRandomForest()
        rf.fit(dataset.X_train, dataset.y_train, dataset.class_weights)

        # Evaluate
        metrics = rf.evaluate(dataset.X_test, dataset.y_test)
        print(f"ROC-AUC: {metrics.roc_auc:.4f}")

        # Predict
        proba = rf.predict_proba(X_new)

        # Feature importance
        importance = rf.get_feature_importance(dataset.feature_names)
        top_features = importance.get_top_features(10)

        # Save model
        rf.save("corruption_rf_v1.joblib")
    """

    def __init__(
        self,
        n_estimators: int = 200,
        max_depth: Optional[int] = None,
        min_samples_split: int = 5,
        min_samples_leaf: int = 2,
        max_features: str = 'sqrt',
        class_weight: Optional[Union[str, Dict]] = 'balanced',
        n_jobs: int = -1,
        random_state: int = 42,
        verbose: int = 0
    ):
        """
        Initialize Random Forest classifier.

        Args:
            n_estimators: Number of trees in the forest
            max_depth: Maximum depth of trees (None = unlimited)
            min_samples_split: Minimum samples required to split node
            min_samples_leaf: Minimum samples required at leaf node
            max_features: Number of features for best split ('sqrt', 'log2', or float)
            class_weight: Weights for classes ('balanced', 'balanced_subsample', or dict)
            n_jobs: Number of parallel jobs (-1 = all CPUs)
            random_state: Random seed for reproducibility
            verbose: Verbosity level
        """
        self.model = RandomForestClassifier(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            max_features=max_features,
            class_weight=class_weight,
            n_jobs=n_jobs,
            random_state=random_state,
            verbose=verbose,
            oob_score=True  # Enable out-of-bag score
        )

        self.is_fitted = False
        self.feature_names: Optional[List[str]] = None
        self.training_metadata: Dict[str, Any] = {}

        logger.info(
            f"CorruptionRandomForest initialized with "
            f"n_estimators={n_estimators}, max_depth={max_depth}"
        )

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        class_weights: Optional[Dict[int, float]] = None,
        feature_names: Optional[List[str]] = None
    ) -> 'CorruptionRandomForest':
        """
        Train the Random Forest model.

        Args:
            X: Training features (n_samples, n_features)
            y: Training labels (n_samples,)
            class_weights: Optional class weights dict
            feature_names: Optional feature names

        Returns:
            self
        """
        logger.info(f"Training Random Forest on {X.shape[0]} samples, {X.shape[1]} features")

        # Update class weights if provided
        if class_weights is not None:
            self.model.class_weight = class_weights

        # Fit model
        start_time = datetime.utcnow()
        self.model.fit(X, y)
        training_time = (datetime.utcnow() - start_time).total_seconds()

        self.is_fitted = True
        self.feature_names = feature_names

        # Store training metadata
        self.training_metadata = {
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'n_positive': int(y.sum()),
            'n_negative': int((~y.astype(bool)).sum()),
            'oob_score': self.model.oob_score_,
            'training_time_seconds': training_time,
            'trained_at': datetime.utcnow().isoformat()
        }

        logger.info(
            f"Training completed in {training_time:.2f}s, "
            f"OOB score: {self.model.oob_score_:.4f}"
        )

        return self

    def fit_with_cv(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
        class_weights: Optional[Dict[int, float]] = None,
        feature_names: Optional[List[str]] = None,
        scoring: str = 'roc_auc'
    ) -> Tuple['CorruptionRandomForest', np.ndarray]:
        """
        Train with stratified cross-validation and return CV scores.

        Args:
            X: Training features
            y: Training labels
            n_folds: Number of CV folds
            class_weights: Optional class weights
            feature_names: Optional feature names
            scoring: Scoring metric for CV

        Returns:
            Tuple of (fitted model, cv_scores)
        """
        logger.info(f"Training with {n_folds}-fold stratified cross-validation")

        if class_weights is not None:
            self.model.class_weight = class_weights

        # Perform cross-validation
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self.model, X, y, cv=cv, scoring=scoring, n_jobs=-1)

        logger.info(f"CV {scoring}: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")

        # Fit on full training data
        self.fit(X, y, class_weights, feature_names)

        # Store CV results
        self.training_metadata['cv_scores'] = cv_scores.tolist()
        self.training_metadata['cv_mean'] = float(cv_scores.mean())
        self.training_metadata['cv_std'] = float(cv_scores.std())
        self.training_metadata['cv_folds'] = n_folds

        return self, cv_scores

    def hyperparameter_tune(
        self,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Optional[Dict[str, List]] = None,
        n_folds: int = 5,
        scoring: str = 'roc_auc',
        n_jobs: int = -1
    ) -> Tuple['CorruptionRandomForest', Dict[str, Any]]:
        """
        Perform hyperparameter tuning with GridSearchCV.

        Args:
            X: Training features
            y: Training labels
            param_grid: Parameter grid (uses default if None)
            n_folds: Number of CV folds
            scoring: Scoring metric
            n_jobs: Number of parallel jobs

        Returns:
            Tuple of (best model, best parameters)
        """
        if param_grid is None:
            # Default parameter grid optimized for corruption detection
            param_grid = {
                'n_estimators': [100, 200, 300],
                'max_depth': [10, 20, 30, None],
                'min_samples_split': [2, 5, 10],
                'min_samples_leaf': [1, 2, 4],
                'max_features': ['sqrt', 'log2', 0.3]
            }

        logger.info(f"Starting hyperparameter tuning with {n_folds}-fold CV...")

        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        grid_search = GridSearchCV(
            self.model,
            param_grid,
            cv=cv,
            scoring=scoring,
            n_jobs=n_jobs,
            verbose=1,
            refit=True
        )

        start_time = datetime.utcnow()
        grid_search.fit(X, y)
        search_time = (datetime.utcnow() - start_time).total_seconds()

        # Update model with best estimator
        self.model = grid_search.best_estimator_
        self.is_fitted = True

        best_params = grid_search.best_params_
        best_score = grid_search.best_score_

        self.training_metadata['hyperparameter_tuning'] = {
            'best_params': best_params,
            'best_score': best_score,
            'search_time_seconds': search_time,
            'cv_results': {
                'mean_test_score': grid_search.cv_results_['mean_test_score'].tolist(),
                'std_test_score': grid_search.cv_results_['std_test_score'].tolist()
            }
        }

        logger.info(
            f"Best {scoring}: {best_score:.4f}, "
            f"Best params: {best_params}, "
            f"Search time: {search_time:.1f}s"
        )

        return self, best_params

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels.

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Predicted labels (n_samples,)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        return self.model.predict(X)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class probabilities.

        Args:
            X: Features (n_samples, n_features)

        Returns:
            Class probabilities (n_samples, 2) for [not corrupt, corrupt]
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")
        return self.model.predict_proba(X)

    def predict_with_confidence(
        self,
        X: np.ndarray,
        threshold: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Predict with confidence scores and custom threshold.

        Args:
            X: Features (n_samples, n_features)
            threshold: Classification threshold (default 0.5)

        Returns:
            List of dicts with 'prediction', 'confidence', 'probability'
        """
        probas = self.predict_proba(X)

        results = []
        for proba in probas:
            prob_corrupt = proba[1]
            prediction = 1 if prob_corrupt >= threshold else 0
            confidence = max(proba)  # Confidence is max of class probabilities

            results.append({
                'prediction': prediction,
                'probability': float(prob_corrupt),
                'confidence': float(confidence),
                'threshold': threshold
            })

        return results

    def evaluate(
        self,
        X: np.ndarray,
        y: np.ndarray,
        compute_cv: bool = False,
        n_folds: int = 5
    ) -> ModelMetrics:
        """
        Evaluate model on test data.

        Args:
            X: Test features
            y: True labels
            compute_cv: Whether to compute CV scores
            n_folds: Number of CV folds if compute_cv

        Returns:
            ModelMetrics with evaluation results
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)[:, 1]

        # Compute metrics
        accuracy = accuracy_score(y, y_pred)
        precision = precision_score(y, y_pred, zero_division=0)
        recall = recall_score(y, y_pred, zero_division=0)
        f1 = f1_score(y, y_pred, zero_division=0)
        roc_auc = roc_auc_score(y, y_proba)
        avg_precision = average_precision_score(y, y_proba)
        conf_matrix = confusion_matrix(y, y_pred)
        class_report = classification_report(y, y_pred, target_names=['Clean', 'Flagged'])

        # Optional CV scores
        cv_scores = None
        cv_mean = None
        cv_std = None

        if compute_cv:
            cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
            cv_scores = cross_val_score(self.model, X, y, cv=cv, scoring='roc_auc')
            cv_mean = float(cv_scores.mean())
            cv_std = float(cv_scores.std())

        metrics = ModelMetrics(
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1=f1,
            roc_auc=roc_auc,
            average_precision=avg_precision,
            confusion_matrix=conf_matrix,
            classification_report=class_report,
            cv_scores=cv_scores,
            cv_mean=cv_mean,
            cv_std=cv_std
        )

        logger.info(
            f"Evaluation: Accuracy={accuracy:.4f}, Precision={precision:.4f}, "
            f"Recall={recall:.4f}, F1={f1:.4f}, ROC-AUC={roc_auc:.4f}"
        )

        return metrics

    def get_feature_importance(
        self,
        feature_names: Optional[List[str]] = None,
        X: Optional[np.ndarray] = None,
        y: Optional[np.ndarray] = None,
        compute_permutation: bool = False,
        n_repeats: int = 10
    ) -> FeatureImportance:
        """
        Get feature importance scores.

        Args:
            feature_names: Feature names (uses stored if None)
            X: Optional data for permutation importance
            y: Optional labels for permutation importance
            compute_permutation: Whether to compute permutation importance
            n_repeats: Number of repeats for permutation importance

        Returns:
            FeatureImportance with MDI and optionally permutation importance
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        names = feature_names or self.feature_names
        if names is None:
            names = [f"feature_{i}" for i in range(len(self.model.feature_importances_))]

        # Mean Decrease Impurity (Gini importance)
        mdi_importance = self.model.feature_importances_

        # Optional permutation importance
        perm_importance = None
        perm_std = None

        if compute_permutation and X is not None and y is not None:
            logger.info(f"Computing permutation importance with {n_repeats} repeats...")
            perm_result = permutation_importance(
                self.model, X, y,
                n_repeats=n_repeats,
                random_state=42,
                n_jobs=-1
            )
            perm_importance = perm_result.importances_mean
            perm_std = perm_result.importances_std

        return FeatureImportance(
            feature_names=names,
            mdi_importance=mdi_importance,
            permutation_importance=perm_importance,
            permutation_std=perm_std
        )

    def get_optimal_threshold(
        self,
        X: np.ndarray,
        y: np.ndarray,
        metric: str = 'f1'
    ) -> Tuple[float, float]:
        """
        Find optimal classification threshold.

        Args:
            X: Validation features
            y: True labels
            metric: Metric to optimize ('f1', 'precision', 'recall')

        Returns:
            Tuple of (optimal_threshold, best_score)
        """
        y_proba = self.predict_proba(X)[:, 1]

        precisions, recalls, thresholds = precision_recall_curve(y, y_proba)

        best_threshold = 0.5
        best_score = 0.0

        for i, threshold in enumerate(thresholds):
            if metric == 'f1':
                if precisions[i] + recalls[i] > 0:
                    score = 2 * precisions[i] * recalls[i] / (precisions[i] + recalls[i])
                else:
                    score = 0
            elif metric == 'precision':
                score = precisions[i]
            elif metric == 'recall':
                score = recalls[i]
            else:
                raise ValueError(f"Unknown metric: {metric}")

            if score > best_score:
                best_score = score
                best_threshold = threshold

        logger.info(f"Optimal threshold for {metric}: {best_threshold:.4f} (score: {best_score:.4f})")
        return best_threshold, best_score

    def save(self, filepath: str) -> None:
        """
        Save model to disk.

        Args:
            filepath: Path to save model (will add .joblib extension)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Cannot save unfitted model.")

        if not filepath.endswith('.joblib'):
            filepath = filepath + '.joblib'

        # Save model and metadata
        save_data = {
            'model': self.model,
            'feature_names': self.feature_names,
            'training_metadata': self.training_metadata,
            'saved_at': datetime.utcnow().isoformat()
        }

        joblib.dump(save_data, filepath)

        # Also save metadata as JSON for easy inspection
        meta_path = filepath.replace('.joblib', '_metadata.json')
        with open(meta_path, 'w') as f:
            json.dump({
                'feature_names': self.feature_names,
                'training_metadata': self.training_metadata,
                'saved_at': save_data['saved_at']
            }, f, indent=2)

        logger.info(f"Model saved to {filepath}")

    @classmethod
    def load(cls, filepath: str) -> 'CorruptionRandomForest':
        """
        Load model from disk.

        Args:
            filepath: Path to saved model

        Returns:
            Loaded CorruptionRandomForest instance
        """
        if not filepath.endswith('.joblib'):
            filepath = filepath + '.joblib'

        save_data = joblib.load(filepath)

        # Create instance
        instance = cls.__new__(cls)
        instance.model = save_data['model']
        instance.feature_names = save_data['feature_names']
        instance.training_metadata = save_data['training_metadata']
        instance.is_fitted = True

        logger.info(f"Model loaded from {filepath}")
        return instance

    def get_model_summary(self) -> Dict[str, Any]:
        """Get summary of model configuration and training."""
        return {
            'model_type': 'RandomForest',
            'is_fitted': self.is_fitted,
            'n_estimators': self.model.n_estimators,
            'max_depth': self.model.max_depth,
            'min_samples_split': self.model.min_samples_split,
            'min_samples_leaf': self.model.min_samples_leaf,
            'max_features': self.model.max_features,
            'class_weight': self.model.class_weight,
            'n_features': len(self.feature_names) if self.feature_names else None,
            'training_metadata': self.training_metadata
        }


def quick_train_random_forest(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Optional[List[str]] = None,
    class_weights: Optional[Dict[int, float]] = None,
    tune_hyperparameters: bool = False
) -> Tuple[CorruptionRandomForest, ModelMetrics, FeatureImportance]:
    """
    Quick training function with evaluation and feature importance.

    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        feature_names: Optional feature names
        class_weights: Optional class weights
        tune_hyperparameters: Whether to tune hyperparameters

    Returns:
        Tuple of (model, metrics, feature_importance)
    """
    rf = CorruptionRandomForest()

    if tune_hyperparameters:
        # Use smaller grid for faster tuning
        param_grid = {
            'n_estimators': [100, 200],
            'max_depth': [10, 20, None],
            'min_samples_leaf': [1, 2]
        }
        rf.hyperparameter_tune(X_train, y_train, param_grid=param_grid)
    else:
        rf.fit_with_cv(X_train, y_train, class_weights=class_weights, feature_names=feature_names)

    metrics = rf.evaluate(X_test, y_test)
    importance = rf.get_feature_importance(
        feature_names,
        X_test, y_test,
        compute_permutation=True,
        n_repeats=5
    )

    return rf, metrics, importance


if __name__ == "__main__":
    # Example usage with synthetic data
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("Random Forest Corruption Detection Model")
    print("=" * 50)

    # Generate synthetic data for demonstration
    np.random.seed(42)
    n_samples = 1000
    n_features = 113  # Match actual feature count

    X = np.random.randn(n_samples, n_features)
    # Create synthetic labels with imbalance
    y = np.random.binomial(1, 0.3, n_samples)

    # Split
    from sklearn.model_selection import train_test_split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    feature_names = [f"feature_{i}" for i in range(n_features)]

    # Quick train
    rf, metrics, importance = quick_train_random_forest(
        X_train, y_train, X_test, y_test,
        feature_names=feature_names
    )

    print("\nModel Summary:")
    print(json.dumps(rf.get_model_summary(), indent=2, default=str))

    print("\nMetrics:")
    print(f"  ROC-AUC: {metrics.roc_auc:.4f}")
    print(f"  F1: {metrics.f1:.4f}")
    print(f"  Precision: {metrics.precision:.4f}")
    print(f"  Recall: {metrics.recall:.4f}")

    print("\nTop 10 Features (MDI):")
    for name, imp in importance.get_top_features(10, method='mdi'):
        print(f"  {name}: {imp:.4f}")

    # Save model
    rf.save("demo_rf_model")
    print("\nModel saved to demo_rf_model.joblib")

    # Load and verify
    rf_loaded = CorruptionRandomForest.load("demo_rf_model")
    print(f"Model loaded, is_fitted: {rf_loaded.is_fitted}")

    # Clean up demo files
    os.remove("demo_rf_model.joblib")
    os.remove("demo_rf_model_metadata.json")
    print("Demo files cleaned up")
