"""
Ground truth data for corruption detection ML models.

This module contains confirmed corruption cases from Macedonian public procurement
that can be used for:
- Training ML models
- Validating detection algorithms
- Testing red flag indicators
- Benchmarking detection performance
- Creating labeled datasets for supervised learning
"""

from .known_cases import (
    CorruptionCase,
    CONVICTED_CASES,
    INVESTIGATION_CASES,
    SANCTIONED_ENTITIES,
    CORRUPTION_INDICATORS,
    get_all_cases,
    get_all_convicted_cases,
    get_all_investigation_cases,
    get_cases_by_sector,
    get_cases_by_year,
    get_cases_by_institution,
    get_company_names,
    get_individual_names,
    get_keywords_mk,
    get_keywords_en,
    get_total_damage_estimate,
    print_summary,
)

from .create_labeled_dataset import (
    LabeledSample,
    LabeledDatasetCreator,
)

__all__ = [
    # Known cases
    "CorruptionCase",
    "CONVICTED_CASES",
    "INVESTIGATION_CASES",
    "SANCTIONED_ENTITIES",
    "CORRUPTION_INDICATORS",
    "get_all_cases",
    "get_all_convicted_cases",
    "get_all_investigation_cases",
    "get_cases_by_sector",
    "get_cases_by_year",
    "get_cases_by_institution",
    "get_company_names",
    "get_individual_names",
    "get_keywords_mk",
    "get_keywords_en",
    "get_total_damage_estimate",
    "print_summary",
    # Labeled dataset creation
    "LabeledSample",
    "LabeledDatasetCreator",
]
