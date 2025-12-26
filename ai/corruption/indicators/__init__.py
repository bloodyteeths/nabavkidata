"""
Statistical Indicators for Corruption Detection

This package implements 50+ adaptive risk indicators organized into five categories:
1. Competition indicators
2. Price indicators
3. Timing indicators
4. Relationship indicators
5. Procedural indicators

Based on Dozorro's research achieving 81-95% accuracy in corruption detection.
"""

from .dozorro_indicators import (
    Indicator,
    IndicatorResult,
    IndicatorRegistry,
    # Competition indicators
    SingleBidderIndicator,
    LowParticipationIndicator,
    SameBidderSetIndicator,
    BidderDiversityIndicator,
    NewBidderRateIndicator,
    MarketConcentrationIndicator,
    BidderTurnoverIndicator,
    GeographicConcentrationIndicator,
    BidderExperienceIndicator,
    CompetitionTrendIndicator,
    # Price indicators
    PriceDeviationIndicator,
    BidClusteringIndicator,
    CoverBiddingIndicator,
    RoundNumberIndicator,
    PriceFixingIndicator,
    BelowMarketPricingIndicator,
    PriceVarianceIndicator,
    WinnerZScoreIndicator,
    EstimateMatchIndicator,
    PriceSequenceIndicator,
    # Timing indicators
    ShortDeadlineIndicator,
    WeekendPublicationIndicator,
    ElectionCycleIndicator,
    SeasonalPatternIndicator,
    AmendmentTimingIndicator,
    LastMinuteSubmissionIndicator,
    ProcessDurationIndicator,
    PublicationPatternIndicator,
    DeadlineExtensionIndicator,
    SubmissionClusteringIndicator,
    # Relationship indicators
    RepeatWinnerIndicator,
    BuyerLoyaltyIndicator,
    NetworkDensityIndicator,
    CompanyAgeIndicator,
    CrossContractPatternIndicator,
    BidRotationIndicator,
    SharedInfrastructureIndicator,
    OwnershipPatternIndicator,
    GeographicProximityIndicator,
    ContractHistoryIndicator,
    # Procedural indicators
    NonCompetitiveProcedureIndicator,
    LotSplittingIndicator,
    ThresholdAvoidanceIndicator,
    SpecificationChangesIndicator,
    QualificationRequirementsIndicator,
    AmendmentFrequencyIndicator,
    DisqualificationRateIndicator,
    DocumentAccessibilityIndicator,
    AppealRateIndicator,
    ContractModificationIndicator,
)

__all__ = [
    "Indicator",
    "IndicatorResult",
    "IndicatorRegistry",
    # Competition
    "SingleBidderIndicator",
    "LowParticipationIndicator",
    "SameBidderSetIndicator",
    "BidderDiversityIndicator",
    "NewBidderRateIndicator",
    "MarketConcentrationIndicator",
    "BidderTurnoverIndicator",
    "GeographicConcentrationIndicator",
    "BidderExperienceIndicator",
    "CompetitionTrendIndicator",
    # Price
    "PriceDeviationIndicator",
    "BidClusteringIndicator",
    "CoverBiddingIndicator",
    "RoundNumberIndicator",
    "PriceFixingIndicator",
    "BelowMarketPricingIndicator",
    "PriceVarianceIndicator",
    "WinnerZScoreIndicator",
    "EstimateMatchIndicator",
    "PriceSequenceIndicator",
    # Timing
    "ShortDeadlineIndicator",
    "WeekendPublicationIndicator",
    "ElectionCycleIndicator",
    "SeasonalPatternIndicator",
    "AmendmentTimingIndicator",
    "LastMinuteSubmissionIndicator",
    "ProcessDurationIndicator",
    "PublicationPatternIndicator",
    "DeadlineExtensionIndicator",
    "SubmissionClusteringIndicator",
    # Relationship
    "RepeatWinnerIndicator",
    "BuyerLoyaltyIndicator",
    "NetworkDensityIndicator",
    "CompanyAgeIndicator",
    "CrossContractPatternIndicator",
    "BidRotationIndicator",
    "SharedInfrastructureIndicator",
    "OwnershipPatternIndicator",
    "GeographicProximityIndicator",
    "ContractHistoryIndicator",
    # Procedural
    "NonCompetitiveProcedureIndicator",
    "LotSplittingIndicator",
    "ThresholdAvoidanceIndicator",
    "SpecificationChangesIndicator",
    "QualificationRequirementsIndicator",
    "AmendmentFrequencyIndicator",
    "DisqualificationRateIndicator",
    "DocumentAccessibilityIndicator",
    "AppealRateIndicator",
    "ContractModificationIndicator",
]
