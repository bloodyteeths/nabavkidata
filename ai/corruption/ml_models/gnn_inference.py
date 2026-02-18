"""
GNN Inference Service for Collusion Detection

Provides on-demand inference using the trained CollusionGNN model.
Supports three modes (in order of preference):

1. ONNX Runtime  -- lightest, ~200MB RAM, uses pre-exported embeddings
2. PyTorch Geometric -- full live inference, ~1-2GB RAM
3. Pre-computed JSON fallback -- no ML dependencies, reads static files

The service is a singleton: call ``GNNInferenceService.get_instance()``
once at startup.  All public methods are async-safe.

Memory constraint: EC2 has only 3.8GB total RAM, so the service eagerly
prefers the lightest option that is available.

Usage (inside FastAPI):

    from ai.corruption.ml_models.gnn_inference import GNNInferenceService

    @app.on_event("startup")
    async def startup_gnn():
        svc = GNNInferenceService.get_instance()
        await svc.initialize()

    @app.get("/api/corruption/collusion/companies")
    async def companies():
        svc = GNNInferenceService.get_instance()
        return await svc.predict_node_risk("Alkaloid")
"""

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)

# Paths to model artifacts
_ML_MODELS_DIR = Path(__file__).parent / "models"
_CLUSTERS_PATH = _ML_MODELS_DIR / "collusion_clusters.json"
_NODE_PREDICTIONS_PATH = _ML_MODELS_DIR / "node_predictions.json"
_GRAPH_INFO_PATH = _ML_MODELS_DIR / "graph_info.json"
_MODEL_PATH = _ML_MODELS_DIR / "gnn_collusion.pt"
_ONNX_EMBEDDINGS_PATH = _ML_MODELS_DIR / "gnn_node_embeddings.npz"

# Optional dependency flags
_TORCH_AVAILABLE = False
_PYG_AVAILABLE = False
_ONNX_AVAILABLE = False

try:
    import torch
    _TORCH_AVAILABLE = True
except ImportError:
    pass

try:
    from torch_geometric.data import Data as PygData
    _PYG_AVAILABLE = True
except ImportError:
    pass

try:
    import onnxruntime  # noqa: F401
    _ONNX_AVAILABLE = True
except ImportError:
    pass


def _risk_level(probability: float) -> str:
    """Derive risk level string from 0-1 probability."""
    if probability >= 0.7:
        return "high"
    if probability >= 0.4:
        return "medium"
    return "low"


