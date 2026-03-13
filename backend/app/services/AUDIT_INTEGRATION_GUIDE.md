# Audit Logging Integration Guide

This guide shows how to integrate audit logging into property-related services and API endpoints.

## Overview

The audit logging system tracks all property operations including:
- Property creation, updates, deletion, and archival
- Transaction linking/unlinking
- Depreciation backfill and generation

## Basic Usage

### 1. Import the AuditService

```python
from app.services.audit_service import AuditService
from app.models.audit_log import AuditOperationType, AuditEntityType
```

### 2. Initialize in Your Service

```python
class PropertyService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)
```

### 3. Log Operations

#### Property Creation

```python
def create_property(self, user_id: int, property_data: PropertyCreate) -> Property:
    # Create property
    property = Property(**property_data.dict())
    self.db.add(property)
    self.db.commit()
    self.db.refresh(property)
    
    # Log the operation
    self.audit_service.log_property_create(
        user_id=user_id,
        property_id=str(property.id),
        property_data={
            "property_type": property.property_type.value,
            "purchase_date": str(property.purchase_date),
            "purchase_price": str(property.purchase_price),
            "building_value": str(property.building_value),
            "address": property.address,
        }
    )
    
    return property
```

#### Property Update

```python
def update_property(self, property_id: UUID, user_id: int, updates: PropertyUpdate) -> Property:
    property = self._validate_ownership(property_id, user_id)
    
    # Track changes
    changes = {}
    for field, value in updates.dict(exclude_unset=True).items():
        old_value = getattr(property, field)
        if old_value != value:
            changes[field] = {"old": str(old_value), "new": str(value)}
            setattr(property, field, value)
    
    self.db.commit()
    self.db.refresh(property)
    
    # Log the operation
    if changes:
        self.audit_service.log_property_update(
            user_id=user_id,
            property_id=str(property_id),
            changes=changes
        )
    
    return property
```

#### Property Deletion

```python
def delete_property(self, property_id: UUID, user_id: int) -> bool:
    property = self._validate_ownership(property_id, user_id)
    
    # Check for linked transactions
    has_transactions = self.db.query(Transaction).filter(
        Transaction.property_id == property_id
    ).first() is not None
    
    if has_transactions:
        raise ValueError("Cannot delete property with linked transactions")
    
    # Delete property
    self.db.delete(property)
    self.db.commit()
    
    # Log the operation
    self.audit_service.log_property_delete(
        user_id=user_id,
        property_id=str(property_id)
    )
    
    return True
```

#### Property Archival

```python
def archive_property(self, property_id: UUID, user_id: int, sale_date: date) -> Property:
    property = self._validate_ownership(property_id, user_id)
    
    property.status = PropertyStatus.SOLD
    property.sale_date = sale_date
    
    self.db.commit()
    self.db.refresh(property)
    
    # Log the operation
    self.audit_service.log_property_archive(
        user_id=user_id,
        property_id=str(property_id),
        sale_date=str(sale_date)
    )
    
    return property
```

#### Transaction Linking

```python
def link_transaction(self, transaction_id: int, property_id: UUID, user_id: int) -> Transaction:
    property = self._validate_ownership(property_id, user_id)
    
    transaction = self.db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id
    ).first()
    
    if not transaction:
        raise ValueError("Transaction not found")
    
    transaction.property_id = property_id
    self.db.commit()
    self.db.refresh(transaction)
    
    # Log the operation
    self.audit_service.log_transaction_link(
        user_id=user_id,
        property_id=str(property_id),
        transaction_id=transaction_id
    )
    
    return transaction
```

#### Depreciation Backfill

```python
def backfill_depreciation(self, property_id: UUID, user_id: int) -> BackfillResult:
    # ... backfill logic ...
    
    # Log the operation
    self.audit_service.log_depreciation_backfill(
        user_id=user_id,
        property_id=str(property_id),
        years_backfilled=len(created_transactions),
        total_amount=str(total_amount)
    )
    
    return result
```

## API Integration

### Extracting Request Context

