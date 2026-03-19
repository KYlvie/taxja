"""Property model for rental property asset management"""
from datetime import datetime
from enum import Enum
from uuid import uuid4
from typing import Optional
from sqlalchemy import Column, Integer, String, Boolean, Date, Numeric, DateTime, ForeignKey, Enum as SQLEnum, CheckConstraint, text
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base
from app.core.encryption import get_encryption


class PropertyType(str, Enum):
    """Property type enumeration"""
    RENTAL = "rental"
    OWNER_OCCUPIED = "owner_occupied"
    MIXED_USE = "mixed_use"


class BuildingUse(str, Enum):
    """Building usage type for AfA rate determination (§8 Abs 1 EStG).

    - RESIDENTIAL (Wohngebäude): 1.5% AfA
    - COMMERCIAL (Betriebsgebäude): 2.5% AfA — offices, retail, warehouses, clinics, etc.
    """
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"


class PropertyStatus(str, Enum):
    """Property status enumeration"""
    ACTIVE = "active"
    SOLD = "sold"
    ARCHIVED = "archived"


class Property(Base):
    """Property model for tracking rental properties and depreciation"""
    __tablename__ = "properties"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid4)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Property classification
    asset_type = Column(String(50), nullable=False, default="real_estate", index=True)
    sub_category = Column(String(100), nullable=True)
    name = Column(String(255), nullable=True)
    property_type = Column(SQLEnum(PropertyType, values_callable=lambda x: [e.value for e in x]), nullable=False, default=PropertyType.RENTAL)
    rental_percentage = Column(
        Numeric(5, 2), 
        default=100.00,
        nullable=False,
        info={"check": "rental_percentage >= 0 AND rental_percentage <= 100"}
    )
    
    # Business use and depreciation tracking
    useful_life_years = Column(Integer, nullable=True)
    business_use_percentage = Column(Numeric(5, 2), default=100.00, nullable=False)
    supplier = Column(String(255), nullable=True)
    accumulated_depreciation = Column(Numeric(12, 2), default=0, nullable=False)
    acquisition_kind = Column(String(30), nullable=True)
    put_into_use_date = Column(Date, nullable=True)
    is_used_asset = Column(Boolean, default=False, nullable=False)
    first_registration_date = Column(Date, nullable=True)
    prior_owner_usage_years = Column(Numeric(5, 2), nullable=True)
    comparison_basis = Column(String(10), nullable=True)
    comparison_amount = Column(Numeric(12, 2), nullable=True)
    gwg_eligible = Column(Boolean, default=False, nullable=False)
    gwg_elected = Column(Boolean, default=False, nullable=False)
    depreciation_method = Column(String(20), nullable=True, default="linear")
    degressive_afa_rate = Column(Numeric(5, 4), nullable=True)
    useful_life_source = Column(String(50), nullable=True)
    income_tax_cost_cap = Column(Numeric(12, 2), nullable=True)
    income_tax_depreciable_base = Column(Numeric(12, 2), nullable=True)
    vat_recoverable_status = Column(String(20), nullable=True)
    ifb_candidate = Column(Boolean, default=False, nullable=False)
    ifb_rate = Column(Numeric(5, 4), nullable=True)
    ifb_rate_source = Column(String(50), nullable=True)
    recognition_decision = Column(String(50), nullable=True)
    policy_confidence = Column(Numeric(5, 4), nullable=True)
    
    # Address fields (encrypted)
    _address = Column("address", String(1000), nullable=False)
    _street = Column("street", String(500), nullable=False)
    _city = Column("city", String(200), nullable=False)
    postal_code = Column(String(10), nullable=False)
    
    # Purchase information
    purchase_date = Column(Date, nullable=False)
    purchase_price = Column(
        Numeric(12, 2), 
        nullable=False,
        info={"check": "purchase_price > 0 AND purchase_price <= 100000000"}
    )
    building_value = Column(
        Numeric(12, 2), 
        nullable=False,
        info={"check": "building_value > 0 AND building_value <= purchase_price"}
    )
    # land_value is calculated as purchase_price - building_value
    # Note: PostgreSQL computed columns require special syntax, so we calculate this in the application layer
    land_value = Column(Numeric(12, 2), nullable=True)
    
    # Purchase costs (for owner-occupied tracking and capital gains calculations)
    grunderwerbsteuer = Column(Numeric(12, 2), nullable=True)  # Property transfer tax
    notary_fees = Column(Numeric(12, 2), nullable=True)
    registry_fees = Column(Numeric(12, 2), nullable=True)  # Eintragungsgebühr
    
    # Building details
    construction_year = Column(
        Integer, 
        nullable=True,
        info={"check": "construction_year >= 1800 AND construction_year <= EXTRACT(YEAR FROM CURRENT_DATE)"}
    )
    # Building usage type for AfA rate (§8 Abs 1 EStG)
    # residential = Wohngebäude (1.5%), commercial = Betriebsgebäude (2.5%)
    building_use = Column(
        SQLEnum(BuildingUse, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=BuildingUse.RESIDENTIAL,
    )
    # Eco/klimaaktiv standard — enables extended 3× AfA for years 1-3
    # Only for new residential buildings completed 2024-2026 (BMF erweiterte beschleunigte AfA)
    eco_standard = Column(Boolean, default=False, nullable=False)

    depreciation_rate = Column(
        Numeric(5, 4),
        nullable=False,
        default=0.015,  # 1.5% — residential buildings (Wohngebäude) since 2016 reform
        info={"check": "depreciation_rate >= 0.001 AND depreciation_rate <= 1.00"}
    )
    
    # Status
    status = Column(SQLEnum(PropertyStatus, values_callable=lambda x: [e.value for e in x]), nullable=False, default=PropertyStatus.ACTIVE, index=True)
    sale_date = Column(Date, nullable=True)
    sale_price = Column(Numeric(12, 2), nullable=True)  # ImmoESt: Veräußerungserlös

    # ImmoESt exemption flags
    hauptwohnsitz = Column(Boolean, default=False, nullable=False)  # §30 Abs 2 Z 1 EStG
    selbst_errichtet = Column(Boolean, default=False, nullable=False)  # Herstellerbefreiung §30 Abs 2 Z 2
    
    # Document references
    kaufvertrag_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    mietvertrag_document_id = Column(Integer, ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Table constraints
    __table_args__ = (
        CheckConstraint(
            "rental_percentage >= 0 AND rental_percentage <= 100",
            name="check_rental_percentage_range"
        ),
        CheckConstraint(
            "purchase_price > 0 AND purchase_price <= 100000000",
            name="check_purchase_price_range"
        ),
        CheckConstraint(
            "building_value > 0 AND building_value <= purchase_price",
            name="check_building_value_range"
        ),
        CheckConstraint(
            "depreciation_rate >= 0.001 AND depreciation_rate <= 1.00",
            name="check_depreciation_rate_range"
        ),
        # Note: construction_year check uses EXTRACT which is PostgreSQL-specific
        # For SQLite testing, this constraint is validated at application level
        CheckConstraint(
            "construction_year IS NULL OR construction_year >= 1800",
            name="check_construction_year_min"
        ),
        CheckConstraint(
            "sale_date IS NULL OR sale_date >= purchase_date",
            name="check_sale_date_after_purchase"
        ),
        CheckConstraint(
            "status != 'sold' OR sale_date IS NOT NULL",
            name="check_sold_has_sale_date"
        ),
    )
    
    # Relationships
    user = relationship("User", back_populates="properties")
    transactions = relationship("Transaction", back_populates="property", foreign_keys="Transaction.property_id")
    loans = relationship("PropertyLoan", back_populates="property", cascade="all, delete-orphan")
    policy_snapshots = relationship("AssetPolicySnapshot", back_populates="property", cascade="all, delete-orphan")
    asset_events = relationship("AssetEvent", back_populates="property", cascade="all, delete-orphan")
    
    # Hybrid properties for encrypted fields
    @hybrid_property
    def address(self) -> Optional[str]:
        """Decrypt address field"""
        if self._address and isinstance(self._address, str):
            return get_encryption().decrypt_field(self._address)
        return None
    
    @address.setter
    def address(self, value: Optional[str]) -> None:
        """Encrypt address field"""
        if value:
            self._address = get_encryption().encrypt_field(value)
        else:
            self._address = None
    
    @hybrid_property
    def street(self) -> Optional[str]:
        """Decrypt street field"""
        if self._street and isinstance(self._street, str):
            return get_encryption().decrypt_field(self._street)
        return None
    
    @street.setter
    def street(self, value: Optional[str]) -> None:
        """Encrypt street field"""
        if value:
            self._street = get_encryption().encrypt_field(value)
        else:
            self._street = None
    
    @hybrid_property
    def city(self) -> Optional[str]:
        """Decrypt city field"""
        if self._city and isinstance(self._city, str):
            return get_encryption().decrypt_field(self._city)
        return None
    
    @city.setter
    def city(self, value: Optional[str]) -> None:
        """Encrypt city field"""
        if value:
            self._city = get_encryption().encrypt_field(value)
        else:
            self._city = None
    
    def __repr__(self):
        return f"<Property(id={self.id}, address={self.address}, status={self.status})>"
