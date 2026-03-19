"""Audit log model for tracking property operations"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum, JSON, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class AuditOperationType(str, Enum):
    """Audit operation type enumeration"""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ARCHIVE = "archive"
    LINK_TRANSACTION = "link_transaction"
    UNLINK_TRANSACTION = "unlink_transaction"
    BACKFILL_DEPRECIATION = "backfill_depreciation"
    GENERATE_DEPRECIATION = "generate_depreciation"


class AuditEntityType(str, Enum):
    """Audit entity type enumeration"""
    PROPERTY = "property"
    TRANSACTION = "transaction"
    PROPERTY_LOAN = "property_loan"


class AuditLog(Base):
    """Audit log for tracking all property-related operations"""
    __tablename__ = "audit_logs"
    
    # Primary key
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # User who performed the operation
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Operation details
    operation_type = Column(
        SQLEnum(AuditOperationType, values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        index=True,
    )
    entity_type = Column(
        SQLEnum(AuditEntityType, values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        index=True,
    )
    entity_id = Column(String(100), nullable=False, index=True)  # UUID or integer as string
    
    # Additional details (JSON format for flexibility)
    details = Column(JSON, nullable=True)
    
    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    
    # IP address and user agent for security tracking
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    user_agent = Column(String(500), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    
    # Composite indexes for common queries
    __table_args__ = (
        Index("idx_audit_user_entity", "user_id", "entity_type", "entity_id"),
        Index("idx_audit_entity_operation", "entity_type", "entity_id", "operation_type"),
        Index("idx_audit_created_at_desc", created_at.desc()),
    )
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, operation={self.operation_type}, entity={self.entity_type}:{self.entity_id})>"
