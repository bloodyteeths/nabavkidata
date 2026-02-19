"""
Adversarial Robustness Analysis for Corruption Detection

Analyzes model vulnerability to feature perturbation and provides:
1. Feature sensitivity analysis (which features are most gameable)
2. Minimum perturbation to flip prediction (robustness margin)
3. Adversarial example generation for model hardening
4. Robustness score per prediction

Uses only numpy and sklearn -- no torch or adversarial ML libraries.
Gradient approximation via finite differences (tree models lack true gradients).

Author: nabavkidata.com
"""

import logging
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import joblib

logger = logging.getLogger(__name__)

MODELS_DIR = Path(__file__).parent / "models"

# Feature constraints: maps feature name -> (min_value, max_value)
# These ensure adversarial examples remain physically realistic.
FEATURE_CONSTRAINTS = {
    # Competition features
    'num_bidders': (0.0, 100.0),
    'single_bidder': (0.0, 1.0),
    'no_bidders': (0.0, 1.0),
    'two_bidders': (0.0, 1.0),
    'bidders_vs_institution_avg': (0.0, 50.0),
    'bidders_vs_category_avg': (0.0, 50.0),
    'num_disqualified': (0.0, 100.0),
    'disqualification_rate': (0.0, 1.0),
    'winner_rank': (0.0, 100.0),
    'winner_not_lowest': (0.0, 1.0),
    'market_concentration_hhi': (0.0, 10000.0),
    'new_bidders_count': (0.0, 100.0),
    'new_bidders_ratio': (0.0, 1.0),
    'bidder_clustering_score': (0.0, 1.0),

    # Price features
    'estimated_value_mkd': (0.0, 1e12),
    'actual_value_mkd': (0.0, 1e12),
    'has_estimated_value': (0.0, 1.0),
    'has_actual_value': (0.0, 1.0),
    'price_vs_estimate_ratio': (0.0, 100.0),
    'price_deviation_from_estimate': (-10.0, 10.0),
    'price_above_estimate': (0.0, 1.0),
    'price_below_estimate': (0.0, 1.0),
    'price_exact_match_estimate': (0.0, 1.0),
    'price_very_close_estimate': (0.0, 1.0),
    'price_deviation_large': (0.0, 1.0),
    'price_deviation_very_large': (0.0, 1.0),
    'bid_coefficient_of_variation': (0.0, 10.0),
    'bid_low_variance': (0.0, 1.0),
    'bid_very_low_variance': (0.0, 1.0),
    'winner_vs_mean_ratio': (0.0, 100.0),
    'winner_vs_median_ratio': (0.0, 100.0),
    'winner_bid_z_score': (-10.0, 10.0),
    'winner_extremely_low': (0.0, 1.0),
    'value_log': (0.0, 15.0),
    'value_small': (0.0, 1.0),
    'value_medium': (0.0, 1.0),
    'value_large': (0.0, 1.0),
    'value_very_large': (0.0, 1.0),

    # Timing features
    'deadline_days': (0.0, 365.0),
    'deadline_very_short': (0.0, 1.0),
    'deadline_short': (0.0, 1.0),
    'deadline_normal': (0.0, 1.0),
    'deadline_long': (0.0, 1.0),
    'time_to_award_days': (0.0, 365.0),
    'pub_day_of_week': (0.0, 6.0),
    'pub_friday': (0.0, 1.0),
    'pub_weekend': (0.0, 1.0),
    'pub_month': (1.0, 12.0),
    'pub_end_of_year': (0.0, 1.0),
    'amendment_count': (0.0, 50.0),
    'has_amendments': (0.0, 1.0),
    'many_amendments': (0.0, 1.0),
    'amendment_days_before_closing': (0.0, 365.0),
    'amendment_very_late': (0.0, 1.0),

    # Relationship features
    'winner_prev_wins_at_institution': (0.0, 10000.0),
    'winner_prev_bids_at_institution': (0.0, 10000.0),
    'winner_win_rate_at_institution': (0.0, 1.0),
    'winner_high_win_rate': (0.0, 1.0),
    'winner_very_high_win_rate': (0.0, 1.0),
    'winner_market_share_at_institution': (0.0, 1.0),
    'winner_dominant_supplier': (0.0, 1.0),
    'winner_total_wins': (0.0, 100000.0),
    'winner_total_bids': (0.0, 100000.0),
    'winner_overall_win_rate': (0.0, 1.0),
    'winner_num_institutions': (0.0, 10000.0),
    'winner_new_supplier': (0.0, 1.0),
    'winner_experienced_supplier': (0.0, 1.0),
    'num_related_bidder_pairs': (0.0, 1000.0),
    'has_related_bidders': (0.0, 1.0),
    'all_bidders_related': (0.0, 1.0),
    'institution_total_tenders': (0.0, 100000.0),
    'institution_single_bidder_rate': (0.0, 1.0),
    'institution_avg_bidders': (0.0, 100.0),

    # Procedural features
    'status_open': (0.0, 1.0),
    'status_closed': (0.0, 1.0),
    'status_awarded': (0.0, 1.0),
    'status_cancelled': (0.0, 1.0),
    'eval_lowest_price': (0.0, 1.0),
    'eval_best_value': (0.0, 1.0),
    'has_eval_method': (0.0, 1.0),
    'has_lots': (0.0, 1.0),
    'num_lots': (0.0, 200.0),
    'many_lots': (0.0, 1.0),
    'has_security_deposit': (0.0, 1.0),
    'has_performance_guarantee': (0.0, 1.0),
    'security_deposit_ratio': (0.0, 1.0),
    'performance_guarantee_ratio': (0.0, 1.0),
    'has_cpv_code': (0.0, 1.0),
    'has_category': (0.0, 1.0),

    # Document features
    'num_documents': (0.0, 500.0),
    'has_documents': (0.0, 1.0),
    'many_documents': (0.0, 1.0),
    'num_docs_extracted': (0.0, 500.0),
    'doc_extraction_success_rate': (0.0, 1.0),
    'total_doc_content_length': (0.0, 1e8),
    'avg_doc_content_length': (0.0, 1e7),
    'has_specification': (0.0, 1.0),
    'has_contract': (0.0, 1.0),

    # Historical features
    'tender_age_days': (0.0, 10000.0),
    'tender_very_recent': (0.0, 1.0),
    'tender_recent': (0.0, 1.0),
    'tender_old': (0.0, 1.0),
    'scrape_count': (0.0, 100.0),
    'rescraped': (0.0, 1.0),
    'institution_tenders_same_month': (0.0, 10000.0),
    'institution_tenders_prev_month': (0.0, 10000.0),
    'institution_activity_spike': (0.0, 1.0),
}

