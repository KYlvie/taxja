"""Tax form PDF template model — stores official BMF form templates per year.

Each row holds one blank PDF form (e.g., E1 2025) as a binary blob,
plus a field_mapping JSON that maps our Kennzahl numbers to the
AcroForm field names inside the PDF.

Templates are uploaded once per year via admin API and used by
the PDF filling service to produce pre-filled tax returns.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, LargeBinary, JSON, DateTime,
    UniqueConstraint, Enum as SQLEnum,
)
from enum import Enum as PyEnum

from app.db.base import Base


class TaxFormType(str, PyEnum):
    """Supported Austrian tax form types."""
    E1 = "E1"          # Einkommensteuererklärung
    E1A = "E1a"        # Beilage Einzelunternehmer
    E1B = "E1b"        # Beilage Vermietung (per property)
    L1 = "L1"          # Arbeitnehmerveranlagung
    L1K = "L1k"        # Beilage Kinder
    K1 = "K1"          # Beilage Kapitalerträge
    U1 = "U1"          # Umsatzsteuerjahreserklärung
    UVA = "UVA"        # Umsatzsteuervoranmeldung


class TaxFormTemplate(Base):
    """Stores official BMF PDF form templates per tax year.

    Usage:
        1. Admin uploads blank PDF from FinanzOnline
        2. Admin provides field_mapping (KZ → PDF AcroForm field name)
        3. PDF filling service reads template + mapping to produce filled PDF
    """
    __tablename__ = "tax_form_templates"
    __table_args__ = (
        UniqueConstraint("tax_year", "form_type", name="uq_tax_form_template_year_type"),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Which form and which year
    tax_year = Column(Integer, nullable=False, index=True)
    form_type = Column(SQLEnum(TaxFormType), nullable=False)

    # Human-readable label, e.g. "Einkommensteuererklärung 2025 (E1)"
    display_name = Column(String(200), nullable=True)

    # The blank PDF template as binary blob
    # Typical size: 100–500 KB per form → 5 years × 8 forms ≈ 20 MB total
    pdf_template = Column(LargeBinary, nullable=False)

    # Maps our internal KZ numbers → AcroForm field names in the PDF
    # Example:
    # {
    #   "245": "Kz245",           -- direct name match
    #   "220": "FamBon_Voll",     -- arbitrary PDF field name
    #   "9040": "EA_Einnahmen",
    # }
    # The PDF filler iterates our form_service output fields[].kz
    # and looks up the AcroForm target name here.
    field_mapping = Column(JSON, nullable=False, default=dict)

    # Metadata
    original_filename = Column(String(255), nullable=True)  # e.g. "E1_2025.pdf"
    file_size_bytes = Column(Integer, nullable=True)
    page_count = Column(Integer, nullable=True)

    # Source tracking
    source_url = Column(String(500), nullable=True)  # BMF download URL for reference
    bmf_version = Column(String(50), nullable=True)   # e.g. "E1-2025-v2"

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<TaxFormTemplate({self.form_type.value} {self.tax_year}, {self.file_size_bytes or 0} bytes)>"
