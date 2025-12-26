"""
XGBoost Classifier for Corruption Detection

This module provides an XGBoost implementation optimized for detecting
procurement corruption patterns. Features include:

- Class imbalance handling with scale_pos_weight
- Early stopping to prevent overfitting
- Multiple feature importance methods (gain, cover, weight)
- SHAP value preparation for explainability
- Prediction with confidence scores
- Model persistence (save/load)
- Hyperparameter tuning with Bayesian optimization support

XGBoost typically outperforms Random Forest on structured/tabular data and
provides better interpretability through SHAP values.

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import pandas as pd
import logging
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime

import xgboost as xgb
from sklearn.model_selection import (
    StratifiedKFold,
    cross_val_score,
    train_test_split
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

logger = logging.getLogger(__name__)


@dataclass
class XGBModelMetrics:
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
    best_iteration: Optional[int] = None

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
            'cv_std': self.cv_std,
            'best_iteration': self.best_iteration
        }


@dataclass
class XGBFeatureImportance:
    """Container for XGBoost feature importance scores."""
    feature_names: List[str]
    gain: np.ndarray      # Total gain of splits using feature
    cover: np.ndarray     # Number of samples affected by splits
    weight: np.ndarray    # Number of times feature is used in splits

    def get_top_features(
        self,
        n: int = 20,
        method: str = 'gain'
    ) -> List[Tuple[str, float]]:
        """Get top N most important features."""
        if method == 'gain':
            importance = self.gain
        elif method == 'cover':
            importance = self.cover
        elif method == 'weight':
            importance = self.weight
        else:
            importance = self.gain

        indices = np.argsort(importance)[::-1][:n]
        return [(self.feature_names[i], importance[i]) for i in indices]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert to pandas DataFrame."""
        df = pd.DataFrame({
            'feature': self.feature_names,
            'gain': self.gain,
            'cover': self.cover,
            'weight': self.weight
        })
        return df.sort_values('gain', ascending=False).reset_index(drop=True)


