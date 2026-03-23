"""
Pydantic schemas for AI Tax Assistant API.
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime
from app.models.chat_message import MessageRole


class SuggestionContext(BaseModel):
    """
    Minimal context for suggestion-aware chat responses.
    Only carries minimum necessary fields — NOT the full ocr_result or document payload.
    This keeps LLM prompts predictable and prevents context bloat (NFR-8).
    """
    document_id: int
    suggestion_type: str  # 'create_asset', 'create_property', etc.
    summary: Dict[str, Any] = Field(
        default_factory=dict,
        description="Key extracted fields only, e.g. {'item': 'BMW 320d', 'amount': 35000}"
    )
    pending_questions: List[str] = Field(
        default_factory=list,
        description="Field keys of unanswered follow-up questions, e.g. ['business_use_percentage']"
    )


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message"""
    message: str = Field(..., min_length=1, max_length=5000, description="User's message")
    language: str = Field(default="de", pattern="^(de|en|zh|fr|ru|hu|pl|tr|bs)$", description="Message language")
    context: Optional[dict] = Field(default=None, description="Optional page/document context for workflow-aware AI")
    suggestion_context: Optional[SuggestionContext] = Field(
        default=None,
        description="When user asks about a pending suggestion, include minimal context for suggestion-aware answers"
    )


class ChatMessageResponse(BaseModel):
    """Schema for chat message response"""
    id: int
    user_id: int
    role: MessageRole
    content: str
    language: str
    created_at: datetime
    
    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    """Schema for AI assistant response"""
    message: str = Field(..., description="AI-generated response text")
    message_id: int = Field(..., description="ID of the saved message")
    timestamp: datetime = Field(..., description="Response timestamp")
    intent: Optional[str] = Field(None, description="Detected user intent")
    data: Optional[dict] = Field(None, description="Structured data (calculations, etc.)")
    suggestions: Optional[List[str]] = Field(None, description="Follow-up suggestions")
    show_disclaimer: bool = Field(False, description="Whether frontend should show tax disclaimer")
    source_tier: Optional[str] = Field(None, description="Response source tier: rag, llm, lightweight, rule_based")


class ConversationHistory(BaseModel):
    """Schema for conversation history"""
    messages: List[ChatMessageResponse]
    total_count: int = Field(..., description="Total number of messages")
    has_more: bool = Field(..., description="Whether there are more messages")


class OCRExplanationRequest(BaseModel):
    """Schema for OCR explanation request"""
    document_id: int = Field(..., description="Document ID to explain")
    language: str = Field(default="de", pattern="^(de|en|zh|fr|ru|hu|pl|tr|bs)$", description="Response language")


class TaxOptimizationRequest(BaseModel):
    """Schema for tax optimization request"""
    tax_year: int = Field(..., ge=2020, le=2030, description="Tax year to analyze")
    language: str = Field(default="de", pattern="^(de|en|zh|fr|ru|hu|pl|tr|bs)$", description="Response language")


class KnowledgeBaseRefreshResponse(BaseModel):
    """Schema for knowledge base refresh response"""
    success: bool
    message: str
    collections_updated: List[str]
