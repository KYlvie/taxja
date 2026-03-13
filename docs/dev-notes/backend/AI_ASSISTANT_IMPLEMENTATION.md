# AI Tax Assistant Implementation

## Overview

The AI Tax Assistant is a RAG (Retrieval-Augmented Generation) powered chatbot that helps users understand Austrian tax law and optimize their tax situation. It combines a vector database knowledge base with LLM integration to provide accurate, context-aware responses.

## Architecture

```
User Question
     ↓
RAG Retrieval Service
     ↓
Vector Database (ChromaDB)
     ├── Austrian Tax Law
     ├── 2026 USP Tax Tables
     └── Tax FAQs
     ↓
Context + User Tax Data
     ↓
LLM (OpenAI GPT-4 / Anthropic Claude)
     ↓
Response + Disclaimer
     ↓
Chat History Storage
```

## Components

### 1. Vector Database Service (`vector_db_service.py`)

**Purpose**: Manages ChromaDB vector database for storing and retrieving document embeddings.

**Key Features**:
- Uses `paraphrase-multilingual-MiniLM-L12-v2` for embeddings (supports German, English, Chinese)
- Three collections:
  - `austrian_tax_law`: Tax law documents
  - `usp_2026_tax_tables`: 2026 tax rate tables
  - `tax_faq`: Common tax questions and answers
- Cosine similarity search for relevance ranking

**Methods**:
- `add_documents()`: Add documents with embeddings
- `query_documents()`: Query by text with metadata filtering
- `reset_collection()`: Refresh collection (admin function)

### 2. Knowledge Base Service (`knowledge_base_service.py`)

**Purpose**: Initializes and manages the tax knowledge base.

**Content**:
- **Tax Law Documents**: Income tax, VAT, SVS, deductions, loss carryforward
- **Tax Tables**: 2026 USP progressive tax brackets
- **FAQs**: Common questions in German, English, Chinese

**Methods**:
- `initialize_all()`: Initialize all collections
- `refresh_knowledge_base()`: Update knowledge base (admin function)

### 3. RAG Retrieval Service (`rag_retrieval_service.py`)

**Purpose**: Retrieves relevant context for user queries using RAG.

**Process**:
1. Query all three collections with user question
2. Filter by language
3. Rank results by relevance (cosine distance)
4. Return top-k results
5. Combine with user's current tax data

**Methods**:
- `retrieve_context()`: Get relevant documents
- `retrieve_context_with_user_data()`: Include user tax data
- `format_context_for_prompt()`: Format for LLM prompt

### 4. AI Assistant Service (`ai_assistant_service.py`)

**Purpose**: Generates AI responses using LLM with RAG context.

**Supported LLMs**:
- OpenAI GPT-4 (default)
- Anthropic Claude
- Configurable via `LLM_PROVIDER` environment variable

**Key Features**:
- Multi-language support (German, English, Chinese)
- Automatic disclaimer appending (all languages)
- Conversation history context (last 10 messages)
- User tax data integration
- OCR result explanation
- Tax optimization suggestions

**Disclaimer** (appended to every response):
- German: "⚠️ Haftungsausschluss: Diese Antwort dient nur zu allgemeinen Informationszwecken..."
- English: "⚠️ Disclaimer: This response is for general information purposes only..."
- Chinese: "⚠️ 免责声明：本回答仅供一般性参考..."

**Methods**:
- `generate_response()`: Main response generation
- `explain_ocr_result()`: Explain OCR extracted data
- `suggest_tax_optimization()`: Provide optimization suggestions

### 5. Chat History Service (`chat_history_service.py`)

**Purpose**: Manages conversation history storage and retrieval.

**Features**:
- Store messages in PostgreSQL
- Retrieve conversation history with pagination
- Format messages for LLM context
- Clear history (GDPR compliance)
- Search messages by content

**Methods**:
- `save_message()`: Save user/assistant message
- `get_conversation_history()`: Get paginated history
- `get_recent_messages()`: Get recent messages for LLM
- `clear_history()`: Delete all user messages
- `delete_old_messages()`: Cleanup task (90 days)

## API Endpoints

### POST `/api/v1/ai/chat`

Send a message to the AI assistant.

**Request**:
```json
{
  "message": "Wie berechne ich meine Einkommensteuer?",
  "language": "de"
}
```

