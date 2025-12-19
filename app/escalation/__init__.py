"""
Escalation module for human handoff.
"""

from app.escalation.human_pool import (
    HumanAgent,
    AgentStatus,
    HumanAgentPool,
    get_human_pool,
    seed_demo_agents,
)
from app.escalation.router import (
    EscalationResult,
    EscalationRouter,
    get_escalation_router,
    check_escalation,
)
from app.escalation.email_service import (
    EscalationEmailService,
    get_email_service,
    send_escalation_email,
)

__all__ = [
    "HumanAgent",
    "AgentStatus",
    "HumanAgentPool",
    "get_human_pool",
    "seed_demo_agents",
    "EscalationResult",
    "EscalationRouter",
    "get_escalation_router",
    "check_escalation",
    "EscalationEmailService",
    "get_email_service",
    "send_escalation_email",
]
