"""
增值税（USt）计算器
"""
from typing import Dict


class VATCalculator:
    """增值税计算器"""
    
    STANDARD_RATE = 0.20  # 标准税率 20%
    REDUCED_RATE = 0.10   # 优惠税率 10%
    SMALL_BUSINESS_THRESHOLD = 55000  # 小企业免税门槛
    
    @classmethod
    def calculate_vat(cls, net_amount: float, rate: float = STANDARD_RATE) -> Dict[str, float]:
        """
        计算增值税
        
        Args:
            net_amount: 净额
            rate: 税率
            
        Returns:
            包含净额、税额、总额的字典
        """
        vat_amount = net_amount * rate
        gross_amount = net_amount + vat_amount
        
        return {
            'net_amount': round(net_amount, 2),
            'vat_amount': round(vat_amount, 2),
            'gross_amount': round(gross_amount, 2),
            'vat_rate': rate
        }
    
    @classmethod
    def is_small_business_exempt(cls, annual_turnover: float) -> bool:
        """
        判断是否符合小企业免增值税条件（Kleinunternehmerregelung）
        
        Args:
            annual_turnover: 年营业额
            
        Returns:
            是否免税
        """
        return annual_turnover < cls.SMALL_BUSINESS_THRESHOLD
