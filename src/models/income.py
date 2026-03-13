from enum import Enum
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class IncomeType(str, Enum):
    """收入类型"""
    EMPLOYMENT = "employment"  # 职员工资
    RENTAL = "rental"  # 租赁收入
    SELF_EMPLOYED = "self_employed"  # 个体户


class Income(BaseModel):
    """收入基础模型"""
    id: Optional[str] = None
    income_type: IncomeType
    amount: float = Field(gt=0, description="金额（欧元）")
    date: date
    description: str
    category: Optional[str] = None


class EmploymentIncome(Income):
    """职员工资收入"""
    income_type: IncomeType = IncomeType.EMPLOYMENT
    employer: str
    gross_salary: float
    wage_tax_withheld: float = 0  # 已扣工资税
    social_security_withheld: float = 0  # 已扣社保


class RentalIncome(Income):
    """租赁收入"""
    income_type: IncomeType = IncomeType.RENTAL
    property_address: str
    tenant_name: Optional[str] = None
    monthly_rent: float


class SelfEmployedIncome(Income):
    """个体户收入"""
    income_type: IncomeType = IncomeType.SELF_EMPLOYED
    client_name: str
    invoice_number: Optional[str] = None
    vat_included: bool = False
    vat_amount: float = 0
