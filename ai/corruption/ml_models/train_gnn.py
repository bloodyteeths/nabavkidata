#!/usr/bin/env python3
"""
GNN Training Script for Collusion Detection

This script trains a Graph Neural Network (GraphSAGE/GAT) for detecting
collusion networks in public procurement data.

Pipeline:
1. Connect to database and build co-bidding graph
2. Extract node features and create pseudo-labels (semi-supervised)
3. Train GNN model for node classification
4. Extract embeddings and detect collusion clusters
5. Save trained model and output results

Usage:
    python train_gnn.py --epochs 100 --hidden-dim 64 --output-dim 32

Author: nabavkidata.com
"""

import os
import sys
import json
import argparse
import logging
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

# Database connection
import asyncpg

# Check for PyTorch availability
try:
    import torch
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("PyTorch not found. Install with: pip install torch")
    sys.exit(1)

try:
    from torch_geometric.data import Data
    from torch_geometric.utils import to_undirected
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False
    print("PyTorch Geometric not found. Install with: pip install torch_geometric")
    sys.exit(1)

# Local imports
from gnn_collusion import (
    GNNConfig, CollusionGNN, CollusionGNNTrainer,
    GraphFeatureExtractor, create_train_val_masks
)
from graph_builder import GraphBuilder, BidderGraph
from collusion_detector import CollusionClusterDetector, CollusionCluster, export_clusters_to_json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Default database URL
DEFAULT_DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Model output path
MODEL_DIR = Path(__file__).parent / "models"
MODEL_PATH = MODEL_DIR / "gnn_collusion.pt"


