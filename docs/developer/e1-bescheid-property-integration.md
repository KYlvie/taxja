# E1/Bescheid Property Integration Guide

## Overview

This document provides comprehensive technical documentation for integrating property management with E1 tax declaration and Bescheid (tax assessment) import functionality. The integration enables automatic property linking when importing rental income data from Austrian tax documents.

## Architecture

### Integration Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    E1/Bescheid Import                            │
│                  (OCR Text Extraction)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              E1FormImportService /                               │
│            BescheidImportService                                 │
│                                                                  │
│  • Extract KZ 350 (rental income)                               │
│  • Extract property addresses                                   │
│  • Create rental income transactions                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AddressMatcher                                  │
│                                                                  │
│  • Normalize addresses                                          │
│  • Fuzzy string matching (Levenshtein)                         │
│  • Calculate confidence scores                                  │
│  • Return ranked property matches                               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              Property Linking Suggestions                        │
│                                                                  │
│  • High confidence (>0.9): Auto-suggest                         │
│  • Medium confidence (0.7-0.9): Show options                    │
│  • Low confidence (<0.7): Suggest create new                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  User Confirmation                               │
│                  (Frontend UI)                                   │
│                                                                  │
│  • Review suggestions                                           │
│  • Confirm or override                                          │
│  • Create new property if needed                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              PropertyService.link_transaction()                  │
│                                                                  │
│  • Link transaction to property                                 │
│  • Update property_id on transaction                            │
│  • Validate ownership                                           │
└─────────────────────────────────────────────────────────────────┘
```

## Component Details

### 1. E1FormImportService Integration

**Location:** `backend/app/services/e1_form_import_service.py`


#### Key Methods

##### `_generate_property_suggestions()`

Generates property linking suggestions when KZ 350 (rental income) is detected.

**Implementation:**
```python
def _generate_property_suggestions(
    self, 
    vermietung_details: List[Dict], 
    user_id: int
) -> List[Dict]:
    """
    Generate property linking suggestions from E1 rental income data.
    
    Args:
        vermietung_details: List of rental income entries with addresses
        user_id: User ID for property matching
    
    Returns:
        List of property suggestions with confidence scores
    """
    suggestions = []
    
    for detail in vermietung_details:
        address = detail.get("address", "")
        if not address:
            continue
        
        # Use AddressMatcher to find matching properties
        matches = self.address_matcher.match_address(address, user_id)
        
        suggestion = {
            "extracted_address": address,
            "rental_income": detail.get("amount", 0),
            "matches": [
                {
                    "property_id": str(match.property.id),
                    "property_address": match.property.address,
                    "confidence": float(match.confidence),
                    "suggested_action": self._determine_action(match.confidence),
                    "matched_components": match.matched_components
                }
                for match in matches
            ]
        }
        
        suggestions.append(suggestion)
    
    return suggestions
```

##### `_determine_action()`

Determines suggested action based on confidence score.

**Implementation:**
```python
def _determine_action(self, confidence: float) -> str:
    """
    Determine suggested action based on confidence score.
    
    Confidence levels:
    - > 0.9: auto_link (high confidence)
    - 0.7-0.9: suggest (medium confidence)
    - < 0.7: create_new (low confidence)
    """
    if confidence > 0.9:
        return "auto_link"
    elif confidence >= 0.7:
        return "suggest"
    else:
        return "create_new"
```


##### `link_imported_rental_income()`

Links an imported rental income transaction to a property.

**Implementation:**
```python
def link_imported_rental_income(
    self,
    transaction_id: int,
    property_id: UUID,
    user_id: int
) -> Transaction:
    """
    Link an imported rental income transaction to a property.
    
    Args:
        transaction_id: ID of the rental income transaction
        property_id: ID of the property to link to
        user_id: User ID for ownership validation
    
    Returns:
        Updated transaction with property_id set
    
    Raises:
        HTTPException: If transaction or property not found, or ownership invalid
    """
    # Validate transaction belongs to user
    transaction = self.db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    
    # Validate property belongs to user
    property = self.db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == user_id
    ).first()
    
    if not property:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Link transaction to property
    transaction.property_id = property_id
    self.db.commit()
    self.db.refresh(transaction)
    
    return transaction
```

#### Integration in `import_e1_data()`

The main import method includes property linking logic:

```python
def import_e1_data(self, data: E1FormData, user_id: int) -> Dict:
    """
    Import E1 form data and generate property linking suggestions.
    
    Returns:
        {
            "transactions": [...],
            "property_linking_required": bool,
            "property_suggestions": [...]
        }
    """
    # ... existing import logic ...
    
    # NEW: Property linking for rental income
    property_suggestions = []
    property_linking_required = False
    
    if data.kz_350 and data.kz_350 > 0:
        # Rental income detected
        property_linking_required = True
        
        if data.vermietung_details:
            property_suggestions = self._generate_property_suggestions(
                data.vermietung_details,
                user_id
            )
    
    return {
        "transactions": created_transactions,
        "user_profile_updated": True,
        "property_linking_required": property_linking_required,
        "property_suggestions": property_suggestions
    }
