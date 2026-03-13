# AI Tax Assistant - Quick Start Guide

## 🚀 5-Minute Setup

### Prerequisites
- Python 3.11+
- PostgreSQL running
- OpenAI or Anthropic API key

### Step 1: Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### Step 2: Configure Environment
Create `.env` file:
```bash
# LLM Provider (openai or anthropic)
LLM_PROVIDER=openai

# OpenAI Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4-turbo-preview

# Vector Database
CHROMA_PERSIST_DIR=./data/chroma
```

### Step 3: Run Migrations
```bash
alembic upgrade head
```

### Step 4: Initialize Knowledge Base
```bash
python scripts/init_knowledge_base.py
```

Expected output:
```
============================================================
AI Tax Assistant Knowledge Base Initialization
============================================================

Initializing Austrian tax law documents...
Initializing 2026 USP tax tables...
Initializing FAQ...

============================================================
✓ Knowledge base initialized successfully!
============================================================

Collections created:
  - austrian_tax_law (Austrian tax law documents)
  - usp_2026_tax_tables (2026 USP tax tables)
  - tax_faq (Common tax questions and answers)

The AI Tax Assistant is now ready to use.
```

### Step 5: Start Server
```bash
uvicorn app.main:app --reload
```

### Step 6: Test API
```bash
# Get auth token first
TOKEN=$(curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password"}' \
  | jq -r '.access_token')

# Send chat message
curl -X POST http://localhost:8000/api/v1/ai/chat \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Wie berechne ich meine Einkommensteuer?",
    "language": "de"
  }'
```

## 📚 Quick API Reference

### Send Message
```http
POST /api/v1/ai/chat
Authorization: Bearer {token}
Content-Type: application/json

{
  "message": "Your question here",
  "language": "de|en|zh"
}
```

### Get History
```http
GET /api/v1/ai/history?limit=50&offset=0
Authorization: Bearer {token}
```

### Clear History
```http
DELETE /api/v1/ai/history
Authorization: Bearer {token}
```

### Explain OCR
```http
POST /api/v1/ai/explain-ocr
Authorization: Bearer {token}
Content-Type: application/json

{
  "document_id": 123,
  "language": "de"
}
```

### Tax Optimization
```http
POST /api/v1/ai/suggest-optimization
Authorization: Bearer {token}
Content-Type: application/json

{
  "tax_year": 2026,
  "language": "en"
}
```

## 🧪 Quick Test

Run the demo script:
```bash
python examples/ai_assistant_demo.py
```

This will demonstrate:
- Basic tax questions (German, English, Chinese)
- OCR result explanation
- Tax optimization suggestions
- Multi-turn conversations
- Disclaimer verification

## 🔧 Troubleshooting

### "LLM provider not configured"
**Solution**: Set `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` in `.env`

### "ChromaDB collection not found"
**Solution**: Run `python scripts/init_knowledge_base.py`

### Slow responses
**Solution**: 
- Check LLM API status
- Use faster model (gpt-3.5-turbo)
- Implement caching

### Out of memory
**Solution**: 
- Increase container memory
- Use cloud vector database

## 📖 Documentation

- **Full Implementation Guide**: `AI_ASSISTANT_IMPLEMENTATION.md`
- **Module Documentation**: `docs/AI_ASSISTANT_MODULE.md`
- **Completion Summary**: `TASK_23_COMPLETION_SUMMARY.md`

## 🎯 Key Features

✅ Multi-language support (German, English, Chinese)
✅ RAG-based accurate responses
✅ Automatic disclaimer appending
✅ OCR result explanation
✅ Tax optimization suggestions
✅ Conversation history management
✅ GDPR compliant
✅ Steuerberatungsgesetz compliant

## 🔐 Compliance

Every response includes a disclaimer:
- German: "⚠️ Haftungsausschluss: Diese Antwort dient nur zu allgemeinen Informationszwecken..."
- English: "⚠️ Disclaimer: This response is for general information purposes only..."
- Chinese: "⚠️ 免责声明：本回答仅供一般性参考..."

## 💡 Usage Example

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
# Output includes tax calculation explanation + disclaimer
```

## 🚦 Production Checklist

Before deploying to production:

- [ ] Set production API keys
- [ ] Enable rate limiting (20 messages/hour recommended)
- [ ] Implement response caching
- [ ] Set up monitoring and logging
- [ ] Configure backup for ChromaDB data
- [ ] Test all languages (de, en, zh)
- [ ] Verify disclaimer in all responses
- [ ] Load test with concurrent users
- [ ] Set up cost alerts for LLM API usage

## 📞 Support

For issues or questions:
- Check logs: `docker-compose logs -f backend`
- Review API docs: `http://localhost:8000/docs`
- Run tests: `pytest tests/test_ai_assistant.py -v`

---

**Ready to use!** The AI Tax Assistant is now operational. 🎉
