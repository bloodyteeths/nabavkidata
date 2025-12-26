"""
Hybrid Anomaly Detector for Corruption Detection

This module implements a hybrid approach combining multiple unsupervised
anomaly detection methods to identify suspicious tenders that deviate
from normal patterns.

Methods:
1. Isolation Forest - High-dimensional outlier detection
2. Autoencoder (PyTorch) - Reconstruction error for anomalies
3. Local Outlier Factor - Density-based local anomalies
4. One-Class SVM - Boundary-based detection with RBF kernel

The ensemble combines scores through weighted voting and calibration
to produce probability scores.

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.ensemble import IsolationForest
from sklearn.neighbors import LocalOutlierFactor
from sklearn.svm import OneClassSVM
from sklearn.preprocessing import StandardScaler, MinMaxScaler
from sklearn.calibration import IsotonicRegression
from sklearn.model_selection import train_test_split
from typing import Dict, List, Optional, Tuple, Any, Union
import logging
import pickle
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
import warnings

warnings.filterwarnings('ignore', category=UserWarning)

logger = logging.getLogger(__name__)


@dataclass
class AnomalyScore:
    """
    Container for anomaly detection results.

    Attributes:
        tender_id: The tender identifier
        anomaly_score: Combined anomaly score (0-1, higher = more anomalous)
        is_anomaly: Binary classification based on threshold
        method_scores: Individual scores from each detection method
        feature_contributions: Which features contributed most to anomaly
        confidence: Confidence in the anomaly classification
        rank_percentile: Where this tender ranks among all tenders
    """
    tender_id: str
    anomaly_score: float
    is_anomaly: bool
    method_scores: Dict[str, float]
    feature_contributions: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0
    rank_percentile: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization"""
        return {
            'tender_id': self.tender_id,
            'anomaly_score': float(self.anomaly_score),
            'is_anomaly': self.is_anomaly,
            'method_scores': {k: float(v) for k, v in self.method_scores.items()},
            'feature_contributions': {k: float(v) for k, v in self.feature_contributions.items()},
            'confidence': float(self.confidence),
            'rank_percentile': float(self.rank_percentile)
        }


