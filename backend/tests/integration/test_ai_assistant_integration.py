"""
Integration tests for AI Tax Assistant.

Tests the complete AI Assistant workflow including:
- Chat message flow
- RAG retrieval
- Response generation
- Disclaimer inclusion
- Multi-language support
- OCR explanation
- Tax optimization suggestions

Requirements validated: 38.1, 38.2, 38.3, 38.4, 38.5, 38.6, 38.7, 38.8
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
from decimal import Decimal


class TestAIChatMessageFlow:
    """Test AI chat message flow and conversation management"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_send_chat_message_and_get_response(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test sending a chat message and receiving AI response.
        
        Requirements: 38.1, 38.2, 38.3
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Test context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "This is a test AI response about Austrian taxes."
        mock_openai.return_value = mock_response
        
        # Send chat message
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What is the income tax rate in Austria?",
                "language": "en"
            }
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "message_id" in data
        assert "timestamp" in data
        assert "This is a test AI response" in data["message"]
        
        # Verify disclaimer is included
        assert "⚠️" in data["message"]
        assert "Disclaimer" in data["message"]
        
        # Verify RAG was called
        mock_rag_service.retrieve_context_with_user_data.assert_called_once()
        
        # Verify OpenAI was called
        mock_openai.assert_called_once()
    
    def test_chat_message_saves_to_history(
        self,
        authenticated_client,
        db
    ):
        """
        Test that chat messages are saved to conversation history.
        
        Requirements: 38.5
        """
        from app.models.chat_message import ChatMessage
        
        with patch('app.services.ai_assistant_service.get_rag_retrieval_service'), \
             patch('app.services.ai_assistant_service.openai.chat.completions.create') as mock_openai:
            
            # Setup mock
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "AI response"
            mock_openai.return_value = mock_response
            
            # Send message
            authenticated_client.post(
                "/api/v1/ai/chat",
                json={
                    "message": "Test question",
                    "language": "de"
                }
            )
            
            # Verify messages saved
            messages = db.query(ChatMessage).all()
            assert len(messages) == 2  # User message + Assistant response
            
            # Verify user message
            user_msg = messages[0]
            assert user_msg.role.value == "user"
            assert user_msg.content == "Test question"
            assert user_msg.language == "de"
            
            # Verify assistant message
            assistant_msg = messages[1]
            assert assistant_msg.role.value == "assistant"
            assert "AI response" in assistant_msg.content
            assert "⚠️" in assistant_msg.content  # Disclaimer

    
    def test_get_conversation_history(
        self,
        authenticated_client,
        db
    ):
        """
        Test retrieving conversation history.
        
        Requirements: 38.5
        """
        from app.models.chat_message import ChatMessage, MessageRole
        from app.models.user import User
        
        # Get test user
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        
        # Create some chat history
        messages_data = [
            ("user", "First question"),
            ("assistant", "First answer"),
            ("user", "Second question"),
            ("assistant", "Second answer")
        ]
        
        for role, content in messages_data:
            msg = ChatMessage(
                user_id=user.id,
                role=MessageRole(role),
                content=content,
                language="de",
                created_at=datetime.utcnow()
            )
            db.add(msg)
        db.commit()
        
        # Get history
        response = authenticated_client.get("/api/v1/ai/history")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "messages" in data
        assert "total_count" in data
        assert "has_more" in data
        
        assert len(data["messages"]) == 4
        assert data["total_count"] == 4
        assert data["has_more"] is False
        
        # Verify chronological order (oldest first)
        assert data["messages"][0]["content"] == "First question"
        assert data["messages"][1]["content"] == "First answer"
    
    def test_clear_conversation_history(
        self,
        authenticated_client,
        db
    ):
        """
        Test clearing conversation history.
        
        Requirements: 38.6
        """
        from app.models.chat_message import ChatMessage, MessageRole
        from app.models.user import User
        
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        
        # Create chat history
        for i in range(5):
            msg = ChatMessage(
                user_id=user.id,
                role=MessageRole.USER,
                content=f"Message {i}",
                language="de"
            )
            db.add(msg)
        db.commit()
        
        # Verify messages exist
        count_before = db.query(ChatMessage).filter(ChatMessage.user_id == user.id).count()
        assert count_before == 5
        
        # Clear history
        response = authenticated_client.delete("/api/v1/ai/history")
        
        assert response.status_code == 204
        
        # Verify messages deleted
        count_after = db.query(ChatMessage).filter(ChatMessage.user_id == user.id).count()
        assert count_after == 0



