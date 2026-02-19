"""
Alert rule types and their evaluation logic.

Each rule class evaluates a tender's data against a specific corruption pattern
and returns alert details when the pattern is detected. Rules are declarative
and configurable through JSON rule_config stored in corruption_alert_subscriptions.

Supported rule types:
  - high_risk_score: Risk score exceeds threshold
  - single_bidder_high_value: Single-bidder tender with high contract value
  - watched_entity: Activity by a watched company or institution
  - multiple_flags: Tender has N+ corruption flags
  - repeat_pattern: Same winner wins from same institution repeatedly
  - escalating_risk: Entity's risk trend is increasing over time
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)

# Severity ordering for comparison (higher = more severe)
SEVERITY_ORDER = {
    'low': 1,
    'medium': 2,
    'high': 3,
    'critical': 4,
}


def severity_meets_threshold(severity: str, threshold: str) -> bool:
    """Check if a severity level meets or exceeds a threshold.

    Args:
        severity: The severity level to check (e.g., 'high').
        threshold: The minimum severity required (e.g., 'medium').

    Returns:
        True if severity >= threshold in the severity ordering.
    """
    return SEVERITY_ORDER.get(severity, 0) >= SEVERITY_ORDER.get(threshold, 0)


@dataclass
class AlertRule:
    """Base alert rule definition.

    Attributes:
        rule_type: Machine-readable rule identifier.
        name: Human-readable rule name.
        description: Explanation of what the rule detects.
        default_severity: Default severity when no override is computed.
    """
    rule_type: str
    name: str
    description: str
    default_severity: str = 'medium'

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        """Evaluate if this rule triggers for a tender.

        Args:
            tender_data: Dict containing tender fields:
                - tender_id, title, procuring_entity, winner
                - risk_score, risk_level, flag_count
                - actual_value_mkd, estimated_value_mkd
                - flags (list of flag_type strings)
                - flag_details (list of flag dicts with type, severity, score)
                - repeat_win_count (int, wins by this winner from this institution)
                - risk_trend (str: 'increasing', 'stable', 'decreasing')
                - risk_history (list of recent risk scores for this entity)

        Returns:
            Dict with keys {severity, title, details} if rule triggers, else None.
        """
        raise NotImplementedError(f"Rule {self.rule_type} must implement evaluate()")


class HighRiskScoreRule(AlertRule):
    """Triggers when a tender's risk score exceeds a configurable threshold.

    Default threshold is 70. Severity is computed from the score:
      - >= 90 -> critical
      - >= 80 -> high
      - >= 70 -> medium
    """

    def __init__(self, threshold: float = 70):
        super().__init__(
            rule_type='high_risk_score',
            name='High Risk Score',
            description=f'Risk score exceeds {threshold}',
        )
        self.threshold = threshold

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        score = tender_data.get('risk_score', 0) or 0
        if score >= self.threshold:
            if score >= 90:
                severity = 'critical'
            elif score >= 80:
                severity = 'high'
            else:
                severity = 'medium'

            tender_id = tender_data.get('tender_id', 'N/A')
            return {
                'severity': severity,
                'title': f'Тендер со висок ризик (Скор: {score}) - {tender_id}',
                'details': {
                    'risk_score': score,
                    'risk_level': tender_data.get('risk_level'),
                    'threshold': self.threshold,
                    'tender_id': tender_id,
                    'procuring_entity': tender_data.get('procuring_entity'),
                    'winner': tender_data.get('winner'),
                },
            }
        return None


class SingleBidderHighValueRule(AlertRule):
    """Triggers when a single-bidder tender has a contract value exceeding a threshold.

    A single-bidder tender is identified by the presence of 'single_bidder' in
    the tender's corruption flags. The value threshold is in MKD (default 5M).
    """

    def __init__(self, value_threshold: float = 5_000_000):
        super().__init__(
            rule_type='single_bidder_high_value',
            name='Single Bidder High Value',
            description=f'Single bidder tender with value > {value_threshold:,.0f} MKD',
        )
        self.value_threshold = value_threshold

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        flags = tender_data.get('flags', []) or []
        if 'single_bidder' not in flags:
            return None

        # Use actual_value if available, otherwise estimated_value
        value = tender_data.get('actual_value_mkd') or tender_data.get('estimated_value_mkd') or 0
        try:
            value = float(value)
        except (TypeError, ValueError):
            value = 0

        if value < self.value_threshold:
            return None

        # Higher value = higher severity
        if value >= 50_000_000:
            severity = 'critical'
        elif value >= 20_000_000:
            severity = 'high'
        else:
            severity = 'medium'

        tender_id = tender_data.get('tender_id', 'N/A')
        return {
            'severity': severity,
            'title': f'Единствен понудувач со висока вредност ({value:,.0f} MKD) - {tender_id}',
            'details': {
                'tender_id': tender_id,
                'value_mkd': value,
                'value_threshold': self.value_threshold,
                'procuring_entity': tender_data.get('procuring_entity'),
                'winner': tender_data.get('winner'),
                'flag_count': tender_data.get('flag_count', 0),
            },
        }


class WatchedEntityRule(AlertRule):
    """Triggers when a watched company or institution is involved in a tender.

    The list of watched entities is stored in rule_config as
    {"watched_entities": ["Company A", "Institution B"]}.
    Matching is case-insensitive substring match.
    """

    def __init__(self, watched_entities: List[str] = None):
        super().__init__(
            rule_type='watched_entity',
            name='Watched Entity Activity',
            description='Activity by watched entity',
        )
        self.watched_entities = [e.lower() for e in (watched_entities or [])]

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        if not self.watched_entities:
            return None

        winner = (tender_data.get('winner') or '').lower()
        institution = (tender_data.get('procuring_entity') or '').lower()
        matched_entities = []

        for entity in self.watched_entities:
            if entity in winner or entity in institution:
                matched_entities.append(entity)

        if not matched_entities:
            return None

        # Severity depends on risk score of the tender
        risk_score = tender_data.get('risk_score', 0) or 0
        if risk_score >= 70:
            severity = 'high'
        elif risk_score >= 40:
            severity = 'medium'
        else:
            severity = 'low'

        tender_id = tender_data.get('tender_id', 'N/A')
        return {
            'severity': severity,
            'title': f'Активност на набљудуван субјект - {", ".join(matched_entities)} - {tender_id}',
            'details': {
                'tender_id': tender_id,
                'matched_entities': matched_entities,
                'winner': tender_data.get('winner'),
                'procuring_entity': tender_data.get('procuring_entity'),
                'risk_score': risk_score,
                'risk_level': tender_data.get('risk_level'),
            },
        }


class MultipleRedFlagsRule(AlertRule):
    """Triggers when a tender has N or more corruption flags.

    Default threshold is 3. Severity scales with the number of flags:
      - >= 6 flags -> critical
      - >= 5 flags -> high
      - >= threshold -> medium
    """

    def __init__(self, flag_threshold: int = 3):
        super().__init__(
            rule_type='multiple_flags',
            name='Multiple Red Flags',
            description=f'{flag_threshold}+ corruption flags on a single tender',
        )
        self.flag_threshold = flag_threshold

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        flag_count = tender_data.get('flag_count', 0) or 0
        flags = tender_data.get('flags', []) or []

        # Use the greater of flag_count or len(flags)
        actual_count = max(flag_count, len(flags))

        if actual_count < self.flag_threshold:
            return None

        if actual_count >= 6:
            severity = 'critical'
        elif actual_count >= 5:
            severity = 'high'
        else:
            severity = 'medium'

        tender_id = tender_data.get('tender_id', 'N/A')
        return {
            'severity': severity,
            'title': f'Повеќекратни знамиња ({actual_count}) - {tender_id}',
            'details': {
                'tender_id': tender_id,
                'flag_count': actual_count,
                'flag_threshold': self.flag_threshold,
                'flag_types': list(flags),
                'risk_score': tender_data.get('risk_score'),
                'procuring_entity': tender_data.get('procuring_entity'),
                'winner': tender_data.get('winner'),
            },
        }


class RepeatPatternRule(AlertRule):
    """Triggers when the same winner wins from the same institution repeatedly.

    The repeat_win_count field in tender_data is populated by the alerter
    by querying the tenders table for historical patterns. Default threshold is 3.
    """

    def __init__(self, repeat_threshold: int = 3):
        super().__init__(
            rule_type='repeat_pattern',
            name='Repeat Winner Pattern',
            description=f'Same winner from same institution {repeat_threshold}+ times',
        )
        self.repeat_threshold = repeat_threshold

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        repeat_count = tender_data.get('repeat_win_count', 0) or 0

        if repeat_count < self.repeat_threshold:
            return None

        if repeat_count >= 10:
            severity = 'critical'
        elif repeat_count >= 6:
            severity = 'high'
        else:
            severity = 'medium'

        tender_id = tender_data.get('tender_id', 'N/A')
        winner = tender_data.get('winner', 'N/A')
        institution = tender_data.get('procuring_entity', 'N/A')
        return {
            'severity': severity,
            'title': f'Повторен победник ({repeat_count}x): {winner} - {institution}',
            'details': {
                'tender_id': tender_id,
                'winner': winner,
                'procuring_entity': institution,
                'repeat_count': repeat_count,
                'repeat_threshold': self.repeat_threshold,
                'risk_score': tender_data.get('risk_score'),
            },
        }


class EscalatingRiskRule(AlertRule):
    """Triggers when an entity's risk trend is increasing.

    The risk_trend field in tender_data is populated by the alerter by
    analyzing the entity's recent tender risk scores. Possible values:
    'increasing', 'stable', 'decreasing'.

    Also considers risk_history (list of recent scores) to compute
    the actual trend magnitude.
    """

    def __init__(self):
        super().__init__(
            rule_type='escalating_risk',
            name='Escalating Risk',
            description='Entity risk trend is increasing',
        )

    def evaluate(self, tender_data: dict) -> Optional[dict]:
        risk_trend = tender_data.get('risk_trend')
        if risk_trend != 'increasing':
            return None

        risk_history = tender_data.get('risk_history', []) or []
        current_score = tender_data.get('risk_score', 0) or 0

        # Calculate trend magnitude
        if len(risk_history) >= 2:
            oldest = risk_history[0]
            newest = risk_history[-1]
            try:
                trend_delta = float(newest) - float(oldest)
            except (TypeError, ValueError):
                trend_delta = 0
        else:
            trend_delta = 0

        # Severity based on current score and trend magnitude
        if current_score >= 80 and trend_delta >= 20:
            severity = 'critical'
        elif current_score >= 60 or trend_delta >= 15:
            severity = 'high'
        else:
            severity = 'medium'

        entity = tender_data.get('procuring_entity') or tender_data.get('winner') or 'N/A'
        tender_id = tender_data.get('tender_id', 'N/A')
        return {
            'severity': severity,
            'title': f'Ескалирачки ризик за {entity} - {tender_id}',
            'details': {
                'tender_id': tender_id,
                'entity': entity,
                'current_risk_score': current_score,
                'risk_trend': risk_trend,
                'trend_delta': trend_delta,
                'risk_history': risk_history,
                'procuring_entity': tender_data.get('procuring_entity'),
                'winner': tender_data.get('winner'),
            },
        }


# ============================================================================
# RULE REGISTRY
# ============================================================================

AVAILABLE_RULES: Dict[str, type] = {
    'high_risk_score': HighRiskScoreRule,
    'single_bidder_high_value': SingleBidderHighValueRule,
    'watched_entity': WatchedEntityRule,
    'multiple_flags': MultipleRedFlagsRule,
    'repeat_pattern': RepeatPatternRule,
    'escalating_risk': EscalatingRiskRule,
}


def create_rule(rule_type: str, config: dict = None) -> AlertRule:
    """Factory to create a rule instance from a type string and optional config.

    Args:
        rule_type: One of the keys in AVAILABLE_RULES.
        config: Optional dict of keyword arguments passed to the rule constructor.
                For example: {"threshold": 80} for HighRiskScoreRule,
                {"watched_entities": ["Alkaloid"]} for WatchedEntityRule.

    Returns:
        An instantiated AlertRule subclass.

    Raises:
        ValueError: If rule_type is not recognized.
    """
    config = config or {}
    cls = AVAILABLE_RULES.get(rule_type)
    if not cls:
        raise ValueError(f"Unknown rule type: {rule_type}. Available: {list(AVAILABLE_RULES.keys())}")
    try:
        return cls(**config)
    except TypeError as e:
        raise ValueError(f"Invalid config for rule '{rule_type}': {e}")


def list_available_rules() -> List[dict]:
    """Return metadata about all available rule types.

    Returns:
        List of dicts with rule_type, name, description for each available rule.
    """
    result = []
    for rule_type, cls in AVAILABLE_RULES.items():
        # Instantiate with defaults to get name/description
        try:
            instance = cls()
            result.append({
                'rule_type': rule_type,
                'name': instance.name,
                'description': instance.description,
                'default_severity': instance.default_severity,
            })
        except Exception:
            result.append({
                'rule_type': rule_type,
                'name': rule_type,
                'description': '',
                'default_severity': 'medium',
            })
    return result
