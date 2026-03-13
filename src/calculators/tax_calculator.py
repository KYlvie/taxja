"""
奥地利税务计算器
基于2026年税率和规则
"""
from typing import List, Dict
from datetime import date


class AustrianTaxCalculator:
    """奥地利所得税计算器"""
    
    # 2026年税率表（累进税率）
    TAX_BRACKETS = [
        (13541, 0.0),      # 免税额
        (20818, 0.20),     # 20%
        (34513, 0.30),     # 30%
        (66612, 0.40),     # 40%
        (99266, 0.48),     # 48%
        (1000000, 0.50),   # 50%
        (float('inf'), 0.55)  # 55%
    ]
    
    VAT_RATE = 0.20  # 标准增值税率
    SMALL_BUSINESS_THRESHOLD = 55000  # 小企业免增值税门槛（2025年提高）
    
    @classmethod
    def calculate_income_tax(cls, annual_income: float) -> Dict[str, float]:
        """
        计算年度所得税
        
        Args:
            annual_income: 年度总收入（欧元）
            
        Returns:
            包含税额、税率等信息的字典
        """
        if annual_income <= cls.TAX_BRACKETS[0][0]:
            return {
                'taxable_income': annual_income,
                'tax_amount': 0,
                'effective_rate': 0,
                'net_income': annual_income
            }
        
        tax_amount = 0
        previous_bracket = 0
        
        for bracket_limit, rate in cls.TAX_BRACKETS:
            if annual_income <= bracket_limit:
                taxable_in_bracket = annual_income - previous_bracket
                tax_amount += taxable_in_bracket * rate
                break
            else:
                taxable_in_bracket = bracket_limit - previous_bracket
                tax_amount += taxable_in_bracket * rate
                previous_bracket = bracket_limit
        
        effective_rate = (tax_amount / annual_income) * 100 if annual_income > 0 else 0
        
        return {
            'taxable_income': annual_income,
            'tax_amount': round(tax_amount, 2),
            'effective_rate': round(effective_rate, 2),
            'net_income': round(annual_income - tax_amount, 2)
        }
