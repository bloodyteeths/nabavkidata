"""
Feature Extraction Module

This module extracts 150+ features from tender data for ML-based corruption detection.

Feature Categories:
1. Competition Features - bidder count, participation rates, market concentration
2. Price Features - price deviations, bid variance, estimate accuracy
3. Timing Features - deadline length, publication patterns, amendment timing
4. Relationship Features - repeat winners, buyer-supplier loyalty, bidder clustering
5. Procedural Features - procedure types, amendments, evaluation methods
6. Document Features - specification complexity, document counts
7. Historical Features - company win rates, institution patterns
8. Network Features - company relationships, ownership connections

Author: nabavkidata.com
License: Proprietary
"""

from ai.corruption.features.feature_extractor import FeatureExtractor

__all__ = ['FeatureExtractor']
