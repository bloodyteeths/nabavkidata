"""
Collusion Detection API Endpoints

Provides access to GNN-detected collusion clusters and network analysis.
Reads from pre-computed model outputs.
"""

import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from utils.risk_levels import calculate_risk_level

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corruption/collusion", tags=["Collusion Detection"])

# Paths to ML model outputs
ML_MODELS_DIR = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models" / "models"
CLUSTERS_PATH = ML_MODELS_DIR / "collusion_clusters.json"
NODE_PREDICTIONS_PATH = ML_MODELS_DIR / "node_predictions.json"
GRAPH_INFO_PATH = ML_MODELS_DIR / "graph_info.json"


# Response Models
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


def load_clusters() -> List[Dict]:
    """Load collusion clusters from JSON file."""
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
    """Load node predictions from JSON file."""
    if NODE_PREDICTIONS_PATH.exists():
        try:
            with open(NODE_PREDICTIONS_PATH, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading node predictions: {e}")
    return {}


@router.get("/clusters", response_model=List[CollusionClusterSummary])
async def get_collusion_clusters(
    min_confidence: float = Query(50.0, ge=0, le=100),
    pattern_type: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0)
):
    """
    Get detected collusion clusters.
    """
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
    min_probability: float = Query(0.5, ge=0, le=1)
):
    """
    Get companies with their risk scores.
    """
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
