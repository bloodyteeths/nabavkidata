#!/usr/bin/env python3
"""
Export GNN Model to Lightweight Inference Format

PyTorch Geometric models with message-passing (SAGEConv, GATConv) cannot
be trivially exported to ONNX because the dynamic neighbour-aggregation
operators are not supported by the ONNX opset.

Instead, this script:
1. Loads the trained CollusionGNN checkpoint
2. Runs a full forward pass on the training graph
3. Extracts the pre-computed node embeddings
4. Extracts the classifier head weights
5. Saves everything as a single .npz file

The inference service (gnn_inference.py) can then load this .npz and do
classification via a simple numpy matmul -- no torch/pyg required at
serving time.

Usage:
    # After training, run once on a machine with torch + pyg installed:
    python export_gnn_onnx.py

    # Or with explicit paths:
    python export_gnn_onnx.py --model models/gnn_collusion.pt \\
                              --graph-info models/graph_info.json \\
                              --output models/gnn_node_embeddings.npz

Output file contents (numpy arrays):
    embeddings       [N, D]     float32   node embeddings
    node_names       [N]        object    company names (unicode strings)
    classifier_weight [C, D]    float32   classifier linear layer weight
    classifier_bias   [C]       float32   classifier linear layer bias
    config           dict                 model config for reference

Author: nabavkidata.com
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import numpy as np

# Setup path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Default paths
MODEL_DIR = Path(__file__).parent / "models"
DEFAULT_MODEL_PATH = MODEL_DIR / "gnn_collusion.pt"
DEFAULT_GRAPH_INFO = MODEL_DIR / "graph_info.json"
DEFAULT_OUTPUT = MODEL_DIR / "gnn_node_embeddings.npz"

# Database URL (for graph reconstruction if needed)
DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", "")


def export_embeddings(
    model_path: str = str(DEFAULT_MODEL_PATH),
    graph_info_path: str = str(DEFAULT_GRAPH_INFO),
    output_path: str = str(DEFAULT_OUTPUT),
    database_url: Optional[str] = None,
):
    """
    Export GNN node embeddings and classifier weights to .npz.

    Steps:
    1. Load the PyTorch checkpoint
    2. Reconstruct the graph from graph_info.json (node features + edge_index)
       or from the database if graph data is not cached locally
    3. Do a forward pass to get embeddings
    4. Extract classifier head weights
    5. Save to .npz
    """
    # Import torch (this script requires it)
    try:
        import torch
        import torch.nn.functional as F
    except ImportError:
        logger.error("PyTorch is required to run this export script.")
        logger.error("Install with: pip install torch")
        sys.exit(1)

    try:
        from torch_geometric.data import Data
        from torch_geometric.utils import to_undirected
    except ImportError:
        logger.error("PyTorch Geometric is required to run this export script.")
        logger.error("Install with: pip install torch_geometric")
        sys.exit(1)

    from ai.corruption.ml_models.gnn_collusion import (
        CollusionGNN,
        GNNConfig,
    )

    # ------------------------------------------------------------------
    # 1. Load checkpoint
    # ------------------------------------------------------------------
    logger.info(f"Loading checkpoint from {model_path}")
    checkpoint = torch.load(model_path, map_location="cpu")

    config_dict = checkpoint.get("config", {})
    config = GNNConfig(**config_dict)

    model = CollusionGNN(config)
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()

    logger.info(
        f"Model loaded: input_dim={config.input_dim}, "
        f"hidden_dim={config.hidden_dim}, output_dim={config.output_dim}"
    )

    # ------------------------------------------------------------------
    # 2. Load or build graph data
    # ------------------------------------------------------------------
    node_names = []
    pyg_data = None

    # Try loading from graph_info + locally cached data
    if Path(graph_info_path).exists():
        with open(graph_info_path, "r") as f:
            graph_info = json.load(f)
        node_names = graph_info.get("node_names", [])
        logger.info(f"Graph info loaded: {len(node_names)} node names")

    # We need the actual PyG Data to do a forward pass.
    # Option A: Rebuild from database (requires async)
    # Option B: Use the saved .pt file if it contains graph data
    if "graph_data" in checkpoint:
        logger.info("Graph data found in checkpoint, reconstructing PyG Data...")
        gd = checkpoint["graph_data"]
        pyg_data = Data(
            x=gd["x"] if isinstance(gd["x"], torch.Tensor) else torch.tensor(gd["x"], dtype=torch.float32),
            edge_index=gd["edge_index"] if isinstance(gd["edge_index"], torch.Tensor) else torch.tensor(gd["edge_index"], dtype=torch.long),
        )
    else:
        # Rebuild from DB
        logger.info("No graph data in checkpoint, rebuilding from database...")
        db_url = database_url or DEFAULT_DATABASE_URL
        pyg_data = _rebuild_graph_from_db(db_url, config)
        if pyg_data is not None and len(node_names) == 0:
            logger.warning("Graph rebuilt but no node_names available from graph_info")

    if pyg_data is None:
        logger.error(
            "Cannot reconstruct graph data. Ensure graph_info.json exists "
            "and the database is reachable, or re-train to include graph_data in checkpoint."
        )
        sys.exit(1)

    logger.info(
        f"PyG Data: {pyg_data.num_nodes} nodes, "
        f"{pyg_data.edge_index.shape[1]} edges, "
        f"{pyg_data.x.shape[1]} features"
    )

    # ------------------------------------------------------------------
    # 3. Forward pass to get embeddings
    # ------------------------------------------------------------------
    logger.info("Running forward pass...")
    with torch.no_grad():
        embeddings = model.get_embeddings(pyg_data)  # [N, D]

    embeddings_np = embeddings.cpu().numpy().astype(np.float32)
    logger.info(f"Embeddings shape: {embeddings_np.shape}")

    # ------------------------------------------------------------------
    # 4. Extract classifier weights
    # ------------------------------------------------------------------
    classifier_state = {}
    for name, param in model.classifier.named_parameters():
        classifier_state[name] = param.cpu().detach().numpy()

    # The classifier is Sequential(Linear, ReLU, Dropout, Linear)
    # We want the final Linear layer for the simple numpy classifier
    # named "3.weight" and "3.bias" (0-indexed layers)
    final_weight = classifier_state.get("3.weight")
    final_bias = classifier_state.get("3.bias")

    if final_weight is None:
        # Try to extract any weight/bias pair
        weights = {k: v for k, v in classifier_state.items() if "weight" in k}
        biases = {k: v for k, v in classifier_state.items() if "bias" in k}
        if weights and biases:
            # Use the last ones
            wk = sorted(weights.keys())[-1]
            bk = sorted(biases.keys())[-1]
            final_weight = weights[wk]
            final_bias = biases[bk]
            logger.info(f"Using classifier params: {wk}, {bk}")

    if final_weight is not None:
        logger.info(
            f"Classifier weight shape: {final_weight.shape}, "
            f"bias shape: {final_bias.shape}"
        )

    # ------------------------------------------------------------------
    # 5. Also run the full forward pass for probabilities
    # ------------------------------------------------------------------
    with torch.no_grad():
        logits = model(pyg_data)
        probs = F.softmax(logits, dim=1).cpu().numpy()

    # ------------------------------------------------------------------
    # 6. Save to .npz
    # ------------------------------------------------------------------
    save_dict = {
        "embeddings": embeddings_np,
        "node_names": np.array(node_names, dtype=object),
        "probabilities": probs.astype(np.float32),
        "config": np.array(json.dumps(config_dict), dtype=object),
    }

    if final_weight is not None:
        save_dict["classifier_weight"] = final_weight.astype(np.float32)
        save_dict["classifier_bias"] = final_bias.astype(np.float32)

    np.savez_compressed(output_path, **save_dict)

    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    logger.info(f"Saved to {output_path} ({file_size_mb:.1f} MB)")
    logger.info(f"  embeddings:  {embeddings_np.shape}")
    logger.info(f"  node_names:  {len(node_names)}")
    logger.info(f"  probs:       {probs.shape}")
    if final_weight is not None:
        logger.info(f"  classifier:  {final_weight.shape} + {final_bias.shape}")

    return output_path


def _rebuild_graph_from_db(database_url: str, config: "GNNConfig"):
    """
    Rebuild the PyG Data by connecting to the database and running
    the graph builder pipeline.

    Returns a PyG Data object or None if it fails.
    """
    import asyncio

    try:
        import asyncpg
        from ai.corruption.ml_models.graph_builder import GraphBuilder
        from ai.corruption.ml_models.gnn_collusion import GraphFeatureExtractor
        from torch_geometric.utils import to_undirected
        import torch
    except ImportError as e:
        logger.error(f"Missing dependency for graph rebuild: {e}")
        return None

    async def _build():
        pool = await asyncpg.create_pool(database_url, min_size=2, max_size=5, command_timeout=300)
        try:
            builder = GraphBuilder(pool)
            graph = await builder.build_co_bidding_graph(
                min_co_bids=2,
                time_window_days=730,
                min_bids_per_company=3,
                include_edge_features=False,
                include_labels=False,
            )

            if graph.num_nodes() < 2:
                logger.error("Graph too small")
                return None

            pyg_data = graph.to_pyg_data()
            if pyg_data is None:
                return None

            # Augment with graph features (same as training)
            try:
                import networkx as nx
                G = graph.to_networkx()
                if G is not None:
                    extractor = GraphFeatureExtractor()
                    graph_features, _ = extractor.extract_features(G)
                    gf_tensor = torch.tensor(graph_features, dtype=torch.float32)
                    pyg_data.x = torch.cat([pyg_data.x, gf_tensor], dim=1)
            except Exception as e:
                logger.warning(f"Graph feature augmentation failed: {e}")

            # Make edges undirected
            pyg_data.edge_index = to_undirected(pyg_data.edge_index)

            return pyg_data
        finally:
            await pool.close()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an already-running loop (e.g. Jupyter)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, _build())
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(_build())
    except RuntimeError:
        return asyncio.run(_build())
    except Exception as e:
        logger.error(f"Graph rebuild failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="Export GNN model to lightweight .npz for inference"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=str(DEFAULT_MODEL_PATH),
        help="Path to .pt checkpoint",
    )
    parser.add_argument(
        "--graph-info",
        type=str,
        default=str(DEFAULT_GRAPH_INFO),
        help="Path to graph_info.json",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=str(DEFAULT_OUTPUT),
        help="Output .npz path",
    )
    parser.add_argument(
        "--database-url",
        type=str,
        default=None,
        help="PostgreSQL connection string (for graph rebuild)",
    )

    args = parser.parse_args()
    export_embeddings(
        model_path=args.model,
        graph_info_path=args.graph_info,
        output_path=args.output,
        database_url=args.database_url,
    )


if __name__ == "__main__":
    main()
