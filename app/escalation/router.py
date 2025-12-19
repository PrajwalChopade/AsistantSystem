"""
Escalation routing logic.
Production-ready: explicit escalation decisions with traceable ticket IDs.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
import uuid
import re

from app.intent import IntentResult, HIGH_RISK_INTENTS
from app.escalation.human_pool import get_human_pool, HumanAgent
from app.config import settings


# Keywords indicating user explicitly wants human help
HUMAN_REQUEST_PATTERNS = [
    r"\b(talk|speak|chat)\s+(to|with)\s+(a\s+)?(human|person|agent|representative|someone)\b",
    r"\b(need|want)\s+(a\s+)?(human|person|agent|representative)\b",
    r"\b(connect|transfer)\s+me\s+to\b",
    r"\bhuman\s+(help|support|assistance)\b",
    r"\breal\s+person\b",
]

# Compiled patterns for efficiency
_human_patterns = [re.compile(p, re.IGNORECASE) for p in HUMAN_REQUEST_PATTERNS]


@dataclass
class EscalationResult:
    """Result of escalation decision."""
    should_escalate: bool
    reason: str
    assigned_agent: Optional[Dict[str, Any]] = None
    ticket_id: Optional[str] = None


def should_escalate(intent: str, confidence: float, message: str, is_actionable: bool = False) -> tuple[bool, str]:
    """
    Production-ready escalation decision.
    
    Args:
        intent: Classified intent string
        confidence: Intent classification confidence (0.0-1.0)
        message: Original user message
        is_actionable: Whether the message is an action request (not just a question)
        
    Returns:
        Tuple of (should_escalate: bool, reason: str)
        
    Rules (in order):
        1. User explicitly requests human → escalate
        2. HIGH_RISK_INTENTS + ACTIONABLE (not informational) → escalate
        3. Otherwise → self-service (answer from docs)
        
    Key distinction:
        - "How do I delete my account?" → informational → self-service
        - "Delete my account now" → action request → escalate
    """
    message_lower = message.lower().strip()
    
    # Rule 1: User explicitly asks for human - always honor this
    for pattern in _human_patterns:
        if pattern.search(message_lower):
            return True, "user_requested_human"
    
    # Rule 2: High-risk intents ONLY escalate if it's an ACTION request
    # Questions like "How do I...?" should get self-service answers
    if intent in HIGH_RISK_INTENTS:
        # Check if this is informational (question) vs action request
        is_question = _is_informational_query(message_lower)
        
        if is_actionable and not is_question:
            return True, f"high_risk_action:{intent}"
        # If it's a question about a high-risk topic, provide self-service info
        # e.g., "How do I delete my account?" → explain the process from docs
    
    # Rule 3: All other cases - self-service
    return False, "self_service"


def _is_informational_query(message: str) -> bool:
    """
    Check if message is asking for information vs requesting action.
    
    Informational: "How do I...", "What is...", "Can I..."
    Action: "Delete my account", "I want a refund", "Process my request"
    """
    # Question word starters
    question_starters = [
        'how ', 'what ', 'when ', 'where ', 'why ', 'which ',
        'can i ', 'can you ', 'is it ', 'is there ', 'do you ', 'does ',
        'could i ', 'could you ', 'would ', 'should ',
    ]
    
    for starter in question_starters:
        if message.startswith(starter):
            return True
    
    # Contains question indicators
    question_indicators = [
        'how do i', 'how can i', 'how to', 'what is', 'what are',
        'tell me about', 'explain', 'information about', 'info on',
        'policy', 'process for', 'steps to', 'way to',
        '?',  # Ends with question mark
    ]
    
    for indicator in question_indicators:
        if indicator in message:
            return True
    
    return False


class EscalationRouter:
    """Routes escalations based on intent and confidence."""
    
    def __init__(self):
        self.pool = get_human_pool()
    
    def _generate_ticket_id(self) -> str:
        """Generate unique, traceable ticket ID."""
        timestamp = datetime.utcnow().strftime("%Y%m%d")
        unique = uuid.uuid4().hex[:6].upper()
        return f"TKT-{timestamp}-{unique}"
    
    def route(
        self,
        user_id: str,
        intent_result: IntentResult,
        message: str,
        client_id: str = "unknown",
        retrieval_confidence: float = 1.0
    ) -> EscalationResult:
        """
        Route escalation to appropriate human agent and send notification.
        
        Args:
            user_id: User requesting assistance
            intent_result: Classified intent
            message: Original message
            client_id: Client/tenant identifier
            retrieval_confidence: Document retrieval confidence
            
        Returns:
            EscalationResult with assignment details
        """
        escalate, reason = should_escalate(
            intent=intent_result.intent,
            confidence=intent_result.confidence,
            message=message,
            is_actionable=intent_result.is_actionable
        )
        
        if not escalate:
            return EscalationResult(
                should_escalate=False,
                reason=reason
            )
        
        ticket_id = self._generate_ticket_id()
        
        agent = self.pool.assign_agent(
            user_id=user_id,
            specialization=intent_result.specialization,
            severity=intent_result.severity
        )
        
        if agent:
            # Send email notification to the assigned agent
            from app.escalation.email_service import send_escalation_email
            
            send_escalation_email(
                agent_email=agent.email,
                agent_name=agent.name,
                ticket_id=ticket_id,
                user_id=user_id,
                user_message=message,
                intent=intent_result.intent,
                escalation_reason=reason,
                client_id=client_id
            )
            
            return EscalationResult(
                should_escalate=True,
                reason=reason,
                assigned_agent={
                    "agent_id": agent.agent_id,
                    "name": agent.name,
                    "email": agent.email,
                    "specializations": agent.specializations
                },
                ticket_id=ticket_id
            )
        else:
            return EscalationResult(
                should_escalate=True,
                reason=reason,
                assigned_agent=None,
                ticket_id=ticket_id
            )
    
    def create_escalation_event(
        self,
        user_id: str,
        client_id: str,
        intent_result: IntentResult,
        message: str,
        escalation_result: EscalationResult
    ) -> Dict[str, Any]:
        """Create escalation event for logging/webhook."""
        return {
            "event_type": "escalation",
            "ticket_id": escalation_result.ticket_id,
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "client_id": client_id,
            "intent": intent_result.intent,
            "confidence": intent_result.confidence,
            "severity": intent_result.severity,
            "reason": escalation_result.reason,
            "message_preview": message[:200] if len(message) > 200 else message,
            "assigned_agent": escalation_result.assigned_agent
        }


_router: Optional[EscalationRouter] = None


def get_escalation_router() -> EscalationRouter:
    """Get singleton escalation router."""
    global _router
    if _router is None:
        _router = EscalationRouter()
    return _router


def check_escalation(
    user_id: str,
    intent_result: IntentResult,
    message: str,
    client_id: str = "unknown",
    retrieval_confidence: float = 1.0
) -> EscalationResult:
    """Convenience function to check and route escalation."""
    router = get_escalation_router()
    return router.route(user_id, intent_result, message, client_id, retrieval_confidence)
