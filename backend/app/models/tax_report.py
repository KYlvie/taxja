"""Tax report model for generated reports"""
from datetime import datetime
from decimal import Decimal
from sqlalchemy import Column, Integer, String, Numeric, JSON, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class TaxReport(Base):
    """Tax report model for storing generated tax reports"""
    __tablename__ = "tax_reports"
    
    # Primary key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign key to user
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Tax year
    tax_year = Column(Integer, nullable=False, index=True)
    
    # Income summary
    income_summary = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "employment": 45000.00,
    #   "rental": 12000.00,
    #   "self_employment": 30000.00,
    #   "capital_gains": 5000.00,
    #   "total": 92000.00
    # }
    
    # Expense summary
    expense_summary = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "deductible": 15000.00,
    #   "non_deductible": 5000.00,
    #   "total": 20000.00,
    #   "by_category": {
    #     "office_supplies": 2000.00,
    #     "equipment": 5000.00,
    #     ...
    #   }
    # }
    
    # Tax calculation
    tax_calculation = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "gross_income": 92000.00,
    #   "deductible_expenses": 15000.00,
    #   "deductions": 10856.80,
    #   "taxable_income": 66143.20,
    #   "income_tax": 18500.00,
    #   "vat": 2400.00,
    #   "svs": 8500.00,
    #   "total_tax": 29400.00,
    #   "breakdown": [
    #     {"bracket": "€0 - €13,539", "rate": "0%", "taxable_amount": 13539.00, "tax_amount": 0.00},
    #     {"bracket": "€13,539 - €21,992", "rate": "20%", "taxable_amount": 8453.00, "tax_amount": 1690.60},
    #     ...
    #   ]
    # }
    
    # Deductions
    deductions = Column(JSON, nullable=False)
    # Example structure:
    # {
    #   "svs_contributions": 8500.00,
    #   "commuting_allowance": 1356.00,
    #   "home_office": 300.00,
    #   "family_deductions": 700.80,
    #   "total": 10856.80
    # }
    
    # Net income (after all taxes and deductions)
    net_income = Column(Numeric(12, 2), nullable=False)
    
    # Report files
    pdf_file_path = Column(String(500), nullable=True)  # Path to generated PDF
    xml_file_path = Column(String(500), nullable=True)  # Path to FinanzOnline XML
    
    # Timestamps
    generated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="tax_reports")
    
    def __repr__(self):
        return f"<TaxReport(id={self.id}, user_id={self.user_id}, year={self.tax_year}, net_income={self.net_income})>"
