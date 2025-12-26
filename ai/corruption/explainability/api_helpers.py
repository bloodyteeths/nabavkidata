"""
API Integration Helpers for Explainability

This module provides helper functions for integrating SHAP and LIME
explanations into the corruption detection API endpoints.

Features:
- Load trained models and create explainers
- Generate API-ready explanations
- Batch explanation generation
- Caching support for expensive computations
- Error handling for production use

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import logging
from typing import Dict, List, Optional, Any, Tuple, Union
from pathlib import Path
from datetime import datetime
import json
import hashlib

logger = logging.getLogger(__name__)

# Default model paths
DEFAULT_MODEL_DIR = Path(__file__).parent.parent / "ml_models" / "models"


class ExplainerCache:
    """
    Simple in-memory cache for explanations.

    In production, this should be replaced with Redis or similar.
    """

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds

    def _make_key(self, tender_id: str, method: str) -> str:
        return f"{method}:{tender_id}"

    def get(self, tender_id: str, method: str) -> Optional[Any]:
        key = self._make_key(tender_id, method)
        if key in self.cache:
            data, timestamp = self.cache[key]
            if datetime.now().timestamp() - timestamp < self.ttl_seconds:
                return data
            else:
                del self.cache[key]
        return None

    def set(self, tender_id: str, method: str, data: Any):
        if len(self.cache) >= self.max_size:
            # Remove oldest entries
            oldest_keys = sorted(
                self.cache.keys(),
                key=lambda k: self.cache[k][1]
            )[:self.max_size // 4]
            for key in oldest_keys:
                del self.cache[key]

        key = self._make_key(tender_id, method)
        self.cache[key] = (data, datetime.now().timestamp())


# Global cache instance
_explanation_cache = ExplainerCache()


async def get_tender_explanation(
    pool,  # asyncpg pool
    tender_id: str,
    method: str = 'auto',
    model_type: str = 'xgboost',
    include_counterfactuals: bool = True,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Generate explanation for a tender's risk score.

    This is the main entry point for API endpoints.

    Args:
        pool: asyncpg connection pool
        tender_id: Tender ID to explain
        method: 'shap', 'lime', 'combined', or 'auto'
        model_type: 'random_forest' or 'xgboost'
        include_counterfactuals: Whether to include counterfactual suggestions
        use_cache: Whether to use cached explanations

    Returns:
        Dict with explanation ready for API response

    Example API usage:
        @router.get("/api/risk/{tender_id}/explain")
        async def explain_risk(
            tender_id: str,
            method: str = "auto",
            db = Depends(get_db_pool)
        ):
            return await get_tender_explanation(db, tender_id, method)
    """
    # Check cache
    cache_key = f"{method}:{model_type}"
    if use_cache:
        cached = _explanation_cache.get(tender_id, cache_key)
        if cached:
            cached['cached'] = True
            return cached

    try:
        # Import here to avoid circular imports
        from ai.corruption.features.feature_extractor import FeatureExtractor

        # Extract features for the tender
        extractor = FeatureExtractor(pool)
        feature_vectors = await extractor.extract_features_batch([tender_id])

        if not feature_vectors:
            return {
                'error': True,
                'message': f'Tender {tender_id} not found or has no features',
                'tender_id': tender_id
            }

        feature_vector = feature_vectors[0]
        X = np.array([feature_vector.feature_array])
        feature_names = feature_vector.feature_names

        # Load model and create explainer
        explainer_result = _load_and_explain(
            X, tender_id, feature_names,
            method=method,
            model_type=model_type,
            include_counterfactuals=include_counterfactuals
        )

        # Cache result
        if use_cache:
            _explanation_cache.set(tender_id, cache_key, explainer_result)

        return explainer_result

    except Exception as e:
        logger.error(f"Failed to generate explanation for {tender_id}: {e}", exc_info=True)
        return {
            'error': True,
            'message': str(e),
            'tender_id': tender_id
        }


