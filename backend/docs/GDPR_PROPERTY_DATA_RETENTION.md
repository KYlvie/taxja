# GDPR Compliance: Property Data Retention Policy

## Overview

This document outlines the data retention and deletion policies for the Property Asset Management feature in compliance with the General Data Protection Regulation (GDPR).

## Legal Basis

The processing of property data is based on:
- **GDPR Article 6(1)(b)**: Processing necessary for contract performance
- **GDPR Article 9**: Special categories of personal data (financial data)
- **Austrian Tax Law**: Legal obligation to maintain tax-relevant records

## Data Categories

### 1. Property Information
**Data Stored:**
- Property address (encrypted)
- Purchase details (date, price, building value)
- Construction year
- Property type and status
- Depreciation rate

**Retention Period:**
- Active: While user account is active
- After deletion: 30 days in backups, then permanently deleted

**Legal Basis:** Contract performance (GDPR Art. 6(1)(b))

### 2. Transaction Data
**Data Stored:**
- Rental income transactions
- Property expense transactions
- Depreciation (AfA) transactions
- Transaction dates and amounts

**Retention Period:**
- Active: While user account is active
- Tax-relevant: 7 years after tax year (Austrian tax law requirement)
- After deletion: 30 days in backups, then permanently deleted

**Legal Basis:** 
- Contract performance (GDPR Art. 6(1)(b))
- Legal obligation (GDPR Art. 6(1)(c)) - Austrian tax record retention

### 3. Cached Data
**Data Stored:**
- Property metrics (Redis cache)
- Portfolio summaries
- Depreciation schedules

**Retention Period:**
- 1 hour (automatic expiration)
- Immediately cleared on user data deletion

**Legal Basis:** Legitimate interest (GDPR Art. 6(1)(f)) - performance optimization

## User Rights Under GDPR

### Right to Access (Article 15)
Users can request a summary of their property data using:
```python
property_service.get_user_property_data_summary(user_id)
```

Returns:
- Number of properties (by status)
- Number of linked transactions
- Data retention information

### Right to Rectification (Article 16)
Users can update property information through:
- `PUT /api/v1/properties/{property_id}` endpoint
- Restricted fields: purchase_date, purchase_price (immutable for audit trail)

### Right to Erasure / "Right to be Forgotten" (Article 17)
Users can request deletion of all property data using:
```python
property_service.delete_user_property_data(user_id)
```

**What gets deleted:**
- All properties owned by the user
- All transactions linked to those properties
- All cached property data in Redis

**Exceptions:**
- If legal obligation requires retention (e.g., ongoing tax audit)
- Backups retained for 30 days for disaster recovery

### Right to Data Portability (Article 20)
Users can export their property data in machine-readable format (JSON/CSV) through:
- Property list export endpoint
- Transaction export endpoint

### Right to Object (Article 21)
Users can object to automated processing (e.g., automatic depreciation generation) by:
- Disabling automatic depreciation in settings
- Manually reviewing all system-generated transactions

## Data Deletion Process

### 1. User-Initiated Deletion
When a user requests account deletion:

```python
# Step 1: Delete property data
result = property_service.delete_user_property_data(user_id)

# Step 2: Verify deletion
assert result["properties_deleted"] > 0
assert result["cache_cleared"] == True

# Step 3: Log deletion for audit trail
audit_service.log_gdpr_deletion(user_id, result)
```

### 2. Cascade Deletion
The database schema enforces cascade deletion:

```sql
-- Properties table
ALTER TABLE properties 
ADD CONSTRAINT fk_user 
FOREIGN KEY (user_id) 
REFERENCES users(id) 
ON DELETE CASCADE;

-- Transactions table
ALTER TABLE transactions 
ADD CONSTRAINT fk_property 
FOREIGN KEY (property_id) 
REFERENCES properties(id) 
ON DELETE SET NULL;
```

**Note:** Transactions are explicitly deleted by the service layer to maintain audit trail integrity.

### 3. Backup Retention
- **Active backups:** Retained for 30 days
- **After 30 days:** Permanently deleted from all backup systems
- **Backup encryption:** AES-256 encryption for all backups

## Data Minimization

### Principle
Only collect and store data necessary for tax calculation and property management.

### Implementation
- **No unnecessary fields:** Property model only includes tax-relevant fields
- **Encrypted sensitive data:** Addresses encrypted at rest (AES-256)
- **Automatic cache expiration:** Cached data expires after 1 hour
- **No third-party sharing:** Property data never shared with third parties

## Data Security Measures

### Encryption
- **At rest:** AES-256 encryption for sensitive fields (address, street, city)
- **In transit:** TLS 1.3 for all API communications
- **Cache:** Redis with authentication and encryption

### Access Control
- **Ownership validation:** All operations validate user ownership
- **404 for unauthorized:** Returns 404 (not 403) to avoid information leakage
- **Audit logging:** All property operations logged with user_id and timestamp

### Code Example
```python
def _validate_ownership(self, property_id: UUID, user_id: int) -> Property:
    """
    Validate property ownership.
    Returns 404 for both non-existent and unauthorized access.
    """
    property = self.db.query(Property).filter(Property.id == property_id).first()
    
    if not property or property.user_id != user_id:
        raise ValueError(f"Property with id {property_id} not found")
    
    return property
```

## Audit Trail

### What is Logged
- Property creation, updates, deletion
- Transaction linking/unlinking
- GDPR data access requests
- GDPR data deletion requests

### Audit Log Retention
- **Active logs:** 7 years (Austrian tax law requirement)
- **After user deletion:** Anonymized logs retained for legal compliance
- **Personal identifiers:** Replaced with anonymized user_id hash

### Example Audit Entry
```json
{
  "timestamp": "2026-03-08T10:30:00Z",
  "action": "GDPR_DELETION",
  "user_id": 123,
  "entity_type": "property",
  "details": {
    "properties_deleted": 3,
    "transactions_deleted": 156,
    "reason": "User account deletion request"
  }
}
```

## Data Breach Response

### Notification Timeline
- **Discovery to assessment:** Within 24 hours
- **Assessment to notification:** Within 72 hours (GDPR requirement)
- **User notification:** Immediate if high risk to rights and freedoms

### Breach Response Plan
1. **Contain:** Isolate affected systems
2. **Assess:** Determine scope and impact
3. **Notify:** Inform data protection authority and affected users
4. **Remediate:** Fix vulnerability and restore security
5. **Document:** Record breach details and response actions

## Compliance Checklist

- [x] Data retention periods defined
- [x] User rights implementation (access, rectification, erasure)
- [x] Cascade deletion implemented
- [x] Encryption at rest and in transit
- [x] Audit logging for all operations
- [x] Data minimization principles applied
- [x] Backup retention policy (30 days)
- [x] Access control and ownership validation
- [x] Data breach response plan
- [x] Documentation and transparency

## Contact Information

For GDPR-related inquiries:
- **Data Protection Officer:** dpo@taxja.com
- **Privacy Policy:** https://taxja.com/privacy
- **Data Subject Requests:** privacy@taxja.com

## References

- [GDPR Official Text](https://gdpr-info.eu/)
- [Austrian Data Protection Authority](https://www.dsb.gv.at/)
- [Austrian Tax Record Retention Requirements](https://www.bmf.gv.at/)

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-08  
**Next Review:** 2027-03-08
