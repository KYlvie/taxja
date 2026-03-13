from enum import Enum
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field


class ExpenseCategory(str, Enum):
    """费用类别"""
    # 租赁相关
    PROPERTY_MAINTENANCE = "property_maintenance"  # 物业维护
    PROPERTY_MANAGEMENT = "property_management"  # 物业管理费
    MORTGAGE_INTEREST = "mortgage_interest"  # 贷款利息
    PROPERTY_TAX = "property_tax"  # 物业税
    INSURANCE = "insurance"  # 保险
    DEPRECIATION = "depreciation"  # 折旧
    
    # 个体户相关
    OFFICE_SUPPLIES = "office_supplies"  # 办公用品
    EQUIPMENT = "equipment"  # 设备
    TRAVEL = "travel"  # 差旅
    PROFESSIONAL_SERVICES = "professional_services"  # 专业服务
    MARKETING = "marketing"  # 营销
    SOFTWARE = "software"  # 软件
    
    # 通用
    COMMUTE = "commute"  # 通勤
    OTHER = "other"


class Expense(BaseModel):
    """费用模型"""
    id: Optional[str] = None
    category: ExpenseCategory
    amount: float = Field(gt=0)
    date: date
    description: str
    receipt_number: Optional[str] = None
    vat_amount: float = 0
    deductible: bool = True  # 是否可抵扣
    related_income_id: Optional[str] = None  # 关联的收入ID
