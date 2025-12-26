"""
Adaptive Learning System

Key innovation from Dozorro: NO FIXED COEFFICIENTS
System learns optimal thresholds from expert feedback.

Components:
- feedback.py: Collect and store expert verdicts
- retrain.py: Automated model retraining pipeline
- thresholds.py: Dynamic threshold optimization

Feedback Loop:
1. Model makes prediction
2. Expert reviews and provides verdict
3. Feedback stored in corruption_feedback table
4. Periodic retraining with new labels
5. Thresholds auto-adjusted based on precision/recall
"""

__all__ = []