class GNNTrainingPipeline:
    """
    Complete GNN training pipeline for collusion detection.

    Steps:
    1. Build co-bidding graph from database
    2. Create pseudo-labels based on heuristics
    3. Train GNN for node classification
    4. Extract embeddings
    5. Detect collusion clusters
    6. Save model and results
    """

    def __init__(
        self,
        database_url: str,
        config: GNNConfig,
        output_dir: Path = MODEL_DIR
    ):
        """
        Initialize training pipeline.

        Args:
            database_url: PostgreSQL connection string
            config: GNN model configuration
            output_dir: Directory for model outputs
        """
        self.database_url = database_url
        self.config = config
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.pool: Optional[asyncpg.Pool] = None
        self.graph: Optional[BidderGraph] = None
        self.model: Optional[CollusionGNN] = None
        self.trainer: Optional[CollusionGNNTrainer] = None
        self.pyg_data: Optional[Data] = None

        logger.info(f"GNN Training Pipeline initialized")
        logger.info(f"Config: hidden_dim={config.hidden_dim}, output_dim={config.output_dim}")
        logger.info(f"Output directory: {self.output_dir}")

    async def connect(self):
        """Establish database connection."""
        logger.info("Connecting to database...")
        self.pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
            command_timeout=300
        )
        logger.info("Database connection established")

    async def disconnect(self):
        """Close database connection."""
        if self.pool:
            await self.pool.close()
            logger.info("Database connection closed")

    async def build_graph(
        self,
        min_co_bids: int = 2,
        time_window_days: int = 730,
        min_bids_per_company: int = 3
    ) -> BidderGraph:
        """
        Build co-bidding graph from database.

        Args:
            min_co_bids: Minimum co-occurrences to create edge
            time_window_days: Time window for data (default 2 years)
            min_bids_per_company: Minimum bids to include a company

        Returns:
            BidderGraph object
        """
        logger.info("Building co-bidding graph from database...")
        logger.info(f"Parameters: min_co_bids={min_co_bids}, "
                   f"time_window={time_window_days}d, min_bids={min_bids_per_company}")

        builder = GraphBuilder(self.pool)

        self.graph = await builder.build_co_bidding_graph(
            min_co_bids=min_co_bids,
            time_window_days=time_window_days,
            min_bids_per_company=min_bids_per_company,
            include_edge_features=True,
            include_labels=True
        )

        logger.info(f"Graph built: {self.graph.num_nodes()} nodes, {self.graph.num_edges()} edges")

        # Compute graph statistics
        stats = await builder.compute_graph_statistics(self.graph)
        logger.info(f"Graph statistics: density={stats.get('density', 0):.4f}, "
                   f"avg_degree={stats.get('avg_degree', 0):.2f}, "
                   f"components={stats.get('num_components', 0)}")

        return self.graph

    def create_pseudo_labels(self) -> torch.Tensor:
        """
        Create pseudo-labels for semi-supervised learning.

        Uses heuristics to identify suspicious nodes:
        1. High single-bidder rate (>50%)
        2. Very high win rate (>80%)
        3. High co-bidding with few partners
        4. Unusual bid patterns

        Returns:
            Tensor of pseudo-labels (0=normal, 1=suspicious)
        """
        logger.info("Creating pseudo-labels for training...")

        num_nodes = len(self.graph.nodes)
        labels = torch.zeros(num_nodes, dtype=torch.long)

        suspicious_count = 0

        for i, node in enumerate(self.graph.nodes):
            if node.node_type != 'bidder':
                continue

            features = node.features
            metadata = node.metadata

            # Heuristic scoring
            suspicion_score = 0

            # High single-bidder rate
            single_bidder_rate = features.get('single_bidder_rate', 0)
            if single_bidder_rate > 0.5:
                suspicion_score += 2
            elif single_bidder_rate > 0.3:
                suspicion_score += 1

            # Very high win rate with many bids
            win_rate = features.get('win_rate', 0)
            total_bids = metadata.get('total_bids', 0)
            if win_rate > 0.8 and total_bids >= 5:
                suspicion_score += 2
            elif win_rate > 0.6 and total_bids >= 10:
                suspicion_score += 1

            # Low institutional diversity with many bids
            num_institutions = features.get('num_institutions', 0)
            if total_bids > 10 and num_institutions < 3:
                suspicion_score += 1

            # High number of co-bidders (graph degree)
            # Calculate degree from edges
            degree = sum(1 for e in self.graph.edges
                        if e.source == i or e.target == i)
            if degree > 10:
                suspicion_score += 1

            # Mark as suspicious if score is high
            if suspicion_score >= 3:
                labels[i] = 1
                suspicious_count += 1

        # If no suspicious nodes found, use unsupervised approach
        if suspicious_count == 0:
            logger.warning("No suspicious nodes found by heuristics, using degree-based approach")
            # Use high-degree nodes as pseudo-positive
            degrees = []
            for i in range(num_nodes):
                degree = sum(1 for e in self.graph.edges
                            if e.source == i or e.target == i)
                degrees.append(degree)

            degrees = np.array(degrees)
            threshold = np.percentile(degrees, 90)  # Top 10%

            for i, degree in enumerate(degrees):
                if degree >= threshold:
                    labels[i] = 1
                    suspicious_count += 1

        logger.info(f"Pseudo-labels created: {suspicious_count}/{num_nodes} suspicious nodes "
                   f"({100*suspicious_count/num_nodes:.1f}%)")

        return labels

    def prepare_pyg_data(self) -> Data:
        """
        Convert BidderGraph to PyTorch Geometric Data object.

        Also augments node features with graph-based features.

        Returns:
            PyG Data object ready for training
        """
        logger.info("Preparing PyTorch Geometric data...")

        # Convert to PyG Data
        self.pyg_data = self.graph.to_pyg_data()

        if self.pyg_data is None:
            raise RuntimeError("Failed to convert graph to PyG format")

        # Create pseudo-labels
        labels = self.create_pseudo_labels()
        self.pyg_data.y = labels

        # Augment with graph features
        try:
            import networkx as nx
            G = self.graph.to_networkx()

            if G is not None:
                extractor = GraphFeatureExtractor()
                graph_features, feature_names = extractor.extract_features(G)

                logger.info(f"Extracted graph features: {feature_names}")

                # Combine with existing features
                graph_features_tensor = torch.tensor(graph_features, dtype=torch.float32)
                self.pyg_data.x = torch.cat([self.pyg_data.x, graph_features_tensor], dim=1)

                logger.info(f"Final feature dimension: {self.pyg_data.x.shape[1]}")
        except Exception as e:
            logger.warning(f"Could not extract graph features: {e}")

        # Make edges undirected
        edge_index = to_undirected(self.pyg_data.edge_index)
        self.pyg_data.edge_index = edge_index

        # Update config with actual input dimension
        self.config.input_dim = self.pyg_data.x.shape[1]

        logger.info(f"PyG Data prepared: {self.pyg_data.num_nodes} nodes, "
                   f"{self.pyg_data.edge_index.shape[1]} edges, "
                   f"{self.pyg_data.x.shape[1]} features")

        return self.pyg_data

    def train_model(
        self,
        epochs: Optional[int] = None,
        train_ratio: float = 0.7,
        val_ratio: float = 0.15
    ) -> Dict[str, List[float]]:
        """
        Train the GNN model.

        Args:
            epochs: Number of training epochs (default from config)
            train_ratio: Fraction of nodes for training
            val_ratio: Fraction of nodes for validation

        Returns:
            Training history dictionary
        """
        epochs = epochs or self.config.epochs

        logger.info(f"Training GNN model for {epochs} epochs...")

        # Create model
        self.model = CollusionGNN(self.config)

        # Create trainer
        self.trainer = CollusionGNNTrainer(self.model, self.config)

        # Create train/val/test masks
        train_mask, val_mask, test_mask = create_train_val_masks(
            num_nodes=self.pyg_data.num_nodes,
            train_ratio=train_ratio,
            val_ratio=val_ratio
        )

        logger.info(f"Train: {train_mask.sum().item()}, "
                   f"Val: {val_mask.sum().item()}, "
                   f"Test: {test_mask.sum().item()}")

        # Train
        history = self.trainer.train_node_classification(
            data=self.pyg_data,
            train_mask=train_mask,
            val_mask=val_mask,
            epochs=epochs
        )

        # Evaluate on test set
        self.model.eval()
        with torch.no_grad():
            logits = self.model(self.pyg_data.to(self.trainer.device))
            test_pred = logits[test_mask].argmax(dim=1)
            test_acc = (test_pred == self.pyg_data.y[test_mask].to(self.trainer.device)).float().mean()
            logger.info(f"Test accuracy: {test_acc.item():.4f}")

        # Final metrics
        final_train_acc = history['train_acc'][-1] if history['train_acc'] else 0
        final_val_acc = history['val_acc'][-1] if history['val_acc'] else 0

        logger.info(f"Training complete. "
                   f"Train Acc: {final_train_acc:.4f}, "
                   f"Val Acc: {final_val_acc:.4f}")

        return history

    def get_embeddings(self) -> np.ndarray:
        """
        Get node embeddings from trained model.

        Returns:
            Node embeddings array [num_nodes, output_dim]
        """
        logger.info("Extracting node embeddings...")

        embeddings = self.trainer.get_node_embeddings(self.pyg_data)

        logger.info(f"Embeddings shape: {embeddings.shape}")

        return embeddings

    async def detect_clusters(
        self,
        embeddings: np.ndarray,
        min_cluster_size: int = 3,
        min_confidence: float = 50.0
    ) -> List[CollusionCluster]:
        """
        Detect collusion clusters using embeddings and graph analysis.

        Args:
            embeddings: Node embeddings from GNN
            min_cluster_size: Minimum companies per cluster
            min_confidence: Minimum confidence threshold

        Returns:
            List of detected CollusionCluster objects
        """
        logger.info("Detecting collusion clusters...")

        detector = CollusionClusterDetector(self.pool)

        # Use individual detection methods to avoid timeouts
        all_clusters = []

        # 1. Community Detection (fast)
        try:
            community_clusters = await detector.detect_communities(self.graph, min_cluster_size)
            all_clusters.extend(community_clusters)
            logger.info(f"Community detection found {len(community_clusters)} clusters")
        except Exception as e:
            logger.warning(f"Community detection failed: {e}")

        # 2. Embedding-based clustering (fast)
        try:
            embedding_clusters = await detector.detect_from_embeddings(
                self.graph, embeddings, min_cluster_size
            )
            all_clusters.extend(embedding_clusters)
            logger.info(f"Embedding clustering found {len(embedding_clusters)} clusters")
        except Exception as e:
            logger.warning(f"Embedding clustering failed: {e}")

        # 3. Dense Subgraph Detection (fast)
        try:
            dense_clusters = await detector.detect_dense_subgraphs(self.graph, min_cluster_size)
            all_clusters.extend(dense_clusters)
            logger.info(f"Dense subgraph detection found {len(dense_clusters)} clusters")
        except Exception as e:
            logger.warning(f"Dense subgraph detection failed: {e}")

        # 4. Bid pattern detection (can be slow, skip for now)
        # pattern_clusters = await detector.detect_bid_patterns(graph, min_cluster_size)

        # Merge overlapping clusters
        clusters = detector._merge_overlapping_clusters(all_clusters)

        # Filter by confidence
        clusters = [c for c in clusters if c.confidence >= min_confidence]

        # Sort by confidence
        clusters.sort(key=lambda c: c.confidence, reverse=True)

        logger.info(f"Detected {len(clusters)} collusion clusters")

        # Log top clusters
        for i, cluster in enumerate(clusters[:5]):
            logger.info(f"Cluster {i+1}: {len(cluster.companies)} companies, "
                       f"confidence={cluster.confidence:.1f}%, "
                       f"pattern={cluster.pattern_type}")
            logger.info(f"  Companies: {cluster.companies[:5]}...")

        return clusters

    def save_model(self, path: Optional[Path] = None):
        """
        Save trained model to file.

        Args:
            path: Output path (default: models/gnn_collusion.pt)
        """
        path = path or MODEL_PATH

        logger.info(f"Saving model to {path}...")

        # Save via trainer (includes optimizer state, config, history)
        self.trainer.save(str(path))

        # Also save graph info for later use
        graph_info = {
            'num_nodes': len(self.graph.nodes),
            'num_edges': len(self.graph.edges),
            'node_names': [n.name for n in self.graph.nodes],
            'feature_dim': self.config.input_dim,
            'hidden_dim': self.config.hidden_dim,
            'output_dim': self.config.output_dim,
            'created_at': datetime.utcnow().isoformat()
        }

        graph_info_path = path.parent / 'graph_info.json'
        with open(graph_info_path, 'w', encoding='utf-8') as f:
            json.dump(graph_info, f, indent=2, ensure_ascii=False)

        logger.info(f"Model saved to {path}")
        logger.info(f"Graph info saved to {graph_info_path}")

    def save_clusters(
        self,
        clusters: List[CollusionCluster],
        path: Optional[Path] = None
    ):
        """
        Save detected clusters to JSON file.

        Args:
            clusters: List of clusters to save
            path: Output path
        """
        path = path or (self.output_dir / 'collusion_clusters.json')

        # Custom JSON encoder for numpy types
        class NumpyEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, np.floating):
                    return float(obj)
                if isinstance(obj, np.integer):
                    return int(obj)
                if isinstance(obj, np.ndarray):
                    return obj.tolist()
                return super().default(obj)

        data = {
            'generated_at': datetime.utcnow().isoformat(),
            'num_clusters': len(clusters),
            'clusters': [c.to_dict() for c in clusters]
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False, cls=NumpyEncoder)

        logger.info(f"Clusters saved to {path}")

    def predict_node_risk(self) -> List[Dict[str, Any]]:
        """
        Get risk predictions for all nodes.

        Returns:
            List of dicts with company name, prediction, and probability
        """
        logger.info("Getting node risk predictions...")

        predictions, probs = self.trainer.predict_node_risk(self.pyg_data)

        results = []
        for i, node in enumerate(self.graph.nodes):
            if node.node_type != 'bidder':
                continue

            results.append({
                'company_name': node.name,
                'prediction': int(predictions[i]),
                'probability': float(probs[i, 1]),  # Prob of class 1 (suspicious)
                'risk_level': 'high' if probs[i, 1] > 0.7 else ('medium' if probs[i, 1] > 0.4 else 'low')
            })

        # Sort by probability
        results.sort(key=lambda x: x['probability'], reverse=True)

        # Log top risky companies
        logger.info("Top 10 highest risk companies:")
        for r in results[:10]:
            logger.info(f"  {r['company_name']}: {r['probability']:.3f} ({r['risk_level']})")

        return results

    async def run(
        self,
        epochs: int = 100,
        min_co_bids: int = 2,
        time_window_days: int = 730,
        min_bids_per_company: int = 3,
        min_cluster_size: int = 3,
        min_confidence: float = 50.0,
        save_to_db: bool = False
    ) -> Dict[str, Any]:
        """
        Run the complete training pipeline.

        Args:
            epochs: Training epochs
            min_co_bids: Minimum co-bids for graph edge
            time_window_days: Data time window
            min_bids_per_company: Min bids to include company
            min_cluster_size: Min companies per cluster
            min_confidence: Min confidence for clusters
            save_to_db: Save clusters to database

        Returns:
            Results dictionary with model info, clusters, predictions
        """
        try:
            # Connect to database
            await self.connect()

            # Build graph
            await self.build_graph(
                min_co_bids=min_co_bids,
                time_window_days=time_window_days,
                min_bids_per_company=min_bids_per_company
            )

            if self.graph.num_nodes() < 10:
                logger.error("Graph too small for training. Need at least 10 nodes.")
                return {'error': 'Insufficient data'}

            # Prepare PyG data
            self.prepare_pyg_data()

            # Train model
            history = self.train_model(epochs=epochs)

            # Get embeddings
            embeddings = self.get_embeddings()

            # Detect clusters
            clusters = await self.detect_clusters(
                embeddings=embeddings,
                min_cluster_size=min_cluster_size,
                min_confidence=min_confidence
            )

            # Save clusters to database if requested
            if save_to_db and clusters:
                detector = CollusionClusterDetector(self.pool)
                saved_count = await detector.save_clusters_to_db(clusters)
                logger.info(f"Saved {saved_count} relationships to database")

            # Get predictions
            predictions = self.predict_node_risk()

            # Save model
            self.save_model()

            # Save clusters
            self.save_clusters(clusters)

            # Save predictions
            predictions_path = self.output_dir / 'node_predictions.json'
            with open(predictions_path, 'w', encoding='utf-8') as f:
                json.dump({
                    'generated_at': datetime.utcnow().isoformat(),
                    'num_predictions': len(predictions),
                    'predictions': predictions
                }, f, indent=2, ensure_ascii=False)
            logger.info(f"Predictions saved to {predictions_path}")

            # Return results
            return {
                'status': 'success',
                'model_path': str(MODEL_PATH),
                'graph_stats': {
                    'num_nodes': self.graph.num_nodes(),
                    'num_edges': self.graph.num_edges()
                },
                'training': {
                    'epochs': len(history['train_loss']),
                    'final_train_acc': history['train_acc'][-1] if history['train_acc'] else 0,
                    'final_val_acc': history['val_acc'][-1] if history['val_acc'] else 0,
                    'best_val_loss': self.trainer.best_val_loss
                },
                'clusters': {
                    'total': len(clusters),
                    'high_confidence': sum(1 for c in clusters if c.confidence >= 70),
                    'samples': [c.to_dict() for c in clusters[:5]]
                },
                'high_risk_companies': predictions[:20]
            }

        finally:
            await self.disconnect()


