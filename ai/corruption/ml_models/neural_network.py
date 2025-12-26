"""
Neural Network Model for Corruption Detection

This module implements a Multi-Layer Perceptron (MLP) for detecting corruption
patterns in public procurement tenders. The architecture is designed to handle
the 113 features extracted by the FeatureExtractor.

Architecture:
    Input(113) -> BatchNorm -> Dense(256) -> ReLU -> Dropout
               -> BatchNorm -> Dense(128) -> ReLU -> Dropout
               -> BatchNorm -> Dense(64) -> ReLU -> Dropout
               -> Dense(1) -> Sigmoid

Features:
- Class-weight handling for imbalanced data
- Learning rate scheduling (ReduceLROnPlateau)
- Early stopping to prevent overfitting
- GPU acceleration when available
- Model checkpointing

Author: nabavkidata.com
License: Proprietary
"""

import logging
import os
from pathlib import Path
from typing import Optional, Tuple, Dict, Any, Union, List

import numpy as np

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import DataLoader, TensorDataset
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    torch = None
    nn = None
    optim = None

logger = logging.getLogger(__name__)


class CorruptionMLP(nn.Module if TORCH_AVAILABLE else object):
    """
    Multi-Layer Perceptron for corruption detection.

    Architecture:
        - Input layer: 113 features
        - Hidden layer 1: 256 neurons with BatchNorm, ReLU, Dropout
        - Hidden layer 2: 128 neurons with BatchNorm, ReLU, Dropout
        - Hidden layer 3: 64 neurons with BatchNorm, ReLU, Dropout
        - Output layer: 1 neuron with Sigmoid activation

    The model uses:
        - BatchNorm for training stability
        - Dropout for regularization
        - ReLU activations for hidden layers
        - Sigmoid activation for binary output
    """

    def __init__(
        self,
        input_dim: int = 113,
        hidden_dims: Tuple[int, ...] = (256, 128, 64),
        dropout_rate: float = 0.3
    ):
        """
        Initialize the MLP architecture.

        Args:
            input_dim: Number of input features (default: 113)
            hidden_dims: Tuple of hidden layer dimensions
            dropout_rate: Dropout probability for regularization
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for neural network models. Install with: pip install torch")

        super().__init__()

        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.dropout_rate = dropout_rate

        # Build layers dynamically
        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, hidden_dim),
                nn.BatchNorm1d(hidden_dim),
                nn.ReLU(),
                nn.Dropout(dropout_rate)
            ])
            prev_dim = hidden_dim

        # Output layer
        layers.append(nn.Linear(prev_dim, 1))
        layers.append(nn.Sigmoid())

        self.network = nn.Sequential(*layers)

        # Initialize weights using Xavier initialization
        self._init_weights()

    def _init_weights(self):
        """Initialize weights using Xavier/Glorot initialization."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """
        Forward pass through the network.

        Args:
            x: Input tensor of shape (batch_size, input_dim)

        Returns:
            Output tensor of shape (batch_size, 1) with probability values
        """
        return self.network(x)


class CorruptionNeuralNetwork:
    """
    Neural Network model for corruption detection with training utilities.

    This class wraps the CorruptionMLP with:
    - Training loop with early stopping
    - Learning rate scheduling
    - Class weight handling for imbalanced data
    - Model save/load functionality
    - GPU support

    Usage:
        model = CorruptionNeuralNetwork()
        model.fit(X_train, y_train, X_val, y_val)
        predictions = model.predict(X_test)
        probabilities = model.predict_proba(X_test)
        model.save('model.pt')
        model.load('model.pt')
    """

    def __init__(
        self,
        input_dim: int = 113,
        hidden_dims: Tuple[int, ...] = (256, 128, 64),
        dropout_rate: float = 0.3,
        learning_rate: float = 0.001,
        batch_size: int = 64,
        max_epochs: int = 100,
        patience: int = 10,
        min_delta: float = 0.001,
        device: Optional[str] = None,
        random_state: int = 42
    ):
        """
        Initialize the neural network model.

        Args:
            input_dim: Number of input features
            hidden_dims: Tuple of hidden layer dimensions
            dropout_rate: Dropout probability
            learning_rate: Initial learning rate for Adam optimizer
            batch_size: Training batch size
            max_epochs: Maximum training epochs
            patience: Early stopping patience (epochs without improvement)
            min_delta: Minimum improvement threshold for early stopping
            device: 'cuda', 'cpu', or None (auto-detect)
            random_state: Random seed for reproducibility
        """
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required. Install with: pip install torch")

        self.input_dim = input_dim
        self.hidden_dims = hidden_dims
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.min_delta = min_delta
        self.random_state = random_state

        # Set device
        if device is None:
            self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        else:
            self.device = torch.device(device)

        logger.info(f"Using device: {self.device}")

        # Set random seeds
        torch.manual_seed(random_state)
        np.random.seed(random_state)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(random_state)

        # Model will be created on first fit
        self.model: Optional[CorruptionMLP] = None
        self.optimizer: Optional[optim.Adam] = None
        self.scheduler: Optional[optim.lr_scheduler.ReduceLROnPlateau] = None
        self.criterion: Optional[nn.BCELoss] = None

        # Training history
        self.history: Dict[str, List[float]] = {
            'train_loss': [],
            'val_loss': [],
            'train_acc': [],
            'val_acc': [],
            'lr': []
        }

        # Best model tracking
        self.best_val_loss = float('inf')
        self.best_model_state: Optional[Dict] = None
        self.epochs_without_improvement = 0

        self._is_fitted = False

    def _create_model(self) -> None:
        """Create and initialize the neural network model."""
        self.model = CorruptionMLP(
            input_dim=self.input_dim,
            hidden_dims=self.hidden_dims,
            dropout_rate=self.dropout_rate
        ).to(self.device)

        self.optimizer = optim.Adam(
            self.model.parameters(),
            lr=self.learning_rate,
            weight_decay=1e-5  # L2 regularization
        )

        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode='min',
            factor=0.5,
            patience=5,
            min_lr=1e-6
        )

        logger.info(f"Created model with architecture: {self.hidden_dims}")
        logger.info(f"Total parameters: {sum(p.numel() for p in self.model.parameters())}")

    def _calculate_class_weights(self, y: np.ndarray) -> 'torch.Tensor':
        """
        Calculate class weights for imbalanced data.

        Args:
            y: Target labels

        Returns:
            Tensor with class weight for the positive class
        """
        n_samples = len(y)
        n_positive = np.sum(y)
        n_negative = n_samples - n_positive

        if n_positive == 0 or n_negative == 0:
            return torch.tensor([1.0]).to(self.device)

        # Weight inversely proportional to class frequency
        pos_weight = n_negative / n_positive

        logger.info(f"Class distribution - Positive: {n_positive}, Negative: {n_negative}")
        logger.info(f"Positive class weight: {pos_weight:.4f}")

        return torch.tensor([pos_weight]).to(self.device)

    def _prepare_data(
        self,
        X: np.ndarray,
        y: Optional[np.ndarray] = None,
        shuffle: bool = True
    ) -> DataLoader:
        """
        Prepare data for training/inference.

        Args:
            X: Feature matrix
            y: Target labels (optional for inference)
            shuffle: Whether to shuffle the data

        Returns:
            DataLoader for the dataset
        """
        # Handle NaN and infinite values
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        X_tensor = torch.FloatTensor(X).to(self.device)

        if y is not None:
            y_tensor = torch.FloatTensor(y.reshape(-1, 1)).to(self.device)
            dataset = TensorDataset(X_tensor, y_tensor)
        else:
            dataset = TensorDataset(X_tensor)

        return DataLoader(
            dataset,
            batch_size=self.batch_size,
            shuffle=shuffle
        )

    def fit(
        self,
        X: np.ndarray,
        y: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        verbose: bool = True
    ) -> 'CorruptionNeuralNetwork':
        """
        Train the neural network.

        Args:
            X: Training features of shape (n_samples, n_features)
            y: Training labels of shape (n_samples,)
            X_val: Validation features (optional)
            y_val: Validation labels (optional)
            verbose: Whether to print training progress

        Returns:
            self for method chaining
        """
        logger.info(f"Training neural network on {len(X)} samples")

        # Auto-detect input dimension
        if X.shape[1] != self.input_dim:
            logger.warning(f"Adjusting input_dim from {self.input_dim} to {X.shape[1]}")
            self.input_dim = X.shape[1]

        # Create model
        self._create_model()

        # Calculate class weights
        pos_weight = self._calculate_class_weights(y)
        self.criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

        # Note: We use BCEWithLogitsLoss internally but the model outputs sigmoid
        # So we'll use regular BCE with the weight adjustment
        self.criterion = nn.BCELoss(reduction='none')

        # Prepare data loaders
        train_loader = self._prepare_data(X, y, shuffle=True)

        val_loader = None
        if X_val is not None and y_val is not None:
            val_loader = self._prepare_data(X_val, y_val, shuffle=False)

        # Reset history and best model tracking
        self.history = {key: [] for key in self.history}
        self.best_val_loss = float('inf')
        self.best_model_state = None
        self.epochs_without_improvement = 0

        # Training loop
        for epoch in range(self.max_epochs):
            # Training phase
            train_loss, train_acc = self._train_epoch(train_loader, y)
            self.history['train_loss'].append(train_loss)
            self.history['train_acc'].append(train_acc)

            # Validation phase
            if val_loader is not None:
                val_loss, val_acc = self._validate_epoch(val_loader, y_val)
                self.history['val_loss'].append(val_loss)
                self.history['val_acc'].append(val_acc)

                # Learning rate scheduling
                self.scheduler.step(val_loss)
            else:
                val_loss = train_loss
                val_acc = train_acc
                self.scheduler.step(train_loss)

            # Record learning rate
            current_lr = self.optimizer.param_groups[0]['lr']
            self.history['lr'].append(current_lr)

            # Logging
            if verbose and (epoch + 1) % 5 == 0:
                logger.info(
                    f"Epoch {epoch+1}/{self.max_epochs} - "
                    f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.4f}, "
                    f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.4f}, "
                    f"LR: {current_lr:.6f}"
                )

            # Early stopping check
            if val_loss < self.best_val_loss - self.min_delta:
                self.best_val_loss = val_loss
                self.best_model_state = {
                    key: value.cpu().clone() for key, value in self.model.state_dict().items()
                }
                self.epochs_without_improvement = 0
            else:
                self.epochs_without_improvement += 1

            if self.epochs_without_improvement >= self.patience:
                logger.info(f"Early stopping triggered at epoch {epoch+1}")
                break

        # Restore best model
        if self.best_model_state is not None:
            self.model.load_state_dict({
                key: value.to(self.device) for key, value in self.best_model_state.items()
            })
            logger.info(f"Restored best model with validation loss: {self.best_val_loss:.4f}")

        self._is_fitted = True
        logger.info("Training completed")

        return self

    def _train_epoch(
        self,
        train_loader: DataLoader,
        y_train: np.ndarray
    ) -> Tuple[float, float]:
        """
        Train for one epoch.

        Args:
            train_loader: Training data loader
            y_train: Full training labels for class weight calculation

        Returns:
            Tuple of (average loss, accuracy)
        """
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        # Calculate class weights for this batch
        n_positive = np.sum(y_train)
        n_negative = len(y_train) - n_positive
        pos_weight = n_negative / max(n_positive, 1)

        for batch_X, batch_y in train_loader:
            self.optimizer.zero_grad()

            outputs = self.model(batch_X)

            # Apply class weights
            weights = torch.where(
                batch_y == 1,
                torch.tensor(pos_weight).to(self.device),
                torch.tensor(1.0).to(self.device)
            )

            loss = (self.criterion(outputs, batch_y) * weights).mean()

            loss.backward()

            # Gradient clipping
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)

            self.optimizer.step()

            total_loss += loss.item() * batch_X.size(0)
            predictions = (outputs >= 0.5).float()
            correct += (predictions == batch_y).sum().item()
            total += batch_y.size(0)

        avg_loss = total_loss / total
        accuracy = correct / total

        return avg_loss, accuracy

    def _validate_epoch(
        self,
        val_loader: DataLoader,
        y_val: np.ndarray
    ) -> Tuple[float, float]:
        """
        Validate for one epoch.

        Args:
            val_loader: Validation data loader
            y_val: Full validation labels for class weight calculation

        Returns:
            Tuple of (average loss, accuracy)
        """
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        # Calculate class weights
        n_positive = np.sum(y_val)
        n_negative = len(y_val) - n_positive
        pos_weight = n_negative / max(n_positive, 1)

        with torch.no_grad():
            for batch_X, batch_y in val_loader:
                outputs = self.model(batch_X)

                # Apply class weights
                weights = torch.where(
                    batch_y == 1,
                    torch.tensor(pos_weight).to(self.device),
                    torch.tensor(1.0).to(self.device)
                )

                loss = (self.criterion(outputs, batch_y) * weights).mean()

                total_loss += loss.item() * batch_X.size(0)
                predictions = (outputs >= 0.5).float()
                correct += (predictions == batch_y).sum().item()
                total += batch_y.size(0)

        avg_loss = total_loss / total
        accuracy = correct / total

        return avg_loss, accuracy

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict binary class labels.

        Args:
            X: Features of shape (n_samples, n_features)

        Returns:
            Predicted labels of shape (n_samples,)
        """
        proba = self.predict_proba(X)
        return (proba >= 0.5).astype(np.int32)

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probability of corruption.

        Args:
            X: Features of shape (n_samples, n_features)

        Returns:
            Probabilities of shape (n_samples,)
        """
        if not self._is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before prediction")

        self.model.eval()

        # Handle NaN and infinite values
        X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)

        X_tensor = torch.FloatTensor(X).to(self.device)

        with torch.no_grad():
            outputs = self.model(X_tensor)

        return outputs.cpu().numpy().flatten()

    def save(self, path: Union[str, Path]) -> None:
        """
        Save model to disk.

        Args:
            path: Path to save the model
        """
        if not self._is_fitted or self.model is None:
            raise RuntimeError("Model must be fitted before saving")

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)

        save_dict = {
            'model_state_dict': self.model.state_dict(),
            'input_dim': self.input_dim,
            'hidden_dims': self.hidden_dims,
            'dropout_rate': self.dropout_rate,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'history': self.history,
            'best_val_loss': self.best_val_loss
        }

        torch.save(save_dict, path)
        logger.info(f"Model saved to {path}")

    def load(self, path: Union[str, Path]) -> 'CorruptionNeuralNetwork':
        """
        Load model from disk.

        Args:
            path: Path to load the model from

        Returns:
            self for method chaining
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Model file not found: {path}")

        save_dict = torch.load(path, map_location=self.device)

        self.input_dim = save_dict['input_dim']
        self.hidden_dims = save_dict['hidden_dims']
        self.dropout_rate = save_dict['dropout_rate']
        self.learning_rate = save_dict.get('learning_rate', self.learning_rate)
        self.batch_size = save_dict.get('batch_size', self.batch_size)
        self.history = save_dict.get('history', self.history)
        self.best_val_loss = save_dict.get('best_val_loss', float('inf'))

        # Recreate model architecture
        self.model = CorruptionMLP(
            input_dim=self.input_dim,
            hidden_dims=self.hidden_dims,
            dropout_rate=self.dropout_rate
        ).to(self.device)

        self.model.load_state_dict(save_dict['model_state_dict'])
        self._is_fitted = True

        logger.info(f"Model loaded from {path}")
        return self

    def get_params(self, deep: bool = True) -> Dict[str, Any]:
        """
        Get model parameters (sklearn-compatible).

        Args:
            deep: Whether to return nested parameters

        Returns:
            Dictionary of parameters
        """
        return {
            'input_dim': self.input_dim,
            'hidden_dims': self.hidden_dims,
            'dropout_rate': self.dropout_rate,
            'learning_rate': self.learning_rate,
            'batch_size': self.batch_size,
            'max_epochs': self.max_epochs,
            'patience': self.patience,
            'min_delta': self.min_delta,
            'random_state': self.random_state
        }

    def set_params(self, **params) -> 'CorruptionNeuralNetwork':
        """
        Set model parameters (sklearn-compatible).

        Args:
            **params: Parameter names and values

        Returns:
            self for method chaining
        """
        for key, value in params.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self


# Convenience function for creating model
def create_neural_network(
    input_dim: int = 113,
    hidden_dims: Tuple[int, ...] = (256, 128, 64),
    **kwargs
) -> CorruptionNeuralNetwork:
    """
    Create a CorruptionNeuralNetwork with sensible defaults.

    Args:
        input_dim: Number of input features
        hidden_dims: Tuple of hidden layer sizes
        **kwargs: Additional arguments passed to CorruptionNeuralNetwork

    Returns:
        Configured CorruptionNeuralNetwork instance
    """
    return CorruptionNeuralNetwork(
        input_dim=input_dim,
        hidden_dims=hidden_dims,
        **kwargs
    )
