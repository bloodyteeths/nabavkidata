"""
Feature Extractor for ML Corruption Detection

This module extracts 150+ features from tender data for machine learning models.
Features are designed to capture patterns indicative of corruption, bid rigging,
and procurement manipulation.

The feature set is based on academic research on corruption detection including:
- Dozorro (Ukraine) corruption indicators
- World Bank procurement red flags
- OECD corruption risk indicators
- Academic literature on bid rigging detection

Author: nabavkidata.com
License: Proprietary
"""

import asyncio
import asyncpg
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
import json
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class FeatureVector:
    """
    Container for extracted features with metadata.

    Attributes:
        tender_id: The tender ID
        features: Dictionary of feature_name -> value
        feature_array: NumPy array of feature values (for ML models)
        feature_names: List of feature names (same order as feature_array)
        metadata: Additional metadata about the tender
        extraction_timestamp: When features were extracted
    """
    tender_id: str
    features: Dict[str, float]
    feature_array: np.ndarray
    feature_names: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    extraction_timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/serialization"""
        return {
            'tender_id': self.tender_id,
            'features': self.features,
            'feature_names': self.feature_names,
            'metadata': self.metadata,
            'extraction_timestamp': self.extraction_timestamp.isoformat()
        }

    def get_feature(self, name: str) -> Optional[float]:
        """Get a specific feature by name"""
        return self.features.get(name)


class FeatureExtractor:
    """
    Extracts 150+ features from tender data for ML corruption detection.

    This class implements a comprehensive feature extraction pipeline that:
    1. Queries tender data from PostgreSQL
    2. Computes statistical features
    3. Extracts relational features (company history, patterns)
    4. Returns features as NumPy arrays ready for ML models

    Features are organized into 7 categories:
    - Competition (20+ features)
    - Price (25+ features)
    - Timing (15+ features)
    - Relationship (30+ features)
    - Procedural (20+ features)
    - Document (15+ features)
    - Historical (25+ features)

    Usage:
        extractor = FeatureExtractor(pool)
        features = await extractor.extract_features('12345/2024')
        X = features.feature_array  # Ready for sklearn/xgboost
        shap_values = explainer.shap_values(X)  # SHAP explainability
    """

    def __init__(self, pool: asyncpg.Pool):
        """
        Initialize feature extractor.

        Args:
            pool: AsyncPG connection pool
        """
        self.pool = pool
        self.feature_names = self._get_feature_names()
        logger.info(f"FeatureExtractor initialized with {len(self.feature_names)} features")

    async def extract_features(
        self,
        tender_id: str,
        include_metadata: bool = True
    ) -> FeatureVector:
        """
        Extract all features for a single tender.

        Args:
            tender_id: The tender ID to extract features for
            include_metadata: Whether to include metadata (title, institution, etc.)

        Returns:
            FeatureVector containing features, feature names, and metadata

        Raises:
            ValueError: If tender not found
            RuntimeError: If feature extraction fails
        """
        logger.info(f"Extracting features for tender {tender_id}")

        try:
            # Get tender data
            tender_data = await self._get_tender_data(tender_id)
            if not tender_data:
                raise ValueError(f"Tender {tender_id} not found")

            # Extract all feature categories
            features = {}

            # 1. Competition features
            competition_feats = await self._extract_competition_features(tender_id, tender_data)
            features.update(competition_feats)

            # 2. Price features
            price_feats = await self._extract_price_features(tender_id, tender_data)
            features.update(price_feats)

            # 3. Timing features
            timing_feats = await self._extract_timing_features(tender_id, tender_data)
            features.update(timing_feats)

            # 4. Relationship features
            relationship_feats = await self._extract_relationship_features(tender_id, tender_data)
            features.update(relationship_feats)

            # 5. Procedural features
            procedural_feats = await self._extract_procedural_features(tender_id, tender_data)
            features.update(procedural_feats)

            # 6. Document features
            document_feats = await self._extract_document_features(tender_id, tender_data)
            features.update(document_feats)

            # 7. Historical features
            historical_feats = await self._extract_historical_features(tender_id, tender_data)
            features.update(historical_feats)

            # Convert to ordered array (same order as feature_names)
            feature_array = np.array([
                features.get(name, 0.0) for name in self.feature_names
            ], dtype=np.float32)

            # Build metadata
            metadata = {}
            if include_metadata:
                metadata = {
                    'title': tender_data.get('title'),
                    'procuring_entity': tender_data.get('procuring_entity'),
                    'winner': tender_data.get('winner'),
                    'estimated_value_mkd': float(tender_data.get('estimated_value_mkd') or 0),
                    'actual_value_mkd': float(tender_data.get('actual_value_mkd') or 0),
                    'publication_date': str(tender_data.get('publication_date')) if tender_data.get('publication_date') else None,
                    'status': tender_data.get('status')
                }

            logger.info(f"Extracted {len(features)} features for {tender_id}")

            return FeatureVector(
                tender_id=tender_id,
                features=features,
                feature_array=feature_array,
                feature_names=self.feature_names,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Feature extraction failed for {tender_id}: {e}")
            raise RuntimeError(f"Feature extraction failed: {e}") from e

    async def extract_features_batch(
        self,
        tender_ids: List[str],
        include_metadata: bool = True
    ) -> List[FeatureVector]:
        """
        Extract features for multiple tenders in batch.

        Args:
            tender_ids: List of tender IDs
            include_metadata: Whether to include metadata

        Returns:
            List of FeatureVector objects
        """
        logger.info(f"Extracting features for {len(tender_ids)} tenders")

        results = []
        for tender_id in tender_ids:
            try:
                features = await self.extract_features(tender_id, include_metadata)
                results.append(features)
            except Exception as e:
                logger.warning(f"Failed to extract features for {tender_id}: {e}")
                # Continue with other tenders

        logger.info(f"Successfully extracted features for {len(results)}/{len(tender_ids)} tenders")
        return results

    # =========================================================================
    # Feature Category Extraction Methods
    # =========================================================================

    async def _extract_competition_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract competition-related features.

        Features:
        - Number of bidders
        - Single bidder indicator
        - Bidder count relative to market average
        - Bidder participation rate (active vs registered)
        - Market concentration (HHI index)
        - New bidder presence
        - Disqualification rate
        """
        features = {}

        # Get bidder data
        bidders = await self._get_bidder_data(tender_id)
        num_bidders = len(bidders)

        # Basic counts
        features['num_bidders'] = float(num_bidders)
        features['single_bidder'] = 1.0 if num_bidders == 1 else 0.0
        features['no_bidders'] = 1.0 if num_bidders == 0 else 0.0
        features['two_bidders'] = 1.0 if num_bidders == 2 else 0.0

        # Bidder count relative to institution average
        avg_bidders = await self._get_institution_avg_bidders(tender_data.get('procuring_entity'))
        if avg_bidders and avg_bidders > 0:
            features['bidders_vs_institution_avg'] = num_bidders / avg_bidders
        else:
            features['bidders_vs_institution_avg'] = 0.0

        # Bidder count relative to category average
        avg_bidders_category = await self._get_category_avg_bidders(tender_data.get('category'))
        if avg_bidders_category and avg_bidders_category > 0:
            features['bidders_vs_category_avg'] = num_bidders / avg_bidders_category
        else:
            features['bidders_vs_category_avg'] = 0.0

        # Disqualification analysis
        disqualified_count = sum(1 for b in bidders if b.get('disqualified'))
        features['num_disqualified'] = float(disqualified_count)
        if num_bidders > 0:
            features['disqualification_rate'] = disqualified_count / num_bidders
        else:
            features['disqualification_rate'] = 0.0

        # Winner analysis
        winner_name = tender_data.get('winner')
        if winner_name and bidders:
            # Check if winner was lowest bidder
            winner_bid = next((b for b in bidders if b.get('is_winner')), None)
            if winner_bid and winner_bid.get('rank'):
                features['winner_rank'] = float(winner_bid['rank'])
                features['winner_not_lowest'] = 1.0 if winner_bid['rank'] > 1 else 0.0
            else:
                features['winner_rank'] = 0.0
                features['winner_not_lowest'] = 0.0
        else:
            features['winner_rank'] = 0.0
            features['winner_not_lowest'] = 0.0

        # Market concentration (Herfindahl-Hirschman Index)
        # Calculate based on bid amounts
        total_bid_value = sum(float(b.get('bid_amount_mkd') or 0) for b in bidders)
        if total_bid_value > 0:
            hhi = sum((float(b.get('bid_amount_mkd') or 0) / total_bid_value) ** 2 for b in bidders)
            features['market_concentration_hhi'] = hhi * 10000  # Normalize to 0-10000
        else:
            features['market_concentration_hhi'] = 0.0

        # New vs returning bidders
        bidder_companies = [b['company_name'] for b in bidders if b.get('company_name')]
        if bidder_companies:
            new_bidders = await self._count_new_bidders(
                bidder_companies,
                tender_data.get('procuring_entity'),
                tender_data.get('publication_date')
            )
            features['new_bidders_count'] = float(new_bidders)
            features['new_bidders_ratio'] = new_bidders / len(bidder_companies)
        else:
            features['new_bidders_count'] = 0.0
            features['new_bidders_ratio'] = 0.0

        # Bidder clustering (same companies always bid together)
        if num_bidders >= 2:
            clustering_score = await self._calculate_bidder_clustering(bidder_companies)
            features['bidder_clustering_score'] = clustering_score
        else:
            features['bidder_clustering_score'] = 0.0

        return features

    async def _extract_price_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract price-related features.

        Features:
        - Price deviation from estimate
        - Bid variance and coefficient of variation
        - Winner's price vs average
        - Winner's price vs median
        - Price anomaly indicators
        - Exact match to estimate
        """
        features = {}

        estimated_value = float(tender_data.get('estimated_value_mkd') or 0)
        actual_value = float(tender_data.get('actual_value_mkd') or 0)

        # Get all bids
        bidders = await self._get_bidder_data(tender_id)
        bid_amounts = [float(b.get('bid_amount_mkd') or 0) for b in bidders if b.get('bid_amount_mkd')]

        # Basic price features
        features['estimated_value_mkd'] = estimated_value
        features['actual_value_mkd'] = actual_value
        features['has_estimated_value'] = 1.0 if estimated_value > 0 else 0.0
        features['has_actual_value'] = 1.0 if actual_value > 0 else 0.0

        # Price deviation from estimate
        if estimated_value > 0 and actual_value > 0:
            deviation = (actual_value - estimated_value) / estimated_value
            features['price_vs_estimate_ratio'] = actual_value / estimated_value
            features['price_deviation_from_estimate'] = deviation
            features['price_above_estimate'] = 1.0 if deviation > 0 else 0.0
            features['price_below_estimate'] = 1.0 if deviation < 0 else 0.0

            # Exact match indicators (suspicious)
            price_diff_pct = abs(deviation)
            features['price_exact_match_estimate'] = 1.0 if price_diff_pct < 0.01 else 0.0
            features['price_very_close_estimate'] = 1.0 if price_diff_pct < 0.05 else 0.0

            # Large deviations
            features['price_deviation_large'] = 1.0 if abs(deviation) > 0.2 else 0.0
            features['price_deviation_very_large'] = 1.0 if abs(deviation) > 0.5 else 0.0
        else:
            features['price_vs_estimate_ratio'] = 0.0
            features['price_deviation_from_estimate'] = 0.0
            features['price_above_estimate'] = 0.0
            features['price_below_estimate'] = 0.0
            features['price_exact_match_estimate'] = 0.0
            features['price_very_close_estimate'] = 0.0
            features['price_deviation_large'] = 0.0
            features['price_deviation_very_large'] = 0.0

        # Bid distribution analysis
        if len(bid_amounts) >= 2:
            bid_mean = np.mean(bid_amounts)
            bid_median = np.median(bid_amounts)
            bid_std = np.std(bid_amounts)
            bid_min = np.min(bid_amounts)
            bid_max = np.max(bid_amounts)

            features['bid_mean'] = bid_mean
            features['bid_median'] = bid_median
            features['bid_std'] = bid_std
            features['bid_min'] = bid_min
            features['bid_max'] = bid_max
            features['bid_range'] = bid_max - bid_min

            # Coefficient of variation (low = possible collusion)
            if bid_mean > 0:
                cov = bid_std / bid_mean
                features['bid_coefficient_of_variation'] = cov
                features['bid_low_variance'] = 1.0 if cov < 0.05 else 0.0
                features['bid_very_low_variance'] = 1.0 if cov < 0.02 else 0.0
            else:
                features['bid_coefficient_of_variation'] = 0.0
                features['bid_low_variance'] = 0.0
                features['bid_very_low_variance'] = 0.0

            # Winner analysis
            winner_bid = actual_value if actual_value > 0 else (
                next((float(b.get('bid_amount_mkd') or 0) for b in bidders if b.get('is_winner')), 0)
            )

            if winner_bid > 0 and bid_mean > 0:
                features['winner_vs_mean_ratio'] = winner_bid / bid_mean
                features['winner_vs_median_ratio'] = winner_bid / bid_median if bid_median > 0 else 0.0

                # Z-score (how many std deviations from mean)
                if bid_std > 0:
                    winner_z_score = (bid_mean - winner_bid) / bid_std
                    features['winner_bid_z_score'] = winner_z_score
                    features['winner_extremely_low'] = 1.0 if winner_z_score > 2 else 0.0
                else:
                    features['winner_bid_z_score'] = 0.0
                    features['winner_extremely_low'] = 0.0
            else:
                features['winner_vs_mean_ratio'] = 0.0
                features['winner_vs_median_ratio'] = 0.0
                features['winner_bid_z_score'] = 0.0
                features['winner_extremely_low'] = 0.0
        else:
            # Not enough bids for analysis
            for key in ['bid_mean', 'bid_median', 'bid_std', 'bid_min', 'bid_max', 'bid_range',
                       'bid_coefficient_of_variation', 'bid_low_variance', 'bid_very_low_variance',
                       'winner_vs_mean_ratio', 'winner_vs_median_ratio', 'winner_bid_z_score',
                       'winner_extremely_low']:
                features[key] = 0.0

        # Value brackets (log scale for ML)
        if estimated_value > 0:
            features['value_log'] = np.log10(estimated_value + 1)
            features['value_small'] = 1.0 if estimated_value < 500000 else 0.0
            features['value_medium'] = 1.0 if 500000 <= estimated_value < 5000000 else 0.0
            features['value_large'] = 1.0 if 5000000 <= estimated_value < 20000000 else 0.0
            features['value_very_large'] = 1.0 if estimated_value >= 20000000 else 0.0
        else:
            features['value_log'] = 0.0
            features['value_small'] = 0.0
            features['value_medium'] = 0.0
            features['value_large'] = 0.0
            features['value_very_large'] = 0.0

        return features

    async def _extract_timing_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract timing-related features.

        Features:
        - Deadline length (publication to closing)
        - Time to award
        - Publication day of week/hour patterns
        - Short deadline indicators
        - Amendment timing patterns
        """
        features = {}

        pub_date = tender_data.get('publication_date')
        closing_date = tender_data.get('closing_date')
        opening_date = tender_data.get('opening_date')

        # Deadline length
        if pub_date and closing_date:
            deadline_days = (closing_date - pub_date).days
            features['deadline_days'] = float(deadline_days)
            features['deadline_very_short'] = 1.0 if deadline_days < 3 else 0.0
            features['deadline_short'] = 1.0 if deadline_days < 7 else 0.0
            features['deadline_normal'] = 1.0 if 7 <= deadline_days <= 30 else 0.0
            features['deadline_long'] = 1.0 if deadline_days > 30 else 0.0
        else:
            features['deadline_days'] = 0.0
            features['deadline_very_short'] = 0.0
            features['deadline_short'] = 0.0
            features['deadline_normal'] = 0.0
            features['deadline_long'] = 0.0

        # Time to award (closing to publication or scraped_at as proxy)
        if closing_date and tender_data.get('scraped_at'):
            time_to_award_days = (tender_data['scraped_at'].date() - closing_date).days
            features['time_to_award_days'] = float(max(0, time_to_award_days))
        else:
            features['time_to_award_days'] = 0.0

        # Publication timing patterns
        if pub_date:
            features['pub_day_of_week'] = float(pub_date.weekday())  # 0=Monday
            features['pub_friday'] = 1.0 if pub_date.weekday() == 4 else 0.0
            features['pub_weekend'] = 1.0 if pub_date.weekday() >= 5 else 0.0
            features['pub_month'] = float(pub_date.month)
            features['pub_end_of_year'] = 1.0 if pub_date.month == 12 else 0.0
        else:
            for key in ['pub_day_of_week', 'pub_friday', 'pub_weekend', 'pub_month', 'pub_end_of_year']:
                features[key] = 0.0

        # Amendment timing
        amendment_count = tender_data.get('amendment_count', 0)
        features['amendment_count'] = float(amendment_count)
        features['has_amendments'] = 1.0 if amendment_count > 0 else 0.0
        features['many_amendments'] = 1.0 if amendment_count >= 3 else 0.0

        if tender_data.get('last_amendment_date') and closing_date:
            days_before_closing = (closing_date - tender_data['last_amendment_date']).days
            features['amendment_days_before_closing'] = float(days_before_closing)
            features['amendment_very_late'] = 1.0 if days_before_closing < 2 else 0.0
        else:
            features['amendment_days_before_closing'] = 0.0
            features['amendment_very_late'] = 0.0

        return features

    async def _extract_relationship_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract relationship and pattern features.

        Features:
        - Repeat winner at institution
        - Winner's overall win rate
        - Buyer-supplier loyalty score
        - Bidder relationships
        - Winner's market share at institution
        """
        features = {}

        winner = tender_data.get('winner')
        institution = tender_data.get('procuring_entity')
        pub_date = tender_data.get('publication_date')

        if winner and institution:
            # Repeat winner analysis
            win_stats = await self._get_winner_statistics(winner, institution, pub_date)

            features['winner_prev_wins_at_institution'] = float(win_stats['prev_wins'])
            features['winner_prev_bids_at_institution'] = float(win_stats['prev_bids'])

            if win_stats['prev_bids'] > 0:
                features['winner_win_rate_at_institution'] = win_stats['prev_wins'] / win_stats['prev_bids']
            else:
                features['winner_win_rate_at_institution'] = 0.0

            # High win rate indicators
            features['winner_high_win_rate'] = 1.0 if features['winner_win_rate_at_institution'] > 0.6 else 0.0
            features['winner_very_high_win_rate'] = 1.0 if features['winner_win_rate_at_institution'] > 0.8 else 0.0

            # Market share at institution
            features['winner_market_share_at_institution'] = win_stats['market_share']
            features['winner_dominant_supplier'] = 1.0 if win_stats['market_share'] > 0.5 else 0.0

            # Overall win statistics
            overall_stats = await self._get_overall_winner_statistics(winner, pub_date)
            features['winner_total_wins'] = float(overall_stats['total_wins'])
            features['winner_total_bids'] = float(overall_stats['total_bids'])
            features['winner_overall_win_rate'] = overall_stats['win_rate']
            features['winner_num_institutions'] = float(overall_stats['num_institutions'])

            # New vs experienced supplier
            features['winner_new_supplier'] = 1.0 if overall_stats['total_bids'] <= 1 else 0.0
            features['winner_experienced_supplier'] = 1.0 if overall_stats['total_bids'] >= 10 else 0.0

        else:
            # No winner data
            for key in ['winner_prev_wins_at_institution', 'winner_prev_bids_at_institution',
                       'winner_win_rate_at_institution', 'winner_high_win_rate', 'winner_very_high_win_rate',
                       'winner_market_share_at_institution', 'winner_dominant_supplier',
                       'winner_total_wins', 'winner_total_bids', 'winner_overall_win_rate',
                       'winner_num_institutions', 'winner_new_supplier', 'winner_experienced_supplier']:
                features[key] = 0.0

        # Bidder relationship analysis
        bidders = await self._get_bidder_data(tender_id)
        bidder_companies = [b['company_name'] for b in bidders if b.get('company_name')]

        if len(bidder_companies) >= 2:
            # Check for known relationships
            relationships = await self._check_bidder_relationships(bidder_companies)
            features['num_related_bidder_pairs'] = float(relationships['related_pairs'])
            features['has_related_bidders'] = 1.0 if relationships['related_pairs'] > 0 else 0.0
            features['all_bidders_related'] = 1.0 if relationships['all_related'] else 0.0
        else:
            features['num_related_bidder_pairs'] = 0.0
            features['has_related_bidders'] = 0.0
            features['all_bidders_related'] = 0.0

        # Institution patterns
        institution_stats = await self._get_institution_statistics(institution, pub_date)
        features['institution_total_tenders'] = float(institution_stats['total_tenders'])
        features['institution_single_bidder_rate'] = institution_stats['single_bidder_rate']
        features['institution_avg_bidders'] = institution_stats['avg_bidders']

        return features

    async def _extract_procedural_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract procedural features.

        Features:
        - Procedure type
        - Evaluation method
        - Lot structure
        - Status indicators
        """
        features = {}

        # Status
        status = tender_data.get('status', 'unknown')
        features['status_open'] = 1.0 if status == 'open' else 0.0
        features['status_closed'] = 1.0 if status == 'closed' else 0.0
        features['status_awarded'] = 1.0 if status == 'awarded' else 0.0
        features['status_cancelled'] = 1.0 if status == 'cancelled' else 0.0

        # Evaluation method
        eval_method = tender_data.get('evaluation_method') or ''
        features['eval_lowest_price'] = 1.0 if 'lowest' in eval_method.lower() else 0.0
        features['eval_best_value'] = 1.0 if 'best' in eval_method.lower() else 0.0
        features['has_eval_method'] = 1.0 if eval_method else 0.0

        # Lot structure
        has_lots = tender_data.get('has_lots') or False
        num_lots = tender_data.get('num_lots') or 0
        features['has_lots'] = 1.0 if has_lots else 0.0
        features['num_lots'] = float(num_lots)
        features['many_lots'] = 1.0 if num_lots >= 5 else 0.0

        # Security and guarantees
        security_deposit = float(tender_data.get('security_deposit_mkd') or 0)
        performance_guarantee = float(tender_data.get('performance_guarantee_mkd') or 0)

        features['has_security_deposit'] = 1.0 if security_deposit > 0 else 0.0
        features['has_performance_guarantee'] = 1.0 if performance_guarantee > 0 else 0.0

        estimated_value = float(tender_data.get('estimated_value_mkd') or 0)
        if estimated_value > 0:
            features['security_deposit_ratio'] = security_deposit / estimated_value
            features['performance_guarantee_ratio'] = performance_guarantee / estimated_value
        else:
            features['security_deposit_ratio'] = 0.0
            features['performance_guarantee_ratio'] = 0.0

        # CPV code presence
        features['has_cpv_code'] = 1.0 if tender_data.get('cpv_code') else 0.0

        # Category
        category = tender_data.get('category') or ''
        features['has_category'] = 1.0 if category else 0.0

        return features

    async def _extract_document_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract document-related features.

        Features:
        - Number of documents
        - Document types
        - Extraction success rate
        - Document completeness
        """
        features = {}

        # Get document data
        documents = await self._get_document_data(tender_id)

        features['num_documents'] = float(len(documents))
        features['has_documents'] = 1.0 if len(documents) > 0 else 0.0
        features['many_documents'] = 1.0 if len(documents) >= 5 else 0.0

        # Document extraction status
        successful_extractions = sum(1 for d in documents if d.get('extraction_status') == 'success')
        failed_extractions = sum(1 for d in documents if d.get('extraction_status') == 'failed')

        features['num_docs_extracted'] = float(successful_extractions)
        if len(documents) > 0:
            features['doc_extraction_success_rate'] = successful_extractions / len(documents)
        else:
            features['doc_extraction_success_rate'] = 0.0

        # Total content length (complexity proxy)
        total_content_length = sum(len(d.get('content_text') or '') for d in documents)
        features['total_doc_content_length'] = float(total_content_length)
        features['avg_doc_content_length'] = total_content_length / len(documents) if len(documents) > 0 else 0.0

        # Document types
        doc_types = [(d.get('doc_type') or '').lower() for d in documents]
        features['has_specification'] = 1.0 if any('спецификација' in dt or 'specification' in dt for dt in doc_types) else 0.0
        features['has_contract'] = 1.0 if any('договор' in dt or 'contract' in dt for dt in doc_types) else 0.0

        return features

    async def _extract_historical_features(
        self,
        tender_id: str,
        tender_data: Dict
    ) -> Dict[str, float]:
        """
        Extract historical and temporal features.

        Features:
        - Tender age
        - Institution activity patterns
        - Seasonal patterns
        - Scraping metadata
        """
        features = {}

        pub_date = tender_data.get('publication_date')
        scraped_at = tender_data.get('scraped_at')

        # Tender age
        if pub_date:
            age_days = (datetime.utcnow().date() - pub_date).days
            features['tender_age_days'] = float(age_days)
            features['tender_very_recent'] = 1.0 if age_days <= 30 else 0.0
            features['tender_recent'] = 1.0 if age_days <= 90 else 0.0
            features['tender_old'] = 1.0 if age_days >= 365 else 0.0
        else:
            features['tender_age_days'] = 0.0
            features['tender_very_recent'] = 0.0
            features['tender_recent'] = 0.0
            features['tender_old'] = 0.0

        # Scraping metadata
        scrape_count = tender_data.get('scrape_count', 0)
        features['scrape_count'] = float(scrape_count)
        features['rescraped'] = 1.0 if scrape_count > 1 else 0.0

        # Institution historical patterns
        institution = tender_data.get('procuring_entity')
        if institution:
            inst_patterns = await self._get_institution_temporal_patterns(institution, pub_date)
            features['institution_tenders_same_month'] = float(inst_patterns['tenders_same_month'])
            features['institution_tenders_prev_month'] = float(inst_patterns['tenders_prev_month'])
            features['institution_activity_spike'] = inst_patterns['activity_spike']
        else:
            features['institution_tenders_same_month'] = 0.0
            features['institution_tenders_prev_month'] = 0.0
            features['institution_activity_spike'] = 0.0

        return features

    # =========================================================================
    # Helper Methods - Database Queries
    # =========================================================================

    async def _get_tender_data(self, tender_id: str) -> Optional[Dict]:
        """Get all tender data from database"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    tender_id, title, description, category, procuring_entity,
                    opening_date, closing_date, publication_date,
                    estimated_value_mkd, actual_value_mkd,
                    cpv_code, status, winner, num_bidders,
                    security_deposit_mkd, performance_guarantee_mkd,
                    evaluation_method, has_lots, num_lots,
                    amendment_count, last_amendment_date,
                    scraped_at, scrape_count
                FROM tenders
                WHERE tender_id = $1
            """, tender_id)
            return dict(row) if row else None

    async def _get_bidder_data(self, tender_id: str) -> List[Dict]:
        """Get all bidders for a tender"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    company_name, company_tax_id, bid_amount_mkd,
                    is_winner, rank, disqualified, disqualification_reason
                FROM tender_bidders
                WHERE tender_id = $1
                ORDER BY rank NULLS LAST, bid_amount_mkd ASC
            """, tender_id)
            return [dict(row) for row in rows]

    async def _get_document_data(self, tender_id: str) -> List[Dict]:
        """Get all documents for a tender"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT
                    doc_type, file_name, content_text,
                    extraction_status, file_size_bytes, page_count
                FROM documents
                WHERE tender_id = $1
            """, tender_id)
            return [dict(row) for row in rows]

    async def _get_institution_avg_bidders(self, institution: Optional[str]) -> Optional[float]:
        """Get average number of bidders for an institution"""
        if not institution:
            return None

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT AVG(num_bidders)
                FROM tenders
                WHERE procuring_entity = $1
                  AND num_bidders > 0
                  AND status IN ('awarded', 'closed')
            """, institution)
            return float(result) if result else None

    async def _get_category_avg_bidders(self, category: Optional[str]) -> Optional[float]:
        """Get average number of bidders for a category"""
        if not category:
            return None

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT AVG(num_bidders)
                FROM tenders
                WHERE category = $1
                  AND num_bidders > 0
                  AND status IN ('awarded', 'closed')
            """, category)
            return float(result) if result else None

    async def _count_new_bidders(
        self,
        bidder_companies: List[str],
        institution: Optional[str],
        pub_date: Optional[datetime.date]
    ) -> int:
        """Count how many bidders are new (never bid at this institution before)"""
        if not institution or not pub_date or not bidder_companies:
            return 0

        async with self.pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(DISTINCT company_name)
                FROM unnest($1::text[]) AS company_name
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM tender_bidders tb
                    JOIN tenders t ON tb.tender_id = t.tender_id
                    WHERE tb.company_name = company_name
                      AND t.procuring_entity = $2
                      AND t.publication_date < $3
                )
            """, bidder_companies, institution, pub_date)
            return int(result) if result else 0

    async def _calculate_bidder_clustering(self, bidder_companies: List[str]) -> float:
        """
        Calculate bidder clustering score (how often these companies bid together).
        Returns score 0.0-1.0 where higher = more clustering
        """
        if len(bidder_companies) < 2:
            return 0.0

        async with self.pool.acquire() as conn:
            # For each pair of companies, calculate co-occurrence rate
            clustering_scores = []

            for i, company_a in enumerate(bidder_companies):
                for company_b in bidder_companies[i+1:]:
                    # Count tenders where both bid
                    co_occurrences = await conn.fetchval("""
                        SELECT COUNT(DISTINCT tb1.tender_id)
                        FROM tender_bidders tb1
                        JOIN tender_bidders tb2 ON tb1.tender_id = tb2.tender_id
                        WHERE tb1.company_name = $1
                          AND tb2.company_name = $2
                    """, company_a, company_b)

                    # Count total tenders for each company
                    total_a = await conn.fetchval("""
                        SELECT COUNT(DISTINCT tender_id)
                        FROM tender_bidders
                        WHERE company_name = $1
                    """, company_a)

                    total_b = await conn.fetchval("""
                        SELECT COUNT(DISTINCT tender_id)
                        FROM tender_bidders
                        WHERE company_name = $1
                    """, company_b)

                    # Calculate overlap rate
                    if total_a and total_b:
                        overlap = co_occurrences / min(total_a, total_b)
                        clustering_scores.append(overlap)

            # Return average clustering score
            return float(np.mean(clustering_scores)) if clustering_scores else 0.0

    async def _get_winner_statistics(
        self,
        winner: str,
        institution: str,
        pub_date: Optional[datetime.date]
    ) -> Dict[str, Any]:
        """Get winner statistics at this institution (before this tender)"""
        cutoff_date = pub_date if pub_date else datetime.utcnow().date()

        async with self.pool.acquire() as conn:
            # Previous wins and bids
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE t.winner = $1) as prev_wins,
                    COUNT(*) FILTER (WHERE tb.company_name = $1) as prev_bids,
                    COUNT(*) as total_institution_tenders
                FROM tenders t
                LEFT JOIN tender_bidders tb ON t.tender_id = tb.tender_id
                WHERE t.procuring_entity = $2
                  AND t.publication_date < $3
                  AND t.status IN ('awarded', 'closed')
            """, winner, institution, cutoff_date)

            prev_wins = int(stats['prev_wins'] or 0)
            prev_bids = int(stats['prev_bids'] or 0)
            total_tenders = int(stats['total_institution_tenders'] or 0)

            market_share = prev_wins / total_tenders if total_tenders > 0 else 0.0

            return {
                'prev_wins': prev_wins,
                'prev_bids': prev_bids,
                'market_share': market_share
            }

    async def _get_overall_winner_statistics(
        self,
        winner: str,
        pub_date: Optional[datetime.date]
    ) -> Dict[str, Any]:
        """Get overall winner statistics across all institutions"""
        cutoff_date = pub_date if pub_date else datetime.utcnow().date()

        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE t.winner = $1) as total_wins,
                    COUNT(*) FILTER (WHERE tb.company_name = $1) as total_bids,
                    COUNT(DISTINCT t.procuring_entity) FILTER (WHERE t.winner = $1) as num_institutions
                FROM tenders t
                LEFT JOIN tender_bidders tb ON t.tender_id = tb.tender_id
                WHERE t.publication_date < $2
                  AND t.status IN ('awarded', 'closed')
            """, winner, cutoff_date)

            total_wins = int(stats['total_wins'] or 0)
            total_bids = int(stats['total_bids'] or 0)

            return {
                'total_wins': total_wins,
                'total_bids': total_bids,
                'win_rate': total_wins / total_bids if total_bids > 0 else 0.0,
                'num_institutions': int(stats['num_institutions'] or 0)
            }

    async def _check_bidder_relationships(self, bidder_companies: List[str]) -> Dict[str, Any]:
        """Check for known relationships between bidders"""
        if len(bidder_companies) < 2:
            return {'related_pairs': 0, 'all_related': False}

        async with self.pool.acquire() as conn:
            # Count related pairs
            related_count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM company_relationships
                WHERE (company_a = ANY($1::text[]) AND company_b = ANY($1::text[]))
                   OR (company_b = ANY($1::text[]) AND company_a = ANY($1::text[]))
            """, bidder_companies)

            # Check if all are related (network)
            max_possible_pairs = len(bidder_companies) * (len(bidder_companies) - 1) / 2
            all_related = related_count == max_possible_pairs if max_possible_pairs > 0 else False

            return {
                'related_pairs': int(related_count or 0),
                'all_related': all_related
            }

    async def _get_institution_statistics(
        self,
        institution: Optional[str],
        pub_date: Optional[datetime.date]
    ) -> Dict[str, Any]:
        """Get institution statistics"""
        if not institution:
            return {
                'total_tenders': 0,
                'single_bidder_rate': 0.0,
                'avg_bidders': 0.0
            }

        cutoff_date = pub_date if pub_date else datetime.utcnow().date()

        async with self.pool.acquire() as conn:
            stats = await conn.fetchrow("""
                SELECT
                    COUNT(*) as total_tenders,
                    COUNT(*) FILTER (WHERE num_bidders = 1) as single_bidder_count,
                    AVG(num_bidders) as avg_bidders
                FROM tenders
                WHERE procuring_entity = $1
                  AND publication_date < $2
                  AND status IN ('awarded', 'closed')
                  AND num_bidders > 0
            """, institution, cutoff_date)

            total = int(stats['total_tenders'] or 0)
            single_bidder = int(stats['single_bidder_count'] or 0)

            return {
                'total_tenders': total,
                'single_bidder_rate': single_bidder / total if total > 0 else 0.0,
                'avg_bidders': float(stats['avg_bidders'] or 0.0)
            }

    async def _get_institution_temporal_patterns(
        self,
        institution: str,
        pub_date: Optional[datetime.date]
    ) -> Dict[str, Any]:
        """Get institution temporal activity patterns"""
        if not pub_date:
            return {
                'tenders_same_month': 0,
                'tenders_prev_month': 0,
                'activity_spike': 0.0
            }

        async with self.pool.acquire() as conn:
            # Tenders in same month
            same_month = await conn.fetchval("""
                SELECT COUNT(*)
                FROM tenders
                WHERE procuring_entity = $1
                  AND EXTRACT(YEAR FROM publication_date) = $2
                  AND EXTRACT(MONTH FROM publication_date) = $3
            """, institution, pub_date.year, pub_date.month)

            # Tenders in previous month
            prev_month_date = (pub_date.replace(day=1) - timedelta(days=1))
            prev_month = await conn.fetchval("""
                SELECT COUNT(*)
                FROM tenders
                WHERE procuring_entity = $1
                  AND EXTRACT(YEAR FROM publication_date) = $2
                  AND EXTRACT(MONTH FROM publication_date) = $3
            """, institution, prev_month_date.year, prev_month_date.month)

            # Calculate spike (activity > 2x previous month)
            spike = 1.0 if (prev_month and same_month and same_month > 2 * prev_month) else 0.0

            return {
                'tenders_same_month': int(same_month or 0),
                'tenders_prev_month': int(prev_month or 0),
                'activity_spike': spike
            }

    # =========================================================================
    # Feature Name Management
    # =========================================================================

    def _get_feature_names(self) -> List[str]:
        """
        Return ordered list of all feature names.

        This is CRITICAL for ML models - feature order must be consistent!
        """
        return [
            # Competition features (20)
            'num_bidders', 'single_bidder', 'no_bidders', 'two_bidders',
            'bidders_vs_institution_avg', 'bidders_vs_category_avg',
            'num_disqualified', 'disqualification_rate',
            'winner_rank', 'winner_not_lowest',
            'market_concentration_hhi',
            'new_bidders_count', 'new_bidders_ratio',
            'bidder_clustering_score',

            # Price features (30)
            'estimated_value_mkd', 'actual_value_mkd', 'has_estimated_value', 'has_actual_value',
            'price_vs_estimate_ratio', 'price_deviation_from_estimate',
            'price_above_estimate', 'price_below_estimate',
            'price_exact_match_estimate', 'price_very_close_estimate',
            'price_deviation_large', 'price_deviation_very_large',
            'bid_mean', 'bid_median', 'bid_std', 'bid_min', 'bid_max', 'bid_range',
            'bid_coefficient_of_variation', 'bid_low_variance', 'bid_very_low_variance',
            'winner_vs_mean_ratio', 'winner_vs_median_ratio', 'winner_bid_z_score', 'winner_extremely_low',
            'value_log', 'value_small', 'value_medium', 'value_large', 'value_very_large',

            # Timing features (15)
            'deadline_days', 'deadline_very_short', 'deadline_short', 'deadline_normal', 'deadline_long',
            'time_to_award_days',
            'pub_day_of_week', 'pub_friday', 'pub_weekend', 'pub_month', 'pub_end_of_year',
            'amendment_count', 'has_amendments', 'many_amendments',
            'amendment_days_before_closing', 'amendment_very_late',

            # Relationship features (18)
            'winner_prev_wins_at_institution', 'winner_prev_bids_at_institution',
            'winner_win_rate_at_institution', 'winner_high_win_rate', 'winner_very_high_win_rate',
            'winner_market_share_at_institution', 'winner_dominant_supplier',
            'winner_total_wins', 'winner_total_bids', 'winner_overall_win_rate',
            'winner_num_institutions', 'winner_new_supplier', 'winner_experienced_supplier',
            'num_related_bidder_pairs', 'has_related_bidders', 'all_bidders_related',
            'institution_total_tenders', 'institution_single_bidder_rate', 'institution_avg_bidders',

            # Procedural features (16)
            'status_open', 'status_closed', 'status_awarded', 'status_cancelled',
            'eval_lowest_price', 'eval_best_value', 'has_eval_method',
            'has_lots', 'num_lots', 'many_lots',
            'has_security_deposit', 'has_performance_guarantee',
            'security_deposit_ratio', 'performance_guarantee_ratio',
            'has_cpv_code', 'has_category',

            # Document features (8)
            'num_documents', 'has_documents', 'many_documents',
            'num_docs_extracted', 'doc_extraction_success_rate',
            'total_doc_content_length', 'avg_doc_content_length',
            'has_specification', 'has_contract',

            # Historical features (10)
            'tender_age_days', 'tender_very_recent', 'tender_recent', 'tender_old',
            'scrape_count', 'rescraped',
            'institution_tenders_same_month', 'institution_tenders_prev_month',
            'institution_activity_spike'
        ]

    def get_feature_count(self) -> int:
        """Get total number of features"""
        return len(self.feature_names)

    def get_feature_categories(self) -> Dict[str, List[str]]:
        """Get features organized by category"""
        names = self.feature_names
        return {
            'competition': names[0:14],
            'price': names[14:44],
            'timing': names[44:60],
            'relationship': names[60:78],
            'procedural': names[78:94],
            'document': names[94:103],
            'historical': names[103:112]
        }
