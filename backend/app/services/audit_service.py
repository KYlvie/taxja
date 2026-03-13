"""Audit logging service for property operations"""
from typing import Optional, Dict, Any, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog, AuditOperationType, AuditEntityType


class AuditService:
    """Service for logging property-related operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def log_operation(
        self,
        user_id: int,
        operation_type: AuditOperationType,
        entity_type: AuditEntityType,
        entity_id: str,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """
        Log an audit operation.
        
        Args:
            user_id: ID of the user performing the operation
            operation_type: Type of operation (create, update, delete, etc.)
            entity_type: Type of entity (property, transaction, etc.)
            entity_id: ID of the entity being operated on
            details: Additional details about the operation (JSON-serializable dict)
            ip_address: IP address of the request
            user_agent: User agent string of the request
        
        Returns:
            Created AuditLog instance
        """
        audit_log = AuditLog(
            user_id=user_id,
            operation_type=operation_type,
            entity_type=entity_type,
            entity_id=str(entity_id),
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
        
        self.db.add(audit_log)
        self.db.commit()
        self.db.refresh(audit_log)
        
        return audit_log
    
    def log_property_create(
        self,
        user_id: int,
        property_id: str,
        property_data: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log property creation"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.CREATE,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={
                "property_type": property_data.get("property_type"),
                "purchase_date": str(property_data.get("purchase_date")),
                "purchase_price": str(property_data.get("purchase_price")),
                "building_value": str(property_data.get("building_value")),
                "address": property_data.get("address"),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_property_update(
        self,
        user_id: int,
        property_id: str,
        changes: Dict[str, Any],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log property update"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.UPDATE,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={"changes": changes},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_property_delete(
        self,
        user_id: int,
        property_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log property deletion"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.DELETE,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_property_archive(
        self,
        user_id: int,
        property_id: str,
        sale_date: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log property archival"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.ARCHIVE,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={"sale_date": sale_date} if sale_date else {},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_transaction_link(
        self,
        user_id: int,
        property_id: str,
        transaction_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log transaction linking to property"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.LINK_TRANSACTION,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={"transaction_id": transaction_id},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_transaction_unlink(
        self,
        user_id: int,
        property_id: str,
        transaction_id: int,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log transaction unlinking from property"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.UNLINK_TRANSACTION,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={"transaction_id": transaction_id},
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_depreciation_backfill(
        self,
        user_id: int,
        property_id: str,
        years_backfilled: int,
        total_amount: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log historical depreciation backfill"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.BACKFILL_DEPRECIATION,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={
                "years_backfilled": years_backfilled,
                "total_amount": total_amount,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def log_depreciation_generation(
        self,
        user_id: int,
        property_id: str,
        year: int,
        amount: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditLog:
        """Log annual depreciation generation"""
        return self.log_operation(
            user_id=user_id,
            operation_type=AuditOperationType.GENERATE_DEPRECIATION,
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
            details={
                "year": year,
                "amount": amount,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    def get_entity_audit_trail(
        self,
        entity_type: AuditEntityType,
        entity_id: str,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit trail for a specific entity.
        
        Args:
            entity_type: Type of entity
            entity_id: ID of the entity
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries, ordered by most recent first
        """
        return (
            self.db.query(AuditLog)
            .filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == str(entity_id),
            )
            .order_by(AuditLog.created_at.desc())
            .limit(limit)
            .all()
        )
    
    def get_user_audit_trail(
        self,
        user_id: int,
        entity_type: Optional[AuditEntityType] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get audit trail for a specific user.
        
        Args:
            user_id: ID of the user
            entity_type: Optional filter by entity type
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries, ordered by most recent first
        """
        query = self.db.query(AuditLog).filter(AuditLog.user_id == user_id)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    def get_recent_operations(
        self,
        operation_type: Optional[AuditOperationType] = None,
        entity_type: Optional[AuditEntityType] = None,
        limit: int = 100,
    ) -> List[AuditLog]:
        """
        Get recent operations across all users.
        
        Args:
            operation_type: Optional filter by operation type
            entity_type: Optional filter by entity type
            limit: Maximum number of records to return
        
        Returns:
            List of AuditLog entries, ordered by most recent first
        """
        query = self.db.query(AuditLog)
        
        if operation_type:
            query = query.filter(AuditLog.operation_type == operation_type)
        
        if entity_type:
            query = query.filter(AuditLog.entity_type == entity_type)
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
