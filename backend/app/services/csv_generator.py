"""CSV generator for transaction data export"""
import csv
from io import StringIO
from typing import List, Dict, Optional
from datetime import date


class CSVGenerator:
    """
    CSV generator for exporting transaction data.
    
    Supports:
    - Full transaction export with all fields
    - Custom date ranges and filters
    - Roundtrip consistency (export → import → export produces same data)
    """
    
    # CSV column headers
    HEADERS = [
        'id',
        'date',
        'type',
        'amount',
        'description',
        'category',
        'is_deductible',
        'deduction_reason',
        'vat_rate',
        'vat_amount',
        'document_id',
        'classification_confidence',
        'import_source',
        'created_at'
    ]
    
    def generate_transactions_csv(
        self,
        transactions: List[Dict],
        include_headers: bool = True
    ) -> str:
        """
        Generate CSV export of transactions.
        
        Args:
            transactions: List of transaction dictionaries
            include_headers: Whether to include header row
            
        Returns:
            CSV string
        """
        output = StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=self.HEADERS,
            extrasaction='ignore'
        )
        
        if include_headers:
            writer.writeheader()
        
        for transaction in transactions:
            # Format transaction for CSV
            row = self._format_transaction_for_csv(transaction)
            writer.writerow(row)
        
        csv_string = output.getvalue()
        output.close()
        
        return csv_string
    
    def _format_transaction_for_csv(self, transaction: Dict) -> Dict:
        """
        Format a transaction dictionary for CSV export.
        
        Ensures all fields are properly formatted and handles None values.
        
        Args:
            transaction: Transaction dictionary
            
        Returns:
            Formatted dictionary ready for CSV export
        """
        # Create a copy to avoid modifying original
        formatted = {}
        
        for header in self.HEADERS:
            value = transaction.get(header)
            
            # Handle None values
            if value is None:
                formatted[header] = ''
                continue
            
            # Format dates
            if header in ['date', 'created_at']:
                if isinstance(value, (date, )):
                    formatted[header] = value.isoformat()
                else:
                    formatted[header] = str(value)
            
            # Format booleans
            elif header == 'is_deductible':
                formatted[header] = 'true' if value else 'false'
            
            # Format decimals/floats
            elif header in ['amount', 'vat_rate', 'vat_amount', 'classification_confidence']:
                formatted[header] = str(value)
            
            # Everything else as string
            else:
                formatted[header] = str(value)
        
        return formatted
    
    def generate_tax_summary_csv(
        self,
        tax_data: Dict,
        tax_year: int
    ) -> str:
        """
        Generate CSV export of tax summary data.
        
        Args:
            tax_data: Tax calculation data
            tax_year: Tax year
            
        Returns:
            CSV string with tax summary
        """
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow(['Austrian Tax Summary', tax_year])
        writer.writerow([])
        
        # Income Summary
        writer.writerow(['Income Summary'])
        income_summary = tax_data.get('income_summary', {})
        if income_summary.get('employment', 0) > 0:
            writer.writerow(['Employment Income', f"{income_summary['employment']:.2f}"])
        if income_summary.get('rental', 0) > 0:
            writer.writerow(['Rental Income', f"{income_summary['rental']:.2f}"])
        if income_summary.get('self_employment', 0) > 0:
            writer.writerow(['Self-Employment Income', f"{income_summary['self_employment']:.2f}"])
        if income_summary.get('capital_gains', 0) > 0:
            writer.writerow(['Capital Gains', f"{income_summary['capital_gains']:.2f}"])
        writer.writerow(['Total Income', f"{income_summary.get('total', 0):.2f}"])
        writer.writerow([])
        
        # Expense Summary
        writer.writerow(['Expense Summary'])
        expense_summary = tax_data.get('expense_summary', {})
        writer.writerow(['Deductible Expenses', f"{expense_summary.get('deductible', 0):.2f}"])
        writer.writerow(['Non-Deductible Expenses', f"{expense_summary.get('non_deductible', 0):.2f}"])
        writer.writerow(['Total Expenses', f"{expense_summary.get('total', 0):.2f}"])
        writer.writerow([])
        
        # Deductions
        writer.writerow(['Deductions'])
        deductions = tax_data.get('deductions', {})
        if deductions.get('svs_contributions', 0) > 0:
            writer.writerow(['SVS Contributions', f"{deductions['svs_contributions']:.2f}"])
        if deductions.get('commuting_allowance', 0) > 0:
            writer.writerow(['Commuting Allowance', f"{deductions['commuting_allowance']:.2f}"])
        if deductions.get('home_office', 0) > 0:
            writer.writerow(['Home Office', f"{deductions['home_office']:.2f}"])
        if deductions.get('family_deductions', 0) > 0:
            writer.writerow(['Family Deductions', f"{deductions['family_deductions']:.2f}"])
        writer.writerow(['Total Deductions', f"{deductions.get('total', 0):.2f}"])
        writer.writerow([])
        
        # Tax Calculation
        writer.writerow(['Tax Calculation'])
        tax_calc = tax_data.get('tax_calculation', {})
        writer.writerow(['Gross Income', f"{tax_calc.get('gross_income', 0):.2f}"])
        writer.writerow(['Deductions', f"{tax_calc.get('deductions', 0):.2f}"])
        writer.writerow(['Taxable Income', f"{tax_calc.get('taxable_income', 0):.2f}"])
        writer.writerow(['Income Tax', f"{tax_calc.get('income_tax', 0):.2f}"])
        if not tax_calc.get('vat_exempt', True):
            writer.writerow(['VAT', f"{tax_calc.get('vat', 0):.2f}"])
        writer.writerow(['SVS', f"{tax_calc.get('svs', 0):.2f}"])
        writer.writerow(['Total Tax', f"{tax_calc.get('total_tax', 0):.2f}"])
        writer.writerow(['Net Income', f"{tax_calc.get('net_income', 0):.2f}"])
        writer.writerow([])
        
        # Tax Brackets
        breakdown = tax_calc.get('breakdown', [])
        if breakdown:
            writer.writerow(['Tax Brackets'])
            writer.writerow(['Bracket', 'Rate', 'Taxable Amount', 'Tax Amount'])
            for bracket in breakdown:
                if bracket.get('taxable_amount', 0) > 0:
                    writer.writerow([
                        bracket.get('bracket', ''),
                        bracket.get('rate', ''),
                        f"{bracket.get('taxable_amount', 0):.2f}",
                        f"{bracket.get('tax_amount', 0):.2f}"
                    ])
        
        csv_string = output.getvalue()
        output.close()
        
        return csv_string
