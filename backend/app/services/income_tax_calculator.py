"""Income tax calculator for Austrian progressive tax system"""
from decimal import Decimal
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class TaxBracketResult:
    """Result for a single tax bracket calculation"""
    bracket_range: str
    rate: str
    taxable_amount: Decimal
    tax_amount: Decimal


@dataclass
class IncomeTaxResult:
    """Result of income tax calculation"""
    total_tax: Decimal
    breakdown: List[TaxBracketResult]
    effective_rate: Decimal
    taxable_income: Decimal
    loss_carryforward_applied: Optional[Decimal] = None
    remaining_loss_balance: Optional[Decimal] = None


class IncomeTaxCalculator:
    """
    Calculator for Austrian progressive income tax based on 2026 USP rates.
    
    Tax brackets (2026):
    - €0 – €13,539: 0%
    - €13,539 – €21,992: 20%
    - €21,992 – €36,458: 30%
    - €36,458 – €70,365: 40%
    - €70,365 – €104,859: 48%
    - €104,859 – €1,000,000: 50%
    - €1,000,000+: 55%
    """
    
    def __init__(self, tax_config: Dict):
        """
        Initialize calculator with tax configuration.
        
        Args:
            tax_config: Dictionary containing tax_brackets and exemption_amount
        """
        self.tax_brackets = tax_config.get("tax_brackets", [])
        self.exemption_amount = Decimal(str(tax_config.get("exemption_amount", "13539.00")))
        
        # Validate tax brackets
        if not self.tax_brackets:
            raise ValueError("Tax brackets configuration is required")
    
    def calculate_progressive_tax(
        self,
        taxable_income: Decimal,
        tax_year: int
    ) -> IncomeTaxResult:
        """
        Calculate progressive income tax based on 2026 USP tax brackets.
        
        Args:
            taxable_income: The taxable income amount (after deductions)
            tax_year: The tax year for calculation
            
        Returns:
            IncomeTaxResult with total tax, breakdown by bracket, and effective rate
        """
        # Ensure taxable_income is Decimal
        if not isinstance(taxable_income, Decimal):
            taxable_income = Decimal(str(taxable_income))
        
        # If income is zero or negative, no tax
        if taxable_income <= 0:
            return IncomeTaxResult(
                total_tax=Decimal('0.00'),
                breakdown=[],
                effective_rate=Decimal('0.00'),
                taxable_income=taxable_income
            )
        
        total_tax = Decimal('0.00')
        breakdown = []
        remaining_income = taxable_income
        
        # Process each tax bracket
        for bracket in self.tax_brackets:
            if remaining_income <= 0:
                break
            
            # Support both {"lower","upper"} and {"min","max"} bracket formats
            lower_limit = Decimal(str(bracket.get("lower", bracket.get("min", 0))))
            raw_upper = bracket.get("upper", bracket.get("max"))
            upper_limit = Decimal(str(raw_upper)) if raw_upper is not None else None
            raw_rate = bracket["rate"]
            # Normalize rate: if > 1 treat as percentage (e.g. 20 → 0.20)
            rate = Decimal(str(raw_rate))
            if rate > 1:
                rate = rate / Decimal("100")
            
            # Calculate taxable amount in this bracket
            if upper_limit is None:
                # Last bracket (no upper limit)
                taxable_in_bracket = remaining_income
            else:
                bracket_width = upper_limit - lower_limit
                taxable_in_bracket = min(remaining_income, bracket_width)
            
            # Calculate tax for this bracket
            tax_in_bracket = taxable_in_bracket * rate
            total_tax += tax_in_bracket
            
            # Format bracket range
            if upper_limit is None:
                bracket_range = f"€{lower_limit:,.2f}+"
            else:
                bracket_range = f"€{lower_limit:,.2f} - €{upper_limit:,.2f}"
            
            # Add to breakdown
            breakdown.append(TaxBracketResult(
                bracket_range=bracket_range,
                rate=f"{rate * 100:.0f}%",
                taxable_amount=taxable_in_bracket.quantize(Decimal('0.01')),
                tax_amount=tax_in_bracket.quantize(Decimal('0.01'))
            ))
            
            remaining_income -= taxable_in_bracket
        
        # Calculate effective rate
        effective_rate = (total_tax / taxable_income) if taxable_income > 0 else Decimal('0.00')
        
        return IncomeTaxResult(
            total_tax=total_tax.quantize(Decimal('0.01')),
            breakdown=breakdown,
            effective_rate=effective_rate.quantize(Decimal('0.0001')),
            taxable_income=taxable_income
        )
    
    def apply_exemption(
        self,
        gross_income: Decimal
    ) -> Decimal:
        """
        Apply exemption amount to gross income.
        
        Args:
            gross_income: The gross income before exemption
            
        Returns:
            Taxable income after applying exemption (minimum 0)
        """
        if not isinstance(gross_income, Decimal):
            gross_income = Decimal(str(gross_income))
        
        taxable_income = gross_income - self.exemption_amount
        
        # Taxable income cannot be negative
        return max(taxable_income, Decimal('0.00'))
    
    def calculate_tax_with_exemption(
        self,
        gross_income: Decimal,
        tax_year: int
    ) -> IncomeTaxResult:
        """
        Calculate income tax using progressive brackets.

        Note: The tax-free allowance (Freibetrag) is already embedded in the
        progressive tax brackets as the 0% first bracket.  Do NOT subtract
        exemption_amount separately — that would double-count the exemption.

        Args:
            gross_income: The gross income (taxable income after deductions)
            tax_year: The tax year for calculation

        Returns:
            IncomeTaxResult with total tax, breakdown, and effective rate
        """
        if not isinstance(gross_income, Decimal):
            gross_income = Decimal(str(gross_income))

        # Pass directly to progressive tax — the 0% bracket IS the exemption
        return self.calculate_progressive_tax(gross_income, tax_year)
    
    def calculate_tax_with_loss_carryforward(
        self,
        gross_income: Decimal,
        tax_year: int,
        loss_carryforward_applied: Decimal = Decimal('0.00'),
        remaining_loss_balance: Decimal = Decimal('0.00')
    ) -> IncomeTaxResult:
        """
        Calculate income tax after applying exemption and loss carryforward.
        
        This method integrates loss carryforward into the tax calculation:
        1. Apply exemption to gross income
        2. Apply loss carryforward to reduce taxable income
        3. Calculate tax on the remaining income
        
        Args:
            gross_income: The gross income before exemption
            tax_year: The tax year for calculation
            loss_carryforward_applied: Amount of loss carryforward applied
            remaining_loss_balance: Remaining loss balance after application
            
        Returns:
            IncomeTaxResult with total tax, breakdown, effective rate, and loss info
        """
        if not isinstance(gross_income, Decimal):
            gross_income = Decimal(str(gross_income))
        if not isinstance(loss_carryforward_applied, Decimal):
            loss_carryforward_applied = Decimal(str(loss_carryforward_applied))
        if not isinstance(remaining_loss_balance, Decimal):
            remaining_loss_balance = Decimal(str(remaining_loss_balance))
        
        # The tax-free allowance (Freibetrag) is already embedded in the
        # progressive brackets as the 0% first bracket.  Do NOT call
        # apply_exemption() here — that would double-count it.

        # §18 Abs. 6 EStG: Defensive cap — loss carryforward may not exceed
        # 75% of income (Verrechnungsgrenze).  The primary enforcement is in
        # LossCarryforwardService; this is a safety net.
        max_offset = (gross_income * Decimal('0.75')).quantize(Decimal('0.01'))
        capped_loss = min(loss_carryforward_applied, max_offset)

        # Apply loss carryforward to gross income
        taxable_income_after_loss = gross_income - capped_loss

        # Ensure taxable income doesn't go negative
        taxable_income_after_loss = max(taxable_income_after_loss, Decimal('0.00'))
        
        # Calculate tax
        tax_result = self.calculate_progressive_tax(taxable_income_after_loss, tax_year)
        
        # Add loss carryforward information to result (report the capped amount)
        tax_result.loss_carryforward_applied = capped_loss.quantize(Decimal('0.01'))
        tax_result.remaining_loss_balance = remaining_loss_balance.quantize(Decimal('0.01'))
        
        return tax_result