**Response**:
```json
{
  "message": "Die Einkommensteuer wird progressiv berechnet...\n\n⚠️ Haftungsausschluss: ...",
  "message_id": 123,
  "timestamp": "2026-03-04T10:30:00Z"
}
```

### GET `/api/v1/ai/history`

Get conversation history.

**Query Parameters**:
- `limit`: Number of messages (default: 50)
- `offset`: Pagination offset (default: 0)

**Response**:
```json
{
  "messages": [
    {
      "id": 123,
      "user_id": 1,
      "role": "user",
      "content": "How is income tax calculated?",
      "language": "en",
      "created_at": "2026-03-04T10:30:00Z"
    },
    {
      "id": 124,
      "user_id": 1,
      "role": "assistant",
      "content": "Income tax is calculated progressively...",
      "language": "en",
      "created_at": "2026-03-04T10:30:15Z"
    }
  ],
  "total_count": 50,
  "has_more": false
}
```

### DELETE `/api/v1/ai/history`

Clear all chat history for the current user.

**Response**: 204 No Content

### POST `/api/v1/ai/explain-ocr`

Get AI explanation of OCR results.

**Request**:
```json
{
  "document_id": 456,
  "language": "de"
}
```

**Response**:
```json
{
  "message": "Dieses Dokument ist eine Rechnung von BILLA...",
  "message_id": 125,
  "timestamp": "2026-03-04T10:35:00Z"
}
```

### POST `/api/v1/ai/suggest-optimization`

Get tax optimization suggestions.

**Request**:
```json
{
  "tax_year": 2026,
  "language": "en"
}
```

**Response**:
```json
{
  "message": "Based on your tax situation, here are some optimization suggestions...",
  "message_id": 126,
  "timestamp": "2026-03-04T10:40:00Z"
}
```

### POST `/api/v1/ai/admin/refresh-knowledge-base` (Admin Only)

Refresh the knowledge base.

**Response**:
```json
{
  "success": true,
  "message": "Knowledge base refreshed successfully",
  "collections_updated": [
    "austrian_tax_law",
    "usp_2026_tax_tables",
    "tax_faq"
  ]
}
```

## Database Schema

### `chat_messages` Table

```sql
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    role VARCHAR(20) NOT NULL,  -- 'user', 'assistant', 'system'
    content TEXT NOT NULL,
    language VARCHAR(5) NOT NULL DEFAULT 'de',  -- 'de', 'en', 'zh'
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_chat_messages_user_id ON chat_messages(user_id);
CREATE INDEX idx_chat_messages_created_at ON chat_messages(created_at);
```

## Configuration

### Environment Variables

```bash
# LLM Provider (openai, anthropic, or local)
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo-preview

# Anthropic Configuration
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-opus-20240229

# Vector Database
CHROMA_PERSIST_DIR=./data/chroma
```

## Setup Instructions

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Set Environment Variables

Create `.env` file:
```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key_here
```

### 3. Run Database Migrations

```bash
alembic upgrade head
```

### 4. Initialize Knowledge Base

```bash
python scripts/init_knowledge_base.py
```

This will:
- Create ChromaDB collections
- Index Austrian tax law documents
- Index 2026 USP tax tables
- Index common tax FAQs

### 5. Start the Server

```bash
uvicorn app.main:app --reload
```

## Testing

### Run All Tests

```bash
pytest tests/test_ai_assistant.py -v
```

### Test Coverage

```bash
pytest tests/test_ai_assistant.py --cov=app.services --cov-report=html
```

### Property-Based Tests

The implementation includes property-based tests using Hypothesis:

1. **Disclaimer Always Included**: Every AI response must include a disclaimer
2. **Multi-Language Disclaimer**: Disclaimer must be available in all supported languages

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
# Output: "Die Einkommensteuer wird progressiv berechnet...
#          ⚠️ Haftungsausschluss: ..."
```

### Example 2: OCR Explanation

```python
ocr_data = {
    "document_type": "receipt",
    "extracted_data": {
        "merchant": "BILLA",
        "amount": 45.50,
        "items": ["Milk", "Bread", "Pens"]
    },
    "confidence_score": 0.85
}

explanation = ai_service.explain_ocr_result(ocr_data, language="en")
print(explanation)
# Output: "This receipt from BILLA shows groceries and office supplies.
#          The pens are deductible as business expenses...
#          ⚠️ Disclaimer: ..."
```

### Example 3: Tax Optimization

```python
user_tax_data = {
    "year_to_date_income": 60000.00,
    "year_to_date_expenses": 5000.00,
    "estimated_tax": 12000.00,
    "user_type": "self_employed"
}

