"""User model with encrypted fields"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Boolean, JSON, DateTime, Enum as SQLEnum, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class UserType(str, Enum):
    """User type enumeration"""
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"
    GMBH = "gmbh"


class User(Base):
    """User model with encrypted sensitive fields"""
    __tablename__ = "users"
    
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
    
    # User type
    user_type = Column(SQLEnum(UserType), nullable=False)
    
    # Family information (JSON)
    family_info = Column(JSON, default={})
    # Example: {"num_children": 2, "is_single_parent": false}
    
    # Commuting information (JSON)
    commuting_info = Column(JSON, default={})
    # Example: {"distance_km": 35, "public_transport_available": true}
    
    # Home office eligibility
    home_office_eligible = Column(Boolean, default=False)
    
    # Language setting
    language = Column(String(5), default="de")  # de, en, zh
    
    # Two-factor authentication
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(500))  # Encrypted
    
    # Disclaimer acceptance
    disclaimer_accepted_at = Column(DateTime, nullable=True)
    
    # Admin flag
    is_admin = Column(Boolean, nullable=False, default=False)
    
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
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, user_type={self.user_type})>"
