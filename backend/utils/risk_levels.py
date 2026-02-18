"""Shared risk level calculation utilities for corruption detection."""


RISK_THRESHOLDS = {
    "critical": 80,
    "high": 60,
    "medium": 40,
    "low": 20,
}

RISK_COLORS = {
    "critical": "#ef4444",
    "high": "#f97316",
    "medium": "#eab308",
    "low": "#3b82f6",
    "minimal": "#22c55e",
}


def calculate_risk_level(score: int) -> str:
    """Calculate risk level from a 0-100 score."""
    if score >= 80:
        return "critical"
    elif score >= 60:
        return "high"
    elif score >= 40:
        return "medium"
    elif score >= 20:
        return "low"
    else:
        return "minimal"


def get_risk_level_info(score_0_100: float) -> dict:
    """Get risk level info from a 0-100 score."""
    level = calculate_risk_level(int(score_0_100))
    return {
        "level": level,
        "color": RISK_COLORS[level],
        "probability": score_0_100 / 100.0,
    }
