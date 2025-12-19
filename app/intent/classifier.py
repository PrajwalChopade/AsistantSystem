"""
Intent classification using keyword and pattern matching.
Deterministic, no LLM dependency.
"""

import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass

from app.intent.constants import (
    IntentCategory,
    HIGH_RISK_INTENTS,
    INFORMATIONAL_KEYWORDS,
    ACTION_KEYWORDS,
    INTENT_SPECIALIZATIONS,
    INTENT_SEVERITY,
)


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: str
    confidence: float
    is_high_risk: bool
    is_actionable: bool
    specialization: str
    severity: str


class IntentClassifier:
    """Rule-based intent classifier with confidence scoring."""
    
    # Pattern definitions with associated intents and base confidence
    INTENT_PATTERNS: List[Tuple[str, str, float]] = [
        # Account deletion patterns
        (r'\b(delete|remove|close|terminate)\s+(my\s+)?(account|profile)\b', IntentCategory.ACCOUNT_DELETION.value, 0.8),
        (r'\bpermanently\s+(delete|remove)\b', IntentCategory.ACCOUNT_DELETION.value, 0.85),
        (r'\b(want|need)\s+to\s+(delete|close)\b', IntentCategory.ACCOUNT_DELETION.value, 0.75),
        
        # Refund patterns
        (r'\b(refund|money\s+back|reimburse)\b', IntentCategory.BILLING_REFUND.value, 0.7),
        (r'\b(get|want|need)\s+(a\s+)?refund\b', IntentCategory.BILLING_REFUND.value, 0.8),
        (r'\bcharge(d|s)?\s+(wrong|incorrect|twice|duplicate)\b', IntentCategory.BILLING_REFUND.value, 0.75),
        
        # Chargeback patterns
        (r'\bchargeback\b', IntentCategory.CHARGEBACK.value, 0.9),
        (r'\bdispute\s+(charge|transaction|payment)\b', IntentCategory.CHARGEBACK.value, 0.8),
        (r'\bcontact(ing)?\s+(my\s+)?bank\b', IntentCategory.CHARGEBACK.value, 0.7),
        
        # Data export patterns
        (r'\b(export|download)\s+(my\s+)?data\b', IntentCategory.DATA_EXPORT.value, 0.8),
        (r'\bgdpr\s+(request|data)\b', IntentCategory.DATA_EXPORT.value, 0.85),
        (r'\b(all\s+)?my\s+information\b', IntentCategory.DATA_EXPORT.value, 0.6),
        
        # Login issues
        (r'\b(can\'?t|cannot|unable)\s+(to\s+)?(login|log\s*in|sign\s*in)\b', IntentCategory.LOGIN_ISSUE.value, 0.85),
        (r'\blogin\s+(problem|issue|error)\b', IntentCategory.LOGIN_ISSUE.value, 0.8),
        (r'\baccount\s+locked\b', IntentCategory.LOGIN_ISSUE.value, 0.85),
        
        # Password reset
        (r'\b(reset|forgot|change)\s+(my\s+)?password\b', IntentCategory.PASSWORD_RESET.value, 0.9),
        (r'\bpassword\s+(reset|recovery)\b', IntentCategory.PASSWORD_RESET.value, 0.85),
        
        # Bug reports
        (r'\b(bug|error|broken|not\s+working)\b', IntentCategory.BUG_REPORT.value, 0.6),
        (r'\b(crash|crashes|crashed)\b', IntentCategory.BUG_REPORT.value, 0.7),
        (r'\b(issue|problem)\s+with\b', IntentCategory.BUG_REPORT.value, 0.5),
        
        # Integration/API
        (r'\bapi\s+(key|documentation|endpoint)\b', IntentCategory.API_SUPPORT.value, 0.8),
        (r'\b(integrate|integration|webhook)\b', IntentCategory.INTEGRATION_HELP.value, 0.75),
        
        # Pricing
        (r'\b(price|pricing|cost|subscription|plan)\b', IntentCategory.PRICING_QUESTION.value, 0.7),
        (r'\bhow\s+much\b', IntentCategory.PRICING_QUESTION.value, 0.6),
        
        # Feedback/complaints
        (r'\b(complaint|complain|disappointed|frustrated)\b', IntentCategory.COMPLAINT.value, 0.7),
        (r'\b(feedback|suggestion|recommend)\b', IntentCategory.FEEDBACK.value, 0.7),
        
        # Feature inquiry
        (r'\b(feature|capability|can\s+you|does\s+it)\b', IntentCategory.FEATURE_INQUIRY.value, 0.5),
    ]
    
    def classify(self, message: str) -> IntentResult:
        """
        Classify user message intent.
        
        Args:
            message: User's message text
            
        Returns:
            IntentResult with intent, confidence, and metadata
        """
        msg_lower = message.lower().strip()
        
        # Check if this is informational (question) vs actionable
        is_informational = self._is_informational(msg_lower)
        is_actionable = self._is_actionable(msg_lower)
        
        # Match patterns
        best_intent = IntentCategory.GENERAL_QUESTION.value
        best_confidence = 0.3
        
        for pattern, intent, base_conf in self.INTENT_PATTERNS:
            if re.search(pattern, msg_lower):
                # Adjust confidence based on actionability
                conf = base_conf
                
                if intent in HIGH_RISK_INTENTS:
                    # High-risk intents need action keywords for high confidence
                    if is_actionable and not is_informational:
                        conf = min(conf + 0.1, 0.95)
                    elif is_informational:
                        conf = max(conf - 0.3, 0.3)  # Reduce confidence for info queries
                
                if conf > best_confidence:
                    best_confidence = conf
                    best_intent = intent
        
        # Build result
        is_high_risk = best_intent in HIGH_RISK_INTENTS
        specialization = INTENT_SPECIALIZATIONS.get(best_intent, "general")
        severity = INTENT_SEVERITY.get(best_intent, "low")
        
        return IntentResult(
            intent=best_intent,
            confidence=round(best_confidence, 2),
            is_high_risk=is_high_risk,
            is_actionable=is_actionable and not is_informational,
            specialization=specialization,
            severity=severity
        )
    
    def _is_informational(self, message: str) -> bool:
        """Check if message is asking for information."""
        for keyword in INFORMATIONAL_KEYWORDS:
            if keyword in message:
                return True
        # Check if starts with question words
        question_starters = ['how', 'what', 'when', 'where', 'why', 'can i', 'is it', 'do you']
        for starter in question_starters:
            if message.startswith(starter):
                return True
        return False
    
    def _is_actionable(self, message: str) -> bool:
        """Check if message is requesting an action."""
        for keyword in ACTION_KEYWORDS:
            if keyword in message:
                return True
        return False


# Singleton instance
_classifier: IntentClassifier = None


def get_intent_classifier() -> IntentClassifier:
    """Get singleton intent classifier."""
    global _classifier
    if _classifier is None:
        _classifier = IntentClassifier()
    return _classifier


def classify_intent(message: str) -> IntentResult:
    """Convenience function to classify intent."""
    classifier = get_intent_classifier()
    return classifier.classify(message)