def _load_and_explain(
    X: np.ndarray,
    tender_id: str,
    feature_names: List[str],
    method: str,
    model_type: str,
    include_counterfactuals: bool
) -> Dict[str, Any]:
    """
    Load model and generate explanation.

    Args:
        X: Feature vector (1, n_features)
        tender_id: Tender ID
        feature_names: Feature names
        method: Explanation method
        model_type: Model type
        include_counterfactuals: Include counterfactuals

    Returns:
        Explanation dict
    """
    # Determine which explainers to use
    if method == 'auto':
        # Use SHAP for tree models, LIME for others
        if model_type in ['random_forest', 'xgboost']:
            method = 'shap'
        else:
            method = 'lime'

    result = {
        'tender_id': tender_id,
        'method': method,
        'generated_at': datetime.utcnow().isoformat(),
        'cached': False
    }

    try:
        # Load model
        model = _load_model(model_type)
        if model is None:
            result['error'] = True
            result['message'] = f'Model {model_type} not found'
            return result

        # Get prediction
        proba = model.predict_proba(X)
        if len(proba.shape) == 2:
            predicted_prob = float(proba[0, 1])
        else:
            predicted_prob = float(proba[0])

        result['predicted_probability'] = predicted_prob
        result['risk_level'] = _get_risk_level(predicted_prob)

        # Generate explanation based on method
        if method == 'shap':
            result['explanation'] = _generate_shap_explanation(
                model, X, tender_id, feature_names
            )
        elif method == 'lime':
            result['explanation'] = _generate_lime_explanation(
                model, X, tender_id, feature_names,
                include_counterfactuals
            )
        elif method == 'combined':
            shap_exp = _generate_shap_explanation(
                model, X, tender_id, feature_names
            )
            lime_exp = _generate_lime_explanation(
                model, X, tender_id, feature_names,
                include_counterfactuals
            )
            result['explanation'] = {
                'shap': shap_exp,
                'lime': lime_exp,
                'consensus_factors': _find_consensus_factors(shap_exp, lime_exp)
            }
        else:
            result['error'] = True
            result['message'] = f'Unknown method: {method}'

    except Exception as e:
        logger.error(f"Explanation generation failed: {e}", exc_info=True)
        result['error'] = True
        result['message'] = str(e)

    return result


def _load_model(model_type: str) -> Optional[Any]:
    """Load a trained model by type"""
    try:
        if model_type == 'random_forest':
            from ai.corruption.ml_models.random_forest import CorruptionRandomForest
            model_path = DEFAULT_MODEL_DIR / "corruption_rf.joblib"
            if model_path.exists():
                return CorruptionRandomForest.load(str(model_path))

        elif model_type == 'xgboost':
            from ai.corruption.ml_models.xgboost_model import CorruptionXGBoost
            model_path = DEFAULT_MODEL_DIR / "corruption_xgb.json"
            if model_path.exists():
                return CorruptionXGBoost.load(str(model_path))

        logger.warning(f"Model file not found for {model_type}")
        return None

    except Exception as e:
        logger.error(f"Failed to load model {model_type}: {e}")
        return None


def _get_risk_level(probability: float) -> str:
    """Convert probability to risk level"""
    if probability >= 0.7:
        return 'high'
    elif probability >= 0.4:
        return 'medium'
    elif probability >= 0.2:
        return 'low'
    return 'minimal'


def _generate_shap_explanation(
    model: Any,
    X: np.ndarray,
    tender_id: str,
    feature_names: List[str]
) -> Dict[str, Any]:
    """Generate SHAP explanation"""
    try:
        from ai.corruption.explainability.shap_explainer import SHAPExplainer

        explainer = SHAPExplainer(model, feature_names=feature_names)

        # Use a simple background (zeros) if we don't have training data
        # In production, this should use a sample of training data
        background = np.zeros((10, X.shape[1]))
        explainer.fit(background)

        explanation = explainer.explain_prediction(X, tender_id, top_n=10)

        return {
            'base_value': explanation.base_value,
            'top_factors': [
                {
                    'feature': c.feature_name,
                    'value': c.feature_value,
                    'shap_value': c.shap_value,
                    'direction': c.direction,
                    'rank': c.importance_rank
                }
                for c in explanation.top_contributions
            ],
            'summary': explanation.summary
        }

    except Exception as e:
        logger.error(f"SHAP explanation failed: {e}")
        return {'error': str(e)}


def _generate_lime_explanation(
    model: Any,
    X: np.ndarray,
    tender_id: str,
    feature_names: List[str],
    include_counterfactuals: bool
) -> Dict[str, Any]:
    """Generate LIME explanation"""
    try:
        from ai.corruption.explainability.lime_explainer import LIMEExplainer

        explainer = LIMEExplainer(model, feature_names=feature_names)

        # Fit with simple background
        background = np.random.randn(100, X.shape[1]) * 0.1
        explainer.fit(background)

        explanation = explainer.explain_prediction(
            X[0],
            tender_id,
            num_features=10,
            generate_counterfactuals=include_counterfactuals
        )

        result = {
            'local_prediction': explanation.local_prediction,
            'model_fidelity': explanation.model_fidelity,
            'explanation_text': explanation.explanation_text,
            'top_factors': [
                {
                    'feature': c.feature_name,
                    'human_name': c.human_name,
                    'value': c.feature_value,
                    'weight': c.weight,
                    'direction': c.direction,
                    'rule': c.rule
                }
                for c in explanation.contributions[:10]
            ]
        }

        if include_counterfactuals:
            result['counterfactuals'] = explanation.counterfactual_suggestions

        return result

    except Exception as e:
        logger.error(f"LIME explanation failed: {e}")
        return {'error': str(e)}


