"""
Property Management Service

Main service for property CRUD operations and business logic.
Handles property registration, updates, archival, transaction linking, and metrics calculation.
"""

from decimal import Decimal
from datetime import date
from typing import List, Optional, Dict, Any
from uuid import UUID
import json
import redis
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, extract, and_

from app.core.config import settings
from app.models.property import Property, PropertyType, PropertyStatus
from app.models.property_loan import PropertyLoan
from app.models.recurring_transaction import RecurringTransaction
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.user import User
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
    PropertyListItem,
    PropertyMetrics
)
from app.services.afa_calculator import AfACalculator
from app.services.asset_lifecycle_service import AssetLifecycleService
from app.core.metrics import property_created_counter


logger = logging.getLogger(__name__)


class PropertyService:
    """Main service for property management operations"""
    
    def __init__(self, db: Session):
        """
        Initialize property service.
        
        Args:
            db: SQLAlchemy database session
        """
        self.db = db
        self.afa_calculator = AfACalculator(db)
        self.asset_lifecycle_service = AssetLifecycleService(db)
        self._redis_client: Optional[redis.Redis] = None
        self._init_redis()
    def _validate_ownership(self, property_id: UUID, user_id: int) -> Property:
        """
        Validate that a property exists and belongs to the specified user.

        This is a security helper that returns 404-style errors for both
        non-existent properties and properties owned by other users to avoid
        leaking information about which properties exist in the system.

        Args:
            property_id: UUID of the property to validate
            user_id: ID of the user who should own the property

        Returns:
            Property instance if validation succeeds

        Raises:
            ValueError: If property not found OR does not belong to user
                       (intentionally uses same error for both cases)
        """
        property = self.db.query(Property).filter(Property.id == property_id).first()

        # Return same error for both "not found" and "not owned" to avoid
        # leaking information about which properties exist
        if not property or property.user_id != user_id:
            raise ValueError(f"Property with id {property_id} not found")

        return property
    
    def _init_redis(self):
        """Initialize synchronous Redis client for caching"""
        try:
            self._redis_client = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2
            )
            # Test connection
            self._redis_client.ping()
        except Exception as e:
            print(f"Redis connection failed: {e}. Caching disabled.")
            self._redis_client = None
    
    def _get_cached_metrics(self, property_id: UUID) -> Optional[PropertyMetrics]:
        """
        Get cached property metrics from Redis.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            PropertyMetrics if cached, None otherwise
        """
        if not self._redis_client:
            return None
        
        try:
            cache_key = f"property_metrics:{property_id}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                # Convert string values back to Decimal
                return PropertyMetrics(
                    property_id=UUID(data["property_id"]),
                    accumulated_depreciation=Decimal(str(data["accumulated_depreciation"])),
                    remaining_depreciable_value=Decimal(str(data["remaining_depreciable_value"])),
                    annual_depreciation=Decimal(str(data["annual_depreciation"])),
                    total_rental_income=Decimal(str(data["total_rental_income"])),
                    total_expenses=Decimal(str(data["total_expenses"])),
                    net_rental_income=Decimal(str(data["net_rental_income"])),
                    years_remaining=Decimal(str(data["years_remaining"])) if data.get("years_remaining") else None
                )
            return None
        except Exception as e:
            print(f"Cache get error for property {property_id}: {e}")
            return None
    
    def _set_cached_metrics(self, property_id: UUID, metrics: PropertyMetrics) -> bool:
        """
        Set cached property metrics in Redis with 1 hour TTL.
        
        Args:
            property_id: UUID of the property
            metrics: PropertyMetrics to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"property_metrics:{property_id}"
            # Convert Decimal to string for JSON serialization
            cache_data = {
                "property_id": str(metrics.property_id),
                "accumulated_depreciation": str(metrics.accumulated_depreciation),
                "remaining_depreciable_value": str(metrics.remaining_depreciable_value),
                "annual_depreciation": str(metrics.annual_depreciation),
                "total_rental_income": str(metrics.total_rental_income),
                "total_expenses": str(metrics.total_expenses),
                "net_rental_income": str(metrics.net_rental_income),
                "years_remaining": str(metrics.years_remaining) if metrics.years_remaining else None
            }
            
            # Cache for 1 hour (3600 seconds)
            self._redis_client.setex(
                cache_key,
                3600,
                json.dumps(cache_data)
            )
            return True
        except Exception as e:
            print(f"Cache set error for property {property_id}: {e}")
            return False
    
    def _invalidate_metrics_cache(self, property_id: UUID) -> bool:
        """
        Invalidate cached property metrics.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"property_metrics:{property_id}"
            self._redis_client.delete(cache_key)
            return True
        except Exception as e:
            print(f"Cache invalidation error for property {property_id}: {e}")
            return False
    
    # Portfolio metrics caching methods
    
    def _get_cached_portfolio_metrics(self, user_id: int, year: int) -> Optional[dict]:
        """
        Get cached portfolio metrics from Redis.
        
        Args:
            user_id: ID of the user
            year: Tax year
            
        Returns:
            Dict with portfolio metrics if cached, None otherwise
        """
        if not self._redis_client:
            return None
        
        try:
            cache_key = f"portfolio_metrics:{user_id}:{year}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                data = json.loads(cached_data)
                # Convert string values back to Decimal
                return {
                    "total_properties": data["total_properties"],
                    "total_building_value": Decimal(str(data["total_building_value"])),
                    "total_annual_depreciation": Decimal(str(data["total_annual_depreciation"])),
                    "total_rental_income": Decimal(str(data["total_rental_income"])),
                    "total_expenses": Decimal(str(data["total_expenses"])),
                    "net_rental_income": Decimal(str(data["net_rental_income"]))
                }
            return None
        except Exception as e:
            print(f"Cache get error for portfolio metrics user {user_id}, year {year}: {e}")
            return None
    
    def _set_cached_portfolio_metrics(self, user_id: int, year: int, metrics: dict) -> bool:
        """
        Set cached portfolio metrics in Redis with 1 hour TTL.
        
        Args:
            user_id: ID of the user
            year: Tax year
            metrics: Dict with portfolio metrics to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"portfolio_metrics:{user_id}:{year}"
            # Convert Decimal to string for JSON serialization
            cache_data = {
                "total_properties": metrics["total_properties"],
                "total_building_value": str(metrics["total_building_value"]),
                "total_annual_depreciation": str(metrics["total_annual_depreciation"]),
                "total_rental_income": str(metrics["total_rental_income"]),
                "total_expenses": str(metrics["total_expenses"]),
                "net_rental_income": str(metrics["net_rental_income"])
            }
            
            # Cache for 1 hour (3600 seconds)
            self._redis_client.setex(cache_key, 3600, json.dumps(cache_data))
            return True
        except Exception as e:
            print(f"Cache set error for portfolio metrics user {user_id}, year {year}: {e}")
            return False
    
    def _invalidate_portfolio_cache(self, user_id: int) -> bool:
        """
        Invalidate all cached portfolio metrics for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            # Delete all portfolio metrics for this user (all years)
            # Use pattern matching to find all keys
            pattern = f"portfolio_metrics:{user_id}:*"
            keys = self._redis_client.keys(pattern)
            if keys:
                self._redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"Cache invalidation error for portfolio metrics user {user_id}: {e}")
            return False
    
    # Depreciation schedule caching methods
    
    def _get_cached_depreciation_schedule(self, property_id: UUID) -> Optional[dict]:
        """
        Get cached depreciation schedule from Redis.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            Dict with depreciation schedule if cached, None otherwise
        """
        if not self._redis_client:
            return None
        
        try:
            cache_key = f"depreciation_schedule:{property_id}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Cache get error for depreciation schedule {property_id}: {e}")
            return None
    
    def _set_cached_depreciation_schedule(self, property_id: UUID, schedule: dict) -> bool:
        """
        Set cached depreciation schedule in Redis with 24 hour TTL.
        
        Args:
            property_id: UUID of the property
            schedule: Dict with depreciation schedule to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"depreciation_schedule:{property_id}"
            # Cache for 24 hours (86400 seconds)
            self._redis_client.setex(cache_key, 86400, json.dumps(schedule))
            return True
        except Exception as e:
            print(f"Cache set error for depreciation schedule {property_id}: {e}")
            return False
    
    def _invalidate_depreciation_schedule_cache(self, property_id: UUID) -> bool:
        """
        Invalidate cached depreciation schedule.
        
        Args:
            property_id: UUID of the property
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"depreciation_schedule:{property_id}"
            self._redis_client.delete(cache_key)
            return True
        except Exception as e:
            print(f"Cache invalidation error for depreciation schedule {property_id}: {e}")
            return False
    
    # Property list caching methods
    
    def _get_cached_property_list(
        self, user_id: int, include_archived: bool, skip: int, limit: int, year: Optional[int]
    ) -> Optional[tuple]:
        """
        Get cached property list from Redis.
        
        Args:
            user_id: ID of the user
            include_archived: Whether to include archived properties
            skip: Number of records to skip
            limit: Maximum number of records
            year: Optional year filter
            
        Returns:
            Tuple of (properties_data, metrics_data, total_count) if cached, None otherwise
        """
        if not self._redis_client:
            return None
        
        try:
            cache_key = f"property_list:{user_id}:{include_archived}:{skip}:{limit}:{year}"
            cached_data = self._redis_client.get(cache_key)
            
            if cached_data:
                return json.loads(cached_data)
            return None
        except Exception as e:
            print(f"Cache get error for property list user {user_id}: {e}")
            return None
    
    def _set_cached_property_list(
        self, user_id: int, include_archived: bool, skip: int, limit: int, 
        year: Optional[int], data: tuple
    ) -> bool:
        """
        Set cached property list in Redis with 5 minute TTL.
        
        Args:
            user_id: ID of the user
            include_archived: Whether to include archived properties
            skip: Number of records to skip
            limit: Maximum number of records
            year: Optional year filter
            data: Tuple of (properties_data, metrics_data, total_count) to cache
            
        Returns:
            True if cached successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            cache_key = f"property_list:{user_id}:{include_archived}:{skip}:{limit}:{year}"
            # Cache for 5 minutes (300 seconds) - shorter due to frequent updates
            self._redis_client.setex(cache_key, 300, json.dumps(data))
            return True
        except Exception as e:
            print(f"Cache set error for property list user {user_id}: {e}")
            return False
    
    def _invalidate_property_list_cache(self, user_id: int) -> bool:
        """
        Invalidate all cached property lists for a user.
        
        Args:
            user_id: ID of the user
            
        Returns:
            True if invalidated successfully, False otherwise
        """
        if not self._redis_client:
            return False
        
        try:
            # Delete all property lists for this user
            pattern = f"property_list:{user_id}:*"
            keys = self._redis_client.keys(pattern)
            if keys:
                self._redis_client.delete(*keys)
            return True
        except Exception as e:
            print(f"Cache invalidation error for property list user {user_id}: {e}")
            return False
    
    def _validate_ownership(self, property_id: UUID, user_id: int) -> Property:
        """
        Validate that a property exists and belongs to the specified user.
        
        This is a security helper that returns 404-style errors for both
        non-existent properties and properties owned by other users to avoid
        leaking information about which properties exist in the system.
        
        Args:
            property_id: UUID of the property to validate
            user_id: ID of the user who should own the property
            
        Returns:
            Property instance if validation succeeds
            
        Raises:
            ValueError: If property not found OR does not belong to user
                       (intentionally uses same error for both cases)
        """
        property = self.db.query(Property).filter(Property.id == property_id).first()
        
        # Return same error for both "not found" and "not owned" to avoid
        # leaking information about which properties exist
        if not property or property.user_id != user_id:
            raise ValueError(f"Property with id {property_id} not found")
        
        return property
    
    def create_property(
        self, 
        user_id: int, 
        property_data: PropertyCreate
    ) -> Property:
        """
        Create a new property with validation and auto-calculations.
        
        Auto-calculations:
        - building_value = 80% of purchase_price if not provided (handled by schema)
        - depreciation_rate based on construction_year (handled by schema)
        - land_value = purchase_price - building_value
        - address = f"{street}, {postal_code} {city}"
        
        Args:
            user_id: ID of the user creating the property
            property_data: Validated property creation data
            
        Returns:
            Created Property instance
            
        Raises:
            ValueError: If user does not exist
        """
        # Verify user exists
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")
        
        # Calculate land_value
        land_value = property_data.purchase_price - property_data.building_value
        
        # Construct full address
        full_address = f"{property_data.street}, {property_data.postal_code} {property_data.city}"
        
        # Create property instance
        property = Property(
            user_id=user_id,
            property_type=property_data.property_type,
            rental_percentage=property_data.rental_percentage,
            address=full_address,
            street=property_data.street,
            city=property_data.city,
            postal_code=property_data.postal_code,
            purchase_date=property_data.purchase_date,
            purchase_price=property_data.purchase_price,
            building_value=property_data.building_value,
            land_value=land_value,
            construction_year=property_data.construction_year,
            depreciation_rate=property_data.depreciation_rate,
            grunderwerbsteuer=property_data.grunderwerbsteuer,
            notary_fees=property_data.notary_fees,
            registry_fees=property_data.registry_fees,
            status=PropertyStatus.ACTIVE
        )
        
        self.db.add(property)
        self.db.commit()
        self.db.refresh(property)
        
        # Increment Prometheus counter for property creation
        property_created_counter.labels(user_id=str(user_id)).inc()
        
        # Log property creation with structured data
        logger.info(
            "Property created",
            extra={
                "user_id": user_id,
                "property_id": str(property.id),
                "property_type": property.property_type.value,
                "address": property.address,
                "purchase_price": float(property.purchase_price),
                "building_value": float(property.building_value),
                "depreciation_rate": float(property.depreciation_rate)
            }
        )
        
        # Invalidate portfolio and list caches
        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)
        
        return property

    def create_asset(self, user_id: int, asset_data) -> Property:
        """
        Create a non-real-estate asset (vehicle, equipment, etc.) as a Property record.

        Uses the existing Property model with asset_type != 'real_estate'.
        Depreciation is straight-line over useful_life_years.

        Args:
            user_id: Owner user ID
            asset_data: AssetCreate schema instance

        Returns:
            Created Property instance
        """
        from app.schemas.property import ASSET_USEFUL_LIFE

        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise ValueError(f"User with id {user_id} not found")

        useful_life = asset_data.useful_life_years or ASSET_USEFUL_LIFE.get(
            asset_data.asset_type, 5
        )
        depreciation_method = getattr(asset_data.depreciation_method, "value", asset_data.depreciation_method) or "linear"
        if asset_data.gwg_elected:
            useful_life = 1
            dep_rate = Decimal("1.0000")
            depreciation_method = "linear"
        elif depreciation_method == "degressive":
            dep_rate = Decimal(str(asset_data.degressive_afa_rate or Decimal("0.30"))).quantize(Decimal("0.0001"))
        else:
            dep_rate = (Decimal("1") / Decimal(str(useful_life))).quantize(Decimal("0.0001"))

        # For non-real-estate assets, building_value is the income-tax depreciable base.
        depreciable_value = (
            asset_data.income_tax_depreciable_base
            or asset_data.comparison_amount
            or asset_data.purchase_price
        )
        comparison_basis = getattr(asset_data.comparison_basis, "value", asset_data.comparison_basis)
        useful_life_source = getattr(asset_data.useful_life_source, "value", asset_data.useful_life_source)
        vat_recoverable_status = getattr(
            asset_data.vat_recoverable_status,
            "value",
            asset_data.vat_recoverable_status,
        )
        ifb_rate_source = getattr(asset_data.ifb_rate_source, "value", asset_data.ifb_rate_source)
        recognition_decision = getattr(
            asset_data.recognition_decision,
            "value",
            asset_data.recognition_decision,
        )

        # Address placeholder for non-real-estate assets (required by DB constraints)
        placeholder_name = asset_data.name or asset_data.asset_type

        asset = Property(
            user_id=user_id,
            asset_type=asset_data.asset_type,
            sub_category=asset_data.sub_category,
            name=asset_data.name,
            property_type=PropertyType.RENTAL,  # reuse enum; means "business use"
            rental_percentage=asset_data.business_use_percentage,
            business_use_percentage=asset_data.business_use_percentage,
            address=placeholder_name,
            street=placeholder_name,
            city="-",
            postal_code="0000",
            purchase_date=asset_data.purchase_date,
            purchase_price=asset_data.purchase_price,
            building_value=depreciable_value,
            land_value=Decimal("0"),
            depreciation_rate=dep_rate,
            useful_life_years=useful_life,
            acquisition_kind=asset_data.acquisition_kind,
            put_into_use_date=asset_data.put_into_use_date,
            is_used_asset=asset_data.is_used_asset,
            first_registration_date=asset_data.first_registration_date,
            prior_owner_usage_years=asset_data.prior_owner_usage_years,
            comparison_basis=comparison_basis,
            comparison_amount=asset_data.comparison_amount or asset_data.purchase_price,
            gwg_eligible=asset_data.gwg_eligible,
            gwg_elected=asset_data.gwg_elected,
            depreciation_method=depreciation_method,
            degressive_afa_rate=asset_data.degressive_afa_rate,
            useful_life_source=useful_life_source,
            income_tax_cost_cap=asset_data.income_tax_cost_cap,
            income_tax_depreciable_base=depreciable_value,
            vat_recoverable_status=vat_recoverable_status,
            ifb_candidate=asset_data.ifb_candidate,
            ifb_rate=asset_data.ifb_rate,
            ifb_rate_source=ifb_rate_source,
            recognition_decision=recognition_decision,
            policy_confidence=asset_data.policy_confidence,
            supplier=asset_data.supplier,
            accumulated_depreciation=Decimal("0"),
            status=PropertyStatus.ACTIVE,
            kaufvertrag_document_id=asset_data.document_id,
        )

        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)

        logger.info(
            "Asset created",
            extra={
                "user_id": user_id,
                "asset_id": str(asset.id),
                "asset_type": asset_data.asset_type,
                "name": asset_data.name,
                "purchase_price": float(asset_data.purchase_price),
                "useful_life": useful_life,
                "depreciation_rate": float(dep_rate),
                "depreciation_method": depreciation_method,
                "put_into_use_date": (
                    asset_data.put_into_use_date.isoformat() if asset_data.put_into_use_date else None
                ),
            },
        )

        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)

        return asset

    def list_assets(self, user_id: int, include_archived: bool = False) -> list:
        """List non-real-estate assets for a user."""
        query = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.asset_type != "real_estate",
        )
        if not include_archived:
            query = query.filter(Property.status == PropertyStatus.ACTIVE)
        return query.order_by(Property.created_at.desc()).all()

    def get_property(self, property_id: UUID, user_id: int) -> Property:
        """
        Get property with ownership validation.
        Also syncs expired rental contracts on-the-fly.
        
        Args:
            property_id: UUID of the property
            user_id: ID of the user requesting the property
            
        Returns:
            Property instance
            
        Raises:
            ValueError: If property not found or does not belong to user
        """
        prop = self._validate_ownership(property_id, user_id)
        self._sync_expired_rental_contracts(prop, user_id)
        return prop

    def _sync_expired_rental_contracts(self, prop: Property, user_id: int) -> None:
        """Deactivate expired rental contracts and recalculate rental percentage."""
        from app.models.recurring_transaction import (
            RecurringTransaction,
            RecurringTransactionType,
        )

        today = date.today()
        changed = False

        # 1. Deactivate any still-active contracts that have expired
        expired_active = (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.property_id == prop.id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.is_active == True,
                RecurringTransaction.end_date.isnot(None),
                RecurringTransaction.end_date < today,
            )
            .all()
        )
        if expired_active:
            for rt in expired_active:
                rt.is_active = False
            self.db.commit()
            changed = True

        # 2. Check if property_type is stale (rental but no active contracts)
        if not changed and prop.property_type in (PropertyType.RENTAL, PropertyType.MIXED_USE):
            active_count = (
                self.db.query(RecurringTransaction)
                .filter(
                    RecurringTransaction.property_id == prop.id,
                    RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                    RecurringTransaction.is_active == True,
                )
                .count()
            )
            if active_count == 0:
                changed = True

        if changed:
            self.recalculate_rental_percentage(prop.id, user_id)
            self.db.refresh(prop)
    
    def list_properties(
        self, 
        user_id: int, 
        include_archived: bool = False
    ) -> List[Property]:
        """
        List user's properties with optional archived filter.
        
        Args:
            user_id: ID of the user
            include_archived: If True, include archived/sold properties. Default False.
            
        Returns:
            List of Property instances
        """
        query = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.asset_type == "real_estate",
        )

        if not include_archived:
            # Exclude both SOLD and ARCHIVED properties
            query = query.filter(Property.status == PropertyStatus.ACTIVE)
        
        # Order by creation date descending (newest first)
        query = query.order_by(Property.created_at.desc())
        
        return query.all()
    
    def list_properties_with_metrics(
        self,
        user_id: int,
        include_archived: bool = False,
        skip: int = 0,
        limit: int = 50,
        year: Optional[int] = None
    ) -> tuple[List[Property], List[PropertyMetrics], int]:
        """
        List user's properties with embedded metrics using optimized SQL queries.
        
        This method avoids N+1 query problems by:
        1. Using SQL joins to fetch properties with related data in one query
        2. Using aggregations to calculate metrics (SUM, COUNT)
        3. Leveraging database indexes created in C.2.1
        
        Args:
            user_id: ID of the user
            include_archived: If True, include archived/sold properties. Default False.
            skip: Number of records to skip (for pagination). Default 0.
            limit: Maximum number of records to return. Default 50.
            year: Optional year filter for metrics. Default current year.
            
        Returns:
            Tuple of (properties_list, metrics_list, total_count)
            - properties_list: List of Property instances
            - metrics_list: List of PropertyMetrics corresponding to properties
            - total_count: Total number of properties (for pagination)
        """
        from sqlalchemy.orm import joinedload
        
        # Use current year if not specified
        if year is None:
            year = date.today().year
        
        # Build base query for properties
        base_query = self.db.query(Property).filter(Property.user_id == user_id)
        
        if not include_archived:
            base_query = base_query.filter(Property.status == PropertyStatus.ACTIVE)
        
        # Get total count for pagination (before applying skip/limit)
        total_count = base_query.count()
        
        # Apply ordering and pagination
        properties_query = base_query.order_by(Property.created_at.desc()).offset(skip).limit(limit)
        
        # Execute query to get properties
        properties = properties_query.all()
        
        if not properties:
            return [], [], total_count
        
        # Extract property IDs for batch metric calculation
        property_ids = [p.id for p in properties]
        
        # Calculate accumulated depreciation for all properties in one query
        # Uses idx_transactions_property_id and idx_transactions_depreciation indexes
        depreciation_subquery = (
            self.db.query(
                Transaction.property_id,
                func.sum(Transaction.amount).label('accumulated_depreciation')
            )
            .filter(
                Transaction.property_id.in_(property_ids),
                Transaction.expense_category == ExpenseCategory.DEPRECIATION_AFA
            )
            .group_by(Transaction.property_id)
            .subquery()
        )
        
        # Calculate rental income for the year for all properties in one query
        # Uses idx_transactions_property_date index
        rental_income_subquery = (
            self.db.query(
                Transaction.property_id,
                func.sum(Transaction.amount).label('rental_income')
            )
            .filter(
                Transaction.property_id.in_(property_ids),
                Transaction.type == TransactionType.INCOME,
                Transaction.income_category == IncomeCategory.RENTAL,
                extract('year', Transaction.transaction_date) == year
            )
            .group_by(Transaction.property_id)
            .subquery()
        )
        
        # Calculate expenses for the year for all properties in one query
        # Uses idx_transactions_property_date index
        expenses_subquery = (
            self.db.query(
                Transaction.property_id,
                func.sum(Transaction.amount).label('total_expenses')
            )
            .filter(
                Transaction.property_id.in_(property_ids),
                Transaction.type == TransactionType.EXPENSE,
                extract('year', Transaction.transaction_date) == year
            )
            .group_by(Transaction.property_id)
            .subquery()
        )
        
        # Fetch all aggregated metrics in one query using LEFT JOINs
        metrics_query = (
            self.db.query(
                Property.id,
                func.coalesce(depreciation_subquery.c.accumulated_depreciation, Decimal("0")).label('accumulated_depreciation'),
                func.coalesce(rental_income_subquery.c.rental_income, Decimal("0")).label('rental_income'),
                func.coalesce(expenses_subquery.c.total_expenses, Decimal("0")).label('total_expenses')
            )
            .outerjoin(depreciation_subquery, Property.id == depreciation_subquery.c.property_id)
            .outerjoin(rental_income_subquery, Property.id == rental_income_subquery.c.property_id)
            .outerjoin(expenses_subquery, Property.id == expenses_subquery.c.property_id)
            .filter(Property.id.in_(property_ids))
        )
        
        # Execute and build metrics dictionary
        metrics_data = {row.id: row for row in metrics_query.all()}
        
        # Build PropertyMetrics for each property
        metrics_list = []
        for property in properties:
            row = metrics_data.get(property.id)
            
            if row:
                accumulated_depreciation = row.accumulated_depreciation
                rental_income = row.rental_income
                total_expenses = row.total_expenses
            else:
                accumulated_depreciation = Decimal("0")
                rental_income = Decimal("0")
                total_expenses = Decimal("0")
            
            # Calculate depreciable value (considering rental percentage for mixed-use)
            depreciable_value = property.building_value
            if getattr(property, "asset_type", "real_estate") != "real_estate":
                depreciable_value = self.asset_lifecycle_service.get_depreciable_base(property)
            elif property.property_type == PropertyType.MIXED_USE:
                rental_pct = property.rental_percentage / Decimal("100")
                depreciable_value = depreciable_value * rental_pct
            
            # Calculate remaining depreciable value
            remaining_depreciable_value = max(
                depreciable_value - accumulated_depreciation,
                Decimal("0")
            )
            
            # Calculate annual depreciation for specified year
            annual_depreciation = self.afa_calculator.calculate_annual_depreciation(
                property, year
            )
            
            # Calculate years remaining (if depreciation is ongoing)
            years_remaining = None
            if getattr(property, "asset_type", "real_estate") != "real_estate":
                years_remaining = self.asset_lifecycle_service.estimate_years_remaining(
                    property,
                    year,
                )
            elif annual_depreciation > 0 and property.depreciation_rate > 0:
                years_remaining = (
                    remaining_depreciable_value / (depreciable_value * property.depreciation_rate)
                ).quantize(Decimal("0.1"))
            
            # Calculate net rental income
            net_rental_income = rental_income - total_expenses
            
            metrics = PropertyMetrics(
                property_id=property.id,
                accumulated_depreciation=accumulated_depreciation,
                remaining_depreciable_value=remaining_depreciable_value,
                annual_depreciation=annual_depreciation,
                total_rental_income=rental_income,
                total_expenses=total_expenses,
                net_rental_income=net_rental_income,
                years_remaining=years_remaining
            )
            
            metrics_list.append(metrics)
        
        return properties, metrics_list, total_count
    
    def update_property(
        self, 
        property_id: UUID, 
        user_id: int, 
        updates: PropertyUpdate
    ) -> Property:
        """
        Update property (restricted fields: purchase_date, purchase_price).
        
        Note: purchase_date and purchase_price are immutable and not included
        in PropertyUpdate schema.
        
        Args:
            property_id: UUID of the property to update
            user_id: ID of the user updating the property
            updates: PropertyUpdate schema with fields to update
            
        Returns:
            Updated Property instance
            
        Raises:
            ValueError: If property not found or does not belong to user
        """
        # Get property with ownership validation
        property = self._validate_ownership(property_id, user_id)
        
        # Update fields that are provided (not None)
        update_data = updates.model_dump(exclude_unset=True)
        
        for field, value in update_data.items():
            if value is not None:
                setattr(property, field, value)
        
        # Recalculate land_value if building_value or purchase_price changed
        if 'building_value' in update_data or 'purchase_price' in update_data:
            property.land_value = property.purchase_price - property.building_value
        
        # Recalculate address if address components changed
        if any(field in update_data for field in ['street', 'city', 'postal_code']):
            property.address = f"{property.street}, {property.postal_code} {property.city}"
        
        self.db.commit()
        self.db.refresh(property)
        
        # Invalidate all caches
        self._invalidate_metrics_cache(property_id)
        self._invalidate_depreciation_schedule_cache(property_id)
        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)
        
        return property

    def recalculate_rental_percentage(self, property_id: UUID, user_id: int) -> Property:
        """
        Recalculate rental_percentage and property_type from rental contracts.

        rental_percentage is based on ACTIVE contracts only (for tax calculation).
        property_type is determined by active contracts:
          - active contracts with 100% → rental
          - active contracts with < 100% → mixed_use
          - no active contracts → owner_occupied (even if expired contracts exist)
        AfA history is preserved in transaction records regardless of property_type.
        """
        prop = self._validate_ownership(property_id, user_id)

        from app.models.recurring_transaction import (
            RecurringTransaction,
            RecurringTransactionType,
        )

        # Active contracts → determine rental_percentage for current tax year
        active_rentals = (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
                RecurringTransaction.is_active == True,
            )
            .all()
        )

        total_pct = sum(
            float(r.unit_percentage or 0) for r in active_rentals
        )
        total_pct = min(total_pct, 100.0)

        prop.rental_percentage = Decimal(str(total_pct)).quantize(Decimal("0.01"))

        # ALL contracts (including expired) → determine property_type
        # A property that was ever rented stays as rental/mixed_use
        all_rentals_count = (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
            )
            .count()
        )

        if all_rentals_count == 0:
            prop.property_type = PropertyType.OWNER_OCCUPIED
        elif total_pct >= 100:
            prop.property_type = PropertyType.RENTAL
        elif total_pct > 0:
            prop.property_type = PropertyType.MIXED_USE
        else:
            # Has rental history but no active contracts → owner_occupied
            # AfA history is preserved in transaction records regardless of property_type
            prop.property_type = PropertyType.OWNER_OCCUPIED

        self.db.commit()
        self.db.refresh(prop)

        self._invalidate_metrics_cache(property_id)
        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)

        logger.info(
            "Recalculated rental_percentage",
            extra={
                "property_id": str(property_id),
                "rental_percentage": float(prop.rental_percentage),
                "property_type": prop.property_type.value,
                "active_contracts": len(active_rentals),
            },
        )
        return prop

    def get_rental_contracts(self, property_id: UUID, user_id: int) -> list:
        """Get all rental income recurring transactions linked to a property."""
        self._validate_ownership(property_id, user_id)

        from app.models.recurring_transaction import (
            RecurringTransaction,
            RecurringTransactionType,
        )

        return (
            self.db.query(RecurringTransaction)
            .filter(
                RecurringTransaction.property_id == property_id,
                RecurringTransaction.recurring_type == RecurringTransactionType.RENTAL_INCOME,
            )
            .order_by(RecurringTransaction.start_date.desc())
            .all()
        )
    
    def archive_property(
        self, 
        property_id: UUID, 
        user_id: int, 
        sale_date: date
    ) -> Property:
        """
        Mark property as sold and archived.
        
        Args:
            property_id: UUID of the property to archive
            user_id: ID of the user archiving the property
            sale_date: Date the property was sold
            
        Returns:
            Updated Property instance
            
        Raises:
            ValueError: If property not found, does not belong to user, or sale_date is before purchase_date
        """
        # Get property with ownership validation
        property = self._validate_ownership(property_id, user_id)
        
        # Validate sale_date
        if sale_date < property.purchase_date:
            raise ValueError(
                f"Sale date ({sale_date}) cannot be before purchase date ({property.purchase_date})"
            )
        
        # Update property status
        property.status = PropertyStatus.SOLD
        property.sale_date = sale_date
        
        self.db.commit()
        self.db.refresh(property)
        
        # Invalidate portfolio and list caches
        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)

        return property

    def dispose_property(
        self,
        property_id: UUID,
        user_id: int,
        disposal_reason: str,
        disposal_date: date,
        sale_price: Optional[Decimal] = None,
    ) -> Property:
        """
        Dispose of a property/asset with a specific reason.

        Maps disposal_reason to PropertyStatus:
            sold -> SOLD, scrapped -> SCRAPPED,
            fully_depreciated -> ARCHIVED, private_withdrawal -> WITHDRAWN

        Creates an AssetEvent for sold/scrapped/private_withdrawal disposals.
        """
        from app.models.asset_event import AssetEvent, AssetEventType, AssetEventTriggerSource

        property = self._validate_ownership(property_id, user_id)

        # Real-estate properties may only be sold
        if property.asset_type == "real_estate" and disposal_reason != "sold":
            raise ValueError(
                f"Real-estate properties can only be disposed with reason 'sold'. "
                f"Got: '{disposal_reason}'"
            )

        # Validate disposal_date >= purchase_date
        if disposal_date < property.purchase_date:
            raise ValueError(
                f"Disposal date ({disposal_date}) cannot be before "
                f"purchase date ({property.purchase_date})"
            )

        # Map disposal_reason -> PropertyStatus
        status_map = {
            "sold": PropertyStatus.SOLD,
            "scrapped": PropertyStatus.SCRAPPED,
            "fully_depreciated": PropertyStatus.ARCHIVED,
            "private_withdrawal": PropertyStatus.WITHDRAWN,
        }
        new_status = status_map.get(disposal_reason)
        if new_status is None:
            raise ValueError(f"Unknown disposal_reason: '{disposal_reason}'")

        property.status = new_status
        property.disposal_reason = disposal_reason
        property.sale_date = disposal_date  # reuse sale_date for all disposal dates
        if disposal_reason == "sold":
            property.sale_price = sale_price

        # Create AssetEvent for sold / scrapped / private_withdrawal
        event_type_map = {
            "sold": AssetEventType.SOLD,
            "scrapped": AssetEventType.SCRAPPED,
            "private_withdrawal": AssetEventType.PRIVATE_WITHDRAWAL,
        }
        event_type = event_type_map.get(disposal_reason)
        if event_type is not None:
            self.asset_lifecycle_service.record_event(
                asset=property,
                event_type=event_type,
                event_date=disposal_date,
                trigger_source=AssetEventTriggerSource.USER,
                payload={
                    "disposal_reason": disposal_reason,
                    "sale_price": float(sale_price) if sale_price else None,
                },
            )

        # Create an income transaction when the asset is sold for a positive price
        if disposal_reason == "sold" and sale_price and sale_price > 0:
            sale_transaction = Transaction(
                user_id=user_id,
                property_id=property.id,
                type=TransactionType.INCOME,
                amount=sale_price,
                transaction_date=disposal_date,
                description=f"Sale of {property.name or property.address}",
                income_category=IncomeCategory.OTHER_INCOME,
                is_deductible=False,
                import_source="asset_disposal",
            )
            self.db.add(sale_transaction)

        self.db.commit()
        self.db.refresh(property)

        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)

        logger.info(
            "Property disposed",
            extra={
                "user_id": user_id,
                "property_id": str(property_id),
                "disposal_reason": disposal_reason,
                "disposal_date": disposal_date.isoformat(),
            },
        )

        return property

    def delete_property(self, property_id: UUID, user_id: int, force: bool = False) -> dict:
        """
        Delete property. If force=True, unlinks transactions and deletes
        recurring transactions/loans first. Otherwise returns impact summary.
        
        Args:
            property_id: UUID of the property to delete
            user_id: ID of the user deleting the property
            force: If True, cascade-delete related data
            
        Returns:
            dict with deletion result and impact summary
        """
        # Get property with ownership validation
        property = self._validate_ownership(property_id, user_id)
        
        # Count linked data
        transaction_count = self.db.query(func.count(Transaction.id)).filter(
            Transaction.property_id == property_id
        ).scalar() or 0
        
        recurring_count = self.db.query(func.count(RecurringTransaction.id)).filter(
            RecurringTransaction.property_id == property_id
        ).scalar() or 0
        
        loan_count = self.db.query(func.count(PropertyLoan.id)).filter(
            PropertyLoan.property_id == property_id
        ).scalar() or 0
        
        impact = {
            "transaction_count": transaction_count,
            "recurring_count": recurring_count,
            "loan_count": loan_count,
        }
        
        if not force:
            return {"deleted": False, "impact": impact}
        
        # Unlink transactions (SET NULL)
        if transaction_count > 0:
            self.db.query(Transaction).filter(
                Transaction.property_id == property_id
            ).update({"property_id": None}, synchronize_session="fetch")
        
        # Recurring transactions and loans cascade via DB ondelete,
        # but delete explicitly for clarity
        if recurring_count > 0:
            self.db.query(RecurringTransaction).filter(
                RecurringTransaction.property_id == property_id
            ).delete(synchronize_session="fetch")
        
        if loan_count > 0:
            self.db.query(PropertyLoan).filter(
                PropertyLoan.property_id == property_id
            ).delete(synchronize_session="fetch")
        
        self.db.delete(property)
        self.db.commit()
        
        # Invalidate portfolio and list caches
        self._invalidate_portfolio_cache(user_id)
        self._invalidate_property_list_cache(user_id)
        
        return {"deleted": True, "impact": impact}
    
    def link_transaction_to_property(
        self, 
        transaction_id: int, 
        property_id: UUID, 
        user_id: int
    ) -> Transaction:
        """
        Link transaction to property with validation.
        
        Args:
            transaction_id: ID of the transaction to link
            property_id: UUID of the property to link to
            user_id: ID of the user performing the operation
            
        Returns:
            Updated Transaction instance
            
        Raises:
            ValueError: If transaction or property not found, or do not belong to user
        """
        # Get transaction
        transaction = self.db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise ValueError(f"Transaction with id {transaction_id} not found")
        
        if transaction.user_id != user_id:
            raise ValueError(f"Transaction with id {transaction_id} not found")
        
        # Get property with ownership validation
        property = self._validate_ownership(property_id, user_id)
        
        # Link transaction to property
        transaction.property_id = property_id
        
        self.db.commit()
        self.db.refresh(transaction)
        
        # Invalidate metrics and portfolio caches
        self._invalidate_metrics_cache(property_id)
        self._invalidate_portfolio_cache(user_id)
        
        return transaction
    
    def unlink_transaction_from_property(
        self,
        transaction_id: int,
        user_id: int
    ) -> Transaction:
        """
        Unlink transaction from property (set property_id to None).
        
        Args:
            transaction_id: ID of the transaction to unlink
            user_id: ID of the user performing the operation
            
        Returns:
            Updated Transaction instance
            
        Raises:
            ValueError: If transaction not found or does not belong to user
        """
        # Get transaction
        transaction = self.db.query(Transaction).filter(
            Transaction.id == transaction_id
        ).first()
        
        if not transaction:
            raise ValueError(f"Transaction with id {transaction_id} not found")
        
        if transaction.user_id != user_id:
            raise ValueError(f"Transaction with id {transaction_id} not found")
        
        # Store property_id before unlinking for cache invalidation
        property_id = transaction.property_id
        
        # Unlink transaction from property
        transaction.property_id = None
        
        self.db.commit()
        self.db.refresh(transaction)
        
        # Invalidate metrics and portfolio caches if transaction was linked to a property
        if property_id:
            self._invalidate_metrics_cache(property_id)
            self._invalidate_portfolio_cache(user_id)
        
        return transaction
    
    def get_property_transactions(
        self, 
        property_id: UUID, 
        user_id: int, 
        year: Optional[int] = None
    ) -> List[Transaction]:
        """
        Get all transactions linked to property.
        
        Args:
            property_id: UUID of the property
            user_id: ID of the user requesting transactions
            year: Optional year filter
            
        Returns:
            List of Transaction instances
            
        Raises:
            ValueError: If property not found or does not belong to user
        """
        # Validate property ownership
        property = self._validate_ownership(property_id, user_id)
        
        # Query transactions
        query = self.db.query(Transaction).filter(
            Transaction.property_id == property_id
        )
        
        if year:
            query = query.filter(
                extract('year', Transaction.transaction_date) == year
            )
        
        # Order by date descending
        query = query.order_by(Transaction.transaction_date.desc())
        
        return query.all()
    
    def calculate_property_metrics(
        self, 
        property_id: UUID,
        user_id: int,
        year: Optional[int] = None
    ) -> PropertyMetrics:
        """
        Calculate property financial metrics with caching.
        
        Metrics calculated:
        - Total rental income
        - Total expenses by category
        - Net rental income
        - Accumulated depreciation
        - Remaining depreciable value
        - Annual depreciation (current year)
        - Years remaining until fully depreciated
        
        Cache TTL: 1 hour (3600 seconds)
        Cache invalidated on:
        - Property update
        - Transaction link/unlink
        - Transaction create/update/delete (handled by transaction service)
        
        Args:
            property_id: UUID of the property
            user_id: ID of the user requesting metrics
            year: Optional year filter (default: current year)
            
        Returns:
            PropertyMetrics instance
            
        Raises:
            ValueError: If property not found or does not belong to user
        """
        # Use current year if not specified
        if year is None:
            year = date.today().year
        
        # Try to get from cache (only for current year)
        if year == date.today().year:
            cached_metrics = self._get_cached_metrics(property_id)
            if cached_metrics:
                return cached_metrics
        
        # Validate property ownership
        property = self._validate_ownership(property_id, user_id)
        
        # Calculate accumulated depreciation (all time)
        accumulated_depreciation = self.afa_calculator.get_accumulated_depreciation(
            property_id
        )
        
        # Calculate depreciable value (considering rental percentage for mixed-use)
        depreciable_value = property.building_value
        if getattr(property, "asset_type", "real_estate") != "real_estate":
            depreciable_value = self.asset_lifecycle_service.get_depreciable_base(property)
        elif property.property_type == PropertyType.MIXED_USE:
            rental_pct = property.rental_percentage / Decimal("100")
            depreciable_value = depreciable_value * rental_pct
        
        # Calculate remaining depreciable value
        remaining_depreciable_value = max(
            depreciable_value - accumulated_depreciation,
            Decimal("0")
        )
        
        # Calculate annual depreciation for specified year (with warnings)
        self.afa_calculator.clear_warnings()  # Clear previous warnings
        annual_depreciation = self.afa_calculator.calculate_annual_depreciation(
            property, year
        )
        warnings = self.afa_calculator.get_warnings()  # Get warnings from calculation
        
        # Calculate years remaining (if depreciation is ongoing)
        years_remaining = None
        if getattr(property, "asset_type", "real_estate") != "real_estate":
            years_remaining = self.asset_lifecycle_service.estimate_years_remaining(
                property,
                year,
            )
        elif annual_depreciation > 0 and property.depreciation_rate > 0:
            years_remaining = (
                remaining_depreciable_value / (depreciable_value * property.depreciation_rate)
            ).quantize(Decimal("0.1"))
        
        # Calculate rental income for the year
        rental_income = self.db.query(func.sum(Transaction.amount)).filter(
            and_(
                Transaction.property_id == property_id,
                Transaction.type == TransactionType.INCOME,
                Transaction.income_category == IncomeCategory.RENTAL,
                extract('year', Transaction.transaction_date) == year
            )
        ).scalar() or Decimal("0")
        
        # Calculate expenses for the year
        total_expenses = self.db.query(func.sum(Transaction.amount)).filter(
            and_(
                Transaction.property_id == property_id,
                Transaction.type == TransactionType.EXPENSE,
                extract('year', Transaction.transaction_date) == year
            )
        ).scalar() or Decimal("0")
        
        # Calculate net rental income
        net_rental_income = rental_income - total_expenses
        
        metrics = PropertyMetrics(
            property_id=property_id,
            accumulated_depreciation=accumulated_depreciation,
            remaining_depreciable_value=remaining_depreciable_value,
            annual_depreciation=annual_depreciation,
            total_rental_income=rental_income,
            total_expenses=total_expenses,
            net_rental_income=net_rental_income,
            years_remaining=years_remaining,
            warnings=warnings  # Include tax validation warnings
        )
        
        # Cache metrics (only for current year)
        if year == date.today().year:
            self._set_cached_metrics(property_id, metrics)
        
        return metrics

    def compare_portfolio_properties(
        self,
        user_id: int,
        year: Optional[int] = None,
        sort_by: str = "net_income",
        sort_order: str = "desc"
    ) -> List[Dict[str, Any]]:
        """
        Compare performance across all user properties.

        Calculates and compares:
        - Rental income
        - Total expenses
        - Net income
        - Rental yield (net income / purchase price)
        - Expense ratio (expenses / rental income)
        - Depreciation amount

        Args:
            user_id: ID of the user
            year: Optional year filter (default: current year)
            sort_by: Field to sort by (net_income, rental_yield, expense_ratio)
            sort_order: Sort order (asc, desc)

        Returns:
            List of property comparison dictionaries
        """
        if year is None:
            year = date.today().year

        # Get all active properties for user
        properties = self.db.query(Property).filter(
            Property.user_id == user_id,
            Property.status == PropertyStatus.ACTIVE
        ).all()

        comparisons = []

        for property in properties:
            # Calculate metrics for this property
            metrics = self.calculate_property_metrics(property.id, user_id, year)

            # Calculate rental yield (net income / purchase price * 100)
            rental_yield = Decimal("0")
            if property.purchase_price > 0:
                rental_yield = (metrics.net_rental_income / property.purchase_price * Decimal("100"))

            # Calculate expense ratio (expenses / rental income * 100)
            expense_ratio = Decimal("0")
            if metrics.total_rental_income > 0:
                expense_ratio = (metrics.total_expenses / metrics.total_rental_income * Decimal("100"))

            comparison = {
                "property_id": str(property.id),
                "address": property.address,
                "property_type": property.property_type.value,
                "purchase_price": float(property.purchase_price),
                "rental_income": float(metrics.total_rental_income),
                "expenses": float(metrics.total_expenses),
                "net_income": float(metrics.net_rental_income),
                "rental_yield": float(rental_yield),
                "expense_ratio": float(expense_ratio),
                "depreciation": float(metrics.annual_depreciation),
                "accumulated_depreciation": float(metrics.accumulated_depreciation)
            }

            comparisons.append(comparison)

        # Sort comparisons
        reverse = (sort_order == "desc")

        if sort_by == "rental_yield":
            comparisons.sort(key=lambda x: x["rental_yield"], reverse=reverse)
        elif sort_by == "expense_ratio":
            comparisons.sort(key=lambda x: x["expense_ratio"], reverse=reverse)
        elif sort_by == "rental_income":
            comparisons.sort(key=lambda x: x["rental_income"], reverse=reverse)
        else:  # default: net_income
            comparisons.sort(key=lambda x: x["net_income"], reverse=reverse)

        # Log portfolio comparison
        logger.info(
            "Portfolio comparison generated",
            extra={
                "user_id": user_id,
                "year": year,
                "property_count": len(comparisons),
                "sort_by": sort_by,
                "sort_order": sort_order,
                "total_rental_income": sum(c["rental_income"] for c in comparisons),
                "total_net_income": sum(c["net_income"] for c in comparisons)
            }
        )

        return comparisons

    def bulk_generate_annual_depreciation(
        self,
        user_id: int,
        property_ids: List[UUID],
        year: int
    ) -> Dict[str, Any]:
        """
        Generate annual depreciation for multiple properties.

        Args:
            user_id: ID of the user
            property_ids: List of property UUIDs
            year: Tax year to generate depreciation for

        Returns:
            Dictionary with generation summary
        """
        from app.services.annual_depreciation_service import AnnualDepreciationService

        results = {
            "year": year,
            "requested_properties": len(property_ids),
            "successful": 0,
            "failed": 0,
            "skipped": 0,
            "transactions_created": [],
            "errors": []
        }

        annual_service = AnnualDepreciationService(self.db)

        for property_id in property_ids:
            try:
                # Validate ownership
                property = self._validate_ownership(property_id, user_id)

                # Generate depreciation for this property only
                result = annual_service.generate_annual_depreciation(year, user_id=user_id)

                if result.transactions_created > 0:
                    results["successful"] += 1
                    results["transactions_created"].extend([t.id for t in result.transactions])
                else:
                    results["skipped"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "property_id": str(property_id),
                    "error": str(e)
                })
                logger.error(
                    f"Bulk depreciation generation failed for property {property_id}: {e}",
                    exc_info=True
                )

        logger.info(
            "Bulk depreciation generation completed",
            extra={
                "user_id": user_id,
                "year": year,
                "requested": results["requested_properties"],
                "successful": results["successful"],
                "failed": results["failed"],
                "skipped": results["skipped"]
            }
        )

        return results

    def bulk_archive_properties(
        self,
        user_id: int,
        property_ids: List[UUID]
    ) -> Dict[str, Any]:
        """
        Archive multiple properties.

        Args:
            user_id: ID of the user
            property_ids: List of property UUIDs to archive

        Returns:
            Dictionary with archive summary
        """
        results = {
            "requested_properties": len(property_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }

        for property_id in property_ids:
            try:
                # Archive property (validates ownership internally)
                self.archive_property(property_id, user_id)
                results["successful"] += 1

            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "property_id": str(property_id),
                    "error": str(e)
                })
                logger.error(
                    f"Bulk archive failed for property {property_id}: {e}",
                    exc_info=True
                )

        logger.info(
            "Bulk archive completed",
            extra={
                "user_id": user_id,
                "requested": results["requested_properties"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )

        return results

    def bulk_link_transactions(
        self,
        user_id: int,
        property_id: UUID,
        transaction_ids: List[int]
    ) -> Dict[str, Any]:
        """
        Link multiple transactions to a property.

        Args:
            user_id: ID of the user
            property_id: UUID of the property
            transaction_ids: List of transaction IDs to link

        Returns:
            Dictionary with linking summary
        """
        results = {
            "property_id": str(property_id),
            "requested_transactions": len(transaction_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }

        for transaction_id in transaction_ids:
            try:
                # Link transaction (validates ownership internally)
                self.link_transaction_to_property(transaction_id, property_id, user_id)
                results["successful"] += 1

            except Exception as e:
                self.db.rollback()
                results["failed"] += 1
                results["errors"].append({
                    "transaction_id": transaction_id,
                    "error": str(e)
                })
                logger.error(
                    f"Bulk link failed for transaction {transaction_id}: {e}",
                    exc_info=True
                )

        logger.info(
            "Bulk transaction linking completed",
            extra={
                "user_id": user_id,
                "property_id": str(property_id),
                "requested": results["requested_transactions"],
                "successful": results["successful"],
                "failed": results["failed"]
            }
        )

        return results


def delete_user_property_data(self, user_id: int) -> dict:
    """
    Delete all property-related data for a user (GDPR compliance).

    This method implements the "right to be forgotten" under GDPR Article 17.
    It performs a cascade delete of:
    - All properties owned by the user
    - All property-linked transactions (depreciation, rental income, expenses)
    - All cached property data in Redis

    WARNING: This operation is irreversible. All property and transaction
    history will be permanently deleted.

    Args:
        user_id: ID of the user whose property data should be deleted

    Returns:
        Dictionary with deletion summary:
        {
            "user_id": int,
            "properties_deleted": int,
            "transactions_deleted": int,
            "cache_cleared": bool,
            "deleted_property_ids": List[str]
        }

    Raises:
        Exception: If deletion fails (transaction will be rolled back)
    """
    try:
        # Get all properties for the user
        properties = self.db.query(Property).filter(
            Property.user_id == user_id
        ).all()

        property_ids = [str(prop.id) for prop in properties]
        property_count = len(properties)

        # Count transactions that will be deleted
        transaction_count = self.db.query(func.count(Transaction.id)).filter(
            Transaction.property_id.in_([prop.id for prop in properties])
        ).scalar() or 0

        # Delete all transactions linked to user's properties
        # This includes depreciation, rental income, and expenses
        if property_ids:
            self.db.query(Transaction).filter(
                Transaction.property_id.in_([prop.id for prop in properties])
            ).delete(synchronize_session=False)

        # Delete all properties
        self.db.query(Property).filter(
            Property.user_id == user_id
        ).delete(synchronize_session=False)

        # Commit the database changes
        self.db.commit()

        # Clear all cached data for these properties
        cache_cleared = self._clear_user_property_cache(user_id, property_ids)

        logger.info(
            f"GDPR deletion completed for user {user_id}: "
            f"{property_count} properties, {transaction_count} transactions deleted"
        )

        return {
            "user_id": user_id,
            "properties_deleted": property_count,
            "transactions_deleted": transaction_count,
            "cache_cleared": cache_cleared,
            "deleted_property_ids": property_ids
        }

    except Exception as e:
        self.db.rollback()
        logger.error(f"GDPR deletion failed for user {user_id}: {e}")
        raise

def _clear_user_property_cache(self, user_id: int, property_ids: List[str]) -> bool:
    """
    Clear all cached property data for a user.

    Clears:
    - Individual property metrics
    - Property list cache
    - Portfolio metrics cache
    - Depreciation schedules

    Args:
        user_id: ID of the user
        property_ids: List of property UUIDs (as strings) to clear

    Returns:
        True if cache clearing succeeded, False if Redis unavailable
    """
    if not self._redis_client:
        return False

    try:
        # Clear individual property caches
        for property_id in property_ids:
            self._invalidate_metrics_cache(UUID(property_id))
            self._invalidate_depreciation_schedule_cache(UUID(property_id))

        # Clear user-level caches
        self._invalidate_property_list_cache(user_id)
        self._invalidate_portfolio_cache(user_id)

        return True

    except Exception as e:
        logger.warning(f"Failed to clear property cache for user {user_id}: {e}")
        return False

def get_user_property_data_summary(self, user_id: int) -> dict:
    """
    Get a summary of all property data stored for a user (GDPR transparency).

    This method implements the "right to access" under GDPR Article 15.
    It provides a summary of what data is stored without exposing sensitive details.

    Args:
        user_id: ID of the user

    Returns:
        Dictionary with data summary:
        {
            "user_id": int,
            "total_properties": int,
            "active_properties": int,
            "archived_properties": int,
            "total_transactions": int,
            "data_retention_info": dict
        }
    """
    # Count properties by status
    property_counts = self.db.query(
        Property.status,
        func.count(Property.id)
    ).filter(
        Property.user_id == user_id
    ).group_by(Property.status).all()

    status_counts = {status.value: count for status, count in property_counts}
    total_properties = sum(status_counts.values())

    # Count transactions linked to user's properties
    property_ids = self.db.query(Property.id).filter(
        Property.user_id == user_id
    ).subquery()

    transaction_count = self.db.query(func.count(Transaction.id)).filter(
        Transaction.property_id.in_(property_ids)
    ).scalar() or 0

    return {
        "user_id": user_id,
        "total_properties": total_properties,
        "active_properties": status_counts.get(PropertyStatus.ACTIVE.value, 0),
        "archived_properties": status_counts.get(PropertyStatus.ARCHIVED.value, 0),
        "sold_properties": status_counts.get(PropertyStatus.SOLD.value, 0),
        "total_transactions": transaction_count,
        "data_retention_info": {
            "retention_period": "Data retained while account is active",
            "deletion_policy": "All property data deleted upon account deletion request",
            "backup_retention": "Backups retained for 30 days after deletion",
            "legal_basis": "GDPR Article 6(1)(b) - Contract performance"
        }
    }


    def delete_user_property_data(self, user_id: int) -> dict:
        """
        Delete all property-related data for a user (GDPR compliance).
        
        This method implements the "right to be forgotten" under GDPR Article 17.
        It performs a cascade delete of:
        - All properties owned by the user
        - All property-linked transactions (depreciation, rental income, expenses)
        - All cached property data in Redis
        
        WARNING: This operation is irreversible. All property and transaction
        history will be permanently deleted.
        
        Args:
            user_id: ID of the user whose property data should be deleted
            
        Returns:
            Dictionary with deletion summary:
            {
                "user_id": int,
                "properties_deleted": int,
                "transactions_deleted": int,
                "cache_cleared": bool,
                "deleted_property_ids": List[str]
            }
            
        Raises:
            Exception: If deletion fails (transaction will be rolled back)
        """
        try:
            # Get all properties for the user
            properties = self.db.query(Property).filter(
                Property.user_id == user_id
            ).all()
            
            property_ids = [str(prop.id) for prop in properties]
            property_count = len(properties)
            
            # Count transactions that will be deleted
            transaction_count = self.db.query(func.count(Transaction.id)).filter(
                Transaction.property_id.in_([prop.id for prop in properties])
            ).scalar() or 0
            
            # Delete all transactions linked to user's properties
            # This includes depreciation, rental income, and expenses
            if property_ids:
                self.db.query(Transaction).filter(
                    Transaction.property_id.in_([prop.id for prop in properties])
                ).delete(synchronize_session=False)
            
            # Delete all properties
            self.db.query(Property).filter(
                Property.user_id == user_id
            ).delete(synchronize_session=False)
            
            # Commit the database changes
            self.db.commit()
            
            # Clear all cached data for these properties
            cache_cleared = self._clear_user_property_cache(user_id, property_ids)
            
            logger.info(
                f"GDPR deletion completed for user {user_id}: "
                f"{property_count} properties, {transaction_count} transactions deleted"
            )
            
            return {
                "user_id": user_id,
                "properties_deleted": property_count,
                "transactions_deleted": transaction_count,
                "cache_cleared": cache_cleared,
                "deleted_property_ids": property_ids
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"GDPR deletion failed for user {user_id}: {e}")
            raise
    
    def _clear_user_property_cache(self, user_id: int, property_ids: List[str]) -> bool:
        """
        Clear all cached property data for a user.
        
        Clears:
        - Individual property metrics
        - Property list cache
        - Portfolio metrics cache
        - Depreciation schedules
        
        Args:
            user_id: ID of the user
            property_ids: List of property UUIDs (as strings) to clear
            
        Returns:
            True if cache clearing succeeded, False if Redis unavailable
        """
        if not self._redis_client:
            return False
        
        try:
            # Clear individual property caches
            for property_id in property_ids:
                self._invalidate_metrics_cache(UUID(property_id))
                self._invalidate_depreciation_schedule_cache(UUID(property_id))
            
            # Clear user-level caches
            self._invalidate_property_list_cache(user_id)
            self._invalidate_portfolio_cache(user_id)
            
            return True
            
        except Exception as e:
            logger.warning(f"Failed to clear property cache for user {user_id}: {e}")
            return False
    
    def get_user_property_data_summary(self, user_id: int) -> dict:
        """
        Get a summary of all property data stored for a user (GDPR transparency).
        
        This method implements the "right to access" under GDPR Article 15.
        It provides a summary of what data is stored without exposing sensitive details.
        
        Args:
            user_id: ID of the user
            
        Returns:
            Dictionary with data summary:
            {
                "user_id": int,
                "total_properties": int,
                "active_properties": int,
                "archived_properties": int,
                "total_transactions": int,
                "data_retention_info": dict
            }
        """
        # Count properties by status
        property_counts = self.db.query(
            Property.status,
            func.count(Property.id)
        ).filter(
            Property.user_id == user_id
        ).group_by(Property.status).all()
        
        status_counts = {status.value: count for status, count in property_counts}
        total_properties = sum(status_counts.values())
        
        # Count transactions linked to user's properties
        property_ids = self.db.query(Property.id).filter(
            Property.user_id == user_id
        ).subquery()
        
        transaction_count = self.db.query(func.count(Transaction.id)).filter(
            Transaction.property_id.in_(property_ids)
        ).scalar() or 0
        
        return {
            "user_id": user_id,
            "total_properties": total_properties,
            "active_properties": status_counts.get(PropertyStatus.ACTIVE.value, 0),
            "archived_properties": status_counts.get(PropertyStatus.ARCHIVED.value, 0),
            "sold_properties": status_counts.get(PropertyStatus.SOLD.value, 0),
            "total_transactions": transaction_count,
            "data_retention_info": {
                "retention_period": "Data retained while account is active",
                "deletion_policy": "All property data deleted upon account deletion request",
                "backup_retention": "Backups retained for 30 days after deletion",
                "legal_basis": "GDPR Article 6(1)(b) - Contract performance"
            }
        }
