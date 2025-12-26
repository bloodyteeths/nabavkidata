"""
Graph Neural Network for Collusion Detection

Implements a GNN architecture for detecting collusion networks in public procurement:
1. GraphSAGE layers for neighborhood aggregation
2. Graph Attention (GAT) layers for weighted relationships
3. Node classification: predict collusion risk per company
4. Edge prediction: predict if two companies are colluding

Architecture:
    Input -> GraphSAGE(64) -> ReLU -> Dropout
          -> GraphSAGE(64) -> ReLU -> Dropout
          -> GAT(32, heads=4) -> ELU -> Dropout
          -> Linear(128) -> ReLU
          -> Linear(num_classes or 1)

The model can be trained for:
- Node classification: Is this company involved in collusion?
- Edge prediction: Are these two companies colluding?
- Graph embedding: Get embeddings for clustering

Author: nabavkidata.com
License: Proprietary
"""

import logging
import os
import json
from typing import Dict, List, Optional, Tuple, Any, Union
from dataclasses import dataclass
from datetime import datetime
import numpy as np

# PyTorch imports
try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    from torch.optim import Adam, AdamW
    from torch.optim.lr_scheduler import ReduceLROnPlateau, CosineAnnealingLR
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    F = None

# PyTorch Geometric imports
try:
    from torch_geometric.nn import SAGEConv, GATConv, GCNConv, global_mean_pool, global_max_pool
    from torch_geometric.data import Data, Batch
    from torch_geometric.loader import NeighborLoader, DataLoader
    from torch_geometric.utils import negative_sampling, to_undirected
    PYG_AVAILABLE = True
except ImportError:
    PYG_AVAILABLE = False
    SAGEConv = None
    GATConv = None
    Data = None
    Batch = None
    NeighborLoader = None

logger = logging.getLogger(__name__)


@dataclass
class GNNConfig:
    """Configuration for CollusionGNN model."""
    # Model architecture
    input_dim: int = 10  # Number of node features
    hidden_dim: int = 64  # Hidden layer dimension
    output_dim: int = 32  # Embedding dimension
    num_layers: int = 3  # Number of GNN layers
    num_heads: int = 4  # Number of attention heads for GAT
    dropout: float = 0.3  # Dropout rate
    use_gat: bool = True  # Use GAT layer at the end

    # Training
    learning_rate: float = 0.001
    weight_decay: float = 1e-4
    epochs: int = 100
    batch_size: int = 256
    patience: int = 15  # Early stopping patience

    # Task
    task: str = 'node_classification'  # 'node_classification', 'link_prediction', 'embedding'
    num_classes: int = 2  # For classification tasks

    # Sampling for large graphs
    num_neighbors: List[int] = None  # e.g., [25, 10] for 2-hop sampling

    def __post_init__(self):
        if self.num_neighbors is None:
            self.num_neighbors = [25, 10, 5][:self.num_layers]


