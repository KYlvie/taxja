"""
使用示例 - 演示如何使用税务系统
"""
from datetime import date
from src.models.income import EmploymentIncome, RentalIncome, SelfEmployedIncome
from src.models.expense import Expense, ExpenseCategory
from src.services.tax_service import TaxService
from src.calculators.tax_calculator import AustrianTaxCalculator
from src.reports.tax_report import TaxReport


def main():
    # 创建税务服务实例
    tax_service = TaxService()
    
    # 示例：添加职员工资收入
    employment = EmploymentIncome(
        employer="ABC GmbH",
        gross_salary=45000,
        amount=45000,
        date=date(2026, 12, 31),
        description="年度工资",
        wage_tax_withheld=8500,
        social_security_withheld=6750
    )
    tax_service.add_income(employment)
    
    # 示例：添加租赁收入
    rental = RentalIncome(
        property_address="Mariahilfer Straße 123, 1060 Wien",
        monthly_rent=1200,
        amount=14400,  # 12个月
        date=date(2026, 12, 31),
        description="年度租金收入"
    )
    tax_service.add_income(rental)
    
    # 示例：添加个体户收入
    self_employed = SelfEmployedIncome(
        client_name="XYZ Consulting",
        invoice_number="INV-2026-001",
        amount=15000,
        date=date(2026, 6, 15),
        description="咨询服务",
        vat_included=True,
        vat_amount=2500
    )
    tax_service.add_income(self_employed)
    
    # 示例：添加租赁相关费用
    maintenance = Expense(
        category=ExpenseCategory.PROPERTY_MAINTENANCE,
        amount=2500,
        date=date(2026, 3, 10),
        description="公寓维修",
        deductible=True
    )
    tax_service.add_expense(maintenance)
    
    # 示例：添加个体户业务费用
    software = Expense(
        category=ExpenseCategory.SOFTWARE,
        amount=800,
        date=date(2026, 1, 15),
        description="专业软件订阅",
        vat_amount=160,
        deductible=True
    )
    tax_service.add_expense(software)
    
    # 计算2026年度数据
    year = 2026
    income_summary = tax_service.calculate_total_income(year)
    expense_summary = tax_service.calculate_deductible_expenses(year)
    
    # 计算净收入和税额
    net_income = income_summary['total'] - expense_summary['total']
    tax_calc = AustrianTaxCalculator.calculate_income_tax(net_income)
    
    # 生成报表
    report = TaxReport.generate_annual_summary(
        year=year,
        income_data=income_summary,
        expense_data=expense_summary,
        tax_calculation=tax_calc
    )
    
    # 打印摘要
    print("=" * 60)
    print(f"奥地利税务摘要 - {year}年")
    print("=" * 60)
    print(f"\n收入明细：")
    print(f"  职员工资:    €{income_summary['employment']:,.2f}")
    print(f"  租赁收入:    €{income_summary['rental']:,.2f}")
    print(f"  个体户收入:  €{income_summary['self_employed']:,.2f}")
    print(f"  总收入:      €{income_summary['total']:,.2f}")
    
    print(f"\n可抵扣费用：")
    print(f"  租赁费用:    €{expense_summary['rental_expenses']:,.2f}")
    print(f"  业务费用:    €{expense_summary['business_expenses']:,.2f}")
    print(f"  总费用:      €{expense_summary['total']:,.2f}")
    
    print(f"\n税务计算：")
    print(f"  应税收入:    €{tax_calc['taxable_income']:,.2f}")
    print(f"  所得税:      €{tax_calc['tax_amount']:,.2f}")
    print(f"  有效税率:    {tax_calc['effective_rate']:.2f}%")
    print(f"  税后净收入:  €{tax_calc['net_income']:,.2f}")
    
    # 导出报表
    TaxReport.export_to_json(report, f'tax_report_{year}.json')
    print(f"\n报表已导出到: tax_report_{year}.json")
    
    # 生成FinanzOnline格式
    finanzonline_data = TaxReport.format_finanzonline_data(report)
    TaxReport.export_to_json(finanzonline_data, f'finanzonline_{year}.json')
    print(f"FinanzOnline格式已导出到: finanzonline_{year}.json")


if __name__ == "__main__":
    main()
