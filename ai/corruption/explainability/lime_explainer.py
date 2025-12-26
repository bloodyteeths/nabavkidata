"""
LIME Explainability for Corruption Detection Models

This module provides LIME (Local Interpretable Model-agnostic Explanations)
for explaining individual predictions from corruption detection models.
LIME creates local linear approximations to explain complex model behavior.

Features:
- Model-agnostic explanations (works with any classifier)
- Human-readable feature contributions
- Confidence intervals for feature importance
- Text-based explanation generation
- Counterfactual suggestions
- API-ready explanation formatting

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any, Union, Callable
from dataclasses import dataclass, field
from datetime import datetime
import warnings

logger = logging.getLogger(__name__)

# Try to import LIME
try:
    import lime
    import lime.lime_tabular
    LIME_AVAILABLE = True
except ImportError:
    LIME_AVAILABLE = False
    lime = None
    logger.warning("LIME not installed. Install with: pip install lime")

# Feature descriptions for human-readable explanations
FEATURE_HUMAN_NAMES = {
    # Competition
    'num_bidders': 'Number of bidders',
    'single_bidder': 'Single bidder only',
    'no_bidders': 'No bidders participated',
    'two_bidders': 'Only two bidders',
    'bidders_vs_institution_avg': 'Bidders vs institution average',
    'bidders_vs_category_avg': 'Bidders vs category average',
    'num_disqualified': 'Disqualified bidders',
    'disqualification_rate': 'Disqualification rate',
    'winner_rank': 'Winner price rank',
    'winner_not_lowest': 'Winner not lowest bidder',
    'market_concentration_hhi': 'Market concentration (HHI)',

    # Price
    'price_vs_estimate_ratio': 'Price vs estimate ratio',
    'price_deviation_from_estimate': 'Price deviation from estimate',
    'price_above_estimate': 'Price above estimate',
    'price_below_estimate': 'Price below estimate',
    'price_exact_match_estimate': 'Price exactly matches estimate',
    'price_very_close_estimate': 'Price very close to estimate',
    'bid_coefficient_of_variation': 'Bid variance coefficient',
    'bid_low_variance': 'Low bid variance',
    'bid_very_low_variance': 'Very low bid variance',
    'winner_bid_z_score': 'Winner bid z-score',

    # Timing
    'deadline_days': 'Deadline length (days)',
    'deadline_very_short': 'Very short deadline',
    'deadline_short': 'Short deadline',
    'pub_friday': 'Published on Friday',
    'pub_weekend': 'Published on weekend',
    'pub_end_of_year': 'End of year publication',
    'amendment_count': 'Number of amendments',
    'amendment_very_late': 'Very late amendment',

    # Relationship
    'winner_prev_wins_at_institution': 'Winner previous wins',
    'winner_win_rate_at_institution': 'Winner win rate at institution',
    'winner_high_win_rate': 'High winner win rate',
    'winner_very_high_win_rate': 'Very high winner win rate',
    'winner_market_share_at_institution': 'Winner market share',
    'winner_dominant_supplier': 'Dominant supplier',
    'winner_new_supplier': 'New supplier',
    'has_related_bidders': 'Related bidders present',
    'all_bidders_related': 'All bidders related',
    'institution_single_bidder_rate': 'Institution single bidder rate',

    # Procedural
    'has_lots': 'Multiple lots',
    'num_lots': 'Number of lots',
    'has_security_deposit': 'Security deposit required',
    'eval_lowest_price': 'Lowest price evaluation',

    # Document
    'num_documents': 'Number of documents',
    'doc_extraction_success_rate': 'Document extraction rate',
    'has_specification': 'Has specification document',
    'has_contract': 'Has contract document'
}


@dataclass
class LIMEFeatureContribution:
    """
    Contribution of a single feature to a LIME explanation.

    Attributes:
        feature_name: Technical feature name
        human_name: Human-readable feature name
        feature_value: Actual value of the feature
        weight: LIME weight (importance)
        direction: 'increases_risk' or 'decreases_risk'
        rule: Human-readable rule (e.g., "num_bidders <= 1.5")
        confidence_low: Lower bound of confidence interval
        confidence_high: Upper bound of confidence interval
    """
    feature_name: str
    human_name: str
    feature_value: float
    weight: float
    direction: str
    rule: str
    confidence_low: Optional[float] = None
    confidence_high: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            'feature_name': self.feature_name,
            'human_name': self.human_name,
            'feature_value': float(self.feature_value),
            'weight': float(self.weight),
            'direction': self.direction,
            'rule': self.rule,
            'confidence_low': float(self.confidence_low) if self.confidence_low else None,
            'confidence_high': float(self.confidence_high) if self.confidence_high else None
        }

    def to_human_readable(self) -> str:
        """Generate human-readable explanation for this contribution"""
        impact = "increases" if self.direction == 'increases_risk' else "decreases"
        strength = abs(self.weight)

        if strength > 0.1:
            intensity = "strongly"
        elif strength > 0.05:
            intensity = "moderately"
        else:
            intensity = "slightly"

        return f"{self.human_name} ({self.feature_value:.2f}) {intensity} {impact} risk"


@dataclass
class LIMEExplanation:
    """
    Complete LIME explanation for a single prediction.

    Attributes:
        tender_id: Tender identifier
        predicted_probability: Model's predicted probability
        prediction_class: 0 (normal) or 1 (suspicious)
        local_prediction: LIME's local model prediction
        intercept: LIME local model intercept
        contributions: Feature contributions sorted by importance
        explanation_text: Human-readable explanation
        counterfactual_suggestions: Suggestions for what would change prediction
        model_fidelity: How well LIME approximates the model locally
        generated_at: Timestamp
    """
    tender_id: str
    predicted_probability: float
    prediction_class: int
    local_prediction: float
    intercept: float
    contributions: List[LIMEFeatureContribution]
    explanation_text: str
    counterfactual_suggestions: List[str]
    model_fidelity: float
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tender_id': self.tender_id,
            'predicted_probability': float(self.predicted_probability),
            'prediction_class': self.prediction_class,
            'local_prediction': float(self.local_prediction),
            'intercept': float(self.intercept),
            'contributions': [c.to_dict() for c in self.contributions],
            'explanation_text': self.explanation_text,
            'counterfactual_suggestions': self.counterfactual_suggestions,
            'model_fidelity': float(self.model_fidelity),
            'generated_at': self.generated_at.isoformat()
        }

    def to_markdown(self) -> str:
        """Generate markdown explanation"""
        lines = [
            f"## LIME Explanation: {self.tender_id}",
            "",
            f"**Predicted Risk:** {self.predicted_probability:.1%}",
            f"**Classification:** {'Suspicious' if self.prediction_class == 1 else 'Normal'}",
            f"**Model Fidelity:** {self.model_fidelity:.1%}",
            "",
            "### Why This Prediction?",
            "",
            self.explanation_text,
            "",
            "### Feature Contributions",
            ""
        ]

        for contrib in self.contributions[:10]:
            emoji = "+" if contrib.weight > 0 else "-"
            lines.append(f"- {emoji} **{contrib.human_name}**: {contrib.rule}")

        if self.counterfactual_suggestions:
            lines.extend([
                "",
                "### What Would Change This?",
                ""
            ])
            for suggestion in self.counterfactual_suggestions[:5]:
                lines.append(f"- {suggestion}")

        return "\n".join(lines)

    def to_api_response(self) -> Dict[str, Any]:
        """Format for API response (shorter version)"""
        return {
            'tender_id': self.tender_id,
            'risk_probability': float(self.predicted_probability),
            'risk_level': 'high' if self.predicted_probability >= 0.7 else
                         'medium' if self.predicted_probability >= 0.4 else
                         'low' if self.predicted_probability >= 0.2 else 'minimal',
            'explanation': self.explanation_text,
            'top_factors': [
                {
                    'factor': c.human_name,
                    'impact': c.direction.replace('_', ' '),
                    'value': c.feature_value
                }
                for c in self.contributions[:5]
            ],
            'counterfactuals': self.counterfactual_suggestions[:3],
            'confidence': self.model_fidelity
        }


class LIMEExplainer:
    """
    LIME-based explainer for corruption detection models.

    LIME (Local Interpretable Model-agnostic Explanations) explains individual
    predictions by fitting a simple linear model in the neighborhood of the
    prediction.

    Usage:
        from ai.corruption.ml_models import CorruptionRandomForest

        # Load model
        model = CorruptionRandomForest.load('model.joblib')

        # Create explainer
        explainer = LIMEExplainer(model, feature_names=feature_names)
        explainer.fit(X_train)

        # Explain prediction
        explanation = explainer.explain_prediction(X_test[0], tender_id='123/2024')

        # Get human-readable explanation
        print(explanation.explanation_text)

        # Get counterfactual suggestions
        print(explanation.counterfactual_suggestions)
    """

    def __init__(
        self,
        model: Any,
        feature_names: Optional[List[str]] = None,
        categorical_features: Optional[List[int]] = None,
        class_names: Optional[List[str]] = None,
        discretize_continuous: bool = True,
        random_state: int = 42
    ):
        """
        Initialize LIME explainer.

        Args:
            model: Trained classifier with predict_proba method
            feature_names: Names of features
            categorical_features: Indices of categorical features
            class_names: Names of classes (e.g., ['Normal', 'Suspicious'])
            discretize_continuous: Whether to discretize continuous features
            random_state: Random seed
        """
        if not LIME_AVAILABLE:
            raise ImportError(
                "LIME is required for this explainer. "
                "Install with: pip install lime"
            )

        self.model = model
        self.feature_names = feature_names
        self.categorical_features = categorical_features or []
        self.class_names = class_names or ['Normal', 'Suspicious']
        self.discretize_continuous = discretize_continuous
        self.random_state = random_state

        # Will be set during fit
        self.lime_explainer: Optional[lime.lime_tabular.LimeTabularExplainer] = None
        self.training_stats: Dict[str, Any] = {}
        self.is_fitted = False

        logger.info("LIMEExplainer initialized")

    def _get_predict_function(self) -> Callable:
        """Get prediction function that returns probabilities"""
        if hasattr(self.model, 'predict_proba'):
            return self.model.predict_proba
        elif hasattr(self.model, 'model') and hasattr(self.model.model, 'predict_proba'):
            return self.model.model.predict_proba
        else:
            raise ValueError("Model must have predict_proba method")

    def fit(
        self,
        X_train: np.ndarray,
        mode: str = 'classification',
        kernel_width: Optional[float] = None
    ) -> 'LIMEExplainer':
        """
        Fit the LIME explainer using training data.

        Args:
            X_train: Training data for building feature statistics
            mode: 'classification' or 'regression'
            kernel_width: Width of exponential kernel (None for auto)

        Returns:
            self (fitted explainer)
        """
        logger.info(f"Fitting LIMEExplainer on {X_train.shape[0]} training samples")

        # Infer feature names if not provided
        if self.feature_names is None:
            self.feature_names = [f"feature_{i}" for i in range(X_train.shape[1])]

        # Create LIME explainer
        self.lime_explainer = lime.lime_tabular.LimeTabularExplainer(
            training_data=X_train,
            feature_names=self.feature_names,
            class_names=self.class_names,
            categorical_features=self.categorical_features,
            discretize_continuous=self.discretize_continuous,
            mode=mode,
            random_state=self.random_state,
            kernel_width=kernel_width
        )

        # Store training statistics for counterfactual generation
        self.training_stats = {
            'mean': np.mean(X_train, axis=0),
            'std': np.std(X_train, axis=0),
            'min': np.min(X_train, axis=0),
            'max': np.max(X_train, axis=0),
            'percentiles': {
                25: np.percentile(X_train, 25, axis=0),
                50: np.percentile(X_train, 50, axis=0),
                75: np.percentile(X_train, 75, axis=0)
            }
        }

        self.is_fitted = True
        logger.info("LIMEExplainer fitted successfully")

        return self

    def explain_prediction(
        self,
        X: np.ndarray,
        tender_id: str,
        num_features: int = 15,
        num_samples: int = 5000,
        generate_counterfactuals: bool = True
    ) -> LIMEExplanation:
        """
        Generate LIME explanation for a single prediction.

        Args:
            X: Feature vector (1D or 2D with single row)
            tender_id: Tender identifier
            num_features: Number of features to include in explanation
            num_samples: Number of samples for LIME perturbation
            generate_counterfactuals: Whether to generate counterfactual suggestions

        Returns:
            LIMEExplanation with detailed breakdown
        """
        if not self.is_fitted:
            raise RuntimeError("Explainer not fitted. Call fit() first.")

        X = np.atleast_1d(X).flatten()

        # Get model prediction
        predict_fn = self._get_predict_function()
        proba = predict_fn(X.reshape(1, -1))[0]

        if len(proba) == 2:
            predicted_prob = proba[1]  # Probability of suspicious class
        else:
            predicted_prob = proba[0]

        prediction_class = 1 if predicted_prob >= 0.5 else 0

        # Generate LIME explanation
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")

            lime_exp = self.lime_explainer.explain_instance(
                X,
                predict_fn,
                num_features=num_features,
                num_samples=num_samples,
                top_labels=1
            )

        # Extract explanation for the predicted class
        if prediction_class in lime_exp.as_map():
            feature_weights = lime_exp.as_map()[prediction_class]
        else:
            # Use first available label
            feature_weights = lime_exp.as_map()[list(lime_exp.as_map().keys())[0]]

        # Get local prediction and intercept
        local_pred = lime_exp.local_pred[0] if hasattr(lime_exp, 'local_pred') else predicted_prob
        intercept = lime_exp.intercept.get(prediction_class, 0) if hasattr(lime_exp, 'intercept') else 0

        # Build contributions list
        contributions = []
        for feature_idx, weight in sorted(feature_weights, key=lambda x: -abs(x[1])):
            feature_name = self.feature_names[feature_idx]
            feature_value = X[feature_idx]

            # Get human-readable name
            human_name = FEATURE_HUMAN_NAMES.get(feature_name, feature_name.replace('_', ' ').title())

            # Get the rule from LIME
            try:
                rule = lime_exp.domain_mapper.discretized_feature_names[feature_idx]
            except (AttributeError, IndexError, KeyError):
                # Generate rule from feature value
                rule = f"{human_name} = {feature_value:.2f}"

            contributions.append(LIMEFeatureContribution(
                feature_name=feature_name,
                human_name=human_name,
                feature_value=float(feature_value),
                weight=float(weight),
                direction='increases_risk' if weight > 0 else 'decreases_risk',
                rule=rule
            ))

        # Calculate model fidelity (R^2 score of local model)
        model_fidelity = lime_exp.score if hasattr(lime_exp, 'score') else 0.0

        # Generate human-readable explanation
        explanation_text = self._generate_explanation_text(
            tender_id, predicted_prob, contributions[:5]
        )

        # Generate counterfactual suggestions
        counterfactuals = []
        if generate_counterfactuals:
            counterfactuals = self._generate_counterfactuals(X, contributions[:5], predicted_prob)

        return LIMEExplanation(
            tender_id=tender_id,
            predicted_probability=float(predicted_prob),
            prediction_class=prediction_class,
            local_prediction=float(local_pred),
            intercept=float(intercept),
            contributions=contributions[:num_features],
            explanation_text=explanation_text,
            counterfactual_suggestions=counterfactuals,
            model_fidelity=float(model_fidelity)
        )

    def _generate_explanation_text(
        self,
        tender_id: str,
        predicted_prob: float,
        top_contributions: List[LIMEFeatureContribution]
    ) -> str:
        """Generate human-readable explanation text"""
        # Determine risk level
        if predicted_prob >= 0.7:
            risk_desc = "high risk"
            action = "requires detailed investigation"
        elif predicted_prob >= 0.4:
            risk_desc = "moderate risk"
            action = "warrants further review"
        elif predicted_prob >= 0.2:
            risk_desc = "low risk"
            action = "shows minor anomalies"
        else:
            risk_desc = "minimal risk"
            action = "appears normal"

        parts = [
            f"Tender {tender_id} is classified as {risk_desc} ({predicted_prob:.0%}) and {action}."
        ]

        # Group contributions by direction
        risk_factors = [c for c in top_contributions if c.direction == 'increases_risk']
        protective_factors = [c for c in top_contributions if c.direction == 'decreases_risk']

        if risk_factors:
            factors_text = ", ".join([c.human_name.lower() for c in risk_factors[:3]])
            parts.append(f"The main risk factors are: {factors_text}.")

        if protective_factors and predicted_prob < 0.5:
            factors_text = ", ".join([c.human_name.lower() for c in protective_factors[:2]])
            parts.append(f"Mitigating factors include: {factors_text}.")

        return " ".join(parts)

    def _generate_counterfactuals(
        self,
        X: np.ndarray,
        top_contributions: List[LIMEFeatureContribution],
        current_prob: float
    ) -> List[str]:
        """Generate counterfactual suggestions"""
        suggestions = []

        target_direction = 'decreases_risk' if current_prob >= 0.5 else 'increases_risk'

        for contrib in top_contributions:
            feature_idx = self.feature_names.index(contrib.feature_name)
            current_value = X[feature_idx]

            # Skip binary features that can't be changed easily
            if contrib.feature_name.startswith(('has_', 'is_', 'single_', 'no_')):
                continue

            # Generate suggestion based on training statistics
            mean_val = self.training_stats['mean'][feature_idx]
            std_val = self.training_stats['std'][feature_idx]

            if contrib.direction == target_direction:
                # This factor is already helping - skip
                continue

            # Suggest moving toward the opposite of current direction
            if contrib.weight > 0:
                # Feature increases risk, suggest decreasing
                target = max(mean_val - std_val, self.training_stats['min'][feature_idx])
                action = "decreasing"
            else:
                # Feature decreases risk, suggest increasing
                target = min(mean_val + std_val, self.training_stats['max'][feature_idx])
                action = "increasing"

            human_name = contrib.human_name
            suggestion = f"Consider {action} {human_name.lower()} from {current_value:.2f} to ~{target:.2f}"
            suggestions.append(suggestion)

            if len(suggestions) >= 5:
                break

        return suggestions

    def explain_batch(
        self,
        X: np.ndarray,
        tender_ids: List[str],
        num_features: int = 10,
        num_samples: int = 1000
    ) -> List[LIMEExplanation]:
        """
        Generate explanations for multiple predictions.

        Args:
            X: Feature matrix (n_samples, n_features)
            tender_ids: List of tender IDs
            num_features: Features per explanation
            num_samples: LIME samples per prediction (reduced for batch)

        Returns:
            List of LIMEExplanation objects
        """
        if len(tender_ids) != X.shape[0]:
            raise ValueError("Number of tender_ids must match number of samples")

        explanations = []
        for i, tender_id in enumerate(tender_ids):
            try:
                exp = self.explain_prediction(
                    X[i],
                    tender_id,
                    num_features=num_features,
                    num_samples=num_samples,
                    generate_counterfactuals=False  # Skip for batch efficiency
                )
                explanations.append(exp)
            except Exception as e:
                logger.warning(f"Failed to explain {tender_id}: {e}")
                # Create minimal explanation
                explanations.append(LIMEExplanation(
                    tender_id=tender_id,
                    predicted_probability=0.0,
                    prediction_class=0,
                    local_prediction=0.0,
                    intercept=0.0,
                    contributions=[],
                    explanation_text=f"Explanation failed: {str(e)}",
                    counterfactual_suggestions=[],
                    model_fidelity=0.0
                ))

        return explanations

    def compare_predictions(
        self,
        X1: np.ndarray,
        X2: np.ndarray,
        tender_id1: str,
        tender_id2: str
    ) -> Dict[str, Any]:
        """
        Compare explanations for two predictions.

        Useful for understanding why similar tenders get different risk scores.

        Args:
            X1, X2: Feature vectors to compare
            tender_id1, tender_id2: Tender identifiers

        Returns:
            Comparison dict with differences
        """
        exp1 = self.explain_prediction(X1, tender_id1)
        exp2 = self.explain_prediction(X2, tender_id2)

        # Find feature differences
        contrib_map1 = {c.feature_name: c for c in exp1.contributions}
        contrib_map2 = {c.feature_name: c for c in exp2.contributions}

        all_features = set(contrib_map1.keys()) | set(contrib_map2.keys())

        differences = []
        for feature in all_features:
            c1 = contrib_map1.get(feature)
            c2 = contrib_map2.get(feature)

            if c1 and c2:
                weight_diff = abs(c1.weight - c2.weight)
                if weight_diff > 0.01:  # Significant difference
                    differences.append({
                        'feature': feature,
                        'human_name': c1.human_name,
                        'value1': c1.feature_value,
                        'value2': c2.feature_value,
                        'weight1': c1.weight,
                        'weight2': c2.weight,
                        'weight_difference': weight_diff
                    })

        differences.sort(key=lambda x: -x['weight_difference'])

        return {
            'tender1': {
                'id': tender_id1,
                'probability': exp1.predicted_probability,
                'class': exp1.prediction_class
            },
            'tender2': {
                'id': tender_id2,
                'probability': exp2.predicted_probability,
                'class': exp2.prediction_class
            },
            'probability_difference': abs(exp1.predicted_probability - exp2.predicted_probability),
            'top_differences': differences[:10],
            'explanation1': exp1.explanation_text,
            'explanation2': exp2.explanation_text
        }


# =============================================================================
# HELPER FUNCTIONS FOR API INTEGRATION
# =============================================================================

def create_lime_explainer_for_model(
    model: Any,
    feature_names: List[str],
    X_train: np.ndarray
) -> LIMEExplainer:
    """
    Create and fit a LIME explainer for a model.

    Args:
        model: Trained classifier
        feature_names: Feature names
        X_train: Training data for fitting

    Returns:
        Fitted LIMEExplainer
    """
    explainer = LIMEExplainer(model, feature_names=feature_names)
    explainer.fit(X_train)
    return explainer


def format_lime_for_api(explanation: LIMEExplanation) -> Dict[str, Any]:
    """
    Format LIME explanation for API response.

    Args:
        explanation: LIME explanation object

    Returns:
        Dict formatted for API response
    """
    return explanation.to_api_response()


def generate_investigation_report(
    explanations: List[LIMEExplanation],
    title: str = "Corruption Risk Investigation Report"
) -> str:
    """
    Generate a markdown investigation report from multiple explanations.

    Args:
        explanations: List of LIME explanations
        title: Report title

    Returns:
        Markdown formatted report
    """
    lines = [
        f"# {title}",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"Tenders Analyzed: {len(explanations)}",
        "",
        "## Summary",
        ""
    ]

    # Categorize by risk
    high_risk = [e for e in explanations if e.predicted_probability >= 0.7]
    medium_risk = [e for e in explanations if 0.4 <= e.predicted_probability < 0.7]
    low_risk = [e for e in explanations if e.predicted_probability < 0.4]

    lines.extend([
        f"- **High Risk**: {len(high_risk)} tenders",
        f"- **Medium Risk**: {len(medium_risk)} tenders",
        f"- **Low Risk**: {len(low_risk)} tenders",
        ""
    ])

    # Aggregate top factors
    factor_counts = {}
    for exp in explanations:
        for contrib in exp.contributions[:3]:
            if contrib.direction == 'increases_risk':
                factor_counts[contrib.human_name] = factor_counts.get(contrib.human_name, 0) + 1

    if factor_counts:
        lines.extend([
            "## Most Common Risk Factors",
            ""
        ])
        for factor, count in sorted(factor_counts.items(), key=lambda x: -x[1])[:10]:
            pct = count / len(explanations) * 100
            lines.append(f"- {factor}: {count} tenders ({pct:.0f}%)")

        lines.append("")

    # High risk details
    if high_risk:
        lines.extend([
            "## High Risk Tenders",
            ""
        ])

        for exp in sorted(high_risk, key=lambda x: -x.predicted_probability)[:10]:
            lines.extend([
                f"### {exp.tender_id}",
                "",
                f"**Risk Score:** {exp.predicted_probability:.0%}",
                "",
                exp.explanation_text,
                ""
            ])

            if exp.counterfactual_suggestions:
                lines.append("**Recommendations:**")
                for suggestion in exp.counterfactual_suggestions[:3]:
                    lines.append(f"- {suggestion}")
                lines.append("")

    return "\n".join(lines)
