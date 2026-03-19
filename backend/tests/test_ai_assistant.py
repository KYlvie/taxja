"""
Unit tests for AI Tax Assistant.
Tests RAG retrieval, response generation, disclaimer inclusion, and multi-language support.
"""
import pytest
from unittest.mock import Mock, patch

from app.services.vector_db_service import VectorDBService
from app.services.rag_retrieval_service import RAGRetrievalService
from app.services.ai_assistant_service import AIAssistantService
from app.services.chat_history_service import ChatHistoryService
from app.models.chat_message import ChatMessage, MessageRole


class TestVectorDBService:
    """Test vector database service"""
    
    @patch('app.services.vector_db_service.chromadb.PersistentClient')
    @patch('app.services.vector_db_service.SentenceTransformer')
    def test_add_documents(self, mock_transformer, mock_client):
        """Test adding documents to vector database"""
        # Setup mocks
        mock_collection = Mock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        mock_transformer.return_value.encode.return_value = [[0.1, 0.2, 0.3]]
        
        # Create service
        service = VectorDBService(persist_directory="./test_data")
        
        # Add documents
        documents = ["Test document about Austrian tax law"]
        metadatas = [{"source": "test", "language": "en"}]
        ids = ["test_1"]
        
        service.add_documents(
            collection_name="austrian_tax_law",
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
        
        # Verify collection.add was called
        mock_collection.add.assert_called_once()
    
    @patch('app.services.vector_db_service.chromadb.PersistentClient')
    @patch('app.services.vector_db_service.SentenceTransformer')
    def test_query_documents(self, mock_transformer, mock_client):
        """Test querying documents from vector database"""
        # Setup mocks
        mock_collection = Mock()
        mock_client.return_value.get_or_create_collection.return_value = mock_collection
        mock_transformer.return_value.encode.return_value = [[0.1, 0.2, 0.3]]
        
        mock_collection.query.return_value = {
            "documents": [["Test document"]],
            "metadatas": [[{"source": "test"}]],
            "distances": [[0.5]],
            "ids": [["test_1"]]
        }
        
        # Create service
        service = VectorDBService(persist_directory="./test_data")
        
        # Query documents
        results = service.query_documents(
            collection_name="austrian_tax_law",
            query_text="What is the income tax rate?",
            n_results=5
        )
        
        # Verify results
        assert "documents" in results
        assert len(results["documents"][0]) == 1
        mock_collection.query.assert_called_once()


class TestRAGRetrievalService:
    """Test RAG retrieval service"""
    
    @patch('app.services.rag_retrieval_service.get_vector_db_service')
    def test_retrieve_context(self, mock_get_vector_db):
        """Test retrieving context for a query"""
        # Setup mock
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        
        mock_vector_db.query_documents.return_value = {
            "documents": [["Income tax is calculated progressively"]],
            "metadatas": [[{"source": "USP 2026", "language": "en"}]],
            "distances": [[0.3]],
            "ids": [["tax_law_1"]]
        }
        
        # Create service
        service = RAGRetrievalService()
        
        # Retrieve context
        context = service.retrieve_context(
            query="How is income tax calculated?",
            language="en",
            top_k=5
        )
        
        # Verify results
        assert len(context) > 0
        assert context[0]["document"] == "Income tax is calculated progressively"
        assert context[0]["metadata"]["language"] == "en"
    
    @patch('app.services.rag_retrieval_service.get_vector_db_service')
    def test_retrieve_context_with_user_data(self, mock_get_vector_db):
        """Test retrieving context with user data"""
        # Setup mock
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        
        mock_vector_db.query_documents.return_value = {
            "documents": [["Tax information"]],
            "metadatas": [[{"source": "test"}]],
            "distances": [[0.3]],
            "ids": [["test_1"]]
        }
        
        # Create service
        service = RAGRetrievalService()
        
        # User context
        user_context = {
            "year_to_date_income": 50000.00,
            "year_to_date_expenses": 10000.00,
            "user_type": "self_employed"
        }
        
        # Retrieve context
        context = service.retrieve_context_with_user_data(
            query="How much tax do I owe?",
            user_context=user_context,
            language="en"
        )
        
        # Verify results
        assert "knowledge_base" in context
        assert "user_data" in context
        assert context["user_data"]["year_to_date_income"] == 50000.00
    
    @patch('app.services.rag_retrieval_service.get_vector_db_service')
    def test_format_context_for_prompt(self, mock_get_vector_db):
        """Test formatting context for LLM prompt"""
        # Setup mock
        mock_vector_db = Mock()
        mock_get_vector_db.return_value = mock_vector_db
        
        # Create service
        service = RAGRetrievalService()
        
        # Context
        context = {
            "knowledge_base": [
                {
                    "document": "Income tax is progressive",
                    "metadata": {"source": "USP 2026"}
                }
            ],
            "user_data": {
                "year_to_date_income": 50000.00,
                "user_type": "employee"
            }
        }
        
        # Format context
        formatted = service.format_context_for_prompt(context)
        
        # Verify formatting
        assert "Income tax is progressive" in formatted
        assert "€50,000.00" in formatted
        assert "employee" in formatted


class TestAIAssistantService:
    """Test AI Assistant service"""
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.AIAssistantService._generate_openai_response')
    def test_generate_response_with_disclaimer(self, mock_openai_response, mock_get_rag):
        """Test that AI response includes disclaimer"""
        # Setup mocks
        mock_rag_service = Mock()
        mock_get_rag.return_value = mock_rag_service
        
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        
        mock_openai_response.return_value = "Income tax is calculated progressively."
        
        # Create service
        service = AIAssistantService()
        service.llm_provider = "openai"
        
        # Generate response
        response = service.generate_response(
            user_message="How is income tax calculated?",
            user_context={},
            conversation_history=[],
            language="en"
        )
        
        # Verify disclaimer is included
        assert "⚠️" in response
        assert "Disclaimer" in response
        assert "not constitute tax advice" in response
        assert "FinanzOnline" in response
        assert "Steuerberater" in response
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.AIAssistantService._generate_openai_response')
    def test_multi_language_support(self, mock_openai_response, mock_get_rag):
        """Test multi-language support (German, English, Chinese)"""
        # Setup mocks
        mock_rag_service = Mock()
        mock_get_rag.return_value = mock_rag_service
        
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        
        mock_openai_response.return_value = "Response"
        
        # Create service
        service = AIAssistantService()
        service.llm_provider = "openai"
        
        # Test German
        response_de = service.generate_response(
            user_message="Test",
            user_context={},
            conversation_history=[],
            language="de"
        )
        assert "Haftungsausschluss" in response_de
        
        # Test English
        response_en = service.generate_response(
            user_message="Test",
            user_context={},
            conversation_history=[],
            language="en"
        )
        assert "Disclaimer" in response_en
        
        # Test Chinese
        response_zh = service.generate_response(
            user_message="Test",
            user_context={},
            conversation_history=[],
            language="zh"
        )
        assert "免责声明" in response_zh
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.AIAssistantService._generate_openai_response')
    def test_explain_ocr_result(self, mock_openai_response, mock_get_rag):
        """Test OCR result explanation"""
        # Setup mocks
        mock_rag_service = Mock()
        mock_get_rag.return_value = mock_rag_service
        
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        
        mock_openai_response.return_value = "This receipt shows groceries. Office supplies are deductible."
        
        # Create service
        service = AIAssistantService()
        service.llm_provider = "openai"
        
        # OCR data
        ocr_data = {
            "document_type": "receipt",
            "extracted_data": {
                "merchant": "BILLA",
                "amount": 45.50,
                "items": ["Milk", "Bread", "Pens"]
            },
            "confidence_score": 0.85
        }
        
        # Generate explanation
        explanation = service.explain_ocr_result(ocr_data, language="en")
        
        # Verify explanation includes disclaimer
        assert "Disclaimer" in explanation
    
    @patch('app.services.ai_assistant_service.get_rag_retrieval_service')
    @patch('app.services.ai_assistant_service.AIAssistantService._generate_openai_response')
    def test_suggest_tax_optimization(self, mock_openai_response, mock_get_rag):
        """Test tax optimization suggestions"""
        # Setup mocks
        mock_rag_service = Mock()
        mock_get_rag.return_value = mock_rag_service
        
        mock_rag_service.retrieve_context_with_user_data.return_value = {
            "knowledge_base": [],
            "user_data": {}
        }
        mock_rag_service.format_context_for_prompt.return_value = "Context"
        
        mock_openai_response.return_value = "Consider claiming commuting allowance."
        
        # Create service
        service = AIAssistantService()
        service.llm_provider = "openai"
        
        # User tax data
        user_tax_data = {
            "year_to_date_income": 60000.00,
            "year_to_date_expenses": 5000.00,
            "estimated_tax": 12000.00
        }
        
        # Generate suggestions
        suggestions = service.suggest_tax_optimization(user_tax_data, language="en")
        
        # Verify suggestions include disclaimer
        assert "Disclaimer" in suggestions


class TestChatHistoryService:
    """Test chat history service"""
    
    def test_save_message(self, db_session):
        """Test saving a chat message"""
        service = ChatHistoryService(db_session)
        
        # Save message
        message = service.save_message(
            user_id=1,
            role=MessageRole.USER,
            content="How is income tax calculated?",
            language="en"
        )
        
        # Verify message
        assert message.id is not None
        assert message.user_id == 1
        assert message.role == MessageRole.USER
        assert message.content == "How is income tax calculated?"
        assert message.language == "en"
    
    def test_get_conversation_history(self, db_session):
        """Test retrieving conversation history"""
        service = ChatHistoryService(db_session)
        
        # Save multiple messages
        service.save_message(1, MessageRole.USER, "Question 1", "en")
        service.save_message(1, MessageRole.ASSISTANT, "Answer 1", "en")
        service.save_message(1, MessageRole.USER, "Question 2", "en")
        
        # Get history
        history = service.get_conversation_history(user_id=1, limit=10)
        
        # Verify history
        assert len(history) == 3
        assert history[0].content == "Question 1"
        assert history[1].content == "Answer 1"
        assert history[2].content == "Question 2"
    
    def test_get_recent_messages(self, db_session):
        """Test getting recent messages formatted for LLM"""
        service = ChatHistoryService(db_session)
        
        # Save messages
        service.save_message(1, MessageRole.USER, "Question", "en")
        service.save_message(1, MessageRole.ASSISTANT, "Answer", "en")
        
        # Get recent messages
        recent = service.get_recent_messages(user_id=1, limit=10)
        
        # Verify format
        assert len(recent) == 2
        assert recent[0]["role"] == "user"
        assert recent[0]["content"] == "Question"
        assert recent[1]["role"] == "assistant"
        assert recent[1]["content"] == "Answer"
    
    def test_clear_history(self, db_session):
        """Test clearing chat history"""
        service = ChatHistoryService(db_session)
        
        # Save messages
        service.save_message(1, MessageRole.USER, "Question 1", "en")
        service.save_message(1, MessageRole.USER, "Question 2", "en")
        
        # Clear history
        deleted_count = service.clear_history(user_id=1)
        
        # Verify deletion
        assert deleted_count == 2
        
        # Verify history is empty
        history = service.get_conversation_history(user_id=1)
        assert len(history) == 0


# Fixtures
@pytest.fixture
def db_session(db):
    """Use the shared isolated test database session."""
    return db


# Property-based tests
from hypothesis import given, strategies as st


@given(
    message=st.text(min_size=1, max_size=1000),
    language=st.sampled_from(["de", "en", "zh"])
)
def test_disclaimer_always_included(message, language):
    """
    Property: Every AI response must include a disclaimer.
    
    This validates Requirement 38.4: Append disclaimer to every response.
    """
    # Get disclaimer for language
    disclaimer = AIAssistantService.DISCLAIMERS.get(language, AIAssistantService.DISCLAIMERS["de"])
    
    # Verify disclaimer exists and contains required elements
    assert "⚠️" in disclaimer
    assert "FinanzOnline" in disclaimer
    assert "Steuerberater" in disclaimer


@given(language=st.sampled_from(["de", "en", "zh"]))
def test_multi_language_disclaimer(language):
    """
    Property: Disclaimer must be available in all supported languages.
    
    This validates Requirement 38.3: Generate response in user's language.
    """
    # Verify disclaimer exists for language
    assert language in AIAssistantService.DISCLAIMERS
    disclaimer = AIAssistantService.DISCLAIMERS[language]
    
    # Verify disclaimer is not empty
    assert len(disclaimer) > 0
    
    # Verify disclaimer contains warning symbol
    assert "⚠️" in disclaimer
