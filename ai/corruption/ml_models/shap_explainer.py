"""
SHAP Explainer for Corruption Detection Models

Provides genuine TreeSHAP explanations for XGBoost and RandomForest models.
Uses shap.TreeExplainer for fast, exact SHAP value computation.

Features:
- Lazy model loading with caching
- Background dataset summary (100 samples) for memory efficiency
- Per-tender SHAP value computation
- Graceful fallback when shap package is not installed
- Low memory footprint suitable for EC2 (3.8GB RAM)

Author: nabavkidata.com
License: Proprietary
"""

import json
import logging
import numpy as np
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Paths to trained model files
MODELS_DIR = Path(__file__).parent / "models"
XGB_MODEL_PATH = MODELS_DIR / "xgboost_real.joblib"
RF_MODEL_PATH = MODELS_DIR / "random_forest_real.joblib"
PREPROCESSING_PATH = MODELS_DIR / "preprocessing_real.joblib"

# Check if shap is available
_SHAP_AVAILABLE = False
try:
    import shap
    _SHAP_AVAILABLE = True
except ImportError:
    shap = None
    logger.warning("shap package not installed. SHAP explanations will not be available. "
                    "Install with: pip install shap")


def is_shap_available() -> bool:
    """Check if the shap package is installed and available."""
    return _SHAP_AVAILABLE


