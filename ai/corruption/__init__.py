"""
Corruption Detection ML Module

This package contains the machine learning-based corruption detection system
for public procurement tenders in North Macedonia.

Components:
- features: Feature extraction pipeline (150+ features)
- models: ML models for corruption risk prediction
- training: Training pipelines and data preparation
- evaluation: Model evaluation and performance metrics

Author: nabavkidata.com
License: Proprietary
"""

from ai.corruption.features.feature_extractor import FeatureExtractor

__all__ = ['FeatureExtractor']
