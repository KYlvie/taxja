"""
Audit and Compliance Schemas

Pydantic schemas for audit, GDPR, and disclaimer endpoints.

Requirements: 17.6, 17.7, 17.8, 17.9, 17.11, 32.1-32.6
"""

from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel, Field


# Audit Checklist Schemas

class AuditIssueSchema(BaseModel):
    """Audit issue"""
    severity: str = Field(..., description="Issue severity: critical, warning, info")
    category: str = Field(..., description="Issue category")
    title: str = Field(..., description="Issue title")
    description: str = Field(..., description="Issue description")
    affected_items: List[Dict] = Field(default_factory=list, description="Affected items")
    recommendation: Optional[str] = Field(None, description="Recommendation to fix")


class AuditChecklistResponse(BaseModel):
    """Audit checklist response"""
    compliance_score: float = Field(..., description="Compliance score (0-100)")
    is_audit_ready: bool = Field(..., description="Whether audit ready")
    summary: Dict = Field(..., description="Summary statistics")
    issues: List[AuditIssueSchema] = Field(..., description="List of issues")


# GDPR Schemas

class GDPRExportResponse(BaseModel):
    """GDPR export response"""
    export_id: str = Field(..., description="Export ID for tracking")
    status: str = Field(..., description="Export status")
    message: str = Field(..., description="Status message")


class GDPRExportStatusResponse(BaseModel):
    """GDPR export status response"""
    export_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None
    download_url: Optional[str] = None
    error_message: Optional[str] = None


class GDPRDeleteResponse(BaseModel):
    """GDPR delete response"""
    success: bool
    message: str
    deleted_counts: Dict
    deleted_at: str


# Audit Log Schemas

class AuditLogQuery(BaseModel):
    """Audit log query parameters"""
    action_type: Optional[str] = Field(None, description="Filter by action type")
    start_date: Optional[datetime] = Field(None, description="Filter by start date")
    end_date: Optional[datetime] = Field(None, description="Filter by end date")
    limit: int = Field(100, ge=1, le=1000, description="Maximum results")
    offset: int = Field(0, ge=0, description="Offset for pagination")


class AuditLogEntry(BaseModel):
    """Audit log entry"""
    id: int
    action: str
    timestamp: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Optional[Dict] = None


class AuditLogResponse(BaseModel):
    """Audit log response"""
    logs: List[AuditLogEntry]
    total_count: int
    limit: int
    offset: int
    has_more: bool


# Disclaimer Schemas

class DisclaimerResponse(BaseModel):
    """Disclaimer response"""
    title: str
    content: str
    version: str
    effective_date: str
    language: str


class DisclaimerAcceptanceRequest(BaseModel):
    """Disclaimer acceptance request"""
    language: str = Field('de', description="Language code")


class DisclaimerAcceptanceResponse(BaseModel):
    """Disclaimer acceptance response"""
    success: bool
    message: str
    accepted_at: str


class DisclaimerStatusResponse(BaseModel):
    """Disclaimer status response"""
    has_accepted: bool
    current_version: str
    acceptance_history: List[Dict] = Field(default_factory=list)