class GNNInferenceService:
    """
    Singleton inference service for collusion detection.

    Attributes:
        mode: One of 'onnx', 'pytorch', 'json_fallback'
    """

    _instance: Optional["GNNInferenceService"] = None

    def __init__(self):
        self.mode: str = "json_fallback"
        self._loaded: bool = False
        self._initialized_at: Optional[str] = None
        self._pool = None  # asyncpg pool, set during initialize()

        # PyTorch mode
        self._model = None
        self._pyg_data = None
        self._trainer = None

        # ONNX mode (pre-computed embeddings + simple classifier)
        self._node_embeddings: Optional[np.ndarray] = None
        self._classifier_weights: Optional[np.ndarray] = None
        self._classifier_bias: Optional[np.ndarray] = None

        # JSON fallback data
        self._clusters: Optional[List[Dict]] = None
        self._node_predictions: Optional[Dict] = None
        self._graph_info: Optional[Dict] = None

        # Shared across modes
        self._node_names: Optional[List[str]] = None
        self._node_name_to_idx: Optional[Dict[str, int]] = None

    # ------------------------------------------------------------------
    # Singleton
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "GNNInferenceService":
        """Return the singleton instance (create if needed)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    async def initialize(self, pool=None):
        """
        Try to load model in order: ONNX -> PyTorch -> JSON fallback.
        Logs which mode is active.

        Args:
            pool: Optional asyncpg pool for DB-based cache lookups
        """
        if self._loaded:
            logger.info(f"GNNInferenceService already loaded (mode={self.mode})")
            return

        self._pool = pool
        start = time.monotonic()

        # Attempt 1: ONNX pre-computed embeddings
        if self._try_load_onnx():
            self.mode = "onnx"
            logger.info("GNN Inference: ONNX embeddings loaded")
        # Attempt 2: Full PyTorch Geometric
        elif self._try_load_pytorch():
            self.mode = "pytorch"
            logger.info("GNN Inference: PyTorch model loaded")
        # Attempt 3: JSON fallback (always available)
        else:
            self._load_json_fallback()
            self.mode = "json_fallback"
            logger.info("GNN Inference: JSON fallback loaded")

        self._loaded = True
        self._initialized_at = datetime.utcnow().isoformat()
        elapsed = time.monotonic() - start
        logger.info(f"GNNInferenceService initialized in {elapsed:.2f}s (mode={self.mode})")

    def cleanup(self):
        """Release model tensors / large arrays."""
        self._model = None
        self._pyg_data = None
        self._trainer = None
        self._node_embeddings = None
        self._classifier_weights = None
        self._classifier_bias = None
        self._clusters = None
        self._node_predictions = None
        self._loaded = False
        logger.info("GNNInferenceService cleaned up")

    # ------------------------------------------------------------------
    # Public prediction API
    # ------------------------------------------------------------------

    async def predict_node_risk(self, company_name: str) -> Dict[str, Any]:
        """
        Predict collusion risk for a specific company.

        Returns:
            {company_name, probability, risk_level, prediction, cluster_id, mode}
        """
        if not self._loaded:
            await self.initialize(self._pool)

        if self.mode == "pytorch":
            return self._predict_node_pytorch(company_name)
        elif self.mode == "onnx":
            return self._predict_node_onnx(company_name)
        else:
            return self._predict_node_json(company_name)

    async def predict_cluster_risk(self, cluster_id: str) -> Dict[str, Any]:
        """
        Get risk assessment for a collusion cluster.

        Returns:
            Full cluster dict or raises KeyError if not found.
        """
        clusters = await self.get_all_clusters(min_confidence=0.0)
        for c in clusters:
            if c.get("cluster_id") == cluster_id:
                return c
        return {}

    async def get_company_network(
        self, company_name: str, depth: int = 2
    ) -> Dict[str, Any]:
        """
        Get the company's co-bidding network neighborhood.

        Returns:
            {nodes: [...], edges: [...], center_node: str}
        """
        if not self._loaded:
            await self.initialize(self._pool)

        # Try DB cache first
        if self._pool is not None:
            return await self._network_from_db(company_name, depth)

        # Fallback: build from cluster data
        return self._network_from_clusters(company_name)

    async def get_all_clusters(
        self, min_confidence: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Get all detected collusion clusters above confidence threshold.

        min_confidence is on 0-100 scale (matching existing API).
        """
        if not self._loaded:
            await self.initialize(self._pool)

        clusters = self._load_clusters_data()
        return [c for c in clusters if c.get("confidence", 0) >= min_confidence]

    def get_status(self) -> Dict[str, Any]:
        """Return inference mode, model version, last update time."""
        model_version = None
        if _GRAPH_INFO_PATH.exists():
            try:
                with open(_GRAPH_INFO_PATH, "r") as f:
                    info = json.load(f)
                model_version = info.get("created_at")
            except Exception:
                pass

        return {
            "mode": self.mode,
            "loaded": self._loaded,
            "initialized_at": self._initialized_at,
            "model_version": model_version,
            "node_count": len(self._node_names) if self._node_names else 0,
            "pytorch_available": _TORCH_AVAILABLE,
            "pyg_available": _PYG_AVAILABLE,
            "onnx_available": _ONNX_AVAILABLE,
            "model_checkpoint_exists": _MODEL_PATH.exists(),
            "onnx_embeddings_exist": _ONNX_EMBEDDINGS_PATH.exists(),
            "json_files_exist": _CLUSTERS_PATH.exists() and _NODE_PREDICTIONS_PATH.exists(),
        }

    # ------------------------------------------------------------------
    # Loading strategies
    # ------------------------------------------------------------------

    def _try_load_onnx(self) -> bool:
        """
        Load pre-computed node embeddings + lightweight classifier weights
        from .npz file (exported by export_gnn_onnx.py).

        This avoids importing torch/pyg entirely. ~200MB RAM.
        """
        if not _ONNX_EMBEDDINGS_PATH.exists():
            return False

        try:
            data = np.load(str(_ONNX_EMBEDDINGS_PATH), allow_pickle=True)
            self._node_embeddings = data["embeddings"]  # [N, D]
            self._node_names = list(data["node_names"])
            self._node_name_to_idx = {n: i for i, n in enumerate(self._node_names)}

            # Classifier weights are optional -- if absent, use cosine heuristic
            if "classifier_weight" in data and "classifier_bias" in data:
                self._classifier_weights = data["classifier_weight"]  # [C, D]
                self._classifier_bias = data["classifier_bias"]  # [C]

            logger.info(
                f"ONNX embeddings loaded: {self._node_embeddings.shape[0]} nodes, "
                f"{self._node_embeddings.shape[1]}D"
            )
            return True
        except Exception as e:
            logger.warning(f"Failed to load ONNX embeddings: {e}")
            return False

    def _try_load_pytorch(self) -> bool:
        """
        Load the full CollusionGNN model + graph data for live inference.

        Requires torch + torch_geometric.  ~1-2GB RAM.
        """
        if not (_TORCH_AVAILABLE and _PYG_AVAILABLE):
            return False
        if not _MODEL_PATH.exists():
            return False

        try:
            import torch
            from ai.corruption.ml_models.gnn_collusion import (
                CollusionGNN,
                CollusionGNNTrainer,
                GNNConfig,
            )

            # Load checkpoint
            checkpoint = torch.load(str(_MODEL_PATH), map_location="cpu")
            config_dict = checkpoint.get("config", {})
            config = GNNConfig(**config_dict)

            model = CollusionGNN(config)
            model.load_state_dict(checkpoint["model_state_dict"])
            model.eval()

            self._model = model
            # Build a minimal trainer wrapper for convenience methods
            self._trainer = CollusionGNNTrainer(model, config, device="cpu")

            # Load graph info for node name mapping
            if _GRAPH_INFO_PATH.exists():
                with open(_GRAPH_INFO_PATH, "r") as f:
                    info = json.load(f)
                self._node_names = info.get("node_names", [])
                self._node_name_to_idx = {n: i for i, n in enumerate(self._node_names)}

            logger.info(f"PyTorch model loaded from {_MODEL_PATH}")
            return True
        except Exception as e:
            logger.warning(f"Failed to load PyTorch model: {e}")
            return False

    def _load_json_fallback(self):
        """Load the static JSON files produced by the training pipeline."""
        # Clusters
        self._clusters = self._load_clusters_data()

        # Node predictions
        self._node_predictions = {}
        if _NODE_PREDICTIONS_PATH.exists():
            try:
                with open(_NODE_PREDICTIONS_PATH, "r") as f:
                    data = json.load(f)
                    preds = data.get("predictions", data)
                    if isinstance(preds, list):
                        for p in preds:
                            self._node_predictions[p["company_name"]] = p
                    elif isinstance(preds, dict):
                        self._node_predictions = preds
            except Exception as e:
                logger.error(f"Error loading node predictions: {e}")

        # Graph info
        if _GRAPH_INFO_PATH.exists():
            try:
                with open(_GRAPH_INFO_PATH, "r") as f:
                    self._graph_info = json.load(f)
                    self._node_names = self._graph_info.get("node_names", [])
                    self._node_name_to_idx = {n: i for i, n in enumerate(self._node_names)}
            except Exception as e:
                logger.error(f"Error loading graph info: {e}")

        logger.info(
            f"JSON fallback loaded: {len(self._node_predictions)} predictions, "
            f"{len(self._clusters)} clusters"
        )

    # ------------------------------------------------------------------
    # Per-mode prediction logic
    # ------------------------------------------------------------------

    def _predict_node_pytorch(self, company_name: str) -> Dict[str, Any]:
        """Live inference using PyTorch model."""
        import torch
        import torch.nn.functional as F

        idx = (self._node_name_to_idx or {}).get(company_name)
        if idx is None:
            return {
                "company_name": company_name,
                "probability": 0.0,
                "risk_level": "unknown",
                "prediction": 0,
                "cluster_id": None,
                "mode": self.mode,
                "found": False,
            }

        # We need PyG Data to do a forward pass.
        # If we have cached graph data, build Data from it.
        # Otherwise fall through to JSON.
        if self._pyg_data is not None:
            self._model.eval()
            with torch.no_grad():
                logits = self._model(self._pyg_data)
                probs = F.softmax(logits, dim=1)
                prob = float(probs[idx, 1])
                pred = int(probs[idx].argmax())
        else:
            # No graph data available for live pass -- fall back to JSON
            return self._predict_node_json(company_name)

        cluster_id = self._find_cluster_for_company(company_name)

        return {
            "company_name": company_name,
            "probability": round(prob, 6),
            "risk_level": _risk_level(prob),
            "prediction": pred,
            "cluster_id": cluster_id,
            "mode": self.mode,
            "found": True,
        }

    def _predict_node_onnx(self, company_name: str) -> Dict[str, Any]:
        """Inference using pre-computed embeddings + classifier weights."""
        idx = (self._node_name_to_idx or {}).get(company_name)
        if idx is None:
            return {
                "company_name": company_name,
                "probability": 0.0,
                "risk_level": "unknown",
                "prediction": 0,
                "cluster_id": None,
                "mode": self.mode,
                "found": False,
            }

        emb = self._node_embeddings[idx]  # [D]

        if self._classifier_weights is not None:
            # classifier_weights: [num_classes, D], bias: [num_classes]
            logits = self._classifier_weights @ emb + self._classifier_bias
            # Softmax
            exp_logits = np.exp(logits - logits.max())
            probs = exp_logits / exp_logits.sum()
            prob = float(probs[1]) if len(probs) > 1 else float(probs[0])
            pred = int(np.argmax(probs))
        else:
            # No classifier weights -- use embedding norm heuristic
            # Higher L2 norm ~ more "unusual" in the graph
            norm = float(np.linalg.norm(emb))
            # Normalize to 0-1 range based on all embeddings
            all_norms = np.linalg.norm(self._node_embeddings, axis=1)
            if all_norms.max() > 0:
                prob = float(norm / all_norms.max())
            else:
                prob = 0.0
            pred = 1 if prob >= 0.5 else 0

        cluster_id = self._find_cluster_for_company(company_name)

        return {
            "company_name": company_name,
            "probability": round(prob, 6),
            "risk_level": _risk_level(prob),
            "prediction": pred,
            "cluster_id": cluster_id,
            "mode": self.mode,
            "found": True,
        }

    def _predict_node_json(self, company_name: str) -> Dict[str, Any]:
        """Lookup from pre-computed JSON predictions."""
        preds = self._node_predictions or {}

        data = preds.get(company_name)
        if data is None:
            return {
                "company_name": company_name,
                "probability": 0.0,
                "risk_level": "unknown",
                "prediction": 0,
                "cluster_id": None,
                "mode": self.mode,
                "found": False,
            }

        if isinstance(data, dict):
            prob = float(data.get("probability", data.get("score", 0.5)))
            pred = int(data.get("prediction", 1 if prob >= 0.5 else 0))
            level = data.get("risk_level", _risk_level(prob))
        else:
            prob = 0.5
            pred = 1 if data == 1 else 0
            level = _risk_level(prob)

        cluster_id = self._find_cluster_for_company(company_name)

        return {
            "company_name": company_name,
            "probability": round(prob, 6),
            "risk_level": level,
            "prediction": pred,
            "cluster_id": cluster_id,
            "mode": self.mode,
            "found": True,
        }

    # ------------------------------------------------------------------
    # Cluster helpers
    # ------------------------------------------------------------------

    def _load_clusters_data(self) -> List[Dict]:
        """Load clusters from JSON file (cached on first call)."""
        if self._clusters is not None:
            return self._clusters

        if _CLUSTERS_PATH.exists():
            try:
                with open(_CLUSTERS_PATH, "r") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "clusters" in data:
                        self._clusters = data["clusters"]
                    elif isinstance(data, list):
                        self._clusters = data
                    else:
                        self._clusters = []
            except Exception as e:
                logger.error(f"Error loading clusters: {e}")
                self._clusters = []
        else:
            self._clusters = []

        return self._clusters

    def _find_cluster_for_company(self, company_name: str) -> Optional[str]:
        """Find the cluster_id that contains this company (if any)."""
        for c in self._load_clusters_data():
            if company_name in c.get("companies", []):
                return c.get("cluster_id")
        return None

    # ------------------------------------------------------------------
    # Network helpers
    # ------------------------------------------------------------------

    async def _network_from_db(
        self, company_name: str, depth: int = 2
    ) -> Dict[str, Any]:
        """
        Build ego-network from tender_bidders table.

        We find all companies that co-bid with the target, then optionally
        their co-bidders (depth 2).
        """
        if self._pool is None:
            return self._network_from_clusters(company_name)

        try:
            async with self._pool.acquire() as conn:
                # Get co-bidders (depth 1)
                rows = await conn.fetch(
                    """
                    WITH target_tenders AS (
                        SELECT DISTINCT tender_id FROM tender_bidders
                        WHERE company_name = $1
                    )
                    SELECT
                        tb.company_name,
                        COUNT(DISTINCT tb.tender_id) as co_bid_count
                    FROM tender_bidders tb
                    JOIN target_tenders tt ON tb.tender_id = tt.tender_id
                    WHERE tb.company_name != $1
                    GROUP BY tb.company_name
                    ORDER BY co_bid_count DESC
                    LIMIT 30
                    """,
                    company_name,
                )

            nodes = [
                {
                    "id": company_name,
                    "name": company_name,
                    "type": "company",
                    "risk_score": None,
                    "risk_level": None,
                    "metadata": {"center": True},
                }
            ]
            edges = []

            for row in rows:
                neighbor = row["company_name"]
                weight = float(row["co_bid_count"])
                nodes.append(
                    {
                        "id": neighbor,
                        "name": neighbor,
                        "type": "company",
                        "risk_score": None,
                        "risk_level": None,
                    }
                )
                edges.append(
                    {
                        "source": company_name,
                        "target": neighbor,
                        "type": "co_bid",
                        "weight": weight,
                    }
                )

            return {
                "nodes": nodes,
                "edges": edges,
                "center_node": company_name,
                "cluster_id": None,
            }

        except Exception as e:
            logger.warning(f"DB network lookup failed: {e}")
            return self._network_from_clusters(company_name)

    def _network_from_clusters(self, company_name: str) -> Dict[str, Any]:
        """Build a minimal network from cluster data (JSON fallback)."""
        for c in self._load_clusters_data():
            companies = c.get("companies", [])
            if company_name in companies:
                nodes = [
                    {
                        "id": comp,
                        "name": comp,
                        "type": "company",
                        "risk_score": c.get("confidence", 50.0) / 100,
                        "risk_level": _risk_level(c.get("confidence", 50.0) / 100),
                    }
                    for comp in companies
                ]
                edges = []
                for i, c1 in enumerate(companies):
                    for c2 in companies[i + 1:]:
                        edges.append(
                            {
                                "source": c1,
                                "target": c2,
                                "type": "co_bid",
                                "weight": 1.0,
                            }
                        )

                return {
                    "nodes": nodes,
                    "edges": edges,
                    "center_node": company_name,
                    "cluster_id": c.get("cluster_id"),
                }

        # Company not found in any cluster
        return {
            "nodes": [
                {
                    "id": company_name,
                    "name": company_name,
                    "type": "company",
                    "risk_score": None,
                    "risk_level": None,
                }
            ],
            "edges": [],
            "center_node": company_name,
            "cluster_id": None,
        }
