"""
Anonymous Whistleblower Tip Triage Module

Provides ML-powered analysis and prioritization of anonymous corruption tips.
Extracts entities from tip text, matches them against known procurement data,
and scores tip credibility and urgency.
"""

from .tip_triage import TipTriageEngine

__all__ = ['TipTriageEngine']