suggestions = ai_service.suggest_tax_optimization(user_tax_data, language="en")
print(suggestions)
# Output: "Based on your tax situation, here are some optimization suggestions:
#          1. Consider claiming commuting allowance...
#          2. Maximize home office deduction...
#          ⚠️ Disclaimer: ..."
```

## Compliance and Legal Considerations

### Steuerberatungsgesetz Compliance

The AI Assistant is designed to comply with Austrian Steuerberatungsgesetz (Tax Advisory Act):

1. **No Tax Advice**: System explicitly states it does not provide tax advice
2. **Disclaimer Required**: Every response includes a disclaimer
3. **Reference System**: Positioned as a reference tool, not a tax advisor
4. **Steuerberater Recommendation**: Complex cases are referred to tax advisors

### GDPR Compliance

1. **Data Minimization**: Only necessary data is stored
2. **Right to Erasure**: Users can delete all chat history
3. **Data Portability**: Chat history can be exported
4. **Retention Policy**: Old messages are automatically deleted after 90 days

### Disclaimer Text

The disclaimer is appended to every AI response in all languages:

**German**:
> ⚠️ **Haftungsausschluss**: Diese Antwort dient nur zu allgemeinen Informationszwecken und stellt keine Steuerberatung oder formelle Empfehlung dar. Bitte verwenden Sie FinanzOnline für die endgültige Steuererklärung. Bei komplexen Situationen konsultieren Sie bitte einen Steuerberater.

**English**:
> ⚠️ **Disclaimer**: This response is for general information purposes only and does not constitute tax advice or formal recommendation. Please use FinanzOnline for final tax filing. For complex situations, please consult a Steuerberater.

**Chinese**:
> ⚠️ **免责声明**：本回答仅供一般性参考，不构成税务咨询或正式建议。请以FinanzOnline最终结果为准。复杂情况请咨询Steuerberater。

## Performance Considerations

### Vector Database

- **Embedding Model**: `paraphrase-multilingual-MiniLM-L12-v2` (420MB)
- **Query Time**: ~50-100ms for 5 results
- **Storage**: ~10MB for initial knowledge base

### LLM API Calls

- **OpenAI GPT-4**: ~2-5 seconds per response
- **Anthropic Claude**: ~2-4 seconds per response
- **Token Usage**: ~500-1000 tokens per response

### Optimization Strategies

1. **Caching**: Cache common questions and responses in Redis
2. **Rate Limiting**: Limit API calls per user (e.g., 20 per hour)
3. **Async Processing**: Use Celery for batch operations
4. **Context Pruning**: Limit conversation history to last 10 messages

## Monitoring and Logging

### Metrics to Track

1. **Response Time**: Average LLM response time
2. **Error Rate**: Failed API calls
3. **Usage**: Messages per user per day
4. **Cost**: LLM API costs per user
5. **Satisfaction**: User feedback on responses

### Logging

All AI interactions are logged:
- User questions
- Retrieved context
- LLM responses
- Errors and exceptions

## Future Enhancements

### Planned Features

1. **Voice Input**: Speech-to-text for mobile users
2. **Document Upload**: Upload tax documents directly in chat
3. **Proactive Suggestions**: Notify users of tax-saving opportunities
4. **Multi-Turn Conversations**: Better context tracking across sessions
5. **Fine-Tuned Model**: Train custom model on Austrian tax law

### Knowledge Base Expansion

1. **Historical Tax Data**: Add tax tables for previous years
2. **Case Studies**: Add real-world tax scenarios
3. **BMF Guidelines**: Index official BMF publications
4. **Court Decisions**: Add relevant tax court rulings

## Troubleshooting

### Common Issues

**Issue**: "LLM provider not configured"
- **Solution**: Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`

**Issue**: "ChromaDB collection not found"
- **Solution**: Run `python scripts/init_knowledge_base.py`

**Issue**: "Slow response times"
- **Solution**: Check LLM API status, consider caching common queries

**Issue**: "Out of memory"
- **Solution**: Reduce embedding model size or use cloud vector database

## Support

For issues or questions:
1. Check logs: `docker-compose logs -f backend`
2. Review API documentation: `http://localhost:8000/docs`
3. Contact: support@taxja.at

## License

Proprietary - Taxja GmbH © 2026
