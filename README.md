# AI Customer Support Platform

A **document-driven** customer support system that answers queries strictly from client-provided documentation. No generic chatbot behavior - all responses are grounded in uploaded PDFs.

## Key Features

- **Document-First Answers**: All responses come from uploaded client PDFs only
- **Per-Client Isolation**: Each client has their own vector store and document index
- **LangGraph Orchestration**: Strict state machine controlling the flow
- **Redis Caching**: Query→response caching with document versioning
- **Smart Escalation**: High-risk intents with high confidence route to humans
- **Local Embeddings**: Uses `all-MiniLM-L6-v2` (no OpenAI dependency)
- **Anti-Hallucination**: Returns "This information is not available in the provided documentation." when no relevant docs found

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
Create a `.env` file:
```env
# LLM Providers (at least one required)
GEMINI_API_KEY=your_gemini_key
OPENROUTER_API_KEY=your_openrouter_key

# Redis (optional but recommended)
REDIS_HOST=localhost
REDIS_PORT=6379

# LangSmith Tracing (optional)
LANGSMITH_API_KEY=your_langsmith_key
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=ai-support-platform
```

### 3. Add Documents
Place PDF files in the client directory:
```
data/documents/{client_id}/
├── product_guide.pdf
├── faq.pdf
└── policies.pdf
```

### 4. Run the Server
```bash
uvicorn app.main:app --reload
```

### 5. Ingest Documents
```bash
curl -X POST http://localhost:8000/ingest/demo_client
```

### 6. Chat
```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"client_id": "demo_client", "user_id": "user123", "message": "How do I reset my password?"}'
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Process support message |
| POST | `/ingest/{client_id}` | Ingest client documents |
| GET | `/documents/{client_id}/status` | Get document store status |
| POST | `/agents/register` | Register human agent |
| PUT | `/agents/{agent_id}/status` | Update agent status |
| GET | `/health` | Health check |
| GET | `/metrics` | Platform metrics |

## Architecture

```
app/
├── main.py           # FastAPI entry point
├── api.py            # API routes
├── agent.py          # LangGraph orchestration
├── config.py         # Settings
├── rag/              # Document retrieval
│   ├── embeddings.py # Local embedding model
│   ├── vectorstore.py# FAISS per-client stores
│   ├── ingest.py     # PDF processing
│   └── retriever.py  # Document retrieval
├── cache/            # Redis caching
│   ├── redis_client.py
│   └── response_cache.py
├── intent/           # Intent classification
│   ├── classifier.py
│   └── constants.py
├── escalation/       # Human handoff
│   ├── router.py
│   └── human_pool.py
├── llm/              # LLM providers
│   ├── models.py
│   └── fallback.py
└── monitoring/       # Observability
    └── langsmith.py
```

## LangGraph Flow

```
intent_classification → cache_check → [cached?]
                                         ↓ no
                              document_retrieval
                                         ↓
                              relevance_validation → [clarify?]
                                         ↓ no
                              confidence_scoring
                                         ↓
                              escalation_decision → [escalate?]
                                    ↓ no              ↓ yes
                              answer_generation   escalation_response
                                         ↓
                                  cache_response → END
```

## Docker

```bash
# Build
docker build -t ai-support-platform .

# Run with Redis
docker-compose up
```

## Docker Compose (with Redis)

```yaml
version: '3.8'
services:
  api:
    build: .
    ports:
      - "8000:8000"
    environment:
      - REDIS_HOST=redis
      - GEMINI_API_KEY=${GEMINI_API_KEY}
    volumes:
      - ./data:/app/data
    depends_on:
      - redis

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
```

## Escalation Rules

- **High-risk intents**: `account_deletion`, `billing_refund`, `chargeback`, `data_export`
- **Escalation trigger**: High-risk + actionable + confidence ≥ 0.75
- **Keywords alone don't escalate**: "refund" or "delete" in questions won't trigger escalation