```


### 2. BescheidImportService Integration

**Location:** `backend/app/services/bescheid_import_service.py`

#### Key Methods

##### `_generate_property_linking_suggestion()`

Generates property linking suggestions from Bescheid rental income data.

**Implementation:**
```python
def _generate_property_linking_suggestion(
    self,
    vermietung_details: List[Dict],
    user_id: int
) -> List[Dict]:
    """
    Generate property linking suggestions from Bescheid data.
    
    Bescheid is the authoritative source (final tax assessment),
    so confidence in extracted data is higher than E1.
    
    Args:
        vermietung_details: Rental income details from Bescheid
        user_id: User ID for property matching
    
    Returns:
        List of property linking suggestions
    """
    suggestions = []
    
    for detail in vermietung_details:
        address = detail.get("address", "")
        if not address:
            continue
        
        # Use AddressMatcher
        matches = self.address_matcher.match_address(address, user_id)
        
        # Bescheid data is authoritative, so boost confidence slightly
        boosted_matches = []
        for match in matches:
            boosted_confidence = min(match.confidence + 0.05, 1.0)
            boosted_matches.append({
                "property_id": str(match.property.id),
                "property_address": match.property.address,
                "confidence": float(boosted_confidence),
                "suggested_action": self._determine_action(boosted_confidence),
                "matched_components": match.matched_components,
                "source": "bescheid"  # Mark as authoritative source
            })
        
        suggestion = {
            "extracted_address": address,
            "confirmed_rental_income": detail.get("amount", 0),  # "confirmed" from tax office
            "matches": boosted_matches
        }
        
        suggestions.append(suggestion)
    
    return suggestions
```

#### Integration in `import_bescheid_data()`

```python
def import_bescheid_data(self, data: BescheidData, user_id: int) -> Dict:
    """
    Import Bescheid data with property linking suggestions.
    
    Returns:
        {
            "transactions": [...],
            "property_linking_suggestions": [...]
        }
    """
    # ... existing import logic ...
    
    # Property linking for rental income
    property_suggestions = []
    
    if data.vermietung_details:
        property_suggestions = self._generate_property_linking_suggestion(
            data.vermietung_details,
            user_id
        )
    
    return {
        "transactions": created_transactions,
        "user_profile_updated": True,
        "property_linking_suggestions": property_suggestions
    }
```


### 3. AddressMatcher Service

**Location:** `backend/app/services/address_matcher.py`

#### Purpose

Performs fuzzy address matching to link imported rental income to existing properties.

#### Key Features

1. **Address Normalization**: Standardizes Austrian address formats
2. **Fuzzy Matching**: Uses Levenshtein distance for similarity
3. **Component Matching**: Matches street, city, postal code separately
4. **Confidence Scoring**: Returns 0.0-1.0 confidence scores

#### Implementation Details

##### Address Normalization

```python
def _normalize_address(self, address: str) -> str:
    """
    Normalize Austrian address for comparison.
    
    Transformations:
    - Convert to lowercase
    - Standardize abbreviations (Str. → strasse)
    - Remove extra whitespace
    - Handle Austrian-specific terms
    """
    normalized = address.lower()
    
    # Austrian address standardization
    replacements = {
        "str.": "strasse",
        "straße": "strasse",
        "gasse": "gasse",
        "platz": "platz",
        "weg": "weg",
        "allee": "allee",
        "hof": "hof",
        "ring": "ring"
    }
    
    for old, new in replacements.items():
        normalized = normalized.replace(old, new)
    
    # Remove extra whitespace
    normalized = " ".join(normalized.split())
    
    return normalized
