"""User model with encrypted fields"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Enum as SQLEnum, ForeignKey, Numeric
from sqlalchemy.orm import relationship
from app.db.base import Base


def _enum_values(enum_cls):
    """Persist enum.value strings instead of Python enum member names."""
    return [member.value for member in enum_cls]


class UserType(str, Enum):
    """User type enumeration"""
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"
    GMBH = "gmbh"


class SelfEmployedType(str, Enum):
    """Self-employed sub-type per Austrian EStG.

    Determines which expenses are deductible and which Pauschalierung rate applies.
    Only relevant when user_type is SELF_EMPLOYED or MIXED.
    """
    FREIBERUFLER = "freiberufler"          # §22 EStG: doctors, lawyers, accountants, IT consultants, architects, artists
    GEWERBETREIBENDE = "gewerbetreibende"  # §23 EStG: trade, crafts, retail, restaurants, e-commerce, delivery
    NEUE_SELBSTAENDIGE = "neue_selbstaendige"  # Trainers, coaches, content creators, freelance non-§22
    LAND_FORSTWIRTSCHAFT = "land_forstwirtschaft"  # §21 EStG: agriculture and forestry


class VatStatus(str, Enum):
    """Persisted VAT handling mode for asset/tax automation."""
    REGELBESTEUERT = "regelbesteuert"
    KLEINUNTERNEHMER = "kleinunternehmer"
    PAUSCHALIERT = "pauschaliert"
    UNKNOWN = "unknown"


class Gewinnermittlungsart(str, Enum):
    """Persisted profit determination method for asset/tax automation."""
    BILANZIERUNG = "bilanzierung"
    EA_RECHNUNG = "ea_rechnung"
    PAUSCHAL = "pauschal"
    UNKNOWN = "unknown"


class User(Base):
    """User model with encrypted sensitive fields"""
    __tablename__ = "users"

    def __init__(self, **kwargs):
        # Backwards compatibility for older seeds/tests that still construct
        # User(hashed_password=...) while the persisted column is password_hash.
        if "hashed_password" in kwargs and "password_hash" not in kwargs:
            kwargs["password_hash"] = kwargs.pop("hashed_password")
        if "full_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs.pop("full_name")
        if "is_active" in kwargs and "account_status" not in kwargs:
            is_active = kwargs.pop("is_active")
            kwargs["account_status"] = "active" if is_active else "inactive"
        if "user_type" not in kwargs:
            kwargs["user_type"] = UserType.EMPLOYEE

        cls_ = type(self)
        for key, value in kwargs.items():
            if not hasattr(cls_, key):
                raise TypeError(
                    f"{key!r} is an invalid keyword argument for {cls_.__name__}"
                )
            setattr(self, key, value)
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Authentication
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Basic information
    name = Column(String(255), nullable=False)
    
    # Encrypted sensitive fields (stored as encrypted strings)
    tax_number = Column(String(500))  # Steuernummer (encrypted)
    vat_number = Column(String(500))  # UID (encrypted)
    address = Column(String(1000))  # Address (encrypted)
    vat_status = Column(
        SQLEnum(VatStatus, name="vatstatus", values_callable=_enum_values),
        nullable=True,
    )
    gewinnermittlungsart = Column(
        SQLEnum(
            Gewinnermittlungsart,
            name="gewinnermittlungsart",
            values_callable=_enum_values,
        ),
        nullable=True,
    )
    
    # User type
    user_type = Column(SQLEnum(UserType), nullable=False)

    # Self-employed sub-type (only relevant for self_employed / mixed)
    business_type = Column(String(50), nullable=True)

    # Business/company name for self-employed users (Firmenname / Unternehmensbezeichnung)
    business_name = Column(String(255), nullable=True)

    # Specific industry within the business_type (e.g., "gastronomie", "kosmetik", "hotel")
    # Used for industry-specific expense deductibility rules
    business_industry = Column(String(50), nullable=True)

    # Employer-light profile:
    # controls reminders/detection strategy, not monthly payroll facts
    employer_mode = Column(String(20), nullable=False, default="none")
    employer_region = Column(String(100), nullable=True)
    
    # Family information (JSON)
    family_info = Column(JSON, default={})
    # Example: {"num_children": 2, "is_single_parent": false}
    
    # Commuting information (JSON)
    commuting_info = Column(JSON, default={})
    # Example: {"distance_km": 35, "public_transport_available": true}
    
    # Home office / Telearbeit
    home_office_eligible = Column(Boolean, default=False)
    telearbeit_days = Column(Integer, nullable=True, default=None)  # None=legacy/unknown, 0=explicit zero
    employer_telearbeit_pauschale = Column(Numeric(10, 2), nullable=True, default=None)  # AG tax-free payment
    
    # Language setting
    language = Column(String(5), default="de")  # de, en, zh
    
    # Two-factor authentication
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(500))  # Encrypted
    
    # Email verification
    email_verified = Column(Boolean, nullable=False, default=False)
    email_verification_token = Column(String(255), nullable=True, index=True)
    email_verification_sent_at = Column(DateTime, nullable=True)

    # Password reset
    password_reset_token = Column(String(255), nullable=True, index=True)
    password_reset_sent_at = Column(DateTime, nullable=True)

    # Disclaimer acceptance
    disclaimer_accepted_at = Column(DateTime, nullable=True)
    
    # Admin flag
    is_admin = Column(Boolean, nullable=False, default=False)
    
    # Account cancellation fields
    account_status = Column(String(20), nullable=False, default="active", index=True)
    deactivated_at = Column(DateTime, nullable=True)
    scheduled_deletion_at = Column(DateTime, nullable=True)
    deletion_retry_count = Column(Integer, nullable=False, default=0)
    cancellation_reason = Column(String(500), nullable=True)
    bao_retention_expiry = Column(DateTime, nullable=True)  # BAO §132: 7-year retention expiry

    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Subscription fields (added by migration 010)
    subscription_id = Column(Integer, ForeignKey("subscriptions.id", ondelete="SET NULL"), nullable=True, index=True)
    trial_used = Column(Boolean, nullable=False, default=False)
    trial_end_date = Column(DateTime, nullable=True, index=True)
    
    # Relationships
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="user", cascade="all, delete-orphan")
    tax_reports = relationship("TaxReport", back_populates="user", cascade="all, delete-orphan")
    loss_carryforwards = relationship("LossCarryforward", back_populates="user", cascade="all, delete-orphan")
    corrections = relationship("ClassificationCorrection", back_populates="user", cascade="all, delete-orphan")
    chat_messages = relationship("ChatMessage", back_populates="user", cascade="all, delete-orphan")
    properties = relationship("Property", back_populates="user", cascade="all, delete-orphan")
    property_loans = relationship("PropertyLoan", back_populates="user", cascade="all, delete-orphan")
    recurring_transactions = relationship("RecurringTransaction", back_populates="user", cascade="all, delete-orphan")
    notifications = relationship("Notification", back_populates="user", cascade="all, delete-orphan")
    subscription = relationship("Subscription", back_populates="user", foreign_keys="[Subscription.user_id]", uselist=False)
    usage_records = relationship("UsageRecord", back_populates="user", cascade="all, delete-orphan")
    payment_events = relationship("PaymentEvent", back_populates="user", cascade="all, delete-orphan")
    classification_rules = relationship("UserClassificationRule", back_populates="user", cascade="all, delete-orphan")
    employer_months = relationship("EmployerMonth", back_populates="user", cascade="all, delete-orphan")
    employer_annual_archives = relationship("EmployerAnnualArchive", back_populates="user", cascade="all, delete-orphan")
    asset_policy_snapshots = relationship("AssetPolicySnapshot", back_populates="user", cascade="all, delete-orphan")
    asset_events = relationship("AssetEvent", back_populates="user", cascade="all, delete-orphan")
    credit_balance = relationship("CreditBalance", back_populates="user", uselist=False, cascade="all, delete-orphan")
    credit_ledger = relationship("CreditLedger", back_populates="user", cascade="all, delete-orphan")
    topup_purchases = relationship("TopupPurchase", back_populates="user", cascade="all, delete-orphan")

    @property
    def hashed_password(self):
        return self.password_hash

    @hashed_password.setter
    def hashed_password(self, value):
        self.password_hash = value

    @property
    def full_name(self):
        return self.name

    @full_name.setter
    def full_name(self, value):
        self.name = value

    @property
    def is_active(self):
        return self.account_status == "active"

    @is_active.setter
    def is_active(self, value):
        self.account_status = "active" if value else "inactive"
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, user_type={self.user_type})>"