def _find_consensus_factors(
    shap_exp: Dict[str, Any],
    lime_exp: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """Find factors that both SHAP and LIME agree on"""
    consensus = []

    if 'error' in shap_exp or 'error' in lime_exp:
        return consensus

    shap_factors = {f['feature']: f for f in shap_exp.get('top_factors', [])}
    lime_factors = {f['feature']: f for f in lime_exp.get('top_factors', [])}

    common = set(shap_factors.keys()) & set(lime_factors.keys())

    for feature in common:
        shap_dir = shap_factors[feature]['direction']
        lime_dir = lime_factors[feature]['direction']

        if shap_dir == lime_dir:
            consensus.append({
                'feature': feature,
                'direction': shap_dir,
                'shap_rank': shap_factors[feature]['rank'],
                'lime_weight': lime_factors[feature]['weight'],
                'confidence': 'high'
            })

    return sorted(consensus, key=lambda x: x.get('shap_rank', 999))


async def batch_explain_tenders(
    pool,
    tender_ids: List[str],
    method: str = 'shap',
    model_type: str = 'xgboost',
    max_concurrent: int = 10
) -> List[Dict[str, Any]]:
    """
    Generate explanations for multiple tenders.

    Args:
        pool: asyncpg connection pool
        tender_ids: List of tender IDs
        method: Explanation method
        model_type: Model type
        max_concurrent: Max concurrent extractions

    Returns:
        List of explanations
    """
    import asyncio

    semaphore = asyncio.Semaphore(max_concurrent)

    async def explain_one(tender_id: str) -> Dict[str, Any]:
        async with semaphore:
            return await get_tender_explanation(
                pool, tender_id, method, model_type,
                include_counterfactuals=False,
                use_cache=True
            )

    results = await asyncio.gather(
        *[explain_one(tid) for tid in tender_ids],
        return_exceptions=True
    )

    # Convert exceptions to error dicts
    return [
        r if not isinstance(r, Exception) else {
            'error': True,
            'message': str(r)
        }
        for r in results
    ]


def format_explanation_for_frontend(
    explanation: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format explanation for frontend display.

    Simplifies the explanation structure for easy rendering.
    """
    if explanation.get('error'):
        return {
            'success': False,
            'error': explanation.get('message', 'Unknown error')
        }

    result = {
        'success': True,
        'tender_id': explanation.get('tender_id'),
        'risk': {
            'probability': explanation.get('predicted_probability', 0),
            'level': explanation.get('risk_level', 'unknown'),
            'color': _get_risk_color(explanation.get('predicted_probability', 0))
        },
        'method': explanation.get('method'),
        'cached': explanation.get('cached', False)
    }

    exp_data = explanation.get('explanation', {})

    # Extract top factors regardless of method
    factors = exp_data.get('top_factors', [])
    result['factors'] = [
        {
            'name': f.get('human_name', f.get('feature', 'Unknown')),
            'impact': 'positive' if f.get('direction') == 'increases_risk' else 'negative',
            'value': f.get('value'),
            'importance': abs(f.get('shap_value') or f.get('weight') or 0)
        }
        for f in factors[:5]
    ]

    result['summary'] = exp_data.get('summary') or exp_data.get('explanation_text', '')

    if 'counterfactuals' in exp_data:
        result['recommendations'] = exp_data['counterfactuals'][:3]

    return result


def _get_risk_color(probability: float) -> str:
    """Get color for risk level"""
    if probability >= 0.7:
        return '#ef4444'  # red-500
    elif probability >= 0.4:
        return '#f97316'  # orange-500
    elif probability >= 0.2:
        return '#eab308'  # yellow-500
    return '#22c55e'  # green-500


# API endpoint examples (for documentation)
ENDPOINT_EXAMPLES = {
    'explain_single': {
        'endpoint': 'GET /api/risk/{tender_id}/explain',
        'params': {
            'method': 'shap|lime|combined|auto',
            'model': 'xgboost|random_forest'
        },
        'response': {
            'tender_id': '12345/2024',
            'predicted_probability': 0.72,
            'risk_level': 'high',
            'method': 'shap',
            'explanation': {
                'base_value': 0.15,
                'top_factors': [
                    {
                        'feature': 'single_bidder',
                        'value': 1.0,
                        'shap_value': 0.25,
                        'direction': 'increases_risk'
                    }
                ],
                'summary': 'This tender shows high risk due to...'
            }
        }
    },
    'batch_explain': {
        'endpoint': 'POST /api/risk/explain/batch',
        'body': {
            'tender_ids': ['12345/2024', '12346/2024'],
            'method': 'shap'
        },
        'response': {
            'explanations': [],
            'total': 2,
            'success': 2,
            'errors': 0
        }
    }
}
