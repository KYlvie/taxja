"""
Chat history management service for AI Tax Assistant.
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.chat_message import ChatMessage, MessageRole


class ChatHistoryService:
    """Service for managing chat conversation history"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def save_message(
        self,
        user_id: int,
        role: MessageRole,
        content: str,
        language: str = "de"
    ) -> ChatMessage:
        """
        Save a chat message to database.
        
        Args:
            user_id: User ID
            role: Message role (user, assistant, system)
            content: Message content
            language: Message language
        
        Returns:
            Created ChatMessage
        """
        message = ChatMessage(
            user_id=user_id,
            role=role,
            content=content,
            language=language,
            created_at=datetime.utcnow()
        )
        
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        
        return message
    
    def get_conversation_history(
        self,
        user_id: int,
        limit: int = 50,
        offset: int = 0
    ) -> List[ChatMessage]:
        """
        Get conversation history for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of messages to return
            offset: Offset for pagination
        
        Returns:
            List of ChatMessage objects
        """
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
            .offset(offset)
            .all()
        )
        
        # Return in chronological order (oldest first)
        return list(reversed(messages))
    
    def get_recent_messages(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent messages formatted for LLM context.
        
        Args:
            user_id: User ID
            limit: Number of recent messages
        
        Returns:
            List of message dicts with role and content
        """
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
            .all()
        )
        
        # Format for LLM (chronological order)
        formatted = []
        for msg in reversed(messages):
            formatted.append({
                "role": msg.role.value,
                "content": msg.content
            })
        
        return formatted
    
    def clear_history(self, user_id: int) -> int:
        """
        Clear all chat history for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Number of messages deleted
        """
        count = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .delete()
        )
        
        self.db.commit()
        
        return count
    
    def delete_old_messages(self, days: int = 90) -> int:
        """
        Delete messages older than specified days (cleanup task).
        
        Args:
            days: Number of days to keep
        
        Returns:
            Number of messages deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        count = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.created_at < cutoff_date)
            .delete()
        )
        
        self.db.commit()
        
        return count
    
    def get_message_count(self, user_id: int) -> int:
        """
        Get total message count for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Total number of messages
        """
        return (
            self.db.query(ChatMessage)
            .filter(ChatMessage.user_id == user_id)
            .count()
        )
    
    def search_messages(
        self,
        user_id: int,
        search_term: str,
        limit: int = 20
    ) -> List[ChatMessage]:
        """
        Search messages by content.
        
        Args:
            user_id: User ID
            search_term: Search term
            limit: Maximum results
        
        Returns:
            List of matching ChatMessage objects
        """
        messages = (
            self.db.query(ChatMessage)
            .filter(
                ChatMessage.user_id == user_id,
                ChatMessage.content.ilike(f"%{search_term}%")
            )
            .order_by(desc(ChatMessage.created_at))
            .limit(limit)
            .all()
        )
        
        return messages


def get_chat_history_service(db: Session) -> ChatHistoryService:
    """Get ChatHistoryService instance"""
    return ChatHistoryService(db)