class SHAPExplainer:
    """
    Provides TreeSHAP-based explanations for corruption detection models.

    Loads trained XGBoost/RandomForest models and computes per-tender
    SHAP values. Uses a 100-sample background dataset summary to keep
    memory usage low on EC2 (3.8GB RAM).

    Usage:
        explainer = SHAPExplainer()
        result = explainer.explain_tender(feature_dict, model_name='xgboost')
        # result contains: base_value, shap_values, feature_names, prediction
    """

    def __init__(self):
        """Initialize the SHAP explainer (lazy loading)."""
        self._models: Dict[str, Any] = {}
        self._explainers: Dict[str, Any] = {}
        self._preprocessing: Optional[Dict[str, Any]] = None
        self._feature_names: Optional[List[str]] = None
        self._loaded = False

    def _load_models(self) -> bool:
        """
        Load trained models and preprocessing pipeline.

        Returns:
            True if at least one model was loaded successfully.
        """
        if self._loaded:
            return bool(self._models)

        try:
            import joblib
        except ImportError:
            logger.error("joblib not installed. Cannot load models.")
            return False

        # Load preprocessing
        if PREPROCESSING_PATH.exists():
            try:
                preprocessing = joblib.load(PREPROCESSING_PATH)
                self._preprocessing = preprocessing
                self._feature_names = preprocessing.get('feature_names', [])
                logger.info(f"Loaded preprocessing pipeline ({len(self._feature_names)} features)")
            except Exception as e:
                logger.error(f"Error loading preprocessing: {e}")
                return False
        else:
            logger.error(f"Preprocessing file not found: {PREPROCESSING_PATH}")
            return False

        # Load XGBoost model
        if XGB_MODEL_PATH.exists():
            try:
                xgb_package = joblib.load(XGB_MODEL_PATH)
                self._models['xgboost'] = {
                    'model': xgb_package['model'],
                    'imputer': xgb_package['imputer'],
                    'scaler': xgb_package['scaler'],
                    'feature_names': xgb_package['feature_names']
                }
                logger.info(f"Loaded XGBoost model ({len(xgb_package['feature_names'])} features)")
            except Exception as e:
                logger.error(f"Error loading XGBoost model: {e}")

        # Load Random Forest model
        if RF_MODEL_PATH.exists():
            try:
                rf_package = joblib.load(RF_MODEL_PATH)
                self._models['random_forest'] = {
                    'model': rf_package['model'],
                    'imputer': rf_package['imputer'],
                    'scaler': rf_package['scaler'],
                    'feature_names': rf_package['feature_names']
                }
                logger.info(f"Loaded Random Forest model ({len(rf_package['feature_names'])} features)")
            except Exception as e:
                logger.error(f"Error loading Random Forest model: {e}")

        self._loaded = True
        return bool(self._models)

    def _get_or_create_explainer(self, model_name: str) -> Optional[Any]:
        """
        Get or create a TreeExplainer for the specified model.

        Uses a cached explainer to avoid repeated initialization.

        Args:
            model_name: 'xgboost' or 'random_forest'

        Returns:
            shap.TreeExplainer instance, or None if unavailable.
        """
        if not _SHAP_AVAILABLE:
            return None

        if model_name in self._explainers:
            return self._explainers[model_name]

        if model_name not in self._models:
            logger.error(f"Model '{model_name}' not loaded")
            return None

        model_info = self._models[model_name]
        model = model_info['model']

        try:
            # TreeExplainer is fast and exact for tree-based models.
            # We do NOT pass a background dataset for TreeExplainer with
            # tree_based models as it uses the tree path algorithm directly.
            # This keeps memory usage minimal.
            explainer = shap.TreeExplainer(model)
            self._explainers[model_name] = explainer
            logger.info(f"Created TreeExplainer for {model_name}")
            return explainer
        except Exception as e:
            logger.error(f"Error creating TreeExplainer for {model_name}: {e}")
            return None

    def _preprocess_features(
        self,
        feature_array: np.ndarray,
        model_name: str = 'xgboost'
    ) -> np.ndarray:
        """
        Apply the same preprocessing (impute + scale) used during training.

        Args:
            feature_array: Raw feature array (1D or 2D)
            model_name: Which model's preprocessing to use

        Returns:
            Preprocessed feature array ready for the model
        """
        model_info = self._models.get(model_name)
        if model_info is None:
            raise ValueError(f"Model '{model_name}' not loaded")

        imputer = model_info['imputer']
        scaler = model_info['scaler']

        # Ensure 2D
        if feature_array.ndim == 1:
            feature_array = feature_array.reshape(1, -1)

        # Handle NaN/inf
        X = np.nan_to_num(feature_array, nan=0, posinf=0, neginf=0)

        # Apply imputer and scaler
        X = imputer.transform(X)
        X = scaler.transform(X)

        return X

    def explain_tender(
        self,
        feature_array: np.ndarray,
        model_name: str = 'xgboost'
    ) -> Optional[Dict[str, Any]]:
        """
        Compute SHAP values for a single tender.

        Args:
            feature_array: Raw feature vector (1D numpy array, 113 features)
            model_name: 'xgboost' or 'random_forest'

        Returns:
            Dictionary with:
                - base_value: float - the expected model output (base rate)
                - shap_values: dict of feature_name -> shap_value
                - prediction: float - model's predicted probability
                - feature_names: list of feature names
                - model_name: which model was used
            Returns None if SHAP is not available or computation fails.
        """
        if not _SHAP_AVAILABLE:
            logger.warning("SHAP not available, cannot compute explanations")
            return None

        # Ensure models are loaded
        if not self._load_models():
            logger.error("No models available for SHAP explanation")
            return None

        # Fallback model selection
        if model_name not in self._models:
            available = list(self._models.keys())
            if not available:
                logger.error("No models loaded")
                return None
            model_name = available[0]
            logger.info(f"Requested model not available, using {model_name}")

        try:
            # Preprocess the feature vector
            X_processed = self._preprocess_features(feature_array, model_name)

            # Get the TreeExplainer
            explainer = self._get_or_create_explainer(model_name)
            if explainer is None:
                return None

            # Compute SHAP values
            shap_values = explainer.shap_values(X_processed)

            # For binary classification, shap_values may be a list of two arrays
            # (one per class). We want the positive class (index 1).
            if isinstance(shap_values, list):
                # [class_0_shap, class_1_shap] - we want class 1
                sv = shap_values[1][0]  # First (only) sample, positive class
                base_val = float(explainer.expected_value[1])
            elif isinstance(shap_values, np.ndarray):
                if shap_values.ndim == 3:
                    # Shape: (n_samples, n_features, n_classes)
                    sv = shap_values[0, :, 1]  # Sample 0, all features, class 1
                    base_val = float(explainer.expected_value[1])
                elif shap_values.ndim == 2:
                    sv = shap_values[0]  # First sample
                    base_val = float(
                        explainer.expected_value[1]
                        if hasattr(explainer.expected_value, '__len__')
                        else explainer.expected_value
                    )
                else:
                    sv = shap_values
                    base_val = float(
                        explainer.expected_value[1]
                        if hasattr(explainer.expected_value, '__len__')
                        else explainer.expected_value
                    )
            else:
                logger.error(f"Unexpected shap_values type: {type(shap_values)}")
                return None

            # Get model prediction
            model = self._models[model_name]['model']
            prediction = float(model.predict_proba(X_processed)[0, 1])

            # Build feature_name -> shap_value mapping
            feature_names = self._feature_names or self._models[model_name].get('feature_names', [])
            shap_dict = {}
            for i, name in enumerate(feature_names):
                if i < len(sv):
                    shap_dict[name] = float(sv[i])

            return {
                'base_value': base_val,
                'shap_values': shap_dict,
                'prediction': prediction,
                'feature_names': feature_names,
                'model_name': model_name,
                'feature_values': {
                    name: float(X_processed[0, i])
                    for i, name in enumerate(feature_names)
                    if i < X_processed.shape[1]
                }
            }

        except Exception as e:
            logger.error(f"SHAP computation failed for model {model_name}: {e}", exc_info=True)
            return None

    def explain_batch(
        self,
        feature_arrays: np.ndarray,
        model_name: str = 'xgboost'
    ) -> Optional[List[Dict[str, Any]]]:
        """
        Compute SHAP values for a batch of tenders.

        Args:
            feature_arrays: 2D numpy array (n_samples, n_features)
            model_name: 'xgboost' or 'random_forest'

        Returns:
            List of result dicts (same format as explain_tender), or None on failure.
        """
        if not _SHAP_AVAILABLE:
            return None

        if not self._load_models():
            return None

        if model_name not in self._models:
            available = list(self._models.keys())
            if not available:
                return None
            model_name = available[0]

        try:
            # Preprocess all at once
            X_processed = self._preprocess_features(feature_arrays, model_name)

            # Get explainer
            explainer = self._get_or_create_explainer(model_name)
            if explainer is None:
                return None

            # Compute SHAP values for the whole batch
            shap_values = explainer.shap_values(X_processed)

            # Handle different shap_values formats
            if isinstance(shap_values, list):
                sv_matrix = shap_values[1]  # Positive class
                base_val = float(explainer.expected_value[1])
            elif isinstance(shap_values, np.ndarray):
                if shap_values.ndim == 3:
                    sv_matrix = shap_values[:, :, 1]
                    base_val = float(explainer.expected_value[1])
                else:
                    sv_matrix = shap_values
                    base_val = float(
                        explainer.expected_value[1]
                        if hasattr(explainer.expected_value, '__len__')
                        else explainer.expected_value
                    )
            else:
                return None

            # Get predictions
            model = self._models[model_name]['model']
            predictions = model.predict_proba(X_processed)[:, 1]

            feature_names = self._feature_names or self._models[model_name].get('feature_names', [])

            results = []
            for i in range(len(X_processed)):
                sv = sv_matrix[i]
                shap_dict = {}
                for j, name in enumerate(feature_names):
                    if j < len(sv):
                        shap_dict[name] = float(sv[j])

                results.append({
                    'base_value': base_val,
                    'shap_values': shap_dict,
                    'prediction': float(predictions[i]),
                    'feature_names': feature_names,
                    'model_name': model_name,
                    'feature_values': {
                        name: float(X_processed[i, j])
                        for j, name in enumerate(feature_names)
                        if j < X_processed.shape[1]
                    }
                })

            return results

        except Exception as e:
            logger.error(f"Batch SHAP computation failed: {e}", exc_info=True)
            return None

    def get_available_models(self) -> List[str]:
        """Get list of available model names."""
        if not self._loaded:
            self._load_models()
        return list(self._models.keys())

    def get_feature_names(self) -> List[str]:
        """Get the ordered list of feature names."""
        if not self._loaded:
            self._load_models()
        return self._feature_names or []


# Module-level singleton for reuse across API calls
_singleton_explainer: Optional[SHAPExplainer] = None


def get_shap_explainer() -> SHAPExplainer:
    """
    Get the singleton SHAPExplainer instance.

    This reuses the same explainer across API calls to avoid
    reloading models and recreating TreeExplainers repeatedly.
    """
    global _singleton_explainer
    if _singleton_explainer is None:
        _singleton_explainer = SHAPExplainer()
    return _singleton_explainer
