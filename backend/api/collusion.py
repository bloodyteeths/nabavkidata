"""
Collusion Detection API Endpoints

Provides access to GNN-detected collusion clusters and network analysis.
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

router = APIRouter(prefix="/api/corruption/collusion", tags=["Collusion Detection"])

# Paths to ML model outputs
ML_MODELS_DIR = Path(__file__).parent.parent.parent / "ai" / "corruption" / "ml_models" / "models"
CLUSTERS_PATH = ML_MODELS_DIR / "collusion_clusters.json"
NODE_PREDICTIONS_PATH = ML_MODELS_DIR / "node_predictions.json"
GRAPH_INFO_PATH = ML_MODELS_DIR / "graph_info.json"


# Response Models
class ClusterEvidence(BaseModel):
    evidence_type: str
    description: str
    score: float
    details: Optional[Dict[str, Any]] = None


class CollusionCluster(BaseModel):
    cluster_id: str
    companies: List[str]
    num_companies: int
    confidence: float
    risk_level: str
    pattern_type: str
    detection_method: str
    evidence: List[ClusterEvidence]
    common_tenders: Optional[List[str]] = None
    common_institutions: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class CollusionClusterSummary(BaseModel):
    cluster_id: str
    num_companies: int
    confidence: float
    risk_level: str
    pattern_type: str
    top_companies: List[str]


class CompanyRisk(BaseModel):
    company_name: str
    prediction: int  # 0 = normal, 1 = suspicious
    probability: float
    risk_level: str


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
    type: str  # 'co_bid', 'relationship', 'contract'
    weight: float
    metadata: Optional[Dict[str, Any]] = None


class NetworkData(BaseModel):
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    cluster_id: Optional[str] = None
    center_node: Optional[str] = None


class CollusionStats(BaseModel):
    total_clusters: int
    high_confidence_clusters: int
    total_suspicious_companies: int
    avg_cluster_size: float
    largest_cluster_size: int
    most_common_pattern: str
    generated_at: str


def get_risk_level(confidence: float) -> str:
    """Convert confidence to risk level."""
    if confidence >= 80:
        return "critical"
    elif confidence >= 60:
        return "high"
    elif confidence >= 40:
        return "medium"
    else:
        return "low"


def load_clusters() -> List[Dict]:
    """Load collusion clusters from JSON file."""
    if not CLUSTERS_PATH.exists():
        return []

    with open(CLUSTERS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('clusters', [])


def load_node_predictions() -> List[Dict]:
    """Load company risk predictions from JSON file."""
    if not NODE_PREDICTIONS_PATH.exists():
        return []

    with open(NODE_PREDICTIONS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
        return data.get('predictions', [])


@router.get("/clusters", response_model=List[CollusionClusterSummary])
async def get_collusion_clusters(
    min_confidence: float = Query(50.0, ge=0, le=100),
    min_companies: int = Query(3, ge=2),
    pattern_type: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """
    Get list of detected collusion clusters.

    Clusters are groups of companies that exhibit suspicious co-bidding patterns.

    Args:
        min_confidence: Minimum confidence threshold (0-100)
        min_companies: Minimum companies in cluster
        pattern_type: Filter by pattern type (e.g., 'bid_clustering')
        limit: Max results to return
        offset: Pagination offset
    """
    clusters = load_clusters()

    # Filter
    filtered = []
    for c in clusters:
        if c.get('confidence', 0) < min_confidence:
            continue
        if len(c.get('companies', [])) < min_companies:
            continue
        if pattern_type and c.get('pattern_type') != pattern_type:
            continue
        filtered.append(c)

    # Sort by confidence
    filtered.sort(key=lambda x: x.get('confidence', 0), reverse=True)

    # Paginate
    paginated = filtered[offset:offset + limit]

    # Convert to summaries
    return [
        CollusionClusterSummary(
            cluster_id=c.get('cluster_id', f"CL-{i}"),
            num_companies=len(c.get('companies', [])),
            confidence=c.get('confidence', 0),
            risk_level=c.get('risk_level', get_risk_level(c.get('confidence', 0))),
            pattern_type=c.get('pattern_type', 'unknown'),
            top_companies=c.get('companies', [])[:5]
        )
        for i, c in enumerate(paginated)
    ]


@router.get("/clusters/{cluster_id}", response_model=CollusionCluster)
async def get_cluster_detail(cluster_id: str):
    """
    Get detailed information about a specific collusion cluster.

    Includes all companies, evidence, and common tenders/institutions.
    """
    clusters = load_clusters()

    for c in clusters:
        if c.get('cluster_id') == cluster_id:
            evidence = []
            for e in c.get('evidence', []):
                evidence.append(ClusterEvidence(
                    evidence_type=e.get('evidence_type', e.get('type', 'unknown')),
                    description=e.get('description', ''),
                    score=e.get('score', 0),
                    details=e.get('details')
                ))

            return CollusionCluster(
                cluster_id=c.get('cluster_id', cluster_id),
                companies=c.get('companies', []),
                num_companies=len(c.get('companies', [])),
                confidence=c.get('confidence', 0),
                risk_level=c.get('risk_level', get_risk_level(c.get('confidence', 0))),
                pattern_type=c.get('pattern_type', 'unknown'),
                detection_method=c.get('detection_method', 'unknown'),
                evidence=evidence,
                common_tenders=c.get('common_tenders'),
                common_institutions=c.get('common_institutions'),
                metadata=c.get('metadata')
            )

    raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")


@router.get("/stats", response_model=CollusionStats)
async def get_collusion_stats():
    """
    Get aggregated statistics about collusion detection results.
    """
    clusters = load_clusters()
    predictions = load_node_predictions()

    if not clusters:
        return CollusionStats(
            total_clusters=0,
            high_confidence_clusters=0,
            total_suspicious_companies=0,
            avg_cluster_size=0,
            largest_cluster_size=0,
            most_common_pattern="none",
            generated_at=datetime.utcnow().isoformat()
        )

    # Calculate stats
    high_conf = sum(1 for c in clusters if c.get('confidence', 0) >= 70)
    sizes = [len(c.get('companies', [])) for c in clusters]
    avg_size = sum(sizes) / len(sizes) if sizes else 0
    max_size = max(sizes) if sizes else 0

    # Most common pattern
    patterns = {}
    for c in clusters:
        p = c.get('pattern_type', 'unknown')
        patterns[p] = patterns.get(p, 0) + 1
    most_common = max(patterns.items(), key=lambda x: x[1])[0] if patterns else "unknown"

    # Suspicious companies
    suspicious = sum(1 for p in predictions if p.get('prediction') == 1)

    return CollusionStats(
        total_clusters=len(clusters),
        high_confidence_clusters=high_conf,
        total_suspicious_companies=suspicious,
        avg_cluster_size=round(avg_size, 1),
        largest_cluster_size=max_size,
        most_common_pattern=most_common,
        generated_at=datetime.utcnow().isoformat()
    )


@router.get("/companies/risk-scores", response_model=List[CompanyRisk])
async def get_company_risk_scores(
    risk_level: Optional[str] = Query(None),
    min_probability: float = Query(0.0, ge=0, le=1),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0)
):
    """
    Get risk scores for companies from GNN predictions.

    Returns companies ranked by their predicted risk probability.
    """
    predictions = load_node_predictions()

    # Filter
    filtered = []
    for p in predictions:
        prob = p.get('probability', 0)
        if prob < min_probability:
            continue

        level = p.get('risk_level', 'low')
        if risk_level and level != risk_level:
            continue

        filtered.append(p)

    # Sort by probability descending
    filtered.sort(key=lambda x: x.get('probability', 0), reverse=True)

    # Paginate
    paginated = filtered[offset:offset + limit]

    return [
        CompanyRisk(
            company_name=p.get('company_name', 'Unknown'),
            prediction=p.get('prediction', 0),
            probability=p.get('probability', 0),
            risk_level=p.get('risk_level', 'low')
        )
        for p in paginated
    ]


@router.get("/company/{company_name}", response_model=Dict[str, Any])
async def get_company_collusion_profile(company_name: str):
    """
    Get collusion analysis for a specific company.

    Returns clusters the company belongs to and risk information.
    """
    clusters = load_clusters()
    predictions = load_node_predictions()

    # Find company in predictions
    company_prediction = None
    for p in predictions:
        if p.get('company_name', '').lower() == company_name.lower():
            company_prediction = p
            break

    # Find clusters containing this company
    company_clusters = []
    for c in clusters:
        companies = [comp.lower() for comp in c.get('companies', [])]
        if company_name.lower() in companies:
            company_clusters.append({
                "cluster_id": c.get('cluster_id'),
                "confidence": c.get('confidence', 0),
                "pattern_type": c.get('pattern_type'),
                "num_companies": len(c.get('companies', [])),
                "other_companies": [comp for comp in c.get('companies', [])
                                   if comp.lower() != company_name.lower()][:10]
            })

    # Check database for additional relationships
    pool = await get_pool()
    db_relationships = []

    async with pool.acquire() as conn:
        relationships = await conn.fetch("""
            SELECT
                CASE WHEN company_a ILIKE $1 THEN company_b ELSE company_a END as related_company,
                relationship_type,
                confidence,
                evidence,
                source
            FROM company_relationships
            WHERE company_a ILIKE $1 OR company_b ILIKE $1
            ORDER BY confidence DESC
            LIMIT 20
        """, f"%{company_name}%")

        for r in relationships:
            evidence = r['evidence']
            if isinstance(evidence, str):
                evidence = json.loads(evidence) if evidence else {}

            db_relationships.append({
                "related_company": r['related_company'],
                "relationship_type": r['relationship_type'],
                "confidence": r['confidence'],
                "source": r['source'],
                "evidence": evidence
            })

    return {
        "company_name": company_name,
        "risk_prediction": company_prediction,
        "clusters": company_clusters,
        "total_clusters": len(company_clusters),
        "database_relationships": db_relationships,
        "is_suspicious": company_prediction.get('prediction', 0) == 1 if company_prediction else len(company_clusters) > 0
    }


@router.get("/network/{cluster_id}", response_model=NetworkData)
async def get_cluster_network(cluster_id: str):
    """
    Get network visualization data for a cluster.

    Returns nodes and edges suitable for force-directed graph visualization.
    """
    clusters = load_clusters()
    predictions = load_node_predictions()

    # Find cluster
    cluster = None
    for c in clusters:
        if c.get('cluster_id') == cluster_id:
            cluster = c
            break

    if not cluster:
        raise HTTPException(status_code=404, detail=f"Cluster {cluster_id} not found")

    # Build prediction lookup
    pred_lookup = {p.get('company_name', '').lower(): p for p in predictions}

    # Create nodes for companies
    nodes = []
    for company in cluster.get('companies', []):
        pred = pred_lookup.get(company.lower(), {})
        nodes.append(NetworkNode(
            id=company,
            name=company,
            type="company",
            risk_score=pred.get('probability', 0.5) * 100,
            risk_level=pred.get('risk_level', 'medium'),
            metadata={"prediction": pred.get('prediction', 0)}
        ))

    # Create edges (all companies in cluster are connected)
    edges = []
    companies = cluster.get('companies', [])
    for i, comp_a in enumerate(companies):
        for comp_b in companies[i + 1:]:
            edges.append(NetworkEdge(
                source=comp_a,
                target=comp_b,
                type="co_bid",
                weight=1.0,
                metadata={"cluster_id": cluster_id}
            ))

    return NetworkData(
        nodes=nodes,
        edges=edges,
        cluster_id=cluster_id,
        center_node=companies[0] if companies else None
    )


@router.get("/network/company/{company_name}", response_model=NetworkData)
async def get_company_network(
    company_name: str,
    depth: int = Query(1, ge=1, le=3),
    max_nodes: int = Query(50, ge=10, le=200)
):
    """
    Get network visualization data centered on a company.

    Shows the company and its connections from collusion clusters.
    """
    clusters = load_clusters()
    predictions = load_node_predictions()

    # Build prediction lookup
    pred_lookup = {p.get('company_name', '').lower(): p for p in predictions}

    # Find all companies connected to this one through clusters
    connected = set()
    for c in clusters:
        companies = [comp.lower() for comp in c.get('companies', [])]
        if company_name.lower() in companies:
            for comp in c.get('companies', []):
                connected.add(comp)

    # Remove self
    connected.discard(company_name)

    # Limit nodes
    connected_list = list(connected)[:max_nodes - 1]

    # Create nodes
    nodes = [
        NetworkNode(
            id=company_name,
            name=company_name,
            type="company",
            risk_score=pred_lookup.get(company_name.lower(), {}).get('probability', 0.5) * 100,
            risk_level=pred_lookup.get(company_name.lower(), {}).get('risk_level', 'medium'),
            metadata={"is_center": True}
        )
    ]

    for company in connected_list:
        pred = pred_lookup.get(company.lower(), {})
        nodes.append(NetworkNode(
            id=company,
            name=company,
            type="company",
            risk_score=pred.get('probability', 0.5) * 100,
            risk_level=pred.get('risk_level', 'medium'),
            metadata={"is_center": False}
        ))

    # Create edges (connect center to all, and interconnect based on clusters)
    edges = []
    for company in connected_list:
        edges.append(NetworkEdge(
            source=company_name,
            target=company,
            type="co_bid",
            weight=1.0
        ))

    # Add inter-connections from same clusters
    for c in clusters:
        companies = [comp for comp in c.get('companies', []) if comp in connected_list]
        for i, comp_a in enumerate(companies):
            for comp_b in companies[i + 1:]:
                # Avoid duplicates
                if not any(e.source == comp_a and e.target == comp_b for e in edges):
                    edges.append(NetworkEdge(
                        source=comp_a,
                        target=comp_b,
                        type="cluster_connection",
                        weight=0.5
                    ))

    return NetworkData(
        nodes=nodes,
        edges=edges,
        center_node=company_name
    )


@router.get("/patterns")
async def get_pattern_types():
    """
    Get available collusion pattern types and their counts.
    """
    clusters = load_clusters()

    patterns = {}
    for c in clusters:
        p = c.get('pattern_type', 'unknown')
        if p not in patterns:
            patterns[p] = {
                "pattern_type": p,
                "count": 0,
                "avg_confidence": 0,
                "total_companies": 0
            }
        patterns[p]['count'] += 1
        patterns[p]['avg_confidence'] += c.get('confidence', 0)
        patterns[p]['total_companies'] += len(c.get('companies', []))

    # Calculate averages
    for p in patterns.values():
        if p['count'] > 0:
            p['avg_confidence'] = round(p['avg_confidence'] / p['count'], 1)

    return list(patterns.values())