class CollusionGNN(nn.Module):
    """
    Graph Neural Network for collusion detection.

    Uses GraphSAGE for neighborhood aggregation and optionally GAT
    for attention-weighted relationships.

    Supports:
    - Node classification (is company colluding?)
    - Link prediction (are these companies colluding together?)
    - Graph embedding extraction for downstream clustering

    Usage:
        config = GNNConfig(input_dim=10, hidden_dim=64)
        model = CollusionGNN(config)

        # For node classification
        logits = model(data)
        loss = F.cross_entropy(logits[data.train_mask], data.y[data.train_mask])

        # For embeddings
        embeddings = model.get_embeddings(data)
    """

    def __init__(self, config: GNNConfig):
        if not TORCH_AVAILABLE or not PYG_AVAILABLE:
            raise ImportError(
                "PyTorch and PyTorch Geometric are required. "
                "Install with: pip install torch torch_geometric"
            )

        super().__init__()
        self.config = config

        # Build layers
        self.convs = nn.ModuleList()
        self.norms = nn.ModuleList()

        # First layer: input_dim -> hidden_dim
        self.convs.append(SAGEConv(config.input_dim, config.hidden_dim))
        self.norms.append(nn.LayerNorm(config.hidden_dim))

        # Middle layers: hidden_dim -> hidden_dim
        for _ in range(config.num_layers - 2):
            self.convs.append(SAGEConv(config.hidden_dim, config.hidden_dim))
            self.norms.append(nn.LayerNorm(config.hidden_dim))

        # Final GNN layer
        if config.use_gat and config.num_layers > 1:
            # GAT layer with multi-head attention
            self.convs.append(GATConv(
                config.hidden_dim,
                config.output_dim,
                heads=config.num_heads,
                dropout=config.dropout,
                concat=False  # Average heads
            ))
            self.norms.append(nn.LayerNorm(config.output_dim))
        else:
            self.convs.append(SAGEConv(config.hidden_dim, config.output_dim))
            self.norms.append(nn.LayerNorm(config.output_dim))

        # Classification head
        self.classifier = nn.Sequential(
            nn.Linear(config.output_dim, config.output_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.output_dim, config.num_classes)
        )

        # Link prediction head (for edge prediction)
        self.link_predictor = nn.Sequential(
            nn.Linear(config.output_dim * 2, config.output_dim),
            nn.ReLU(),
            nn.Dropout(config.dropout),
            nn.Linear(config.output_dim, 1)
        )

        self.dropout = nn.Dropout(config.dropout)

        logger.info(f"CollusionGNN initialized with {self._count_parameters()} parameters")

    def forward(
        self,
        data: 'Data',
        return_embeddings: bool = False
    ) -> Union['torch.Tensor', Tuple['torch.Tensor', 'torch.Tensor']]:
        """
        Forward pass for node classification.

        Args:
            data: PyTorch Geometric Data object with x, edge_index
            return_embeddings: Also return node embeddings

        Returns:
            Node logits (and embeddings if requested)
        """
        x, edge_index = data.x, data.edge_index

        # Pass through GNN layers
        for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
            x = conv(x, edge_index)
            x = norm(x)

            if i < len(self.convs) - 1:
                x = F.relu(x)
                x = self.dropout(x)
            else:
                x = F.elu(x)  # ELU for final layer

        embeddings = x

        # Classification
        logits = self.classifier(embeddings)

        if return_embeddings:
            return logits, embeddings
        return logits

    def get_embeddings(self, data: 'Data') -> 'torch.Tensor':
        """
        Get node embeddings without classification head.

        Args:
            data: PyTorch Geometric Data object

        Returns:
            Node embeddings [num_nodes, output_dim]
        """
        self.eval()
        with torch.no_grad():
            x, edge_index = data.x, data.edge_index

            for i, (conv, norm) in enumerate(zip(self.convs, self.norms)):
                x = conv(x, edge_index)
                x = norm(x)

                if i < len(self.convs) - 1:
                    x = F.relu(x)
                else:
                    x = F.elu(x)

        return x

    def predict_links(
        self,
        data: 'Data',
        edge_index_query: 'torch.Tensor'
    ) -> 'torch.Tensor':
        """
        Predict probability of edges (link prediction).

        Args:
            data: PyTorch Geometric Data object
            edge_index_query: Edges to predict [2, num_queries]

        Returns:
            Edge probabilities [num_queries]
        """
        embeddings = self.get_embeddings(data)

        # Get source and target embeddings
        src_emb = embeddings[edge_index_query[0]]
        dst_emb = embeddings[edge_index_query[1]]

        # Concatenate and predict
        edge_features = torch.cat([src_emb, dst_emb], dim=1)
        logits = self.link_predictor(edge_features).squeeze(-1)
        probs = torch.sigmoid(logits)

        return probs

    def _count_parameters(self) -> int:
        """Count trainable parameters."""
        return sum(p.numel() for p in self.parameters() if p.requires_grad)


