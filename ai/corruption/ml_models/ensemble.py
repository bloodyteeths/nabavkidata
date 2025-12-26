"""
Stacking Ensemble for Corruption Detection

This module implements a meta-learning ensemble that combines predictions from
multiple base models (Random Forest, XGBoost, Neural Network) to achieve
superior corruption detection performance.

The ensemble uses:
1. Out-of-fold predictions for training the meta-learner (prevents data leakage)
2. Logistic Regression as the default meta-learner
3. Weighted averaging as fallback when meta-learner fails
4. Probability calibration for reliable confidence scores

Author: nabavkidata.com
License: Proprietary
"""

import logging
import pickle
from pathlib import Path
from typing import Optional, Dict, Any, Union, List, Tuple
from abc import ABC, abstractmethod

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedKFold
    from sklearn.preprocessing import StandardScaler
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger(__name__)


class BaseModel(ABC):
    """Abstract base class defining the interface for base models."""

    @abstractmethod
    def fit(self, X: np.ndarray, y: np.ndarray) -> 'BaseModel':
        """Fit the model."""
        pass

    @abstractmethod
    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        pass

    @abstractmethod
    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities."""
        pass

    @abstractmethod
    def save(self, path: Union[str, Path]) -> None:
        """Save model to disk."""
        pass

    @abstractmethod
    def load(self, path: Union[str, Path]) -> 'BaseModel':
        """Load model from disk."""
        pass


class MetaLearner:
    """
    Meta-learner for stacking ensemble.

    Uses Logistic Regression with calibration by default, but can be
    replaced with a small neural network for more complex combinations.
    """

    def __init__(
        self,
        calibrate: bool = True,
        random_state: int = 42
    ):
        """
        Initialize the meta-learner.

        Args:
            calibrate: Whether to calibrate probabilities
            random_state: Random seed for reproducibility
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required. Install with: pip install scikit-learn")

        self.calibrate = calibrate
        self.random_state = random_state
        self.scaler = StandardScaler()
        self.model = LogisticRegression(
            random_state=random_state,
            max_iter=1000,
            class_weight='balanced'
        )
        self._is_fitted = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'MetaLearner':
        """
        Fit the meta-learner.

        Args:
            X: Stacked base model predictions of shape (n_samples, n_models)
            y: True labels of shape (n_samples,)

        Returns:
            self for method chaining
        """
        # Handle NaN values
        X = np.nan_to_num(X, nan=0.5, posinf=1.0, neginf=0.0)

        # Scale features
        X_scaled = self.scaler.fit_transform(X)

        # Fit with calibration if requested
        if self.calibrate:
            base_model = LogisticRegression(
                random_state=self.random_state,
                max_iter=1000,
                class_weight='balanced'
            )
            self.model = CalibratedClassifierCV(
                base_model,
                cv=3,
                method='isotonic'
            )
        else:
            self.model = LogisticRegression(
                random_state=self.random_state,
                max_iter=1000,
                class_weight='balanced'
            )

        self.model.fit(X_scaled, y)
        self._is_fitted = True

        logger.info("Meta-learner fitted successfully")
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict class labels.

        Args:
            X: Stacked base model predictions

        Returns:
            Predicted labels
        """
        X = np.nan_to_num(X, nan=0.5, posinf=1.0, neginf=0.0)
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probabilities.

        Args:
            X: Stacked base model predictions

        Returns:
            Probability of corruption (positive class)
        """
        X = np.nan_to_num(X, nan=0.5, posinf=1.0, neginf=0.0)
        X_scaled = self.scaler.transform(X)
        probas = self.model.predict_proba(X_scaled)

        # Return probability of positive class
        if probas.ndim > 1:
            return probas[:, 1]
        return probas


