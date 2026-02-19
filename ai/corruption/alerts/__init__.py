"""
Corruption Alert Pipeline

Real-time alert system for detecting and notifying users about corruption
risk events in Macedonian public procurement tenders.

Components:
- alert_rules: Declarative alert rule definitions and evaluation logic
- corruption_alerter: Main alerting engine (evaluation, delivery, stats)
- evaluate_triggers: CLI script for cron-based evaluation

Phase 4.4 of the corruption detection system.
"""

from .alert_rules import (
    AlertRule,
    HighRiskScoreRule,
    SingleBidderHighValueRule,
    WatchedEntityRule,
    MultipleRedFlagsRule,
    RepeatPatternRule,
    EscalatingRiskRule,
    AVAILABLE_RULES,
    create_rule,
)
from .corruption_alerter import CorruptionAlerter

__all__ = [
    'AlertRule',
    'HighRiskScoreRule',
    'SingleBidderHighValueRule',
    'WatchedEntityRule',
    'MultipleRedFlagsRule',
    'RepeatPatternRule',
    'EscalatingRiskRule',
    'AVAILABLE_RULES',
    'create_rule',
    'CorruptionAlerter',
]
