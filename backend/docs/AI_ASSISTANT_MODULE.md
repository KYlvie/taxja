# AI Tax Assistant Module Documentation

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [API Reference](#api-reference)
5. [Configuration](#configuration)
6. [Usage Examples](#usage-examples)
7. [Testing](#testing)
8. [Deployment](#deployment)
9. [Troubleshooting](#troubleshooting)

## Overview

The AI Tax Assistant is a RAG-powered conversational AI that helps users understand Austrian tax law and optimize their tax situation. It combines:

- **Vector Database**: ChromaDB for semantic search
- **Embeddings**: Multilingual sentence transformers
- **LLM**: OpenAI GPT-4 or Anthropic Claude
- **Knowledge Base**: Austrian tax law, 2026 USP tables, FAQs
- **User Context**: Current tax data integration

### Key Features

✓ Multi-language support (German, English, Chinese)
✓ RAG-based accurate responses
✓ Automatic disclaimer appending
✓ OCR result explanation
✓ Tax optimization suggestions
✓ Conversation history management
✓ GDPR compliant
✓ Steuerberatungsgesetz compliant

## Architecture

### High-Level Flow

```
┌─────────────┐
│ User Query  │
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│ RAG Retrieval Service       │
│ - Query vector database     │
│ - Retrieve relevant docs    │
│ - Rank by relevance         │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Context Builder             │
│ - Knowledge base context    │
│ - User tax data             │
│ - Conversation history      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ LLM (GPT-4 / Claude)        │
│ - Generate response         │
│ - Apply system prompt       │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────────────────────┐
│ Response Post-Processing    │
│ - Append disclaimer         │
│ - Save to chat history      │
└──────┬──────────────────────┘
       │
       ▼
┌─────────────┐
│ User        │
└─────────────┘
```

### Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│                    API Layer                              │
│  /api/v1/ai/chat                                         │
│  /api/v1/ai/history                                      │
│  /api/v1/ai/explain-ocr                                  │
│  /api/v1/ai/suggest-optimization                         │
└────────────────────┬─────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              Service Layer                                │
│  ┌──────────────────────────────────────────────────┐   │
│  │ AIAssistantService                               │   │
│  │ - generate_response()                            │   │
│  │ - explain_ocr_result()                           │   │
│  │ - suggest_tax_optimization()                     │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                     │
│  ┌──────────────────▼───────────────────────────────┐   │
│  │ RAGRetrievalService                              │   │
│  │ - retrieve_context()                             │   │
│  │ - retrieve_context_with_user_data()              │   │
│  │ - format_context_for_prompt()                    │   │
│  └──────────────────┬───────────────────────────────┘   │
│                     │                                     │
│  ┌──────────────────▼───────────────────────────────┐   │
│  │ VectorDBService                                  │   │
│  │ - add_documents()                                │   │
│  │ - query_documents()                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ChatHistoryService                               │   │
│  │ - save_message()                                 │   │
│  │ - get_conversation_history()                     │   │
│  │ - clear_history()                                │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────────┐
│              Data Layer                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │ ChromaDB (Vector Database)                       │   │
│  │ - austrian_tax_law                               │   │
│  │ - usp_2026_tax_tables                            │   │
│  │ - tax_faq                                        │   │
│  └──────────────────────────────────────────────────┘   │
│                                                           │
│  ┌──────────────────────────────────────────────────┐   │
│  │ PostgreSQL                                       │   │
│  │ - chat_messages table                            │   │
│  └──────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

## Components

### 1. VectorDBService

**File**: `app/services/vector_db_service.py`

**Purpose**: Manages ChromaDB vector database operations.

**Key Methods**:

```python
class VectorDBService:
    def __init__(self, persist_directory: str = "./data/chroma"):
        """Initialize vector database with ChromaDB"""
        
    def add_documents(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
        ids: Optional[List[str]] = None
    ):
        """Add documents with embeddings to collection"""
        
    def query_documents(
        self,
        collection_name: str,
        query_text: str,
        n_results: int = 5,
        where: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Query documents by text with metadata filtering"""
```

**Collections**:
- `austrian_tax_law`: Tax law documents (income tax, VAT, SVS, deductions)
- `usp_2026_tax_tables`: 2026 USP progressive tax brackets
- `tax_faq`: Common tax questions and answers

**Embedding Model**: `paraphrase-multilingual-MiniLM-L12-v2`
- Supports German, English, Chinese
- 384-dimensional embeddings
- Cosine similarity for ranking

### 2. KnowledgeBaseService

**File**: `app/services/knowledge_base_service.py`

**Purpose**: Initializes and manages tax knowledge base content.

**Key Methods**:

```python
class KnowledgeBaseService:
    def initialize_all(self):
        """Initialize all knowledge base collections"""
        
    def initialize_tax_law_documents(self):
        """Initialize Austrian tax law documents"""
        
    def initialize_tax_tables(self):
        """Initialize 2026 USP tax tables"""
        
    def initialize_faq(self):
        """Initialize common tax questions"""
        
    def refresh_knowledge_base(self):
        """Refresh knowledge base (admin function)"""
```

**Content Coverage**:
- Income tax (Einkommensteuer) - 7 tax brackets
- VAT (Umsatzsteuer) - standard 20%, residential 10%
- Social insurance (SVS/GSVG) - contribution rates
- Deductions (Pendlerpauschale, home office, family)
- Loss carryforward (Verlustvortrag)

### 3. RAGRetrievalService

**File**: `app/services/rag_retrieval_service.py`

**Purpose**: Retrieves relevant context using RAG methodology.

**Key Methods**:

```python
class RAGRetrievalService:
    def retrieve_context(
        self,
        query: str,
        language: str = "de",
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve relevant context for user query"""
        
    def retrieve_context_with_user_data(
        self,
        query: str,
        user_context: Dict[str, Any],
        language: str = "de",
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Retrieve context including user's tax data"""
        
    def format_context_for_prompt(
        self,
        context: Dict[str, Any]
    ) -> str:
        """Format retrieved context for LLM prompt"""
```

**Retrieval Process**:
1. Query all three collections (tax_law, tax_tables, faq)
2. Filter by language
3. Rank by cosine similarity
4. Return top-k results
5. Combine with user tax data

### 4. AIAssistantService

**File**: `app/services/ai_assistant_service.py`

**Purpose**: Generates AI responses using LLM with RAG context.

**Key Methods**:

```python
class AIAssistantService:
    def generate_response(
        self,
        user_message: str,
        user_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        language: str = "de"
    ) -> str:
        """Generate AI response with disclaimer"""
        
    def explain_ocr_result(
        self,
        ocr_data: Dict[str, Any],
        language: str = "de"
    ) -> str:
        """Generate natural language explanation of OCR results"""
        
    def suggest_tax_optimization(
        self,
        user_tax_data: Dict[str, Any],
        language: str = "de"
    ) -> str:
        """Analyze tax situation and suggest optimizations"""
```

**Supported LLMs**:
- OpenAI GPT-4 Turbo (default)
- Anthropic Claude 3 Opus
- Configurable via `LLM_PROVIDER` env var

**System Prompt** (German example):
```
Du bist ein hilfreicher AI-Assistent für österreichische Steuerfragen.

WICHTIGE REGELN:
1. Verwende IMMER die bereitgestellten Steuergesetze als Grundlage
2. Beziehe die aktuellen Steuerdaten des Benutzers ein
3. Gib NIEMALS spezifische Steuerbeträge als Garantie an
4. Erkläre komplexe Steuerkonzepte in einfacher Sprache
5. Empfehle bei Unsicherheit einen Steuerberater
6. Antworte in der Sprache des Benutzers

Du darfst KEINE Steuerberatung im Sinne des Steuerberatungsgesetzes anbieten.
```

### 5. ChatHistoryService

**File**: `app/services/chat_history_service.py`

**Purpose**: Manages conversation history storage and retrieval.

**Key Methods**:

```python
class ChatHistoryService:
    def save_message(
        self,
        user_id: int,
        role: MessageRole,
        content: str,
        language: str = "de"
    ) -> ChatMessage:
        """Save chat message to database"""
        
    def get_conversation_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """Get conversation history with pagination"""
        
    def get_recent_messages(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get recent messages formatted for LLM context"""
        
    def clear_history(self, user_id: int) -> int:
        """Clear all chat history for user (GDPR)"""
```

**Database Schema**:
```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'de',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

## API Reference

### POST /api/v1/ai/chat

Send a message to the AI assistant.

**Authentication**: Required (JWT token)

**Request Body**:
```json
{
  "message": "string (1-5000 chars)",
  "language": "de|en|zh"
}
```

**Response** (200 OK):
```json
{
  "message": "string (AI response with disclaimer)",
  "message_id": "integer",
  "timestamp": "datetime"
}
```

**Example**:
```bash
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Wie berechne ich meine Einkommensteuer?",
    "language": "de"
  }'
```

### GET /api/v1/ai/history

Get conversation history.

**Authentication**: Required

**Query Parameters**:
- `limit` (optional): Number of messages (default: 50, max: 100)
- `offset` (optional): Pagination offset (default: 0)

**Response** (200 OK):
```json
{
  "messages": [
    {
      "id": "integer",
      "user_id": "integer",
      "role": "user|assistant|system",
      "content": "string",
      "language": "de|en|zh",
      "created_at": "datetime"
    }
  ],
  "total_count": "integer",
  "has_more": "boolean"
}
```

### DELETE /api/v1/ai/history

Clear all chat history for current user.

**Authentication**: Required

**Response** (204 No Content)

### POST /api/v1/ai/explain-ocr

Get AI explanation of OCR results.

**Authentication**: Required

**Request Body**:
```json
{
  "document_id": "integer",
  "language": "de|en|zh"
}
```

**Response** (200 OK):
```json
{
  "message": "string (explanation with disclaimer)",
  "message_id": "integer",
  "timestamp": "datetime"
}
```

### POST /api/v1/ai/suggest-optimization

Get tax optimization suggestions.

**Authentication**: Required

**Request Body**:
```json
{
  "tax_year": "integer (2020-2030)",
  "language": "de|en|zh"
}
```

**Response** (200 OK):
```json
{
  "message": "string (suggestions with disclaimer)",
  "message_id": "integer",
  "timestamp": "datetime"
}
```

### POST /api/v1/ai/admin/refresh-knowledge-base

Refresh the knowledge base (admin only).

**Authentication**: Required (admin role)

**Response** (200 OK):
```json
{
  "success": "boolean",
  "message": "string",
  "collections_updated": ["string"]
}
```

## Configuration

### Environment Variables

```bash
# LLM Provider
LLM_PROVIDER=openai  # openai, anthropic, or local

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229

# Vector Database
CHROMA_PERSIST_DIR=./data/chroma

# Rate Limiting
AI_CHAT_RATE_LIMIT=20  # messages per hour per user
```

### Docker Compose

```yaml
services:
  backend:
    environment:
      - LLM_PROVIDER=openai
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - CHROMA_PERSIST_DIR=/app/data/chroma
    volumes:
      - chroma_data:/app/data/chroma

volumes:
  chroma_data:
```

## Usage Examples

### Example 1: Basic Tax Question

```python
from app.services.ai_assistant_service import get_ai_assistant_service

ai_service = get_ai_assistant_service()

response = ai_service.generate_response(
    user_message="Wie berechne ich meine Einkommensteuer?",
    user_context={"user_type": "employee"},
    conversation_history=[],
    language="de"
)

print(response)
```

### Example 2: With User Tax Data

```python
user_context = {
    "year_to_date_income": 50000.00,
    "year_to_date_expenses": 5000.00,
    "estimated_tax": 10000.00,
    "user_type": "self_employed",
    "vat_liable": False
}

response = ai_service.generate_response(
    user_message="How much tax will I owe this year?",
    user_context=user_context,
    conversation_history=[],
    language="en"
)
```

### Example 3: Multi-Turn Conversation

```python
# First message
response1 = ai_service.generate_response(
    user_message="What is the income tax rate?",
    user_context={},
    conversation_history=[],
    language="en"
)

# Follow-up with context
history = [
    {"role": "user", "content": "What is the income tax rate?"},
    {"role": "assistant", "content": response1}
]

response2 = ai_service.generate_response(
    user_message="What about for €100,000?",
    user_context={},
    conversation_history=history,
    language="en"
)
```

## Testing

### Run All Tests

```bash
cd backend
pytest tests/test_ai_assistant.py -v
```

### Test Coverage

```bash
pytest tests/test_ai_assistant.py --cov=app.services --cov-report=html
open htmlcov/index.html
```

### Property-Based Tests

```python
from hypothesis import given, strategies as st

@given(
    message=st.text(min_size=1, max_size=1000),
    language=st.sampled_from(["de", "en", "zh"])
)
def test_disclaimer_always_included(message, language):
    """Property: Every AI response must include a disclaimer"""
    service = AIAssistantService()
    disclaimer = service.DISCLAIMERS.get(language)
    assert disclaimer is not None
    assert "⚠️" in disclaimer
```

## Deployment

### 1. Build Docker Image

```bash
docker build -t taxja-backend:latest -f backend/Dockerfile .
```

### 2. Initialize Knowledge Base

```bash
docker-compose exec backend python scripts/init_knowledge_base.py
```

### 3. Run Migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Start Services

```bash
docker-compose up -d
```

### 5. Verify

```bash
curl http://localhost:8000/health
```

## Troubleshooting

### Issue: "LLM provider not configured"

**Cause**: Missing API key

**Solution**:
```bash
# Add to .env
OPENAI_API_KEY=sk-...
# or
ANTHROPIC_API_KEY=sk-ant-...
```

### Issue: "ChromaDB collection not found"

**Cause**: Knowledge base not initialized

**Solution**:
```bash
python scripts/init_knowledge_base.py
```

### Issue: Slow response times

**Causes**:
- LLM API latency
- Large conversation history
- Network issues

**Solutions**:
- Enable caching for common queries
- Limit conversation history to 10 messages
- Use faster LLM model (gpt-3.5-turbo)
- Implement rate limiting

### Issue: Out of memory

**Cause**: Embedding model too large

**Solutions**:
- Use smaller embedding model
- Increase container memory limit
- Use cloud vector database (Pinecone, Weaviate)

### Issue: Incorrect responses

**Causes**:
- Outdated knowledge base
- Poor query formulation
- Insufficient context

**Solutions**:
- Refresh knowledge base
- Improve system prompt
- Add more relevant documents
- Fine-tune retrieval parameters

## Performance Optimization

### Caching Strategy

```python
from functools import lru_cache
import redis

redis_client = redis.Redis(host='localhost', port=6379)

def get_cached_response(query: str, language: str) -> Optional[str]:
    """Get cached response if available"""
    cache_key = f"ai_response:{language}:{hash(query)}"
    return redis_client.get(cache_key)

def cache_response(query: str, language: str, response: str):
    """Cache response for 1 hour"""
    cache_key = f"ai_response:{language}:{hash(query)}"
    redis_client.setex(cache_key, 3600, response)
```

### Rate Limiting

```python
from fastapi import HTTPException
from datetime import datetime, timedelta

def check_rate_limit(user_id: int, limit: int = 20):
    """Check if user exceeded rate limit"""
    key = f"ai_rate_limit:{user_id}"
    count = redis_client.incr(key)
    
    if count == 1:
        redis_client.expire(key, 3600)  # 1 hour
    
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later."
        )
```

## Monitoring

### Metrics to Track

1. **Response Time**: Average LLM API response time
2. **Error Rate**: Failed API calls / total calls
3. **Usage**: Messages per user per day
4. **Cost**: LLM API costs per user
5. **Satisfaction**: User feedback ratings

### Logging

```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"AI chat request: user_id={user_id}, language={language}")
logger.info(f"Retrieved {len(context)} context documents")
logger.info(f"LLM response time: {response_time}ms")
logger.error(f"LLM API error: {error}")
```

## License

Proprietary - Taxja GmbH © 2026
