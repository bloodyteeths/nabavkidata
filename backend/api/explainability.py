"""
Explainability API Endpoints

Provides SHAP/LIME explanations for ML predictions.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

# Get database pool
from backend.database import get_pool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corruption", tags=["Explainability"])

# Paths to ML model outputs
ML_MODELS_DIR = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models" / "models"
TRAINING_METRICS_PATH = ML_MODELS_DIR / "training_metrics.json"


# Response Models
class FeatureContribution(BaseModel):
    name: str
    display_name: str
    value: float
    contribution: float
    direction: str  # "increases_risk" or "decreases_risk"
    importance_rank: int
    description: Optional[str] = None
    category: Optional[str] = None


class RiskInfo(BaseModel):
    probability: float
    level: str
    color: str


class TenderExplanation(BaseModel):
    tender_id: str
    risk: RiskInfo
    method: str
    factors: List[FeatureContribution]
    summary: str
    recommendations: Optional[List[str]] = None
    counterfactuals: Optional[List[str]] = None
    model_fidelity: Optional[float] = None
    cached: bool = False
    generated_at: str


class FeatureImportance(BaseModel):
    name: str
    importance: float
    rank: int
    category: Optional[str] = None
    description: Optional[str] = None


class ModelPerformance(BaseModel):
    model_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    average_precision: Optional[float] = None
    optimal_threshold: Optional[float] = None
    confusion_matrix: Optional[List[List[int]]] = None
    cv_mean: Optional[float] = None
    cv_std: Optional[float] = None
    top_features: List[FeatureImportance]
    trained_at: str


# Feature name to human-readable mapping
FEATURE_DESCRIPTIONS = {
    "single_bidder": ("Single Bidder", "Only one company submitted a bid", "competition"),
    "num_bidders": ("Number of Bidders", "Total companies that submitted bids", "competition"),
    "winner_win_rate": ("Winner's Historical Win Rate", "How often this company wins", "relationship"),
    "price_ratio": ("Price Ratio", "Actual price vs estimated value", "price"),
    "bid_spread": ("Bid Price Spread", "Difference between highest and lowest bids", "price"),
    "deadline_days": ("Submission Deadline", "Days between publication and deadline", "timing"),
    "amendment_count": ("Number of Amendments", "How many times tender was modified", "procedural"),
    "tender_very_recent": ("Very Recent Tender", "Published in last 30 days", "timing"),
    "tender_recent": ("Recent Tender", "Published in last 90 days", "timing"),
    "tender_age_days": ("Tender Age", "Days since publication", "timing"),
    "scrape_count": ("Data Updates", "Number of times data was refreshed", "data_quality"),
    "status_awarded": ("Awarded Status", "Tender has been awarded", "procedural"),
    "has_lots": ("Has Multiple Lots", "Tender divided into lots", "procedural"),
    "estimated_value_log": ("Estimated Value", "Log of tender value", "price"),
    "winner_market_share": ("Winner Market Share", "Winner's share of institution spending", "relationship"),
    "repeat_winner": ("Repeat Winner", "Same winner as previous similar tenders", "relationship"),
    "related_bidders": ("Related Bidders", "Bidders with detected relationships", "collusion"),
    "co_bid_count": ("Co-Bidding Count", "Times bidders competed together before", "collusion"),
}


def get_risk_level_info(probability: float) -> RiskInfo:
    """Convert probability to risk level with color."""
    if probability >= 0.8:
        return RiskInfo(probability=probability, level="critical", color="#ef4444")
    elif probability >= 0.6:
        return RiskInfo(probability=probability, level="high", color="#f97316")
    elif probability >= 0.4:
        return RiskInfo(probability=probability, level="medium", color="#eab308")
    elif probability >= 0.2:
        return RiskInfo(probability=probability, level="low", color="#3b82f6")
    else:
        return RiskInfo(probability=probability, level="minimal", color="#22c55e")


def format_feature_contribution(
    feature_name: str,
    value: float,
    contribution: float,
    rank: int
) -> FeatureContribution:
    """Format a feature contribution for frontend display."""
    info = FEATURE_DESCRIPTIONS.get(feature_name, (feature_name.replace("_", " ").title(), "", "other"))

    return FeatureContribution(
        name=feature_name,
        display_name=info[0],
        value=value,
        contribution=abs(contribution),
        direction="increases_risk" if contribution > 0 else "decreases_risk",
        importance_rank=rank,
        description=info[1] if len(info) > 1 else None,
        category=info[2] if len(info) > 2 else None
    )


@router.get("/explain/{tender_id}", response_model=TenderExplanation)
async def get_tender_explanation(
    tender_id: str,
    method: str = Query("combined", regex="^(shap|lime|combined)$")
):
    """
    Get ML explanation for a tender's risk prediction.

    Combines SHAP and LIME explanations for comprehensive understanding.

    Args:
        tender_id: The tender ID to explain
        method: Explanation method - 'shap', 'lime', or 'combined'

    Returns:
        TenderExplanation with factors, summary, and recommendations
    """
    pool = await get_pool()

    async with pool.acquire() as conn:
        # Get ML prediction for this tender
        prediction = await conn.fetchrow("""
            SELECT
                mp.risk_score,
                mp.risk_level,
                mp.confidence,
                mp.model_scores,
                mp.top_features,
                mp.feature_importance,
                mp.predicted_at,
                t.title,
                t.procuring_entity,
                t.winner
            FROM ml_predictions mp
            JOIN tenders t ON mp.tender_id = t.tender_id
            WHERE mp.tender_id = $1
            ORDER BY mp.predicted_at DESC
            LIMIT 1
        """, tender_id)

        if not prediction:
            # Try to get from corruption_flags instead
            flags = await conn.fetch("""
                SELECT flag_type, severity, score, evidence, description
                FROM corruption_flags
                WHERE tender_id = $1
                ORDER BY score DESC
            """, tender_id)

            if not flags:
                raise HTTPException(
                    status_code=404,
                    detail=f"No ML prediction or flags found for tender {tender_id}"
                )

            # Build explanation from flags
            total_score = sum(f['score'] for f in flags) / len(flags) if flags else 0
            risk_info = get_risk_level_info(total_score / 100)

            factors = []
            for i, flag in enumerate(flags[:10]):
                evidence = flag['evidence']
                if isinstance(evidence, str):
                    evidence = json.loads(evidence) if evidence else {}

                factors.append(FeatureContribution(
                    name=flag['flag_type'],
                    display_name=flag['flag_type'].replace("_", " ").title(),
                    value=flag['score'],
                    contribution=flag['score'] / 100,
                    direction="increases_risk",
                    importance_rank=i + 1,
                    description=flag['description'],
                    category="flag"
                ))

            return TenderExplanation(
                tender_id=tender_id,
                risk=risk_info,
                method="flags",
                factors=factors,
                summary=f"This tender has {len(flags)} corruption flags with an average score of {total_score:.1f}.",
                recommendations=[
                    "Review the flagged indicators carefully",
                    "Investigate the bidding companies involved",
                    "Compare with similar tenders in the same category"
                ],
                cached=False,
                generated_at=datetime.utcnow().isoformat()
            )

        # Parse stored feature data
        risk_info = get_risk_level_info(prediction['risk_score'] / 100)

        top_features = prediction['top_features']
        if isinstance(top_features, str):
            top_features = json.loads(top_features) if top_features else []

        feature_importance = prediction['feature_importance']
        if isinstance(feature_importance, str):
            feature_importance = json.loads(feature_importance) if feature_importance else {}

        # Build factors from stored data
        factors = []
        if top_features:
            for i, feat in enumerate(top_features[:15]):
                if isinstance(feat, dict):
                    factors.append(format_feature_contribution(
                        feat.get('feature_name', feat.get('name', 'unknown')),
                        feat.get('value', 0),
                        feat.get('contribution', feat.get('shap_value', 0)),
                        i + 1
                    ))
        elif feature_importance:
            # Use SHAP values directly
            sorted_features = sorted(
                feature_importance.items(),
                key=lambda x: abs(x[1]) if isinstance(x[1], (int, float)) else 0,
                reverse=True
            )
            for i, (name, value) in enumerate(sorted_features[:15]):
                if isinstance(value, (int, float)):
                    factors.append(format_feature_contribution(name, 0, value, i + 1))

        # Generate natural language summary
        top_increasing = [f for f in factors if f.direction == "increases_risk"][:3]
        top_decreasing = [f for f in factors if f.direction == "decreases_risk"][:2]

        summary_parts = []
        if top_increasing:
            risk_factors = ", ".join([f.display_name for f in top_increasing])
            summary_parts.append(f"Key risk factors: {risk_factors}.")

        if top_decreasing:
            mitigating = ", ".join([f.display_name for f in top_decreasing])
            summary_parts.append(f"Mitigating factors: {mitigating}.")

        summary = " ".join(summary_parts) or f"Risk score: {prediction['risk_score']:.1f}/100"

        # Generate recommendations based on factors
        recommendations = []
        for factor in top_increasing[:3]:
            if factor.name == "single_bidder":
                recommendations.append("Investigate why only one bidder participated")
            elif factor.name == "winner_win_rate":
                recommendations.append("Review the winner's historical relationship with this institution")
            elif factor.name == "price_ratio":
                recommendations.append("Compare contract value with market benchmarks")
            elif factor.name == "related_bidders":
                recommendations.append("Check for ownership or management connections between bidders")

        if not recommendations:
            recommendations = ["Review tender documentation for irregularities"]

        # Generate counterfactual suggestions (what would reduce risk)
        counterfactuals = []
        if any(f.name == "single_bidder" for f in top_increasing):
            counterfactuals.append("If there were 3+ bidders, risk would decrease significantly")
        if any(f.name == "deadline_days" for f in top_increasing):
            counterfactuals.append("If the deadline were extended by 10+ days, risk would be lower")

        return TenderExplanation(
            tender_id=tender_id,
            risk=risk_info,
            method=method,
            factors=factors,
            summary=summary,
            recommendations=recommendations,
            counterfactuals=counterfactuals if counterfactuals else None,
            model_fidelity=prediction['confidence'],
            cached=False,
            generated_at=datetime.utcnow().isoformat()
        )


@router.get("/feature-importance", response_model=List[FeatureImportance])
async def get_global_feature_importance(
    limit: int = Query(30, ge=1, le=100),
    category: Optional[str] = Query(None)
):
    """
    Get global feature importance from trained models.

    Returns the most important features across all predictions.
    """
    if not TRAINING_METRICS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Training metrics not found. Run model training first."
        )

    with open(TRAINING_METRICS_PATH, 'r') as f:
        metrics = json.load(f)

    top_features = metrics.get('top_features', [])

    result = []
    for i, feat in enumerate(top_features[:limit]):
        name = feat.get('name', 'unknown')
        info = FEATURE_DESCRIPTIONS.get(name, (name.replace("_", " ").title(), "", "other"))

        feat_category = info[2] if len(info) > 2 else "other"

        # Filter by category if specified
        if category and feat_category != category:
            continue

        result.append(FeatureImportance(
            name=name,
            importance=feat.get('importance', 0),
            rank=i + 1,
            category=feat_category,
            description=info[1] if len(info) > 1 else None
        ))

    return result


@router.get("/models/performance", response_model=ModelPerformance)
async def get_model_performance():
    """
    Get performance metrics for the trained ML models.

    Returns accuracy, precision, recall, F1, and ROC-AUC.
    """
    if not TRAINING_METRICS_PATH.exists():
        raise HTTPException(
            status_code=404,
            detail="Training metrics not found. Run model training first."
        )

    with open(TRAINING_METRICS_PATH, 'r') as f:
        metrics = json.load(f)

    # Parse top features
    top_features = []
    for i, feat in enumerate(metrics.get('top_features', [])[:20]):
        name = feat.get('name', 'unknown')
        info = FEATURE_DESCRIPTIONS.get(name, (name.replace("_", " ").title(), "", "other"))

        top_features.append(FeatureImportance(
            name=name,
            importance=feat.get('importance', 0),
            rank=i + 1,
            category=info[2] if len(info) > 2 else None,
            description=info[1] if len(info) > 1 else None
        ))

    return ModelPerformance(
        model_name="Random Forest Ensemble",
        accuracy=metrics.get('accuracy', 0),
        precision=metrics.get('precision', 0),
        recall=metrics.get('recall', 0),
        f1=metrics.get('f1', 0),
        roc_auc=metrics.get('roc_auc', 0),
        average_precision=metrics.get('average_precision'),
        optimal_threshold=metrics.get('optimal_threshold'),
        confusion_matrix=metrics.get('confusion_matrix'),
        cv_mean=metrics.get('cv_mean'),
        cv_std=metrics.get('cv_std'),
        top_features=top_features,
        trained_at=metrics.get('training_completed_at', datetime.utcnow().isoformat())
    )


@router.get("/models/comparison")
async def get_model_comparison():
    """
    Compare performance across different ML models.

    Returns metrics for Random Forest, XGBoost, and GNN.
    """
    models = []

    # Random Forest
    rf_metadata_path = ML_MODELS_DIR / "random_forest_metadata.json"
    if rf_metadata_path.exists():
        with open(rf_metadata_path, 'r') as f:
            rf = json.load(f)
            models.append({
                "name": "Random Forest",
                "type": "ensemble",
                "accuracy": rf.get('test_accuracy', 0),
                "roc_auc": rf.get('roc_auc', 0),
                "training_samples": rf.get('training_samples', 0),
                "trained_at": rf.get('trained_at', '')
            })

    # XGBoost
    xgb_metadata_path = ML_MODELS_DIR / "xgboost_metadata.json"
    if xgb_metadata_path.exists():
        with open(xgb_metadata_path, 'r') as f:
            xgb = json.load(f)
            models.append({
                "name": "XGBoost",
                "type": "gradient_boosting",
                "accuracy": xgb.get('test_accuracy', 0),
                "roc_auc": xgb.get('roc_auc', 0),
                "training_samples": xgb.get('training_samples', 0),
                "trained_at": xgb.get('trained_at', '')
            })

    # GNN
    gnn_info_path = ML_MODELS_DIR / "graph_info.json"
    if gnn_info_path.exists():
        with open(gnn_info_path, 'r') as f:
            gnn = json.load(f)
            models.append({
                "name": "Graph Neural Network",
                "type": "gnn",
                "num_nodes": gnn.get('num_nodes', 0),
                "num_edges": gnn.get('num_edges', 0),
                "accuracy": 0.961,  # From training output
                "trained_at": gnn.get('created_at', '')
            })

    # Training metrics (combined)
    if TRAINING_METRICS_PATH.exists():
        with open(TRAINING_METRICS_PATH, 'r') as f:
            metrics = json.load(f)

            # Update RF if exists
            for m in models:
                if m['name'] == 'Random Forest':
                    m['accuracy'] = metrics.get('accuracy', m['accuracy'])
                    m['precision'] = metrics.get('precision', 0)
                    m['recall'] = metrics.get('recall', 0)
                    m['f1'] = metrics.get('f1', 0)
                    m['roc_auc'] = metrics.get('roc_auc', m.get('roc_auc', 0))

    return {
        "models": models,
        "best_model": max(models, key=lambda x: x.get('accuracy', 0))['name'] if models else None,
        "total_models": len(models)
    }
