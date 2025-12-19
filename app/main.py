"""
FastAPI application entry point.
Document-Driven AI Support Platform.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings, ensure_directories
from app.api import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    print("🚀 Starting AI Support Platform...")
    
    # Ensure directories exist
    ensure_directories()
    print(f"📁 Data directory: {settings.DATA_DIR}")
    print(f"📁 Documents directory: {settings.DOCUMENTS_DIR}")
    
    # Pre-load embedding model (singleton initialization)
    try:
        from app.rag.embeddings import get_embedding_model
        get_embedding_model()
    except Exception as e:
        print(f"⚠️ Embedding model load deferred: {e}")
    
    # Initialize LLM chain
    try:
        from app.llm import get_llm
        get_llm()
    except Exception as e:
        print(f"⚠️ LLM initialization deferred: {e}")
    
    # Initialize Redis connection
    try:
        from app.cache import get_redis_client
        get_redis_client()
    except Exception as e:
        print(f"⚠️ Redis connection deferred: {e}")
    
    print("✅ Platform ready")
    print(f"📖 API docs: http://localhost:8000/docs")
    
    yield
    
    # Shutdown
    print("👋 Shutting down AI Support Platform...")


# Create FastAPI app
app = FastAPI(
    title="AI Support Platform",
    description="""
## Document-Driven Customer Support API

This platform provides AI-powered customer support that is **strictly grounded in client-provided documents**.

### Key Features:
- **Document-First Answers**: All responses come from uploaded PDFs only
- **Per-Client Isolation**: Each client has their own document store and vector index
- **Smart Escalation**: High-risk actions automatically route to human agents
- **Response Caching**: Identical queries return cached responses instantly
- **Intent Classification**: Automatic intent detection with confidence scoring

### How It Works:
1. Upload PDFs to `data/documents/{client_id}/`
2. Call `POST /ingest/{client_id}` to process documents
3. Use `POST /chat` to interact with the support agent

### Anti-Hallucination Safeguards:
- If no relevant document context is found, returns: "This information is not available in the provided documentation."
- Never uses general knowledge or makes up information
- Enforces maximum response length and factual tone
    """,
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


# Root endpoint
@app.get("/", tags=["Root"])
def root():
    """Root endpoint with platform info."""
    return {
        "name": "AI Support Platform",
        "version": "2.0.0",
        "description": "Document-driven customer support API",
        "docs": "/docs",
        "health": "/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.ENV == "development",
    )
