"""
SHAP Explainability for Corruption Detection Models

This module provides SHAP (SHapley Additive exPlanations) based explanations
for the corruption detection models. SHAP values provide theoretically grounded
feature importance that explains how each feature contributes to a prediction.

Features:
- TreeExplainer for Random Forest and XGBoost (fast, exact)
- DeepExplainer for Neural Networks (approximate)
- Global feature importance plots
- Local prediction explanations (waterfall, force plots)
- Cohort analysis for grouped explanations
- API-ready explanation formatting

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Try to import SHAP
try:
    import shap
    SHAP_AVAILABLE = True
except ImportError:
    SHAP_AVAILABLE = False
    shap = None
    logger.warning("SHAP not installed. Install with: pip install shap")

# Try to import matplotlib for plotting
try:
    import matplotlib
    matplotlib.use('Agg')  # Non-interactive backend
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    plt = None


@dataclass
class SHAPFeatureContribution:
    """
    Contribution of a single feature to a prediction.

    Attributes:
        feature_name: Name of the feature
        feature_value: Actual value of the feature
        shap_value: SHAP contribution to prediction
        direction: 'increases_risk' or 'decreases_risk'
        importance_rank: Rank among all features (1 = most important)
        relative_contribution: Contribution as percentage of total
    """
    feature_name: str
    feature_value: float
    shap_value: float
    direction: str
    importance_rank: int
    relative_contribution: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'feature_value': float(self.feature_value),
            'shap_value': float(self.shap_value),
            'direction': self.direction,
            'importance_rank': self.importance_rank,
            'relative_contribution': float(self.relative_contribution)
        }


@dataclass
class SHAPLocalExplanation:
    """
    Complete SHAP explanation for a single prediction.

    Attributes:
        tender_id: Tender identifier
        predicted_probability: Model's predicted probability
        base_value: Expected value (baseline prediction)
        shap_values: Raw SHAP values for all features
        top_contributions: Top contributing features
        summary: Human-readable summary
        plot_data: Data for visualization
        generated_at: Timestamp
    """
    tender_id: str
    predicted_probability: float
    base_value: float
    shap_values: List[float]
    top_contributions: List[SHAPFeatureContribution]
    summary: str
    plot_data: Optional[Dict[str, Any]] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tender_id': self.tender_id,
            'predicted_probability': float(self.predicted_probability),
            'base_value': float(self.base_value),
            'shap_values': [float(v) for v in self.shap_values],
            'top_contributions': [c.to_dict() for c in self.top_contributions],
            'summary': self.summary,
            'plot_data': self.plot_data,
            'generated_at': self.generated_at.isoformat()
        }

    def to_markdown(self) -> str:
        """Generate markdown explanation"""
        lines = [
            f"## SHAP Explanation: {self.tender_id}",
            "",
            f"**Predicted Risk:** {self.predicted_probability:.1%}",
            f"**Baseline Risk:** {self.base_value:.1%}",
            f"**Deviation:** {(self.predicted_probability - self.base_value):+.1%}",
            "",
            "### Top Contributing Factors",
            ""
        ]

        for contrib in self.top_contributions[:10]:
            arrow = "+" if contrib.shap_value > 0 else "-"
            lines.append(
                f"- **{contrib.feature_name}** ({contrib.feature_value:.2f}): "
                f"{arrow}{abs(contrib.shap_value):.3f} ({contrib.direction})"
            )

        lines.extend(["", "### Summary", self.summary])

        return "\n".join(lines)


@dataclass
class SHAPGlobalExplanation:
    """
    Global SHAP explanation aggregated across multiple predictions.

    Attributes:
        n_samples: Number of samples analyzed
        mean_abs_shap: Mean absolute SHAP values per feature
        feature_importance_ranking: Features ranked by importance
        interaction_effects: Top feature interactions (if computed)
        summary: Overall summary
        plot_data: Data for global importance plot
    """
    n_samples: int
    mean_abs_shap: Dict[str, float]
    feature_importance_ranking: List[Tuple[str, float]]
    interaction_effects: Optional[Dict[str, Dict[str, float]]] = None
    summary: str = ""
    plot_data: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'n_samples': self.n_samples,
            'mean_abs_shap': {k: float(v) for k, v in self.mean_abs_shap.items()},
            'feature_importance_ranking': [
                {'feature': f, 'importance': float(i)}
                for f, i in self.feature_importance_ranking
            ],
            'interaction_effects': self.interaction_effects,
            'summary': self.summary,
            'plot_data': self.plot_data
        }


class SHAPExplainer:
    """
    SHAP-based explainer for corruption detection models.

    Supports:
    - Random Forest (TreeExplainer)
    - XGBoost (TreeExplainer)
    - Neural Network (DeepExplainer or KernelExplainer)

    Usage:
        from ai.corruption.ml_models import CorruptionRandomForest, CorruptionXGBoost

        # Load trained model
        rf_model = CorruptionRandomForest.load('corruption_rf.joblib')

        # Create explainer
        explainer = SHAPExplainer(rf_model, feature_names=feature_names)
        explainer.fit(X_background)

        # Explain single prediction
        explanation = explainer.explain_prediction(X_test[0], tender_id='123/2024')

        # Global feature importance
        global_exp = explainer.global_explanation(X_test)

        # Generate plots
        explainer.plot_waterfall(X_test[0], save_path='waterfall.png')
        explainer.plot_summary(X_test, save_path='summary.png')
    """

    def __init__(
        self,
        model: Any,
        feature_names: Optional[List[str]] = None,
        model_type: Optional[str] = None,
        background_samples: int = 100
    ):
        """
        Initialize SHAP explainer.

        Args:
            model: Trained model (RF, XGBoost, or NN wrapper)
            feature_names: Names of features
            model_type: 'random_forest', 'xgboost', 'neural_network', or None (auto-detect)
            background_samples: Number of background samples for KernelExplainer
        """
        if not SHAP_AVAILABLE:
            raise ImportError(
                "SHAP is required for this explainer. "
                "Install with: pip install shap"
            )

        self.model = model
        self.feature_names = feature_names
        self.background_samples = background_samples

        # Auto-detect model type
        self.model_type = model_type or self._detect_model_type()

        # Will be set during fit
        self.explainer: Optional[Any] = None
        self.expected_value: Optional[float] = None
        self.is_fitted = False

        logger.info(f"SHAPExplainer initialized for {self.model_type}")

    def _detect_model_type(self) -> str:
        """Auto-detect the model type"""
        model_class = type(self.model).__name__

        if 'RandomForest' in model_class:
            return 'random_forest'
        elif 'XGB' in model_class or 'xgboost' in model_class.lower():
            return 'xgboost'
        elif 'Neural' in model_class or 'MLP' in model_class:
            return 'neural_network'
        elif hasattr(self.model, 'model'):
            # Check wrapped model
            inner_class = type(self.model.model).__name__
            if 'RandomForest' in inner_class:
                return 'random_forest'
            elif 'XGB' in inner_class:
                return 'xgboost'

        # Default to kernel explainer
        return 'kernel'

    def _get_sklearn_model(self) -> Any:
        """Get the underlying sklearn/xgboost model"""
        if hasattr(self.model, 'model'):
            return self.model.model
        return self.model

    def _get_predict_function(self) -> callable:
        """Get the prediction function that returns probabilities"""
        if hasattr(self.model, 'predict_proba'):
            # Return probability of positive class
            def predict_fn(X):
                proba = self.model.predict_proba(X)
                if len(proba.shape) == 2:
                    return proba[:, 1]
                return proba
            return predict_fn
        elif hasattr(self.model, 'model') and hasattr(self.model.model, 'predict_proba'):
            def predict_fn(X):
                proba = self.model.model.predict_proba(X)
                if len(proba.shape) == 2:
                    return proba[:, 1]
                return proba
            return predict_fn
        else:
            raise ValueError("Model must have predict_proba method")

    def fit(
        self,
        X_background: np.ndarray,
        check_additivity: bool = True
    ) -> 'SHAPExplainer':
        """
        Fit the SHAP explainer using background data.

        Args:
            X_background: Background data for computing expected values
            check_additivity: Whether to check SHAP additivity

        Returns:
            self (fitted explainer)
        """
        logger.info(f"Fitting SHAPExplainer on {X_background.shape[0]} background samples")

        # Get underlying model
        sklearn_model = self._get_sklearn_model()

        if self.model_type in ['random_forest', 'xgboost']:
            # Use TreeExplainer for tree-based models (fast and exact)
            try:
                self.explainer = shap.TreeExplainer(
                    sklearn_model,
                    data=X_background if X_background.shape[0] <= 500 else None,
                    feature_perturbation='interventional',
                    check_additivity=check_additivity
                )
                logger.info("Created TreeExplainer (exact)")
            except Exception as e:
                logger.warning(f"TreeExplainer failed: {e}, falling back to KernelExplainer")
                self._create_kernel_explainer(X_background)

        elif self.model_type == 'neural_network':
            # For neural networks, use DeepExplainer or KernelExplainer
            try:
                import torch
                if hasattr(self.model, 'model') and hasattr(self.model.model, 'network'):
                    # PyTorch model
                    background_tensor = torch.FloatTensor(X_background[:self.background_samples])
                    self.explainer = shap.DeepExplainer(
                        self.model.model.network,
                        background_tensor
                    )
                    logger.info("Created DeepExplainer for PyTorch model")
                else:
                    self._create_kernel_explainer(X_background)
            except Exception as e:
                logger.warning(f"DeepExplainer failed: {e}, using KernelExplainer")
                self._create_kernel_explainer(X_background)

        else:
            # Fallback to KernelExplainer (model-agnostic)
            self._create_kernel_explainer(X_background)

        # Get expected value (base rate)
        if hasattr(self.explainer, 'expected_value'):
            ev = self.explainer.expected_value
            if isinstance(ev, np.ndarray):
                self.expected_value = float(ev[1]) if len(ev) > 1 else float(ev[0])
            else:
                self.expected_value = float(ev)
        else:
            # Estimate from predictions on background
            predict_fn = self._get_predict_function()
            self.expected_value = float(np.mean(predict_fn(X_background)))

        self.is_fitted = True
        logger.info(f"SHAPExplainer fitted with expected_value={self.expected_value:.4f}")

        return self

    def _create_kernel_explainer(self, X_background: np.ndarray):
        """Create KernelExplainer (model-agnostic, slower)"""
        # Sample background if too large
        if X_background.shape[0] > self.background_samples:
            np.random.seed(42)
            idx = np.random.choice(
                X_background.shape[0],
                self.background_samples,
                replace=False
            )
            X_bg = X_background[idx]
        else:
            X_bg = X_background

        predict_fn = self._get_predict_function()

        self.explainer = shap.KernelExplainer(
            predict_fn,
            shap.kmeans(X_bg, min(10, len(X_bg)))  # Use k-means summary
        )
        logger.info("Created KernelExplainer (model-agnostic)")

    def compute_shap_values(
        self,
        X: np.ndarray,
        check_additivity: bool = False
    ) -> np.ndarray:
        """
        Compute SHAP values for samples.

        Args:
            X: Feature matrix (n_samples, n_features)
            check_additivity: Whether to verify SHAP additivity

        Returns:
            SHAP values array (n_samples, n_features)
        """
        if not self.is_fitted:
            raise RuntimeError("Explainer not fitted. Call fit() first.")

        # Ensure 2D
        X = np.atleast_2d(X)

        # Compute SHAP values
        if isinstance(self.explainer, shap.KernelExplainer):
            shap_values = self.explainer.shap_values(X, nsamples=100)
        else:
            shap_values = self.explainer.shap_values(X, check_additivity=check_additivity)

        # Handle binary classification (returns list of 2 arrays)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]  # Positive class SHAP values

        return shap_values

    def explain_prediction(
        self,
        X: np.ndarray,
        tender_id: str,
        top_n: int = 15
    ) -> SHAPLocalExplanation:
        """
        Generate detailed explanation for a single prediction.

        Args:
            X: Feature vector (1D or 2D with single row)
            tender_id: Tender identifier
            top_n: Number of top features to include

        Returns:
            SHAPLocalExplanation with detailed breakdown
        """
        X = np.atleast_2d(X)
        if X.shape[0] != 1:
            X = X[:1]

        # Get SHAP values
        shap_values = self.compute_shap_values(X)[0]

        # Get prediction
        predict_fn = self._get_predict_function()
        predicted_prob = float(predict_fn(X)[0])

        # Get feature names
        feature_names = self.feature_names or [f"feature_{i}" for i in range(len(shap_values))]

        # Create feature contributions
        contributions = []
        total_abs_shap = np.sum(np.abs(shap_values)) + 1e-10

        # Sort by absolute SHAP value
        indices = np.argsort(-np.abs(shap_values))

        for rank, idx in enumerate(indices, 1):
            shap_val = shap_values[idx]
            feature_val = X[0, idx]

            contributions.append(SHAPFeatureContribution(
                feature_name=feature_names[idx],
                feature_value=float(feature_val),
                shap_value=float(shap_val),
                direction='increases_risk' if shap_val > 0 else 'decreases_risk',
                importance_rank=rank,
                relative_contribution=float(abs(shap_val) / total_abs_shap)
            ))

        # Generate summary
        summary = self._generate_local_summary(
            tender_id, predicted_prob, self.expected_value, contributions[:5]
        )

        # Prepare plot data
        plot_data = {
            'shap_values': shap_values.tolist(),
            'feature_values': X[0].tolist(),
            'feature_names': feature_names,
            'expected_value': self.expected_value,
            'predicted_value': predicted_prob
        }

        return SHAPLocalExplanation(
            tender_id=tender_id,
            predicted_probability=predicted_prob,
            base_value=self.expected_value,
            shap_values=shap_values.tolist(),
            top_contributions=contributions[:top_n],
            summary=summary,
            plot_data=plot_data
        )

    def _generate_local_summary(
        self,
        tender_id: str,
        predicted_prob: float,
        base_value: float,
        top_contributions: List[SHAPFeatureContribution]
    ) -> str:
        """Generate human-readable summary for local explanation"""
        deviation = predicted_prob - base_value

        if predicted_prob >= 0.7:
            risk_level = "high"
            risk_desc = "significantly elevated"
        elif predicted_prob >= 0.4:
            risk_level = "moderate"
            risk_desc = "elevated"
        elif predicted_prob >= 0.2:
            risk_level = "low"
            risk_desc = "slightly elevated"
        else:
            risk_level = "minimal"
            risk_desc = "normal"

        parts = [
            f"Tender {tender_id} has a {risk_level} risk score of {predicted_prob:.1%}. "
            f"This is {abs(deviation):+.1%} from the baseline of {base_value:.1%}."
        ]

        # Describe top risk factors
        risk_increasing = [c for c in top_contributions if c.direction == 'increases_risk']
        risk_decreasing = [c for c in top_contributions if c.direction == 'decreases_risk']

        if risk_increasing:
            factors = [c.feature_name for c in risk_increasing[:3]]
            parts.append(f"Key risk factors: {', '.join(factors)}.")

        if risk_decreasing and predicted_prob < 0.5:
            factors = [c.feature_name for c in risk_decreasing[:2]]
            parts.append(f"Protective factors: {', '.join(factors)}.")

        return " ".join(parts)

    def global_explanation(
        self,
        X: np.ndarray,
        compute_interactions: bool = False
    ) -> SHAPGlobalExplanation:
        """
        Generate global feature importance across multiple samples.

        Args:
            X: Feature matrix (n_samples, n_features)
            compute_interactions: Whether to compute feature interactions

        Returns:
            SHAPGlobalExplanation with aggregated importances
        """
        logger.info(f"Computing global SHAP explanation for {X.shape[0]} samples")

        # Compute SHAP values
        shap_values = self.compute_shap_values(X)

        # Feature names
        feature_names = self.feature_names or [f"feature_{i}" for i in range(shap_values.shape[1])]

        # Mean absolute SHAP values
        mean_abs_shap = np.mean(np.abs(shap_values), axis=0)

        # Create feature importance dict
        importance_dict = {
            name: float(imp)
            for name, imp in zip(feature_names, mean_abs_shap)
        }

        # Ranking
        ranking = sorted(
            zip(feature_names, mean_abs_shap),
            key=lambda x: -x[1]
        )

        # Interactions (optional, expensive)
        interactions = None
        if compute_interactions and hasattr(self.explainer, 'shap_interaction_values'):
            try:
                logger.info("Computing SHAP interaction values...")
                interaction_values = self.explainer.shap_interaction_values(X[:100])

                # Get top interactions
                if isinstance(interaction_values, list):
                    interaction_values = interaction_values[1]

                # Mean absolute interaction
                mean_interactions = np.mean(np.abs(interaction_values), axis=0)

                # Get top off-diagonal interactions
                interactions = {}
                for i, name_i in enumerate(feature_names[:20]):
                    interactions[name_i] = {}
                    for j, name_j in enumerate(feature_names[:20]):
                        if i != j:
                            interactions[name_i][name_j] = float(mean_interactions[i, j])

            except Exception as e:
                logger.warning(f"Failed to compute interactions: {e}")

        # Generate summary
        summary = self._generate_global_summary(X.shape[0], ranking[:10])

        # Plot data
        plot_data = {
            'mean_abs_shap': mean_abs_shap.tolist(),
            'feature_names': feature_names,
            'shap_values': shap_values.tolist() if shap_values.shape[0] <= 500 else None
        }

        return SHAPGlobalExplanation(
            n_samples=X.shape[0],
            mean_abs_shap=importance_dict,
            feature_importance_ranking=[(name, float(imp)) for name, imp in ranking],
            interaction_effects=interactions,
            summary=summary,
            plot_data=plot_data
        )

    def _generate_global_summary(
        self,
        n_samples: int,
        top_features: List[Tuple[str, float]]
    ) -> str:
        """Generate summary for global explanation"""
        total_importance = sum(imp for _, imp in top_features)

        top_3 = [name for name, _ in top_features[:3]]
        top_3_pct = sum(imp for _, imp in top_features[:3]) / total_importance * 100

        return (
            f"Analysis of {n_samples} tenders shows the top 3 risk factors are: "
            f"{', '.join(top_3)}. "
            f"Together they account for {top_3_pct:.0f}% of the model's decision-making."
        )

    def explain_batch(
        self,
        X: np.ndarray,
        tender_ids: List[str],
        top_n: int = 10
    ) -> List[SHAPLocalExplanation]:
        """
        Generate explanations for multiple predictions.

        Args:
            X: Feature matrix (n_samples, n_features)
            tender_ids: List of tender IDs
            top_n: Top features per explanation

        Returns:
            List of SHAPLocalExplanation objects
        """
        if len(tender_ids) != X.shape[0]:
            raise ValueError("Number of tender_ids must match number of samples")

        explanations = []
        for i, tender_id in enumerate(tender_ids):
            exp = self.explain_prediction(X[i:i+1], tender_id, top_n)
            explanations.append(exp)

        return explanations

    # =========================================================================
    # PLOTTING METHODS
    # =========================================================================

    def plot_waterfall(
        self,
        X: np.ndarray,
        tender_id: str = "",
        save_path: Optional[str] = None,
        max_display: int = 15
    ) -> Optional[bytes]:
        """
        Generate SHAP waterfall plot for a single prediction.

        Args:
            X: Single feature vector
            tender_id: Tender ID for title
            save_path: Path to save plot (optional)
            max_display: Maximum features to display

        Returns:
            PNG bytes if save_path is None, else None
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for plotting")
            return None

        X = np.atleast_2d(X)[:1]
        shap_values = self.compute_shap_values(X)

        # Create SHAP Explanation object
        feature_names = self.feature_names or [f"f{i}" for i in range(X.shape[1])]

        exp = shap.Explanation(
            values=shap_values[0],
            base_values=self.expected_value,
            data=X[0],
            feature_names=feature_names
        )

        # Create figure
        fig, ax = plt.subplots(figsize=(12, 8))
        shap.plots.waterfall(exp, max_display=max_display, show=False)

        if tender_id:
            plt.title(f"SHAP Waterfall: {tender_id}", fontsize=14)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return None
        else:
            import io
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            buf.seek(0)
            return buf.read()

    def plot_force(
        self,
        X: np.ndarray,
        tender_id: str = "",
        save_path: Optional[str] = None
    ) -> Optional[str]:
        """
        Generate SHAP force plot (interactive HTML).

        Args:
            X: Single feature vector
            tender_id: Tender ID for title
            save_path: Path to save HTML (optional)

        Returns:
            HTML string if save_path is None
        """
        X = np.atleast_2d(X)[:1]
        shap_values = self.compute_shap_values(X)

        feature_names = self.feature_names or [f"f{i}" for i in range(X.shape[1])]

        # Generate force plot HTML
        force_plot = shap.force_plot(
            self.expected_value,
            shap_values[0],
            X[0],
            feature_names=feature_names,
            matplotlib=False
        )

        html = shap.getjs() + force_plot.html()

        if save_path:
            with open(save_path, 'w') as f:
                f.write(f"<html><head><title>SHAP Force Plot: {tender_id}</title></head><body>")
                f.write(html)
                f.write("</body></html>")
            return None

        return html

    def plot_summary(
        self,
        X: np.ndarray,
        save_path: Optional[str] = None,
        plot_type: str = "dot",
        max_display: int = 20
    ) -> Optional[bytes]:
        """
        Generate SHAP summary plot (beeswarm or bar).

        Args:
            X: Feature matrix
            save_path: Path to save plot
            plot_type: 'dot' (beeswarm) or 'bar'
            max_display: Maximum features to show

        Returns:
            PNG bytes if save_path is None
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for plotting")
            return None

        shap_values = self.compute_shap_values(X)
        feature_names = self.feature_names or [f"f{i}" for i in range(X.shape[1])]

        fig, ax = plt.subplots(figsize=(12, 10))

        if plot_type == "bar":
            shap.summary_plot(
                shap_values,
                X,
                feature_names=feature_names,
                plot_type="bar",
                max_display=max_display,
                show=False
            )
        else:
            shap.summary_plot(
                shap_values,
                X,
                feature_names=feature_names,
                max_display=max_display,
                show=False
            )

        plt.title("Global Feature Importance (SHAP)", fontsize=14)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return None
        else:
            import io
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            buf.seek(0)
            return buf.read()

    def plot_dependence(
        self,
        X: np.ndarray,
        feature: str,
        interaction_feature: Optional[str] = None,
        save_path: Optional[str] = None
    ) -> Optional[bytes]:
        """
        Generate SHAP dependence plot for a feature.

        Args:
            X: Feature matrix
            feature: Feature name to analyze
            interaction_feature: Feature for interaction coloring
            save_path: Path to save plot

        Returns:
            PNG bytes if save_path is None
        """
        if not MATPLOTLIB_AVAILABLE:
            logger.warning("matplotlib not available for plotting")
            return None

        shap_values = self.compute_shap_values(X)
        feature_names = self.feature_names or [f"f{i}" for i in range(X.shape[1])]

        # Find feature index
        if feature in feature_names:
            feature_idx = feature_names.index(feature)
        else:
            feature_idx = int(feature.replace('feature_', ''))

        fig, ax = plt.subplots(figsize=(10, 6))

        shap.dependence_plot(
            feature_idx,
            shap_values,
            X,
            feature_names=feature_names,
            interaction_index=interaction_feature,
            show=False
        )

        plt.title(f"SHAP Dependence: {feature}", fontsize=14)
        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, bbox_inches='tight')
            plt.close()
            return None
        else:
            import io
            buf = io.BytesIO()
            plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
            plt.close()
            buf.seek(0)
            return buf.read()


# =============================================================================
# HELPER FUNCTIONS FOR API INTEGRATION
# =============================================================================

def create_shap_explainer_for_model(
    model_type: str,
    model_path: str,
    feature_names: List[str],
    X_background: Optional[np.ndarray] = None
) -> SHAPExplainer:
    """
    Create a SHAP explainer for a saved model.

    Args:
        model_type: 'random_forest' or 'xgboost'
        model_path: Path to saved model
        feature_names: List of feature names
        X_background: Background data (required for fitting)

    Returns:
        Fitted SHAPExplainer
    """
    if model_type == 'random_forest':
        from ai.corruption.ml_models.random_forest import CorruptionRandomForest
        model = CorruptionRandomForest.load(model_path)
    elif model_type == 'xgboost':
        from ai.corruption.ml_models.xgboost_model import CorruptionXGBoost
        model = CorruptionXGBoost.load(model_path)
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    explainer = SHAPExplainer(model, feature_names=feature_names)

    if X_background is not None:
        explainer.fit(X_background)

    return explainer


def format_shap_for_api(
    explanation: Union[SHAPLocalExplanation, SHAPGlobalExplanation]
) -> Dict[str, Any]:
    """
    Format SHAP explanation for API response.

    Removes large arrays and prepares for JSON serialization.
    """
    data = explanation.to_dict()

    # Remove large arrays that shouldn't be in API response
    if 'plot_data' in data:
        plot_data = data['plot_data']
        if plot_data:
            # Keep only essential plot data
            if 'shap_values' in plot_data and plot_data['shap_values']:
                # Truncate if too many samples
                if isinstance(plot_data['shap_values'], list) and len(plot_data['shap_values']) > 100:
                    plot_data['shap_values'] = None
                    plot_data['note'] = 'SHAP values truncated for API response'

    if 'shap_values' in data:
        # Keep summary only
        data['shap_values_summary'] = {
            'count': len(data['shap_values']),
            'mean': float(np.mean(data['shap_values'])),
            'std': float(np.std(data['shap_values'])),
            'min': float(np.min(data['shap_values'])),
            'max': float(np.max(data['shap_values']))
        }
        del data['shap_values']

    return data