In FastAPI endpoints, you can extract IP address and user agent from the request:

```python
from fastapi import Request

@router.post("/properties")
async def create_property(
    property_data: PropertyCreate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    service = PropertyService(db)
    
    # Extract request context
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    
    # Create property with audit logging
    property = service.create_property(
        user_id=current_user.id,
        property_data=property_data,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return property
```

### Update Service Methods to Accept Request Context

Modify service methods to accept optional IP address and user agent:

```python
def create_property(
    self,
    user_id: int,
    property_data: PropertyCreate,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> Property:
    # ... create property ...
    
    # Log with request context
    self.audit_service.log_property_create(
        user_id=user_id,
        property_id=str(property.id),
        property_data=property_dict,
        ip_address=ip_address,
        user_agent=user_agent
    )
    
    return property
```

## Querying Audit Logs

### Get Audit Trail for a Property

```python
audit_service = AuditService(db)

audit_trail = audit_service.get_entity_audit_trail(
    entity_type=AuditEntityType.PROPERTY,
    entity_id=str(property_id),
    limit=50
)

for log in audit_trail:
    print(f"{log.created_at}: {log.operation_type} by user {log.user_id}")
    print(f"  Details: {log.details}")
```

### Get User's Audit Trail

```python
user_trail = audit_service.get_user_audit_trail(
    user_id=user_id,
    entity_type=AuditEntityType.PROPERTY,
    limit=100
)
```

### Get Recent Operations (Admin)

```python
recent_ops = audit_service.get_recent_operations(
    operation_type=AuditOperationType.DELETE,
    limit=50
)
```

## API Endpoints for Audit Logs

### Get Property Audit Trail

```python
@router.get("/properties/{property_id}/audit-trail")
async def get_property_audit_trail(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Validate ownership
    property_service = PropertyService(db)
    property_service._validate_ownership(property_id, current_user.id)
    
    # Get audit trail
    audit_service = AuditService(db)
    audit_trail = audit_service.get_entity_audit_trail(
        entity_type=AuditEntityType.PROPERTY,
        entity_id=str(property_id)
    )
    
    return {"logs": audit_trail}
```

### Get User's Audit History

```python
@router.get("/users/me/audit-trail")
async def get_my_audit_trail(
    entity_type: Optional[AuditEntityType] = None,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    audit_service = AuditService(db)
    audit_trail = audit_service.get_user_audit_trail(
        user_id=current_user.id,
        entity_type=entity_type,
        limit=limit
    )
    
    return {"logs": audit_trail}
```

## Best Practices

1. **Always log after successful operations**: Only log after the database commit succeeds
2. **Include relevant context**: Store meaningful details in the `details` JSON field
3. **Don't log sensitive data**: Avoid storing full addresses or financial details in plaintext
4. **Use appropriate operation types**: Choose the correct `AuditOperationType` for each operation
5. **Handle errors gracefully**: If audit logging fails, log the error but don't fail the main operation
6. **Set retention policies**: Implement data retention policies for audit logs (e.g., keep for 7 years)

## Error Handling

```python
try:
    # Perform operation
    property = self.create_property(...)
    
    # Log operation
    try:
        self.audit_service.log_property_create(...)
    except Exception as audit_error:
        # Log audit failure but don't fail the operation
        logger.error(f"Failed to log audit entry: {audit_error}")
    
    return property
except Exception as e:
    # Handle main operation failure
    self.db.rollback()
    raise
```

## Testing

Always test audit logging in your unit tests:

```python
def test_create_property_logs_audit(db_session, test_user):
    service = PropertyService(db_session)
    
    property = service.create_property(
        user_id=test_user.id,
        property_data=property_data
    )
    
    # Verify audit log was created
    audit_service = AuditService(db_session)
    audit_trail = audit_service.get_entity_audit_trail(
        entity_type=AuditEntityType.PROPERTY,
        entity_id=str(property.id)
    )
    
    assert len(audit_trail) == 1
    assert audit_trail[0].operation_type == AuditOperationType.CREATE
```
