"""Unit tests for audit logging service"""
import pytest
from sqlalchemy.orm import Session
from app.models.audit_log import AuditLog, AuditOperationType, AuditEntityType
from app.models.user import User, UserType
from app.services.audit_service import AuditService


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a current-model test user on the shared isolated test DB."""
    user = User(
        email="audit@example.com",
        password_hash="hashed_password",
        name="Audit User",
        user_type=UserType.EMPLOYEE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


class TestAuditService:
    """Test suite for AuditService"""
    
    def test_log_property_create(self, db: Session, test_user):
        """Test logging property creation"""
        audit_service = AuditService(db)
        
        property_data = {
            "property_type": "rental",
            "purchase_date": "2020-06-15",
            "purchase_price": "350000.00",
            "building_value": "280000.00",
            "address": "Hauptstraße 123, 1010 Wien",
        }
        
        audit_log = audit_service.log_property_create(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            property_data=property_data,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0",
        )
        
        assert audit_log.id is not None
        assert audit_log.user_id == test_user.id
        assert audit_log.operation_type == AuditOperationType.CREATE
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.entity_id == "550e8400-e29b-41d4-a716-446655440000"
        assert audit_log.details["property_type"] == "rental"
        assert audit_log.details["purchase_price"] == "350000.00"
        assert audit_log.ip_address == "192.168.1.1"
        assert audit_log.user_agent == "Mozilla/5.0"
        assert audit_log.created_at is not None
    
    def test_log_property_update(self, db: Session, test_user):
        """Test logging property update"""
        audit_service = AuditService(db)
        
        changes = {
            "depreciation_rate": {"old": "0.02", "new": "0.015"},
            "status": {"old": "active", "new": "archived"},
        }
        
        audit_log = audit_service.log_property_update(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            changes=changes,
        )
        
        assert audit_log.operation_type == AuditOperationType.UPDATE
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["changes"] == changes
    
    def test_log_property_delete(self, db: Session, test_user):
        """Test logging property deletion"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_property_delete(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
        )
        
        assert audit_log.operation_type == AuditOperationType.DELETE
        assert audit_log.entity_type == AuditEntityType.PROPERTY
    
    def test_log_property_archive(self, db: Session, test_user):
        """Test logging property archival"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_property_archive(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            sale_date="2025-12-31",
        )
        
        assert audit_log.operation_type == AuditOperationType.ARCHIVE
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["sale_date"] == "2025-12-31"
    
    def test_log_transaction_link(self, db: Session, test_user):
        """Test logging transaction linking"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_transaction_link(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            transaction_id=123,
        )
        
        assert audit_log.operation_type == AuditOperationType.LINK_TRANSACTION
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["transaction_id"] == 123
    
    def test_log_transaction_unlink(self, db: Session, test_user):
        """Test logging transaction unlinking"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_transaction_unlink(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            transaction_id=123,
        )
        
        assert audit_log.operation_type == AuditOperationType.UNLINK_TRANSACTION
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["transaction_id"] == 123
    
    def test_log_depreciation_backfill(self, db: Session, test_user):
        """Test logging depreciation backfill"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_depreciation_backfill(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            years_backfilled=5,
            total_amount="28000.00",
        )
        
        assert audit_log.operation_type == AuditOperationType.BACKFILL_DEPRECIATION
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["years_backfilled"] == 5
        assert audit_log.details["total_amount"] == "28000.00"
    
    def test_log_depreciation_generation(self, db: Session, test_user):
        """Test logging annual depreciation generation"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_depreciation_generation(
            user_id=test_user.id,
            property_id="550e8400-e29b-41d4-a716-446655440000",
            year=2025,
            amount="5600.00",
        )
        
        assert audit_log.operation_type == AuditOperationType.GENERATE_DEPRECIATION
        assert audit_log.entity_type == AuditEntityType.PROPERTY
        assert audit_log.details["year"] == 2025
        assert audit_log.details["amount"] == "5600.00"
    
    def test_get_entity_audit_trail(self, db: Session, test_user):
        """Test retrieving audit trail for an entity"""
        audit_service = AuditService(db)
        property_id = "550e8400-e29b-41d4-a716-446655440000"
        
        # Create multiple audit logs
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id=property_id,
            property_data={"property_type": "rental"},
        )
        
        audit_service.log_property_update(
            user_id=test_user.id,
            property_id=property_id,
            changes={"status": {"old": "active", "new": "archived"}},
        )
        
        audit_service.log_transaction_link(
            user_id=test_user.id,
            property_id=property_id,
            transaction_id=123,
        )
        
        # Retrieve audit trail
        audit_trail = audit_service.get_entity_audit_trail(
            entity_type=AuditEntityType.PROPERTY,
            entity_id=property_id,
        )
        
        assert len(audit_trail) == 3
        # Should be ordered by most recent first
        assert audit_trail[0].operation_type == AuditOperationType.LINK_TRANSACTION
        assert audit_trail[1].operation_type == AuditOperationType.UPDATE
        assert audit_trail[2].operation_type == AuditOperationType.CREATE
    
    def test_get_user_audit_trail(self, db: Session, test_user):
        """Test retrieving audit trail for a user"""
        audit_service = AuditService(db)
        
        # Create audit logs for different properties
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id="property-1",
            property_data={"property_type": "rental"},
        )
        
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id="property-2",
            property_data={"property_type": "owner_occupied"},
        )
        
        # Retrieve user's audit trail
        audit_trail = audit_service.get_user_audit_trail(user_id=test_user.id)
        
        assert len(audit_trail) == 2
        assert all(log.user_id == test_user.id for log in audit_trail)
    
    def test_get_user_audit_trail_filtered(self, db: Session, test_user):
        """Test retrieving filtered audit trail for a user"""
        audit_service = AuditService(db)
        
        # Create different types of audit logs
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id="property-1",
            property_data={"property_type": "rental"},
        )
        
        audit_service.log_transaction_link(
            user_id=test_user.id,
            property_id="property-1",
            transaction_id=123,
        )
        
        # Retrieve only property entity type
        audit_trail = audit_service.get_user_audit_trail(
            user_id=test_user.id,
            entity_type=AuditEntityType.PROPERTY,
        )
        
        assert len(audit_trail) == 2
        assert all(log.entity_type == AuditEntityType.PROPERTY for log in audit_trail)
    
    def test_get_recent_operations(self, db: Session, test_user):
        """Test retrieving recent operations"""
        audit_service = AuditService(db)
        
        # Create various audit logs
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id="property-1",
            property_data={"property_type": "rental"},
        )
        
        audit_service.log_property_update(
            user_id=test_user.id,
            property_id="property-1",
            changes={"status": {"old": "active", "new": "archived"}},
        )
        
        # Retrieve recent operations
        recent_ops = audit_service.get_recent_operations(limit=10)
        
        assert len(recent_ops) >= 2
        # Should be ordered by most recent first
        assert recent_ops[0].created_at >= recent_ops[1].created_at
    
    def test_get_recent_operations_filtered(self, db: Session, test_user):
        """Test retrieving filtered recent operations"""
        audit_service = AuditService(db)
        
        # Create different operation types
        audit_service.log_property_create(
            user_id=test_user.id,
            property_id="property-1",
            property_data={"property_type": "rental"},
        )
        
        audit_service.log_property_update(
            user_id=test_user.id,
            property_id="property-1",
            changes={"status": {"old": "active", "new": "archived"}},
        )
        
        audit_service.log_property_delete(
            user_id=test_user.id,
            property_id="property-2",
        )
        
        # Retrieve only CREATE operations
        create_ops = audit_service.get_recent_operations(
            operation_type=AuditOperationType.CREATE,
        )
        
        assert all(op.operation_type == AuditOperationType.CREATE for op in create_ops)
    
    def test_audit_log_without_optional_fields(self, db: Session, test_user):
        """Test creating audit log without optional fields"""
        audit_service = AuditService(db)
        
        audit_log = audit_service.log_property_delete(
            user_id=test_user.id,
            property_id="property-1",
            # No ip_address or user_agent
        )
        
        assert audit_log.id is not None
        assert audit_log.ip_address is None
        assert audit_log.user_agent is None
        assert audit_log.details == {}
