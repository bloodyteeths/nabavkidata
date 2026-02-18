"""
Collusion Detection API Endpoints

Provides access to GNN-detected collusion clusters and network analysis.
Uses the GNNInferenceService for live inference when available, with
graceful fallback to pre-computed JSON files.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from utils.risk_levels import calculate_risk_level

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corruption/collusion", tags=["Collusion Detection"])

# Paths to ML model outputs (used as fallback when inference service is in json mode)
ML_MODELS_DIR = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models" / "models"
CLUSTERS_PATH = ML_MODELS_DIR / "collusion_clusters.json"
NODE_PREDICTIONS_PATH = ML_MODELS_DIR / "node_predictions.json"
GRAPH_INFO_PATH = ML_MODELS_DIR / "graph_info.json"

# Ensure the ai/corruption/ml_models package is importable
_AI_ROOT = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models"
if str(_AI_ROOT.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT.parent.parent.parent))

# Lazy import of inference service to avoid import errors when torch is missing
_inference_service = None


def _get_inference_service():
    """Get (or lazily create) the singleton GNNInferenceService."""
    global _inference_service
    if _inference_service is None:
        try:
            from ai.corruption.ml_models.gnn_inference import GNNInferenceService
            _inference_service = GNNInferenceService.get_instance()
        except Exception as e:
            logger.warning(f"Could not import GNNInferenceService: {e}")
            _inference_service = None
    return _inference_service


# ---------------------------------------------------------------------------
# Response Models (unchanged -- backward compatible)
# ---------------------------------------------------------------------------


class CollusionClusterSummary(BaseModel):
    cluster_id: str
    num_companies: int
    confidence: float
    risk_level: str
    pattern_type: str
    top_companies: List[str]


class ClusterEvidence(BaseModel):
    evidence_type: str
    description: str
    score: float
    details: Optional[Dict[str, Any]] = None


class CollusionCluster(CollusionClusterSummary):
    companies: List[str]
    detection_method: str
    evidence: List[ClusterEvidence]
    common_tenders: Optional[List[str]] = None
    common_institutions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class CollusionStats(BaseModel):
    total_clusters: int
    high_confidence_clusters: int
    total_suspicious_companies: int
    avg_cluster_size: float
    largest_cluster_size: int
    most_common_pattern: str
    generated_at: str


class CompanyRisk(BaseModel):
    company_name: str
    probability: float
    risk_level: str
    prediction: int


class NetworkNode(BaseModel):
    id: str
    name: str
    type: str  # 'company', 'tender', 'institution'
    risk_score: Optional[float] = None
    risk_level: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class NetworkEdge(BaseModel):
    source: str
    target: str
    type: str
    weight: float
    metadata: Optional[Dict[str, Any]] = None


class NetworkData(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    cluster_id: Optional[str] = None
    center_node: Optional[str] = None


class InferenceStatus(BaseModel):
    mode: str
    loaded: bool
    initialized_at: Optional[str] = None
    model_version: Optional[str] = None
    node_count: int
    pytorch_available: bool
    pyg_available: bool
    onnx_available: bool
    model_checkpoint_exists: bool
    onnx_embeddings_exist: bool
    json_files_exist: bool


# Pattern labels in Macedonian
PATTERN_LABELS = {
    "bid_clustering": "Групирање понуди",
    "clique_detection": "Клика компании",
    "community_detection": "Заедница",
    "price_manipulation": "Ценовна манипулација",
    "repeat_bidding": "Повторувачко понудување",
    "unknown": "Непознат образец"
}


get_risk_level = calculate_risk_level


# ---------------------------------------------------------------------------
# Data loading helpers (JSON fallback -- kept for backward compat)
# ---------------------------------------------------------------------------


def load_clusters() -> List[Dict]:
    """Load collusion clusters via inference service or JSON file."""
    svc = _get_inference_service()
    if svc is not None and svc._loaded:
        return svc._load_clusters_data()

    # Direct JSON fallback
    if CLUSTERS_PATH.exists():
        try:
            with open(CLUSTERS_PATH, 'r') as f:
                data = json.load(f)
                # Handle wrapped format
                if isinstance(data, dict) and 'clusters' in data:
                    return data['clusters']
                return data if isinstance(data, list) else []
        except Exception as e:
            logger.error(f"Error loading clusters: {e}")
    return []


def load_node_predictions() -> Dict:
    """Load node predictions via inference service or JSON file."""
    svc = _get_inference_service()
    if svc is not None and svc._loaded and svc._node_predictions:
        return svc._node_predictions

    # Direct JSON fallback
    if NODE_PREDICTIONS_PATH.exists():
        try:
            with open(NODE_PREDICTIONS_PATH, 'r') as f:
                raw = json.load(f)
                # Handle wrapped format from training pipeline
                preds = raw.get('predictions', raw)
                if isinstance(preds, list):
                    return {p['company_name']: p for p in preds}
                return preds
        except Exception as e:
            logger.error(f"Error loading node predictions: {e}")
    return {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status", response_model=InferenceStatus)
async def get_inference_status():
    """
    Health/status endpoint for the GNN inference service.
    Reports which inference mode is active and model metadata.
    """
    svc = _get_inference_service()
    if svc is not None:
        return InferenceStatus(**svc.get_status())

    # No service available at all
    return InferenceStatus(
        mode="unavailable",
        loaded=False,
        initialized_at=None,
        model_version=None,
        node_count=0,
        pytorch_available=False,
        pyg_available=False,
        onnx_available=False,
        model_checkpoint_exists=False,
        onnx_embeddings_exist=False,
        json_files_exist=CLUSTERS_PATH.exists() and NODE_PREDICTIONS_PATH.exists(),
    )


@router.get("/clusters", response_model=List[CollusionClusterSummary])
async def get_collusion_clusters(
    min_confidence: float = Query(50.0, ge=0, le=100),
    pattern_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    force_refresh: bool = Query(False, description="Admin: force re-read from source"),
):
    """
    Get detected collusion clusters.
    """
    # If force_refresh, re-load from disk (invalidate in-memory cache)
    if force_refresh:
        svc = _get_inference_service()
        if svc is not None:
            svc._clusters = None

    clusters = load_clusters()

    # Filter by confidence
    clusters = [c for c in clusters if c.get('confidence', 0) >= min_confidence]

    # Filter by pattern type
    if pattern_type:
        clusters = [c for c in clusters if c.get('pattern_type') == pattern_type]

    # Sort by confidence desc
    clusters.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    # Paginate
    clusters = clusters[skip:skip + limit]

    # Convert to response model
    result = []
    for c in clusters:
        companies = c.get('companies', [])
        result.append(CollusionClusterSummary(
            cluster_id=c.get('cluster_id', str(hash(tuple(companies[:3])))),
            num_companies=len(companies),
            confidence=c.get('confidence', 50.0),
            risk_level=get_risk_level(c.get('confidence', 50.0)),
            pattern_type=c.get('pattern_type', 'unknown'),
            top_companies=companies[:5]
        ))

    return result


@router.get("/clusters/{cluster_id}", response_model=CollusionCluster)
async def get_cluster_detail(cluster_id: str):
    """
    Get detailed information about a specific cluster.
    """
    # Try inference service first
    svc = _get_inference_service()
    if svc is not None and svc._loaded:
        cluster_data = await svc.predict_cluster_risk(cluster_id)
        if cluster_data:
            companies = cluster_data.get('companies', [])
            evidence_raw = cluster_data.get('evidence', [])
            evidence = []
            for ev in evidence_raw:
                if isinstance(ev, dict):
                    evidence.append(ClusterEvidence(
                        evidence_type=ev.get('evidence_type', 'co_bidding'),
                        description=ev.get('description', 'Компаниите често се натпреваруваат заедно'),
                        score=ev.get('score', cluster_data.get('confidence', 50.0)),
                        details=ev.get('details'),
                    ))

            if not evidence:
                evidence = [
                    ClusterEvidence(
                        evidence_type="co_bidding",
                        description="Компаниите често се натпреваруваат заедно",
                        score=cluster_data.get('confidence', 50.0)
                    )
                ]

            return CollusionCluster(
                cluster_id=cluster_id,
                num_companies=len(companies),
                confidence=cluster_data.get('confidence', 50.0),
                risk_level=get_risk_level(cluster_data.get('confidence', 50.0)),
                pattern_type=cluster_data.get('pattern_type', 'unknown'),
                top_companies=companies[:5],
                companies=companies,
                detection_method=cluster_data.get('detection_method', 'gnn'),
                evidence=evidence,
                common_tenders=cluster_data.get('common_tenders', []),
                common_institutions=cluster_data.get('common_institutions', []),
                metadata=cluster_data.get('metadata'),
            )

    # Fallback to direct JSON reading
    clusters = load_clusters()

    for c in clusters:
        if c.get('cluster_id') == cluster_id:
            companies = c.get('companies', [])
            return CollusionCluster(
                cluster_id=cluster_id,
                num_companies=len(companies),
                confidence=c.get('confidence', 50.0),
                risk_level=get_risk_level(c.get('confidence', 50.0)),
                pattern_type=c.get('pattern_type', 'unknown'),
                top_companies=companies[:5],
                companies=companies,
                detection_method=c.get('detection_method', 'gnn'),
                evidence=[
                    ClusterEvidence(
                        evidence_type="co_bidding",
                        description="Компаниите често се натпреваруваат заедно",
                        score=c.get('confidence', 50.0)
                    )
                ],
                common_tenders=c.get('common_tenders', []),
                common_institutions=c.get('common_institutions', []),
                metadata=c.get('metadata')
            )

    raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")


@router.get("/stats", response_model=CollusionStats)
async def get_collusion_stats():
    """
    Get overall collusion detection statistics.
    """
    clusters = load_clusters()
    predictions = load_node_predictions()

    if not clusters:
        return CollusionStats(
            total_clusters=0,
            high_confidence_clusters=0,
            total_suspicious_companies=0,
            avg_cluster_size=0.0,
            largest_cluster_size=0,
            most_common_pattern="unknown",
            generated_at=datetime.utcnow().isoformat()
        )

    high_conf = len([c for c in clusters if c.get('confidence', 0) >= 70])
    sizes = [len(c.get('companies', [])) for c in clusters]
    avg_size = sum(sizes) / len(sizes) if sizes else 0

    # Count pattern types
    pattern_counts: Dict[str, int] = {}
    for c in clusters:
        pt = c.get('pattern_type', 'unknown')
        pattern_counts[pt] = pattern_counts.get(pt, 0) + 1

    most_common = max(pattern_counts.items(), key=lambda x: x[1])[0] if pattern_counts else "unknown"

    # Count suspicious companies from predictions
    suspicious_count = 0
    if predictions:
        for company, data in predictions.items():
            if isinstance(data, dict) and data.get('prediction', 0) == 1:
                suspicious_count += 1
            elif data == 1:
                suspicious_count += 1

    return CollusionStats(
        total_clusters=len(clusters),
        high_confidence_clusters=high_conf,
        total_suspicious_companies=suspicious_count or sum(sizes),
        avg_cluster_size=round(avg_size, 1),
        largest_cluster_size=max(sizes) if sizes else 0,
        most_common_pattern=most_common,
        generated_at=datetime.utcnow().isoformat()
    )


@router.get("/companies", response_model=List[CompanyRisk])
async def get_company_risk_scores(
    limit: int = Query(50, ge=1, le=200),
    min_probability: float = Query(0.5, ge=0, le=1),
    force_refresh: bool = Query(False, description="Admin: force re-read from source"),
):
    """
    Get companies with their risk scores.
    Uses the GNN inference service when available.
    """
    if force_refresh:
        svc = _get_inference_service()
        if svc is not None:
            svc._node_predictions = None

    predictions = load_node_predictions()

    companies = []
    for company_name, data in predictions.items():
        if isinstance(data, dict):
            prob = data.get('probability', data.get('score', 0.5))
            pred = data.get('prediction', 1 if prob >= 0.5 else 0)
        else:
            prob = 0.5
            pred = 1 if data == 1 else 0

        if prob >= min_probability:
            companies.append(CompanyRisk(
                company_name=company_name,
                probability=prob,
                risk_level=get_risk_level(prob * 100),
                prediction=pred
            ))

    # Sort by probability desc
    companies.sort(key=lambda x: x.probability, reverse=True)

    return companies[:limit]


@router.get("/companies/{company_name}")
async def get_single_company_risk(company_name: str):
    """
    Get risk prediction for a specific company via inference service.
    Falls back to JSON lookup if inference service is unavailable.
    """
    svc = _get_inference_service()
    if svc is not None:
        try:
            result = await svc.predict_node_risk(company_name)
            return result
        except Exception as e:
            logger.warning(f"Inference service error for {company_name}: {e}")

    # Fallback
    predictions = load_node_predictions()
    data = predictions.get(company_name)
    if data is None:
        raise HTTPException(status_code=404, detail=f"Company '{company_name}' not found in predictions")

    if isinstance(data, dict):
        prob = data.get('probability', data.get('score', 0.5))
        pred = data.get('prediction', 1 if prob >= 0.5 else 0)
        level = data.get('risk_level', get_risk_level(prob * 100))
    else:
        prob = 0.5
        pred = 1 if data == 1 else 0
        level = get_risk_level(prob * 100)

    return {
        "company_name": company_name,
        "probability": prob,
        "risk_level": level,
        "prediction": pred,
        "cluster_id": None,
        "mode": "json_fallback",
        "found": True,
    }


@router.get("/network/{cluster_id}", response_model=NetworkData)
async def get_cluster_network(cluster_id: str):
    """
    Get network visualization data for a cluster.
    """
    clusters = load_clusters()

    for c in clusters:
        if c.get('cluster_id') == cluster_id:
            companies = c.get('companies', [])

            nodes = []
            for comp in companies:
                nodes.append(NetworkNode(
                    id=comp,
                    name=comp,
                    type="company",
                    risk_score=c.get('confidence', 50.0) / 100,
                    risk_level=get_risk_level(c.get('confidence', 50.0))
                ))

            # Create edges between all companies in cluster
            edges = []
            for i, comp1 in enumerate(companies):
                for comp2 in companies[i+1:]:
                    edges.append(NetworkEdge(
                        source=comp1,
                        target=comp2,
                        type="co_bid",
                        weight=1.0
                    ))

            return NetworkData(
                nodes=nodes,
                edges=edges,
                cluster_id=cluster_id
            )

    raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")


@router.get("/network/company/{company_name}", response_model=NetworkData)
async def get_company_network(
    company_name: str,
    depth: int = Query(2, ge=1, le=3),
):
    """
    Get co-bidding network for a specific company.
    Uses the inference service for live DB queries when available.
    """
    svc = _get_inference_service()
    if svc is not None:
        try:
            net = await svc.get_company_network(company_name, depth=depth)
            nodes = [NetworkNode(**n) for n in net.get("nodes", [])]
            edges = [NetworkEdge(**e) for e in net.get("edges", [])]
            return NetworkData(
                nodes=nodes,
                edges=edges,
                center_node=net.get("center_node"),
                cluster_id=net.get("cluster_id"),
            )
        except Exception as e:
            logger.warning(f"Inference network error for {company_name}: {e}")

    # Fallback: find company in clusters
    clusters = load_clusters()
    for c in clusters:
        companies = c.get('companies', [])
        if company_name in companies:
            nodes = [
                NetworkNode(
                    id=comp,
                    name=comp,
                    type="company",
                    risk_score=c.get('confidence', 50.0) / 100,
                    risk_level=get_risk_level(c.get('confidence', 50.0)),
                )
                for comp in companies
            ]
            edges = []
            for i, comp1 in enumerate(companies):
                for comp2 in companies[i + 1:]:
                    edges.append(NetworkEdge(
                        source=comp1,
                        target=comp2,
                        type="co_bid",
                        weight=1.0,
                    ))

            return NetworkData(
                nodes=nodes,
                edges=edges,
                center_node=company_name,
                cluster_id=c.get("cluster_id"),
            )

    # Not found in any cluster -- return solo node
    return NetworkData(
        nodes=[NetworkNode(id=company_name, name=company_name, type="company")],
        edges=[],
        center_node=company_name,
    )
