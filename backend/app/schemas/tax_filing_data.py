"""Pydantic schemas for TaxFilingData"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class TaxFilingDataCreate(BaseModel):
    tax_year: int
    data_type: str
    source_document_id: Optional[int] = None
    data: Dict[str, Any]


class TaxFilingDataResponse(BaseModel):
    id: int
    user_id: int
    tax_year: int
    data_type: str
    source_document_id: Optional[int] = None
    data: Dict[str, Any]
    status: str
    created_at: datetime
    confirmed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TaxFilingDataList(BaseModel):
    items: List[TaxFilingDataResponse]
    total: int