class CollusionGNNTrainer:
    """
    Trainer for CollusionGNN model.

    Supports:
    - Node classification training
    - Link prediction training
    - Early stopping
    - Learning rate scheduling
    - Model checkpointing

    Usage:
        trainer = CollusionGNNTrainer(model, config)
        trainer.train(train_data, val_data)
        trainer.save('model.pt')
    """

    def __init__(
        self,
        model: CollusionGNN,
        config: GNNConfig,
        device: str = 'auto'
    ):
        self.model = model
        self.config = config

        # Set device
        if device == 'auto':
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        self.model = self.model.to(self.device)

        # Optimizer
        self.optimizer = AdamW(
            model.parameters(),
            lr=config.learning_rate,
            weight_decay=config.weight_decay
        )

        # Learning rate scheduler
        self.scheduler = ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        )

        # Loss functions
        self.node_loss_fn = nn.CrossEntropyLoss()
        self.link_loss_fn = nn.BCEWithLogitsLoss()

        # Training history
        self.history = {
            'train_loss': [],
            'val_loss': [],
            'train_acc': [],
            'val_acc': [],
            'learning_rate': []
        }

        # Early stopping
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        self.best_model_state = None

        logger.info(f"Trainer initialized on device: {self.device}")

    def train_node_classification(
        self,
        data: 'Data',
        train_mask: 'torch.Tensor',
        val_mask: 'torch.Tensor',
        epochs: Optional[int] = None
    ) -> Dict[str, List[float]]:
        """
        Train model for node classification task.

        Args:
            data: PyTorch Geometric Data with node labels (data.y)
            train_mask: Boolean mask for training nodes
            val_mask: Boolean mask for validation nodes
            epochs: Override config epochs

        Returns:
            Training history dictionary
        """
        epochs = epochs or self.config.epochs
        data = data.to(self.device)
        train_mask = train_mask.to(self.device)
        val_mask = val_mask.to(self.device)

        logger.info(f"Starting node classification training for {epochs} epochs")
        logger.info(f"Train nodes: {train_mask.sum().item()}, Val nodes: {val_mask.sum().item()}")

        for epoch in range(epochs):
            # Training
            self.model.train()
            self.optimizer.zero_grad()

            logits = self.model(data)
            train_loss = self.node_loss_fn(logits[train_mask], data.y[train_mask])

            train_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

            # Training accuracy
            train_pred = logits[train_mask].argmax(dim=1)
            train_acc = (train_pred == data.y[train_mask]).float().mean().item()

            # Validation
            self.model.eval()
            with torch.no_grad():
                logits = self.model(data)
                val_loss = self.node_loss_fn(logits[val_mask], data.y[val_mask])

                val_pred = logits[val_mask].argmax(dim=1)
                val_acc = (val_pred == data.y[val_mask]).float().mean().item()

            # Update scheduler
            self.scheduler.step(val_loss)
            current_lr = self.optimizer.param_groups[0]['lr']

            # Record history
            self.history['train_loss'].append(train_loss.item())
            self.history['val_loss'].append(val_loss.item())
            self.history['train_acc'].append(train_acc)
            self.history['val_acc'].append(val_acc)
            self.history['learning_rate'].append(current_lr)

            # Early stopping check
            if val_loss < self.best_val_loss:
                self.best_val_loss = val_loss.item()
                self.best_model_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}
                self.patience_counter = 0
            else:
                self.patience_counter += 1

            # Logging
            if (epoch + 1) % 10 == 0 or epoch == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} | "
                    f"Train Loss: {train_loss.item():.4f} | "
                    f"Val Loss: {val_loss.item():.4f} | "
                    f"Train Acc: {train_acc:.4f} | "
                    f"Val Acc: {val_acc:.4f} | "
                    f"LR: {current_lr:.6f}"
                )

            # Early stopping
            if self.patience_counter >= self.config.patience:
                logger.info(f"Early stopping at epoch {epoch+1}")
                break

        # Restore best model
        if self.best_model_state is not None:
            self.model.load_state_dict(self.best_model_state)
            logger.info(f"Restored best model with val_loss: {self.best_val_loss:.4f}")

        return self.history

    def train_link_prediction(
        self,
        data: 'Data',
        pos_edge_index: 'torch.Tensor',
        neg_edge_index: Optional['torch.Tensor'] = None,
        epochs: Optional[int] = None
    ) -> Dict[str, List[float]]:
        """
        Train model for link prediction (collusion edge prediction).

        Args:
            data: PyTorch Geometric Data
            pos_edge_index: Known positive edges (colluding companies)
            neg_edge_index: Known negative edges (or will be sampled)
            epochs: Override config epochs

        Returns:
            Training history
        """
        epochs = epochs or self.config.epochs
        data = data.to(self.device)
        pos_edge_index = pos_edge_index.to(self.device)

        logger.info(f"Starting link prediction training for {epochs} epochs")

        for epoch in range(epochs):
            self.model.train()
            self.optimizer.zero_grad()

            # Get embeddings
            embeddings = self.model.get_embeddings(data)

            # Sample negative edges if not provided
            if neg_edge_index is None:
                neg_edge = negative_sampling(
                    edge_index=data.edge_index,
                    num_nodes=data.num_nodes,
                    num_neg_samples=pos_edge_index.size(1)
                )
            else:
                neg_edge = neg_edge_index.to(self.device)

            # Positive edge scores
            pos_src = embeddings[pos_edge_index[0]]
            pos_dst = embeddings[pos_edge_index[1]]
            pos_features = torch.cat([pos_src, pos_dst], dim=1)
            pos_scores = self.model.link_predictor(pos_features).squeeze()

            # Negative edge scores
            neg_src = embeddings[neg_edge[0]]
            neg_dst = embeddings[neg_edge[1]]
            neg_features = torch.cat([neg_src, neg_dst], dim=1)
            neg_scores = self.model.link_predictor(neg_features).squeeze()

            # Binary cross-entropy loss
            pos_labels = torch.ones(pos_scores.size(0), device=self.device)
            neg_labels = torch.zeros(neg_scores.size(0), device=self.device)

            loss = self.link_loss_fn(pos_scores, pos_labels) + \
                   self.link_loss_fn(neg_scores, neg_labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
            self.optimizer.step()

            # Calculate AUC-like metric
            with torch.no_grad():
                pos_prob = torch.sigmoid(pos_scores)
                neg_prob = torch.sigmoid(neg_scores)
                auc_approx = (pos_prob.mean() > neg_prob.mean()).float().item()

            self.history['train_loss'].append(loss.item())

            if (epoch + 1) % 10 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{epochs} | "
                    f"Loss: {loss.item():.4f} | "
                    f"Pos Prob: {pos_prob.mean().item():.4f} | "
                    f"Neg Prob: {neg_prob.mean().item():.4f}"
                )

        return self.history

    def predict_node_risk(
        self,
        data: 'Data',
        return_probs: bool = True
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Predict collusion risk for all nodes.

        Args:
            data: PyTorch Geometric Data
            return_probs: Return probabilities instead of logits

        Returns:
            Tuple of (predictions, probabilities or logits)
        """
        self.model.eval()
        data = data.to(self.device)

        with torch.no_grad():
            logits = self.model(data)

            if return_probs:
                probs = F.softmax(logits, dim=1)
                predictions = probs.argmax(dim=1)
                return predictions.cpu().numpy(), probs.cpu().numpy()
            else:
                predictions = logits.argmax(dim=1)
                return predictions.cpu().numpy(), logits.cpu().numpy()

    def predict_link_risk(
        self,
        data: 'Data',
        edge_index_query: 'torch.Tensor'
    ) -> np.ndarray:
        """
        Predict collusion probability between pairs of companies.

        Args:
            data: PyTorch Geometric Data
            edge_index_query: Pairs to predict [2, num_pairs]

        Returns:
            Collusion probabilities [num_pairs]
        """
        self.model.eval()
        data = data.to(self.device)
        edge_index_query = edge_index_query.to(self.device)

        with torch.no_grad():
            probs = self.model.predict_links(data, edge_index_query)

        return probs.cpu().numpy()

    def get_node_embeddings(self, data: 'Data') -> np.ndarray:
        """
        Get node embeddings for downstream clustering.

        Args:
            data: PyTorch Geometric Data

        Returns:
            Node embeddings [num_nodes, output_dim]
        """
        self.model.eval()
        data = data.to(self.device)

        with torch.no_grad():
            embeddings = self.model.get_embeddings(data)

        return embeddings.cpu().numpy()

    def save(self, path: str, include_history: bool = True):
        """
        Save model checkpoint.

        Args:
            path: Path to save (.pt file)
            include_history: Include training history
        """
        checkpoint = {
            'model_state_dict': self.model.state_dict(),
            'optimizer_state_dict': self.optimizer.state_dict(),
            'config': self.config.__dict__,
            'best_val_loss': self.best_val_loss,
        }

        if include_history:
            checkpoint['history'] = self.history

        torch.save(checkpoint, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str):
        """
        Load model checkpoint.

        Args:
            path: Path to checkpoint (.pt file)
        """
        checkpoint = torch.load(path, map_location=self.device)

        self.model.load_state_dict(checkpoint['model_state_dict'])
        self.optimizer.load_state_dict(checkpoint['optimizer_state_dict'])

        if 'history' in checkpoint:
            self.history = checkpoint['history']

        if 'best_val_loss' in checkpoint:
            self.best_val_loss = checkpoint['best_val_loss']

        logger.info(f"Model loaded from {path}")


class GraphFeatureExtractor:
    """
    Extract graph-based features for each node.

    Features include:
    - Degree centrality
    - Betweenness centrality
    - Clustering coefficient
    - PageRank
    - Core number (k-core decomposition)
    - Neighborhood features

    These features can be used as additional node features for the GNN
    or for traditional ML models.
    """

    def __init__(self):
        try:
            import networkx as nx
            self.nx = nx
        except ImportError:
            raise ImportError("NetworkX is required. Install with: pip install networkx")

    def extract_features(
        self,
        G,  # NetworkX graph
        feature_names: Optional[List[str]] = None
    ) -> Tuple[np.ndarray, List[str]]:
        """
        Extract graph-based features for all nodes.

        Args:
            G: NetworkX graph
            feature_names: Which features to extract (default: all)

        Returns:
            Tuple of (feature_matrix, feature_names)
        """
        if feature_names is None:
            feature_names = [
                'degree', 'degree_centrality', 'clustering_coefficient',
                'pagerank', 'core_number', 'avg_neighbor_degree',
                'triangles', 'eccentricity'
            ]

        nodes = list(G.nodes())
        n = len(nodes)
        node_to_idx = {node: i for i, node in enumerate(nodes)}

        features = {}

        # Degree
        if 'degree' in feature_names:
            degree = dict(G.degree())
            features['degree'] = [degree[n] for n in nodes]

        # Degree centrality
        if 'degree_centrality' in feature_names:
            dc = self.nx.degree_centrality(G)
            features['degree_centrality'] = [dc[n] for n in nodes]

        # Clustering coefficient
        if 'clustering_coefficient' in feature_names:
            cc = self.nx.clustering(G)
            features['clustering_coefficient'] = [cc[n] for n in nodes]

        # PageRank
        if 'pagerank' in feature_names:
            try:
                pr = self.nx.pagerank(G, max_iter=100)
                features['pagerank'] = [pr[n] for n in nodes]
            except Exception:
                features['pagerank'] = [1.0 / n] * n

        # Core number (k-core decomposition)
        if 'core_number' in feature_names:
            core = self.nx.core_number(G)
            features['core_number'] = [core[n] for n in nodes]

        # Average neighbor degree
        if 'avg_neighbor_degree' in feature_names:
            avg_nd = self.nx.average_neighbor_degree(G)
            features['avg_neighbor_degree'] = [avg_nd.get(n, 0) for n in nodes]

        # Number of triangles
        if 'triangles' in feature_names:
            tri = self.nx.triangles(G)
            features['triangles'] = [tri[n] for n in nodes]

        # Betweenness centrality (expensive for large graphs)
        if 'betweenness_centrality' in feature_names and n <= 5000:
            bc = self.nx.betweenness_centrality(G)
            features['betweenness_centrality'] = [bc[n] for n in nodes]

        # Eccentricity (only for connected graphs)
        if 'eccentricity' in feature_names:
            try:
                if self.nx.is_connected(G):
                    ecc = self.nx.eccentricity(G)
                    features['eccentricity'] = [ecc[n] for n in nodes]
                else:
                    features['eccentricity'] = [0.0] * n
            except Exception:
                features['eccentricity'] = [0.0] * n

        # Build feature matrix
        actual_features = list(features.keys())
        feature_matrix = np.zeros((n, len(actual_features)), dtype=np.float32)

        for j, fname in enumerate(actual_features):
            feature_matrix[:, j] = features[fname]

        # Normalize features
        for j in range(feature_matrix.shape[1]):
            col = feature_matrix[:, j]
            col_max = col.max()
            if col_max > 0:
                feature_matrix[:, j] = col / col_max

        return feature_matrix, actual_features

    def get_node_feature_dict(
        self,
        G,
        node
    ) -> Dict[str, float]:
        """Get features for a single node."""
        features = {}

        features['degree'] = G.degree(node)
        features['clustering_coefficient'] = self.nx.clustering(G, node)
        features['triangles'] = self.nx.triangles(G, node)

        # PageRank
        try:
            pr = self.nx.pagerank(G, max_iter=50)
            features['pagerank'] = pr[node]
        except Exception:
            features['pagerank'] = 0.0

        # Core number
        core = self.nx.core_number(G)
        features['core_number'] = core[node]

        return features


# =============================================================================
# Utility Functions
# =============================================================================

def create_train_val_masks(
    num_nodes: int,
    train_ratio: float = 0.7,
    val_ratio: float = 0.15,
    stratify: Optional[np.ndarray] = None
) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """
    Create training, validation, and test masks.

    Args:
        num_nodes: Total number of nodes
        train_ratio: Fraction for training
        val_ratio: Fraction for validation
        stratify: Labels for stratified split

    Returns:
        Tuple of (train_mask, val_mask, test_mask)
    """
    indices = np.random.permutation(num_nodes)

    train_size = int(num_nodes * train_ratio)
    val_size = int(num_nodes * val_ratio)

    train_idx = indices[:train_size]
    val_idx = indices[train_size:train_size + val_size]
    test_idx = indices[train_size + val_size:]

    train_mask = torch.zeros(num_nodes, dtype=torch.bool)
    val_mask = torch.zeros(num_nodes, dtype=torch.bool)
    test_mask = torch.zeros(num_nodes, dtype=torch.bool)

    train_mask[train_idx] = True
    val_mask[val_idx] = True
    test_mask[test_idx] = True

    return train_mask, val_mask, test_mask


def augment_node_features(
    data: 'Data',
    G,  # NetworkX graph
    normalize: bool = True
) -> 'Data':
    """
    Augment node features with graph-based features.

    Args:
        data: PyTorch Geometric Data
        G: NetworkX graph
        normalize: Normalize features

    Returns:
        Data with augmented node features
    """
    extractor = GraphFeatureExtractor()
    graph_features, feature_names = extractor.extract_features(G)

    # Combine with existing features
    if data.x is not None:
        combined = torch.cat([
            data.x,
            torch.tensor(graph_features, dtype=torch.float32)
        ], dim=1)
    else:
        combined = torch.tensor(graph_features, dtype=torch.float32)

    data.x = combined
    return data


def build_collusion_gnn(
    input_dim: int,
    hidden_dim: int = 64,
    output_dim: int = 32,
    num_classes: int = 2,
    device: str = 'auto'
) -> Tuple[CollusionGNN, CollusionGNNTrainer]:
    """
    Convenience function to build GNN model and trainer.

    Args:
        input_dim: Number of input node features
        hidden_dim: Hidden layer dimension
        output_dim: Embedding dimension
        num_classes: Number of output classes
        device: Device to use

    Returns:
        Tuple of (model, trainer)
    """
    config = GNNConfig(
        input_dim=input_dim,
        hidden_dim=hidden_dim,
        output_dim=output_dim,
        num_classes=num_classes
    )

    model = CollusionGNN(config)
    trainer = CollusionGNNTrainer(model, config, device=device)

    return model, trainer