class TestRAGRetrieval:
    """Test RAG (Retrieval-Augmented Generation) functionality"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_rag_retrieves_relevant_context(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test that RAG retrieves relevant context from knowledge base.
        
        Requirements: 38.2
        """
        # Setup RAG mock with relevant documents
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [
                {
                    "document": "Austrian income tax uses progressive rates from 0% to 55%",
                    "metadata": {"source": "tax_law", "year": 2026},
                    "distance": 0.15,
                    "collection": "tax_law"
                },
                {
                    "document": "Exemption amount for 2026 is €13,539",
                    "metadata": {"source": "usp_2026"},
                    "distance": 0.22,
                    "collection": "tax_tables"
                }
            ],
            "user_data": {
                "year_to_date_income": 45000.00,
                "user_type": "employee"
            }
        }
        mock_rag_service.format_context_for_prompt.return_value = (
            "=== Relevant Tax Law Information ===\n"
            "[Source 1]: Austrian income tax uses progressive rates from 0% to 55%\n"
            "[Source 2]: Exemption amount for 2026 is €13,539\n\n"
            "=== User's Current Tax Situation ===\n"
            "Year-to-date income: €45,000.00\n"
            "User type: employee"
        )
        mock_get_rag.return_value = mock_rag_service
        
        # Setup OpenAI mock
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Based on the tax law, your income is taxed progressively."
        mock_openai.return_value = mock_response
        
        # Send message
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "How is my income taxed?",
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        
        # Verify RAG was called with correct parameters
        call_args = mock_rag_service.retrieve_context_with_user_data.call_args
        assert call_args[1]["query"] == "How is my income taxed?"
        assert call_args[1]["language"] == "en"
        assert "user_context" in call_args[1]
        
        # Verify context was formatted
        mock_rag_service.format_context_for_prompt.assert_called_once()
        
        # Verify OpenAI received the context
        openai_call_args = mock_openai.call_args
        messages = openai_call_args[1]["messages"]
        
        # Find user message with context
        user_message = next(msg for msg in messages if msg["role"] == "user")
        assert "Relevant Tax Law Information" in user_message["content"]
        assert "progressive rates" in user_message["content"]
        assert "User's Current Tax Situation" in user_message["content"]

    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_rag_includes_user_tax_data(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test that RAG includes user's current tax data in context.
        
        Requirements: 38.2
        """
        from app.models.transaction import Transaction
        from app.models.user import User
        
        # Create some transactions for the user
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        
        transactions = [
            Transaction(
                user_id=user.id,
                type="income",
                amount=Decimal("3500.00"),
                date=datetime(2026, 1, 31).date(),
                description="Salary",
                category="employment_income"
            ),
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("150.00"),
                date=datetime(2026, 1, 15).date(),
                description="Office supplies",
                category="office_supplies",
                is_deductible=True
            )
        ]
        
        for txn in transactions:
            db.add(txn)
        db.commit()
        
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Response"
        mock_openai.return_value = mock_response
        
        # Send message
        authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What's my tax situation?",
                "language": "en"
            }
        )
        
        # Verify user context was passed to RAG
        call_args = mock_rag_service.retrieve_context_with_user_data.call_args
        user_context = call_args[1]["user_context"]
        
        assert "year_to_date_income" in user_context
        assert "year_to_date_expenses" in user_context
        assert "user_type" in user_context
        assert user_context["user_type"] == "employee"



class TestResponseGeneration:
    """Test AI response generation with LLM"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_response_generation_with_openai(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test response generation using OpenAI.
        
        Requirements: 38.2, 38.3
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "The Austrian tax system uses progressive rates."
        mock_openai.return_value = mock_response
        
        # Send message
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Explain Austrian taxes",
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        
        # Verify OpenAI was called with correct parameters
        call_args = mock_openai.call_args
        assert call_args[1]["model"] is not None
        assert "messages" in call_args[1]
        
        messages = call_args[1]["messages"]
        
        # Verify system prompt
        system_msg = next(msg for msg in messages if msg["role"] == "system")
        assert "AI assistant" in system_msg["content"] or "AI-Assistent" in system_msg["content"]
        assert "tax" in system_msg["content"].lower()
        
        # Verify user message
        user_msg = next(msg for msg in messages if msg["role"] == "user")
        assert "Explain Austrian taxes" in user_msg["content"]
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_response_includes_conversation_history(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test that conversation history is included in LLM context.
        
        Requirements: 38.5
        """
        from app.models.chat_message import ChatMessage, MessageRole
        from app.models.user import User
        
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        
        # Create previous conversation
        previous_messages = [
            ChatMessage(
                user_id=user.id,
                role=MessageRole.USER,
                content="What is the exemption amount?",
                language="en"
            ),
            ChatMessage(
                user_id=user.id,
                role=MessageRole.ASSISTANT,
                content="The exemption amount for 2026 is €13,539.",
                language="en"
            )
        ]
        
        for msg in previous_messages:
            db.add(msg)
        db.commit()
        
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Follow-up response"
        mock_openai.return_value = mock_response
        
        # Send follow-up message
        authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "How is that calculated?",
                "language": "en"
            }
        )
        
        # Verify conversation history was included
        call_args = mock_openai.call_args
        messages = call_args[1]["messages"]
        
        # Should have: system + previous user + previous assistant + current user
        assert len(messages) >= 4
        
        # Verify previous messages are included
        message_contents = [msg["content"] for msg in messages]
        assert any("exemption amount" in content for content in message_contents)
        assert any("€13,539" in content for content in message_contents)



class TestDisclaimerInclusion:
    """Test that disclaimer is always included in AI responses"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_disclaimer_included_in_german_response(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test disclaimer is included in German responses.
        
        Requirements: 38.4
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Die Einkommensteuer wird progressiv berechnet."
        mock_openai.return_value = mock_response
        
        # Send message in German
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Wie funktioniert die Einkommensteuer?",
                "language": "de"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify German disclaimer
        assert "⚠️" in data["message"]
        assert "Haftungsausschluss" in data["message"]
        assert "Steuerberatung" in data["message"]
        assert "FinanzOnline" in data["message"]
        assert "Steuerberater" in data["message"]
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_disclaimer_included_in_english_response(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test disclaimer is included in English responses.
        
        Requirements: 38.4
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Income tax is calculated progressively."
        mock_openai.return_value = mock_response
        
        # Send message in English
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "How does income tax work?",
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify English disclaimer
        assert "⚠️" in data["message"]
        assert "Disclaimer" in data["message"]
        assert "tax advice" in data["message"]
        assert "FinanzOnline" in data["message"]
        assert "Steuerberater" in data["message"]

    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_disclaimer_included_in_chinese_response(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test disclaimer is included in Chinese responses.
        
        Requirements: 38.4
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "所得税采用累进税率计算。"
        mock_openai.return_value = mock_response
        
        # Send message in Chinese
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "所得税如何计算？",
                "language": "zh"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Chinese disclaimer
        assert "⚠️" in data["message"]
        assert "免责声明" in data["message"]
        assert "税务咨询" in data["message"]
        assert "FinanzOnline" in data["message"]
        assert "Steuerberater" in data["message"]
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_disclaimer_always_appended_regardless_of_content(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test disclaimer is appended even if AI response is short or simple.
        
        Requirements: 38.4
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        # Test with very short response
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Yes."
        mock_openai.return_value = mock_response
        
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Is VAT applicable?",
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Even short responses must have disclaimer
        assert "Yes." in data["message"]
        assert "⚠️" in data["message"]
        assert "Disclaimer" in data["message"]
        
        # Verify disclaimer comes after the response
        assert data["message"].index("Yes.") < data["message"].index("⚠️")



class TestOCRExplanation:
    """Test AI-powered OCR result explanation"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_explain_ocr_result(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        document_with_ocr
    ):
        """
        Test AI explanation of OCR results.
        
        Requirements: 38.7
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "This is a grocery receipt from BILLA. "
            "The total amount is €8.50. "
            "Groceries are generally not tax deductible unless you are self-employed "
            "and can prove they are business expenses."
        )
        mock_openai.return_value = mock_response
        
        # Request OCR explanation
        response = authenticated_client.post(
            "/api/v1/ai/explain-ocr",
            json={
                "document_id": document_with_ocr["id"],
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify explanation content
        assert "message" in data
        assert "BILLA" in data["message"] or "grocery" in data["message"].lower()
        
        # Verify disclaimer included
        assert "⚠️" in data["message"]
        assert "Disclaimer" in data["message"]
        
        # Verify RAG was called with OCR context
        call_args = mock_rag_service.retrieve_context_with_user_data.call_args
        user_context = call_args[1]["user_context"]
        assert "ocr_result" in user_context
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_explain_ocr_with_deductibility_analysis(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        invoice_ocr_data
    ):
        """
        Test OCR explanation includes deductibility analysis.
        
        Requirements: 38.7
        """
        from app.models.document import Document
        
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "This is an invoice for office supplies totaling €120.00 with €20.00 VAT (20%). "
            "Office supplies are tax deductible for self-employed individuals and businesses. "
            "You can deduct the full amount as a business expense, and the VAT can be claimed "
            "as input VAT if you are VAT-liable."
        )
        mock_openai.return_value = mock_response
        
        # Request explanation
        response = authenticated_client.post(
            "/api/v1/ai/explain-ocr",
            json={
                "document_id": invoice_ocr_data["document_id"],
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify deductibility mentioned
        assert "deduct" in data["message"].lower()
        assert "VAT" in data["message"] or "tax" in data["message"].lower()

    
    def test_explain_ocr_document_not_found(
        self,
        authenticated_client
    ):
        """
        Test OCR explanation with non-existent document.
        
        Requirements: 38.7
        """
        response = authenticated_client.post(
            "/api/v1/ai/explain-ocr",
            json={
                "document_id": 99999,
                "language": "en"
            }
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestTaxOptimizationSuggestions:
    """Test AI-powered tax optimization suggestions"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_suggest_tax_optimization(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test AI tax optimization suggestions.
        
        Requirements: 38.8
        """
        from app.models.transaction import Transaction
        from app.models.user import User
        
        # Create transactions for user
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        
        transactions = [
            Transaction(
                user_id=user.id,
                type="income",
                amount=Decimal("50000.00"),
                date=datetime(2026, 1, 31).date(),
                description="Annual income",
                category="employment_income"
            ),
            Transaction(
                user_id=user.id,
                type="expense",
                amount=Decimal("500.00"),
                date=datetime(2026, 1, 15).date(),
                description="Business expense",
                category="office_supplies",
                is_deductible=True
            )
        ]
        
        for txn in transactions:
            db.add(txn)
        db.commit()
        
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "Based on your income of €50,000, here are some optimization suggestions:\n\n"
            "1. Commuting Allowance: If you commute more than 20km to work, "
            "you may be eligible for Pendlerpauschale.\n"
            "2. Home Office Deduction: You can claim €300/year for home office expenses.\n"
            "3. Consider tracking all deductible expenses carefully to maximize deductions."
        )
        mock_openai.return_value = mock_response
        
        # Request optimization suggestions
        response = authenticated_client.post(
            "/api/v1/ai/suggest-optimization",
            json={
                "tax_year": 2026,
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify suggestions content
        assert "message" in data
        assert "optimization" in data["message"].lower() or "suggestion" in data["message"].lower()
        
        # Verify disclaimer included
        assert "⚠️" in data["message"]
        assert "Disclaimer" in data["message"]

    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_optimization_suggestions_with_user_context(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test optimization suggestions include user's specific tax context.
        
        Requirements: 38.8
        """
        from app.models.user import User
        
        # Update user with commuting info
        user = db.query(User).filter(User.email == "testuser@example.com").first()
        user.commuting_distance_km = 50
        user.public_transport_available = False
        db.commit()
        
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Optimization suggestions"
        mock_openai.return_value = mock_response
        
        # Request suggestions
        authenticated_client.post(
            "/api/v1/ai/suggest-optimization",
            json={
                "tax_year": 2026,
                "language": "en"
            }
        )
        
        # Verify user context was passed
        call_args = mock_rag_service.retrieve_context_with_user_data.call_args
        user_context = call_args[1]["user_context"]
        
        # Should include dashboard data
        assert "year_to_date_income" in user_context or "user_type" in user_context


class TestMultiLanguageSupport:
    """Test multi-language support in AI Assistant"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_german_language_support(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test AI responds in German when requested.
        
        Requirements: 38.3
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Kontext"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Die Einkommensteuer in Österreich ist progressiv."
        mock_openai.return_value = mock_response
        
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Wie funktioniert die Einkommensteuer?",
                "language": "de"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify German response
        assert "Einkommensteuer" in data["message"] or "progressiv" in data["message"]
        
        # Verify German disclaimer
        assert "Haftungsausschluss" in data["message"]
        
        # Verify system prompt was in German
        call_args = mock_openai.call_args
        messages = call_args[1]["messages"]
        system_msg = next(msg for msg in messages if msg["role"] == "system")
        assert "AI-Assistent" in system_msg["content"] or "Steuer" in system_msg["content"]
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_english_language_support(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test AI responds in English when requested.
        
        Requirements: 38.3
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Austrian income tax is progressive."
        mock_openai.return_value = mock_response
        
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "How does income tax work?",
                "language": "en"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify English response
        assert "tax" in data["message"].lower()
        
        # Verify English disclaimer
        assert "Disclaimer" in data["message"]

    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_chinese_language_support(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test AI responds in Chinese when requested.
        
        Requirements: 38.3
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "上下文"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "奥地利的所得税采用累进税率。"
        mock_openai.return_value = mock_response
        
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "所得税如何计算？",
                "language": "zh"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify Chinese response
        assert "所得税" in data["message"] or "税" in data["message"]
        
        # Verify Chinese disclaimer
        assert "免责声明" in data["message"]


class TestErrorHandling:
    """Test error handling in AI Assistant"""
    
    def test_chat_without_authentication(self, client):
        """
        Test chat endpoint requires authentication.
        
        Requirements: 38.1
        """
        response = client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Test question",
                "language": "en"
            }
        )
        
        assert response.status_code == 401
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_chat_with_llm_error(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test error handling when LLM fails.
        
        Requirements: 38.2
        """
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        # Simulate OpenAI error
        mock_openai.side_effect = Exception("API rate limit exceeded")
        
        response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "Test question",
                "language": "en"
            }
        )
        
        assert response.status_code == 500
        assert "error" in response.json()["detail"].lower()
    
    def test_get_history_without_authentication(self, client):
        """
        Test history endpoint requires authentication.
        
        Requirements: 38.5
        """
        response = client.get("/api/v1/ai/history")
        
        assert response.status_code == 401
    
    def test_clear_history_without_authentication(self, client):
        """
        Test clear history endpoint requires authentication.
        
        Requirements: 38.6
        """
        response = client.delete("/api/v1/ai/history")
        
        assert response.status_code == 401


class TestUserIsolation:
    """Test that users can only access their own chat history"""
    
    def test_users_have_separate_chat_histories(
        self,
        client,
        multiple_test_users,
        db
    ):
        """
        Test that each user has isolated chat history.
        
        Requirements: 38.5
        """
        from app.models.chat_message import ChatMessage, MessageRole
        from app.models.user import User
        
        # Create messages for different users
        user1 = db.query(User).filter(User.email == multiple_test_users[0]["email"]).first()
        user2 = db.query(User).filter(User.email == multiple_test_users[1]["email"]).first()
        
        # User 1 messages
        for i in range(3):
            msg = ChatMessage(
                user_id=user1.id,
                role=MessageRole.USER,
                content=f"User 1 message {i}",
                language="en"
            )
            db.add(msg)
        
        # User 2 messages
        for i in range(2):
            msg = ChatMessage(
                user_id=user2.id,
                role=MessageRole.USER,
                content=f"User 2 message {i}",
                language="en"
            )
            db.add(msg)
        
        db.commit()
        
        # Login as user 1
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": multiple_test_users[0]["email"],
                "password": multiple_test_users[0]["password"]
            }
        )
        user1_token = login_response.json()["access_token"]
        
        # Get user 1 history
        response = client.get(
            "/api/v1/ai/history",
            headers={"Authorization": f"Bearer {user1_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should only see user 1's messages
        assert data["total_count"] == 3
        assert all("User 1" in msg["content"] for msg in data["messages"])
        assert not any("User 2" in msg["content"] for msg in data["messages"])



class TestKnowledgeBaseRefresh:
    """Test knowledge base refresh functionality (admin only)"""
    
    def test_refresh_knowledge_base_requires_admin(
        self,
        authenticated_client
    ):
        """
        Test that knowledge base refresh requires admin privileges.
        
        Requirements: 38.10
        """
        response = authenticated_client.post(
            "/api/v1/ai/admin/refresh-knowledge-base"
        )
        
        # Should fail because test user is not admin
        assert response.status_code in [403, 401]
    
    @patch('app.services.knowledge_base_service.get_knowledge_base_service')
    def test_refresh_knowledge_base_as_admin(
        self,
        mock_kb_service,
        client,
        db
    ):
        """
        Test knowledge base refresh by admin user.
        
        Requirements: 38.10
        """
        from app.models.user import User
        from app.core.security import get_password_hash
        
        # Create admin user
        admin_user = User(
            email="admin@example.com",
            full_name="Admin User",
            hashed_password=get_password_hash("AdminPass123!"),
            user_type="employee",
            is_admin=True,
            two_factor_enabled=False
        )
        db.add(admin_user)
        db.commit()
        
        # Login as admin
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "admin@example.com",
                "password": "AdminPass123!"
            }
        )
        admin_token = login_response.json()["access_token"]
        
        # Setup mock
        mock_kb = MagicMock()
        mock_kb.refresh_knowledge_base.return_value = None
        mock_kb_service.return_value = mock_kb
        
        # Refresh knowledge base
        response = client.post(
            "/api/v1/ai/admin/refresh-knowledge-base",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "collections_updated" in data
        assert len(data["collections_updated"]) > 0
        
        # Verify refresh was called
        mock_kb.refresh_knowledge_base.assert_called_once()


class TestEndToEndAIWorkflow:
    """Test complete end-to-end AI Assistant workflows"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_complete_tax_question_workflow(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        db
    ):
        """
        Test complete workflow: ask question → get response → view history.
        
        Requirements: 38.1, 38.2, 38.3, 38.4, 38.5
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [
                {
                    "document": "2026 exemption amount is €13,539",
                    "metadata": {},
                    "distance": 0.1,
                    "collection": "tax_tables"
                }
            ],
            "user_data": {"user_type": "employee"}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context with exemption info"
        mock_get_rag.return_value = mock_rag_service
        
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = (
            "The tax exemption amount for 2026 is €13,539. "
            "This means the first €13,539 of your income is tax-free."
        )
        mock_openai.return_value = mock_response
        
        # Step 1: Ask question
        chat_response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What is the tax exemption amount?",
                "language": "en"
            }
        )
        
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        
        # Verify response
        assert "€13,539" in chat_data["message"]
        assert "⚠️" in chat_data["message"]
        assert "Disclaimer" in chat_data["message"]
        
        # Step 2: View history
        history_response = authenticated_client.get("/api/v1/ai/history")
        
        assert history_response.status_code == 200
        history_data = history_response.json()
        
        # Should have 2 messages (user + assistant)
        assert history_data["total_count"] == 2
        assert history_data["messages"][0]["role"] == "user"
        assert history_data["messages"][0]["content"] == "What is the tax exemption amount?"
        assert history_data["messages"][1]["role"] == "assistant"
        assert "€13,539" in history_data["messages"][1]["content"]
        
        # Step 3: Clear history
        clear_response = authenticated_client.delete("/api/v1/ai/history")
        
        assert clear_response.status_code == 204
        
        # Step 4: Verify history cleared
        history_after = authenticated_client.get("/api/v1/ai/history")
        assert history_after.json()["total_count"] == 0

    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_multi_turn_conversation_workflow(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client
    ):
        """
        Test multi-turn conversation with context retention.
        
        Requirements: 38.1, 38.5
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        # Turn 1: Initial question
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message.content = "VAT applies if your turnover exceeds €55,000."
        mock_openai.return_value = mock_response1
        
        response1 = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "When does VAT apply?",
                "language": "en"
            }
        )
        
        assert response1.status_code == 200
        assert "€55,000" in response1.json()["message"]
        
        # Turn 2: Follow-up question
        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message.content = (
            "The tolerance rule allows you to remain VAT-exempt up to €60,500."
        )
        mock_openai.return_value = mock_response2
        
        response2 = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "What about the tolerance rule?",
                "language": "en"
            }
        )
        
        assert response2.status_code == 200
        assert "€60,500" in response2.json()["message"]
        
        # Verify conversation history includes both turns
        history = authenticated_client.get("/api/v1/ai/history")
        assert history.json()["total_count"] == 4  # 2 user + 2 assistant messages
        
        # Verify second LLM call included first conversation
        second_call_args = mock_openai.call_args_list[1]
        messages = second_call_args[1]["messages"]
        
        # Should include previous messages
        message_contents = [msg["content"] for msg in messages]
        assert any("€55,000" in content for content in message_contents)
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.openai.chat.completions.create')
    def test_ocr_to_chat_workflow(
        self,
        mock_openai,
        mock_get_rag,
        authenticated_client,
        document_with_ocr
    ):
        """
        Test workflow: OCR document → explain → ask follow-up.
        
        Requirements: 38.7, 38.1
        """
        # Setup mocks
        mock_rag_service = MagicMock()
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        mock_get_rag.return_value = mock_rag_service
        
        # Step 1: Explain OCR result
        mock_response1 = MagicMock()
        mock_response1.choices = [MagicMock()]
        mock_response1.choices[0].message.content = (
            "This is a grocery receipt from BILLA for €8.50. "
            "Groceries are generally not deductible."
        )
        mock_openai.return_value = mock_response1
        
        ocr_response = authenticated_client.post(
            "/api/v1/ai/explain-ocr",
            json={
                "document_id": document_with_ocr["id"],
                "language": "en"
            }
        )
        
        assert ocr_response.status_code == 200
        assert "BILLA" in ocr_response.json()["message"]
        
        # Step 2: Ask follow-up question
        mock_response2 = MagicMock()
        mock_response2.choices = [MagicMock()]
        mock_response2.choices[0].message.content = (
            "Groceries can be deductible if you're self-employed and can prove "
            "they're for business purposes, such as client meetings."
        )
        mock_openai.return_value = mock_response2
        
        chat_response = authenticated_client.post(
            "/api/v1/ai/chat",
            json={
                "message": "When can groceries be deductible?",
                "language": "en"
            }
        )
        
        assert chat_response.status_code == 200
        assert "deductible" in chat_response.json()["message"].lower()
        
        # Verify both messages in history
        history = authenticated_client.get("/api/v1/ai/history")
        assert history.json()["total_count"] == 2  # OCR explanation + chat response
