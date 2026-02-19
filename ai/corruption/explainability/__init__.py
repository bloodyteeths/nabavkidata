"""
Explainability Layer (XAI) for Corruption Detection

This module provides interpretable explanations for corruption detection
model predictions. It offers multiple complementary explanation methods
to help investigators understand why a tender is flagged as high-risk.

Components:
- shap_explainer.py: SHAP values for global and local feature importance
  - TreeExplainer for Random Forest and XGBoost (exact, fast)
  - Global feature importance plots (summary, bar, dependence)
  - Local prediction explanations (waterfall, force plots)

- lime_explainer.py: LIME for human-readable local explanations
  - Model-agnostic local approximations
  - Human-readable rules and explanations
  - Counterfactual suggestions ("what would need to change?")

Output Formats:
- Human-readable text explanations for investigators
- Visual charts (SHAP waterfall, force plots, summary plots)
- API-ready JSON responses
- Markdown reports for documentation

Usage:
    from ai.corruption.explainability import (
        SHAPExplainer,
        LIMEExplainer,
        create_combined_explanation
    )

    # Load model
    from ai.corruption.ml_models import CorruptionRandomForest
    model = CorruptionRandomForest.load('model.joblib')

    # Create SHAP explainer
    shap_exp = SHAPExplainer(model, feature_names=features)
    shap_exp.fit(X_background)
    shap_explanation = shap_exp.explain_prediction(X_test[0], '123/2024')

    # Create LIME explainer
    lime_exp = LIMEExplainer(model, feature_names=features)
    lime_exp.fit(X_train)
    lime_explanation = lime_exp.explain_prediction(X_test[0], '123/2024')

    # Combined explanation
    combined = create_combined_explanation(shap_explanation, lime_explanation)

Author: nabavkidata.com
License: Proprietary
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# SHAP Explainer
_SHAP_AVAILABLE = False
try:
    from ai.corruption.explainability.shap_explainer import (
        SHAPExplainer,
        SHAPLocalExplanation,
        SHAPGlobalExplanation,
        SHAPFeatureContribution,
        create_shap_explainer_for_model,
        format_shap_for_api
    )
    _SHAP_AVAILABLE = True
except ImportError as e:
    logger.warning(f"SHAP explainer not available: {e}")
    SHAPExplainer = None
    SHAPLocalExplanation = None
    SHAPGlobalExplanation = None
    SHAPFeatureContribution = None
    create_shap_explainer_for_model = None
    format_shap_for_api = None

# LIME Explainer
_LIME_AVAILABLE = False
try:
    from ai.corruption.explainability.lime_explainer import (
        LIMEExplainer,
        LIMEExplanation,
        LIMEFeatureContribution,
        create_lime_explainer_for_model,
        format_lime_for_api,
        generate_investigation_report,
        FEATURE_HUMAN_NAMES
    )
    _LIME_AVAILABLE = True
except ImportError as e:
    logger.warning(f"LIME explainer not available: {e}")
    LIMEExplainer = None
    LIMEExplanation = None
    LIMEFeatureContribution = None
    create_lime_explainer_for_model = None
    format_lime_for_api = None
    generate_investigation_report = None
    FEATURE_HUMAN_NAMES = None

# API Helpers
_API_HELPERS_AVAILABLE = False
try:
    from ai.corruption.explainability.api_helpers import (
        get_tender_explanation,
        batch_explain_tenders,
        format_explanation_for_frontend,
        ExplainerCache
    )
    _API_HELPERS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"API helpers not available: {e}")
    get_tender_explanation = None
    batch_explain_tenders = None
    format_explanation_for_frontend = None
    ExplainerCache = None

# Counterfactual Engine (Phase 4.3)
_COUNTERFACTUAL_AVAILABLE = False
try:
    from ai.corruption.explainability.counterfactual_engine import CounterfactualEngine
    from ai.corruption.explainability.counterfactual_cache import CounterfactualCache
    _COUNTERFACTUAL_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Counterfactual engine not available: {e}")
    CounterfactualEngine = None
    CounterfactualCache = None


def check_explainability_dependencies() -> Dict[str, bool]:
    """
    Check which explainability dependencies are available.

    Returns:
        Dict with availability status of each component
    """
    status = {
        'shap_explainer': _SHAP_AVAILABLE,
        'lime_explainer': _LIME_AVAILABLE,
        'api_helpers': _API_HELPERS_AVAILABLE,
        'counterfactual_engine': _COUNTERFACTUAL_AVAILABLE,
        'shap_library': False,
        'lime_library': False,
        'matplotlib': False
    }

    try:
        import shap
        status['shap_library'] = True
    except ImportError:
        pass

    try:
        import lime
        status['lime_library'] = True
    except ImportError:
        pass

    try:
        import matplotlib
        status['matplotlib'] = True
    except ImportError:
        pass

    return status


def create_combined_explanation(
    shap_explanation: Optional['SHAPLocalExplanation'] = None,
    lime_explanation: Optional['LIMEExplanation'] = None,
    tender_id: str = ""
) -> Dict[str, Any]:
    """
    Combine SHAP and LIME explanations into a unified format.

    This provides a comprehensive explanation that leverages:
    - SHAP's theoretically grounded feature importance
    - LIME's human-readable rules and counterfactuals

    Args:
        shap_explanation: SHAP local explanation (optional)
        lime_explanation: LIME explanation (optional)
        tender_id: Tender identifier

    Returns:
        Combined explanation dict suitable for API response
    """
    result = {
        'tender_id': tender_id,
        'explanation_methods': [],
        'consensus_factors': [],
        'explanation_text': '',
        'recommendations': []
    }

    # Collect factors from both methods
    shap_factors = {}
    lime_factors = {}

    if shap_explanation:
        result['explanation_methods'].append('shap')
        result['predicted_probability'] = shap_explanation.predicted_probability
        result['shap'] = {
            'base_value': shap_explanation.base_value,
            'top_contributions': [
                c.to_dict() for c in shap_explanation.top_contributions[:10]
            ]
        }

        for contrib in shap_explanation.top_contributions[:10]:
            shap_factors[contrib.feature_name] = {
                'value': contrib.shap_value,
                'direction': contrib.direction,
                'rank': contrib.importance_rank
            }

    if lime_explanation:
        result['explanation_methods'].append('lime')
        if 'predicted_probability' not in result:
            result['predicted_probability'] = lime_explanation.predicted_probability

        result['lime'] = {
            'local_prediction': lime_explanation.local_prediction,
            'model_fidelity': lime_explanation.model_fidelity,
            'top_contributions': [
                c.to_dict() for c in lime_explanation.contributions[:10]
            ],
            'counterfactual_suggestions': lime_explanation.counterfactual_suggestions
        }

        result['explanation_text'] = lime_explanation.explanation_text
        result['recommendations'] = lime_explanation.counterfactual_suggestions[:5]

        for contrib in lime_explanation.contributions[:10]:
            lime_factors[contrib.feature_name] = {
                'value': contrib.weight,
                'direction': contrib.direction,
                'human_name': contrib.human_name
            }

    # Find consensus factors (appearing in both methods with same direction)
    if shap_factors and lime_factors:
        common_features = set(shap_factors.keys()) & set(lime_factors.keys())

        for feature in common_features:
            shap_dir = shap_factors[feature]['direction']
            lime_dir = lime_factors[feature]['direction']

            if shap_dir == lime_dir:
                result['consensus_factors'].append({
                    'feature': feature,
                    'human_name': lime_factors.get(feature, {}).get('human_name', feature),
                    'direction': shap_dir,
                    'shap_rank': shap_factors[feature]['rank'],
                    'confidence': 'high'  # Both methods agree
                })

        # Sort by SHAP rank
        result['consensus_factors'].sort(
            key=lambda x: x.get('shap_rank', 999)
        )

    # Generate combined explanation text if not already set
    if not result['explanation_text'] and shap_explanation:
        result['explanation_text'] = shap_explanation.summary

    return result


def get_explainer_for_model(
    model: Any,
    feature_names: List[str],
    X_background: Any,
    method: str = 'auto'
) -> Any:
    """
    Get appropriate explainer for a model.

    Args:
        model: Trained model
        feature_names: Feature names
        X_background: Background/training data
        method: 'shap', 'lime', or 'auto'

    Returns:
        Fitted explainer
    """
    if method == 'auto':
        # Prefer SHAP for tree-based models (faster, exact)
        model_name = type(model).__name__.lower()
        if 'forest' in model_name or 'xgb' in model_name or 'tree' in model_name:
            method = 'shap'
        else:
            method = 'lime'

    if method == 'shap':
        if not _SHAP_AVAILABLE:
            raise ImportError("SHAP not available. Install with: pip install shap")
        explainer = SHAPExplainer(model, feature_names=feature_names)
        explainer.fit(X_background)
        return explainer

    elif method == 'lime':
        if not _LIME_AVAILABLE:
            raise ImportError("LIME not available. Install with: pip install lime")
        explainer = LIMEExplainer(model, feature_names=feature_names)
        explainer.fit(X_background)
        return explainer

    else:
        raise ValueError(f"Unknown method: {method}. Use 'shap', 'lime', or 'auto'")


__all__ = [
    # SHAP
    'SHAPExplainer',
    'SHAPLocalExplanation',
    'SHAPGlobalExplanation',
    'SHAPFeatureContribution',
    'create_shap_explainer_for_model',
    'format_shap_for_api',

    # LIME
    'LIMEExplainer',
    'LIMEExplanation',
    'LIMEFeatureContribution',
    'create_lime_explainer_for_model',
    'format_lime_for_api',
    'generate_investigation_report',
    'FEATURE_HUMAN_NAMES',

    # API Helpers
    'get_tender_explanation',
    'batch_explain_tenders',
    'format_explanation_for_frontend',
    'ExplainerCache',

    # Counterfactual (Phase 4.3)
    'CounterfactualEngine',
    'CounterfactualCache',

    # Combined
    'check_explainability_dependencies',
    'create_combined_explanation',
    'get_explainer_for_model'
]