class CorruptionXGBoost:
    """
    XGBoost classifier for procurement corruption detection.

    This class implements:
    - Training with class imbalance handling (scale_pos_weight)
    - Early stopping to prevent overfitting
    - Multiple feature importance methods
    - SHAP value preparation for explainability
    - Prediction with probability/confidence scores
    - Model persistence

    Example usage:
        from training_data import extract_training_data

        # Prepare data
        dataset = await extract_training_data()

        # Train model
        xgb_model = CorruptionXGBoost()
        xgb_model.fit(
            dataset.X_train, dataset.y_train,
            eval_set=[(dataset.X_test, dataset.y_test)],
            scale_pos_weight=dataset.get_pos_weight()
        )

        # Evaluate
        metrics = xgb_model.evaluate(dataset.X_test, dataset.y_test)
        print(f"ROC-AUC: {metrics.roc_auc:.4f}")

        # Get SHAP explainer
        explainer = xgb_model.get_shap_explainer()
        shap_values = explainer(dataset.X_test)

        # Save model
        xgb_model.save("corruption_xgb_v1")
    """

    def __init__(
        self,
        n_estimators: int = 500,
        max_depth: int = 6,
        learning_rate: float = 0.1,
        subsample: float = 0.8,
        colsample_bytree: float = 0.8,
        reg_alpha: float = 0.0,
        reg_lambda: float = 1.0,
        min_child_weight: int = 1,
        gamma: float = 0.0,
        scale_pos_weight: float = 1.0,
        objective: str = 'binary:logistic',
        eval_metric: str = 'auc',
        use_gpu: bool = False,
        n_jobs: int = -1,
        random_state: int = 42,
        verbose: bool = False
    ):
        """
        Initialize XGBoost classifier.

        Args:
            n_estimators: Number of boosting rounds
            max_depth: Maximum tree depth
            learning_rate: Step size shrinkage (eta)
            subsample: Subsample ratio of training instances
            colsample_bytree: Subsample ratio of columns per tree
            reg_alpha: L1 regularization term
            reg_lambda: L2 regularization term
            min_child_weight: Minimum sum of instance weight in child
            gamma: Minimum loss reduction for partition
            scale_pos_weight: Balance of positive and negative weights
            objective: Learning objective
            eval_metric: Evaluation metric for early stopping
            use_gpu: Whether to use GPU for training
            n_jobs: Number of parallel threads
            random_state: Random seed
            verbose: Whether to print training progress
        """
        self.params = {
            'n_estimators': n_estimators,
            'max_depth': max_depth,
            'learning_rate': learning_rate,
            'subsample': subsample,
            'colsample_bytree': colsample_bytree,
            'reg_alpha': reg_alpha,
            'reg_lambda': reg_lambda,
            'min_child_weight': min_child_weight,
            'gamma': gamma,
            'scale_pos_weight': scale_pos_weight,
            'objective': objective,
            'eval_metric': eval_metric,
            'n_jobs': n_jobs,
            'random_state': random_state,
            'verbosity': 1 if verbose else 0
        }

        # Use GPU if requested and available
        if use_gpu:
            self.params['tree_method'] = 'gpu_hist'
            self.params['predictor'] = 'gpu_predictor'
        else:
            self.params['tree_method'] = 'hist'  # Fast histogram-based method

        self.model: Optional[xgb.XGBClassifier] = None
        self.is_fitted = False
        self.feature_names: Optional[List[str]] = None
        self.training_metadata: Dict[str, Any] = {}
        self.best_iteration: Optional[int] = None

        logger.info(
            f"CorruptionXGBoost initialized with "
            f"n_estimators={n_estimators}, max_depth={max_depth}, lr={learning_rate}"
        )

    def _create_model(self, scale_pos_weight: Optional[float] = None) -> xgb.XGBClassifier:
        """Create XGBClassifier with current parameters."""
        params = self.params.copy()

        if scale_pos_weight is not None:
            params['scale_pos_weight'] = scale_pos_weight

        return xgb.XGBClassifier(**params)

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        eval_set: Optional[List[Tuple[np.ndarray, np.ndarray]]] = None,
        early_stopping_rounds: int = 50,
        scale_pos_weight: Optional[float] = None,
        feature_names: Optional[List[str]] = None,
        verbose: bool = True
    ) -> 'CorruptionXGBoost':
        """
        Train the XGBoost model with optional early stopping.

        Args:
            X: Training features (n_samples, n_features)
            y: Training labels (n_samples,)
            eval_set: Evaluation set(s) for early stopping [(X_val, y_val)]
            early_stopping_rounds: Rounds without improvement before stopping
            scale_pos_weight: Override scale_pos_weight for class imbalance
            feature_names: Optional feature names
            verbose: Whether to show training progress

        Returns:
            self
        """
        logger.info(f"Training XGBoost on {X.shape[0]} samples, {X.shape[1]} features")

        self.model = self._create_model(scale_pos_weight)
        self.feature_names = feature_names

        start_time = datetime.utcnow()

        # Prepare fit kwargs
        fit_kwargs = {
            'verbose': verbose
        }

        if eval_set is not None:
            fit_kwargs['eval_set'] = eval_set

            # Early stopping (XGBoost 2.0+ syntax)
            self.model.set_params(
                early_stopping_rounds=early_stopping_rounds
            )

        # Fit model
        self.model.fit(X, y, **fit_kwargs)

        training_time = (datetime.utcnow() - start_time).total_seconds()
        self.is_fitted = True

        # Get best iteration if early stopping was used
        if hasattr(self.model, 'best_iteration'):
            self.best_iteration = self.model.best_iteration
        else:
            self.best_iteration = self.params['n_estimators']

        # Store training metadata
        self.training_metadata = {
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'n_positive': int(y.sum()),
            'n_negative': int((~y.astype(bool)).sum()),
            'best_iteration': self.best_iteration,
            'training_time_seconds': training_time,
            'trained_at': datetime.utcnow().isoformat(),
            'scale_pos_weight': scale_pos_weight or self.params['scale_pos_weight']
        }

        logger.info(
            f"Training completed in {training_time:.2f}s, "
            f"best iteration: {self.best_iteration}"
        )

        return self

    def fit_with_cv(
        self,
        X: np.ndarray,
        y: np.ndarray,
        n_folds: int = 5,
        early_stopping_rounds: int = 50,
        scale_pos_weight: Optional[float] = None,
        feature_names: Optional[List[str]] = None
    ) -> Tuple['CorruptionXGBoost', np.ndarray]:
        """
        Train with cross-validation for hyperparameter evaluation.

        Args:
            X: Training features
            y: Training labels
            n_folds: Number of CV folds
            early_stopping_rounds: Early stopping rounds
            scale_pos_weight: Class imbalance weight
            feature_names: Feature names

        Returns:
            Tuple of (fitted model, cv_scores)
        """
        logger.info(f"Training with {n_folds}-fold cross-validation")

        # Use xgboost's native CV for proper early stopping
        dtrain = xgb.DMatrix(X, label=y)

        params = self.params.copy()
        params.pop('n_estimators', None)  # CV will determine best number
        if scale_pos_weight is not None:
            params['scale_pos_weight'] = scale_pos_weight

        cv_results = xgb.cv(
            params,
            dtrain,
            num_boost_round=self.params['n_estimators'],
            nfold=n_folds,
            stratified=True,
            early_stopping_rounds=early_stopping_rounds,
            seed=self.params['random_state'],
            verbose_eval=10
        )

        # Get best iteration from CV
        best_iteration = len(cv_results)
        cv_scores = cv_results[f'test-{self.params["eval_metric"]}-mean'].values

        logger.info(
            f"CV best iteration: {best_iteration}, "
            f"best score: {cv_scores[-1]:.4f}"
        )

        # Update n_estimators and fit on full data
        self.params['n_estimators'] = best_iteration

        # Split for early stopping eval
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.1, random_state=42, stratify=y
        )

        self.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=early_stopping_rounds,
            scale_pos_weight=scale_pos_weight,
            feature_names=feature_names,
            verbose=False
        )

        # Store CV results
        self.training_metadata['cv_results'] = cv_results.to_dict()
        self.training_metadata['cv_best_score'] = float(cv_scores[-1])
        self.training_metadata['cv_folds'] = n_folds

        return self, cv_scores

    def hyperparameter_tune(
        self,
        X: np.ndarray,
        y: np.ndarray,
        param_grid: Optional[Dict[str, List]] = None,
        n_folds: int = 5,
        early_stopping_rounds: int = 30,
        scale_pos_weight: Optional[float] = None,
        n_iter: int = 20
    ) -> Tuple['CorruptionXGBoost', Dict[str, Any]]:
        """
        Perform hyperparameter tuning.

        Uses randomized search for efficiency.

        Args:
            X: Training features
            y: Training labels
            param_grid: Parameter distributions (uses default if None)
            n_folds: Number of CV folds
            early_stopping_rounds: Early stopping rounds
            scale_pos_weight: Class imbalance weight
            n_iter: Number of random parameter combinations

        Returns:
            Tuple of (best model, best parameters)
        """
        from sklearn.model_selection import RandomizedSearchCV

        if param_grid is None:
            # Default parameter distributions for corruption detection
            param_grid = {
                'max_depth': [4, 5, 6, 7, 8],
                'learning_rate': [0.01, 0.05, 0.1, 0.15],
                'subsample': [0.6, 0.7, 0.8, 0.9],
                'colsample_bytree': [0.6, 0.7, 0.8, 0.9],
                'min_child_weight': [1, 3, 5, 7],
                'reg_alpha': [0, 0.1, 0.5, 1.0],
                'reg_lambda': [0.5, 1.0, 2.0, 5.0]
            }

        logger.info(f"Starting hyperparameter tuning with {n_iter} iterations...")

        model = self._create_model(scale_pos_weight)
        cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)

        random_search = RandomizedSearchCV(
            model,
            param_grid,
            n_iter=n_iter,
            cv=cv,
            scoring='roc_auc',
            n_jobs=-1,
            verbose=1,
            random_state=42,
            refit=True
        )

        start_time = datetime.utcnow()

        # Split data for early stopping
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.1, random_state=42, stratify=y
        )

        random_search.fit(
            X_train, y_train,
            eval_set=[(X_val, y_val)],
            verbose=False
        )

        search_time = (datetime.utcnow() - start_time).total_seconds()

        # Update with best estimator
        self.model = random_search.best_estimator_
        self.is_fitted = True
        self.best_iteration = getattr(self.model, 'best_iteration', None)

        best_params = random_search.best_params_
        best_score = random_search.best_score_

        self.training_metadata['hyperparameter_tuning'] = {
            'best_params': best_params,
            'best_score': float(best_score),
            'search_time_seconds': search_time,
            'n_iter': n_iter
        }

        logger.info(
            f"Best ROC-AUC: {best_score:.4f}, "
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
            threshold: Classification threshold

        Returns:
            List of dicts with prediction details
        """
        probas = self.predict_proba(X)

        results = []
        for proba in probas:
            prob_corrupt = proba[1]
            prediction = 1 if prob_corrupt >= threshold else 0
            confidence = max(proba)

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
        y: np.ndarray
    ) -> XGBModelMetrics:
        """
        Evaluate model on test data.

        Args:
            X: Test features
            y: True labels

        Returns:
            XGBModelMetrics with evaluation results
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)[:, 1]

        metrics = XGBModelMetrics(
            accuracy=accuracy_score(y, y_pred),
            precision=precision_score(y, y_pred, zero_division=0),
            recall=recall_score(y, y_pred, zero_division=0),
            f1=f1_score(y, y_pred, zero_division=0),
            roc_auc=roc_auc_score(y, y_proba),
            average_precision=average_precision_score(y, y_proba),
            confusion_matrix=confusion_matrix(y, y_pred),
            classification_report=classification_report(y, y_pred, target_names=['Clean', 'Flagged']),
            best_iteration=self.best_iteration
        )

        logger.info(
            f"Evaluation: Accuracy={metrics.accuracy:.4f}, "
            f"Precision={metrics.precision:.4f}, Recall={metrics.recall:.4f}, "
            f"F1={metrics.f1:.4f}, ROC-AUC={metrics.roc_auc:.4f}"
        )

        return metrics

    def get_feature_importance(
        self,
        feature_names: Optional[List[str]] = None
    ) -> XGBFeatureImportance:
        """
        Get feature importance scores using all three XGBoost methods.

        Args:
            feature_names: Feature names (uses stored if None)

        Returns:
            XGBFeatureImportance with gain, cover, and weight
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        names = feature_names or self.feature_names
        n_features = self.model.n_features_in_

        if names is None:
            names = [f"feature_{i}" for i in range(n_features)]

        # Get importance for each method
        booster = self.model.get_booster()

        gain_dict = booster.get_score(importance_type='gain')
        cover_dict = booster.get_score(importance_type='cover')
        weight_dict = booster.get_score(importance_type='weight')

        # Convert to arrays (features not in tree get 0)
        gain = np.zeros(n_features)
        cover = np.zeros(n_features)
        weight = np.zeros(n_features)

        for i, name in enumerate(names):
            # XGBoost uses f0, f1, ... for feature names
            key = f'f{i}'
            gain[i] = gain_dict.get(key, 0)
            cover[i] = cover_dict.get(key, 0)
            weight[i] = weight_dict.get(key, 0)

        # Normalize
        if gain.sum() > 0:
            gain = gain / gain.sum()
        if cover.sum() > 0:
            cover = cover / cover.sum()
        if weight.sum() > 0:
            weight = weight / weight.sum()

        return XGBFeatureImportance(
            feature_names=names,
            gain=gain,
            cover=cover,
            weight=weight
        )

    def get_shap_explainer(self, X_background: Optional[np.ndarray] = None) -> Any:
        """
        Get SHAP explainer for model interpretability.

        Args:
            X_background: Background data for SHAP (uses 100 samples if None)

        Returns:
            SHAP TreeExplainer

        Raises:
            ImportError: If shap is not installed
        """
        try:
            import shap
        except ImportError:
            raise ImportError(
                "SHAP is required for explainability. "
                "Install it with: pip install shap"
            )

        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Call fit() first.")

        # TreeExplainer is faster and exact for tree-based models
        explainer = shap.TreeExplainer(self.model)

        return explainer

    def explain_prediction(
        self,
        X: np.ndarray,
        feature_names: Optional[List[str]] = None,
        top_n: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Explain individual predictions using SHAP values.

        Args:
            X: Features for predictions to explain
            feature_names: Feature names
            top_n: Number of top contributing features to show

        Returns:
            List of explanation dicts with feature contributions
        """
        try:
            import shap
        except ImportError:
            logger.warning("SHAP not available, returning feature importance instead")
            return self._explain_without_shap(X, feature_names, top_n)

        names = feature_names or self.feature_names or [f"f{i}" for i in range(X.shape[1])]

        explainer = self.get_shap_explainer()
        shap_values = explainer.shap_values(X)

        # For binary classification, shap_values might be a list
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Get positive class SHAP values

        explanations = []
        probas = self.predict_proba(X)

        for i in range(len(X)):
            sample_shap = shap_values[i]

            # Get top contributing features
            abs_shap = np.abs(sample_shap)
            top_indices = np.argsort(abs_shap)[::-1][:top_n]

            contributions = []
            for idx in top_indices:
                contributions.append({
                    'feature': names[idx],
                    'value': float(X[i, idx]),
                    'shap_value': float(sample_shap[idx]),
                    'contribution': 'increases risk' if sample_shap[idx] > 0 else 'decreases risk'
                })

            explanations.append({
                'prediction_probability': float(probas[i, 1]),
                'expected_value': float(explainer.expected_value) if hasattr(explainer, 'expected_value') else 0.5,
                'top_contributions': contributions,
                'shap_sum': float(sample_shap.sum())
            })

        return explanations

    def _explain_without_shap(
        self,
        X: np.ndarray,
        feature_names: Optional[List[str]],
        top_n: int
    ) -> List[Dict[str, Any]]:
        """Fallback explanation using feature importance when SHAP unavailable."""
        names = feature_names or self.feature_names or [f"f{i}" for i in range(X.shape[1])]
        importance = self.get_feature_importance(names)
        top_features = importance.get_top_features(top_n, method='gain')

        probas = self.predict_proba(X)

        explanations = []
        for i in range(len(X)):
            contributions = [
                {
                    'feature': name,
                    'value': float(X[i, names.index(name)]),
                    'importance': float(imp),
                    'contribution': 'see feature importance'
                }
                for name, imp in top_features
            ]

            explanations.append({
                'prediction_probability': float(probas[i, 1]),
                'top_contributions': contributions,
                'note': 'SHAP unavailable, showing global feature importance'
            })

        return explanations

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
            filepath: Path to save model (creates .json and _metadata.json)
        """
        if not self.is_fitted:
            raise RuntimeError("Model not fitted. Cannot save unfitted model.")

        # XGBoost native format
        if not filepath.endswith('.json'):
            model_path = filepath + '.json'
        else:
            model_path = filepath

        self.model.save_model(model_path)

        # Save metadata separately
        meta_path = model_path.replace('.json', '_metadata.json')
        metadata = {
            'params': self.params,
            'feature_names': self.feature_names,
            'training_metadata': self.training_metadata,
            'best_iteration': self.best_iteration,
            'saved_at': datetime.utcnow().isoformat()
        }

        with open(meta_path, 'w') as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Model saved to {model_path}")

    @classmethod
    def load(cls, filepath: str) -> 'CorruptionXGBoost':
        """
        Load model from disk.

        Args:
            filepath: Path to saved model

        Returns:
            Loaded CorruptionXGBoost instance
        """
        if not filepath.endswith('.json'):
            model_path = filepath + '.json'
        else:
            model_path = filepath

        # Load metadata
        meta_path = model_path.replace('.json', '_metadata.json')
        with open(meta_path, 'r') as f:
            metadata = json.load(f)

        # Create instance
        instance = cls.__new__(cls)
        instance.params = metadata['params']
        instance.feature_names = metadata['feature_names']
        instance.training_metadata = metadata['training_metadata']
        instance.best_iteration = metadata['best_iteration']

        # Load XGBoost model
        instance.model = xgb.XGBClassifier()
        instance.model.load_model(model_path)
        instance.is_fitted = True

        logger.info(f"Model loaded from {model_path}")
        return instance

    def get_model_summary(self) -> Dict[str, Any]:
        """Get summary of model configuration and training."""
        return {
            'model_type': 'XGBoost',
            'is_fitted': self.is_fitted,
            'params': self.params,
            'best_iteration': self.best_iteration,
            'n_features': len(self.feature_names) if self.feature_names else None,
            'training_metadata': self.training_metadata
        }


def quick_train_xgboost(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_test: np.ndarray,
    y_test: np.ndarray,
    feature_names: Optional[List[str]] = None,
    scale_pos_weight: Optional[float] = None,
    tune_hyperparameters: bool = False
) -> Tuple[CorruptionXGBoost, XGBModelMetrics, XGBFeatureImportance]:
    """
    Quick training function with evaluation and feature importance.

    Args:
        X_train: Training features
        y_train: Training labels
        X_test: Test features
        y_test: Test labels
        feature_names: Optional feature names
        scale_pos_weight: Class imbalance weight
        tune_hyperparameters: Whether to tune hyperparameters

    Returns:
        Tuple of (model, metrics, feature_importance)
    """
    # Calculate scale_pos_weight if not provided
    if scale_pos_weight is None:
        n_neg = (y_train == 0).sum()
        n_pos = (y_train == 1).sum()
        scale_pos_weight = n_neg / n_pos if n_pos > 0 else 1.0

    xgb_model = CorruptionXGBoost(scale_pos_weight=scale_pos_weight)

    if tune_hyperparameters:
        xgb_model.hyperparameter_tune(
            X_train, y_train,
            n_iter=10,
            scale_pos_weight=scale_pos_weight
        )
    else:
        # Split validation set for early stopping
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=0.1, random_state=42, stratify=y_train
        )

        xgb_model.fit(
            X_tr, y_tr,
            eval_set=[(X_val, y_val)],
            early_stopping_rounds=50,
            scale_pos_weight=scale_pos_weight,
            feature_names=feature_names,
            verbose=False
        )

    metrics = xgb_model.evaluate(X_test, y_test)
    importance = xgb_model.get_feature_importance(feature_names)

    return xgb_model, metrics, importance


if __name__ == "__main__":
    # Example usage with synthetic data
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print("XGBoost Corruption Detection Model")
    print("=" * 50)

    # Generate synthetic data
    np.random.seed(42)
    n_samples = 1000
    n_features = 113  # Match actual feature count

    X = np.random.randn(n_samples, n_features)
    y = np.random.binomial(1, 0.3, n_samples)  # 30% positive rate

    # Split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    feature_names = [f"feature_{i}" for i in range(n_features)]

    # Quick train
    xgb_model, metrics, importance = quick_train_xgboost(
        X_train, y_train, X_test, y_test,
        feature_names=feature_names
    )

    print("\nModel Summary:")
    print(json.dumps(xgb_model.get_model_summary(), indent=2, default=str))

    print("\nMetrics:")
    print(f"  ROC-AUC: {metrics.roc_auc:.4f}")
    print(f"  F1: {metrics.f1:.4f}")
    print(f"  Precision: {metrics.precision:.4f}")
    print(f"  Recall: {metrics.recall:.4f}")
    print(f"  Best Iteration: {metrics.best_iteration}")

    print("\nTop 10 Features (Gain):")
    for name, imp in importance.get_top_features(10, method='gain'):
        print(f"  {name}: {imp:.4f}")

    # Test explainability
    print("\nExplanation for first test sample:")
    explanations = xgb_model.explain_prediction(X_test[:1], feature_names, top_n=5)
    print(json.dumps(explanations[0], indent=2))

    # Save model
    xgb_model.save("demo_xgb_model")
    print("\nModel saved to demo_xgb_model.json")

    # Load and verify
    xgb_loaded = CorruptionXGBoost.load("demo_xgb_model")
    print(f"Model loaded, is_fitted: {xgb_loaded.is_fitted}")

    # Clean up demo files
    os.remove("demo_xgb_model.json")
    os.remove("demo_xgb_model_metadata.json")
    print("Demo files cleaned up")
