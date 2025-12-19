# AI Customer Support Platform

A **scalable, document-aware AI customer support system** built to solve **real SaaS support problems** — not a generic chatbot.

The system answers **strictly from company PDFs**, classifies user intent, evaluates risk, and escalates to **available human agents only when required**.


## Key Features

- **Document-First Answers**: All responses come from uploaded client PDFs only
- **Per-Client Isolation**: Each client has their own vector store and document index
- **LangGraph Orchestration**: Strict state machine controlling the flow
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
## 🧪 Example Response
```json
{
  "reply": "Account deletion requests must be submitted to support as per the Terms.",
  "intent": "account_deletion",
  "confidence": 0.82,
  "escalated": false
}
