"""Document model for OCR storage"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, Text, Numeric, JSON, DateTime, ForeignKey, Enum as SQLEnum, Boolean
from sqlalchemy.orm import relationship
from app.db.base import Base


class DocumentType(str, Enum):
    """Document type enumeration"""
    PAYSLIP = "payslip"  # Wage slip
    RECEIPT = "receipt"  # Supermarket receipt
    INVOICE = "invoice"  # Purchase invoice
    PURCHASE_CONTRACT = "purchase_contract"  # Property purchase contract (Kaufvertrag)
    RENTAL_CONTRACT = "rental_contract"  # Rental contract (Mietvertrag)
    LOAN_CONTRACT = "loan_contract"  # Loan contract (Kreditvertrag)
    BANK_STATEMENT = "bank_statement"  # Bank statement
    PROPERTY_TAX = "property_tax"  # Property tax bill
    LOHNZETTEL = "lohnzettel"  # Wage tax card
    SVS_NOTICE = "svs_notice"  # SVS contribution notice
    EINKOMMENSTEUERBESCHEID = "einkommensteuerbescheid"  # Annual income tax assessment
    E1_FORM = "e1_form"  # E1 tax declaration form
    L1_FORM = "l1_form"  # L1 employee tax return form
    L1K_BEILAGE = "l1k_beilage"  # L1k child supplement form
    L1AB_BEILAGE = "l1ab_beilage"  # L1ab deductions supplement form
    E1A_BEILAGE = "e1a_beilage"  # E1a self-employment income supplement
    E1B_BEILAGE = "e1b_beilage"  # E1b rental income supplement
    E1KV_BEILAGE = "e1kv_beilage"  # E1kv capital gains supplement
    U1_FORM = "u1_form"  # U1 annual VAT declaration
    U30_FORM = "u30_form"  # U30 VAT advance return (UVA)
    JAHRESABSCHLUSS = "jahresabschluss"  # Annual financial statement
    SPENDENBESTAETIGUNG = "spendenbestaetigung"  # Donation confirmation (Spendenbestätigung)
    VERSICHERUNGSBESTAETIGUNG = "versicherungsbestaetigung"  # Insurance confirmation
    KINDERBETREUUNGSKOSTEN = "kinderbetreuungskosten"  # Childcare cost receipt
    FORTBILDUNGSKOSTEN = "fortbildungskosten"  # Continuing education cost receipt
    PENDLERPAUSCHALE = "pendlerpauschale"  # Commuter allowance confirmation
    KIRCHENBEITRAG = "kirchenbeitrag"  # Church tax confirmation
    GRUNDBUCHAUSZUG = "grundbuchauszug"  # Land registry extract
    BETRIEBSKOSTENABRECHNUNG = "betriebskostenabrechnung"  # Operating cost statement
    GEWERBESCHEIN = "gewerbeschein"  # Trade license
    KONTOAUSZUG = "kontoauszug"  # Bank account statement (Kontoauszug)
    OTHER = "other"


class Document(Base):
    """Document model for storing uploaded documents and OCR results"""
    __tablename__ = "documents"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # Document type
    document_type = Column(SQLEnum(DocumentType), nullable=False, index=True)
    
    # File storage information
    file_path = Column(String(500), nullable=False)  # S3/MinIO path
    file_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=True, index=True)  # SHA-256 of uploaded file bytes
    file_size = Column(Integer, nullable=True)  # Size in bytes
    mime_type = Column(String(100), nullable=True)
    
    # OCR results
    ocr_result = Column(JSON, nullable=True)  # Structured extracted data
    raw_text = Column(Text, nullable=True)  # Raw OCR text
    confidence_score = Column(Numeric(3, 2), nullable=True)  # 0.00 to 1.00
    
    # Foreign key to transaction (optional, set after transaction is created)
    transaction_id = Column(Integer, ForeignKey("transactions.id"), nullable=True)
    
    # Parent document (for multi-form PDF splitting)
    parent_document_id = Column(Integer, ForeignKey("documents.id"), nullable=True, index=True)

    # Archival status
    is_archived = Column(Boolean, default=False, nullable=False)
    archived_at = Column(DateTime, nullable=True)
    
    # Timestamps
    uploaded_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)  # When OCR was completed
    
    # Relationships
    user = relationship("User", back_populates="documents")
    # No direct relationship to Transaction - use transaction_id foreign key directly if needed
    
    def __repr__(self):
        return f"<Document(id={self.id}, type={self.document_type}, file_name={self.file_name})>"