```

##### Confidence Calculation

```python
def match_address(self, address_string: str, user_id: int) -> List[AddressMatch]:
    """
    Match address string to user's properties.
    
    Confidence calculation:
    - Overall similarity: 60% weight
    - Street similarity: 30% weight
    - Postal code exact match: 20% bonus
    
    Returns matches with confidence >= 0.7
    """
    properties = self.db.query(Property).filter(
        Property.user_id == user_id,
        Property.status == PropertyStatus.ACTIVE
    ).all()
    
    normalized_input = self._normalize_address(address_string)
    matches = []
    
    for property in properties:
        # Full address similarity
        full_address = f"{property.street}, {property.postal_code} {property.city}"
        normalized_property = self._normalize_address(full_address)
        overall_score = self._calculate_similarity(normalized_input, normalized_property)
        
        # Street-specific similarity
        street_score = self._calculate_similarity(
            self._normalize_address(address_string),
            self._normalize_address(property.street)
        )
        
        # Postal code exact match bonus
        postal_bonus = 0.2 if property.postal_code in address_string else 0
        
        # Final confidence
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
```


## API Integration

### E1 Import Endpoint

**Endpoint:** `POST /api/v1/documents/import-e1`

**Response with Property Suggestions:**
```json
{
  "success": true,
  "transactions": [
    {
      "id": 12345,
      "type": "income",
      "amount": 12000.00,
      "income_category": "rental_income",
      "description": "Vermietung und Verpachtung (KZ 350)",
      "transaction_date": "2025-12-31"
    }
  ],
  "property_linking_required": true,
  "property_suggestions": [
    {
      "extracted_address": "Hauptstraße 123, 1010 Wien",
      "rental_income": 12000.00,
      "matches": [
        {
          "property_id": "550e8400-e29b-41d4-a716-446655440000",
          "property_address": "Hauptstraße 123, 1010 Wien",
          "confidence": 0.95,
          "suggested_action": "auto_link",
          "matched_components": {
            "street": true,
            "postal_code": true,
            "city": true
          }
        }
      ]
    }
  ]
}
```

### Bescheid Import Endpoint

**Endpoint:** `POST /api/v1/documents/import-bescheid`

**Response with Property Suggestions:**
```json
{
  "success": true,
  "transactions": [
    {
      "id": 12346,
      "type": "income",
      "amount": 11800.00,
      "income_category": "rental_income",
      "description": "Vermietung (Bescheid bestätigt)",
      "transaction_date": "2025-12-31"
    }
  ],
  "property_linking_suggestions": [
    {
      "extracted_address": "Hauptstr. 123, 1010 Wien",
      "confirmed_rental_income": 11800.00,
      "matches": [
        {
          "property_id": "550e8400-e29b-41d4-a716-446655440000",
          "property_address": "Hauptstraße 123, 1010 Wien",
          "confidence": 0.97,
          "suggested_action": "auto_link",
          "matched_components": {
            "street": true,
            "postal_code": true,
            "city": true
          },
          "source": "bescheid"
        }
      ]
    }
  ]
}
```

### Property Linking Endpoint

**Endpoint:** `POST /api/v1/properties/{property_id}/link-transaction`

**Request:**
```json
{
  "transaction_id": 12345
}
```

**Response:**
```json
{
  "success": true,
  "transaction": {
    "id": 12345,
    "property_id": "550e8400-e29b-41d4-a716-446655440000",
    "type": "income",
    "amount": 12000.00,
    "income_category": "rental_income"
  }
}
```


## Frontend Integration

### E1FormImport Component

**Location:** `frontend/src/components/documents/E1FormImport.tsx`

#### Property Linking UI Flow

1. **Import Preview**: User uploads E1 form, sees extracted data
2. **Property Suggestions**: If rental income detected, show property suggestions
3. **User Confirmation**: User reviews and confirms/modifies suggestions
4. **Link Execution**: Transactions linked to properties on import confirmation

#### Implementation Example

```typescript
const E1FormImport: React.FC = () => {
  const [importResult, setImportResult] = useState<E1ImportResult | null>(null);
  const [propertyLinks, setPropertyLinks] = useState<Map<string, string>>(new Map());
  
  const handleImportPreview = async (file: File) => {
    // Upload and extract E1 data
    const result = await e1Service.importE1Form(file);
    setImportResult(result);
    
    // Pre-populate high-confidence matches
    if (result.property_suggestions) {
      const autoLinks = new Map<string, string>();
      result.property_suggestions.forEach(suggestion => {
        const highConfidenceMatch = suggestion.matches.find(
          m => m.suggested_action === 'auto_link'
        );
        if (highConfidenceMatch) {
          autoLinks.set(
            suggestion.extracted_address,
            highConfidenceMatch.property_id
          );
        }
      });
      setPropertyLinks(autoLinks);
    }
  };
  
  const handleConfirmImport = async () => {
    // Link transactions to properties
    for (const [address, propertyId] of propertyLinks.entries()) {
      const transaction = findTransactionByAddress(address);
      if (transaction && propertyId) {
        await propertyService.linkTransaction(propertyId, transaction.id);
      }
    }
    
    // Complete import
    toast.success('E1 imported and properties linked successfully');
  };
  
  return (
    <div>
      {/* File upload */}
      <FileUpload onUpload={handleImportPreview} />
      
      {/* Property linking suggestions */}
      {importResult?.property_linking_required && (
        <PropertyLinkingSuggestions
          suggestions={importResult.property_suggestions}
          selectedLinks={propertyLinks}
          onLinkChange={setPropertyLinks}
        />
      )}
      
      {/* Confirm button */}
      <Button onClick={handleConfirmImport}>
        Confirm Import
      </Button>
    </div>
  );
};
```

### PropertyLinkingSuggestions Component

**Location:** `frontend/src/components/properties/PropertyLinkingSuggestions.tsx`

```typescript
interface PropertyLinkingSuggestionsProps {
  suggestions: PropertySuggestion[];
  selectedLinks: Map<string, string>;
  onLinkChange: (links: Map<string, string>) => void;
}

