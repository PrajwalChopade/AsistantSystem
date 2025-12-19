"""
Intent classification module.
"""

from app.intent.constants import (
    IntentCategory,
    LOW_RISK_INTENTS,
    HIGH_RISK_INTENTS,
    INFORMATIONAL_INTENTS,
    INTENT_SPECIALIZATIONS,
    INTENT_SEVERITY,
)
from app.intent.classifier import (
    IntentClassifier,
    IntentResult,
    get_intent_classifier,
    classify_intent,
)

__all__ = [
    "IntentCategory",
    "LOW_RISK_INTENTS",
    "HIGH_RISK_INTENTS",
    "INFORMATIONAL_INTENTS",
    "INTENT_SPECIALIZATIONS",
    "INTENT_SEVERITY",
    "IntentClassifier",
    "IntentResult",
    "get_intent_classifier",
    "classify_intent",
]
