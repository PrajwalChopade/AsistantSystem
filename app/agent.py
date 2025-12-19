"""
LangGraph-based agent orchestration.
Production-ready: Document-first, self-service, explicit escalation.
"""

from typing import TypedDict, Optional, Dict, Any, List

from langgraph.graph import StateGraph, END

from app.config import settings
from app.intent import classify_intent, IntentResult
from app.rag import DocumentRetriever, RetrievalResponse
from app.escalation import check_escalation, EscalationResult
from app.llm import get_llm
from app.monitoring import get_tracer, get_metrics


# === Constants ===

NO_DOCS_RESPONSE = "I couldn't find information about this in our documentation. Please rephrase your question or contact support for assistance."
SYSTEM_ERROR_RESPONSE = "I apologize, but I encountered an error. Please try again."


# === State Definition ===

class AgentState(TypedDict):
    """State passed between nodes in the graph."""
    # Input
    client_id: str
    user_id: str
    message: str
    
    # Intent classification
    intent: str
    intent_confidence: float
    is_high_risk: bool
    is_actionable: bool
    specialization: str
    severity: str
    
    # Retrieval
    context: str
    retrieval_confidence: float
    sources: List[str]
    has_relevant_docs: bool
    doc_version: str
    
    # Response
    reply: str
    source: str  # "document" | "llm" | "human"
    
    # Escalation
    should_escalate: bool
    escalation_reason: Optional[str]
    assigned_human: Optional[Dict[str, Any]]
    ticket_id: Optional[str]
    
    # Control flow
    needs_clarification: Optional[bool]
    error: Optional[str]


# === Node Functions ===

def intent_classification_node(state: AgentState) -> AgentState:
    """Classify user intent."""
    tracer = get_tracer()
    
    with tracer.trace_run("intent_classification", inputs={"message": state["message"]}):
        result = classify_intent(state["message"])
        
        return {
            **state,
            "intent": result.intent,
            "intent_confidence": result.confidence,
            "is_high_risk": result.is_high_risk,
            "is_actionable": result.is_actionable,
            "specialization": result.specialization,
            "severity": result.severity,
        }


def document_retrieval_node(state: AgentState) -> AgentState:
    """Retrieve relevant documents with expanded search."""
    tracer = get_tracer()
    
    with tracer.trace_run("document_retrieval", inputs={"query": state["message"]}):
        retriever = DocumentRetriever(state["client_id"])
        
        # Check if client has documents
        if not retriever.has_documents:
            return {
                **state,
                "context": "",
                "retrieval_confidence": 0.0,
                "sources": [],
                "has_relevant_docs": False,
            }
        
        # Retrieve with expanded search
        result = retriever.retrieve(
            state["message"],
            top_k=5,  # Get more chunks for better context
            min_score=0.25  # Lower threshold to capture more
        )
        
        return {
            **state,
            "context": result.context,
            "retrieval_confidence": result.confidence,
            "sources": result.sources,
            "has_relevant_docs": result.is_relevant,
        }


def relevance_validation_node(state: AgentState) -> AgentState:
    """Validate retrieval relevance - no longer blocks for clarification."""
    tracer = get_tracer()
    metrics = get_metrics()
    
    with tracer.trace_run("relevance_validation"):
        confidence = state.get("retrieval_confidence", 0)
        metrics.record_confidence(confidence)
        
        # Mark if we have relevant documents
        has_relevant_docs = (
            confidence >= 0.3 and 
            bool(state.get("context", "").strip())
        )
        
        return {
            **state,
            "has_relevant_docs": has_relevant_docs,
            "needs_clarification": False,  # Never block for clarification
        }


def confidence_scoring_node(state: AgentState) -> AgentState:
    """Score overall confidence for escalation decision."""
    tracer = get_tracer()
    
    with tracer.trace_run("confidence_scoring"):
        intent_conf = state.get("intent_confidence", 0)
        retrieval_conf = state.get("retrieval_confidence", 0)
        
        # Combined confidence score
        combined = (intent_conf + retrieval_conf) / 2
        
        return {
            **state,
            "combined_confidence": combined,
        }


def escalation_decision_node(state: AgentState) -> AgentState:
    """Decide if escalation is needed based on intent and confidence."""
    tracer = get_tracer()
    metrics = get_metrics()
    
    with tracer.trace_run("escalation_decision"):
        intent_result = IntentResult(
            intent=state.get("intent", "unknown"),
            confidence=state.get("intent_confidence", 0),
            is_high_risk=state.get("is_high_risk", False),
            is_actionable=state.get("is_actionable", False),
            specialization=state.get("specialization", "general"),
            severity=state.get("severity", "low"),
        )
        
        result = check_escalation(
            user_id=state["user_id"],
            intent_result=intent_result,
            message=state["message"],
            client_id=state["client_id"],
            retrieval_confidence=state.get("retrieval_confidence", 1.0)
        )
        
        if result.should_escalate:
            metrics.increment("escalations")
        
        return {
            **state,
            "should_escalate": result.should_escalate,
            "escalation_reason": result.reason,
            "assigned_human": result.assigned_agent,
            "ticket_id": result.ticket_id,
        }


