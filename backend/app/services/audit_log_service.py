"""
Audit Log Service

Logs all user actions for security and compliance purposes.
Tracks login/logout, transaction operations, document operations,
report generation, and settings changes.

Requirements: 17.9
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc

from app.models.audit_log import AuditLog


class AuditAction(str, Enum):
    """Audit action types"""
    # Authentication
    LOGIN_SUCCESS = "login_success"
    LOGIN_FAILED = "login_failed"
    LOGOUT = "logout"
    PASSWORD_CHANGED = "password_changed"
    TWO_FACTOR_ENABLED = "two_factor_enabled"
    TWO_FACTOR_DISABLED = "two_factor_disabled"
    
    # Transaction operations
    TRANSACTION_CREATED = "transaction_created"
    TRANSACTION_UPDATED = "transaction_updated"
    TRANSACTION_DELETED = "transaction_deleted"
    TRANSACTION_IMPORTED = "transaction_imported"
    
    # Document operations
    DOCUMENT_UPLOADED = "document_uploaded"
    DOCUMENT_DELETED = "document_deleted"
    DOCUMENT_DOWNLOADED = "document_downloaded"
    OCR_PROCESSED = "ocr_processed"
    OCR_CORRECTED = "ocr_corrected"
    
    # Report operations
    REPORT_GENERATED = "report_generated"
    REPORT_DOWNLOADED = "report_downloaded"
    XML_EXPORTED = "xml_exported"
    CSV_EXPORTED = "csv_exported"
    
    # Settings changes
    PROFILE_UPDATED = "profile_updated"
    TAX_SETTINGS_UPDATED = "tax_settings_updated"
    LANGUAGE_CHANGED = "language_changed"
    
    # GDPR operations
    GDPR_EXPORT_REQUESTED = "gdpr_export_requested"
    GDPR_EXPORT_COMPLETED = "gdpr_export_completed"
    GDPR_EXPORT_FAILED = "gdpr_export_failed"
    GDPR_DELETE_REQUESTED = "gdpr_delete_requested"
    
    # AI Assistant
    AI_CHAT_MESSAGE = "ai_chat_message"
    AI_CHAT_CLEARED = "ai_chat_cleared"


class AuditLogService:
    """Service for audit logging"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_action(
        self,
        user_id: int,
        action: AuditAction,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict] = None
    ) -> AuditLog:
        """
        Log a user action
        
        Args:
            user_id: User ID
            action: Action type
            ip_address: IP address of the request
            user_agent: User agent string
            details: Additional details (JSON)
            
        Returns:
            Created audit log entry
        """
        log_entry = AuditLog(
            user_id=user_id,
            action=action.value,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {},
            timestamp=datetime.utcnow()
        )
        
        self.db.add(log_entry)
        self.db.commit()
        self.db.refresh(log_entry)
        
        return log_entry
    
    def query_logs(
        self,
        user_id: int,
        action_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0
    ) -> Dict:
        """
        Query audit logs for a user
        
        Args:
            user_id: User ID
            action_type: Filter by action type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of results
            offset: Offset for pagination
            
        Returns:
            Dictionary with logs and pagination info
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        # Apply filters
        if action_type:
            query = query.filter(AuditLog.action == action_type)
        
        if start_date:
            query = query.filter(AuditLog.timestamp >= start_date)
        
        if end_date:
            query = query.filter(AuditLog.timestamp <= end_date)
        
        # Get total count
        total_count = query.count()
        
        # Apply pagination and ordering
        logs = query.order_by(desc(AuditLog.timestamp)).limit(limit).offset(offset).all()
        
        return {
            'logs': [
                {
                    'id': log.id,
                    'action': log.action,
                    'timestamp': log.timestamp.isoformat(),
                    'ip_address': log.ip_address,
                    'user_agent': log.user_agent,
                    'details': log.details
                }
                for log in logs
            ],
            'total_count': total_count,
            'limit': limit,
            'offset': offset,
            'has_more': (offset + limit) < total_count
        }
    
    def get_recent_activity(
        self,
        user_id: int,
        limit: int = 10
    ) -> List[Dict]:
        """
        Get recent activity for a user (for dashboard display)
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            
        Returns:
            List of recent activity entries
        """
        logs = self.db.query(AuditLog).filter(
            AuditLog.user_id == user_id
        ).order_by(desc(AuditLog.timestamp)).limit(limit).all()
        
        return [
            {
                'action': log.action,
                'timestamp': log.timestamp.isoformat(),
                'description': self._get_action_description(log)
            }
            for log in logs
        ]
    
    def _get_action_description(self, log: AuditLog) -> str:
        """Generate human-readable description of action"""
        action_descriptions = {
            AuditAction.LOGIN_SUCCESS: "Logged in successfully",
            AuditAction.LOGOUT: "Logged out",
            AuditAction.TRANSACTION_CREATED: "Created a transaction",
            AuditAction.TRANSACTION_UPDATED: "Updated a transaction",
            AuditAction.TRANSACTION_DELETED: "Deleted a transaction",
            AuditAction.TRANSACTION_IMPORTED: "Imported transactions",
            AuditAction.DOCUMENT_UPLOADED: "Uploaded a document",
            AuditAction.DOCUMENT_DELETED: "Deleted a document",
            AuditAction.OCR_PROCESSED: "Processed document with OCR",
            AuditAction.REPORT_GENERATED: "Generated tax report",
            AuditAction.REPORT_DOWNLOADED: "Downloaded tax report",
            AuditAction.XML_EXPORTED: "Exported FinanzOnline XML",
            AuditAction.PROFILE_UPDATED: "Updated profile",
            AuditAction.GDPR_EXPORT_REQUESTED: "Requested GDPR data export",
            AuditAction.GDPR_DELETE_REQUESTED: "Requested account deletion",
        }
        
        base_description = action_descriptions.get(
            log.action,
            log.action.replace('_', ' ').title()
        )
        
        # Add details if available
        if log.details:
            if 'count' in log.details:
                base_description += f" ({log.details['count']} items)"
            elif 'tax_year' in log.details:
                base_description += f" for {log.details['tax_year']}"
        
        return base_description
    
    def get_login_history(
        self,
        user_id: int,
        limit: int = 20
    ) -> List[Dict]:
        """
        Get login history for security review
        
        Args:
            user_id: User ID
            limit: Maximum number of results
            
        Returns:
            List of login events
        """
        logs = self.db.query(AuditLog).filter(
            and_(
                AuditLog.user_id == user_id,
                AuditLog.action.in_([
                    AuditAction.LOGIN_SUCCESS.value,
                    AuditAction.LOGIN_FAILED.value
                ])
            )
        ).order_by(desc(AuditLog.timestamp)).limit(limit).all()
        
        return [
            {
                'timestamp': log.timestamp.isoformat(),
                'success': log.action == AuditAction.LOGIN_SUCCESS.value,
                'ip_address': log.ip_address,
                'user_agent': log.user_agent,
                'details': log.details
            }
            for log in logs
        ]
