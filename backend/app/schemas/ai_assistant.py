"""
Pydantic schemas for AI Tax Assistant API.
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from app.models.chat_message import MessageRole


class ChatMessageCreate(BaseModel):
    """Schema for creating a chat message"""
    message: str = Field(..., min_length=1, max_length=5000, description="User's message")
    language: str = Field(default="de", pattern="^(de|en|zh)$", description="Message language")


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
    message: str = Field(..., description="AI-generated response with disclaimer")
    message_id: int = Field(..., description="ID of the saved message")
    timestamp: datetime = Field(..., description="Response timestamp")
    intent: Optional[str] = Field(None, description="Detected user intent")
    data: Optional[dict] = Field(None, description="Structured data (calculations, etc.)")
    suggestions: Optional[List[str]] = Field(None, description="Follow-up suggestions")


class ConversationHistory(BaseModel):
    """Schema for conversation history"""
    messages: List[ChatMessageResponse]
    total_count: int = Field(..., description="Total number of messages")
    has_more: bool = Field(..., description="Whether there are more messages")


class OCRExplanationRequest(BaseModel):
    """Schema for OCR explanation request"""
    document_id: int = Field(..., description="Document ID to explain")
    language: str = Field(default="de", pattern="^(de|en|zh)$", description="Response language")


class TaxOptimizationRequest(BaseModel):
    """Schema for tax optimization request"""
    tax_year: int = Field(..., ge=2020, le=2030, description="Tax year to analyze")
    language: str = Field(default="de", pattern="^(de|en|zh)$", description="Response language")


class KnowledgeBaseRefreshResponse(BaseModel):
    """Schema for knowledge base refresh response"""
    success: bool
    message: str
    collections_updated: List[str]