const PropertyLinkingSuggestions: React.FC<PropertyLinkingSuggestionsProps> = ({
  suggestions,
  selectedLinks,
  onLinkChange
}) => {
  const handleLinkSelect = (address: string, propertyId: string) => {
    const newLinks = new Map(selectedLinks);
    newLinks.set(address, propertyId);
    onLinkChange(newLinks);
  };
  
  return (
    <div className="property-suggestions">
      <h3>Property Linking Suggestions</h3>
      
      {suggestions.map(suggestion => (
        <div key={suggestion.extracted_address} className="suggestion-card">
          <div className="extracted-info">
            <strong>Address from E1:</strong> {suggestion.extracted_address}
            <br />
            <strong>Rental Income:</strong> €{suggestion.rental_income.toFixed(2)}
          </div>
          
          <div className="matches">
            {suggestion.matches.length > 0 ? (
              suggestion.matches.map(match => (
                <div key={match.property_id} className="match-option">
                  <input
                    type="radio"
                    name={`link-${suggestion.extracted_address}`}
                    value={match.property_id}
                    checked={selectedLinks.get(suggestion.extracted_address) === match.property_id}
                    onChange={() => handleLinkSelect(suggestion.extracted_address, match.property_id)}
                  />
                  <label>
                    <strong>{match.property_address}</strong>
                    <ConfidenceBadge 
                      confidence={match.confidence}
                      action={match.suggested_action}
                    />
                    <MatchedComponents components={match.matched_components} />
                  </label>
                </div>
              ))
            ) : (
              <div className="no-matches">
                <p>No matching properties found</p>
                <Button onClick={() => createNewProperty(suggestion.extracted_address)}>
                  Create New Property
                </Button>
              </div>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};
```


## Data Flow Examples

### Example 1: High Confidence Match (Auto-Link)

**Scenario:** User imports E1 with rental income, address matches existing property with 95% confidence.

**Flow:**
```
1. User uploads E1 form
   ↓
2. E1FormImportService extracts:
   - KZ 350: €12,000
   - Address: "Hauptstraße 123, 1010 Wien"
   ↓
3. AddressMatcher finds:
   - Property ID: 550e8400-...
   - Address: "Hauptstraße 123, 1010 Wien"
   - Confidence: 0.95
   ↓
4. Frontend displays:
   - ✓ Auto-selected (high confidence)
   - User can override if needed
   ↓
5. User confirms import
   ↓
6. PropertyService.link_transaction():
   - Sets transaction.property_id = 550e8400-...
   - Validates ownership
   - Commits to database
   ↓
7. Success: Transaction linked to property
```

### Example 2: Medium Confidence Match (User Selection)

**Scenario:** User imports E1, address partially matches two properties.

**Flow:**
```
1. User uploads E1 form
   ↓
2. E1FormImportService extracts:
   - KZ 350: €8,000
   - Address: "Hauptstr. 45, Wien"
   ↓
3. AddressMatcher finds:
   - Property A: "Hauptstraße 45, 1020 Wien" (confidence: 0.85)
   - Property B: "Hauptstraße 45, 1030 Wien" (confidence: 0.82)
   ↓
4. Frontend displays:
   - Both options shown
   - User must select one
   ↓
5. User selects Property A
   ↓
6. User confirms import
   ↓
7. PropertyService.link_transaction():
   - Links to selected property
   ↓
8. Success: Transaction linked to Property A
```

### Example 3: No Match (Create New Property)

**Scenario:** User imports E1 with rental income from new property not yet registered.

**Flow:**
```
1. User uploads E1 form
   ↓
2. E1FormImportService extracts:
   - KZ 350: €15,000
   - Address: "Neubaugasse 78, 1070 Wien"
   ↓
3. AddressMatcher finds:
   - No matches (confidence < 0.7)
   ↓
4. Frontend displays:
   - "No matching properties found"
   - "Create New Property" button
   ↓
5. User clicks "Create New Property"
   ↓
6. PropertyForm opens with pre-filled address
   ↓
7. User completes property details:
   - Purchase date, price, etc.
   ↓
8. PropertyService.create_property():
   - Creates new property
   - Returns property_id
   ↓
9. PropertyService.link_transaction():
   - Links transaction to new property
   ↓
10. Success: New property created and linked
```


## Testing

### Unit Tests

#### Test AddressMatcher

**Location:** `backend/tests/test_address_matcher.py`

```python
def test_address_matcher_exact_match(db, test_user):
    """Test exact address match returns high confidence"""
    # Create property
    property = create_test_property(
        user_id=test_user.id,
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010"
    )
    
    # Match address
    matcher = AddressMatcher(db)
    matches = matcher.match_address("Hauptstraße 123, 1010 Wien", test_user.id)
    
    # Assert
    assert len(matches) == 1
    assert matches[0].property.id == property.id
    assert matches[0].confidence > 0.9
    assert matches[0].matched_components["street"] is True
    assert matches[0].matched_components["postal_code"] is True


def test_address_matcher_fuzzy_match(db, test_user):
    """Test fuzzy matching with abbreviations"""
    property = create_test_property(
        user_id=test_user.id,
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010"
    )
    
    matcher = AddressMatcher(db)
    
    # Test with abbreviation
    matches = matcher.match_address("Hauptstr. 123, 1010 Wien", test_user.id)
    
    assert len(matches) == 1
    assert matches[0].confidence > 0.85  # High but not perfect


def test_address_matcher_no_match(db, test_user):
    """Test no match returns empty list"""
    create_test_property(
        user_id=test_user.id,
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010"
    )
    
    matcher = AddressMatcher(db)
    matches = matcher.match_address("Completely Different Street 999, 9999 City", test_user.id)
    
    assert len(matches) == 0
```

#### Test E1 Property Linking

**Location:** `backend/tests/test_e1_property_linking.py`

```python
def test_e1_import_generates_property_suggestions(db, test_user):
    """Test E1 import with rental income generates property suggestions"""
    # Create property
    property = create_test_property(
        user_id=test_user.id,
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010"
    )
    
    # Import E1 data
    e1_service = E1FormImportService(db)
    result = e1_service.import_e1_data(
        data=E1FormData(
            kz_350=Decimal("12000.00"),
            vermietung_details=[
                {"address": "Hauptstraße 123, 1010 Wien", "amount": 12000.00}
            ]
        ),
        user_id=test_user.id
    )
    
    # Assert
    assert result["property_linking_required"] is True
    assert len(result["property_suggestions"]) == 1
    
    suggestion = result["property_suggestions"][0]
    assert suggestion["extracted_address"] == "Hauptstraße 123, 1010 Wien"
    assert len(suggestion["matches"]) == 1
    assert suggestion["matches"][0]["property_id"] == str(property.id)
    assert suggestion["matches"][0]["suggested_action"] == "auto_link"


def test_link_imported_rental_income(db, test_user):
    """Test linking imported transaction to property"""
    # Create property and transaction
    property = create_test_property(user_id=test_user.id)
    transaction = create_test_transaction(
        user_id=test_user.id,
        type=TransactionType.INCOME,
        income_category=IncomeCategory.RENTAL_INCOME,
        amount=Decimal("12000.00")
    )
    
    # Link transaction
    e1_service = E1FormImportService(db)
    result = e1_service.link_imported_rental_income(
        transaction_id=transaction.id,
        property_id=property.id,
        user_id=test_user.id
    )
    
    # Assert
    assert result.property_id == property.id
    
    # Verify in database
    db.refresh(transaction)
    assert transaction.property_id == property.id
```


### Integration Tests

**Location:** `backend/tests/test_property_import_integration.py`

```python
def test_e2e_e1_import_to_property_link(db, test_user):
    """End-to-end test: E1 import → property linking → transaction verification"""
    # 1. Create existing property
    property = create_test_property(
        user_id=test_user.id,
        street="Hauptstraße 123",
        city="Wien",
        postal_code="1010",
        purchase_date=date(2020, 1, 1),
        purchase_price=Decimal("350000.00")
    )
    
    # 2. Import E1 with rental income
    e1_service = E1FormImportService(db)
    import_result = e1_service.import_e1_data(
        data=E1FormData(
            kz_350=Decimal("12000.00"),
            vermietung_details=[
                {"address": "Hauptstraße 123, 1010 Wien", "amount": 12000.00}
            ]
        ),
        user_id=test_user.id
    )
    
    # 3. Verify property suggestions generated
    assert import_result["property_linking_required"] is True
    assert len(import_result["property_suggestions"]) == 1
    
    suggestion = import_result["property_suggestions"][0]
    assert suggestion["matches"][0]["suggested_action"] == "auto_link"
    
    # 4. Link transaction to property
    transaction_id = import_result["transactions"][0]["id"]
    e1_service.link_imported_rental_income(
        transaction_id=transaction_id,
        property_id=property.id,
        user_id=test_user.id
    )
    
    # 5. Verify transaction linked
    transaction = db.query(Transaction).get(transaction_id)
    assert transaction.property_id == property.id
    assert transaction.income_category == IncomeCategory.RENTAL_INCOME
    
    # 6. Verify property metrics updated
    property_service = PropertyService(db)
    metrics = property_service.calculate_property_metrics(property.id)
    assert metrics.rental_income == Decimal("12000.00")


def test_bescheid_import_with_address_matching(db, test_user):
    """Test Bescheid import with automatic address matching"""
    # Create property
    property = create_test_property(
        user_id=test_user.id,
        street="Mariahilfer Straße 45",
        city="Wien",
        postal_code="1060"
    )
    
    # Import Bescheid
    bescheid_service = BescheidImportService(db)
    result = bescheid_service.import_bescheid_data(
        data=BescheidData(
            vermietung_details=[
                {
                    "address": "Mariahilfer Str. 45, 1060 Wien",
                    "amount": 15000.00
                }
            ]
        ),
        user_id=test_user.id
    )
    
    # Verify suggestions
    assert len(result["property_linking_suggestions"]) == 1
    suggestion = result["property_linking_suggestions"][0]
    
    # Bescheid has confidence boost
    assert suggestion["matches"][0]["confidence"] > 0.9
    assert suggestion["matches"][0]["source"] == "bescheid"
```

## Error Handling

### Common Error Scenarios

#### 1. Property Not Found

```python
# Scenario: User tries to link transaction to non-existent property
try:
    e1_service.link_imported_rental_income(
        transaction_id=12345,
        property_id=UUID("00000000-0000-0000-0000-000000000000"),
        user_id=test_user.id
    )
except HTTPException as e:
    assert e.status_code == 404
    assert "Property not found" in e.detail
```

#### 2. Ownership Validation Failure

```python
# Scenario: User tries to link transaction to another user's property
other_user_property = create_test_property(user_id=other_user.id)

try:
    e1_service.link_imported_rental_income(
        transaction_id=12345,
        property_id=other_user_property.id,
        user_id=test_user.id  # Different user
    )
except HTTPException as e:
    assert e.status_code == 404  # Property not found (for security)
```

#### 3. Address Matching Timeout

```python
# Scenario: Address matching takes too long
from app.core.exceptions import TimeoutError

try:
    matcher = AddressMatcher(db)
    matches = matcher.match_address(very_long_address_string, user_id)
except TimeoutError:
    # Fallback: suggest creating new property
    return {"matches": [], "suggested_action": "create_new"}
```


## Performance Considerations

### Optimization Strategies

#### 1. Batch Address Matching

When importing multiple rental income entries, batch the address matching:

```python
def _generate_property_suggestions_batch(
    self,
    vermietung_details: List[Dict],
    user_id: int
) -> List[Dict]:
    """Optimized batch address matching"""
    # Fetch all user properties once
    properties = self.db.query(Property).filter(
        Property.user_id == user_id,
        Property.status == PropertyStatus.ACTIVE
    ).all()
    
    # Pre-normalize all property addresses
    normalized_properties = [
        (prop, self.address_matcher._normalize_address(prop.address))
        for prop in properties
    ]
    
    suggestions = []
    for detail in vermietung_details:
        address = detail.get("address", "")
        if not address:
            continue
        
        # Match against pre-loaded properties
        matches = self._match_against_properties(
            address,
            normalized_properties
        )
        
        suggestions.append({
            "extracted_address": address,
            "matches": matches
        })
    
    return suggestions
```

#### 2. Cache Address Normalization

```python
from functools import lru_cache

class AddressMatcher:
    @lru_cache(maxsize=1000)
    def _normalize_address(self, address: str) -> str:
        """Cached address normalization"""
        # ... normalization logic ...
        return normalized
```

#### 3. Index Optimization

Ensure database indexes exist for common queries:

```sql
-- Index for property lookups by user
CREATE INDEX idx_properties_user_status ON properties(user_id, status);

-- Index for transaction-property links
CREATE INDEX idx_transactions_property_id ON transactions(property_id);

-- Index for rental income transactions
CREATE INDEX idx_transactions_income_category ON transactions(income_category) 
WHERE income_category = 'rental_income';
```

### Performance Benchmarks

**Target Performance:**
- Address matching: < 100ms per property
- E1 import with 5 properties: < 2 seconds
- Batch linking 10 transactions: < 500ms

**Monitoring:**
```python
import time
import logging

logger = logging.getLogger(__name__)

def match_address(self, address_string: str, user_id: int) -> List[AddressMatch]:
    start_time = time.time()
    
    matches = # ... matching logic ...
    
    elapsed = time.time() - start_time
    logger.info(f"Address matching took {elapsed:.3f}s for user {user_id}")
    
    if elapsed > 0.5:
        logger.warning(f"Slow address matching: {elapsed:.3f}s")
    
    return matches
```


## Security Considerations

### 1. Ownership Validation

**Always validate** that both property and transaction belong to the requesting user:

```python
def link_imported_rental_income(
    self,
    transaction_id: int,
    property_id: UUID,
    user_id: int
) -> Transaction:
    """Link with strict ownership validation"""
    
    # Validate transaction ownership
    transaction = self.db.query(Transaction).filter(
        Transaction.id == transaction_id,
        Transaction.user_id == user_id  # CRITICAL
    ).first()
    
    if not transaction:
        raise HTTPException(
            status_code=404,
            detail="Transaction not found"  # Don't reveal if exists
        )
    
    # Validate property ownership
    property = self.db.query(Property).filter(
        Property.id == property_id,
        Property.user_id == user_id  # CRITICAL
    ).first()
    
    if not property:
        raise HTTPException(
            status_code=404,
            detail="Property not found"  # Don't reveal if exists
        )
    
    # Link only after validation
    transaction.property_id = property_id
    self.db.commit()
    
    return transaction
```

### 2. Data Encryption

Property addresses are encrypted at rest:

```python
from app.core.encryption import encrypt_field, decrypt_field

class Property(Base):
    _address = Column("address", String(1000), nullable=False)
    
    @hybrid_property
    def address(self):
        """Decrypt address on read"""
        return decrypt_field(self._address)
    
    @address.setter
    def address(self, value):
        """Encrypt address on write"""
        self._address = encrypt_field(value)
```

### 3. Audit Logging

Log all property linking operations:

```python
def link_imported_rental_income(self, transaction_id: int, property_id: UUID, user_id: int):
    # ... linking logic ...
    
    # Audit log
    audit_log = AuditLog(
        user_id=user_id,
        operation="property_link",
        entity_type="transaction",
        entity_id=transaction_id,
        details={
            "property_id": str(property_id),
            "source": "e1_import"
        },
        timestamp=datetime.utcnow()
    )
    self.db.add(audit_log)
    self.db.commit()
```

### 4. Rate Limiting

Prevent abuse of address matching endpoint:

```python
from fastapi_limiter.depends import RateLimiter

@router.post("/import-e1", dependencies=[Depends(RateLimiter(times=10, seconds=60))])
async def import_e1_form(file: UploadFile, db: Session = Depends(get_db)):
    """Rate limited: 10 imports per minute"""
    # ... import logic ...
```


## Troubleshooting

### Issue 1: Address Matching Returns No Results

**Symptoms:** E1 import doesn't suggest any property matches despite having properties.

**Possible Causes:**
1. Address format mismatch (abbreviations, special characters)
2. Properties are archived/sold (only active properties matched)
3. Confidence threshold too high

**Debug Steps:**
```python
# 1. Check user's active properties
properties = db.query(Property).filter(
    Property.user_id == user_id,
    Property.status == PropertyStatus.ACTIVE
).all()
print(f"Active properties: {len(properties)}")
for prop in properties:
    print(f"  - {prop.address}")

# 2. Test address normalization
matcher = AddressMatcher(db)
normalized = matcher._normalize_address("Hauptstr. 123, 1010 Wien")
print(f"Normalized: {normalized}")

# 3. Test similarity calculation
similarity = matcher._calculate_similarity(
    "hauptstrasse 123 1010 wien",
    "hauptstrasse 123 1010 wien"
)
print(f"Similarity: {similarity}")  # Should be 1.0

# 4. Lower confidence threshold temporarily
matches = matcher.match_address(address, user_id)
for match in matches:
    print(f"Property: {match.property.address}, Confidence: {match.confidence}")
```

**Solutions:**
- Ensure properties are marked as `active`
- Add more address normalization rules for Austrian formats
- Consider lowering confidence threshold from 0.7 to 0.6 for testing

### Issue 2: High Confidence Match for Wrong Property

**Symptoms:** System suggests linking to incorrect property with high confidence.

**Possible Causes:**
1. Multiple properties with similar addresses
2. Postal code not included in extracted address
3. Insufficient component-wise matching

**Debug Steps:**
```python
# Check all matches with details
matches = matcher.match_address(address, user_id)
for match in matches:
    print(f"\nProperty: {match.property.address}")
    print(f"Confidence: {match.confidence}")
    print(f"Components: {match.matched_components}")
    print(f"Street match: {match.matched_components['street']}")
    print(f"Postal match: {match.matched_components['postal_code']}")
    print(f"City match: {match.matched_components['city']}")
```

**Solutions:**
- Increase weight of postal code matching
- Require all components to match for confidence > 0.9
- Add disambiguation UI for multiple high-confidence matches

### Issue 3: Transaction Not Linking After Import

**Symptoms:** User confirms import but transaction.property_id remains NULL.

**Possible Causes:**
1. Frontend not calling link endpoint
2. Ownership validation failing silently
3. Database transaction rollback

**Debug Steps:**
```python
# 1. Check transaction exists
transaction = db.query(Transaction).get(transaction_id)
print(f"Transaction: {transaction}")
print(f"User ID: {transaction.user_id}")
print(f"Property ID: {transaction.property_id}")

# 2. Check property exists
property = db.query(Property).get(property_id)
print(f"Property: {property}")
print(f"User ID: {property.user_id}")

# 3. Test linking directly
try:
    e1_service.link_imported_rental_income(
        transaction_id=transaction_id,
        property_id=property_id,
        user_id=user_id
    )
    print("Link successful")
except Exception as e:
    print(f"Link failed: {e}")

# 4. Check database logs
# Look for ROLLBACK statements
```

**Solutions:**
- Add frontend error handling and display
- Ensure database commit is called
- Add logging to link_imported_rental_income method


## Best Practices

### 1. Always Use Confidence Thresholds

Don't auto-link below 0.9 confidence:

```python
# GOOD
if confidence > 0.9:
    suggested_action = "auto_link"
elif confidence >= 0.7:
    suggested_action = "suggest"
else:
    suggested_action = "create_new"

# BAD - auto-linking with low confidence
if confidence > 0.5:  # Too low!
    suggested_action = "auto_link"
```

### 2. Provide User Override Options

Always allow users to override suggestions:

```typescript
// GOOD - User can override
<PropertyLinkingSuggestions
  suggestions={suggestions}
  selectedLinks={userSelectedLinks}
  onLinkChange={handleUserOverride}
  allowOverride={true}
/>

// BAD - Auto-linking without user confirmation
autoLinkTransactions(suggestions);
```

### 3. Handle Multiple Matches Gracefully

```python
# GOOD - Return all matches, let user decide
matches = matcher.match_address(address, user_id)
return {
    "matches": matches,
    "requires_user_selection": len(matches) > 1
}

# BAD - Arbitrarily pick first match
matches = matcher.match_address(address, user_id)
return matches[0] if matches else None
```

### 4. Log Integration Events

```python
import logging

logger = logging.getLogger(__name__)

def import_e1_data(self, data: E1FormData, user_id: int):
    logger.info(f"E1 import started for user {user_id}")
    
    if data.kz_350:
        logger.info(f"Rental income detected: €{data.kz_350}")
    
    suggestions = self._generate_property_suggestions(...)
    logger.info(f"Generated {len(suggestions)} property suggestions")
    
    for suggestion in suggestions:
        logger.debug(f"Suggestion: {suggestion['extracted_address']}, "
                    f"matches: {len(suggestion['matches'])}")
    
    return result
```

### 5. Validate Before Committing

```python
# GOOD - Validate then commit
def link_imported_rental_income(self, transaction_id, property_id, user_id):
    # Validate ownership
    transaction = self._validate_transaction_ownership(transaction_id, user_id)
    property = self._validate_property_ownership(property_id, user_id)
    
    # Validate business rules
    if transaction.type != TransactionType.INCOME:
        raise ValueError("Only income transactions can be linked to properties")
    
    # Link
    transaction.property_id = property_id
    self.db.commit()
    
    return transaction

# BAD - Commit without validation
def link_imported_rental_income(self, transaction_id, property_id, user_id):
    transaction = self.db.query(Transaction).get(transaction_id)
    transaction.property_id = property_id
    self.db.commit()  # No validation!
```


## Future Enhancements

### 1. Machine Learning Address Matching

Replace rule-based matching with ML model:

```python
class MLAddressMatcher:
    """ML-based address matcher using trained model"""
    
    def __init__(self, db: Session):
        self.db = db
        self.model = load_model("address_matcher_v1.pkl")
    
    def match_address(self, address_string: str, user_id: int) -> List[AddressMatch]:
        """Use ML model for address matching"""
        properties = self._get_user_properties(user_id)
        
        # Extract features
        features = self._extract_features(address_string, properties)
        
        # Predict matches
        predictions = self.model.predict_proba(features)
        
        # Return matches with ML confidence scores
        matches = []
        for i, property in enumerate(properties):
            confidence = predictions[i][1]  # Probability of match
            if confidence >= 0.7:
                matches.append(AddressMatch(
                    property=property,
                    confidence=confidence,
                    source="ml_model"
                ))
        
        return sorted(matches, key=lambda m: m.confidence, reverse=True)
```

### 2. Historical Import Suggestions

Suggest historical depreciation backfill after property linking:

```python
def link_imported_rental_income(self, transaction_id, property_id, user_id):
    # ... existing linking logic ...
    
    # Check if historical backfill needed
    property = self.db.query(Property).get(property_id)
    if property.purchase_date.year < datetime.now().year:
        # Suggest backfill
        return {
            "transaction": transaction,
            "backfill_suggestion": {
                "property_id": str(property_id),
                "years_to_backfill": datetime.now().year - property.purchase_date.year,
                "estimated_depreciation": self._estimate_historical_depreciation(property)
            }
        }
    
    return {"transaction": transaction}
```

### 3. Bulk Import with Auto-Linking

Support importing multiple years of E1 forms with automatic property linking:

```python
def bulk_import_e1_forms(
    self,
    files: List[UploadFile],
    user_id: int,
    auto_link: bool = True
) -> BulkImportResult:
    """Import multiple E1 forms with automatic property linking"""
    results = []
    
    for file in files:
        # Import E1
        import_result = self.import_e1_data(extract_e1_data(file), user_id)
        
        # Auto-link high confidence matches
        if auto_link:
            for suggestion in import_result["property_suggestions"]:
                high_confidence_match = next(
                    (m for m in suggestion["matches"] if m["confidence"] > 0.9),
                    None
                )
                if high_confidence_match:
                    self.link_imported_rental_income(
                        transaction_id=import_result["transactions"][0]["id"],
                        property_id=UUID(high_confidence_match["property_id"]),
                        user_id=user_id
                    )
        
        results.append(import_result)
    
    return BulkImportResult(
        total_files=len(files),
        successful_imports=len(results),
        total_transactions=sum(len(r["transactions"]) for r in results),
        auto_linked=sum(1 for r in results if r.get("auto_linked"))
    )
```

### 4. Address Geocoding

Add geocoding for better address matching:

```python
from geopy.geocoders import Nominatim

class GeocodingAddressMatcher(AddressMatcher):
    """Address matcher with geocoding support"""
    
    def __init__(self, db: Session):
        super().__init__(db)
        self.geocoder = Nominatim(user_agent="taxja")
    
    def match_address(self, address_string: str, user_id: int) -> List[AddressMatch]:
        # Try geocoding
        try:
            location = self.geocoder.geocode(address_string)
            if location:
                # Match by coordinates
                return self._match_by_coordinates(
                    location.latitude,
                    location.longitude,
                    user_id
                )
        except Exception:
            pass
        
        # Fallback to fuzzy matching
        return super().match_address(address_string, user_id)
```


## References

### Related Documentation

- **Service Layer Guide:** `docs/developer/service-layer-guide.md`
- **Database Schema:** `docs/developer/database-schema.md`
- **Property Management Design:** `.kiro/specs/property-asset-management/design.md`
- **Property Management Requirements:** `.kiro/specs/property-asset-management/requirements.md`

### Source Code

**Backend Services:**
- `backend/app/services/e1_form_import_service.py` - E1 import with property linking
- `backend/app/services/bescheid_import_service.py` - Bescheid import with property linking
- `backend/app/services/address_matcher.py` - Fuzzy address matching
- `backend/app/services/property_service.py` - Property management

**Frontend Components:**
- `frontend/src/components/documents/E1FormImport.tsx` - E1 import UI
- `frontend/src/components/documents/BescheidImport.tsx` - Bescheid import UI
- `frontend/src/components/properties/PropertyLinkingSuggestions.tsx` - Property linking UI

**API Endpoints:**
- `backend/app/api/v1/endpoints/documents.py` - Document import endpoints
- `backend/app/api/v1/endpoints/properties.py` - Property management endpoints

### Testing

**Test Files:**
- `backend/tests/test_address_matcher.py` - Address matching unit tests
- `backend/tests/test_e1_property_linking.py` - E1 integration tests
- `backend/tests/test_property_import_integration.py` - End-to-end integration tests

### Austrian Tax Law

- **§ 28 EStG:** Rental Income (Einkünfte aus Vermietung und Verpachtung)
- **KZ 350:** Tax form field code for rental income
- **E1 Form:** Annual tax declaration (Einkommensteuererklärung)
- **Bescheid:** Tax assessment document (Einkommensteuerbescheid)

### External Libraries

- **python-Levenshtein:** Fast string similarity calculations
- **fuzzywuzzy:** Alternative fuzzy string matching library
- **geopy:** Geocoding library (optional, for future enhancement)

---

## Changelog

**Version 1.0** (2026-03-07)
- Initial documentation
- E1FormImportService integration
- BescheidImportService integration
- AddressMatcher implementation
- Frontend integration guide
- Testing strategies
- Performance optimization
- Security considerations

---

**Document Version:** 1.0  
**Last Updated:** 2026-03-07  
**Maintained By:** Taxja Development Team  
**Status:** Complete

