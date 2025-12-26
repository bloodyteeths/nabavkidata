"""
Anomaly Explainer for Corruption Detection

This module provides interpretable explanations for why a tender is
classified as anomalous. It generates both technical feature-level
explanations and natural language summaries.

Features:
- Feature contribution analysis
- Comparison with similar normal tenders
- Natural language explanation generation
- Visualization support

Author: nabavkidata.com
License: Proprietary
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


# Feature categories for explanation grouping
FEATURE_CATEGORIES = {
    'competition': [
        'num_bidders', 'single_bidder', 'no_bidders', 'two_bidders',
        'bidders_vs_institution_avg', 'bidders_vs_category_avg',
        'num_disqualified', 'disqualification_rate',
        'winner_rank', 'winner_not_lowest',
        'market_concentration_hhi',
        'new_bidders_count', 'new_bidders_ratio',
        'bidder_clustering_score'
    ],
    'price': [
        'estimated_value_mkd', 'actual_value_mkd', 'has_estimated_value', 'has_actual_value',
        'price_vs_estimate_ratio', 'price_deviation_from_estimate',
        'price_above_estimate', 'price_below_estimate',
        'price_exact_match_estimate', 'price_very_close_estimate',
        'price_deviation_large', 'price_deviation_very_large',
        'bid_mean', 'bid_median', 'bid_std', 'bid_min', 'bid_max', 'bid_range',
        'bid_coefficient_of_variation', 'bid_low_variance', 'bid_very_low_variance',
        'winner_vs_mean_ratio', 'winner_vs_median_ratio', 'winner_bid_z_score', 'winner_extremely_low',
        'value_log', 'value_small', 'value_medium', 'value_large', 'value_very_large'
    ],
    'timing': [
        'deadline_days', 'deadline_very_short', 'deadline_short', 'deadline_normal', 'deadline_long',
        'time_to_award_days',
        'pub_day_of_week', 'pub_friday', 'pub_weekend', 'pub_month', 'pub_end_of_year',
        'amendment_count', 'has_amendments', 'many_amendments',
        'amendment_days_before_closing', 'amendment_very_late'
    ],
    'relationship': [
        'winner_prev_wins_at_institution', 'winner_prev_bids_at_institution',
        'winner_win_rate_at_institution', 'winner_high_win_rate', 'winner_very_high_win_rate',
        'winner_market_share_at_institution', 'winner_dominant_supplier',
        'winner_total_wins', 'winner_total_bids', 'winner_overall_win_rate',
        'winner_num_institutions', 'winner_new_supplier', 'winner_experienced_supplier',
        'num_related_bidder_pairs', 'has_related_bidders', 'all_bidders_related',
        'institution_total_tenders', 'institution_single_bidder_rate', 'institution_avg_bidders'
    ],
    'procedural': [
        'status_open', 'status_closed', 'status_awarded', 'status_cancelled',
        'eval_lowest_price', 'eval_best_value', 'has_eval_method',
        'has_lots', 'num_lots', 'many_lots',
        'has_security_deposit', 'has_performance_guarantee',
        'security_deposit_ratio', 'performance_guarantee_ratio',
        'has_cpv_code', 'has_category'
    ],
    'document': [
        'num_documents', 'has_documents', 'many_documents',
        'num_docs_extracted', 'doc_extraction_success_rate',
        'total_doc_content_length', 'avg_doc_content_length',
        'has_specification', 'has_contract'
    ],
    'historical': [
        'tender_age_days', 'tender_very_recent', 'tender_recent', 'tender_old',
        'scrape_count', 'rescraped',
        'institution_tenders_same_month', 'institution_tenders_prev_month',
        'institution_activity_spike'
    ]
}

# Human-readable feature descriptions for natural language generation
FEATURE_DESCRIPTIONS = {
    # Competition
    'num_bidders': 'number of bidders',
    'single_bidder': 'only one bidder participated',
    'no_bidders': 'no bidders participated',
    'two_bidders': 'only two bidders participated',
    'bidders_vs_institution_avg': 'bidder count relative to institution average',
    'bidders_vs_category_avg': 'bidder count relative to category average',
    'num_disqualified': 'number of disqualified bidders',
    'disqualification_rate': 'bidder disqualification rate',
    'winner_rank': 'rank of the winning bidder',
    'winner_not_lowest': 'winner was not the lowest bidder',
    'market_concentration_hhi': 'market concentration (Herfindahl index)',
    'new_bidders_count': 'number of new bidders',
    'new_bidders_ratio': 'ratio of new to total bidders',
    'bidder_clustering_score': 'bidder co-occurrence clustering',

    # Price
    'estimated_value_mkd': 'estimated contract value',
    'actual_value_mkd': 'actual contract value',
    'price_vs_estimate_ratio': 'actual vs estimated price ratio',
    'price_deviation_from_estimate': 'deviation from estimated price',
    'price_above_estimate': 'final price above estimate',
    'price_below_estimate': 'final price below estimate',
    'price_exact_match_estimate': 'price exactly matches estimate (suspicious)',
    'price_very_close_estimate': 'price very close to estimate',
    'price_deviation_large': 'large price deviation (>20%)',
    'price_deviation_very_large': 'very large price deviation (>50%)',
    'bid_coefficient_of_variation': 'bid price variation coefficient',
    'bid_low_variance': 'unusually low bid variance (collusion indicator)',
    'bid_very_low_variance': 'very low bid variance (strong collusion indicator)',
    'winner_vs_mean_ratio': 'winner\'s bid vs average bid',
    'winner_vs_median_ratio': 'winner\'s bid vs median bid',
    'winner_bid_z_score': 'winner\'s bid z-score',
    'winner_extremely_low': 'winner\'s bid extremely low (abnormally low bid)',

    # Timing
    'deadline_days': 'deadline length in days',
    'deadline_very_short': 'very short deadline (<3 days)',
    'deadline_short': 'short deadline (<7 days)',
    'deadline_normal': 'normal deadline length',
    'deadline_long': 'long deadline (>30 days)',
    'time_to_award_days': 'time from closing to award',
    'pub_friday': 'published on Friday (less visibility)',
    'pub_weekend': 'published on weekend (less visibility)',
    'pub_end_of_year': 'published in December (year-end rush)',
    'amendment_count': 'number of amendments',
    'has_amendments': 'has amendments',
    'many_amendments': 'many amendments (3+)',
    'amendment_days_before_closing': 'days between last amendment and closing',
    'amendment_very_late': 'very late amendment (<2 days before closing)',

    # Relationship
    'winner_prev_wins_at_institution': 'winner\'s previous wins at this institution',
    'winner_prev_bids_at_institution': 'winner\'s previous bids at this institution',
    'winner_win_rate_at_institution': 'winner\'s win rate at this institution',
    'winner_high_win_rate': 'winner has high win rate (>60%)',
    'winner_very_high_win_rate': 'winner has very high win rate (>80%)',
    'winner_market_share_at_institution': 'winner\'s market share at institution',
    'winner_dominant_supplier': 'winner is dominant supplier (>50% market share)',
    'winner_total_wins': 'winner\'s total wins across all institutions',
    'winner_total_bids': 'winner\'s total bids across all institutions',
    'winner_overall_win_rate': 'winner\'s overall win rate',
    'winner_num_institutions': 'number of institutions winner has won at',
    'winner_new_supplier': 'winner is a new supplier',
    'winner_experienced_supplier': 'winner is experienced (10+ previous bids)',
    'num_related_bidder_pairs': 'number of related bidder pairs',
    'has_related_bidders': 'has related bidders',
    'all_bidders_related': 'all bidders are related',
    'institution_total_tenders': 'institution\'s total tender count',
    'institution_single_bidder_rate': 'institution\'s single bidder rate',
    'institution_avg_bidders': 'institution\'s average bidder count',

    # Procedural
    'has_lots': 'tender has multiple lots',
    'num_lots': 'number of lots',
    'many_lots': 'many lots (5+)',
    'has_security_deposit': 'requires security deposit',
    'has_performance_guarantee': 'requires performance guarantee',
    'security_deposit_ratio': 'security deposit as ratio of value',
    'performance_guarantee_ratio': 'performance guarantee as ratio of value',

    # Document
    'num_documents': 'number of documents',
    'has_documents': 'has documents',
    'many_documents': 'many documents (5+)',
    'num_docs_extracted': 'number of documents with extracted text',
    'doc_extraction_success_rate': 'document extraction success rate',
    'total_doc_content_length': 'total document content length',
    'avg_doc_content_length': 'average document content length',
    'has_specification': 'has specification document',
    'has_contract': 'has contract document',

    # Historical
    'tender_age_days': 'tender age in days',
    'tender_very_recent': 'very recent tender (<30 days)',
    'tender_recent': 'recent tender (<90 days)',
    'tender_old': 'old tender (>365 days)',
    'institution_tenders_same_month': 'institution tenders in same month',
    'institution_tenders_prev_month': 'institution tenders in previous month',
    'institution_activity_spike': 'institution activity spike'
}

# Risk pattern templates for natural language generation
RISK_PATTERNS = {
    'single_bidder_concern': {
        'triggers': [('single_bidder', 1.0)],
        'template': 'Only one bidder participated, which may indicate limited competition or tailored specifications.'
    },
    'bid_rigging_low_variance': {
        'triggers': [('bid_very_low_variance', 1.0)],
        'template': 'Bid prices show unusually low variance, which is a classic indicator of potential bid rigging or price coordination.'
    },
    'bid_rigging_low_variance_moderate': {
        'triggers': [('bid_low_variance', 1.0)],
        'template': 'Bid prices show relatively low variance, suggesting possible coordination among bidders.'
    },
    'dominant_supplier': {
        'triggers': [('winner_dominant_supplier', 1.0)],
        'template': 'The winner is a dominant supplier with over 50% market share at this institution, indicating potential favoritism.'
    },
    'high_win_rate': {
        'triggers': [('winner_very_high_win_rate', 1.0)],
        'template': 'The winner has an unusually high win rate (>80%) at this institution, suggesting possible preferential treatment.'
    },
    'price_exact_match': {
        'triggers': [('price_exact_match_estimate', 1.0)],
        'template': 'The winning price exactly matches the estimate, which is statistically improbable and may indicate information leakage.'
    },
    'very_short_deadline': {
        'triggers': [('deadline_very_short', 1.0)],
        'template': 'Very short bidding deadline (<3 days) may restrict competition and favor prepared insiders.'
    },
    'short_deadline': {
        'triggers': [('deadline_short', 1.0)],
        'template': 'Short bidding deadline (<7 days) may limit the pool of potential bidders.'
    },
    'weekend_publication': {
        'triggers': [('pub_weekend', 1.0)],
        'template': 'Published on weekend, reducing visibility to potential bidders.'
    },
    'friday_publication': {
        'triggers': [('pub_friday', 1.0)],
        'template': 'Published on Friday, potentially reducing visibility due to weekend following.'
    },
    'late_amendment': {
        'triggers': [('amendment_very_late', 1.0)],
        'template': 'Late amendment made less than 2 days before deadline, possibly to disadvantage some bidders.'
    },
    'related_bidders': {
        'triggers': [('has_related_bidders', 1.0)],
        'template': 'Multiple bidders appear to be related entities, raising concerns about sham bidding.'
    },
    'all_related_bidders': {
        'triggers': [('all_bidders_related', 1.0)],
        'template': 'All bidders are related entities, strongly suggesting coordinated sham bidding.'
    },
    'winner_not_lowest': {
        'triggers': [('winner_not_lowest', 1.0)],
        'template': 'Winner was not the lowest bidder, which may be justified but warrants review.'
    },
    'high_disqualification': {
        'triggers': [('disqualification_rate', 0.5)],  # threshold
        'template': 'High proportion of bidders were disqualified, potentially manipulating competition.'
    },
    'year_end_rush': {
        'triggers': [('pub_end_of_year', 1.0)],
        'template': 'Published in December during year-end budget spending rush, when oversight may be reduced.'
    },
    'new_supplier_high_value': {
        'triggers': [('winner_new_supplier', 1.0), ('value_large', 1.0)],
        'template': 'Winner is a new supplier with no prior history, awarded a large value contract.'
    },
    'institution_single_bidder_pattern': {
        'triggers': [('institution_single_bidder_rate', 0.4)],  # threshold
        'template': 'This institution has a pattern of single-bidder tenders, suggesting systemic competition issues.'
    },
    'low_bidder_count': {
        'triggers': [('bidders_vs_category_avg', 0.5)],  # threshold - below 50% of avg
        'template': 'Fewer bidders than typical for this category, indicating possible restricted competition.'
    },
    'price_deviation_high': {
        'triggers': [('price_deviation_very_large', 1.0)],
        'template': 'Large price deviation from estimate (>50%) may indicate poor estimation or manipulation.'
    },
    'bidder_clustering': {
        'triggers': [('bidder_clustering_score', 0.7)],  # threshold
        'template': 'Bidders frequently participate together in tenders, suggesting potential coordination.'
    }
}


@dataclass
class FeatureAnomaly:
    """Details about an anomalous feature"""
    feature_name: str
    feature_value: float
    normal_mean: float
    normal_std: float
    z_score: float
    contribution: float
    description: str
    category: str


@dataclass
class SimilarTender:
    """A similar normal tender for comparison"""
    tender_id: str
    distance: float
    key_differences: Dict[str, Tuple[float, float]]  # feature -> (anomaly_value, normal_value)


@dataclass
class AnomalyExplanation:
    """
    Complete explanation for why a tender is anomalous.

    Attributes:
        tender_id: The tender identifier
        anomaly_score: The overall anomaly score
        summary: Brief natural language summary
        risk_patterns: Identified risk patterns with explanations
        top_features: Most anomalous features with details
        category_breakdown: Anomaly contribution by feature category
        similar_normal_tenders: Similar normal tenders for comparison
        recommendations: Suggested investigation actions
        generated_at: Timestamp of explanation generation
    """
    tender_id: str
    anomaly_score: float
    summary: str
    risk_patterns: List[Dict[str, Any]]
    top_features: List[FeatureAnomaly]
    category_breakdown: Dict[str, float]
    similar_normal_tenders: List[SimilarTender]
    recommendations: List[str]
    generated_at: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'tender_id': self.tender_id,
            'anomaly_score': float(self.anomaly_score),
            'summary': self.summary,
            'risk_patterns': self.risk_patterns,
            'top_features': [
                {
                    'feature_name': f.feature_name,
                    'feature_value': float(f.feature_value),
                    'normal_mean': float(f.normal_mean),
                    'normal_std': float(f.normal_std),
                    'z_score': float(f.z_score),
                    'contribution': float(f.contribution),
                    'description': f.description,
                    'category': f.category
                }
                for f in self.top_features
            ],
            'category_breakdown': {k: float(v) for k, v in self.category_breakdown.items()},
            'similar_normal_tenders': [
                {
                    'tender_id': s.tender_id,
                    'distance': float(s.distance),
                    'key_differences': {
                        k: (float(v[0]), float(v[1]))
                        for k, v in s.key_differences.items()
                    }
                }
                for s in self.similar_normal_tenders
            ],
            'recommendations': self.recommendations,
            'generated_at': self.generated_at.isoformat()
        }

    def to_markdown(self) -> str:
        """Generate markdown explanation"""
        lines = [
            f"# Anomaly Analysis: Tender {self.tender_id}",
            "",
            f"**Anomaly Score:** {self.anomaly_score:.2%}",
            "",
            "## Summary",
            self.summary,
            ""
        ]

        if self.risk_patterns:
            lines.append("## Risk Patterns Detected")
            for pattern in self.risk_patterns:
                lines.append(f"- **{pattern['name']}**: {pattern['description']}")
            lines.append("")

        if self.top_features:
            lines.append("## Top Contributing Features")
            lines.append("")
            lines.append("| Feature | Value | Normal Mean | Z-Score | Category |")
            lines.append("|---------|-------|-------------|---------|----------|")
            for f in self.top_features[:10]:
                lines.append(
                    f"| {f.description} | {f.feature_value:.2f} | "
                    f"{f.normal_mean:.2f} | {f.z_score:+.2f} | {f.category} |"
                )
            lines.append("")

        if self.category_breakdown:
            lines.append("## Anomaly by Category")
            for category, score in sorted(self.category_breakdown.items(), key=lambda x: -x[1]):
                bar = '#' * int(score * 20)
                lines.append(f"- {category}: {score:.2%} {bar}")
            lines.append("")

        if self.similar_normal_tenders:
            lines.append("## Similar Normal Tenders")
            for tender in self.similar_normal_tenders[:3]:
                lines.append(f"- **{tender.tender_id}** (distance: {tender.distance:.3f})")
                for feature, (anomaly_val, normal_val) in list(tender.key_differences.items())[:3]:
                    lines.append(f"  - {feature}: {anomaly_val:.2f} vs {normal_val:.2f}")
            lines.append("")

        if self.recommendations:
            lines.append("## Recommended Actions")
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class AnomalyExplainer:
    """
    Generates interpretable explanations for anomaly detection results.

    This class takes anomaly scores and feature values and produces:
    1. Feature-level contribution analysis
    2. Comparison with similar normal tenders
    3. Natural language explanations
    4. Recommended investigation actions

    Usage:
        explainer = AnomalyExplainer()
        explainer.fit(X_normal, tender_ids_normal, feature_names)
        explanation = explainer.explain(tender_id, features, anomaly_score)
    """

    def __init__(
        self,
        n_neighbors: int = 10,
        top_features: int = 15,
        similar_tenders: int = 5
    ):
        """
        Initialize explainer.

        Args:
            n_neighbors: Number of neighbors for similar tender search
            top_features: Number of top contributing features to show
            similar_tenders: Number of similar normal tenders to find
        """
        self.n_neighbors = n_neighbors
        self.top_features_count = top_features
        self.similar_tenders_count = similar_tenders

        # Will be set during fit
        self.scaler = StandardScaler()
        self.nn_model = NearestNeighbors(n_neighbors=n_neighbors, metric='euclidean')
        self.feature_names: Optional[List[str]] = None
        self.normal_mean: Optional[np.ndarray] = None
        self.normal_std: Optional[np.ndarray] = None
        self.X_normal: Optional[np.ndarray] = None
        self.tender_ids_normal: Optional[List[str]] = None
        self.is_fitted = False

        logger.info("AnomalyExplainer initialized")

    def fit(
        self,
        X_normal: np.ndarray,
        tender_ids: List[str],
        feature_names: List[str]
    ) -> 'AnomalyExplainer':
        """
        Fit the explainer on normal tender data.

        Args:
            X_normal: Feature matrix of normal tenders (n_samples, n_features)
            tender_ids: List of tender IDs corresponding to rows in X_normal
            feature_names: Names of features

        Returns:
            self (fitted explainer)
        """
        logger.info(f"Fitting AnomalyExplainer on {X_normal.shape[0]} normal samples")

        self.feature_names = feature_names
        self.tender_ids_normal = tender_ids

        # Store normal data statistics
        self.normal_mean = np.mean(X_normal, axis=0)
        self.normal_std = np.std(X_normal, axis=0) + 1e-10  # Avoid division by zero

        # Fit scaler and nearest neighbors
        X_scaled = self.scaler.fit_transform(X_normal)
        self.X_normal = X_normal
        self.nn_model.fit(X_scaled)

        self.is_fitted = True
        return self

    def explain(
        self,
        tender_id: str,
        features: np.ndarray,
        anomaly_score: float,
        feature_contributions: Optional[Dict[str, float]] = None
    ) -> AnomalyExplanation:
        """
        Generate explanation for an anomalous tender.

        Args:
            tender_id: The tender identifier
            features: Feature vector (1D array)
            anomaly_score: The anomaly score from the detector
            feature_contributions: Optional pre-computed feature contributions

        Returns:
            AnomalyExplanation with full analysis
        """
        if not self.is_fitted:
            raise RuntimeError("Explainer not fitted. Call fit() first.")

        features = features.flatten()

        # 1. Analyze individual features
        top_features = self._analyze_features(features, feature_contributions)

        # 2. Calculate category breakdown
        category_breakdown = self._calculate_category_breakdown(features, top_features)

        # 3. Find similar normal tenders
        similar_tenders = self._find_similar_tenders(features)

        # 4. Identify risk patterns
        risk_patterns = self._identify_risk_patterns(features)

        # 5. Generate natural language summary
        summary = self._generate_summary(
            anomaly_score, top_features, risk_patterns, category_breakdown
        )

        # 6. Generate recommendations
        recommendations = self._generate_recommendations(
            anomaly_score, risk_patterns, top_features
        )

        return AnomalyExplanation(
            tender_id=tender_id,
            anomaly_score=anomaly_score,
            summary=summary,
            risk_patterns=risk_patterns,
            top_features=top_features,
            category_breakdown=category_breakdown,
            similar_normal_tenders=similar_tenders,
            recommendations=recommendations
        )

    def _analyze_features(
        self,
        features: np.ndarray,
        contributions: Optional[Dict[str, float]] = None
    ) -> List[FeatureAnomaly]:
        """Analyze individual features for anomalies"""
        anomalies = []

        for i, name in enumerate(self.feature_names):
            value = features[i]
            mean = self.normal_mean[i]
            std = self.normal_std[i]
            z_score = (value - mean) / std

            # Get contribution from provided or calculate
            if contributions and name in contributions:
                contribution = contributions[name]
            else:
                contribution = abs(z_score) / 10  # Normalize roughly to [0, 1]

            # Get description and category
            description = FEATURE_DESCRIPTIONS.get(name, name)
            category = self._get_feature_category(name)

            anomalies.append(FeatureAnomaly(
                feature_name=name,
                feature_value=value,
                normal_mean=mean,
                normal_std=std,
                z_score=z_score,
                contribution=contribution,
                description=description,
                category=category
            ))

        # Sort by contribution and return top N
        anomalies.sort(key=lambda x: -x.contribution)
        return anomalies[:self.top_features_count]

    def _get_feature_category(self, feature_name: str) -> str:
        """Get the category for a feature"""
        for category, features in FEATURE_CATEGORIES.items():
            if feature_name in features:
                return category
        return 'other'

    def _calculate_category_breakdown(
        self,
        features: np.ndarray,
        top_features: List[FeatureAnomaly]
    ) -> Dict[str, float]:
        """Calculate anomaly contribution by category"""
        category_scores = {cat: 0.0 for cat in FEATURE_CATEGORIES.keys()}

        for feature in top_features:
            if feature.category in category_scores:
                category_scores[feature.category] += feature.contribution

        # Normalize
        total = sum(category_scores.values())
        if total > 0:
            category_scores = {k: v / total for k, v in category_scores.items()}

        return category_scores

    def _find_similar_tenders(self, features: np.ndarray) -> List[SimilarTender]:
        """Find similar normal tenders for comparison"""
        features_scaled = self.scaler.transform(features.reshape(1, -1))

        # Find nearest neighbors
        distances, indices = self.nn_model.kneighbors(features_scaled)

        similar = []
        for dist, idx in zip(distances[0], indices[0]):
            normal_features = self.X_normal[idx]
            tender_id = self.tender_ids_normal[idx]

            # Calculate key differences
            differences = {}
            for i, name in enumerate(self.feature_names):
                anomaly_val = features[i]
                normal_val = normal_features[i]

                # Check if significantly different
                if self.normal_std[i] > 0:
                    diff_z = abs(anomaly_val - normal_val) / self.normal_std[i]
                    if diff_z > 1.5:  # More than 1.5 std different
                        differences[name] = (anomaly_val, normal_val)

            # Keep top 5 differences
            sorted_diffs = sorted(
                differences.items(),
                key=lambda x: abs(x[1][0] - x[1][1]),
                reverse=True
            )[:5]

            similar.append(SimilarTender(
                tender_id=tender_id,
                distance=float(dist),
                key_differences=dict(sorted_diffs)
            ))

        return similar[:self.similar_tenders_count]

    def _identify_risk_patterns(self, features: np.ndarray) -> List[Dict[str, Any]]:
        """Identify known risk patterns in features"""
        patterns = []

        feature_dict = {name: features[i] for i, name in enumerate(self.feature_names)}

        for pattern_id, pattern_info in RISK_PATTERNS.items():
            triggers = pattern_info['triggers']
            template = pattern_info['template']

            # Check if all triggers are met
            all_met = True
            for feature_name, threshold in triggers:
                if feature_name not in feature_dict:
                    all_met = False
                    break

                value = feature_dict[feature_name]

                # For binary features, check exact match
                # For continuous features, check threshold
                if threshold == 1.0 and value != 1.0:
                    all_met = False
                    break
                elif threshold < 1.0 and value < threshold:
                    all_met = False
                    break

            if all_met:
                patterns.append({
                    'id': pattern_id,
                    'name': pattern_id.replace('_', ' ').title(),
                    'description': template,
                    'severity': self._get_pattern_severity(pattern_id)
                })

        # Sort by severity
        patterns.sort(key=lambda x: -x['severity'])
        return patterns

    def _get_pattern_severity(self, pattern_id: str) -> float:
        """Get severity score for a risk pattern (0-1)"""
        severity_map = {
            'all_related_bidders': 1.0,
            'bid_rigging_low_variance': 0.95,
            'bid_rigging_low_variance_moderate': 0.8,
            'price_exact_match': 0.9,
            'dominant_supplier': 0.85,
            'high_win_rate': 0.8,
            'single_bidder_concern': 0.7,
            'related_bidders': 0.75,
            'very_short_deadline': 0.65,
            'late_amendment': 0.6,
            'high_disqualification': 0.6,
            'bidder_clustering': 0.7,
            'short_deadline': 0.5,
            'winner_not_lowest': 0.4,
            'friday_publication': 0.3,
            'weekend_publication': 0.4,
            'year_end_rush': 0.35,
            'new_supplier_high_value': 0.5,
            'institution_single_bidder_pattern': 0.6,
            'low_bidder_count': 0.45,
            'price_deviation_high': 0.5
        }
        return severity_map.get(pattern_id, 0.5)

    def _generate_summary(
        self,
        anomaly_score: float,
        top_features: List[FeatureAnomaly],
        risk_patterns: List[Dict[str, Any]],
        category_breakdown: Dict[str, float]
    ) -> str:
        """Generate natural language summary"""
        # Determine severity level
        if anomaly_score >= 0.8:
            severity = "highly anomalous"
            action = "requires immediate investigation"
        elif anomaly_score >= 0.6:
            severity = "moderately anomalous"
            action = "warrants detailed review"
        elif anomaly_score >= 0.4:
            severity = "mildly anomalous"
            action = "may benefit from additional scrutiny"
        else:
            severity = "somewhat unusual"
            action = "shows minor deviations from typical patterns"

        # Start summary
        summary_parts = [
            f"This tender is {severity} (score: {anomaly_score:.0%}) and {action}."
        ]

        # Add risk patterns if present
        if risk_patterns:
            high_severity = [p for p in risk_patterns if p['severity'] >= 0.7]
            if high_severity:
                pattern_names = [p['name'] for p in high_severity[:3]]
                summary_parts.append(
                    f"Key concerns include: {', '.join(pattern_names)}."
                )

        # Add top category
        if category_breakdown:
            top_category = max(category_breakdown.items(), key=lambda x: x[1])
            if top_category[1] > 0.3:
                summary_parts.append(
                    f"The primary anomaly category is {top_category[0]} "
                    f"({top_category[1]:.0%} of total anomaly)."
                )

        # Add top feature insight
        if top_features:
            top_feat = top_features[0]
            direction = "higher" if top_feat.z_score > 0 else "lower"
            summary_parts.append(
                f"The most unusual feature is {top_feat.description}, which is "
                f"significantly {direction} than normal (z-score: {top_feat.z_score:+.1f})."
            )

        return " ".join(summary_parts)

    def _generate_recommendations(
        self,
        anomaly_score: float,
        risk_patterns: List[Dict[str, Any]],
        top_features: List[FeatureAnomaly]
    ) -> List[str]:
        """Generate recommended investigation actions"""
        recommendations = []

        # Score-based recommendations
        if anomaly_score >= 0.8:
            recommendations.append(
                "Prioritize this tender for manual review by procurement auditors."
            )

        # Pattern-specific recommendations
        pattern_ids = {p['id'] for p in risk_patterns}

        if 'single_bidder_concern' in pattern_ids:
            recommendations.append(
                "Review tender specifications for overly restrictive requirements "
                "that may have limited competition."
            )

        if 'bid_rigging_low_variance' in pattern_ids or 'bid_rigging_low_variance_moderate' in pattern_ids:
            recommendations.append(
                "Analyze bid submission patterns and bidder relationships for "
                "signs of price coordination or bid rotation."
            )

        if 'dominant_supplier' in pattern_ids or 'high_win_rate' in pattern_ids:
            recommendations.append(
                "Review the institution's procurement history with this supplier "
                "for patterns of preferential treatment."
            )

        if 'related_bidders' in pattern_ids or 'all_related_bidders' in pattern_ids:
            recommendations.append(
                "Investigate corporate relationships between bidders to confirm "
                "whether they are independent entities."
            )

        if 'price_exact_match' in pattern_ids:
            recommendations.append(
                "Examine how the price estimate was developed and who had "
                "access to this information."
            )

        if 'late_amendment' in pattern_ids or 'very_short_deadline' in pattern_ids:
            recommendations.append(
                "Review amendment history and deadline timeline to assess "
                "whether all bidders had fair notice."
            )

        if 'bidder_clustering' in pattern_ids:
            recommendations.append(
                "Conduct market analysis to determine if bidder clustering "
                "reflects legitimate industry structure or coordination."
            )

        # Feature-based recommendations
        competition_features = [f for f in top_features if f.category == 'competition']
        if competition_features:
            recommendations.append(
                "Consider market outreach to understand barriers to participation "
                "in this procurement category."
            )

        # General recommendations
        if not recommendations:
            recommendations.append(
                "Document findings and monitor future tenders from this "
                "institution for similar patterns."
            )

        recommendations.append(
            "Cross-reference with any complaints, appeals, or media reports "
            "related to this tender or institution."
        )

        return recommendations[:5]  # Limit to 5 recommendations

    def explain_batch(
        self,
        tender_ids: List[str],
        features: np.ndarray,
        anomaly_scores: np.ndarray,
        feature_contributions: Optional[List[Dict[str, float]]] = None
    ) -> List[AnomalyExplanation]:
        """
        Generate explanations for multiple tenders.

        Args:
            tender_ids: List of tender IDs
            features: Feature matrix (n_samples, n_features)
            anomaly_scores: Array of anomaly scores
            feature_contributions: Optional list of contribution dicts

        Returns:
            List of AnomalyExplanation objects
        """
        explanations = []

        for i, tender_id in enumerate(tender_ids):
            contrib = feature_contributions[i] if feature_contributions else None
            explanation = self.explain(
                tender_id=tender_id,
                features=features[i],
                anomaly_score=anomaly_scores[i],
                feature_contributions=contrib
            )
            explanations.append(explanation)

        return explanations


def create_risk_report(
    explanations: List[AnomalyExplanation],
    title: str = "Anomaly Detection Risk Report"
) -> str:
    """
    Create a comprehensive risk report from multiple explanations.

    Args:
        explanations: List of explanations to include
        title: Report title

    Returns:
        Markdown formatted report
    """
    lines = [
        f"# {title}",
        f"",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"## Overview",
        f"",
        f"Total tenders analyzed: {len(explanations)}",
        ""
    ]

    # Categorize by risk level
    high_risk = [e for e in explanations if e.anomaly_score >= 0.7]
    medium_risk = [e for e in explanations if 0.4 <= e.anomaly_score < 0.7]
    low_risk = [e for e in explanations if e.anomaly_score < 0.4]

    lines.append(f"- High risk (>70%): {len(high_risk)} tenders")
    lines.append(f"- Medium risk (40-70%): {len(medium_risk)} tenders")
    lines.append(f"- Low risk (<40%): {len(low_risk)} tenders")
    lines.append("")

    # Pattern frequency
    pattern_counts = {}
    for exp in explanations:
        for pattern in exp.risk_patterns:
            pattern_id = pattern['id']
            pattern_counts[pattern_id] = pattern_counts.get(pattern_id, 0) + 1

    if pattern_counts:
        lines.append("## Most Common Risk Patterns")
        lines.append("")
        for pattern_id, count in sorted(pattern_counts.items(), key=lambda x: -x[1])[:10]:
            pattern_name = pattern_id.replace('_', ' ').title()
            lines.append(f"- {pattern_name}: {count} tenders ({count/len(explanations)*100:.1f}%)")
        lines.append("")

    # High risk details
    if high_risk:
        lines.append("## High Risk Tenders")
        lines.append("")
        for exp in sorted(high_risk, key=lambda x: -x.anomaly_score)[:20]:
            lines.append(f"### {exp.tender_id} (Score: {exp.anomaly_score:.0%})")
            lines.append("")
            lines.append(exp.summary)
            lines.append("")
            if exp.risk_patterns:
                lines.append("**Risk Patterns:**")
                for pattern in exp.risk_patterns[:3]:
                    lines.append(f"- {pattern['name']}")
            lines.append("")

    return "\n".join(lines)
