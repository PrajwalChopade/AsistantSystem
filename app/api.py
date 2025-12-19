"""
FastAPI API routes for the support platform.
Production-ready: clean request/response contracts.
"""

from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.agent import handle_message
from app.rag import ingest_client_documents, ingest_all_clients, VectorStoreManager
from app.escalation import get_human_pool, HumanAgent, AgentStatus, seed_demo_agents
from app.monitoring import get_metrics


router = APIRouter()


# === Request/Response Models ===

class ChatRequest(BaseModel):
    """Chat request model."""
    client_id: str = Field(..., description="Client/tenant identifier")
    user_id: str = Field(..., description="User identifier")
    message: str = Field(..., min_length=1, max_length=5000, description="User message")


class ChatResponse(BaseModel):
    """
    Chat response model - production API contract.
    
    Fields:
        reply: The assistant's response text
        escalated: True if request was escalated to human
        intent: Classified intent category
        confidence: Intent classification confidence (0.0-1.0)
        source: Response source - "document", "llm", or "human"
        assigned_human: Human agent details if escalated
        ticket_id: Support ticket ID if escalated
    """
    reply: str
    escalated: bool
    intent: str
    confidence: float
    source: str  # "document" | "llm" | "human"
    assigned_human: Optional[Dict[str, Any]] = None
    ticket_id: Optional[str] = None


class IngestRequest(BaseModel):
    """Document ingestion request."""
    client_id: str
    force: bool = Field(default=False, description="Force re-ingestion of all documents")


class IngestResponse(BaseModel):
    """Document ingestion response."""
    client_id: str
    processed: List[str]
    skipped: List[str]
    errors: List[Dict[str, str]]
    total_chunks: int


class AgentRegistration(BaseModel):
    """Human agent registration request."""
    agent_id: str
    name: str
    email: str
    specializations: List[str]
    max_load: int = Field(default=5, ge=1, le=20)


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    redis: str
    llm: str


# === Chat Endpoint ===

@router.post("/chat", response_model=ChatResponse, tags=["Chat"])
def chat(request: ChatRequest):
    """
    Process a support chat message.
    
    The response is document-grounded:
    - Answers come from client-provided documents only
    - If no relevant docs found, returns standard message
    - High-risk actions with high confidence trigger escalation
    """
    try:
        result = handle_message(
            client_id=request.client_id,
            user_id=request.user_id,
            message=request.message
        )
        
        return ChatResponse(
            reply=result["reply"],
            escalated=result["escalated"],
            intent=result["intent"],
            confidence=result["confidence"],
            source=result["source"],
            assigned_human=result.get("assigned_human"),
            ticket_id=result.get("ticket_id"),
        )
        
    except Exception as e:
        print(f"❌ Chat error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# === Document Management ===

@router.post("/ingest/{client_id}", response_model=IngestResponse, tags=["Documents"])
def ingest_documents(client_id: str, force: bool = False):
    """
    Ingest PDF documents for a client.
    
    Place PDF files in `data/documents/{client_id}/` directory.
    """
    try:
        result = ingest_client_documents(client_id, force=force)
        
        return IngestResponse(
            client_id=client_id,
            processed=result.get("processed", []),
            skipped=result.get("skipped", []),
            errors=result.get("errors", []),
            total_chunks=result.get("total_chunks", 0),
        )
        
    except Exception as e:
        print(f"❌ Ingestion error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/ingest", tags=["Documents"])
def ingest_all(force: bool = False, background_tasks: BackgroundTasks = None):
    """
    Ingest documents for all clients.
    
    Runs in background if many clients.
    """
    try:
        results = ingest_all_clients(force=force)
        return {"status": "completed", "clients": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/documents/{client_id}/status", tags=["Documents"])
def get_document_status(client_id: str):
    """Get document store status for a client."""
    try:
        store = VectorStoreManager.get_store(client_id)
        return {
            "client_id": client_id,
            "document_count": store.document_count,
            "version": store.version,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === Human Agent Management ===

@router.post("/agents/register", tags=["Agents"])
def register_agent(registration: AgentRegistration):
    """Register a human support agent."""
    pool = get_human_pool()
    
    agent = HumanAgent(
        agent_id=registration.agent_id,
        name=registration.name,
        email=registration.email,
        status=AgentStatus.INACTIVE.value,
        specializations=registration.specializations,
        max_load=registration.max_load,
        current_load=0,
    )
    
    pool.register_agent(agent)
    return {"status": "registered", "agent_id": agent.agent_id}


@router.put("/agents/{agent_id}/status", tags=["Agents"])
def update_agent_status(agent_id: str, status: str):
    """Update agent availability status."""
    pool = get_human_pool()
    
    try:
        agent_status = AgentStatus(status)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid status. Use: {[s.value for s in AgentStatus]}")
    
    if pool.update_status(agent_id, agent_status):
        return {"status": "updated", "agent_id": agent_id, "new_status": status}
    
    raise HTTPException(status_code=404, detail="Agent not found")


@router.get("/agents", tags=["Agents"])
def list_agents():
    """List all registered agents."""
    pool = get_human_pool()
    agents = pool.get_all_agents()
    return {"agents": [a.to_dict() for a in agents]}


@router.get("/agents/available", tags=["Agents"])
def list_available_agents(specialization: Optional[str] = None):
    """List available agents, optionally filtered by specialization."""
    pool = get_human_pool()
    agents = pool.get_available_agents(specialization)
    return {"agents": [a.to_dict() for a in agents]}


@router.post("/agents/seed-demo", tags=["Agents"])
def seed_agents():
    """Seed demo agents for testing."""
    seed_demo_agents()
    return {"status": "seeded"}


# === Metrics & Health ===

@router.get("/metrics", tags=["Monitoring"])
def get_platform_metrics():
    """Get platform metrics."""
    metrics = get_metrics()
    cache_metrics = get_response_cache().get_metrics()
    
    return {
        **metrics.get_metrics(),
        "cache": cache_metrics,
    }


@router.get("/health", response_model=HealthResponse, tags=["Monitoring"])
def health_check():
    """Health check endpoint."""
    from app.cache.redis_client import get_redis_client
    from app.llm import get_llm
    
    redis_status = "connected" if get_redis_client().is_connected else "disconnected"
    llm_status = "configured" if get_llm().providers else "not_configured"
    
    return HealthResponse(
        status="healthy",
        redis=redis_status,
        llm=llm_status,
    )