# Binary features should not be continuously perturbed
BINARY_FEATURES = {
    'single_bidder', 'no_bidders', 'two_bidders', 'winner_not_lowest',
    'has_estimated_value', 'has_actual_value',
    'price_above_estimate', 'price_below_estimate',
    'price_exact_match_estimate', 'price_very_close_estimate',
    'price_deviation_large', 'price_deviation_very_large',
    'bid_low_variance', 'bid_very_low_variance', 'winner_extremely_low',
    'value_small', 'value_medium', 'value_large', 'value_very_large',
    'deadline_very_short', 'deadline_short', 'deadline_normal', 'deadline_long',
    'pub_friday', 'pub_weekend', 'pub_end_of_year',
    'has_amendments', 'many_amendments', 'amendment_very_late',
    'winner_high_win_rate', 'winner_very_high_win_rate',
    'winner_dominant_supplier', 'winner_new_supplier', 'winner_experienced_supplier',
    'has_related_bidders', 'all_bidders_related',
    'status_open', 'status_closed', 'status_awarded', 'status_cancelled',
    'eval_lowest_price', 'eval_best_value', 'has_eval_method',
    'has_lots', 'many_lots',
    'has_security_deposit', 'has_performance_guarantee',
    'has_cpv_code', 'has_category',
    'has_documents', 'many_documents', 'has_specification', 'has_contract',
    'tender_very_recent', 'tender_recent', 'tender_old', 'rescraped',
    'institution_activity_spike',
}

