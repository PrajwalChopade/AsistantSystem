"""
Intent classification constants and categories.
"""

from enum import Enum
from typing import Set, Dict, List


class IntentCategory(str, Enum):
    """User intent categories."""
    
    # General queries
    GENERAL_QUESTION = "general_question"
    FEATURE_INQUIRY = "feature_inquiry"
    PRICING_QUESTION = "pricing_question"
    
    # Account management
    LOGIN_ISSUE = "login_issue"
    PASSWORD_RESET = "password_reset"
    ACCOUNT_SETTINGS = "account_settings"
    
    # High-risk actions (require escalation at high confidence)
    ACCOUNT_DELETION = "account_deletion"
    BILLING_REFUND = "billing_refund"
    CHARGEBACK = "chargeback"
    DATA_EXPORT = "data_export"
    
    # Technical support
    BUG_REPORT = "bug_report"
    INTEGRATION_HELP = "integration_help"
    API_SUPPORT = "api_support"
    
    # Feedback
    FEEDBACK = "feedback"
    COMPLAINT = "complaint"
    
    # Unknown
    UNKNOWN = "unknown"


# Low-risk intents - always self-service, never escalate
LOW_RISK_INTENTS: Set[str] = {
    IntentCategory.GENERAL_QUESTION.value,
    IntentCategory.FEATURE_INQUIRY.value,
    IntentCategory.PRICING_QUESTION.value,
    IntentCategory.PASSWORD_RESET.value,
    IntentCategory.LOGIN_ISSUE.value,
    IntentCategory.ACCOUNT_SETTINGS.value,
    IntentCategory.FEEDBACK.value,
}

# High-risk intents - ALWAYS escalate immediately with ticket
HIGH_RISK_INTENTS: Set[str] = {
    IntentCategory.BILLING_REFUND.value,
    IntentCategory.CHARGEBACK.value,
    IntentCategory.ACCOUNT_DELETION.value,
    IntentCategory.DATA_EXPORT.value,
}

# Informational intents about risky topics (don't escalate)
INFORMATIONAL_INTENTS: Set[str] = {
    "refund_info",
    "delete_info", 
    "cancellation_info",
}

# Keywords that indicate informational queries (not action requests)
INFORMATIONAL_KEYWORDS: Set[str] = {
    "how", "what", "when", "where", "why",
    "policy", "policies", "information", "info",
    "tell me about", "explain", "describe",
    "can i", "is it possible", "do you",
}

# Keywords that indicate action requests
ACTION_KEYWORDS: Set[str] = {
    "want", "need", "please", "now",
    "initiate", "process", "start",
    "do", "make", "get", "give",
    "immediately", "asap", "urgent",
}

# Intent to specialization mapping for human routing
INTENT_SPECIALIZATIONS: Dict[str, str] = {
    IntentCategory.BILLING_REFUND.value: "billing",
    IntentCategory.CHARGEBACK.value: "billing",
    IntentCategory.PRICING_QUESTION.value: "billing",
    IntentCategory.ACCOUNT_DELETION.value: "account",
    IntentCategory.ACCOUNT_SETTINGS.value: "account",
    IntentCategory.LOGIN_ISSUE.value: "account",
    IntentCategory.PASSWORD_RESET.value: "account",
    IntentCategory.DATA_EXPORT.value: "security",
    IntentCategory.BUG_REPORT.value: "technical",
    IntentCategory.INTEGRATION_HELP.value: "technical",
    IntentCategory.API_SUPPORT.value: "technical",
    IntentCategory.COMPLAINT.value: "general",
    IntentCategory.FEEDBACK.value: "general",
    IntentCategory.GENERAL_QUESTION.value: "general",
    IntentCategory.FEATURE_INQUIRY.value: "general",
}

# Intent severity levels
INTENT_SEVERITY: Dict[str, str] = {
    IntentCategory.CHARGEBACK.value: "high",
    IntentCategory.ACCOUNT_DELETION.value: "high",
    IntentCategory.BILLING_REFUND.value: "medium",
    IntentCategory.DATA_EXPORT.value: "medium",
    IntentCategory.COMPLAINT.value: "medium",
    IntentCategory.BUG_REPORT.value: "medium",
    IntentCategory.LOGIN_ISSUE.value: "low",
    IntentCategory.PASSWORD_RESET.value: "low",
    IntentCategory.GENERAL_QUESTION.value: "low",
    IntentCategory.FEATURE_INQUIRY.value: "low",
    IntentCategory.PRICING_QUESTION.value: "low",
    IntentCategory.FEEDBACK.value: "low",
    IntentCategory.ACCOUNT_SETTINGS.value: "low",
    IntentCategory.INTEGRATION_HELP.value: "low",
    IntentCategory.API_SUPPORT.value: "low",
}