async def main():
    """Main entry point for training script."""
    parser = argparse.ArgumentParser(
        description='Train GNN for collusion detection'
    )

    # Model parameters
    parser.add_argument('--hidden-dim', type=int, default=64,
                       help='Hidden layer dimension (default: 64)')
    parser.add_argument('--output-dim', type=int, default=32,
                       help='Output embedding dimension (default: 32)')
    parser.add_argument('--num-layers', type=int, default=3,
                       help='Number of GNN layers (default: 3)')
    parser.add_argument('--num-heads', type=int, default=4,
                       help='Number of attention heads (default: 4)')
    parser.add_argument('--dropout', type=float, default=0.3,
                       help='Dropout rate (default: 0.3)')

    # Training parameters
    parser.add_argument('--epochs', type=int, default=100,
                       help='Training epochs (default: 100)')
    parser.add_argument('--learning-rate', type=float, default=0.001,
                       help='Learning rate (default: 0.001)')
    parser.add_argument('--patience', type=int, default=15,
                       help='Early stopping patience (default: 15)')

    # Graph parameters
    parser.add_argument('--min-co-bids', type=int, default=2,
                       help='Minimum co-bids for edge (default: 2)')
    parser.add_argument('--time-window', type=int, default=730,
                       help='Time window in days (default: 730)')
    parser.add_argument('--min-bids', type=int, default=3,
                       help='Minimum bids per company (default: 3)')

    # Cluster detection
    parser.add_argument('--min-cluster-size', type=int, default=3,
                       help='Minimum cluster size (default: 3)')
    parser.add_argument('--min-confidence', type=float, default=50.0,
                       help='Minimum cluster confidence (default: 50.0)')

    # Database
    parser.add_argument('--database-url', type=str, default=DEFAULT_DATABASE_URL,
                       help='PostgreSQL connection string')

    # Options
    parser.add_argument('--save-to-db', action='store_true',
                       help='Save detected clusters to database')
    parser.add_argument('--output-dir', type=str, default=str(MODEL_DIR),
                       help='Output directory for models and results')

    args = parser.parse_args()

    # Create config
    config = GNNConfig(
        input_dim=10,  # Will be updated after data loading
        hidden_dim=args.hidden_dim,
        output_dim=args.output_dim,
        num_layers=args.num_layers,
        num_heads=args.num_heads,
        dropout=args.dropout,
        learning_rate=args.learning_rate,
        epochs=args.epochs,
        patience=args.patience,
        num_classes=2  # Binary classification: normal vs suspicious
    )

    # Create and run pipeline
    pipeline = GNNTrainingPipeline(
        database_url=args.database_url,
        config=config,
        output_dir=Path(args.output_dir)
    )

    results = await pipeline.run(
        epochs=args.epochs,
        min_co_bids=args.min_co_bids,
        time_window_days=args.time_window,
        min_bids_per_company=args.min_bids,
        min_cluster_size=args.min_cluster_size,
        min_confidence=args.min_confidence,
        save_to_db=args.save_to_db
    )

    # Print summary
    print("\n" + "="*60)
    print("GNN COLLUSION DETECTION - TRAINING COMPLETE")
    print("="*60)

    if results.get('status') == 'success':
        print(f"\nModel saved to: {results['model_path']}")
        print(f"\nGraph Statistics:")
        print(f"  Nodes: {results['graph_stats']['num_nodes']}")
        print(f"  Edges: {results['graph_stats']['num_edges']}")

        print(f"\nTraining Results:")
        print(f"  Epochs: {results['training']['epochs']}")
        print(f"  Train Accuracy: {results['training']['final_train_acc']:.4f}")
        print(f"  Val Accuracy: {results['training']['final_val_acc']:.4f}")

        print(f"\nDetected Clusters:")
        print(f"  Total: {results['clusters']['total']}")
        print(f"  High Confidence (>=70%): {results['clusters']['high_confidence']}")

        if results['clusters']['samples']:
            print(f"\nTop Clusters:")
            for i, cluster in enumerate(results['clusters']['samples'], 1):
                print(f"  {i}. {len(cluster['companies'])} companies, "
                     f"confidence={cluster['confidence']:.1f}%, "
                     f"pattern={cluster['pattern_type']}")

        if results['high_risk_companies']:
            print(f"\nTop High-Risk Companies:")
            for i, comp in enumerate(results['high_risk_companies'][:10], 1):
                print(f"  {i}. {comp['company_name']}: "
                     f"{comp['probability']:.3f} ({comp['risk_level']})")
    else:
        print(f"\nError: {results.get('error', 'Unknown error')}")

    print("\n" + "="*60)


if __name__ == '__main__':
    asyncio.run(main())