# Features that are externally observable and potentially gameable by corrupt actors
# (e.g., they can add more documents, extend deadlines, etc.)
GAMEABLE_FEATURES = {
    'num_bidders', 'deadline_days', 'amendment_count', 'num_documents',
    'num_lots', 'bid_coefficient_of_variation', 'bid_range',
    'new_bidders_count', 'new_bidders_ratio',
    'total_doc_content_length', 'avg_doc_content_length',
    'num_docs_extracted', 'doc_extraction_success_rate',
}


class AdversarialAnalyzer:
    """
    Adversarial robustness analyzer for tree-based corruption detection models.

    Uses finite-difference gradient approximation to:
    - Measure per-feature sensitivity of model output
    - Find minimum perturbation to flip the decision boundary
    - Generate adversarial examples for model hardening
    - Provide robustness scores per prediction
    """

    def __init__(self):
        self.model = None
        self.imputer = None
        self.scaler = None
        self.feature_names: List[str] = []
        self.model_name: str = ''
        self._loaded = False

    def load_model(self, model_name: str = 'xgboost') -> None:
        """
        Load model and preprocessing pipeline from joblib files.

        Args:
            model_name: 'xgboost' or 'random_forest'
        """
        self.model_name = model_name

        if model_name == 'xgboost':
            model_path = MODELS_DIR / "xgboost_real.joblib"
        elif model_name == 'random_forest':
            model_path = MODELS_DIR / "random_forest_real.joblib"
        else:
            raise ValueError(f"Unknown model: {model_name}. Use 'xgboost' or 'random_forest'.")

        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        package = joblib.load(model_path)
        self.model = package['model']
        self.imputer = package['imputer']
        self.scaler = package['scaler']
        self.feature_names = package['feature_names']
        self._loaded = True

        logger.info(
            f"Loaded {model_name} model with {len(self.feature_names)} features"
        )

    def _ensure_loaded(self) -> None:
        """Ensure model is loaded before operations."""
        if not self._loaded:
            raise RuntimeError("Model not loaded. Call load_model() first.")

    def _predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict probability of corruption (class 1) for preprocessed feature vectors.

        Args:
            X: Raw feature array (before imputation/scaling), shape (n_samples, n_features)

        Returns:
            Array of probabilities, shape (n_samples,)
        """
        self._ensure_loaded()
        X_clean = np.nan_to_num(X, nan=0, posinf=0, neginf=0)
        X_imp = self.imputer.transform(X_clean)
        X_scaled = self.scaler.transform(X_imp)
        return self.model.predict_proba(X_scaled)[:, 1]

    def _predict_single(self, feature_vector: np.ndarray) -> float:
        """Predict probability for a single feature vector."""
        return float(self._predict_proba(feature_vector.reshape(1, -1))[0])

    def compute_feature_sensitivity(
        self,
        feature_vector: np.ndarray,
        epsilon: float = 0.01
    ) -> dict:
        """
        For each feature, compute the numerical gradient of model output via
        finite differences: (f(x + eps) - f(x - eps)) / (2 * eps).

        For binary features, we test flipping 0->1 and 1->0.

        Args:
            feature_vector: 1-D array of raw feature values (length = n_features)
            epsilon: Step size for finite differences (fraction of feature range)

        Returns:
            {
                'sensitivities': [{feature_name, sensitivity, direction, gameable}],
                'most_vulnerable_features': [top 5 by |sensitivity|],
                'least_vulnerable_features': [bottom 5],
            }
        """
        self._ensure_loaded()
        fv = feature_vector.copy().astype(np.float64)
        base_pred = self._predict_single(fv)

        sensitivities = []

        for i, feat_name in enumerate(self.feature_names):
            is_binary = feat_name in BINARY_FEATURES
            is_gameable = feat_name in GAMEABLE_FEATURES

            if is_binary:
                # For binary features, compute sensitivity as difference from flipping
                fv_flip = fv.copy()
                fv_flip[i] = 1.0 - fv[i]  # flip 0->1 or 1->0
                flip_pred = self._predict_single(fv_flip)
                sensitivity = flip_pred - base_pred
            else:
                # Finite difference gradient approximation
                constraints = FEATURE_CONSTRAINTS.get(feat_name, (None, None))
                feat_min, feat_max = constraints

                if feat_min is not None and feat_max is not None:
                    feat_range = feat_max - feat_min
                    step = epsilon * max(feat_range, 1e-6)
                else:
                    step = epsilon * max(abs(fv[i]), 1.0)

                fv_plus = fv.copy()
                fv_minus = fv.copy()
                fv_plus[i] = fv[i] + step
                fv_minus[i] = fv[i] - step

                # Clip to valid range
                if feat_min is not None:
                    fv_plus[i] = min(fv_plus[i], feat_max)
                    fv_minus[i] = max(fv_minus[i], feat_min)

                pred_plus = self._predict_single(fv_plus)
                pred_minus = self._predict_single(fv_minus)

                actual_step = fv_plus[i] - fv_minus[i]
                if abs(actual_step) > 1e-12:
                    sensitivity = (pred_plus - pred_minus) / actual_step
                else:
                    sensitivity = 0.0

            # Direction: positive means increasing feature increases risk
            direction = 'increases_risk' if sensitivity > 0 else 'decreases_risk'

            sensitivities.append({
                'feature_name': feat_name,
                'sensitivity': float(sensitivity),
                'abs_sensitivity': float(abs(sensitivity)),
                'direction': direction,
                'gameable': is_gameable,
                'is_binary': is_binary,
                'current_value': float(fv[i]),
            })

        # Sort by absolute sensitivity
        sensitivities.sort(key=lambda x: x['abs_sensitivity'], reverse=True)

        return {
            'base_prediction': float(base_pred),
            'sensitivities': sensitivities,
            'most_vulnerable_features': [
                {
                    'feature_name': s['feature_name'],
                    'sensitivity': s['sensitivity'],
                    'direction': s['direction'],
                    'gameable': s['gameable'],
                }
                for s in sensitivities[:5]
            ],
            'least_vulnerable_features': [
                {
                    'feature_name': s['feature_name'],
                    'sensitivity': s['sensitivity'],
                    'direction': s['direction'],
                    'gameable': s['gameable'],
                }
                for s in sensitivities[-5:]
            ],
            'gameable_sensitive_features': [
                {
                    'feature_name': s['feature_name'],
                    'sensitivity': s['sensitivity'],
                    'direction': s['direction'],
                }
                for s in sensitivities if s['gameable'] and s['abs_sensitivity'] > 1e-4
            ],
        }

    def compute_robustness_margin(
        self,
        feature_vector: np.ndarray,
        current_pred: Optional[float] = None,
        threshold: float = 0.5,
        max_features_to_perturb: int = 10,
        max_iterations: int = 50,
    ) -> dict:
        """
        Find minimum perturbation to flip prediction across the decision threshold.
        Uses iterative greedy search on the most sensitive features.

        Algorithm:
        1. Compute feature sensitivities
        2. Rank features by |sensitivity| (continuous, non-binary only)
        3. For each top feature, binary search for the flip point
        4. Find the feature requiring the smallest perturbation to flip

        Args:
            feature_vector: 1-D raw feature array
            current_pred: Current prediction (computed if None)
            threshold: Decision boundary threshold
            max_features_to_perturb: Max features to try perturbing
            max_iterations: Max binary search iterations per feature

        Returns:
            {
                'current_prediction': float,
                'robustness_margin': float,  # L2 norm of minimum perturbation
                'robustness_level': str,     # 'robust', 'moderate', 'fragile'
                'flip_features': [{feature, original_value, flipped_value, perturbation}],
                'is_boundary_case': bool,    # within 0.1 of decision boundary
            }
        """
        self._ensure_loaded()
        fv = feature_vector.copy().astype(np.float64)

        if current_pred is None:
            current_pred = self._predict_single(fv)

        # Determine which direction we need to push
        is_flagged = current_pred >= threshold
        target_direction = -1.0 if is_flagged else 1.0  # push opposite of threshold

        # Get sensitivities
        sens_result = self.compute_feature_sensitivity(fv)
        sensitivities = sens_result['sensitivities']

        # Filter to continuous features that push in the right direction
        candidate_features = []
        for s in sensitivities:
            if s['is_binary']:
                continue
            # We want features where perturbing in the right direction flips
            # If we need to decrease risk (target_direction < 0),
            # we want features with positive sensitivity (so decreasing them lowers risk)
            # or negative sensitivity (so increasing them lowers risk)
            if abs(s['sensitivity']) > 1e-6:
                candidate_features.append(s)

        candidate_features = candidate_features[:max_features_to_perturb]

        best_flip = None
        best_l2 = float('inf')
        flip_features = []

        for feat_info in candidate_features:
            feat_idx = self.feature_names.index(feat_info['feature_name'])
            feat_name = feat_info['feature_name']
            original_value = float(fv[feat_idx])

            constraints = FEATURE_CONSTRAINTS.get(feat_name, (None, None))
            feat_min, feat_max = constraints
            if feat_min is None:
                feat_min = original_value - 100 * abs(original_value + 1)
            if feat_max is None:
                feat_max = original_value + 100 * abs(original_value + 1)

            # Determine search direction based on sensitivity and target
            # sensitivity > 0 means increasing feature increases risk
            if (target_direction < 0 and feat_info['sensitivity'] > 0):
                # Need to decrease this feature to lower risk
                search_low, search_high = feat_min, original_value
            elif (target_direction < 0 and feat_info['sensitivity'] < 0):
                # Need to increase this feature to lower risk
                search_low, search_high = original_value, feat_max
            elif (target_direction > 0 and feat_info['sensitivity'] > 0):
                # Need to increase this feature to raise risk
                search_low, search_high = original_value, feat_max
            else:
                # Need to decrease this feature to raise risk
                search_low, search_high = feat_min, original_value

            # Binary search for the flip point
            flipped = False
            flip_value = None

            for _ in range(max_iterations):
                mid = (search_low + search_high) / 2.0
                fv_test = fv.copy()
                fv_test[feat_idx] = mid
                test_pred = self._predict_single(fv_test)

                crossed = (is_flagged and test_pred < threshold) or \
                          (not is_flagged and test_pred >= threshold)

                if crossed:
                    flipped = True
                    flip_value = mid
                    # Narrow toward original to find minimal perturbation
                    if mid > original_value:
                        search_high = mid
                    else:
                        search_low = mid
                else:
                    # Widen away from original
                    if mid > original_value:
                        search_low = mid
                    else:
                        search_high = mid

                if abs(search_high - search_low) < 1e-8:
                    break

            if flipped and flip_value is not None:
                perturbation = abs(flip_value - original_value)
                # Normalize perturbation by feature range
                feat_range = (feat_max - feat_min) if (feat_max - feat_min) > 0 else 1.0
                normalized_perturbation = perturbation / feat_range
                l2_contribution = normalized_perturbation ** 2

                if l2_contribution < best_l2:
                    best_l2 = l2_contribution
                    best_flip = feat_name

                flip_features.append({
                    'feature': feat_name,
                    'original_value': original_value,
                    'flipped_value': float(flip_value),
                    'perturbation': float(perturbation),
                    'normalized_perturbation': float(normalized_perturbation),
                })

        # Sort flip features by normalized perturbation
        flip_features.sort(key=lambda x: x['normalized_perturbation'])

        robustness_margin = float(np.sqrt(best_l2)) if best_l2 < float('inf') else 1.0
        is_boundary = abs(current_pred - threshold) < 0.1

        # Classify robustness level
        if robustness_margin >= 0.3:
            robustness_level = 'robust'
        elif robustness_margin >= 0.1:
            robustness_level = 'moderate'
        else:
            robustness_level = 'fragile'

        return {
            'current_prediction': float(current_pred),
            'robustness_margin': robustness_margin,
            'robustness_level': robustness_level,
            'flip_features': flip_features[:5],  # Top 5 easiest flips
            'is_boundary_case': is_boundary,
            'total_flippable_features': len(flip_features),
            'easiest_flip_feature': best_flip,
        }

    def generate_adversarial_examples(
        self,
        feature_vector: np.ndarray,
        n_examples: int = 10,
        epsilon: float = 0.1,
        target_direction: str = 'reduce_risk',
    ) -> list:
        """
        Generate adversarial examples using FGSM-like approach for tabular data:
        1. Compute feature sensitivities
        2. Perturb features in direction that changes risk score
        3. Constrain perturbations to be realistic (non-negative bidders, valid ranges)

        Args:
            feature_vector: 1-D raw feature array
            n_examples: Number of adversarial examples to generate
            epsilon: Maximum perturbation magnitude (as fraction of feature range)
            target_direction: 'reduce_risk' or 'increase_risk'

        Returns:
            List of dicts with perturbed feature vectors and new predictions.
            Used for adversarial training data augmentation.
        """
        self._ensure_loaded()
        fv = feature_vector.copy().astype(np.float64)
        base_pred = self._predict_single(fv)

        # Compute sensitivities
        sens_result = self.compute_feature_sensitivity(fv)
        sensitivities = sens_result['sensitivities']

        # Build gradient-like direction vector
        gradient = np.zeros(len(self.feature_names))
        for s in sensitivities:
            idx = self.feature_names.index(s['feature_name'])
            gradient[idx] = s['sensitivity']

        # Direction multiplier
        if target_direction == 'reduce_risk':
            direction = -1.0  # move opposite to gradient
        else:
            direction = 1.0   # move along gradient

        examples = []

        for i in range(n_examples):
            # Scale epsilon for this example (vary from small to large)
            scale = epsilon * (i + 1) / n_examples

            # Add random noise to gradient direction for diversity
            rng = np.random.RandomState(42 + i)
            noise = rng.normal(0, 0.1, size=gradient.shape)
            perturb_direction = gradient * direction + noise

            # Normalize
            norm = np.linalg.norm(perturb_direction)
            if norm > 1e-10:
                perturb_direction = perturb_direction / norm

            # Apply perturbation
            fv_adv = fv.copy()
            perturbed_features = []

            for j, feat_name in enumerate(self.feature_names):
                if feat_name in BINARY_FEATURES:
                    # Skip binary features in continuous perturbation
                    continue

                constraints = FEATURE_CONSTRAINTS.get(feat_name, (None, None))
                feat_min, feat_max = constraints
                if feat_min is None or feat_max is None:
                    continue

                feat_range = feat_max - feat_min
                if feat_range <= 0:
                    continue

                step = scale * feat_range * perturb_direction[j]
                new_val = fv[j] + step

                # Clip to valid range
                new_val = np.clip(new_val, feat_min, feat_max)

                if abs(new_val - fv[j]) > 1e-10:
                    fv_adv[j] = new_val
                    perturbed_features.append({
                        'feature': feat_name,
                        'original': float(fv[j]),
                        'perturbed': float(new_val),
                        'delta': float(new_val - fv[j]),
                    })

            adv_pred = self._predict_single(fv_adv)

            # Compute L2 distance (normalized by feature ranges)
            l2_dist = 0.0
            for j, feat_name in enumerate(self.feature_names):
                constraints = FEATURE_CONSTRAINTS.get(feat_name, (None, None))
                feat_min, feat_max = constraints
                if feat_min is not None and feat_max is not None:
                    feat_range = max(feat_max - feat_min, 1e-10)
                    l2_dist += ((fv_adv[j] - fv[j]) / feat_range) ** 2
            l2_dist = float(np.sqrt(l2_dist))

            examples.append({
                'example_id': i,
                'feature_vector': fv_adv.tolist(),
                'original_prediction': float(base_pred),
                'adversarial_prediction': float(adv_pred),
                'prediction_change': float(adv_pred - base_pred),
                'l2_distance': l2_dist,
                'epsilon_used': float(scale),
                'n_features_perturbed': len(perturbed_features),
                'top_perturbations': sorted(
                    perturbed_features,
                    key=lambda x: abs(x['delta']),
                    reverse=True
                )[:5],
            })

        # Sort by prediction change magnitude
        examples.sort(key=lambda x: abs(x['prediction_change']), reverse=True)

        return examples

    def assess_prediction_robustness(
        self,
        feature_vector: np.ndarray,
    ) -> dict:
        """
        Full robustness assessment for a single prediction.
        Combines sensitivity, margin, and adversarial analysis.

        Args:
            feature_vector: 1-D raw feature array

        Returns:
            {
                'prediction': float,
                'robustness_score': float (0-1, higher is more robust),
                'robustness_level': str,
                'robustness_margin': float,
                'is_boundary_case': bool,
                'vulnerable_features': list,
                'gameable_vulnerabilities': list,
                'adversarial_resistance': float (0-1),
                'recommendations': list of str,
            }
        """
        self._ensure_loaded()
        fv = feature_vector.copy().astype(np.float64)
        current_pred = self._predict_single(fv)

        # 1. Feature sensitivity analysis
        sens = self.compute_feature_sensitivity(fv)

        # 2. Robustness margin
        margin = self.compute_robustness_margin(fv, current_pred=current_pred)

        # 3. Generate adversarial examples (small set for scoring)
        adv_examples = self.generate_adversarial_examples(
            fv, n_examples=5, epsilon=0.05, target_direction='reduce_risk'
        )

        # 4. Compute adversarial resistance
        # How much does the prediction change under small perturbations?
        pred_changes = [abs(ex['prediction_change']) for ex in adv_examples]
        avg_change = float(np.mean(pred_changes)) if pred_changes else 0.0
        max_change = float(np.max(pred_changes)) if pred_changes else 0.0

        # Resistance: 1.0 means no change, 0.0 means huge change
        adversarial_resistance = max(0.0, 1.0 - max_change)

        # 5. Compute overall robustness score (0-1)
        # Weighted combination of margin, distance from boundary, and resistance
        boundary_distance = abs(current_pred - 0.5)
        margin_score = min(margin['robustness_margin'] / 0.5, 1.0)

        robustness_score = (
            0.4 * margin_score +
            0.3 * min(boundary_distance * 2, 1.0) +
            0.3 * adversarial_resistance
        )
        robustness_score = float(np.clip(robustness_score, 0.0, 1.0))

        # 6. Classify level
        if robustness_score >= 0.7:
            robustness_level = 'robust'
        elif robustness_score >= 0.4:
            robustness_level = 'moderate'
        else:
            robustness_level = 'fragile'

        # 7. Vulnerable features (top 5 most sensitive)
        vulnerable_features = [
            {
                'feature': s['feature_name'],
                'sensitivity': s['sensitivity'],
                'direction': s['direction'],
                'gameable': s['gameable'],
            }
            for s in sens['sensitivities'][:5]
        ]

        # 8. Gameable vulnerabilities
        gameable_vulns = sens.get('gameable_sensitive_features', [])

        # 9. Recommendations
        recommendations = []

        if margin['is_boundary_case']:
            recommendations.append(
                "Prediction is near the decision boundary (within 0.1). "
                "Manual review is recommended for this tender."
            )

        if len(gameable_vulns) > 0:
            top_gameable = gameable_vulns[0]['feature_name']
            recommendations.append(
                f"Feature '{top_gameable}' is both highly sensitive and gameable. "
                "Consider adding this to the watchlist for manual verification."
            )

        if robustness_level == 'fragile':
            recommendations.append(
                "This prediction is fragile -- small changes in input data could "
                "flip the classification. Cross-reference with rule-based flags."
            )

        if margin['total_flippable_features'] > 5:
            recommendations.append(
                f"{margin['total_flippable_features']} features can individually flip "
                "this prediction. The model has multiple attack surfaces for this case."
            )

        if adversarial_resistance < 0.5:
            recommendations.append(
                "Low adversarial resistance detected. This prediction is vulnerable "
                "to coordinated small perturbations across features."
            )

        return {
            'prediction': float(current_pred),
            'robustness_score': robustness_score,
            'robustness_level': robustness_level,
            'robustness_margin': margin['robustness_margin'],
            'is_boundary_case': margin['is_boundary_case'],
            'vulnerable_features': vulnerable_features,
            'gameable_vulnerabilities': gameable_vulns[:5],
            'adversarial_resistance': adversarial_resistance,
            'avg_prediction_change_under_perturbation': avg_change,
            'max_prediction_change_under_perturbation': max_change,
            'total_flippable_features': margin['total_flippable_features'],
            'easiest_flip_feature': margin.get('easiest_flip_feature'),
            'recommendations': recommendations,
            'model_name': self.model_name,
        }
