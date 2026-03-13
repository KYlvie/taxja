"""Historical import models for document import sessions and uploads"""
from datetime import datetime
from enum import Enum
from uuid import uuid4
from sqlalchemy import Column, Integer, String, Text, Numeric, JSON, DateTime, ForeignKey, Enum as SQLEnum, Boolean, ARRAY, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.db.base import Base


class HistoricalDocumentType(str, Enum):
    """Historical document type enumeration"""
    E1_FORM = "e1_form"
    BESCHEID = "bescheid"
    KAUFVERTRAG = "kaufvertrag"
    SALDENLISTE = "saldenliste"


class ImportStatus(str, Enum):
    """Import status enumeration"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_REQUIRED = "review_required"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"


class ImportSessionStatus(str, Enum):
    """Import session status enumeration"""
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class HistoricalImportSession(Base):
    """Historical import session for multi-document imports"""
    __tablename__ = "historical_import_sessions"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid4)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Session status
    status = Column(SQLEnum(ImportSessionStatus), nullable=False, default=ImportSessionStatus.ACTIVE, index=True)
    
    # Tax years covered by this session
    tax_years = Column(ARRAY(Integer), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Summary metrics
    total_documents = Column(Integer, default=0, nullable=False)
    successful_imports = Column(Integer, default=0, nullable=False)
    failed_imports = Column(Integer, default=0, nullable=False)
    transactions_created = Column(Integer, default=0, nullable=False)
    properties_created = Column(Integer, default=0, nullable=False)
    properties_linked = Column(Integer, default=0, nullable=False)
    
    # Relationships
    uploads = relationship("HistoricalImportUpload", back_populates="session", cascade="all, delete-orphan")
    conflicts = relationship("ImportConflict", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<HistoricalImportSession(id={self.id}, user_id={self.user_id}, status={self.status})>"


class HistoricalImportUpload(Base):
    """Historical import upload for individual document processing"""
    __tablename__ = "historical_import_uploads"
    
    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"), default=uuid4)
    
    # Foreign keys
    session_id = Column(UUID(as_uuid=True), ForeignKey("historical_import_sessions.id", ondelete="CASCADE"), nullable=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Document classification
    document_type = Column(SQLEnum(HistoricalDocumentType), nullable=False, index=True)
    tax_year = Column(Integer, nullable=False, index=True)
    
    # Processing status
    status = Column(SQLEnum(ImportStatus), nullable=False, default=ImportStatus.UPLOADED, index=True)
    ocr_task_id = Column(String(255), nullable=True)
    extraction_confidence = Column(Numeric(3, 2), nullable=True)
    
    # Extracted data (JSONB for flexibility)
    extracted_data = Column(JSONB, nullable=True)
    edited_data = Column(JSONB, nullable=True)
    
    # Import results
    transactions_created = Column(ARRAY(Integer), default=[], nullable=False)
    properties_created = Column(ARRAY(UUID(as_uuid=True)), default=[], nullable=False)
    properties_linked = Column(ARRAY(UUID(as_uuid=True)), default=[], nullable=False)
    
    # Review and approval
    requires_review = Column(Boolean, default=False, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approval_notes = Column(Text, nullable=True)
    
    # Error tracking
    errors = Column(JSONB, default=[], nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    session = relationship("HistoricalImportSession", back_populates="uploads")
    document = relationship("Document")
    metrics = relationship("ImportMetrics", back_populates="upload", cascade="all, delete-orphan", uselist=False)
    
    def __repr__(self):
        return f"<HistoricalImportUpload(id={self.id}, document_type={self.document_type}, status={self.status})>"


class ImportConflict(Base):
    """Import conflict tracking for data reconciliation"""
    __tablename__ = "import_conflicts"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign keys
    session_id = Column(UUID(as_uuid=True), ForeignKey("historical_import_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    upload_id_1 = Column(UUID(as_uuid=True), ForeignKey("historical_import_uploads.id", ondelete="CASCADE"), nullable=False)
    upload_id_2 = Column(UUID(as_uuid=True), ForeignKey("historical_import_uploads.id", ondelete="CASCADE"), nullable=False)
    
    # Conflict details
    conflict_type = Column(String(100), nullable=False)
    field_name = Column(String(255), nullable=False)
    value_1 = Column(String(500), nullable=True)
    value_2 = Column(String(500), nullable=True)
    
    # Resolution
    resolution = Column(String(100), nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    session = relationship("HistoricalImportSession", back_populates="conflicts")
    
    def __repr__(self):
        return f"<ImportConflict(id={self.id}, type={self.conflict_type}, resolved={self.resolution is not None})>"


class ImportMetrics(Base):
    """Import metrics for quality tracking and ML training"""
    __tablename__ = "import_metrics"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key
    upload_id = Column(UUID(as_uuid=True), ForeignKey("historical_import_uploads.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    
    # Document classification
    document_type = Column(SQLEnum(HistoricalDocumentType), nullable=False, index=True)
    
    # Extraction metrics
    extraction_confidence = Column(Numeric(3, 2), nullable=False)
    fields_extracted = Column(Integer, nullable=False)
    fields_total = Column(Integer, nullable=False)
    extraction_time_ms = Column(Integer, nullable=False)
    
    # Field-level accuracy (for ML training)
    field_accuracies = Column(JSONB, default={}, nullable=False)
    
    # User corrections
    fields_corrected = Column(Integer, default=0, nullable=False)
    corrections = Column(JSONB, default=[], nullable=False)
    
    # Timestamp
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    upload = relationship("HistoricalImportUpload", back_populates="metrics")
    
    def __repr__(self):
        return f"<ImportMetrics(id={self.id}, document_type={self.document_type}, confidence={self.extraction_confidence})>"
