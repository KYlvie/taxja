# Design Document: Property Asset Management

## Overview

This document provides the technical design for the property asset management feature in the Taxja Austrian tax management platform. The design covers database schema, service architecture, API design, frontend components, and integration points with existing systems.

## System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend (React)                         │
├─────────────────────────────────────────────────────────────────┤
│  PropertiesPage  │  PropertyForm  │  PropertyList  │  Dashboard │
│  PropertyDetail  │  PortfolioDash │  LinkingSuggestions         │
└────────────┬────────────────────────────────────────────────────┘
             │ REST API (JSON)
┌────────────┴────────────────────────────────────────────────────┐
│                    API Layer (FastAPI)                           │
├─────────────────────────────────────────────────────────────────┤
│  /api/v1/properties/*  │  /api/v1/transactions/*                │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                      Service Layer                               │
├─────────────────────────────────────────────────────────────────┤
│  PropertyService  │  AfACalculator  │  AddressMatcher           │
│  HistoricalDepreciationService  │  AnnualDepreciationService    │
│  E1FormImportService  │  BescheidImportService                  │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                    Data Layer (SQLAlchemy)                       │
├─────────────────────────────────────────────────────────────────┤
│  Property Model  │  Transaction Model  │  User Model            │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────┴────────────────────────────────────────────────────┐
│                   Database (PostgreSQL)                          │
└─────────────────────────────────────────────────────────────────┘
```

## Database Design

### Entity Relationship Diagram

```
┌─────────────────┐         ┌──────────────────┐
│      User       │         │    Property      │
├─────────────────┤         ├──────────────────┤
│ id (PK)         │1      * │ id (PK)          │
│ email           │─────────│ user_id (FK)     │
│ name            │         │ property_type    │
│ user_type       │         │ rental_pct       │
│ ...             │         │ address          │
└─────────────────┘         │ street           │
                            │ city             │
                            │ postal_code      │
                            │ purchase_date    │
                            │ purchase_price   │
                            │ building_value   │
                            │ land_value       │
                            │ construction_year│
                            │ depreciation_rate│
                            │ status           │
                            │ sale_date        │
                            │ created_at       │
                            │ updated_at       │
                            └────────┬─────────┘
                                     │
                                     │1
                                     │
                                     │*
                            ┌────────┴─────────┐
                            │   Transaction    │
                            ├──────────────────┤
                            │ id (PK)          │
                            │ user_id (FK)     │
                            │ property_id (FK) │
                            │ type             │
                            │ amount           │
                            │ transaction_date │
                            │ description      │
                            │ income_category  │
                            │ expense_category │
                            │ is_deductible    │
                            │ is_system_gen    │
                            │ ...              │
                            └──────────────────┘
```


### Database Schema

#### Property Table

```sql
CREATE TYPE property_type AS ENUM ('rental', 'owner_occupied', 'mixed_use');
CREATE TYPE property_status AS ENUM ('active', 'sold', 'archived');

CREATE TABLE properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    
    -- Property classification
    property_type property_type NOT NULL DEFAULT 'rental',
    rental_percentage NUMERIC(5,2) DEFAULT 100.00 CHECK (rental_percentage >= 0 AND rental_percentage <= 100),
    
    -- Address
    address TEXT NOT NULL,
    street TEXT NOT NULL,
    city TEXT NOT NULL,
    postal_code VARCHAR(10) NOT NULL,
    
    -- Purchase information
    purchase_date DATE NOT NULL,
    purchase_price NUMERIC(12,2) NOT NULL CHECK (purchase_price > 0 AND purchase_price <= 100000000),
    building_value NUMERIC(12,2) NOT NULL CHECK (building_value > 0 AND building_value <= purchase_price),
    land_value NUMERIC(12,2) GENERATED ALWAYS AS (purchase_price - building_value) STORED,
    
    -- Purchase costs (for owner-occupied tracking)
    grunderwerbsteuer NUMERIC(12,2),  -- Property transfer tax
    notary_fees NUMERIC(12,2),
    registry_fees NUMERIC(12,2),      -- Eintragungsgebühr
    
    -- Building details
    construction_year INTEGER CHECK (construction_year >= 1800 AND construction_year <= EXTRACT(YEAR FROM CURRENT_DATE)),
    depreciation_rate NUMERIC(5,4) NOT NULL DEFAULT 0.02 CHECK (depreciation_rate >= 0.001 AND depreciation_rate <= 0.10),
    
    -- Status
    status property_status NOT NULL DEFAULT 'active',
    sale_date DATE CHECK (sale_date IS NULL OR sale_date >= purchase_date),
    
    -- Document references
    kaufvertrag_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    mietvertrag_document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    
    -- Timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes
    CONSTRAINT valid_sale_date CHECK (status != 'sold' OR sale_date IS NOT NULL)
);

CREATE INDEX idx_properties_user_id ON properties(user_id);
CREATE INDEX idx_properties_status ON properties(status);
CREATE INDEX idx_properties_user_status ON properties(user_id, status);
```

#### Transaction Table Extension

```sql
-- Add property_id column to existing transactions table
ALTER TABLE transactions 
ADD COLUMN property_id UUID REFERENCES properties(id) ON DELETE SET NULL;

-- Add system-generated flag for depreciation transactions
ALTER TABLE transactions
ADD COLUMN is_system_generated BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX idx_transactions_property_id ON transactions(property_id);
CREATE INDEX idx_transactions_property_date ON transactions(property_id, transaction_date);
```


## Service Layer Design

### 1. PropertyService

**Responsibility:** Core CRUD operations and business logic for property management.

```python
class PropertyService:
    """Main service for property management operations"""
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator()
    
    def create_property(
        self, 
        user_id: int, 
        property_data: PropertyCreate
    ) -> Property:
        """
        Create a new property with validation and auto-calculations.
        
        Auto-calculations:
        - building_value = 80% of purchase_price if not provided
        - depreciation_rate based on construction_year
        - land_value = purchase_price - building_value
        """
        
    def get_property(self, property_id: UUID, user_id: int) -> Property:
        """Get property with ownership validation"""
        
    def list_properties(
        self, 
        user_id: int, 
        include_archived: bool = False
    ) -> List[Property]:
        """List user's properties with optional archived filter"""
        
    def update_property(
        self, 
        property_id: UUID, 
        user_id: int, 
        updates: PropertyUpdate
    ) -> Property:
        """
        Update property (restricted fields: purchase_date, purchase_price)
        """
        
    def archive_property(
        self, 
        property_id: UUID, 
        user_id: int, 
        sale_date: date
    ) -> Property:
        """Mark property as sold and archived"""
        
    def delete_property(self, property_id: UUID, user_id: int) -> bool:
        """Delete property (only if no linked transactions)"""
        
    def link_transaction(
        self, 
        transaction_id: int, 
        property_id: UUID, 
        user_id: int
    ) -> Transaction:
        """Link transaction to property with validation"""
        
    def get_property_transactions(
        self, 
        property_id: UUID, 
        user_id: int, 
        year: Optional[int] = None
    ) -> List[Transaction]:
        """Get all transactions linked to property"""
        
    def calculate_property_metrics(
        self, 
        property_id: UUID, 
        year: Optional[int] = None
    ) -> PropertyMetrics:
        """
        Calculate property financial metrics:
        - Total rental income
        - Total expenses by category
        - Net rental income
        - Accumulated depreciation
        - Remaining depreciable value
        """
```


### 2. AfACalculator (Depreciation Calculator)

**Responsibility:** Calculate depreciation (AfA) according to Austrian tax law.

```python
class AfACalculator:
    """
    Calculates depreciation (Absetzung für Abnutzung) for rental properties.
    
    Austrian Tax Law:
    - Buildings constructed before 1915: 1.5% annual depreciation
    - Buildings constructed 1915 or later: 2.0% annual depreciation
    - Only building value is depreciable (not land)
    - Pro-rated for partial year ownership
    - Stops when accumulated depreciation reaches building value
    """
    
    def determine_depreciation_rate(
        self, 
        construction_year: Optional[int]
    ) -> Decimal:
        """
        Determine depreciation rate based on construction year.
        
        Returns:
            Decimal("0.015") for pre-1915 buildings
            Decimal("0.020") for 1915+ buildings or unknown
        """
        if construction_year and construction_year < 1915:
            return Decimal("0.015")
        return Decimal("0.020")
    
    def calculate_annual_depreciation(
        self, 
        property: Property, 
        year: int
    ) -> Decimal:
        """
        Calculate annual depreciation for a property in a given year.
        
        Handles:
        - Full year depreciation
        - Pro-rated first year (based on purchase month)
        - Pro-rated last year (if sold mid-year)
        - Building value limit (stops when fully depreciated)
        - Mixed-use properties (only rental percentage)
        
        Returns:
            Decimal amount rounded to 2 decimal places
        """
        # Check if property was owned during this year
        if year < property.purchase_date.year:
            return Decimal("0")
        
        if property.sale_date and year > property.sale_date.year:
            return Decimal("0")
        
        # Get accumulated depreciation up to previous year
        accumulated = self.get_accumulated_depreciation(property.id, year - 1)
        
        # Calculate depreciable value (considering rental percentage)
        depreciable_value = property.building_value
        if property.property_type == PropertyType.MIXED_USE:
            depreciable_value = depreciable_value * (property.rental_percentage / 100)
        
        # Check if already fully depreciated
        if accumulated >= depreciable_value:
            return Decimal("0")
        
        # Calculate base annual depreciation
        annual_amount = depreciable_value * property.depreciation_rate
        
        # Pro-rate for partial year
        months_owned = self._calculate_months_owned(property, year)
        if months_owned < 12:
            annual_amount = (annual_amount * months_owned) / 12
        
        # Ensure we don't exceed building value
        remaining = depreciable_value - accumulated
        final_amount = min(annual_amount, remaining)
        
        return final_amount.quantize(Decimal("0.01"))
    
    def calculate_prorated_depreciation(
        self, 
        building_value: Decimal, 
        depreciation_rate: Decimal, 
        months_owned: int
    ) -> Decimal:
        """Calculate pro-rated depreciation for partial year"""
        annual = building_value * depreciation_rate
        return (annual * months_owned / 12).quantize(Decimal("0.01"))
    
    def get_accumulated_depreciation(
        self, 
        property_id: UUID, 
        up_to_year: Optional[int] = None
    ) -> Decimal:
        """
        Get total accumulated depreciation for a property.
        
        Sums all depreciation transactions up to specified year.
        """
        query = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.property_id == property_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        )
        
        if up_to_year:
            query = query.filter(
                extract('year', Transaction.transaction_date) <= up_to_year
            )
        
        result = query.scalar()
        return result or Decimal("0")
    
    def _calculate_months_owned(self, property: Property, year: int) -> int:
        """Calculate number of months property was owned in given year"""
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        
        # Determine ownership period within the year
        ownership_start = max(property.purchase_date, year_start)
        ownership_end = min(property.sale_date or year_end, year_end)
        
        # Calculate months (inclusive)
        months = (ownership_end.year - ownership_start.year) * 12
        months += ownership_end.month - ownership_start.month + 1
        
        return min(months, 12)
```


### 3. HistoricalDepreciationService

**Responsibility:** Backfill historical depreciation for properties purchased in previous years.

```python
class HistoricalDepreciationService:
    """
    Backfills depreciation transactions for properties purchased in previous years.
    
    Use case: New user registers a property bought in 2020, needs depreciation
    for 2020, 2021, 2022, 2023, 2024, 2025 to have accurate accumulated depreciation.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator(db)
    
    def calculate_historical_depreciation(
        self, 
        property_id: UUID
    ) -> List[HistoricalDepreciationYear]:
        """
        Calculate depreciation for all years from purchase to current year.
        
        Returns list of (year, amount) tuples for preview.
        Does not create transactions.
        """
        property = self._get_property(property_id)
        current_year = date.today().year
        
        results = []
        for year in range(property.purchase_date.year, current_year + 1):
            # Skip if depreciation already exists for this year
            if self._depreciation_exists(property_id, year):
                continue
            
            amount = self.afa_calculator.calculate_annual_depreciation(property, year)
            if amount > 0:
                results.append(HistoricalDepreciationYear(
                    year=year,
                    amount=amount,
                    transaction_date=date(year, 12, 31)
                ))
        
        return results
    
    def backfill_depreciation(
        self, 
        property_id: UUID, 
        user_id: int
    ) -> BackfillResult:
        """
        Create historical depreciation transactions.
        
        Creates transactions dated December 31 of each year.
        Marks as system-generated.
        Validates no duplicates.
        
        Returns summary of created transactions.
        """
        property = self._get_property(property_id)
        
        # Validate ownership
        if property.user_id != user_id:
            raise PermissionError("Property does not belong to user")
        
        # Calculate historical depreciation
        historical_years = self.calculate_historical_depreciation(property_id)
        
        created_transactions = []
        
        try:
            for year_data in historical_years:
                transaction = Transaction(
                    user_id=user_id,
                    property_id=property_id,
                    type=TransactionType.EXPENSE,
                    amount=year_data.amount,
                    transaction_date=year_data.transaction_date,
                    description=f"AfA {property.address} ({year_data.year})",
                    expense_category=ExpenseCategory.DEPRECIATION_AFA,
                    is_deductible=True,
                    is_system_generated=True,
                    import_source="historical_backfill",
                    classification_confidence=Decimal("1.0")
                )
                self.db.add(transaction)
                created_transactions.append(transaction)
            
            self.db.commit()
            
            return BackfillResult(
                property_id=property_id,
                years_backfilled=len(created_transactions),
                total_amount=sum(t.amount for t in created_transactions),
                transactions=created_transactions
            )
            
        except Exception as e:
            self.db.rollback()
            raise
    
    def _depreciation_exists(self, property_id: UUID, year: int) -> bool:
        """Check if depreciation transaction already exists for year"""
        exists = self.db.query(Transaction).filter(
            Transaction.property_id == property_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            extract('year', Transaction.transaction_date) == year
        ).first()
        return exists is not None
```


### 4. AddressMatcher

**Responsibility:** Fuzzy matching of property addresses for E1/Bescheid import integration.

```python
class AddressMatcher:
    """
    Matches property addresses using fuzzy string matching.
    
    Used when importing E1/Bescheid with rental income to suggest
    linking to existing properties.
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def match_address(
        self, 
        address_string: str, 
        user_id: int
    ) -> List[AddressMatch]:
        """
        Find properties matching the given address string.
        
        Returns list of (property, confidence_score) sorted by confidence.
        
        Confidence levels:
        - > 0.9: High confidence (auto-suggest)
        - 0.7-0.9: Medium confidence (show as option)
        - < 0.7: Low confidence (don't suggest)
        """
        # Get user's properties
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE
        ).all()
        
        # Normalize input address
        normalized_input = self._normalize_address(address_string)
        
        matches = []
        for property in properties:
            # Calculate similarity scores for different components
            full_address = f"{property.street}, {property.postal_code} {property.city}"
            normalized_property = self._normalize_address(full_address)
            
            # Overall similarity
            overall_score = self._calculate_similarity(normalized_input, normalized_property)
            
            # Component-wise matching for better accuracy
            street_score = self._calculate_similarity(
                self._normalize_address(address_string),
                self._normalize_address(property.street)
            )
            
            # Postal code exact match bonus
            postal_bonus = 0.2 if property.postal_code in address_string else 0
            
            # Final confidence score
            confidence = min(
                (overall_score * 0.6 + street_score * 0.3 + postal_bonus),
                1.0
            )
            
            if confidence >= 0.7:
                matches.append(AddressMatch(
                    property=property,
                    confidence=confidence,
                    matched_components={
                        "street": street_score > 0.8,
                        "postal_code": postal_bonus > 0,
                        "city": property.city.lower() in address_string.lower()
                    }
                ))
        
        # Sort by confidence descending
        matches.sort(key=lambda m: m.confidence, reverse=True)
        return matches
    
    def _normalize_address(self, address: str) -> str:
        """Normalize address for comparison"""
        # Convert to lowercase
        normalized = address.lower()
        
        # Remove common abbreviations and standardize
        replacements = {
            "str.": "strasse",
            "straße": "strasse",
            "gasse": "gasse",
            "platz": "platz",
            "weg": "weg",
            "allee": "allee",
        }
        
        for old, new in replacements.items():
            normalized = normalized.replace(old, new)
        
        # Remove extra whitespace
        normalized = " ".join(normalized.split())
        
        return normalized
    
    def _calculate_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate string similarity using Levenshtein distance.
        
        Returns value between 0.0 (no match) and 1.0 (exact match).
        """
        from Levenshtein import ratio
        return ratio(str1, str2)
```


### 5. AnnualDepreciationService

**Responsibility:** Generate annual depreciation transactions at year-end.

```python
class AnnualDepreciationService:
    """
    Generates annual depreciation transactions for all active properties.
    
    Typically run at year-end (December 31) via Celery scheduled task.
    Can also be triggered manually by users or admins.
    """
    
    def __init__(self, db: Session):
        self.db = db
        self.afa_calculator = AfACalculator(db)
    
    def generate_annual_depreciation(
        self, 
        year: int, 
        user_id: Optional[int] = None
    ) -> AnnualDepreciationResult:
        """
        Generate depreciation transactions for all active properties.
        
        Args:
            year: Tax year to generate depreciation for
            user_id: If provided, only generate for this user's properties
        
        Returns:
            Summary of generated transactions
        """
        # Query active properties
        query = self.db.query(Property).filter(
            Property.status == PropertyStatus.ACTIVE
        )
        
        if user_id:
            query = query.filter(Property.user_id == user_id)
        
        properties = query.all()
        
        created_transactions = []
        skipped_properties = []
        
        for property in properties:
            try:
                # Check if depreciation already exists for this year
                if self._depreciation_exists(property.id, year):
                    skipped_properties.append({
                        "property_id": property.id,
                        "reason": "already_exists"
                    })
                    continue
                
                # Calculate depreciation
                amount = self.afa_calculator.calculate_annual_depreciation(property, year)
                
                if amount == Decimal("0"):
                    skipped_properties.append({
                        "property_id": property.id,
                        "reason": "fully_depreciated"
                    })
                    continue
                
                # Create transaction
                transaction = Transaction(
                    user_id=property.user_id,
                    property_id=property.id,
                    type=TransactionType.EXPENSE,
                    amount=amount,
                    transaction_date=date(year, 12, 31),
                    description=f"AfA {property.address} ({year})",
                    expense_category=ExpenseCategory.DEPRECIATION_AFA,
                    is_deductible=True,
                    is_system_generated=True,
                    import_source="annual_depreciation",
                    classification_confidence=Decimal("1.0")
                )
                
                self.db.add(transaction)
                created_transactions.append(transaction)
                
            except Exception as e:
                logger.error(f"Error generating depreciation for property {property.id}: {e}")
                skipped_properties.append({
                    "property_id": property.id,
                    "reason": f"error: {str(e)}"
                })
        
        self.db.commit()
        
        return AnnualDepreciationResult(
            year=year,
            properties_processed=len(properties),
            transactions_created=len(created_transactions),
            properties_skipped=len(skipped_properties),
            total_amount=sum(t.amount for t in created_transactions),
            transactions=created_transactions,
            skipped_details=skipped_properties
        )
    
    def _depreciation_exists(self, property_id: UUID, year: int) -> bool:
        """Check if depreciation already exists for property and year"""
        exists = self.db.query(Transaction).filter(
            Transaction.property_id == property_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            extract('year', Transaction.transaction_date) == year
        ).first()
        return exists is not None
```


## API Design

### REST API Endpoints

#### Property Management

```
POST   /api/v1/properties
GET    /api/v1/properties
GET    /api/v1/properties/{property_id}
PUT    /api/v1/properties/{property_id}
DELETE /api/v1/properties/{property_id}
POST   /api/v1/properties/{property_id}/archive
```

#### Property-Transaction Linking

```
POST   /api/v1/properties/{property_id}/link-transaction
DELETE /api/v1/properties/{property_id}/unlink-transaction/{transaction_id}
GET    /api/v1/properties/{property_id}/transactions
```

#### Historical Depreciation

```
GET    /api/v1/properties/{property_id}/historical-depreciation
POST   /api/v1/properties/{property_id}/backfill-depreciation
```

#### Annual Depreciation

```
POST   /api/v1/properties/generate-annual-depreciation
POST   /api/v1/admin/generate-annual-depreciation  (admin only)
```

#### Property Reports

```
GET    /api/v1/properties/{property_id}/reports/income-statement
GET    /api/v1/properties/{property_id}/reports/depreciation-schedule
```

### API Endpoint Details

#### POST /api/v1/properties

Create a new property.

**Request Body:**
```json
{
  "property_type": "rental",
  "rental_percentage": 100.0,
  "street": "Hauptstraße 123",
  "city": "Wien",
  "postal_code": "1010",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 280000.00,
  "construction_year": 1985,
  "depreciation_rate": 0.02
}
```

**Response (201 Created):**
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "user_id": 123,
  "property_type": "rental",
  "rental_percentage": 100.0,
  "address": "Hauptstraße 123, 1010 Wien",
  "street": "Hauptstraße 123",
  "city": "Wien",
  "postal_code": "1010",
  "purchase_date": "2020-06-15",
  "purchase_price": 350000.00,
  "building_value": 280000.00,
  "land_value": 70000.00,
  "construction_year": 1985,
  "depreciation_rate": 0.02,
  "status": "active",
  "created_at": "2026-03-07T10:30:00Z",
  "updated_at": "2026-03-07T10:30:00Z"
}
```

**Validation Errors (400 Bad Request):**
```json
{
  "detail": [
    {
      "loc": ["body", "purchase_price"],
      "msg": "purchase_price must be greater than 0",
      "type": "value_error"
    }
  ]
}
```


#### GET /api/v1/properties

List user's properties.

**Query Parameters:**
- `include_archived` (boolean, default: false) - Include archived properties
- `property_type` (string, optional) - Filter by type: rental, owner_occupied, mixed_use

**Response (200 OK):**
```json
{
  "properties": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "address": "Hauptstraße 123, 1010 Wien",
      "purchase_date": "2020-06-15",
      "building_value": 280000.00,
      "depreciation_rate": 0.02,
      "status": "active",
      "accumulated_depreciation": 33600.00,
      "remaining_depreciable_value": 246400.00
    }
  ],
  "total": 1,
  "portfolio_metrics": {
    "total_building_value": 280000.00,
    "total_annual_depreciation": 5600.00,
    "total_rental_income": 18000.00,
    "total_properties": 1
  }
}
```

#### GET /api/v1/properties/{property_id}

Get property details with linked transactions.

**Response (200 OK):**
```json
{
  "property": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "property_type": "rental",
    "address": "Hauptstraße 123, 1010 Wien",
    "purchase_date": "2020-06-15",
    "purchase_price": 350000.00,
    "building_value": 280000.00,
    "depreciation_rate": 0.02,
    "status": "active"
  },
  "metrics": {
    "accumulated_depreciation": 33600.00,
    "remaining_depreciable_value": 246400.00,
    "years_remaining": 44,
    "rental_income_ytd": 12000.00,
    "expenses_ytd": 8500.00,
    "net_income_ytd": 3500.00
  },
  "transactions": [
    {
      "id": 1001,
      "type": "income",
      "amount": 1000.00,
      "transaction_date": "2026-01-01",
      "description": "Miete Januar 2026",
      "income_category": "rental"
    },
    {
      "id": 1002,
      "type": "expense",
      "amount": 5600.00,
      "transaction_date": "2025-12-31",
      "description": "AfA Hauptstraße 123, 1010 Wien (2025)",
      "expense_category": "depreciation_afa",
      "is_system_generated": true
    }
  ]
}
```

#### POST /api/v1/properties/{property_id}/backfill-depreciation

Backfill historical depreciation.

**Response (200 OK):**
```json
{
  "property_id": "550e8400-e29b-41d4-a716-446655440000",
  "years_backfilled": 6,
  "total_amount": 33600.00,
  "transactions_created": [
    {
      "year": 2020,
      "amount": 2800.00,
      "transaction_date": "2020-12-31"
    },
    {
      "year": 2021,
      "amount": 5600.00,
      "transaction_date": "2021-12-31"
    }
  ]
}
```


## Frontend Design

### Component Architecture

```
PropertiesPage
├── PropertyList
│   ├── PropertyCard (for each property)
│   └── PropertyFilters
├── PropertyForm (modal/drawer)
│   ├── AddressFields
│   ├── PurchaseFields
│   └── DepreciationFields
├── PropertyDetail
│   ├── PropertyInfo
│   ├── PropertyMetrics
│   ├── TransactionList
│   ├── HistoricalDepreciationBackfill
│   └── PropertyActions
└── PropertyPortfolioDashboard
    ├── PortfolioMetrics
    ├── PropertyComparison (chart)
    └── DepreciationSchedule (chart)
```

### State Management (Zustand)

```typescript
interface PropertyStore {
  // State
  properties: Property[];
  selectedProperty: Property | null;
  loading: boolean;
  error: string | null;
  
  // Actions
  fetchProperties: (includeArchived?: boolean) => Promise<void>;
  fetchProperty: (id: string) => Promise<void>;
  createProperty: (data: PropertyCreate) => Promise<Property>;
  updateProperty: (id: string, data: PropertyUpdate) => Promise<Property>;
  archiveProperty: (id: string, saleDate: string) => Promise<Property>;
  deleteProperty: (id: string) => Promise<void>;
  selectProperty: (id: string | null) => void;
  
  // Property linking
  linkTransaction: (propertyId: string, transactionId: number) => Promise<void>;
  unlinkTransaction: (propertyId: string, transactionId: number) => Promise<void>;
  
  // Historical depreciation
  previewHistoricalDepreciation: (propertyId: string) => Promise<HistoricalYear[]>;
  backfillDepreciation: (propertyId: string) => Promise<BackfillResult>;
}
```

### Key Components

#### PropertyForm Component

```typescript
interface PropertyFormProps {
  property?: Property;  // For edit mode
  onSubmit: (data: PropertyCreate | PropertyUpdate) => Promise<void>;
  onCancel: () => void;
}

const PropertyForm: React.FC<PropertyFormProps> = ({ property, onSubmit, onCancel }) => {
  const { register, handleSubmit, watch, setValue, formState: { errors } } = useForm<PropertyFormData>({
    resolver: zodResolver(propertySchema),
    defaultValues: property || {
      property_type: 'rental',
      rental_percentage: 100,
      depreciation_rate: 0.02
    }
  });
  
  // Auto-calculate building_value as 80% if not provided
  const purchasePrice = watch('purchase_price');
  useEffect(() => {
    if (purchasePrice && !watch('building_value')) {
      setValue('building_value', purchasePrice * 0.8);
    }
  }, [purchasePrice]);
  
  // Auto-determine depreciation_rate based on construction_year
  const constructionYear = watch('construction_year');
  useEffect(() => {
    if (constructionYear) {
      const rate = constructionYear < 1915 ? 0.015 : 0.02;
      setValue('depreciation_rate', rate);
    }
  }, [constructionYear]);
  
  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Form fields */}
    </form>
  );
};
```


#### PropertyList Component

```typescript
interface PropertyListProps {
  includeArchived?: boolean;
}

