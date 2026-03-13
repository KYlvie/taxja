"""Pydantic schemas for audit log responses"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from app.models.audit_log import AuditOperationType, AuditEntityType


class AuditLogResponse(BaseModel):
    """Response schema for audit log entries"""
    
    id: int
    user_id: Optional[int] = None
    operation_type: AuditOperationType
    entity_type: AuditEntityType
    entity_id: str
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)
    created_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    class Config:
        from_attributes = True


class AuditTrailResponse(BaseModel):
    """Response schema for audit trail queries"""
    
    total: int
    logs: list[AuditLogResponse]
    
    class Config:
        from_attributes = True