def answer_generation_node(state: AgentState) -> AgentState:
    """
    Generate answer from documents with LLM fallback.
    
    Priority:
    1. If docs have the answer -> use document-grounded response
    2. If no docs but not high-risk -> use LLM general knowledge
    3. Otherwise -> return helpful fallback message
    """
    tracer = get_tracer()
    metrics = get_metrics()
    
    with tracer.trace_run("answer_generation"):
        llm = get_llm()
        context = state.get("context", "")
        has_docs = state.get("has_relevant_docs", False)
        query = state["message"]
        is_high_risk = state.get("is_high_risk", False)
        
        # Priority 1: Document-grounded response when docs are available
        if has_docs and context.strip():
            response = llm.generate_document_grounded(
                context=context,
                query=query,
                sources=state.get("sources", [])
            )
            if response:
                return {
                    **state,
                    "reply": response,
                    "source": "document",
                }
        
        # Priority 2: LLM general response for non-sensitive queries
        if not is_high_risk:
            response = llm.generate_general_response(
                query=query,
                intent=state.get("intent", "general_question")
            )
            if response:
                return {
                    **state,
                    "reply": response,
                    "source": "llm",
                }
        
        # Priority 3: Fallback for cases where nothing works
        metrics.increment("retrieval_failures")
        return {
            **state,
            "reply": NO_DOCS_RESPONSE,
            "source": "document",
        }


def escalation_response_node(state: AgentState) -> AgentState:
    """Generate escalation response."""
    assigned = state.get("assigned_human")
    ticket_id = state.get("ticket_id", "")
    
    if assigned:
        reply = (
            f"I've connected you with a support specialist who can help with this request.\n\n"
            f"🎫 Ticket ID: {ticket_id}\n"
            f"👤 Agent: {assigned.get('name', 'Support Agent')}\n\n"
            f"They will be with you shortly."
        )
    else:
        reply = (
            f"This request requires assistance from our support team. "
            f"I've created a ticket for you.\n\n"
            f"🎫 Ticket ID: {ticket_id}\n\n"
            f"A team member will contact you soon."
        )
    
    return {
        **state,
        "reply": reply,
        "source": "human",
    }


def cache_response_node(state: AgentState) -> AgentState:
    """No-op node - caching disabled per production requirements."""
    return state


# === Routing Functions ===

def route_after_escalation(state: AgentState) -> str:
    """Route based on escalation decision."""
    if state.get("should_escalate"):
        return "escalate"
    return "answer"


# === Graph Builder ===

def build_support_graph() -> StateGraph:
    """Build the LangGraph state machine - simplified flow without caching."""
    
    # Create graph
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("intent_classification", intent_classification_node)
    graph.add_node("document_retrieval", document_retrieval_node)
    graph.add_node("relevance_validation", relevance_validation_node)
    graph.add_node("confidence_scoring", confidence_scoring_node)
    graph.add_node("escalation_decision", escalation_decision_node)
    graph.add_node("answer_generation", answer_generation_node)
    graph.add_node("escalation_response", escalation_response_node)
    
    # Set entry point
    graph.set_entry_point("intent_classification")
    
    # Define edges - linear flow until escalation decision
    graph.add_edge("intent_classification", "document_retrieval")
    graph.add_edge("document_retrieval", "relevance_validation")
    graph.add_edge("relevance_validation", "confidence_scoring")
    graph.add_edge("confidence_scoring", "escalation_decision")
    
    # Conditional: after escalation decision
    graph.add_conditional_edges(
        "escalation_decision",
        route_after_escalation,
        {
            "escalate": "escalation_response",
            "answer": "answer_generation",
        }
    )
    
    graph.add_edge("answer_generation", END)
    graph.add_edge("escalation_response", END)
    
    return graph.compile()


# === Main Handler ===

class SupportAgent:
    """Document-driven support agent - production-ready."""
    
    def __init__(self):
        self.graph = build_support_graph()
    
    def handle(
        self,
        client_id: str,
        user_id: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Handle a support request.
        
        Args:
            client_id: Client identifier
            user_id: User identifier
            message: User's message
            
        Returns:
            Response with reply, intent, confidence, source, etc.
        """
        metrics = get_metrics()
        metrics.increment("requests_total")
        
        # Initial state
        initial_state: AgentState = {
            "client_id": client_id,
            "user_id": user_id,
            "message": message,
            "intent": None,
            "intent_confidence": None,
            "is_high_risk": None,
            "is_actionable": None,
            "specialization": None,
            "severity": None,
            "context": None,
            "retrieval_confidence": None,
            "sources": None,
            "has_relevant_docs": None,
            "doc_version": None,
            "reply": None,
            "source": None,
            "should_escalate": None,
            "escalation_reason": None,
            "assigned_human": None,
            "ticket_id": None,
            "needs_clarification": None,
            "error": None,
        }
        
        try:
            # Run the graph
            final_state = self.graph.invoke(initial_state)
            
            # Build response with safe defaults
            escalated = final_state.get("should_escalate")
            confidence = final_state.get("intent_confidence")
            
            return {
                "reply": final_state.get("reply") or SYSTEM_ERROR_RESPONSE,
                "escalated": bool(escalated) if escalated is not None else False,
                "intent": final_state.get("intent") or "unknown",
                "confidence": float(confidence) if confidence is not None else 0.0,
                "source": final_state.get("source") or "document",
                "assigned_human": final_state.get("assigned_human"),
                "ticket_id": final_state.get("ticket_id"),
            }
            
        except Exception as e:
            print(f"❌ Agent error: {e}")
            import traceback
            traceback.print_exc()
            
            return {
                "reply": SYSTEM_ERROR_RESPONSE,
                "escalated": False,
                "intent": "error",
                "confidence": 0.0,
                "source": "document",
                "assigned_human": None,
                "ticket_id": None,
            }


# Singleton instance
_agent: Optional[SupportAgent] = None


def get_support_agent() -> SupportAgent:
    """Get singleton support agent."""
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


def handle_message(
    client_id: str,
    user_id: str,
    message: str
) -> Dict[str, Any]:
    """Convenience function to handle messages."""
    agent = get_support_agent()
    return agent.handle(client_id, user_id, message)