class TenderAutoencoder(nn.Module):
    """
    PyTorch Autoencoder for anomaly detection.

    Architecture:
        Encoder: input_dim -> 64 -> 32 -> 16 (latent)
        Decoder: 16 -> 32 -> 64 -> input_dim

    Uses reconstruction error as anomaly score.
    Normal tenders should reconstruct well; anomalies poorly.
    """

    def __init__(self, input_dim: int = 113, latent_dim: int = 16):
        """
        Initialize autoencoder.

        Args:
            input_dim: Number of input features
            latent_dim: Size of latent representation
        """
        super(TenderAutoencoder, self).__init__()

        self.input_dim = input_dim
        self.latent_dim = latent_dim

        # Encoder layers
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.BatchNorm1d(64),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.2),

            nn.Linear(64, 32),
            nn.BatchNorm1d(32),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.1),

            nn.Linear(32, latent_dim),
            nn.BatchNorm1d(latent_dim),
            nn.LeakyReLU(0.2)
        )

        # Decoder layers
        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 32),
            nn.BatchNorm1d(32),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.1),

            nn.Linear(32, 64),
            nn.BatchNorm1d(64),
            nn.LeakyReLU(0.2),
            nn.Dropout(0.2),

            nn.Linear(64, input_dim)
            # No activation - reconstruction can be any value
        )

        # Initialize weights
        self._init_weights()

    def _init_weights(self):
        """Initialize weights using Xavier initialization"""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

    def encode(self, x: torch.Tensor) -> torch.Tensor:
        """Encode input to latent representation"""
        return self.encoder(x)

    def decode(self, z: torch.Tensor) -> torch.Tensor:
        """Decode latent representation to reconstruction"""
        return self.decoder(z)

    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass: encode then decode.

        Args:
            x: Input tensor of shape (batch_size, input_dim)

        Returns:
            Tuple of (reconstruction, latent_representation)
        """
        z = self.encode(x)
        reconstruction = self.decode(z)
        return reconstruction, z

    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """
        Compute reconstruction error (MSE) for each sample.

        Args:
            x: Input tensor

        Returns:
            Per-sample reconstruction error
        """
        self.eval()
        with torch.no_grad():
            reconstruction, _ = self.forward(x)
            error = torch.mean((x - reconstruction) ** 2, dim=1)
        return error


class HybridAnomalyDetector:
    """
    Hybrid anomaly detector combining multiple methods.

    This detector uses an ensemble of unsupervised anomaly detection
    methods and combines their scores to identify anomalous tenders.

    Methods:
    1. Isolation Forest: Good for high-dimensional data, tree-based
    2. Autoencoder: Neural network learns normal patterns
    3. Local Outlier Factor: Density-based local anomalies
    4. One-Class SVM: Learns a boundary around normal data

    Usage:
        detector = HybridAnomalyDetector()
        detector.fit(X_normal)  # Train on normal data
        scores = detector.anomaly_score(X_test)
        predictions = detector.predict(X_test)
    """

    # Default feature count from feature_extractor.py
    DEFAULT_FEATURE_DIM = 113

    def __init__(
        self,
        contamination: float = 0.05,
        isolation_forest_params: Optional[Dict] = None,
        autoencoder_params: Optional[Dict] = None,
        lof_params: Optional[Dict] = None,
        ocsvm_params: Optional[Dict] = None,
        weights: Optional[Dict[str, float]] = None,
        threshold: float = 0.5,
        device: str = 'auto',
        random_state: int = 42
    ):
        """
        Initialize hybrid anomaly detector.

        Args:
            contamination: Expected proportion of outliers (0-0.5)
            isolation_forest_params: Parameters for Isolation Forest
            autoencoder_params: Parameters for Autoencoder
            lof_params: Parameters for Local Outlier Factor
            ocsvm_params: Parameters for One-Class SVM
            weights: Weights for combining methods (default: equal)
            threshold: Threshold for binary anomaly classification
            device: Device for PyTorch ('auto', 'cpu', 'cuda', 'mps')
            random_state: Random seed for reproducibility
        """
        self.contamination = contamination
        self.threshold = threshold
        self.random_state = random_state

        # Set device
        if device == 'auto':
            if torch.cuda.is_available():
                self.device = torch.device('cuda')
            elif torch.backends.mps.is_available():
                self.device = torch.device('mps')
            else:
                self.device = torch.device('cpu')
        else:
            self.device = torch.device(device)

        logger.info(f"Using device: {self.device}")

        # Method weights for ensemble
        self.weights = weights or {
            'isolation_forest': 0.25,
            'autoencoder': 0.30,
            'lof': 0.20,
            'ocsvm': 0.25
        }

        # Normalize weights
        total_weight = sum(self.weights.values())
        self.weights = {k: v / total_weight for k, v in self.weights.items()}

        # Initialize models with default or custom params
        if_params = isolation_forest_params or {}
        self.isolation_forest = IsolationForest(
            contamination=contamination,
            n_estimators=if_params.get('n_estimators', 200),
            max_samples=if_params.get('max_samples', 'auto'),
            max_features=if_params.get('max_features', 0.8),
            bootstrap=if_params.get('bootstrap', True),
            n_jobs=if_params.get('n_jobs', -1),
            random_state=random_state
        )

        lof_params_use = lof_params or {}
        self.lof = LocalOutlierFactor(
            n_neighbors=lof_params_use.get('n_neighbors', 20),
            algorithm=lof_params_use.get('algorithm', 'auto'),
            contamination=contamination,
            novelty=True,  # Enable predict method
            n_jobs=lof_params_use.get('n_jobs', -1)
        )

        ocsvm_params_use = ocsvm_params or {}
        self.ocsvm = OneClassSVM(
            kernel=ocsvm_params_use.get('kernel', 'rbf'),
            gamma=ocsvm_params_use.get('gamma', 'scale'),
            nu=min(contamination * 2, 0.5),  # nu must be in (0, 1]
            cache_size=ocsvm_params_use.get('cache_size', 500)
        )

        # Autoencoder params
        ae_params = autoencoder_params or {}
        self.ae_params = {
            'latent_dim': ae_params.get('latent_dim', 16),
            'epochs': ae_params.get('epochs', 100),
            'batch_size': ae_params.get('batch_size', 64),
            'learning_rate': ae_params.get('learning_rate', 0.001),
            'patience': ae_params.get('patience', 10),
            'validation_split': ae_params.get('validation_split', 0.1)
        }

        self.autoencoder: Optional[TenderAutoencoder] = None

        # Scalers for different components
        self.feature_scaler = StandardScaler()
        self.ae_scaler = MinMaxScaler(feature_range=(-1, 1))

        # Score calibrators
        self.score_calibrators: Dict[str, IsotonicRegression] = {}

        # Fitted state
        self.is_fitted = False
        self.feature_dim: Optional[int] = None
        self.feature_names: Optional[List[str]] = None

        # Training statistics
        self.training_stats: Dict[str, Any] = {}

        logger.info(f"HybridAnomalyDetector initialized with contamination={contamination}")

    def fit(
        self,
        X: np.ndarray,
        feature_names: Optional[List[str]] = None,
        y_known: Optional[np.ndarray] = None,
        verbose: bool = True
    ) -> 'HybridAnomalyDetector':
        """
        Fit the hybrid anomaly detector on normal data.

        Args:
            X: Training data (n_samples, n_features), assumed mostly normal
            feature_names: Names of features (for interpretability)
            y_known: Optional known labels for threshold calibration
                    (1 = normal, -1 = anomaly)
            verbose: Whether to print training progress

        Returns:
            self (fitted detector)
        """
        logger.info(f"Fitting HybridAnomalyDetector on {X.shape[0]} samples with {X.shape[1]} features")

        # Store dimensions
        self.feature_dim = X.shape[1]
        self.feature_names = feature_names

        # Handle NaN/Inf
        X = self._clean_data(X)

        # Fit scalers
        X_scaled = self.feature_scaler.fit_transform(X)
        X_ae_scaled = self.ae_scaler.fit_transform(X)

        # Fit each model
        start_time = datetime.now()

        # 1. Isolation Forest
        if verbose:
            logger.info("Fitting Isolation Forest...")
        self.isolation_forest.fit(X_scaled)

        # 2. Local Outlier Factor
        if verbose:
            logger.info("Fitting Local Outlier Factor...")
        self.lof.fit(X_scaled)

        # 3. One-Class SVM
        if verbose:
            logger.info("Fitting One-Class SVM...")
        # Sample if too large (OCSVM is O(n^2))
        if X_scaled.shape[0] > 10000:
            np.random.seed(self.random_state)
            sample_idx = np.random.choice(X_scaled.shape[0], 10000, replace=False)
            self.ocsvm.fit(X_scaled[sample_idx])
        else:
            self.ocsvm.fit(X_scaled)

        # 4. Autoencoder
        if verbose:
            logger.info("Training Autoencoder...")
        self._train_autoencoder(X_ae_scaled, verbose=verbose)

        # Compute raw scores for calibration
        if verbose:
            logger.info("Computing raw scores for calibration...")

        raw_scores = self._compute_raw_scores(X)

        # Calibrate scores to [0, 1]
        self._calibrate_scores(raw_scores, y_known)

        # Record training statistics
        self.training_stats = {
            'n_samples': X.shape[0],
            'n_features': X.shape[1],
            'contamination': self.contamination,
            'training_time': (datetime.now() - start_time).total_seconds(),
            'timestamp': datetime.now().isoformat()
        }

        self.is_fitted = True

        if verbose:
            logger.info(f"Training complete in {self.training_stats['training_time']:.2f}s")

        return self

    def _clean_data(self, X: np.ndarray) -> np.ndarray:
        """Clean data by handling NaN and Inf values"""
        X = np.array(X, dtype=np.float32)

        # Replace inf with large finite values
        X = np.clip(X, -1e10, 1e10)

        # Replace NaN with column means
        nan_mask = np.isnan(X)
        if nan_mask.any():
            col_means = np.nanmean(X, axis=0)
            col_means = np.where(np.isnan(col_means), 0, col_means)

            for j in range(X.shape[1]):
                X[nan_mask[:, j], j] = col_means[j]

        return X

    def _train_autoencoder(self, X: np.ndarray, verbose: bool = True):
        """Train the autoencoder neural network"""
        # Initialize model
        self.autoencoder = TenderAutoencoder(
            input_dim=X.shape[1],
            latent_dim=self.ae_params['latent_dim']
        ).to(self.device)

        # Split for validation
        X_train, X_val = train_test_split(
            X,
            test_size=self.ae_params['validation_split'],
            random_state=self.random_state
        )

        # Create data loaders
        train_tensor = torch.FloatTensor(X_train).to(self.device)
        val_tensor = torch.FloatTensor(X_val).to(self.device)

        train_dataset = TensorDataset(train_tensor, train_tensor)
        train_loader = DataLoader(
            train_dataset,
            batch_size=self.ae_params['batch_size'],
            shuffle=True
        )

        # Loss and optimizer
        criterion = nn.MSELoss()
        optimizer = optim.Adam(
            self.autoencoder.parameters(),
            lr=self.ae_params['learning_rate'],
            weight_decay=1e-5
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )

        # Training loop
        best_val_loss = float('inf')
        patience_counter = 0

        for epoch in range(self.ae_params['epochs']):
            self.autoencoder.train()
            train_loss = 0.0

            for batch_x, _ in train_loader:
                optimizer.zero_grad()
                reconstruction, _ = self.autoencoder(batch_x)
                loss = criterion(reconstruction, batch_x)
                loss.backward()

                # Gradient clipping
                torch.nn.utils.clip_grad_norm_(self.autoencoder.parameters(), 1.0)

                optimizer.step()
                train_loss += loss.item()

            train_loss /= len(train_loader)

            # Validation
            self.autoencoder.eval()
            with torch.no_grad():
                val_reconstruction, _ = self.autoencoder(val_tensor)
                val_loss = criterion(val_reconstruction, val_tensor).item()

            scheduler.step(val_loss)

            # Early stopping
            if val_loss < best_val_loss:
                best_val_loss = val_loss
                patience_counter = 0
                # Save best model
                self.best_ae_state = self.autoencoder.state_dict().copy()
            else:
                patience_counter += 1

            if verbose and (epoch + 1) % 10 == 0:
                logger.info(f"Epoch {epoch+1}: train_loss={train_loss:.6f}, val_loss={val_loss:.6f}")

            if patience_counter >= self.ae_params['patience']:
                if verbose:
                    logger.info(f"Early stopping at epoch {epoch+1}")
                break

        # Load best model
        if hasattr(self, 'best_ae_state'):
            self.autoencoder.load_state_dict(self.best_ae_state)

        self.autoencoder.eval()

        # Store reconstruction error threshold
        self.autoencoder.eval()
        with torch.no_grad():
            train_tensor = torch.FloatTensor(X).to(self.device)
            errors = self.autoencoder.reconstruction_error(train_tensor).cpu().numpy()
            self.ae_error_mean = float(np.mean(errors))
            self.ae_error_std = float(np.std(errors))
            self.ae_error_threshold = float(np.percentile(errors, 100 * (1 - self.contamination)))

    def _compute_raw_scores(self, X: np.ndarray) -> Dict[str, np.ndarray]:
        """Compute raw anomaly scores from each method"""
        X_clean = self._clean_data(X)
        X_scaled = self.feature_scaler.transform(X_clean)
        X_ae_scaled = self.ae_scaler.transform(X_clean)

        scores = {}

        # Isolation Forest: decision_function returns negative for anomalies
        # Transform to [0, 1] where higher = more anomalous
        if_scores = -self.isolation_forest.decision_function(X_scaled)
        scores['isolation_forest'] = if_scores

        # LOF: decision_function returns negative for anomalies
        lof_scores = -self.lof.decision_function(X_scaled)
        scores['lof'] = lof_scores

        # One-Class SVM: decision_function returns negative for anomalies
        ocsvm_scores = -self.ocsvm.decision_function(X_scaled)
        scores['ocsvm'] = ocsvm_scores

        # Autoencoder: reconstruction error
        self.autoencoder.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_ae_scaled).to(self.device)
            ae_scores = self.autoencoder.reconstruction_error(X_tensor).cpu().numpy()
        scores['autoencoder'] = ae_scores

        return scores

    def _calibrate_scores(
        self,
        raw_scores: Dict[str, np.ndarray],
        y_known: Optional[np.ndarray] = None
    ):
        """Calibrate raw scores to probability-like [0, 1] range"""
        for method, scores in raw_scores.items():
            # Use min-max scaling with percentile clipping
            p_low, p_high = np.percentile(scores, [2, 98])
            scores_clipped = np.clip(scores, p_low, p_high)
            scores_normalized = (scores_clipped - p_low) / (p_high - p_low + 1e-10)

            # If we have known labels, use isotonic regression
            if y_known is not None and len(y_known) > 0:
                # Convert labels: -1 (anomaly) -> 1, 1 (normal) -> 0
                y_binary = (y_known == -1).astype(float)
                calibrator = IsotonicRegression(y_min=0, y_max=1, out_of_bounds='clip')
                calibrator.fit(scores_normalized, y_binary)
                self.score_calibrators[method] = calibrator
            else:
                # Store percentiles for transformation
                self.score_calibrators[method] = {
                    'p_low': float(p_low),
                    'p_high': float(p_high)
                }

    def _normalize_score(self, method: str, raw_score: np.ndarray) -> np.ndarray:
        """Normalize a raw score to [0, 1] using stored calibration"""
        calibrator = self.score_calibrators.get(method)

        if calibrator is None:
            # Fallback: simple normalization
            return (raw_score - raw_score.min()) / (raw_score.max() - raw_score.min() + 1e-10)

        if isinstance(calibrator, IsotonicRegression):
            # Use isotonic regression
            return calibrator.predict(raw_score)
        else:
            # Use percentile-based normalization
            p_low = calibrator['p_low']
            p_high = calibrator['p_high']
            clipped = np.clip(raw_score, p_low, p_high)
            return (clipped - p_low) / (p_high - p_low + 1e-10)

    def anomaly_score(
        self,
        X: np.ndarray,
        return_components: bool = False
    ) -> Union[np.ndarray, Tuple[np.ndarray, Dict[str, np.ndarray]]]:
        """
        Compute anomaly scores for samples.

        Args:
            X: Input data (n_samples, n_features)
            return_components: Whether to return individual method scores

        Returns:
            Combined anomaly scores (n_samples,)
            If return_components=True, also returns dict of method scores
        """
        if not self.is_fitted:
            raise RuntimeError("Detector not fitted. Call fit() first.")

        # Get raw scores
        raw_scores = self._compute_raw_scores(X)

        # Normalize each score
        normalized_scores = {}
        for method, raw in raw_scores.items():
            normalized_scores[method] = self._normalize_score(method, raw)

        # Combine with weights
        combined = np.zeros(X.shape[0])
        for method, weight in self.weights.items():
            combined += weight * normalized_scores[method]

        # Clip to [0, 1]
        combined = np.clip(combined, 0, 1)

        if return_components:
            return combined, normalized_scores
        return combined

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict whether samples are anomalous.

        Args:
            X: Input data (n_samples, n_features)

        Returns:
            Predictions: 1 for normal, -1 for anomaly
        """
        scores = self.anomaly_score(X)
        predictions = np.where(scores >= self.threshold, -1, 1)
        return predictions

    def score_tenders(
        self,
        X: np.ndarray,
        tender_ids: List[str]
    ) -> List[AnomalyScore]:
        """
        Score tenders and return detailed results.

        Args:
            X: Feature matrix (n_samples, n_features)
            tender_ids: List of tender IDs

        Returns:
            List of AnomalyScore objects
        """
        if len(tender_ids) != X.shape[0]:
            raise ValueError("Number of tender_ids must match number of samples")

        # Get combined and component scores
        combined_scores, component_scores = self.anomaly_score(X, return_components=True)

        # Compute feature contributions for each sample
        feature_contributions = self._compute_feature_contributions(X)

        # Calculate rank percentiles
        rank_order = np.argsort(-combined_scores)
        rank_percentiles = np.zeros(len(combined_scores))
        for i, idx in enumerate(rank_order):
            rank_percentiles[idx] = (i + 1) / len(combined_scores) * 100

        # Build results
        results = []
        for i, tender_id in enumerate(tender_ids):
            result = AnomalyScore(
                tender_id=tender_id,
                anomaly_score=float(combined_scores[i]),
                is_anomaly=combined_scores[i] >= self.threshold,
                method_scores={
                    method: float(scores[i])
                    for method, scores in component_scores.items()
                },
                feature_contributions=feature_contributions[i],
                confidence=self._compute_confidence(combined_scores[i], component_scores, i),
                rank_percentile=float(rank_percentiles[i])
            )
            results.append(result)

        return results

    def _compute_feature_contributions(
        self,
        X: np.ndarray
    ) -> List[Dict[str, float]]:
        """
        Compute feature contributions to anomaly score.

        Uses Isolation Forest path lengths and Autoencoder reconstruction
        errors to estimate feature importance for each sample.
        """
        X_clean = self._clean_data(X)
        X_scaled = self.feature_scaler.transform(X_clean)
        X_ae_scaled = self.ae_scaler.transform(X_clean)

        contributions = []

        # Get feature-level reconstruction errors from autoencoder
        self.autoencoder.eval()
        with torch.no_grad():
            X_tensor = torch.FloatTensor(X_ae_scaled).to(self.device)
            reconstruction, _ = self.autoencoder(X_tensor)
            feature_errors = (X_tensor - reconstruction).abs().cpu().numpy()

        # Normalize feature errors
        feature_errors_norm = feature_errors / (feature_errors.sum(axis=1, keepdims=True) + 1e-10)

        # Combine with deviation from training mean
        training_mean = self.feature_scaler.mean_
        training_std = self.feature_scaler.scale_

        for i in range(X.shape[0]):
            sample_contrib = {}

            # Z-scores
            z_scores = np.abs((X_clean[i] - training_mean) / (training_std + 1e-10))

            # Combine autoencoder errors with z-scores
            combined_contrib = 0.5 * feature_errors_norm[i] + 0.5 * (z_scores / (z_scores.sum() + 1e-10))

            # Get top contributing features
            if self.feature_names:
                for j, name in enumerate(self.feature_names):
                    sample_contrib[name] = float(combined_contrib[j])
            else:
                for j in range(len(combined_contrib)):
                    sample_contrib[f'feature_{j}'] = float(combined_contrib[j])

            # Keep only top 20 contributors
            sorted_contrib = sorted(sample_contrib.items(), key=lambda x: -x[1])[:20]
            contributions.append(dict(sorted_contrib))

        return contributions

    def _compute_confidence(
        self,
        combined_score: float,
        component_scores: Dict[str, np.ndarray],
        idx: int
    ) -> float:
        """
        Compute confidence in the anomaly classification.

        Higher confidence when:
        - All methods agree
        - Score is far from threshold
        """
        # Method agreement: low variance = high agreement
        method_values = [scores[idx] for scores in component_scores.values()]
        variance = np.var(method_values)
        agreement = 1 - min(variance, 1)  # Higher agreement = lower variance

        # Distance from threshold
        distance = abs(combined_score - self.threshold)
        certainty = min(distance * 2, 1)  # Scale and clip

        # Combined confidence
        confidence = 0.6 * agreement + 0.4 * certainty
        return float(confidence)

    def get_isolation_forest_importances(self) -> Dict[str, float]:
        """
        Get feature importances from Isolation Forest.

        Uses average path length as proxy for importance.
        Features that lead to faster isolation are more important.
        """
        if not self.is_fitted or self.feature_names is None:
            return {}

        # Use feature_importances_ if available (sklearn >= 1.0)
        if hasattr(self.isolation_forest, 'feature_importances_'):
            importances = self.isolation_forest.feature_importances_
        else:
            # Estimate from estimators
            n_features = len(self.feature_names)
            importances = np.zeros(n_features)

            for tree in self.isolation_forest.estimators_:
                # Count feature usage in tree
                feature_counts = np.bincount(
                    tree.tree_.feature[tree.tree_.feature >= 0],
                    minlength=n_features
                )
                importances += feature_counts

            # Normalize
            importances = importances / (importances.sum() + 1e-10)

        return {name: float(imp) for name, imp in zip(self.feature_names, importances)}

    def optimize_threshold(
        self,
        X: np.ndarray,
        y_true: np.ndarray,
        metric: str = 'f1'
    ) -> float:
        """
        Optimize detection threshold using known labels.

        Args:
            X: Feature matrix
            y_true: True labels (1 for normal, -1 for anomaly)
            metric: Optimization metric ('f1', 'precision', 'recall')

        Returns:
            Optimal threshold
        """
        from sklearn.metrics import f1_score, precision_score, recall_score

        scores = self.anomaly_score(X)

        best_threshold = self.threshold
        best_metric = 0

        for threshold in np.linspace(0.1, 0.9, 81):
            predictions = np.where(scores >= threshold, -1, 1)

            if metric == 'f1':
                current = f1_score(y_true, predictions, pos_label=-1)
            elif metric == 'precision':
                current = precision_score(y_true, predictions, pos_label=-1)
            else:  # recall
                current = recall_score(y_true, predictions, pos_label=-1)

            if current > best_metric:
                best_metric = current
                best_threshold = threshold

        self.threshold = best_threshold
        logger.info(f"Optimized threshold: {best_threshold:.3f} ({metric}={best_metric:.3f})")

        return best_threshold

    def save(self, path: str):
        """
        Save detector to disk.

        Args:
            path: Directory path for saving
        """
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save sklearn models
        with open(path / 'isolation_forest.pkl', 'wb') as f:
            pickle.dump(self.isolation_forest, f)

        with open(path / 'lof.pkl', 'wb') as f:
            pickle.dump(self.lof, f)

        with open(path / 'ocsvm.pkl', 'wb') as f:
            pickle.dump(self.ocsvm, f)

        # Save autoencoder
        torch.save({
            'state_dict': self.autoencoder.state_dict(),
            'input_dim': self.autoencoder.input_dim,
            'latent_dim': self.autoencoder.latent_dim,
            'ae_error_mean': self.ae_error_mean,
            'ae_error_std': self.ae_error_std,
            'ae_error_threshold': self.ae_error_threshold
        }, path / 'autoencoder.pt')

        # Save scalers
        with open(path / 'feature_scaler.pkl', 'wb') as f:
            pickle.dump(self.feature_scaler, f)

        with open(path / 'ae_scaler.pkl', 'wb') as f:
            pickle.dump(self.ae_scaler, f)

        # Save calibrators and config
        config = {
            'contamination': self.contamination,
            'threshold': self.threshold,
            'weights': self.weights,
            'feature_dim': self.feature_dim,
            'feature_names': self.feature_names,
            'training_stats': self.training_stats,
            'ae_params': self.ae_params,
            'score_calibrators': {}
        }

        # Convert calibrators to serializable format
        for method, calibrator in self.score_calibrators.items():
            if isinstance(calibrator, dict):
                config['score_calibrators'][method] = calibrator
            else:
                # Save isotonic regression separately
                with open(path / f'calibrator_{method}.pkl', 'wb') as f:
                    pickle.dump(calibrator, f)
                config['score_calibrators'][method] = 'file'

        with open(path / 'config.json', 'w') as f:
            json.dump(config, f, indent=2)

        logger.info(f"Model saved to {path}")

    @classmethod
    def load(cls, path: str, device: str = 'auto') -> 'HybridAnomalyDetector':
        """
        Load detector from disk.

        Args:
            path: Directory path to load from
            device: Device for PyTorch

        Returns:
            Loaded HybridAnomalyDetector
        """
        path = Path(path)

        # Load config
        with open(path / 'config.json', 'r') as f:
            config = json.load(f)

        # Create instance
        detector = cls(
            contamination=config['contamination'],
            threshold=config['threshold'],
            weights=config['weights'],
            device=device
        )

        detector.feature_dim = config['feature_dim']
        detector.feature_names = config['feature_names']
        detector.training_stats = config['training_stats']
        detector.ae_params = config['ae_params']

        # Load sklearn models
        with open(path / 'isolation_forest.pkl', 'rb') as f:
            detector.isolation_forest = pickle.load(f)

        with open(path / 'lof.pkl', 'rb') as f:
            detector.lof = pickle.load(f)

        with open(path / 'ocsvm.pkl', 'rb') as f:
            detector.ocsvm = pickle.load(f)

        # Load scalers
        with open(path / 'feature_scaler.pkl', 'rb') as f:
            detector.feature_scaler = pickle.load(f)

        with open(path / 'ae_scaler.pkl', 'rb') as f:
            detector.ae_scaler = pickle.load(f)

        # Load autoencoder
        ae_data = torch.load(path / 'autoencoder.pt', map_location=detector.device)
        detector.autoencoder = TenderAutoencoder(
            input_dim=ae_data['input_dim'],
            latent_dim=ae_data['latent_dim']
        ).to(detector.device)
        detector.autoencoder.load_state_dict(ae_data['state_dict'])
        detector.autoencoder.eval()
        detector.ae_error_mean = ae_data['ae_error_mean']
        detector.ae_error_std = ae_data['ae_error_std']
        detector.ae_error_threshold = ae_data['ae_error_threshold']

        # Load calibrators
        for method, calibrator in config['score_calibrators'].items():
            if calibrator == 'file':
                with open(path / f'calibrator_{method}.pkl', 'rb') as f:
                    detector.score_calibrators[method] = pickle.load(f)
            else:
                detector.score_calibrators[method] = calibrator

        detector.is_fitted = True

        logger.info(f"Model loaded from {path}")
        return detector


# Convenience function for quick anomaly detection
async def detect_anomalies(
    pool,
    tender_ids: List[str],
    model_path: Optional[str] = None
) -> List[AnomalyScore]:
    """
    Convenience function to detect anomalies in tenders.

    Args:
        pool: AsyncPG connection pool
        tender_ids: List of tender IDs to analyze
        model_path: Path to saved model (optional, will use default)

    Returns:
        List of AnomalyScore objects
    """
    from ai.corruption.features.feature_extractor import FeatureExtractor

    # Extract features
    extractor = FeatureExtractor(pool)
    feature_vectors = await extractor.extract_features_batch(tender_ids)

    if not feature_vectors:
        return []

    # Build feature matrix
    X = np.array([fv.feature_array for fv in feature_vectors])
    ids = [fv.tender_id for fv in feature_vectors]

    # Load or create detector
    if model_path and Path(model_path).exists():
        detector = HybridAnomalyDetector.load(model_path)
    else:
        # Use default model or raise error
        raise ValueError("Model not found. Train a model first using HybridAnomalyDetector.fit()")

    # Score tenders
    return detector.score_tenders(X, ids)
