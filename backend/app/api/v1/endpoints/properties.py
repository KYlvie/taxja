"""Property management API endpoints"""
from typing import Optional, List, Dict, Any
from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status, Body
from sqlalchemy.orm import Session

from app.db.base import get_db
from app.models.user import User
from app.core.security import get_current_user
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    PropertyListResponse,
    PropertyDetailResponse,
    PropertyMetrics,
    HistoricalDepreciationPreview,
    BackfillDepreciationResult,
    AnnualDepreciationResponse
)
from app.services.property_service import PropertyService
from app.services.historical_depreciation_service import HistoricalDepreciationService
from app.services.annual_depreciation_service import AnnualDepreciationService

router = APIRouter()


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    property_data: PropertyCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Create a new property.
    
    **Required fields:**
    - **street**: Street address
    - **city**: City name
    - **postal_code**: Postal code
    - **purchase_date**: Property purchase date (cannot be in future)
    - **purchase_price**: Total purchase price (must be > 0 and <= €100,000,000)
    
    **Optional fields (with auto-calculation):**
    - **building_value**: Depreciable building value (default: 80% of purchase_price)
    - **depreciation_rate**: Annual depreciation rate (default: 2.0% for buildings >= 1915, 1.5% for pre-1915)
    - **construction_year**: Year of construction (affects depreciation rate)
    - **property_type**: rental (default), owner_occupied, or mixed_use
    - **rental_percentage**: Percentage used for rental (default: 100 for rental properties)
    - **grunderwerbsteuer**: Property transfer tax paid
    - **notary_fees**: Notary fees paid
    - **registry_fees**: Land registry fees
    
    **Auto-calculations:**
    - building_value = 80% of purchase_price if not provided
    - depreciation_rate based on construction_year (1.5% pre-1915, 2.0% otherwise)
    - land_value = purchase_price - building_value
    - address = "{street}, {postal_code} {city}"
    
    **Example Request:**
    ```json
    {
      "street": "Hauptstraße 123",
      "city": "Wien",
      "postal_code": "1010",
      "purchase_date": "2020-06-15",
      "purchase_price": 350000.00,
      "building_value": 280000.00,
      "construction_year": 1985,
      "property_type": "rental",
      "rental_percentage": 100.0
    }
    ```
    
    **Example Response (201 Created):**
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
      "sale_date": null,
      "created_at": "2026-03-07T10:30:00Z",
      "updated_at": "2026-03-07T10:30:00Z"
    }
    ```
    """
    service = PropertyService(db)

    try:
        property_obj = service.create_property(current_user.id, property_data)

        # Auto-create recurring rental income if monthly_rent provided
        if property_data.monthly_rent and property_data.property_type in (
            "rental", PropertyType.RENTAL, "mixed_use", PropertyType.MIXED_USE
        ):
            try:
                from app.services.recurring_transaction_service import RecurringTransactionService
                recurring_service = RecurringTransactionService(db)
                start = property_data.rent_start_date or property_data.purchase_date
                recurring_service.create_rental_income_recurring(
                    user_id=current_user.id,
                    property_id=str(property_obj.id),
                    monthly_rent=property_data.monthly_rent,
                    start_date=start,
                    day_of_month=1,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(
                    f"Auto-create recurring rental income failed: {e}"
                )

        return property_obj
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("", response_model=PropertyListResponse)
def list_properties(
    include_archived: bool = Query(
        False,
        description="Include archived/sold properties in the list"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    List all properties owned by the current user.
    
    **Query Parameters:**
    - **include_archived**: If true, includes archived/sold properties (default: false)
    
    **Returns:**
    - List of properties with basic information
    - Total count of properties
    
    **Example Request:**
    ```
    GET /api/v1/properties?include_archived=false
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "total": 2,
      "include_archived": false,
      "properties": [
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "address": "Hauptstraße 123, 1010 Wien",
          "purchase_date": "2020-06-15",
          "purchase_price": 350000.00,
          "building_value": 280000.00,
          "depreciation_rate": 0.02,
          "status": "active"
        },
        {
          "id": "660e8400-e29b-41d4-a716-446655440001",
          "address": "Mariahilfer Straße 45, 1060 Wien",
          "purchase_date": "2018-03-20",
          "purchase_price": 420000.00,
          "building_value": 336000.00,
          "depreciation_rate": 0.02,
          "status": "active"
        }
      ]
    }
    ```
    """
    service = PropertyService(db)
    properties = service.list_properties(current_user.id, include_archived)
    
    return PropertyListResponse(
        total=len(properties),
        properties=properties,
        include_archived=include_archived
    )


@router.get("/{property_id}", response_model=PropertyDetailResponse)
def get_property(
    property_id: UUID,
    include_metrics: bool = Query(
        True,
        description="Include financial metrics in response"
    ),
    year: Optional[int] = Query(
        None,
        description="Year for metrics calculation (default: current year)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get detailed information about a specific property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **include_metrics**: Include financial metrics (default: true)
    - **year**: Year for metrics calculation (default: current year)
    
    **Returns:**
    - Complete property details
    - Financial metrics (if include_metrics=true):
      - Accumulated depreciation
      - Remaining depreciable value
      - Annual depreciation
      - Total rental income
      - Total expenses
      - Net rental income
      - Years remaining until fully depreciated
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000?include_metrics=true&year=2026
    ```
    
    **Example Response (200 OK):**
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
      "sale_date": null,
      "metrics": {
        "accumulated_depreciation": 33600.00,
        "remaining_depreciable_value": 246400.00,
        "annual_depreciation": 5600.00,
        "total_rental_income": 18000.00,
        "total_expenses": 8200.00,
        "net_rental_income": 9800.00,
        "years_remaining": 44
      }
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        property = service.get_property(property_id, current_user.id)
        
        # Calculate metrics if requested
        metrics = None
        if include_metrics:
            metrics = service.calculate_property_metrics(
                property_id,
                current_user.id,
                year
            )
        
        # Use model_validate to properly access hybrid properties
        response = PropertyDetailResponse.model_validate(property)
        response.metrics = metrics
        return response
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: UUID,
    property_data: PropertyUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update an existing property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property to update
    
    **Updatable fields:**
    - property_type, rental_percentage
    - street, city, postal_code
    - building_value, construction_year, depreciation_rate
    - grunderwerbsteuer, notary_fees, registry_fees
    - status, sale_date
    
    **Immutable fields (cannot be updated):**
    - purchase_date
    - purchase_price
    
    **Note:** Only provided fields will be updated. Omitted fields remain unchanged.
    
    **Example Request:**
    ```json
    {
      "depreciation_rate": 0.025,
      "construction_year": 1980
    }
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "user_id": 123,
      "property_type": "rental",
      "address": "Hauptstraße 123, 1010 Wien",
      "purchase_date": "2020-06-15",
      "purchase_price": 350000.00,
      "building_value": 280000.00,
      "construction_year": 1980,
      "depreciation_rate": 0.025,
      "status": "active",
      "updated_at": "2026-03-07T11:45:00Z"
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        property = service.update_property(property_id, current_user.id, property_data)
        return property
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_property(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Delete a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property to delete
    
    **Restrictions:**
    - Property can only be deleted if it has NO linked transactions
    - If transactions exist, you must either:
      1. Unlink all transactions first, or
      2. Archive the property instead (use POST /properties/{property_id}/archive)
    
    **Returns:**
    - 204 No Content on success
    - 400 Bad Request if property has linked transactions
    - 404 Not Found if property doesn't exist
    - 403 Forbidden if property doesn't belong to user
    """
    service = PropertyService(db)
    
    try:
        service.delete_property(property_id, current_user.id)
        return None
    except ValueError as e:
        # Check if it's a "has transactions" error
        if "linked transaction" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e)
            )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{property_id}/archive", response_model=PropertyResponse)
def archive_property(
    property_id: UUID,
    sale_date: date = Query(..., description="Date the property was sold"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Archive a property (mark as sold).
    
    **Path Parameters:**
    - **property_id**: UUID of the property to archive
    
    **Query Parameters:**
    - **sale_date**: Date the property was sold (required)
    
    **Effects:**
    - Property status changed to 'sold'
    - Property will not appear in default property lists (unless include_archived=true)
    - All historical transactions and depreciation records are preserved
    - Depreciation will stop being calculated after the sale date
    
    **Validation:**
    - sale_date must be >= purchase_date
    
    **Example Request:**
    ```
    POST /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/archive?sale_date=2025-12-31
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "address": "Hauptstraße 123, 1010 Wien",
      "purchase_date": "2020-06-15",
      "purchase_price": 350000.00,
      "status": "sold",
      "sale_date": "2025-12-31",
      "updated_at": "2026-03-07T12:00:00Z"
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        property = service.archive_property(property_id, current_user.id, sale_date)
        return property
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/metrics", response_model=PropertyMetrics)
def get_property_metrics(
    property_id: UUID,
    year: Optional[int] = Query(
        None,
        description="Year for metrics calculation (default: current year)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get property financial metrics with tax validation warnings.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **year**: Year for metrics calculation (default: current year)
    
    **Returns:**
    - Financial metrics including:
      - Accumulated depreciation
      - Remaining depreciable value
      - Annual depreciation
      - Total rental income
      - Total expenses
      - Net rental income
      - Years remaining until fully depreciated
      - Tax validation warnings (e.g., no rental income)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/metrics?year=2026
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "accumulated_depreciation": 33600.00,
      "remaining_depreciable_value": 246400.00,
      "annual_depreciation": 5600.00,
      "total_rental_income": 0.00,
      "total_expenses": 8200.00,
      "net_rental_income": -8200.00,
      "years_remaining": 44,
      "warnings": [
        {
          "property_id": "550e8400-e29b-41d4-a716-446655440000",
          "property_address": "Hauptstraße 123, 1010 Wien",
          "year": 2026,
          "level": "warning",
          "type": "NO_RENTAL_INCOME",
          "months_vacant": 8,
          "message_de": "⚠️ Längere Leerstandsphase...",
          "message_en": "⚠️ Extended vacancy...",
          "message_zh": "⚠️ 长期空置..."
        }
      ]
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        metrics = service.calculate_property_metrics(
            property_id,
            current_user.id,
            year
        )
        return metrics
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{property_id}/transactions")
def get_property_transactions(
    property_id: UUID,
    year: Optional[int] = Query(
        None,
        description="Filter transactions by year (default: all years)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all transactions linked to a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **year**: Filter transactions by year (optional)
    
    **Returns:**
    - List of transactions linked to the property
    - Includes both income (rental income) and expenses
    - Ordered by transaction date (newest first)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/transactions?year=2026
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "year": 2026,
      "total": 15,
      "transactions": [
        {
          "id": 1001,
          "type": "income",
          "amount": 1500.00,
          "transaction_date": "2026-03-01",
          "description": "Miete März 2026",
          "income_category": "rental_income",
          "property_id": "550e8400-e29b-41d4-a716-446655440000"
        },
        {
          "id": 1002,
          "type": "expense",
          "amount": 350.00,
          "transaction_date": "2026-02-15",
          "description": "Hausverwaltung",
          "expense_category": "property_management_fees",
          "property_id": "550e8400-e29b-41d4-a716-446655440000"
        }
      ]
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        transactions = service.get_property_transactions(
            property_id,
            current_user.id,
            year
        )
        return {
            "property_id": str(property_id),
            "year": year,
            "total": len(transactions),
            "transactions": transactions
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{property_id}/link-transaction")
def link_transaction(
    property_id: UUID,
    transaction_id: int = Query(..., description="ID of the transaction to link"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Link a transaction to a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **transaction_id**: ID of the transaction to link (required)
    
    **Use cases:**
    - Link rental income to a property
    - Link property expenses (maintenance, insurance, etc.) to a property
    - Link depreciation transactions to a property
    
    **Validation:**
    - Both property and transaction must belong to the current user
    - Transaction must exist
    - Property must exist
    
    **Returns:**
    - Updated transaction with property_id set
    
    **Example Request:**
    ```
    POST /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/link-transaction?transaction_id=1001
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "message": "Transaction linked successfully",
      "transaction_id": 1001,
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "transaction": {
        "id": 1001,
        "type": "income",
        "amount": 1500.00,
        "transaction_date": "2026-03-01",
        "description": "Miete März 2026",
        "income_category": "rental_income",
        "property_id": "550e8400-e29b-41d4-a716-446655440000"
      }
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        transaction = service.link_transaction_to_property(
            transaction_id,
            property_id,
            current_user.id
        )
        return {
            "message": "Transaction linked successfully",
            "transaction_id": transaction.id,
            "property_id": str(property_id),
            "transaction": transaction
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.delete("/{property_id}/unlink-transaction/{transaction_id}")
def unlink_transaction(
    property_id: UUID,
    transaction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Unlink a transaction from a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property (for validation)
    - **transaction_id**: ID of the transaction to unlink
    
    **Effects:**
    - Transaction's property_id is set to NULL
    - Transaction remains in the system but is no longer associated with the property
    
    **Validation:**
    - Transaction must belong to the current user
    - Transaction must exist
    
    **Returns:**
    - Updated transaction with property_id = null
    
    **Example Request:**
    ```
    DELETE /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/unlink-transaction/1001
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "message": "Transaction unlinked successfully",
      "transaction_id": 1001,
      "property_id": null,
      "transaction": {
        "id": 1001,
        "type": "income",
        "amount": 1500.00,
        "transaction_date": "2026-03-01",
        "description": "Miete März 2026",
        "income_category": "rental_income",
        "property_id": null
      }
    }
    ```
    """
    service = PropertyService(db)
    
    try:
        # Verify property ownership first
        service.get_property(property_id, current_user.id)
        
        # Unlink transaction
        transaction = service.unlink_transaction_from_property(
            transaction_id,
            current_user.id
        )
        
        return {
            "message": "Transaction unlinked successfully",
            "transaction_id": transaction.id,
            "property_id": None,
            "transaction": transaction
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/{property_id}/historical-depreciation", response_model=HistoricalDepreciationPreview)
def preview_historical_depreciation(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Preview historical depreciation backfill for a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Returns:**
    - List of years with depreciation amounts
    - Total amount to be backfilled
    - Number of years to backfill
    
    **Use Case:**
    When a property was purchased in a previous year (e.g., 2020) but registered
    in the system later (e.g., 2026), this endpoint shows what depreciation
    transactions will be created for the missing years (2020-2025).
    
    **Note:**
    - This is a preview only - no transactions are created
    - Years that already have depreciation transactions are excluded
    - Use POST /backfill-depreciation to confirm and create transactions
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/historical-depreciation
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "years_count": 6,
      "total_amount": 33600.00,
      "years": [
        {
          "year": 2020,
          "amount": 2800.00,
          "transaction_date": "2020-12-31"
        },
        {
          "year": 2021,
          "amount": 5600.00,
          "transaction_date": "2021-12-31"
        },
        {
          "year": 2022,
          "amount": 5600.00,
          "transaction_date": "2022-12-31"
        },
        {
          "year": 2023,
          "amount": 5600.00,
          "transaction_date": "2023-12-31"
        },
        {
          "year": 2024,
          "amount": 5600.00,
          "transaction_date": "2024-12-31"
        },
        {
          "year": 2025,
          "amount": 5600.00,
          "transaction_date": "2025-12-31"
        }
      ]
    }
    ```
    """
    service = PropertyService(db)
    historical_service = HistoricalDepreciationService(db)
    
    try:
        # Validate ownership
        property = service.get_property(property_id, current_user.id)
        
        # Calculate historical depreciation
        historical_years = historical_service.calculate_historical_depreciation(property_id)
        
        # Convert to response format
        years_data = [
            {
                "year": year.year,
                "amount": year.amount,
                "transaction_date": year.transaction_date
            }
            for year in historical_years
        ]
        
        total_amount = sum(year.amount for year in historical_years)
        
        return HistoricalDepreciationPreview(
            property_id=property_id,
            years=years_data,
            total_amount=total_amount,
            years_count=len(historical_years)
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.post("/{property_id}/backfill-depreciation", response_model=BackfillDepreciationResult)
def backfill_historical_depreciation(
    property_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Backfill historical depreciation transactions for a property.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Effects:**
    - Creates depreciation expense transactions for all missing years
    - Transactions are dated December 31 of each year
    - Transactions are marked as system-generated (is_system_generated=True)
    - Transactions are linked to the property
    
    **Returns:**
    - Number of years backfilled
    - Total depreciation amount created
    - List of created transaction IDs
    
    **Use Case:**
    After previewing with GET /historical-depreciation, call this endpoint to
    confirm and create the historical depreciation transactions.
    
    **Validation:**
    - Property must belong to current user
    - Duplicate transactions are prevented (years already backfilled are skipped)
    - Total accumulated depreciation cannot exceed building value
    
    **Example:**
    Property purchased in 2020, registered in 2026:
    - Creates transactions for 2020, 2021, 2022, 2023, 2024, 2025
    - Each transaction dated December 31 of respective year
    - Total accumulated depreciation updated
    
    **Error Handling:**
    - 404: Property not found
    - 403: Property doesn't belong to user
    - 400: Already backfilled (no missing years)
    - 500: Database error (transaction rolled back)
    
    **Example Request:**
    ```
    POST /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/backfill-depreciation
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property_id": "550e8400-e29b-41d4-a716-446655440000",
      "years_backfilled": 6,
      "total_amount": 33600.00,
      "transaction_ids": [5001, 5002, 5003, 5004, 5005, 5006]
    }
    ```
    """
    service = PropertyService(db)
    historical_service = HistoricalDepreciationService(db)
    
    try:
        # Validate ownership
        property = service.get_property(property_id, current_user.id)
        
        # Backfill depreciation (confirm=True creates transactions)
        result = historical_service.backfill_depreciation(
            property_id,
            current_user.id,
            confirm=True
        )
        
        # Check if any transactions were created
        if result.years_backfilled == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No historical depreciation to backfill. All years already have depreciation transactions."
            )
        
        return BackfillDepreciationResult(
            property_id=result.property_id,
            years_backfilled=result.years_backfilled,
            total_amount=result.total_amount,
            transaction_ids=[t.id for t in result.transactions]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except RuntimeError as e:
        # Database error during backfill
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



@router.post("/generate-annual-depreciation", response_model=AnnualDepreciationResponse)
def generate_annual_depreciation(
    year: int = Query(
        None,
        description="Tax year to generate depreciation for (default: current year)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate annual depreciation transactions for current user's properties.
    
    **Query Parameters:**
    - **year**: Tax year to generate depreciation for (optional, default: current year)
    
    **Effects:**
    - Creates depreciation expense transactions for all active properties owned by current user
    - Transactions are dated December 31 of the specified year
    - Transactions are marked as system-generated (is_system_generated=True)
    - Transactions are linked to their respective properties
    
    **Returns:**
    - Number of properties processed
    - Number of transactions created
    - Number of properties skipped (with reasons)
    - Total depreciation amount generated
    - List of created transaction IDs
    
    **Skipping Logic:**
    Properties are skipped if:
    - Depreciation already exists for the specified year
    - Property is fully depreciated (accumulated depreciation = building value)
    - Calculated depreciation amount is zero
    
    **Use Case:**
    At year-end, users can trigger this endpoint to generate depreciation transactions
    for all their rental properties. This ensures all depreciation expenses are recorded
    for tax filing purposes.
    
    **Example Request:**
    ```
    POST /api/v1/properties/generate-annual-depreciation?year=2025
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "year": 2025,
      "properties_processed": 3,
      "transactions_created": 2,
      "properties_skipped": 1,
      "total_amount": 11200.00,
      "transaction_ids": [1234, 1235],
      "skipped_details": [
        {
          "property_id": "550e8400-e29b-41d4-a716-446655440000",
          "address": "Hauptstraße 123, 1010 Wien",
          "reason": "already_exists"
        }
      ]
    }
    ```
    
    **Error Handling:**
    - 401: Not authenticated
    - 400: Invalid year parameter
    - 500: Database error (transaction rolled back)
    """
    annual_service = AnnualDepreciationService(db)
    
    # Default to current year if not provided
    if year is None:
        year = date.today().year
    
    # Validate year
    current_year = date.today().year
    if year < 2000 or year > current_year + 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid year. Year must be between 2000 and {current_year + 1}. Provided: {year}"
        )
    
    try:
        # Generate depreciation for current user only
        result = annual_service.generate_annual_depreciation(
            year=year,
            user_id=current_user.id
        )
        
        return AnnualDepreciationResponse(
            year=result.year,
            properties_processed=result.properties_processed,
            transactions_created=result.transactions_created,
            properties_skipped=result.properties_skipped,
            total_amount=result.total_amount,
            transaction_ids=[t.id for t in result.transactions],
            skipped_details=result.skipped_details
        )
        
    except RuntimeError as e:
        # Database error during generation
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )



@router.post("/extract-kaufvertrag")
def extract_kaufvertrag_data(
    file: bytes = Depends(lambda: None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract property data from Kaufvertrag (purchase contract) using Tesseract OCR + pattern matching.
    
    **Process:**
    1. OCR text extraction using Tesseract
    2. Pattern-based field extraction
    3. Confidence scoring and validation
    
    **Extracted fields:**
    - Property address (street, city, postal code)
    - Purchase price, building value, land value
    - Purchase date
    - Buyer and seller names
    - Notary information
    - Construction year
    - Purchase costs (Grunderwerbsteuer, notary fees, registry fees)
    
    **Returns:**
    - Extracted data with confidence scores
    - Validation status and recommendations
    - Raw OCR text for review
    
    **Usage:**
    Upload a PDF or image of a Kaufvertrag document. The system will extract
    structured data that can be used to pre-fill the property registration form.
    """
    from fastapi import File, UploadFile
    from app.services.kaufvertrag_ocr_service import KaufvertragOCRService
    
    # This endpoint should be called with multipart/form-data
    # For now, returning a placeholder response
    # Full implementation requires FastAPI File upload handling
    
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Endpoint implementation pending. Use POST /api/v1/documents/upload with document_type=KAUFVERTRAG"
    )


@router.post("/extract-kaufvertrag-from-text")
def extract_kaufvertrag_from_text(
    text: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Extract property data from pre-extracted Kaufvertrag text (skip OCR stage).
    
    Useful for testing or when text has already been extracted.
    
    **Request body:**
    ```json
    {
        "text": "KAUFVERTRAG\\n\\nLiegenschaft: Hauptstraße 123, 1010 Wien\\n..."
    }
    ```
    
    **Returns:**
    - Extracted property data
    - Confidence scores
    - Validation results
    """
    from app.services.kaufvertrag_ocr_service import KaufvertragOCRService
    from pydantic import BaseModel
    
    try:
        service = KaufvertragOCRService()
        result = service.process_kaufvertrag_from_text(text)
        validation = service.validate_extraction(result)
        
        return {
            "success": True,
            "extraction": result.to_dict(),
            "validation": validation
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )


@router.get("/{property_id}/reports/income-statement")
def get_income_statement(
    property_id: UUID,
    start_date: Optional[date] = Query(None, description="Start date for report (default: beginning of current year)"),
    end_date: Optional[date] = Query(None, description="End date for report (default: today)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate income statement report for a property.
    
    Shows rental income, expenses by category, and net income for the specified period.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **start_date**: Start date for report (optional, default: beginning of current year)
    - **end_date**: End date for report (optional, default: today)
    
    **Returns:**
    - Property details (address, purchase date, building value)
    - Period information (start and end dates)
    - Income breakdown (rental income, total income)
    - Expenses breakdown (by category, total expenses)
    - Net income (income - expenses)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement?start_date=2026-01-01&end_date=2026-12-31
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "address": "Hauptstraße 123, 1010 Wien",
        "purchase_date": "2020-06-15",
        "building_value": 280000.00
      },
      "period": {
        "start_date": "2026-01-01",
        "end_date": "2026-12-31"
      },
      "income": {
        "rental_income": 18000.00,
        "total": 18000.00
      },
      "expenses": {
        "depreciation_afa": 5600.00,
        "property_management_fees": 1200.00,
        "property_insurance": 800.00,
        "maintenance_repairs": 1500.00,
        "utilities": 900.00,
        "total": 10000.00
      },
      "net_income": 8000.00
    }
    ```
    """
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        report_data = report_service.generate_income_statement(
            str(property_id),
            start_date=start_date,
            end_date=end_date
        )
        return report_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/reports/depreciation-schedule")
def get_depreciation_schedule(
    property_id: UUID,
    include_future: bool = Query(
        default=True,
        description="Include future depreciation projections"
    ),
    future_years: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Number of future years to project (1-50)"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Generate depreciation schedule report for a property.
    
    Shows annual depreciation, accumulated depreciation, and remaining value by year.
    Includes both historical (actual) and future (projected) depreciation.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **include_future**: Include future depreciation projections (default: true)
    - **future_years**: Number of future years to project, 1-50 (default: 10)
    
    **Returns:**
    - Property details (address, purchase date, building value, depreciation rate, status)
    - Depreciation schedule (year-by-year breakdown with is_projected flag)
    - Summary (total years, years elapsed, years projected, accumulated depreciation, remaining value, years remaining)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule?include_future=true&future_years=10
    ```
    
    **Example Response (200 OK):**
    ```json
    {
      "property": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "address": "Hauptstraße 123, 1010 Wien",
        "purchase_date": "2020-06-15",
        "building_value": 280000.00,
        "depreciation_rate": 0.02,
        "status": "active",
        "sale_date": null
      },
      "schedule": [
        {
          "year": 2020,
          "annual_depreciation": 2800.00,
          "accumulated_depreciation": 2800.00,
          "remaining_value": 277200.00,
          "is_projected": false
        },
        {
          "year": 2021,
          "annual_depreciation": 5600.00,
          "accumulated_depreciation": 8400.00,
          "remaining_value": 271600.00,
          "is_projected": false
        },
        {
          "year": 2027,
          "annual_depreciation": 5600.00,
          "accumulated_depreciation": 42000.00,
          "remaining_value": 238000.00,
          "is_projected": true
        }
      ],
      "summary": {
        "total_years": 56,
        "years_elapsed": 6,
        "years_projected": 10,
        "total_depreciation": 280000.00,
        "accumulated_depreciation": 33600.00,
        "remaining_value": 246400.00,
        "years_remaining": 44.0,
        "fully_depreciated_year": 2070
      }
    }
    ```
    """
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        report_data = report_service.generate_depreciation_schedule(
            str(property_id),
            include_future=include_future,
            future_years=future_years
        )
        return report_data
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/reports/income-statement/export/pdf")
def export_income_statement_pdf(
    property_id: UUID,
    start_date: Optional[date] = Query(None, description="Start date for report"),
    end_date: Optional[date] = Query(None, description="End date for report"),
    language: str = Query("de", description="Language code (de, en)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export income statement to PDF format.
    
    Generates a professional PDF report with property details, income/expense breakdown,
    and net income for the specified period.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **start_date**: Start date for report (optional, default: beginning of current year)
    - **end_date**: End date for report (optional, default: today)
    - **language**: Language code for report (de, en) (default: de)
    
    **Returns:**
    - PDF file (application/pdf)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/pdf?start_date=2026-01-01&end_date=2026-12-31&language=de
    ```
    """
    from fastapi.responses import Response
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        pdf_bytes = report_service.export_income_statement_pdf(
            str(property_id),
            start_date=start_date,
            end_date=end_date,
            language=language
        )
        
        # Generate filename
        filename = f"income_statement_{property_id}_{date.today().isoformat()}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/reports/income-statement/export/csv")
def export_income_statement_csv(
    property_id: UUID,
    start_date: Optional[date] = Query(None, description="Start date for report"),
    end_date: Optional[date] = Query(None, description="End date for report"),
    language: str = Query("de", description="Language code (de, en)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export income statement to CSV format.
    
    Generates a CSV file with property details, income/expense breakdown,
    and net income for the specified period.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **start_date**: Start date for report (optional, default: beginning of current year)
    - **end_date**: End date for report (optional, default: today)
    - **language**: Language code for report (de, en) (default: de)
    
    **Returns:**
    - CSV file (text/csv)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/income-statement/export/csv?start_date=2026-01-01&end_date=2026-12-31&language=de
    ```
    """
    from fastapi.responses import Response
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        csv_content = report_service.export_income_statement_csv(
            str(property_id),
            start_date=start_date,
            end_date=end_date,
            language=language
        )
        
        # Generate filename
        filename = f"income_statement_{property_id}_{date.today().isoformat()}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/reports/depreciation-schedule/export/pdf")
def export_depreciation_schedule_pdf(
    property_id: UUID,
    include_future: bool = Query(True, description="Include future projections"),
    future_years: int = Query(10, ge=1, le=50, description="Number of future years to project"),
    language: str = Query("de", description="Language code (de, en)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export depreciation schedule to PDF format.
    
    Generates a professional PDF report with property details, year-by-year depreciation
    schedule, and summary statistics.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **include_future**: Include future depreciation projections (default: true)
    - **future_years**: Number of future years to project, 1-50 (default: 10)
    - **language**: Language code for report (de, en) (default: de)
    
    **Returns:**
    - PDF file (application/pdf)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/pdf?include_future=true&future_years=10&language=de
    ```
    """
    from fastapi.responses import Response
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        pdf_bytes = report_service.export_depreciation_schedule_pdf(
            str(property_id),
            include_future=include_future,
            future_years=future_years,
            language=language
        )
        
        # Generate filename
        filename = f"depreciation_schedule_{property_id}_{date.today().isoformat()}.pdf"
        
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.get("/{property_id}/reports/depreciation-schedule/export/csv")
def export_depreciation_schedule_csv(
    property_id: UUID,
    include_future: bool = Query(True, description="Include future projections"),
    future_years: int = Query(10, ge=1, le=50, description="Number of future years to project"),
    language: str = Query("de", description="Language code (de, en)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Export depreciation schedule to CSV format.
    
    Generates a CSV file with property details, year-by-year depreciation schedule,
    and summary statistics.
    
    **Path Parameters:**
    - **property_id**: UUID of the property
    
    **Query Parameters:**
    - **include_future**: Include future depreciation projections (default: true)
    - **future_years**: Number of future years to project, 1-50 (default: 10)
    - **language**: Language code for report (de, en) (default: de)
    
    **Returns:**
    - CSV file (text/csv)
    
    **Example Request:**
    ```
    GET /api/v1/properties/550e8400-e29b-41d4-a716-446655440000/reports/depreciation-schedule/export/csv?include_future=true&future_years=10&language=de
    ```
    """
    from fastapi.responses import Response
    from app.services.property_report_service import PropertyReportService
    
    property_service = PropertyService(db)
    report_service = PropertyReportService(db)
    
    # Validate ownership
    property = property_service.get_property(property_id, current_user.id)
    if not property:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property {property_id} not found"
        )
    
    try:
        csv_content = report_service.export_depreciation_schedule_csv(
            str(property_id),
            include_future=include_future,
            future_years=future_years,
            language=language
        )
        
        # Generate filename
        filename = f"depreciation_schedule_{property_id}_{date.today().isoformat()}.csv"
        
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# Portfolio Comparison Endpoints

@router.get("/portfolio/compare", response_model=List[Dict[str, Any]])
def compare_portfolio(
    year: Optional[int] = Query(None, description="Tax year (default: current year)"),
    sort_by: str = Query("net_income", description="Sort field: net_income, rental_yield, expense_ratio, rental_income"),
    sort_order: str = Query("desc", description="Sort order: asc, desc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Compare performance across all user properties.
    
    Returns list of properties with:
    - Rental income
    - Expenses
    - Net income
    - Rental yield (%)
    - Expense ratio (%)
    - Depreciation
    
    Sorted by specified field and order.
    """
    from app.services.property_portfolio_service import PropertyPortfolioService
    
    portfolio_service = PropertyPortfolioService(db)
    
    try:
        comparisons = portfolio_service.compare_portfolio_properties(
            user_id=current_user.id,
            year=year,
            sort_by=sort_by,
            sort_order=sort_order
        )
        return comparisons
    except Exception as e:
        logger.error(f"Portfolio comparison failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to compare portfolio: {str(e)}")


@router.get("/portfolio/summary", response_model=Dict[str, Any])
def get_portfolio_summary(
    year: Optional[int] = Query(None, description="Tax year (default: current year)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get portfolio-level summary statistics.
    
    Returns:
    - Total property count
    - Total rental income
    - Total expenses
    - Total net income
    - Average rental yield
    - Average expense ratio
    - Best/worst performers
    """
    from app.services.property_portfolio_service import PropertyPortfolioService
    
    portfolio_service = PropertyPortfolioService(db)
    
    try:
        summary = portfolio_service.get_portfolio_summary(
            user_id=current_user.id,
            year=year
        )
        return summary
    except Exception as e:
        logger.error(f"Portfolio summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio summary: {str(e)}")


# Bulk Operations Endpoints

@router.post("/bulk/generate-depreciation", response_model=Dict[str, Any])
def bulk_generate_depreciation(
    property_ids: List[str] = Body(..., description="List of property UUIDs"),
    year: int = Body(..., description="Tax year"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate annual depreciation for multiple properties.
    
    Request body:
    ```json
    {
        "property_ids": ["uuid1", "uuid2", ...],
        "year": 2026
    }
    ```
    
    Returns summary with successful, failed, and skipped counts.
    """
    from app.services.property_portfolio_service import PropertyPortfolioService
    
    portfolio_service = PropertyPortfolioService(db)
    
    try:
        # Convert string UUIDs to UUID objects
        uuid_list = [UUID(pid) for pid in property_ids]
        
        results = portfolio_service.bulk_generate_annual_depreciation(
            user_id=current_user.id,
            property_ids=uuid_list,
            year=year
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except Exception as e:
        logger.error(f"Bulk depreciation generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to generate depreciation: {str(e)}")


@router.post("/bulk/archive", response_model=Dict[str, Any])
def bulk_archive(
    property_ids: List[str] = Body(..., description="List of property UUIDs to archive"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Archive multiple properties.
    
    Request body:
    ```json
    {
        "property_ids": ["uuid1", "uuid2", ...]
    }
    ```
    
    Returns summary with successful and failed counts.
    """
    from app.services.property_portfolio_service import PropertyPortfolioService
    
    portfolio_service = PropertyPortfolioService(db)
    
    try:
        # Convert string UUIDs to UUID objects
        uuid_list = [UUID(pid) for pid in property_ids]
        
        results = portfolio_service.bulk_archive_properties(
            user_id=current_user.id,
            property_ids=uuid_list
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except Exception as e:
        logger.error(f"Bulk archive failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to archive properties: {str(e)}")


@router.post("/{property_id}/bulk/link-transactions", response_model=Dict[str, Any])
def bulk_link_transactions(
    property_id: str,
    transaction_ids: List[int] = Body(..., description="List of transaction IDs to link"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Link multiple transactions to a property.
    
    Request body:
    ```json
    {
        "transaction_ids": [1, 2, 3, ...]
    }
    ```
    
    Returns summary with successful and failed counts.
    """
    from app.services.property_portfolio_service import PropertyPortfolioService
    
    portfolio_service = PropertyPortfolioService(db)
    
    try:
        property_uuid = UUID(property_id)
        
        results = portfolio_service.bulk_link_transactions(
            user_id=current_user.id,
            property_id=property_uuid,
            transaction_ids=transaction_ids
        )
        return results
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid UUID format: {str(e)}")
    except Exception as e:
        logger.error(f"Bulk transaction linking failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to link transactions: {str(e)}")