const PropertyList: React.FC<PropertyListProps> = ({ includeArchived = false }) => {
  const { properties, loading, fetchProperties } = usePropertyStore();
  const { t } = useTranslation();
  
  useEffect(() => {
    fetchProperties(includeArchived);
  }, [includeArchived]);
  
  if (loading) return <LoadingSpinner />;
  
  return (
    <div className="property-list">
      {properties.map(property => (
        <PropertyCard key={property.id} property={property} />
      ))}
    </div>
  );
};

const PropertyCard: React.FC<{ property: Property }> = ({ property }) => {
  const navigate = useNavigate();
  const { t } = useTranslation();
  
  const accumulatedDepreciation = property.accumulated_depreciation || 0;
  const remainingValue = property.building_value - accumulatedDepreciation;
  const depreciationProgress = (accumulatedDepreciation / property.building_value) * 100;
  
  return (
    <div className="property-card" onClick={() => navigate(`/properties/${property.id}`)}>
      <div className="property-header">
        <h3>{property.address}</h3>
        <span className={`status-badge ${property.status}`}>
          {t(`properties.status.${property.status}`)}
        </span>
      </div>
      
      <div className="property-details">
        <div className="detail-row">
          <span>{t('properties.purchaseDate')}:</span>
          <span>{formatDate(property.purchase_date)}</span>
        </div>
        <div className="detail-row">
          <span>{t('properties.buildingValue')}:</span>
          <span>{formatCurrency(property.building_value)}</span>
        </div>
        <div className="detail-row">
          <span>{t('properties.depreciationRate')}:</span>
          <span>{(property.depreciation_rate * 100).toFixed(1)}%</span>
        </div>
      </div>
      
      <div className="depreciation-progress">
        <div className="progress-header">
          <span>{t('properties.accumulatedDepreciation')}</span>
          <span>{formatCurrency(accumulatedDepreciation)}</span>
        </div>
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${depreciationProgress}%` }}
          />
        </div>
        <div className="progress-footer">
          <span>{t('properties.remainingValue')}: {formatCurrency(remainingValue)}</span>
        </div>
      </div>
    </div>
  );
};
```

#### PropertyDetail Component

```typescript
const PropertyDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { selectedProperty, loading, fetchProperty } = usePropertyStore();
  const { t } = useTranslation();
  
  useEffect(() => {
    if (id) fetchProperty(id);
  }, [id]);
  
  if (loading || !selectedProperty) return <LoadingSpinner />;
  
  return (
    <div className="property-detail">
      <PropertyInfo property={selectedProperty} />
      <PropertyMetrics property={selectedProperty} />
      <TransactionList propertyId={selectedProperty.id} />
      <HistoricalDepreciationBackfill property={selectedProperty} />
    </div>
  );
};
```


#### HistoricalDepreciationBackfill Component

```typescript
const HistoricalDepreciationBackfill: React.FC<{ property: Property }> = ({ property }) => {
  const [preview, setPreview] = useState<HistoricalYear[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [loading, setLoading] = useState(false);
  const { backfillDepreciation, previewHistoricalDepreciation } = usePropertyStore();
  const { t } = useTranslation();
  
  // Check if property needs backfill
  const needsBackfill = property.purchase_date < new Date(new Date().getFullYear(), 0, 1);
  
  if (!needsBackfill) return null;
  
  const handlePreview = async () => {
    setLoading(true);
    try {
      const years = await previewHistoricalDepreciation(property.id);
      setPreview(years);
      setShowModal(true);
    } catch (error) {
      toast.error(t('properties.backfill.previewError'));
    } finally {
      setLoading(false);
    }
  };
  
  const handleConfirm = async () => {
    setLoading(true);
    try {
      await backfillDepreciation(property.id);
      toast.success(t('properties.backfill.success'));
      setShowModal(false);
    } catch (error) {
      toast.error(t('properties.backfill.error'));
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div className="historical-backfill">
      <div className="backfill-notice">
        <InfoIcon />
        <p>{t('properties.backfill.notice')}</p>
        <button onClick={handlePreview} disabled={loading}>
          {t('properties.backfill.preview')}
        </button>
      </div>
      
      {showModal && (
        <Modal onClose={() => setShowModal(false)}>
          <h2>{t('properties.backfill.title')}</h2>
          <p>{t('properties.backfill.description')}</p>
          
          <table className="backfill-preview">
            <thead>
              <tr>
                <th>{t('properties.backfill.year')}</th>
                <th>{t('properties.backfill.amount')}</th>
              </tr>
            </thead>
            <tbody>
              {preview.map(year => (
                <tr key={year.year}>
                  <td>{year.year}</td>
                  <td>{formatCurrency(year.amount)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td><strong>{t('properties.backfill.total')}</strong></td>
                <td><strong>{formatCurrency(preview.reduce((sum, y) => sum + y.amount, 0))}</strong></td>
              </tr>
            </tfoot>
          </table>
          
          <div className="modal-actions">
            <button onClick={() => setShowModal(false)}>
              {t('common.cancel')}
            </button>
            <button onClick={handleConfirm} disabled={loading} className="primary">
              {t('properties.backfill.confirm')}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
};
```


## Integration Points

### 1. E1 Form Import Integration

**Modification to E1FormImportService:**

```python
class E1FormImportService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = E1FormExtractor()
        self.address_matcher = AddressMatcher(db)  # NEW
    
    def import_e1_data(
        self, 
        data: E1FormData, 
        user_id: int, 
        document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        # ... existing code ...
        
        # NEW: Property linking for rental income (KZ 350)
        property_suggestions = []
        if data.kz_350 and data.kz_350 > 0:
            # Try to match property if address available
            if data.vermietung_details:
                for detail in data.vermietung_details:
                    address = detail.get("address", "")
                    matches = self.address_matcher.match_address(address, user_id)
                    property_suggestions.append({
                        "extracted_address": address,
                        "matches": [
                            {
                                "property_id": str(m.property.id),
                                "address": m.property.address,
                                "confidence": float(m.confidence),
                                "suggested_action": self._get_suggested_action(m.confidence)
                            }
                            for m in matches
                        ]
                    })
        
        return {
            # ... existing fields ...
            "property_linking_required": len(property_suggestions) > 0,
            "property_suggestions": property_suggestions
        }
    
    def _get_suggested_action(self, confidence: float) -> str:
        if confidence > 0.9:
            return "auto_link"
        elif confidence >= 0.7:
            return "suggest"
        else:
            return "create_new"
```

### 2. Bescheid Import Integration

**Modification to BescheidImportService:**

```python
class BescheidImportService:
    def __init__(self, db: Session):
        self.db = db
        self.extractor = BescheidExtractor()
        self.address_matcher = AddressMatcher(db)  # NEW
    
    def import_bescheid_data(
        self, 
        data: BescheidData, 
        user_id: int, 
        document_id: Optional[int] = None
    ) -> Dict[str, Any]:
        # ... existing code ...
        
        # NEW: Auto-match properties from vermietung_details
        property_suggestions = []
        if data.vermietung_details:
            for detail in data.vermietung_details:
                address = detail.get("address", "")
                matches = self.address_matcher.match_address(address, user_id)
                
                property_suggestions.append({
                    "extracted_address": address,
                    "rental_income": float(detail.get("amount", 0)),
                    "matches": [
                        {
                            "property_id": str(m.property.id),
                            "address": m.property.address,
                            "confidence": float(m.confidence),
                            "suggested_action": self._get_suggested_action(m.confidence)
                        }
                        for m in matches
                    ]
                })
        
        return {
            # ... existing fields ...
            "property_linking_required": len(property_suggestions) > 0,
            "property_suggestions": property_suggestions
        }
```


### 3. Tax Calculation Engine Integration

**Modification to TaxCalculationEngine:**

```python
class TaxCalculationEngine:
    def calculate_tax(self, user_id: int, year: int) -> TaxCalculation:
        # ... existing code ...
        
        # NEW: Include property depreciation in deductions
        property_depreciation = self._calculate_property_depreciation(user_id, year)
        total_deductions += property_depreciation
        
        # NEW: Include rental income in total income
        rental_income = self._calculate_rental_income(user_id, year)
        total_income += rental_income
        
        # NEW: Include property expenses
        property_expenses = self._calculate_property_expenses(user_id, year)
        total_deductions += property_expenses
        
        # ... rest of calculation ...
    
    def _calculate_property_depreciation(self, user_id: int, year: int) -> Decimal:
        """Sum all depreciation transactions for user's properties in year"""
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        return total or Decimal("0")
    
    def _calculate_rental_income(self, user_id: int, year: int) -> Decimal:
        """Sum all rental income transactions in year"""
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.income_category == IncomeCategory.RENTAL,
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        return total or Decimal("0")
    
    def _calculate_property_expenses(self, user_id: int, year: int) -> Decimal:
        """Sum all property-related expenses (excluding depreciation)"""
        property_expense_categories = [
            ExpenseCategory.LOAN_INTEREST,
            ExpenseCategory.MAINTENANCE,
            ExpenseCategory.PROPERTY_MANAGEMENT_FEES,
            ExpenseCategory.PROPERTY_INSURANCE,
            ExpenseCategory.PROPERTY_TAX,
            ExpenseCategory.UTILITIES
        ]
        
        total = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.expense_category.in_(property_expense_categories),
            Transaction.property_id.isnot(None),  # Only property-linked expenses
            extract('year', Transaction.transaction_date) == year
        ).scalar()
        return total or Decimal("0")
```

### 4. Dashboard Integration

**Modification to DashboardService:**

```python
class DashboardService:
    def get_dashboard_data(self, user_id: int) -> DashboardData:
        # ... existing code ...
        
        # NEW: Add property portfolio metrics for landlords
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if user.user_type in [UserType.LANDLORD, UserType.MIXED]:
            portfolio_metrics = self._get_property_portfolio_metrics(user_id)
            dashboard_data["property_portfolio"] = portfolio_metrics
        
        return dashboard_data
    
    def _get_property_portfolio_metrics(self, user_id: int) -> Dict[str, Any]:
        """Calculate portfolio-level metrics for landlord dashboard"""
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE
        ).all()
        
        if not properties:
            return None
        
        current_year = date.today().year
        
        # Calculate totals
        total_building_value = sum(p.building_value for p in properties)
        total_annual_depreciation = sum(
            self.afa_calculator.calculate_annual_depreciation(p, current_year)
            for p in properties
        )
        
        # Get YTD rental income
        rental_income_ytd = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.INCOME,
            Transaction.income_category == IncomeCategory.RENTAL,
            extract('year', Transaction.transaction_date) == current_year
        ).scalar() or Decimal("0")
        
        # Get YTD property expenses
        expenses_ytd = self.db.query(func.sum(Transaction.amount)).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.property_id.isnot(None),
            extract('year', Transaction.transaction_date) == current_year
        ).scalar() or Decimal("0")
        
        return {
            "total_properties": len(properties),
            "total_building_value": float(total_building_value),
            "total_annual_depreciation": float(total_annual_depreciation),
            "rental_income_ytd": float(rental_income_ytd),
            "expenses_ytd": float(expenses_ytd),
            "net_income_ytd": float(rental_income_ytd - expenses_ytd)
        }
```


## Data Flow Diagrams

### Property Registration Flow

```
User → PropertyForm → PropertyService.create_property()
                            ↓
                      Validate data
                            ↓
                      Auto-calculate:
                      - building_value (80% if not provided)
                      - depreciation_rate (based on construction_year)
                      - land_value (purchase_price - building_value)
                            ↓
                      Create Property record
                            ↓
                      Return Property ← User sees confirmation
```

### Historical Depreciation Backfill Flow

```
User → PropertyDetail → "Backfill" button
                            ↓
                      HistoricalDepreciationService.calculate_historical_depreciation()
                            ↓
                      For each year from purchase_date to current:
                        - Calculate depreciation amount
                        - Check if already exists
                            ↓
                      Show preview to user
                            ↓
                      User confirms
                            ↓
                      HistoricalDepreciationService.backfill_depreciation()
                            ↓
                      Create Transaction records:
                        - type: EXPENSE
                        - category: DEPRECIATION_AFA
                        - is_system_generated: true
                        - date: December 31 of each year
                            ↓
                      Return summary ← User sees success message
```

### E1 Import with Property Linking Flow

```
User uploads E1 PDF → E1FormImportService.import_from_ocr_text()
                            ↓
                      Extract KZ 350 (rental income)
                            ↓
                      AddressMatcher.match_address()
                            ↓
                      Find matching properties with confidence scores
                            ↓
                      Return import result with property_suggestions
                            ↓
User sees suggestions → PropertyLinkingSuggestions component
                            ↓
                      User selects:
                      - Link to existing property
                      - Create new property
                      - Skip
                            ↓
                      PropertyService.link_transaction()
                            ↓
                      Update Transaction.property_id
                            ↓
                      Return success ← User sees linked transaction
```

### Annual Depreciation Generation Flow (Automated)

```
Celery Beat Schedule → December 31, 23:00
                            ↓
                      AnnualDepreciationService.generate_annual_depreciation()
                            ↓
                      Query all active properties
                            ↓
                      For each property:
                        - Check if depreciation already exists for year
                        - Calculate annual depreciation
                        - Create Transaction if amount > 0
                            ↓
                      Commit all transactions
                            ↓
                      Send notification email to users
                            ↓
                      Log summary (properties processed, transactions created)
```


## Security & Privacy Considerations

### Data Encryption

**Property addresses are sensitive personal data and must be encrypted:**

```python
from app.core.encryption import encrypt_field, decrypt_field

class Property(Base):
    __tablename__ = "properties"
    
    # Encrypted fields
    _address = Column("address", String(1000), nullable=False)
    _street = Column("street", String(500), nullable=False)
    _city = Column("city", String(200), nullable=False)
    
    @hybrid_property
    def address(self):
        return decrypt_field(self._address)
    
    @address.setter
    def address(self, value):
        self._address = encrypt_field(value)
    
    # Similar for street and city
```

### Access Control

**All property operations must validate ownership:**

```python
def _validate_ownership(self, property_id: UUID, user_id: int) -> Property:
    """Validate that property belongs to user"""
    property = self.db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == user_id
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=404,
            detail="Property not found or access denied"
        )
    
    return property
```

### GDPR Compliance

**Property data deletion:**

```python
def delete_user_data(self, user_id: int):
    """
    Delete all user data including properties (GDPR right to erasure).
    
    Cascade delete will handle:
    - Properties
    - Transactions (including property-linked)
    - Documents
    """
    # Properties will be deleted via CASCADE
    user = self.db.query(User).filter(User.id == user_id).first()
    self.db.delete(user)
    self.db.commit()
```

### Audit Logging

**Log all property operations:**

```python
def _log_property_operation(
    self, 
    operation: str, 
    property_id: UUID, 
    user_id: int, 
    details: Dict[str, Any]
):
    """Log property operations for audit trail"""
    audit_log = AuditLog(
        user_id=user_id,
        operation=operation,
        entity_type="property",
        entity_id=str(property_id),
        details=details,
        timestamp=datetime.utcnow()
    )
    self.db.add(audit_log)
```

## Performance Optimization

### Database Indexing

```sql
-- Critical indexes for property queries
CREATE INDEX idx_properties_user_id ON properties(user_id);
CREATE INDEX idx_properties_status ON properties(status);
CREATE INDEX idx_properties_user_status ON properties(user_id, status);

-- Indexes for transaction-property queries
CREATE INDEX idx_transactions_property_id ON transactions(property_id);
CREATE INDEX idx_transactions_property_date ON transactions(property_id, transaction_date);
CREATE INDEX idx_transactions_user_property ON transactions(user_id, property_id);

-- Index for depreciation queries
CREATE INDEX idx_transactions_depreciation ON transactions(expense_category, transaction_date) 
WHERE expense_category = 'depreciation_afa';
```

### Caching Strategy

```python
from app.core.cache import cache_result

class PropertyService:
    @cache_result(ttl=3600)  # Cache for 1 hour
    def get_property_metrics(self, property_id: UUID) -> PropertyMetrics:
        """
        Calculate property metrics with caching.
        Cache invalidated on:
        - Property update
        - Transaction creation/update/delete
        """
        # ... calculation logic ...
    
    def update_property(self, property_id: UUID, updates: PropertyUpdate):
        # ... update logic ...
        
        # Invalidate cache
        cache.delete(f"property_metrics:{property_id}")
```

### Query Optimization

```python
def list_properties_with_metrics(self, user_id: int) -> List[PropertyWithMetrics]:
    """
    Optimized query using joins and aggregations.
    Avoids N+1 query problem.
    """
    # Single query with aggregations
    query = self.db.query(
        Property,
        func.coalesce(func.sum(Transaction.amount), 0).label('accumulated_depreciation')
    ).outerjoin(
        Transaction,
        and_(
            Transaction.property_id == Property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        )
    ).filter(
        Property.user_id == user_id
    ).group_by(Property.id)
    
    results = query.all()
    
    return [
        PropertyWithMetrics(
            property=prop,
            accumulated_depreciation=acc_dep,
            remaining_value=prop.building_value - acc_dep
        )
        for prop, acc_dep in results
    ]
```


## Testing Strategy

### Unit Tests

**Test AfACalculator:**

```python
class TestAfACalculator:
    def test_determine_depreciation_rate_pre_1915(self):
        calculator = AfACalculator()
        rate = calculator.determine_depreciation_rate(1900)
        assert rate == Decimal("0.015")
    
    def test_determine_depreciation_rate_post_1915(self):
        calculator = AfACalculator()
        rate = calculator.determine_depreciation_rate(1985)
        assert rate == Decimal("0.020")
    
    def test_calculate_annual_depreciation_full_year(self):
        property = Property(
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02"),
            purchase_date=date(2020, 1, 1)
        )
        calculator = AfACalculator()
        depreciation = calculator.calculate_annual_depreciation(property, 2021)
        assert depreciation == Decimal("5600.00")
    
    def test_calculate_annual_depreciation_partial_year(self):
        property = Property(
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02"),
            purchase_date=date(2020, 7, 1)  # Mid-year purchase
        )
        calculator = AfACalculator()
        depreciation = calculator.calculate_annual_depreciation(property, 2020)
        # 6 months: (280000 * 0.02 * 6) / 12 = 2800
        assert depreciation == Decimal("2800.00")
    
    def test_depreciation_stops_at_building_value(self):
        property = Property(
            building_value=Decimal("10000"),
            depreciation_rate=Decimal("0.02"),
            purchase_date=date(1970, 1, 1)
        )
        calculator = AfACalculator()
        # After 50 years, should be fully depreciated
        depreciation = calculator.calculate_annual_depreciation(property, 2025)
        assert depreciation == Decimal("0.00")
```

### Property-Based Tests (Hypothesis)

```python
from hypothesis import given, strategies as st
from decimal import Decimal

class TestAfAProperties:
    @given(
        building_value=st.decimals(
            min_value=10000, 
            max_value=1000000, 
            places=2
        ),
        depreciation_rate=st.decimals(
            min_value=Decimal("0.015"), 
            max_value=Decimal("0.02"), 
            places=4
        )
    )
    def test_annual_depreciation_consistency(self, building_value, depreciation_rate):
        """Property: annual_depreciation = building_value * depreciation_rate"""
        expected = building_value * depreciation_rate
        expected = expected.quantize(Decimal("0.01"))
        
        property = Property(
            building_value=building_value,
            depreciation_rate=depreciation_rate,
            purchase_date=date(2020, 1, 1)
        )
        
        calculator = AfACalculator()
        actual = calculator.calculate_annual_depreciation(property, 2021)
        
        assert abs(actual - expected) < Decimal("0.01")
    
    @given(
        building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
        depreciation_rate=st.decimals(min_value=Decimal("0.015"), max_value=Decimal("0.02"), places=4)
    )
    def test_depreciation_idempotence(self, building_value, depreciation_rate):
        """Property: Calculating depreciation twice produces same result"""
        property = Property(
            building_value=building_value,
            depreciation_rate=depreciation_rate,
            purchase_date=date(2020, 1, 1)
        )
        
        calculator = AfACalculator()
        result1 = calculator.calculate_annual_depreciation(property, 2021)
        result2 = calculator.calculate_annual_depreciation(property, 2021)
        
        assert result1 == result2
    
    @given(
        building_value=st.decimals(min_value=10000, max_value=1000000, places=2),
        rate1=st.decimals(min_value=Decimal("0.015"), max_value=Decimal("0.02"), places=4)
    )
    def test_depreciation_rate_metamorphic(self, building_value, rate1):
        """Property: Doubling rate doubles depreciation"""
        rate2 = rate1 * 2
        
        property1 = Property(
            building_value=building_value,
            depreciation_rate=rate1,
            purchase_date=date(2020, 1, 1)
        )
        
        property2 = Property(
            building_value=building_value,
            depreciation_rate=rate2,
            purchase_date=date(2020, 1, 1)
        )
        
        calculator = AfACalculator()
        dep1 = calculator.calculate_annual_depreciation(property1, 2021)
        dep2 = calculator.calculate_annual_depreciation(property2, 2021)
        
        # Allow small rounding tolerance
        assert abs(dep2 - (dep1 * 2)) < Decimal("0.02")
```


### Integration Tests

```python
class TestPropertyImportIntegration:
    def test_e1_import_with_property_linking(self, db_session, test_user):
        """Test E1 import suggests property linking for rental income"""
        # Setup: Create existing property
        property = Property(
            user_id=test_user.id,
            street="Hauptstraße 123",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2020, 1, 1),
            purchase_price=Decimal("350000"),
            building_value=Decimal("280000"),
            depreciation_rate=Decimal("0.02")
        )
        db_session.add(property)
        db_session.commit()
        
        # Import E1 with rental income
        e1_text = """
        Einkommensteuererklärung für 2025
        KZ 350: 18.000,00
        Vermietung: Hauptstraße 123, 1010 Wien
        """
        
        service = E1FormImportService(db_session)
        result = service.import_from_ocr_text(e1_text, test_user.id)
        
        # Verify property linking suggestions
        assert result["property_linking_required"] is True
        assert len(result["property_suggestions"]) == 1
        
        suggestion = result["property_suggestions"][0]
        assert suggestion["extracted_address"] == "Hauptstraße 123, 1010 Wien"
        assert len(suggestion["matches"]) == 1
        assert suggestion["matches"][0]["confidence"] > 0.9
        assert suggestion["matches"][0]["suggested_action"] == "auto_link"
    
    def test_historical_depreciation_backfill_integration(self, db_session, test_user):
        """Test complete historical depreciation backfill flow"""
        # Create property purchased 3 years ago
        property = Property(
            user_id=test_user.id,
            street="Teststraße 1",
            city="Wien",
            postal_code="1010",
            purchase_date=date(2022, 6, 15),
            purchase_price=Decimal("300000"),
            building_value=Decimal("240000"),
            depreciation_rate=Decimal("0.02")
        )
        db_session.add(property)
        db_session.commit()
        
        # Backfill depreciation
        service = HistoricalDepreciationService(db_session)
        result = service.backfill_depreciation(property.id, test_user.id)
        
        # Verify transactions created
        assert result.years_backfilled == 4  # 2022, 2023, 2024, 2025
        
        # Verify amounts
        transactions = db_session.query(Transaction).filter(
            Transaction.property_id == property.id,
            Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
        ).order_by(Transaction.transaction_date).all()
        
        assert len(transactions) == 4
        
        # 2022: Partial year (6.5 months)
        assert transactions[0].amount == Decimal("2600.00")
        
        # 2023-2025: Full years
        for txn in transactions[1:]:
            assert txn.amount == Decimal("4800.00")
            assert txn.is_system_generated is True
```

### End-to-End Tests

```python
class TestPropertyE2E:
    def test_complete_property_lifecycle(self, client, test_user_token):
        """Test complete property management lifecycle"""
        headers = {"Authorization": f"Bearer {test_user_token}"}
        
        # 1. Create property
        property_data = {
            "street": "Teststraße 100",
            "city": "Wien",
            "postal_code": "1010",
            "purchase_date": "2020-01-15",
            "purchase_price": 400000.00,
            "construction_year": 1990
        }
        
        response = client.post("/api/v1/properties", json=property_data, headers=headers)
        assert response.status_code == 201
        property_id = response.json()["id"]
        
        # Verify auto-calculations
        property = response.json()
        assert property["building_value"] == 320000.00  # 80% of purchase_price
        assert property["depreciation_rate"] == 0.02  # Post-1915 building
        
        # 2. Backfill historical depreciation
        response = client.post(
            f"/api/v1/properties/{property_id}/backfill-depreciation",
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["years_backfilled"] == 6  # 2020-2025
        
        # 3. Create rental income transaction
        transaction_data = {
            "type": "income",
            "amount": 1200.00,
            "transaction_date": "2025-01-01",
            "description": "Miete Januar 2025",
            "income_category": "rental"
        }
        
        response = client.post("/api/v1/transactions", json=transaction_data, headers=headers)
        assert response.status_code == 201
        transaction_id = response.json()["id"]
        
        # 4. Link transaction to property
        response = client.post(
            f"/api/v1/properties/{property_id}/link-transaction",
            json={"transaction_id": transaction_id},
            headers=headers
        )
        assert response.status_code == 200
        
        # 5. Get property with metrics
        response = client.get(f"/api/v1/properties/{property_id}", headers=headers)
        assert response.status_code == 200
        
        property_detail = response.json()
        assert property_detail["metrics"]["rental_income_ytd"] == 1200.00
        assert property_detail["metrics"]["accumulated_depreciation"] > 0
        
        # 6. Archive property
        response = client.post(
            f"/api/v1/properties/{property_id}/archive",
            json={"sale_date": "2025-12-31"},
            headers=headers
        )
        assert response.status_code == 200
        assert response.json()["status"] == "archived"
```


## Error Handling

### Common Error Scenarios

```python
class PropertyError(Exception):
    """Base exception for property-related errors"""
    pass

class PropertyNotFoundError(PropertyError):
    """Property does not exist or user doesn't have access"""
    pass

class PropertyValidationError(PropertyError):
    """Property data validation failed"""
    pass

class DepreciationAlreadyExistsError(PropertyError):
    """Depreciation transaction already exists for property and year"""
    pass

class PropertyHasTransactionsError(PropertyError):
    """Cannot delete property with linked transactions"""
    pass

# Error handling in API endpoints
@router.post("/properties")
async def create_property(
    property_data: PropertyCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        service = PropertyService(db)
        property = service.create_property(current_user.id, property_data)
        return property
    except PropertyValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating property: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.delete("/properties/{property_id}")
async def delete_property(
    property_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        service = PropertyService(db)
        service.delete_property(property_id, current_user.id)
        return {"message": "Property deleted successfully"}
    except PropertyNotFoundError:
        raise HTTPException(status_code=404, detail="Property not found")
    except PropertyHasTransactionsError:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete property with linked transactions. Archive it instead."
        )
```

## Deployment Considerations

### Database Migration Strategy

```bash
# Phase 1: Add property table and extend transactions
alembic revision --autogenerate -m "add_property_table"
alembic revision --autogenerate -m "add_property_id_to_transactions"
alembic revision --autogenerate -m "add_system_generated_flag"

# Deploy to staging
alembic upgrade head

# Run tests
pytest

# Deploy to production
alembic upgrade head
```

### Celery Task Configuration

```python
# backend/app/core/celery_app.py

from celery.schedules import crontab

app.conf.beat_schedule = {
    'generate-annual-depreciation': {
        'task': 'app.tasks.property_tasks.generate_annual_depreciation_task',
        'schedule': crontab(month_of_year=12, day_of_month=31, hour=23, minute=0),
        'args': (datetime.now().year,)
    },
}
```

### Monitoring & Alerting

```python
# Log key metrics for monitoring
import logging
from prometheus_client import Counter, Histogram

property_created_counter = Counter('property_created_total', 'Total properties created')
depreciation_generated_counter = Counter('depreciation_generated_total', 'Total depreciation transactions generated')
backfill_duration = Histogram('backfill_duration_seconds', 'Time to backfill depreciation')

class PropertyService:
    def create_property(self, user_id: int, property_data: PropertyCreate):
        # ... creation logic ...
        property_created_counter.inc()
        logger.info(f"Property created: {property.id} for user {user_id}")
        return property
    
    def backfill_depreciation(self, property_id: UUID, user_id: int):
        with backfill_duration.time():
            # ... backfill logic ...
            depreciation_generated_counter.inc(len(created_transactions))
            logger.info(f"Backfilled {len(created_transactions)} depreciation transactions for property {property_id}")
```


## Future Enhancements (Phase 3)

### Contract OCR Architecture

```
User uploads PDF → OCRService.process_document()
                        ↓
                  Detect document type:
                  - Kaufvertrag (purchase contract)
                  - Mietvertrag (rental contract)
                        ↓
                  Route to appropriate extractor:
                  - KaufvertragExtractor
                  - MietvertragExtractor
                        ↓
                  Extract fields with confidence scores
                        ↓
                  Return structured data
                        ↓
User reviews/edits → PropertyService.create_from_contract()
                        ↓
                  Create Property record
                  Link contract document
```

### Loan Tracking Data Model

```sql
CREATE TABLE property_loans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    loan_amount NUMERIC(12,2) NOT NULL,
    interest_rate NUMERIC(5,4) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    monthly_payment NUMERIC(12,2),
    lender_name VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_property_loans_property_id ON property_loans(property_id);
```

### Tenant Management Data Model

```sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    property_id UUID NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    phone VARCHAR(50),
    move_in_date DATE NOT NULL,
    move_out_date DATE,
    monthly_rent NUMERIC(12,2) NOT NULL,
    deposit_amount NUMERIC(12,2),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_tenants_property_id ON tenants(property_id);
CREATE INDEX idx_tenants_current ON tenants(property_id, move_out_date) WHERE move_out_date IS NULL;
```

## Design Decisions & Rationale

### 1. Why UUID for Property ID?

**Decision:** Use UUID instead of auto-incrementing integer.

**Rationale:**
- Better for distributed systems and data migration
- Prevents enumeration attacks
- Easier to merge data from multiple sources
- Standard practice for sensitive entities

### 2. Why Store Depreciation as Transactions?

**Decision:** Create Transaction records for depreciation instead of calculated fields.

**Rationale:**
- Maintains audit trail
- Consistent with other income/expense tracking
- Allows manual adjustments if needed
- Simplifies tax calculation (all deductions are transactions)
- Supports historical backfill

### 3. Why Separate Property Types (Rental, Owner-Occupied, Mixed-Use)?

**Decision:** Support multiple property types with different tax treatment.

**Rationale:**
- Austrian tax law treats them differently
- Owner-occupied properties: no depreciation, limited deductions
- Rental properties: full depreciation and expense deductions
- Mixed-use: proportional allocation based on rental percentage
- Future-proofs for home office deductions

### 4. Why Auto-Calculate Building Value as 80%?

**Decision:** Default building value to 80% of purchase price if not provided.

**Rationale:**
- Common Austrian tax convention for land/building split
- Simplifies data entry for users
- Can be overridden if user has exact values from Kaufvertrag
- Conservative estimate (land typically 15-25% of total)

### 5. Why Fuzzy Address Matching Instead of Exact?

**Decision:** Use Levenshtein distance for address matching.

**Rationale:**
- OCR may have minor errors (typos, formatting)
- Different address formats (abbreviations, spacing)
- User may enter address slightly differently
- Confidence scores allow user to review and confirm

### 6. Why Generate Depreciation on December 31?

**Decision:** All depreciation transactions dated December 31 of tax year.

**Rationale:**
- Austrian tax law: depreciation claimed annually
- Simplifies year-end reporting
- Consistent with E1 form structure
- Easier to query and aggregate


## Summary

This design document provides a comprehensive technical blueprint for implementing property asset management in the Taxja platform. The design follows these key principles:

1. **Layered Architecture:** Clear separation between API, service, and data layers
2. **Austrian Tax Law Compliance:** Accurate AfA calculations following § 7 and § 8 EStG
3. **Integration-First:** Seamless integration with existing E1/Bescheid import and tax calculation
4. **User-Friendly:** Auto-calculations, fuzzy matching, and guided workflows
5. **Secure & Private:** GDPR-compliant with encryption and access control
6. **Testable:** Comprehensive testing strategy including property-based tests
7. **Scalable:** Optimized queries, caching, and async processing
8. **Maintainable:** Clear service boundaries and error handling

### Key Components

- **PropertyService:** Core CRUD and business logic
- **AfACalculator:** Depreciation calculations per Austrian tax law
- **HistoricalDepreciationService:** Backfill depreciation for existing properties
- **AddressMatcher:** Fuzzy matching for E1/Bescheid integration
- **AnnualDepreciationService:** Automated year-end depreciation generation

### Implementation Phases

**Phase 1 (MVP):** Core property management, manual registration, depreciation calculation
**Phase 2:** E1/Bescheid integration, historical backfill, portfolio dashboard
**Phase 3:** Contract OCR, loan tracking, tenant management, advanced reports

### Success Metrics

- Property registration completion rate > 90%
- Address matching accuracy > 80%
- Depreciation calculation accuracy: 100% (validated by property-based tests)
- Historical backfill success rate > 95%
- User satisfaction with property management features > 4.5/5

### Next Steps

1. Review and approve design document
2. Create database migrations (Task 1.2)
3. Implement core services (Tasks 1.5, 1.6)
4. Build API endpoints (Task 1.7)
5. Develop frontend components (Tasks 1.14-1.17)
6. Write comprehensive tests (Tasks 1.9, 1.10)
7. Integration testing (Task 2.13)
8. User acceptance testing
9. Production deployment

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Authors:** Kiro AI Assistant  
**Status:** Ready for Review
