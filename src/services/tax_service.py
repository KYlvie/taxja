"""
税务服务 - 整合所有收入和费用计算
"""
from typing import List, Dict
from datetime import date
from ..models.income import Income, EmploymentIncome, RentalIncome, SelfEmployedIncome
from ..models.expense import Expense, ExpenseCategory
from ..calculators.tax_calculator import AustrianTaxCalculator
from ..calculators.vat_calculator import VATCalculator


class TaxService:
    """税务服务"""
    
    def __init__(self):
        self.incomes: List[Income] = []
        self.expenses: List[Expense] = []
    
    def add_income(self, income: Income):
        """添加收入"""
        self.incomes.append(income)
    
    def add_expense(self, expense: Expense):
        """添加费用"""
        self.expenses.append(expense)
    
    def calculate_total_income(self, year: int) -> Dict[str, float]:
        """计算年度总收入（按类型分类）"""
        result = {
            'employment': 0,
            'rental': 0,
            'self_employed': 0,
            'total': 0
        }
        
        for income in self.incomes:
            if income.date.year == year:
                if income.income_type.value == 'employment':
                    result['employment'] += income.amount
                elif income.income_type.value == 'rental':
                    result['rental'] += income.amount
                elif income.income_type.value == 'self_employed':
                    result['self_employed'] += income.amount
                result['total'] += income.amount
        
        return result
    
    def calculate_deductible_expenses(self, year: int) -> Dict[str, float]:
        """计算可抵扣费用"""
        result = {
            'rental_expenses': 0,
            'business_expenses': 0,
            'total': 0
        }
        
        rental_categories = {
            ExpenseCategory.PROPERTY_MAINTENANCE,
            ExpenseCategory.PROPERTY_MANAGEMENT,
            ExpenseCategory.MORTGAGE_INTEREST,
            ExpenseCategory.INSURANCE,
            ExpenseCategory.DEPRECIATION
        }
        
        for expense in self.expenses:
            if expense.date.year == year and expense.deductible:
                if expense.category in rental_categories:
                    result['rental_expenses'] += expense.amount
                else:
                    result['business_expenses'] += expense.amount
                result['total'] += expense.amount
        
        return result