class CorruptionEnsemble:
    """
    Stacking ensemble for corruption detection.

    This ensemble combines predictions from multiple base models:
    - Random Forest
    - XGBoost
    - Neural Network

    The ensemble uses out-of-fold predictions to train a meta-learner,
    which learns optimal weights for combining base model predictions.
    If the meta-learner fails, weighted averaging is used as fallback.

    Features:
    - Robust to missing base models
    - Out-of-fold predictions prevent data leakage
    - Probability calibration for reliable confidence
    - Save/load entire ensemble

    Usage:
        ensemble = CorruptionEnsemble()
        ensemble.add_model('rf', random_forest_model)
        ensemble.add_model('xgb', xgboost_model)
        ensemble.add_model('nn', neural_network_model)

        ensemble.fit(X_train, y_train)
        predictions = ensemble.predict(X_test)
        probabilities = ensemble.predict_proba(X_test)

        ensemble.save('ensemble/')
        ensemble.load('ensemble/')
    """

    def __init__(
        self,
        use_meta_learner: bool = True,
        n_folds: int = 5,
        calibrate: bool = True,
        weights: Optional[Dict[str, float]] = None,
        random_state: int = 42
    ):
        """
        Initialize the ensemble.

        Args:
            use_meta_learner: Whether to use a meta-learner (True) or weighted average (False)
            n_folds: Number of folds for out-of-fold predictions
            calibrate: Whether to calibrate final probabilities
            weights: Optional fixed weights for each model (used if meta-learner disabled)
            random_state: Random seed for reproducibility
        """
        if not SKLEARN_AVAILABLE:
            raise ImportError("scikit-learn is required. Install with: pip install scikit-learn")

        self.use_meta_learner = use_meta_learner
        self.n_folds = n_folds
        self.calibrate = calibrate
        self.random_state = random_state

        # Base models
        self.base_models: Dict[str, Any] = {}

        # Model weights (for weighted averaging fallback)
        self.weights = weights or {
            'rf': 0.35,      # Random Forest - robust baseline
            'xgb': 0.40,     # XGBoost - typically best on tabular
            'nn': 0.25       # Neural Network - captures complex patterns
        }

        # Meta-learner
        self.meta_learner: Optional[MetaLearner] = None

        # Fitted base models (one per fold for OOF predictions)
        self.fitted_models: Dict[str, List[Any]] = {}

        # Training state
        self._is_fitted = False
        self._model_order: List[str] = []

    def add_model(
        self,
        name: str,
        model: Any,
        weight: Optional[float] = None
    ) -> 'CorruptionEnsemble':
        """
        Add a base model to the ensemble.

        Args:
            name: Model name (e.g., 'rf', 'xgb', 'nn')
            model: Model instance with fit, predict, predict_proba methods
            weight: Optional weight for weighted averaging

        Returns:
            self for method chaining
        """
        self.base_models[name] = model

        if weight is not None:
            self.weights[name] = weight

        logger.info(f"Added model '{name}' to ensemble")
        return self

    def _get_out_of_fold_predictions(
        self,
        X: np.ndarray,
        y: np.ndarray
    ) -> np.ndarray:
        """
        Generate out-of-fold predictions for training meta-learner.

        This method trains each base model on k-1 folds and predicts on
        the held-out fold, ensuring no data leakage in meta-learner training.

        Args:
            X: Training features
            y: Training labels

        Returns:
            OOF predictions of shape (n_samples, n_models)
        """
        n_samples = len(X)
        n_models = len(self.base_models)
        self._model_order = list(self.base_models.keys())

        # Initialize OOF predictions
        oof_predictions = np.zeros((n_samples, n_models))

        # Stratified k-fold
        kfold = StratifiedKFold(
            n_splits=self.n_folds,
            shuffle=True,
            random_state=self.random_state
        )

        # Initialize fitted models storage
        self.fitted_models = {name: [] for name in self._model_order}

        for fold_idx, (train_idx, val_idx) in enumerate(kfold.split(X, y)):
            logger.info(f"Processing fold {fold_idx + 1}/{self.n_folds}")

            X_train_fold = X[train_idx]
            y_train_fold = y[train_idx]
            X_val_fold = X[val_idx]

            for model_idx, model_name in enumerate(self._model_order):
                # Get a fresh copy of the model
                base_model = self.base_models[model_name]

                # Clone or recreate model for this fold
                if hasattr(base_model, 'get_params'):
                    # sklearn-style cloning
                    try:
                        from sklearn.base import clone
                        fold_model = clone(base_model)
                    except Exception:
                        # Use the same model (for neural networks)
                        fold_model = base_model
                else:
                    fold_model = base_model

                try:
                    # Fit on training fold
                    fold_model.fit(X_train_fold, y_train_fold)

                    # Predict on validation fold
                    fold_preds = fold_model.predict_proba(X_val_fold)

                    # Handle different predict_proba output formats
                    if isinstance(fold_preds, np.ndarray) and fold_preds.ndim > 1:
                        fold_preds = fold_preds[:, 1]  # Get positive class probability

                    oof_predictions[val_idx, model_idx] = fold_preds

                    # Store fitted model
                    self.fitted_models[model_name].append(fold_model)

                    logger.debug(f"Fold {fold_idx + 1}: {model_name} fitted successfully")

                except Exception as e:
                    logger.warning(f"Failed to fit {model_name} on fold {fold_idx + 1}: {e}")
                    # Use 0.5 as neutral prediction for failed models
                    oof_predictions[val_idx, model_idx] = 0.5

        return oof_predictions

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        verbose: bool = True
    ) -> 'CorruptionEnsemble':
        """
        Fit the ensemble using out-of-fold predictions.

        Args:
            X: Training features of shape (n_samples, n_features)
            y: Training labels of shape (n_samples,)
            verbose: Whether to print progress

        Returns:
            self for method chaining
        """
        if len(self.base_models) == 0:
            raise ValueError("No base models added. Use add_model() first.")

        logger.info(f"Fitting ensemble with {len(self.base_models)} base models")
        logger.info(f"Training samples: {len(X)}, Features: {X.shape[1]}")

        # Generate out-of-fold predictions
        oof_predictions = self._get_out_of_fold_predictions(X, y)

        logger.info(f"OOF predictions shape: {oof_predictions.shape}")

        # Train meta-learner on OOF predictions
        if self.use_meta_learner:
            try:
                self.meta_learner = MetaLearner(
                    calibrate=self.calibrate,
                    random_state=self.random_state
                )
                self.meta_learner.fit(oof_predictions, y)
                logger.info("Meta-learner trained successfully")
            except Exception as e:
                logger.warning(f"Meta-learner training failed: {e}. Using weighted average.")
                self.use_meta_learner = False

        # Also fit all base models on full training data for final predictions
        self._fit_final_models(X, y)

        self._is_fitted = True
        logger.info("Ensemble fitting completed")

        return self

    def _fit_final_models(self, X: np.ndarray, y: np.ndarray) -> None:
        """
        Fit all base models on full training data.

        Args:
            X: Full training features
            y: Full training labels
        """
        logger.info("Fitting final models on full training data")

        for model_name, model in self.base_models.items():
            try:
                model.fit(X, y)
                logger.info(f"Final {model_name} model fitted")
            except Exception as e:
                logger.warning(f"Failed to fit final {model_name} model: {e}")

    def _get_base_predictions(self, X: np.ndarray) -> np.ndarray:
        """
        Get predictions from all base models.

        Args:
            X: Features

        Returns:
            Stacked predictions of shape (n_samples, n_models)
        """
        n_samples = len(X)
        predictions = np.zeros((n_samples, len(self._model_order)))

        for idx, model_name in enumerate(self._model_order):
            if model_name in self.base_models:
                model = self.base_models[model_name]

                try:
                    preds = model.predict_proba(X)

                    # Handle different predict_proba output formats
                    if isinstance(preds, np.ndarray) and preds.ndim > 1:
                        preds = preds[:, 1]

                    predictions[:, idx] = preds

                except Exception as e:
                    logger.warning(f"Prediction failed for {model_name}: {e}")
                    predictions[:, idx] = 0.5  # Neutral prediction
            else:
                predictions[:, idx] = 0.5

        return predictions

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict binary class labels.

        Args:
            X: Features of shape (n_samples, n_features)

        Returns:
            Predicted labels of shape (n_samples,)
        """
        proba = self.predict_proba(X)
        return (proba >= 0.5).astype(np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probability of corruption.

        Args:
            X: Features of shape (n_samples, n_features)

        Returns:
            Probabilities of shape (n_samples,)
        """
        if not self._is_fitted:
            raise RuntimeError("Ensemble must be fitted before prediction")

        # Get base model predictions
        base_predictions = self._get_base_predictions(X)

        # Combine using meta-learner or weighted average
        if self.use_meta_learner and self.meta_learner is not None:
            try:
                final_proba = self.meta_learner.predict_proba(base_predictions)
            except Exception as e:
                logger.warning(f"Meta-learner prediction failed: {e}. Using weighted average.")
                final_proba = self._weighted_average(base_predictions)
        else:
            final_proba = self._weighted_average(base_predictions)

        return final_proba

    def _weighted_average(self, predictions: np.ndarray) -> np.ndarray:
        """
        Compute weighted average of predictions.

        Args:
            predictions: Base model predictions of shape (n_samples, n_models)

        Returns:
            Weighted average predictions of shape (n_samples,)
        """
        weights = np.array([
            self.weights.get(name, 1.0 / len(self._model_order))
            for name in self._model_order
        ])

        # Normalize weights
        weights = weights / weights.sum()

        return np.average(predictions, weights=weights, axis=1)

    def get_model_contributions(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """
        Get individual model predictions for analysis.

        Args:
            X: Features

        Returns:
            Dictionary mapping model name to predictions
        """
        if not self._is_fitted:
            raise RuntimeError("Ensemble must be fitted before getting contributions")

        base_predictions = self._get_base_predictions(X)

        contributions = {}
        for idx, model_name in enumerate(self._model_order):
            contributions[model_name] = base_predictions[:, idx]

        contributions['ensemble'] = self.predict_proba(X)

        return contributions

    def save(self, path: Union[str, Path]) -> None:
        """
        Save the entire ensemble to disk.

        Args:
            path: Directory path to save the ensemble
        """
        if not self._is_fitted:
            raise RuntimeError("Ensemble must be fitted before saving")

        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save ensemble metadata
        metadata = {
            'use_meta_learner': self.use_meta_learner,
            'n_folds': self.n_folds,
            'calibrate': self.calibrate,
            'weights': self.weights,
            'random_state': self.random_state,
            'model_order': self._model_order,
            'is_fitted': self._is_fitted
        }

        with open(path / 'ensemble_metadata.pkl', 'wb') as f:
            pickle.dump(metadata, f)

        # Save meta-learner
        if self.meta_learner is not None:
            with open(path / 'meta_learner.pkl', 'wb') as f:
                pickle.dump(self.meta_learner, f)

        # Save base models
        for model_name, model in self.base_models.items():
            model_path = path / f'{model_name}_model'

            try:
                if hasattr(model, 'save'):
                    # Neural network or custom save
                    model.save(model_path)
                else:
                    # sklearn-style pickle
                    with open(f'{model_path}.pkl', 'wb') as f:
                        pickle.dump(model, f)

                logger.info(f"Saved {model_name} model")

            except Exception as e:
                logger.warning(f"Failed to save {model_name} model: {e}")

        logger.info(f"Ensemble saved to {path}")

    def load(self, path: Union[str, Path]) -> 'CorruptionEnsemble':
        """
        Load ensemble from disk.

        Args:
            path: Directory path containing saved ensemble

        Returns:
            self for method chaining
        """
        path = Path(path)

        if not path.exists():
            raise FileNotFoundError(f"Ensemble directory not found: {path}")

        # Load metadata
        with open(path / 'ensemble_metadata.pkl', 'rb') as f:
            metadata = pickle.load(f)

        self.use_meta_learner = metadata['use_meta_learner']
        self.n_folds = metadata['n_folds']
        self.calibrate = metadata['calibrate']
        self.weights = metadata['weights']
        self.random_state = metadata['random_state']
        self._model_order = metadata['model_order']
        self._is_fitted = metadata['is_fitted']

        # Load meta-learner
        meta_learner_path = path / 'meta_learner.pkl'
        if meta_learner_path.exists():
            with open(meta_learner_path, 'rb') as f:
                self.meta_learner = pickle.load(f)

        # Load base models
        for model_name in self._model_order:
            model_path = path / f'{model_name}_model'
            pkl_path = Path(f'{model_path}.pkl')

            try:
                if pkl_path.exists():
                    # sklearn-style pickle
                    with open(pkl_path, 'rb') as f:
                        self.base_models[model_name] = pickle.load(f)
                elif model_path.exists():
                    # Directory-based save (neural network)
                    # Note: Neural network loading requires recreating the model
                    logger.warning(f"Neural network {model_name} needs to be loaded separately")
                else:
                    logger.warning(f"Model {model_name} not found at {model_path}")

            except Exception as e:
                logger.warning(f"Failed to load {model_name} model: {e}")

        logger.info(f"Ensemble loaded from {path}")
        return self

    def get_params(self, deep: bool = True) -> Dict[str, Any]:
        """
        Get ensemble parameters (sklearn-compatible).

        Args:
            deep: Whether to return nested parameters

        Returns:
            Dictionary of parameters
        """
        return {
            'use_meta_learner': self.use_meta_learner,
            'n_folds': self.n_folds,
            'calibrate': self.calibrate,
            'weights': self.weights,
            'random_state': self.random_state
        }

    def set_params(self, **params) -> 'CorruptionEnsemble':
        """
        Set ensemble parameters (sklearn-compatible).

        Args:
            **params: Parameter names and values

        Returns:
            self for method chaining
        """
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self


# Convenience function for creating ensemble
def create_ensemble(
    models: Optional[Dict[str, Any]] = None,
    weights: Optional[Dict[str, float]] = None,
    use_meta_learner: bool = True,
    **kwargs
) -> CorruptionEnsemble:
    """
    Create a CorruptionEnsemble with optional pre-configured models.

    Args:
        models: Dictionary of model_name -> model instance
        weights: Optional weights for each model
        use_meta_learner: Whether to use a meta-learner
        **kwargs: Additional arguments passed to CorruptionEnsemble

    Returns:
        Configured CorruptionEnsemble instance

    Example:
        from sklearn.ensemble import RandomForestClassifier
        from xgboost import XGBClassifier
        from .neural_network import CorruptionNeuralNetwork

        ensemble = create_ensemble({
            'rf': RandomForestClassifier(n_estimators=100),
            'xgb': XGBClassifier(n_estimators=100),
            'nn': CorruptionNeuralNetwork()
        })
    """
    ensemble = CorruptionEnsemble(
        use_meta_learner=use_meta_learner,
        weights=weights,
        **kwargs
    )

    if models:
        for name, model in models.items():
            ensemble.add_model(name, model)

    return ensemble


class SimpleWeightedEnsemble:
    """
    Simple weighted ensemble without meta-learning.

    Use this when you want a straightforward weighted average of
    model predictions without the complexity of stacking.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize simple ensemble.

        Args:
            weights: Dictionary of model_name -> weight
        """
        self.weights = weights or {}
        self.models: Dict[str, Any] = {}
        self._is_fitted = False

    def add_model(
        self,
        name: str,
        model: Any,
        weight: float = 1.0
    ) -> 'SimpleWeightedEnsemble':
        """Add a model with optional weight."""
        self.models[name] = model
        self.weights[name] = weight
        return self

    def fit(self, X: np.ndarray, y: np.ndarray) -> 'SimpleWeightedEnsemble':
        """Fit all base models."""
        for name, model in self.models.items():
            try:
                model.fit(X, y)
                logger.info(f"Fitted {name}")
            except Exception as e:
                logger.warning(f"Failed to fit {name}: {e}")

        self._is_fitted = True
        return self

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predict class labels."""
        proba = self.predict_proba(X)
        return (proba >= 0.5).astype(np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predict probabilities using weighted average."""
        if not self._is_fitted:
            raise RuntimeError("Ensemble must be fitted before prediction")

        predictions = []
        weights = []

        for name, model in self.models.items():
            try:
                preds = model.predict_proba(X)
                if isinstance(preds, np.ndarray) and preds.ndim > 1:
                    preds = preds[:, 1]
                predictions.append(preds)
                weights.append(self.weights.get(name, 1.0))
            except Exception as e:
                logger.warning(f"Prediction failed for {name}: {e}")

        if not predictions:
            raise RuntimeError("No models produced predictions")

        # Normalize weights
        weights = np.array(weights)
        weights = weights / weights.sum()

        # Stack and average
        stacked = np.column_stack(predictions)
        return np.average(stacked, weights=weights, axis=1)

    def save(self, path: Union[str, Path]) -> None:
        """Save ensemble."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        with open(path / 'simple_ensemble.pkl', 'wb') as f:
            pickle.dump({
                'weights': self.weights,
                'models': self.models,
                'is_fitted': self._is_fitted
            }, f)

    def load(self, path: Union[str, Path]) -> 'SimpleWeightedEnsemble':
        """Load ensemble."""
        path = Path(path)

        with open(path / 'simple_ensemble.pkl', 'rb') as f:
            data = pickle.load(f)

        self.weights = data['weights']
        self.models = data['models']
        self._is_fitted = data['is_fitted']

        return self
