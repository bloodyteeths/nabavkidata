"""
Conformal Prediction for Corruption Risk Score Calibration

Provides distribution-free prediction intervals with finite-sample
coverage guarantees. Implements split conformal prediction and
adaptive conformal inference.

Key guarantee: If we claim "90% coverage", then at least 90% of
truly corrupt tenders will fall within our prediction sets.

Theory:
    Split conformal prediction works by:
    1. Splitting data into training and calibration sets
    2. Computing nonconformity scores on the calibration set
    3. Taking the (1-alpha)(1 + 1/n) quantile of these scores
    4. Using this quantile to construct prediction sets for new data

    This gives marginal coverage P(Y in C(X)) >= 1-alpha for any
    distribution, with no assumptions on the model or data.

References:
    - Vovk, Gammerman, Shafer (2005) "Algorithmic Learning in a Random World"
    - Angelopoulos & Bates (2021) "A Gentle Introduction to Conformal Prediction"

Author: nabavkidata.com
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import NearestNeighbors

logger = logging.getLogger(__name__)


class ConformalPredictor:
    """
    Split Conformal Predictor for corruption risk scores.

    Converts raw model outputs (0-1 probabilities) into calibrated
    predictions with coverage guarantees. Also provides Platt-scaled
    calibrated probabilities.

    Usage:
        cp = ConformalPredictor(alpha=0.10)
        cp.fit(y_pred_proba_cal, y_true_cal)
        result = cp.predict_set(0.75)
        # result['calibrated_probability'] is the Platt-scaled probability
        # result['prediction_set'] is [lower, upper] with 90% coverage guarantee
    """

    def __init__(self, alpha: float = 0.10):
        """
        Args:
            alpha: Miscoverage rate. 0.10 means 90% coverage guarantee.
                   Must be in (0, 1).
        """
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")

        self.alpha = alpha
        self.calibration_scores: Optional[np.ndarray] = None
        self.quantile: Optional[float] = None
        self._fitted = False

        # Platt scaling parameters (logistic regression)
        self._platt_model: Optional[LogisticRegression] = None
        self._platt_a: Optional[float] = None  # sigmoid slope
        self._platt_b: Optional[float] = None  # sigmoid intercept

        # Calibration set metadata
        self._calibration_set_size: int = 0
        self._calibration_y_pred: Optional[np.ndarray] = None
        self._calibration_y_true: Optional[np.ndarray] = None

    def fit(self, y_pred_proba: np.ndarray, y_true: np.ndarray):
        """
        Fit conformal predictor on calibration set.

        Computes nonconformity scores = |y_true - y_pred| for each
        calibration point, then stores the (1-alpha)(1 + 1/n) quantile.
        Also fits Platt scaling (logistic regression) for probability
        calibration.

        Args:
            y_pred_proba: Model predicted probabilities on calibration set.
                          Shape (n_samples,), values in [0, 1].
            y_true: True binary labels on calibration set.
                    Shape (n_samples,), values in {0, 1}.
        """
        y_pred_proba = np.asarray(y_pred_proba, dtype=np.float64)
        y_true = np.asarray(y_true, dtype=np.float64)

        if len(y_pred_proba) != len(y_true):
            raise ValueError(
                f"Length mismatch: y_pred_proba ({len(y_pred_proba)}) "
                f"vs y_true ({len(y_true)})"
            )

        if len(y_pred_proba) < 10:
            raise ValueError(
                f"Calibration set too small ({len(y_pred_proba)} samples). "
                f"Need at least 10 for meaningful calibration."
            )

        n = len(y_pred_proba)
        self._calibration_set_size = n
        self._calibration_y_pred = y_pred_proba.copy()
        self._calibration_y_true = y_true.copy()

        # Step 1: Compute nonconformity scores
        # Using absolute residual: |y_true - y_pred|
        self.calibration_scores = np.abs(y_true - y_pred_proba)

        # Step 2: Compute the conformal quantile
        # For finite-sample coverage, use ceil((1-alpha)(n+1))/n quantile
        # This is equivalent to np.quantile with the right level
        quantile_level = min(
            np.ceil((1 - self.alpha) * (n + 1)) / n,
            1.0
        )
        self.quantile = float(np.quantile(self.calibration_scores, quantile_level))

        logger.info(
            f"Conformal quantile at {quantile_level:.4f} level: {self.quantile:.4f} "
            f"(alpha={self.alpha}, n={n})"
        )

        # Step 3: Fit Platt scaling (logistic regression on predicted probabilities)
        self._fit_platt_scaling(y_pred_proba, y_true)

        self._fitted = True
        logger.info(
            f"ConformalPredictor fitted: alpha={self.alpha}, "
            f"quantile={self.quantile:.4f}, n_cal={n}, "
            f"platt_a={self._platt_a:.4f}, platt_b={self._platt_b:.4f}"
        )

    def _fit_platt_scaling(self, y_pred_proba: np.ndarray, y_true: np.ndarray):
        """
        Fit Platt scaling via logistic regression.

        Maps raw model outputs through a sigmoid: P(y=1|f) = 1/(1+exp(a*f+b))
        where f is the raw model output.

        Uses sklearn LogisticRegression which fits: P(y=1|x) = sigmoid(w*x + b)
        We reshape predictions to be a single feature.
        """
        # Reshape predictions as single feature for logistic regression
        X_platt = y_pred_proba.reshape(-1, 1)

        self._platt_model = LogisticRegression(
            solver='lbfgs',
            max_iter=1000,
            C=1e10,  # Very weak regularization (effectively unregularized)
        )
        self._platt_model.fit(X_platt, y_true)

        # Extract sigmoid parameters: P = sigmoid(a*f + b)
        self._platt_a = float(self._platt_model.coef_[0, 0])
        self._platt_b = float(self._platt_model.intercept_[0])

        logger.info(
            f"Platt scaling fitted: a={self._platt_a:.4f}, b={self._platt_b:.4f}"
        )

    def predict_set(self, y_pred_proba: float) -> dict:
        """
        Convert a point prediction to a prediction set with coverage guarantee.

        The prediction set is [y_pred - q, y_pred + q] where q is the
        conformal quantile. This set has guaranteed (1-alpha) coverage.

        Args:
            y_pred_proba: Raw model predicted probability for a single sample.

        Returns:
            dict with keys:
                prediction: Raw model output
                prediction_set: [lower, upper] bounds with coverage guarantee
                set_width: Width of the prediction set
                calibrated_probability: Platt-scaled probability
                coverage_level: Target coverage level (1 - alpha)
        """
        if not self._fitted:
            raise RuntimeError("ConformalPredictor not fitted. Call fit() first.")

        y_pred_proba = float(y_pred_proba)

        # Conformal prediction set: [pred - quantile, pred + quantile]
        # Clipped to [0, 1] since we are predicting probabilities
        lower = max(0.0, y_pred_proba - self.quantile)
        upper = min(1.0, y_pred_proba + self.quantile)

        # Calibrated probability via Platt scaling
        calibrated_prob = self.calibrate_score(y_pred_proba)

        return {
            'prediction': y_pred_proba,
            'prediction_set': [round(lower, 6), round(upper, 6)],
            'set_width': round(upper - lower, 6),
            'calibrated_probability': round(calibrated_prob, 6),
            'coverage_level': round(1 - self.alpha, 4),
        }

    def calibrate_score(self, raw_score: float) -> float:
        """
        Platt scaling: convert raw model output to calibrated probability.

        Uses the logistic regression fitted on the calibration set.
        A calibrated probability of 0.7 means "70% of tenders with
        this score are actually corrupt" (in the calibration set sense).

        Args:
            raw_score: Raw model output in [0, 1].

        Returns:
            Calibrated probability in [0, 1].
        """
        if self._platt_model is None:
            raise RuntimeError("Platt scaling not fitted. Call fit() first.")

        X = np.array([[raw_score]])
        calibrated = self._platt_model.predict_proba(X)[0, 1]
        return float(calibrated)

    def get_parameters(self) -> dict:
        """
        Get fitted parameters for storage in database.

        Returns:
            dict with all parameters needed to reconstruct the predictor.
        """
        if not self._fitted:
            raise RuntimeError("ConformalPredictor not fitted.")

        return {
            'alpha': self.alpha,
            'quantile_threshold': self.quantile,
            'platt_a': self._platt_a,
            'platt_b': self._platt_b,
            'calibration_set_size': self._calibration_set_size,
            'coverage_level': 1 - self.alpha,
        }

    @classmethod
    def from_parameters(cls, params: dict) -> 'ConformalPredictor':
        """
        Reconstruct a ConformalPredictor from stored parameters.

        This allows loading from database without needing the calibration data.

        Args:
            params: dict with keys: alpha, quantile_threshold, platt_a, platt_b

        Returns:
            Reconstructed ConformalPredictor (predict_set works, but
            calibrate_score requires a full LogisticRegression model,
            so we use the sigmoid formula directly).
        """
        cp = cls(alpha=params['alpha'])
        cp.quantile = params['quantile_threshold']
        cp._platt_a = params['platt_a']
        cp._platt_b = params['platt_b']
        cp._calibration_set_size = params.get('calibration_set_size', 0)
        cp._fitted = True

        # Create a minimal Platt model that works for prediction
        # We manually construct the logistic regression with known params
        cp._platt_model = LogisticRegression()
        cp._platt_model.classes_ = np.array([0, 1])
        cp._platt_model.coef_ = np.array([[params['platt_a']]])
        cp._platt_model.intercept_ = np.array([params['platt_b']])

        return cp


class AdaptiveConformalPredictor(ConformalPredictor):
    """
    Adaptive Conformal Inference (ACI) that adjusts prediction intervals
    based on local data density.

    Tenders in sparse feature regions get wider intervals because there
    is more uncertainty. Dense regions get tighter intervals.

    This uses k-nearest neighbors in the calibration feature space to
    estimate local nonconformity score distributions.

    Usage:
        acp = AdaptiveConformalPredictor(alpha=0.10, k_neighbors=30)
        acp.fit(y_pred_cal, y_true_cal)  # basic conformal first
        acp.fit_adaptive(X_cal, y_pred_cal, y_true_cal)
        result = acp.predict_adaptive(x_new, y_pred_new)
    """

    def __init__(self, alpha: float = 0.10, k_neighbors: int = 30):
        """
        Args:
            alpha: Miscoverage rate.
            k_neighbors: Number of neighbors for local calibration.
                         Larger k = smoother but less adaptive.
        """
        super().__init__(alpha=alpha)
        self.k_neighbors = k_neighbors
        self._knn: Optional[NearestNeighbors] = None
        self._X_cal: Optional[np.ndarray] = None
        self._local_scores: Optional[np.ndarray] = None
        self._adaptive_fitted = False

    def fit_adaptive(
        self,
        X_cal: np.ndarray,
        y_pred_cal: np.ndarray,
        y_true_cal: np.ndarray,
    ):
        """
        Fit adaptive conformal predictor using k-nearest neighbors
        to estimate local nonconformity score distribution.

        Args:
            X_cal: Feature matrix for calibration samples. Shape (n, d).
            y_pred_cal: Model predictions on calibration set. Shape (n,).
            y_true_cal: True labels for calibration set. Shape (n,).
        """
        X_cal = np.asarray(X_cal, dtype=np.float64)
        y_pred_cal = np.asarray(y_pred_cal, dtype=np.float64)
        y_true_cal = np.asarray(y_true_cal, dtype=np.float64)

        n = len(X_cal)
        if n < self.k_neighbors:
            logger.warning(
                f"Calibration set ({n}) smaller than k_neighbors ({self.k_neighbors}). "
                f"Reducing k_neighbors to {n - 1}."
            )
            self.k_neighbors = max(1, n - 1)

        # Fit base conformal predictor first (for fallback)
        if not self._fitted:
            self.fit(y_pred_cal, y_true_cal)

        # Store calibration data
        self._X_cal = X_cal.copy()
        self._local_scores = np.abs(y_true_cal - y_pred_cal)

        # Fit k-NN model on calibration features
        self._knn = NearestNeighbors(
            n_neighbors=self.k_neighbors,
            metric='euclidean',
            algorithm='auto',
        )
        self._knn.fit(X_cal)
        self._adaptive_fitted = True

        logger.info(
            f"AdaptiveConformalPredictor fitted: k={self.k_neighbors}, "
            f"n_cal={n}, feature_dim={X_cal.shape[1]}"
        )

    def predict_adaptive(self, x: np.ndarray, y_pred: float) -> dict:
        """
        Adaptive prediction set based on local calibration.

        Finds k nearest neighbors in feature space, computes the
        local nonconformity quantile, and constructs a prediction set.

        Args:
            x: Feature vector for the new sample. Shape (d,) or (1, d).
            y_pred: Model prediction for the new sample.

        Returns:
            dict with same keys as predict_set, plus:
                local_quantile: The locally-adapted quantile
                n_neighbors_used: Number of neighbors used
        """
        if not self._adaptive_fitted:
            raise RuntimeError(
                "AdaptiveConformalPredictor not fitted. Call fit_adaptive() first."
            )

        x = np.asarray(x, dtype=np.float64)
        if x.ndim == 1:
            x = x.reshape(1, -1)

        y_pred = float(y_pred)

        # Find k nearest neighbors
        distances, indices = self._knn.kneighbors(x)
        neighbor_scores = self._local_scores[indices[0]]

        # Compute local quantile (same formula as global, but on neighbors)
        k = len(neighbor_scores)
        quantile_level = min(
            np.ceil((1 - self.alpha) * (k + 1)) / k,
            1.0
        )
        local_quantile = float(np.quantile(neighbor_scores, quantile_level))

        # Construct prediction set with local quantile
        lower = max(0.0, y_pred - local_quantile)
        upper = min(1.0, y_pred + local_quantile)

        # Calibrated probability via Platt scaling (global, not local)
        calibrated_prob = self.calibrate_score(y_pred)

        return {
            'prediction': y_pred,
            'prediction_set': [round(lower, 6), round(upper, 6)],
            'set_width': round(upper - lower, 6),
            'calibrated_probability': round(calibrated_prob, 6),
            'coverage_level': round(1 - self.alpha, 4),
            'local_quantile': round(local_quantile, 6),
            'global_quantile': round(self.quantile, 6),
            'n_neighbors_used': k,
            'avg_neighbor_distance': round(float(distances[0].mean()), 6),
        }


class CalibrationMonitor:
    """
    Monitors calibration quality over time using reliability diagrams
    and calibration error metrics.

    Key metrics:
    - ECE (Expected Calibration Error): Weighted average of per-bin
      |accuracy - confidence|. Lower is better.
    - MCE (Maximum Calibration Error): Worst-case per-bin error.
    - Reliability diagram: Visual check of calibration quality.

    Thresholds:
    - ECE < 0.05: Well-calibrated
    - ECE 0.05-0.10: Marginally calibrated
    - ECE > 0.10: Poorly calibrated, recalibration needed
    """

    def compute_calibration_metrics(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        n_bins: int = 10,
    ) -> dict:
        """
        Compute Expected Calibration Error (ECE) and reliability diagram data.

        Args:
            y_pred: Predicted probabilities. Shape (n_samples,).
            y_true: True binary labels. Shape (n_samples,).
            n_bins: Number of bins for the reliability diagram.

        Returns:
            dict with keys:
                ece: Expected Calibration Error
                mce: Maximum Calibration Error
                reliability_diagram: list of {bin_center, observed_freq,
                    predicted_freq, count} per bin
                is_well_calibrated: True if ECE < 0.05
                n_samples: Total samples used
        """
        y_pred = np.asarray(y_pred, dtype=np.float64)
        y_true = np.asarray(y_true, dtype=np.float64)

        n = len(y_pred)
        if n == 0:
            return {
                'ece': 1.0,
                'mce': 1.0,
                'reliability_diagram': [],
                'is_well_calibrated': False,
                'n_samples': 0,
            }

        # Create bins
        bin_edges = np.linspace(0, 1, n_bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

        ece = 0.0
        mce = 0.0
        reliability_diagram = []

        for i in range(n_bins):
            # Find samples in this bin
            if i == n_bins - 1:
                # Last bin: include right edge
                mask = (y_pred >= bin_edges[i]) & (y_pred <= bin_edges[i + 1])
            else:
                mask = (y_pred >= bin_edges[i]) & (y_pred < bin_edges[i + 1])

            count = int(mask.sum())

            if count == 0:
                reliability_diagram.append({
                    'bin_center': round(float(bin_centers[i]), 3),
                    'observed_freq': 0.0,
                    'predicted_freq': 0.0,
                    'count': 0,
                })
                continue

            # Average predicted probability in this bin
            predicted_freq = float(y_pred[mask].mean())

            # Actual frequency of positives in this bin
            observed_freq = float(y_true[mask].mean())

            # Bin-wise calibration error
            bin_error = abs(observed_freq - predicted_freq)

            # Weighted contribution to ECE
            ece += (count / n) * bin_error

            # Track max calibration error
            mce = max(mce, bin_error)

            reliability_diagram.append({
                'bin_center': round(float(bin_centers[i]), 3),
                'observed_freq': round(observed_freq, 4),
                'predicted_freq': round(predicted_freq, 4),
                'count': count,
            })

        return {
            'ece': round(float(ece), 6),
            'mce': round(float(mce), 6),
            'reliability_diagram': reliability_diagram,
            'is_well_calibrated': ece < 0.05,
            'n_samples': n,
        }

    def compute_coverage(
        self,
        y_pred: np.ndarray,
        y_true: np.ndarray,
        quantile: float,
    ) -> dict:
        """
        Compute empirical coverage of prediction sets.

        Args:
            y_pred: Predicted probabilities. Shape (n_samples,).
            y_true: True binary labels. Shape (n_samples,).
            quantile: Conformal quantile threshold.

        Returns:
            dict with actual coverage vs target coverage.
        """
        y_pred = np.asarray(y_pred, dtype=np.float64)
        y_true = np.asarray(y_true, dtype=np.float64)

        # Check if true labels fall within prediction sets
        lower = np.maximum(0.0, y_pred - quantile)
        upper = np.minimum(1.0, y_pred + quantile)

        covered = ((y_true >= lower) & (y_true <= upper)).mean()

        return {
            'coverage_actual': round(float(covered), 4),
            'n_samples': len(y_pred),
        }

    async def check_calibration_drift(
        self,
        pool,
        window_days: int = 30,
        ece_threshold: float = 0.10,
    ) -> dict:
        """
        Compare calibration on recent predictions vs historical.
        Alert if ECE increases beyond threshold.

        Uses calibrated predictions from the database and checks
        against proxy labels (corruption flags).

        Args:
            pool: asyncpg connection pool.
            window_days: Days to look back for recent predictions.
            ece_threshold: Threshold above which drift is flagged.

        Returns:
            dict with drift analysis results.
        """
        async with pool.acquire() as conn:
            # Get recent calibrated predictions with proxy labels
            rows = await conn.fetch("""
                SELECT
                    cp.tender_id,
                    cp.calibrated_probability,
                    cp.raw_score,
                    CASE
                        WHEN EXISTS (
                            SELECT 1 FROM corruption_flags cf
                            WHERE cf.tender_id = cp.tender_id
                              AND cf.flag_type IN (
                                  'short_deadline', 'price_anomaly',
                                  'bid_clustering', 'repeat_winner'
                              )
                              AND cf.score >= 30
                        ) THEN 1
                        ELSE 0
                    END as proxy_label
                FROM calibrated_predictions cp
                WHERE cp.calibrated_at > NOW() - $1::interval
                ORDER BY cp.calibrated_at DESC
            """, f"{window_days} days")

            if len(rows) < 20:
                return {
                    'drift_detected': False,
                    'reason': f'Insufficient data: {len(rows)} samples (need >= 20)',
                    'n_samples': len(rows),
                    'window_days': window_days,
                }

            y_pred = np.array([float(r['calibrated_probability']) for r in rows])
            y_true = np.array([int(r['proxy_label']) for r in rows])

            # Compute calibration metrics on recent data
            metrics = self.compute_calibration_metrics(y_pred, y_true)

            drift_detected = metrics['ece'] > ece_threshold

            return {
                'drift_detected': drift_detected,
                'ece': metrics['ece'],
                'mce': metrics['mce'],
                'is_well_calibrated': metrics['is_well_calibrated'],
                'n_samples': len(rows),
                'window_days': window_days,
                'ece_threshold': ece_threshold,
                'reliability_diagram': metrics['reliability_diagram'],
                'recommendation': (
                    'Recalibration recommended: ECE exceeds threshold.'
                    if drift_detected
                    else 'Calibration within acceptable range.'
                ),
            }

    async def store_calibration_check(self, pool, metrics: dict):
        """
        Store calibration check results for tracking over time.

        Args:
            pool: asyncpg connection pool.
            metrics: dict from check_calibration_drift or compute_calibration_metrics.
        """
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO calibration_checks (
                    model_name, ece, mce,
                    coverage_actual, coverage_target,
                    n_samples, drift_detected, checked_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
            """,
                metrics.get('model_name', 'xgboost_rf_v1'),
                metrics.get('ece', 0.0),
                metrics.get('mce', 0.0),
                metrics.get('coverage_actual'),
                metrics.get('coverage_target'),
                metrics.get('n_samples', 0),
                metrics.get('drift_detected', False),
            )
