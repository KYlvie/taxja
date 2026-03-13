"""PDF generator for tax reports using ReportLab"""
from decimal import Decimal
from datetime import datetime
from typing import Dict, Optional
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, Image
)
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT


class PDFGenerator:
    """
    PDF generator for Austrian tax reports.
    
    Supports multi-language templates (German, English, Chinese).
    Generates comprehensive tax summary reports with:
    - Taxpayer information
    - Income/expense summary
    - Tax calculation breakdown
    - Deductions
    - Net income
    """
    
    # Translation dictionaries
    TRANSLATIONS = {
        'de': {
            'title': 'Steuerbericht',
            'tax_year': 'Steuerjahr',
            'taxpayer_info': 'Steuerpflichtige Information',
            'name': 'Name',
            'tax_number': 'Steuernummer',
            'address': 'Adresse',
            'user_type': 'Benutzertyp',
            'income_summary': 'Einkommensübersicht',
            'employment_income': 'Einkommen aus nichtselbständiger Arbeit',
            'rental_income': 'Einkommen aus Vermietung',
            'rental_income_by_property': 'Mieteinnahmen nach Immobilie',
            'self_employment_income': 'Einkommen aus selbständiger Arbeit',
            'capital_gains': 'Kapitalerträge',
            'total_income': 'Gesamteinkommen',
            'expense_summary': 'Ausgabenübersicht',
            'deductible_expenses': 'Abzugsfähige Ausgaben',
            'non_deductible_expenses': 'Nicht abzugsfähige Ausgaben',
            'property_expenses': 'Immobilienausgaben',
            'property_depreciation': 'Immobilienabschreibung (AfA)',
            'loan_interest': 'Darlehenszinsen',
            'property_management_fees': 'Hausverwaltungsgebühren',
            'property_insurance': 'Gebäudeversicherung',
            'property_tax': 'Grundsteuer',
            'maintenance': 'Instandhaltung',
            'utilities': 'Nebenkosten',
            'total_expenses': 'Gesamtausgaben',
            'tax_calculation': 'Steuerberechnung',
            'gross_income': 'Bruttoeinkommen',
            'deductions': 'Abzüge',
            'taxable_income': 'Zu versteuerndes Einkommen',
            'income_tax': 'Einkommensteuer',
            'vat': 'Umsatzsteuer',
            'svs': 'SVS-Beiträge',
            'total_tax': 'Gesamtsteuer',
            'net_income': 'Nettoeinkommen',
            'tax_brackets': 'Steuerstufen',
            'bracket': 'Stufe',
            'rate': 'Satz',
            'taxable_amount': 'Steuerpflichtiger Betrag',
            'tax_amount': 'Steuerbetrag',
            'deduction_details': 'Abzugsdetails',
            'svs_contributions': 'SVS-Beiträge',
            'commuting_allowance': 'Pendlerpauschale',
            'home_office': 'Homeoffice-Pauschale',
            'family_deductions': 'Familienabzüge',
            'generated_on': 'Erstellt am',
            'disclaimer': 'Haftungsausschluss: Dieser Bericht dient nur als Referenz und stellt keine Steuerberatung dar. Die endgültige Steuererklärung erfolgt über FinanzOnline. Bei komplexen Fällen konsultieren Sie bitte einen Steuerberater.',
            'based_on_usp': 'Basierend auf USP 2026 Steuertabelle',
            'employee': 'Angestellter',
            'self_employed': 'Selbständiger',
            'landlord': 'Vermieter',
            'mixed': 'Gemischt',
        },
        'en': {
            'title': 'Tax Report',
            'tax_year': 'Tax Year',
            'taxpayer_info': 'Taxpayer Information',
            'name': 'Name',
            'tax_number': 'Tax Number',
            'address': 'Address',
            'user_type': 'User Type',
            'income_summary': 'Income Summary',
            'employment_income': 'Employment Income',
            'rental_income': 'Rental Income',
            'rental_income_by_property': 'Rental Income by Property',
            'self_employment_income': 'Self-Employment Income',
            'capital_gains': 'Capital Gains',
            'total_income': 'Total Income',
            'expense_summary': 'Expense Summary',
            'deductible_expenses': 'Deductible Expenses',
            'non_deductible_expenses': 'Non-Deductible Expenses',
            'property_expenses': 'Property Expenses',
            'property_depreciation': 'Property Depreciation (AfA)',
            'loan_interest': 'Loan Interest',
            'property_management_fees': 'Property Management Fees',
            'property_insurance': 'Property Insurance',
            'property_tax': 'Property Tax',
            'maintenance': 'Maintenance',
            'utilities': 'Utilities',
            'total_expenses': 'Total Expenses',
            'tax_calculation': 'Tax Calculation',
            'gross_income': 'Gross Income',
            'deductions': 'Deductions',
            'taxable_income': 'Taxable Income',
            'income_tax': 'Income Tax',
            'vat': 'VAT',
            'svs': 'SVS Contributions',
            'total_tax': 'Total Tax',
            'net_income': 'Net Income',
            'tax_brackets': 'Tax Brackets',
            'bracket': 'Bracket',
            'rate': 'Rate',
            'taxable_amount': 'Taxable Amount',
            'tax_amount': 'Tax Amount',
            'deduction_details': 'Deduction Details',
            'svs_contributions': 'SVS Contributions',
            'commuting_allowance': 'Commuting Allowance',
            'home_office': 'Home Office Deduction',
            'family_deductions': 'Family Deductions',
            'generated_on': 'Generated on',
            'disclaimer': 'Disclaimer: This report is for reference only and does not constitute tax advice. Final tax filing must be done through FinanzOnline. For complex cases, please consult a Steuerberater.',
            'based_on_usp': 'Based on USP 2026 Tax Tables',
            'employee': 'Employee',
            'self_employed': 'Self-Employed',
            'landlord': 'Landlord',
            'mixed': 'Mixed',
        },
        'zh': {
            'title': '税务报告',
            'tax_year': '纳税年度',
            'taxpayer_info': '纳税人信息',
            'name': '姓名',
            'tax_number': '税号',
            'address': '地址',
            'user_type': '用户类型',
            'income_summary': '收入汇总',
            'employment_income': '工资收入',
            'rental_income': '租赁收入',
            'rental_income_by_property': '按物业分类的租金收入',
            'self_employment_income': '个体户收入',
            'capital_gains': '资本收益',
            'total_income': '总收入',
            'expense_summary': '支出汇总',
            'deductible_expenses': '可抵扣支出',
            'non_deductible_expenses': '不可抵扣支出',
            'property_expenses': '物业支出',
            'property_depreciation': '物业折旧 (AfA)',
            'loan_interest': '贷款利息',
            'property_management_fees': '物业管理费',
            'property_insurance': '物业保险',
            'property_tax': '物业税',
            'maintenance': '维护费用',
            'utilities': '水电费',
            'total_expenses': '总支出',
            'tax_calculation': '税款计算',
            'gross_income': '总收入',
            'deductions': '扣除项',
            'taxable_income': '应税收入',
            'income_tax': '所得税',
            'vat': '增值税',
            'svs': 'SVS社保缴费',
            'total_tax': '总税款',
            'net_income': '净收入',
            'tax_brackets': '税级',
            'bracket': '税级',
            'rate': '税率',
            'taxable_amount': '应税金额',
            'tax_amount': '税额',
            'deduction_details': '扣除详情',
            'svs_contributions': 'SVS社保缴费',
            'commuting_allowance': '通勤补贴',
            'home_office': '家庭办公室扣除',
            'family_deductions': '家庭扣除',
            'generated_on': '生成日期',
            'disclaimer': '免责声明：本报告仅供参考，不构成税务咨询。最终报税必须通过 FinanzOnline 进行。复杂情况请咨询 Steuerberater。',
            'based_on_usp': '基于 USP 2026 税率表',
            'employee': '职员',
            'self_employed': '个体户',
            'landlord': '房东',
            'mixed': '混合',
        }
    }
    
    def __init__(self):
        """Initialize PDF generator with styles"""
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()
    
    def _setup_custom_styles(self):
        """Set up custom paragraph styles"""
        # Title style
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1a237e'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        ))
        
        # Section heading style
        self.styles.add(ParagraphStyle(
            name='SectionHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#283593'),
            spaceAfter=12,
            spaceBefore=20,
            fontName='Helvetica-Bold'
        ))
        
        # Disclaimer style
        self.styles.add(ParagraphStyle(
            name='Disclaimer',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.HexColor('#666666'),
            spaceAfter=12,
            spaceBefore=12,
            leftIndent=20,
            rightIndent=20,
            alignment=TA_LEFT
        ))
    
    def generate_tax_report(
        self,
        user_data: Dict,
        tax_data: Dict,
        tax_year: int,
        language: str = 'de'
    ) -> bytes:
        """
        Generate a comprehensive tax report PDF.
        
        Args:
            user_data: User information (name, tax_number, address, user_type)
            tax_data: Tax calculation data (income_summary, expense_summary, tax_calculation, deductions)
            tax_year: Tax year for the report
            language: Language code ('de', 'en', 'zh')
            
        Returns:
            PDF file as bytes
        """
        # Validate language
        if language not in self.TRANSLATIONS:
            language = 'de'
        
        t = self.TRANSLATIONS[language]
        
        # Create PDF buffer
        buffer = BytesIO()
        
        # Create document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2*cm,
            bottomMargin=2*cm
        )
        
        # Build content
        story = []
        
        # Title
        story.append(Paragraph(f"{t['title']} {tax_year}", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.5*cm))
        
        # Based on USP note
        story.append(Paragraph(
            f"<i>{t['based_on_usp']}</i>",
            self.styles['Normal']
        ))
        story.append(Spacer(1, 0.5*cm))
        
        # Taxpayer Information
        story.append(Paragraph(t['taxpayer_info'], self.styles['SectionHeading']))
        taxpayer_data = [
            [t['name'], user_data.get('name', 'N/A')],
            [t['tax_number'], user_data.get('tax_number', 'N/A')],
            [t['address'], user_data.get('address', 'N/A')],
            [t['user_type'], t.get(user_data.get('user_type', 'employee'), user_data.get('user_type', 'N/A'))],
        ]
        story.append(self._create_table(taxpayer_data, col_widths=[5*cm, 11*cm]))
        story.append(Spacer(1, 0.5*cm))
        
        # Income Summary
        story.append(Paragraph(t['income_summary'], self.styles['SectionHeading']))
        income_summary = tax_data.get('income_summary', {})
        income_data = []
        
        if income_summary.get('employment', 0) > 0:
            income_data.append([t['employment_income'], self._format_currency(income_summary['employment'])])
        
        # Rental income with property breakdown
        if income_summary.get('rental', 0) > 0:
            income_data.append([t['rental_income'], self._format_currency(income_summary['rental'])])
            
            # Add property breakdown if available
            rental_by_property = income_summary.get('rental_by_property', {})
            if rental_by_property:
                income_data.append([f"<i>  {t['rental_income_by_property']}:</i>", ''])
                for property_address, amount in rental_by_property.items():
                    income_data.append([f"<i>    • {property_address}</i>", f"<i>{self._format_currency(amount)}</i>"])
        
        if income_summary.get('self_employment', 0) > 0:
            income_data.append([t['self_employment_income'], self._format_currency(income_summary['self_employment'])])
        if income_summary.get('capital_gains', 0) > 0:
            income_data.append([t['capital_gains'], self._format_currency(income_summary['capital_gains'])])
        
        income_data.append(['', ''])  # Separator
        income_data.append([f"<b>{t['total_income']}</b>", f"<b>{self._format_currency(income_summary.get('total', 0))}</b>"])
        
        story.append(self._create_table(income_data, col_widths=[10*cm, 6*cm]))
        story.append(Spacer(1, 0.5*cm))
        
        # Expense Summary
        story.append(Paragraph(t['expense_summary'], self.styles['SectionHeading']))
        expense_summary = tax_data.get('expense_summary', {})
        expense_data = [
            [t['deductible_expenses'], self._format_currency(expense_summary.get('deductible', 0))],
            [t['non_deductible_expenses'], self._format_currency(expense_summary.get('non_deductible', 0))],
        ]
        
        # Add property expenses breakdown if available
        property_expenses = expense_summary.get('property_expenses', {})
        if property_expenses:
            expense_data.append(['', ''])  # Separator
            expense_data.append([f"<i>{t['property_expenses']}:</i>", ''])
            for category, amount in property_expenses.items():
                if amount > 0:
                    # Translate category name if available in translations
                    category_display = t.get(category, category.replace('_', ' ').title())
                    expense_data.append([f"<i>  • {category_display}</i>", f"<i>{self._format_currency(amount)}</i>"])
        
        # Add property depreciation if available
        property_depreciation = expense_summary.get('property_depreciation', 0)
        if property_depreciation > 0:
            if not property_expenses:  # Add separator if not already added
                expense_data.append(['', ''])
            expense_data.append([f"<i>{t['property_depreciation']}</i>", f"<i>{self._format_currency(property_depreciation)}</i>"])
        
        expense_data.append(['', ''])  # Separator
        expense_data.append([f"<b>{t['total_expenses']}</b>", f"<b>{self._format_currency(expense_summary.get('total', 0))}</b>"])
        
        story.append(self._create_table(expense_data, col_widths=[10*cm, 6*cm]))
        story.append(Spacer(1, 0.5*cm))
        
        # Deduction Details
        story.append(Paragraph(t['deduction_details'], self.styles['SectionHeading']))
        deductions = tax_data.get('deductions', {})
        deduction_data = []
        
        if deductions.get('svs_contributions', 0) > 0:
            deduction_data.append([t['svs_contributions'], self._format_currency(deductions['svs_contributions'])])
        if deductions.get('commuting_allowance', 0) > 0:
            deduction_data.append([t['commuting_allowance'], self._format_currency(deductions['commuting_allowance'])])
        if deductions.get('home_office', 0) > 0:
            deduction_data.append([t['home_office'], self._format_currency(deductions['home_office'])])
        if deductions.get('family_deductions', 0) > 0:
            deduction_data.append([t['family_deductions'], self._format_currency(deductions['family_deductions'])])
        
        if deduction_data:
            deduction_data.append(['', ''])  # Separator
            deduction_data.append([f"<b>{t['deductions']}</b>", f"<b>{self._format_currency(deductions.get('total', 0))}</b>"])
            story.append(self._create_table(deduction_data, col_widths=[10*cm, 6*cm]))
        else:
            story.append(Paragraph("<i>Keine Abzüge</i>", self.styles['Normal']))
        story.append(Spacer(1, 0.5*cm))
        
        # Tax Calculation
        story.append(Paragraph(t['tax_calculation'], self.styles['SectionHeading']))
        tax_calc = tax_data.get('tax_calculation', {})
        
        calc_data = [
            [t['gross_income'], self._format_currency(tax_calc.get('gross_income', 0))],
            [t['deductions'], f"- {self._format_currency(tax_calc.get('deductions', 0))}"],
            [f"<b>{t['taxable_income']}</b>", f"<b>{self._format_currency(tax_calc.get('taxable_income', 0))}</b>"],
            ['', ''],  # Separator
            [t['income_tax'], self._format_currency(tax_calc.get('income_tax', 0))],
        ]
        
        if not tax_calc.get('vat_exempt', True):
            calc_data.append([t['vat'], self._format_currency(tax_calc.get('vat', 0))])
        
        calc_data.append([t['svs'], self._format_currency(tax_calc.get('svs', 0))])
        calc_data.append(['', ''])  # Separator
        calc_data.append([f"<b>{t['total_tax']}</b>", f"<b>{self._format_currency(tax_calc.get('total_tax', 0))}</b>"])
        calc_data.append(['', ''])  # Separator
        calc_data.append([f"<b>{t['net_income']}</b>", f"<b>{self._format_currency(tax_calc.get('net_income', 0))}</b>"])
        
        story.append(self._create_table(calc_data, col_widths=[10*cm, 6*cm]))
        story.append(Spacer(1, 0.5*cm))
        
        # Tax Brackets Breakdown
        breakdown = tax_calc.get('breakdown', [])
        if breakdown:
            story.append(Paragraph(t['tax_brackets'], self.styles['SectionHeading']))
            
            bracket_data = [[
                f"<b>{t['bracket']}</b>",
                f"<b>{t['rate']}</b>",
                f"<b>{t['taxable_amount']}</b>",
                f"<b>{t['tax_amount']}</b>"
            ]]
            
            for bracket in breakdown:
                if bracket.get('taxable_amount', 0) > 0:
                    bracket_data.append([
                        bracket.get('bracket', ''),
                        bracket.get('rate', ''),
                        self._format_currency(bracket.get('taxable_amount', 0)),
                        self._format_currency(bracket.get('tax_amount', 0))
                    ])
            
            story.append(self._create_table(
                bracket_data,
                col_widths=[5*cm, 3*cm, 4*cm, 4*cm],
                header_row=True
            ))
            story.append(Spacer(1, 0.5*cm))
        
        # Generated timestamp
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(
            f"<i>{t['generated_on']}: {datetime.now().strftime('%d.%m.%Y %H:%M')}</i>",
            self.styles['Normal']
        ))
        
        # Disclaimer
        story.append(Spacer(1, 1*cm))
        story.append(Paragraph(
            f"<b>⚠️ {t['disclaimer']}</b>",
            self.styles['Disclaimer']
        ))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF bytes
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
    
    def _create_table(
        self,
        data: list,
        col_widths: list,
        header_row: bool = False
    ) -> Table:
        """
        Create a formatted table.
        
        Args:
            data: Table data as list of lists
            col_widths: Column widths
            header_row: Whether first row is a header
            
        Returns:
            Formatted Table object
        """
        table = Table(data, colWidths=col_widths)
        
        # Base style
        style = [
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]
        
        # Header row style
        if header_row:
            style.extend([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e8eaf6')),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ])
        
        # Alternating row colors
        for i in range(1 if header_row else 0, len(data)):
            if i % 2 == 0:
                style.append(('BACKGROUND', (0, i), (-1, i), colors.HexColor('#f5f5f5')))
        
        # Grid
        style.append(('GRID', (0, 0), (-1, -1), 0.5, colors.grey))
        
        table.setStyle(TableStyle(style))
        
        return table
    
    def _format_currency(self, amount: float) -> str:
        """
        Format amount as currency.
        
        Args:
            amount: Amount to format
            
        Returns:
            Formatted currency string
        """
        if isinstance(amount, Decimal):
            amount = float(amount)
        
        return f"€ {amount:,.2f}"
