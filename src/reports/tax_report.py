"""
税务报表生成器
"""
from typing import Dict
from datetime import date
import json


class TaxReport:
    """税务报表生成器"""
    
    @staticmethod
    def generate_annual_summary(
        year: int,
        income_data: Dict,
        expense_data: Dict,
        tax_calculation: Dict
    ) -> Dict:
        """
        生成年度税务摘要
        
        Args:
            year: 年份
            income_data: 收入数据
            expense_data: 费用数据
            tax_calculation: 税务计算结果
            
        Returns:
            完整的年度报表
        """
        return {
            'year': year,
            'generated_date': date.today().isoformat(),
            'income_summary': income_data,
            'expense_summary': expense_data,
            'tax_calculation': tax_calculation,
            'net_taxable_income': income_data['total'] - expense_data['total']
        }
    
    @staticmethod
    def export_to_json(report: Dict, filename: str):
        """导出为JSON格式"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    
    @staticmethod
    def format_finanzonline_data(report: Dict) -> Dict:
        """
        格式化为FinanzOnline兼容格式
        这是简化版本，实际需要根据官方表格调整
        """
        return {
            'Steuerjahr': report['year'],
            'Einkünfte': {
                'Nichtselbständige_Arbeit': report['income_summary']['employment'],
                'Vermietung_und_Verpachtung': report['income_summary']['rental'],
                'Selbständige_Arbeit': report['income_summary']['self_employed']
            },
            'Werbungskosten': report['expense_summary']['total'],
            'Einkommen': report['net_taxable_income'],
            'Einkommensteuer': report['tax_calculation']['tax_amount']
        }
