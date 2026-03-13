"""Deductibility checker for expense categorization by user type"""
from typing import Tuple, Optional
from enum import Enum


class UserType(str, Enum):
    """User types for tax purposes"""
    EMPLOYEE = "employee"
    SELF_EMPLOYED = "self_employed"
    LANDLORD = "landlord"
    MIXED = "mixed"
    GMBH = "gmbh"


class ExpenseCategory(str, Enum):
    """Expense categories"""
    # General categories
    GROCERIES = "groceries"
    OTHER = "other"
    
    # Employee categories
    COMMUTING = "commuting"
    HOME_OFFICE = "home_office"
    
    # Self-employed categories
    OFFICE_SUPPLIES = "office_supplies"
    EQUIPMENT = "equipment"
    TRAVEL = "travel"
    MARKETING = "marketing"
    PROFESSIONAL_SERVICES = "professional_services"
    
    # Landlord categories
    MAINTENANCE = "maintenance"
    PROPERTY_TAX = "property_tax"
    LOAN_INTEREST = "loan_interest"
    
    # Shared categories
    INSURANCE = "insurance"
    UTILITIES = "utilities"

    # New categories (aligned with Austrian Kontenrahmen)
    VEHICLE = "vehicle"
    TELECOM = "telecom"
    RENT = "rent"
    BANK_FEES = "bank_fees"
    SVS_CONTRIBUTIONS = "svs_contributions"
    DEPRECIATION = "depreciation"


class DeductibilityResult:
    """Result of deductibility check"""
    
    def __init__(
        self,
        is_deductible: bool,
        reason: str,
        requires_review: bool = False,
        max_amount: Optional[float] = None
    ):
        self.is_deductible = is_deductible
        self.reason = reason
        self.requires_review = requires_review
        self.max_amount = max_amount
    
    def __repr__(self):
        return f"<DeductibilityResult(deductible={self.is_deductible}, reason={self.reason})>"


class DeductibilityChecker:
    """
    Check if expenses are deductible based on user type and expense category.
    
    Implements Austrian tax law rules for different user types:
    - Employees: Limited deductions (commuting, home office)
    - Self-employed: Business expenses fully deductible
    - Landlords: Rental property expenses deductible
    """
    
    # Deduction rules by user type and expense category
    DEDUCTION_RULES = {
        UserType.EMPLOYEE: {
            ExpenseCategory.COMMUTING: {
                'deductible': True,
                'reason': 'Pendlerpauschale (commuting allowance) applies for employees',
                'condition': 'distance >= 20km'
            },
            ExpenseCategory.HOME_OFFICE: {
                'deductible': True,
                'reason': 'Home office flat-rate deduction ?300/year for employees',
                'max_amount': 300.00
            },
            ExpenseCategory.GROCERIES: {
                'deductible': False,
                'reason': 'Personal living expenses are not deductible for employees'
            },
            ExpenseCategory.OFFICE_SUPPLIES: {
                'deductible': False,
                'reason': 'Office supplies are not deductible for employees (employer responsibility)'
            },
            ExpenseCategory.EQUIPMENT: {
                'deductible': False,
                'reason': 'Equipment is not deductible for employees (employer responsibility)'
            },
            ExpenseCategory.TRAVEL: {
                'deductible': False,
                'reason': 'Travel expenses are not deductible for employees (use commuting allowance instead)'
            },
            ExpenseCategory.INSURANCE: {
                'deductible': False,
                'reason': 'Insurance is generally not deductible for employees (except specific cases)'
            },
            ExpenseCategory.OTHER: {
                'deductible': False,
                'reason': 'Other expenses are generally not deductible for employees'
            },
            ExpenseCategory.VEHICLE: {
                'deductible': False,
                'reason': 'Vehicle expenses are not deductible for employees (use Pendlerpauschale)'
            },
            ExpenseCategory.TELECOM: {
                'deductible': False,
                'reason': 'Telecom expenses are not deductible for employees'
            },
            ExpenseCategory.RENT: {
                'deductible': False,
                'reason': 'Rent is not deductible for employees'
            },
            ExpenseCategory.BANK_FEES: {
                'deductible': False,
                'reason': 'Bank fees are not deductible for employees'
            },
            ExpenseCategory.SVS_CONTRIBUTIONS: {
                'deductible': False,
                'reason': 'SVS contributions are handled by employer for employees'
            }
        },
        
        UserType.SELF_EMPLOYED: {
            ExpenseCategory.OFFICE_SUPPLIES: {
                'deductible': True,
                'reason': 'Business office supplies are fully deductible for self-employed'
            },
            ExpenseCategory.EQUIPMENT: {
                'deductible': True,
                'reason': 'Business equipment is deductible for self-employed (may require depreciation for high-value items)'
            },
            ExpenseCategory.TRAVEL: {
                'deductible': True,
                'reason': 'Business travel expenses are fully deductible for self-employed',
                'condition': 'business_purpose'
            },
            ExpenseCategory.MARKETING: {
                'deductible': True,
                'reason': 'Marketing and advertising expenses are fully deductible for self-employed'
            },
            ExpenseCategory.PROFESSIONAL_SERVICES: {
                'deductible': True,
                'reason': 'Professional services (accountant, lawyer) are fully deductible for self-employed'
            },
            ExpenseCategory.INSURANCE: {
                'deductible': True,
                'reason': 'Business insurance is deductible for self-employed',
                'condition': 'business_related'
            },
            ExpenseCategory.UTILITIES: {
                'deductible': True,
                'reason': 'Business utilities (internet, phone) are deductible for self-employed',
                'condition': 'business_use_percentage'
            },
            ExpenseCategory.HOME_OFFICE: {
                'deductible': True,
                'reason': 'Home office expenses are deductible for self-employed based on usage percentage'
            },
            ExpenseCategory.GROCERIES: {
                'deductible': 'partial',
                'reason': 'Groceries may be deductible if used for business purposes (e.g., client entertainment)',
                'requires_review': True
            },
            ExpenseCategory.OTHER: {
                'deductible': 'partial',
                'reason': 'Other expenses may be deductible if business-related',
                'requires_review': True
            },
            ExpenseCategory.VEHICLE: {
                'deductible': True,
                'reason': 'Business vehicle expenses (fuel, maintenance, insurance) are deductible for self-employed'
            },
            ExpenseCategory.TELECOM: {
                'deductible': True,
                'reason': 'Telephone, internet and postage are deductible for self-employed'
            },
            ExpenseCategory.RENT: {
                'deductible': True,
                'reason': 'Business premises rent is fully deductible for self-employed'
            },
            ExpenseCategory.BANK_FEES: {
                'deductible': True,
                'reason': 'Business bank fees are deductible for self-employed'
            },
            ExpenseCategory.SVS_CONTRIBUTIONS: {
                'deductible': True,
                'reason': 'SVS/SVA social insurance contributions are deductible for self-employed'
            },
            ExpenseCategory.DEPRECIATION: {
                'deductible': True,
                'reason': 'Depreciation (AfA) is deductible for self-employed'
            }
        },
        
        UserType.LANDLORD: {
            ExpenseCategory.MAINTENANCE: {
                'deductible': True,
                'reason': 'Property maintenance and repair costs are fully deductible for landlords'
            },
            ExpenseCategory.PROPERTY_TAX: {
                'deductible': True,
                'reason': 'Property tax (Grundsteuer) is fully deductible for landlords'
            },
            ExpenseCategory.LOAN_INTEREST: {
                'deductible': True,
                'reason': 'Mortgage interest on rental property is fully deductible for landlords'
            },
            ExpenseCategory.INSURANCE: {
                'deductible': True,
                'reason': 'Property insurance is fully deductible for landlords',
                'condition': 'property_related'
            },
            ExpenseCategory.UTILITIES: {
                'deductible': True,
                'reason': 'Utilities for rental property are deductible for landlords (if paid by landlord)'
            },
            ExpenseCategory.PROFESSIONAL_SERVICES: {
                'deductible': True,
                'reason': 'Property management and legal services are deductible for landlords'
            },
            ExpenseCategory.GROCERIES: {
                'deductible': False,
                'reason': 'Groceries are not deductible for landlords (personal expense)'
            },
            ExpenseCategory.OFFICE_SUPPLIES: {
                'deductible': True,
                'reason': 'Office supplies for property management are deductible for landlords'
            },
            ExpenseCategory.OTHER: {
                'deductible': 'partial',
                'reason': 'Other expenses may be deductible if property-related',
                'requires_review': True
            },
            ExpenseCategory.VEHICLE: {
                'deductible': 'partial',
                'reason': 'Vehicle expenses may be deductible if used for property management',
                'requires_review': True
            },
            ExpenseCategory.TELECOM: {
                'deductible': True,
                'reason': 'Telephone and internet for property management are deductible'
            },
            ExpenseCategory.RENT: {
                'deductible': False,
                'reason': 'Rent expenses are not typically deductible for landlords'
            },
            ExpenseCategory.BANK_FEES: {
                'deductible': True,
                'reason': 'Bank fees related to rental property are deductible'
            },
            ExpenseCategory.SVS_CONTRIBUTIONS: {
                'deductible': True,
                'reason': 'SVS/SVA contributions are deductible'
            },
            ExpenseCategory.DEPRECIATION: {
                'deductible': True,
                'reason': 'Depreciation (AfA) on rental property is deductible for landlords'
            }
        },

        # Mixed user type: employee + landlord/self-employed
        # Personal items (pure groceries/food) are NOT deductible
        # Business/property items are deductible (user has business/rental activity)
        UserType.MIXED: {
            ExpenseCategory.COMMUTING: {
                'deductible': True,
                'reason': 'Pendlerpauschale (commuting allowance) applies',
                'condition': 'distance >= 20km'
            },
            ExpenseCategory.HOME_OFFICE: {
                'deductible': True,
                'reason': 'Home office expenses are deductible based on usage percentage'
            },
            ExpenseCategory.OFFICE_SUPPLIES: {
                'deductible': True,
                'reason': 'Office supplies are deductible for business/rental property management',
                'requires_review': True
            },
            ExpenseCategory.EQUIPMENT: {
                'deductible': True,
                'reason': 'Equipment for business or rental property is deductible (may require depreciation for items over €1,000)',
                'requires_review': True
            },
            ExpenseCategory.TRAVEL: {
                'deductible': True,
                'reason': 'Travel expenses are deductible if business-related',
                'requires_review': True,
                'condition': 'business_purpose'
            },
            ExpenseCategory.MARKETING: {
                'deductible': True,
                'reason': 'Marketing and advertising expenses are deductible'
            },
            ExpenseCategory.PROFESSIONAL_SERVICES: {
                'deductible': True,
                'reason': 'Professional services (accountant, lawyer) are deductible'
            },
            ExpenseCategory.INSURANCE: {
                'deductible': True,
                'reason': 'Business or property insurance is deductible',
                'requires_review': True
            },
            ExpenseCategory.UTILITIES: {
                'deductible': True,
                'reason': 'Utilities for business or rental property are deductible',
                'requires_review': True
            },
            ExpenseCategory.MAINTENANCE: {
                'deductible': True,
                'reason': 'Maintenance and repair costs for rental property or business are fully deductible',
                'requires_review': True
            },
            ExpenseCategory.PROPERTY_TAX: {
                'deductible': True,
                'reason': 'Property tax (Grundsteuer) is deductible for rental property'
            },
            ExpenseCategory.LOAN_INTEREST: {
                'deductible': True,
                'reason': 'Mortgage/business loan interest is deductible'
            },
            ExpenseCategory.GROCERIES: {
                'deductible': False,
                'reason': 'Personal/household purchases are not deductible'
            },
            ExpenseCategory.OTHER: {
                'deductible': False,
                'reason': 'Unclassified expenses are not deductible by default',
                'requires_review': True
            },
            ExpenseCategory.VEHICLE: {
                'deductible': True,
                'reason': 'Vehicle expenses (fuel, maintenance) are deductible for business/rental activity',
                'requires_review': True
            },
            ExpenseCategory.TELECOM: {
                'deductible': True,
                'reason': 'Telephone, internet and postage are deductible for business/rental activity'
            },
            ExpenseCategory.RENT: {
                'deductible': True,
                'reason': 'Business premises rent is deductible'
            },
            ExpenseCategory.BANK_FEES: {
                'deductible': True,
                'reason': 'Business bank fees are deductible'
            },
            ExpenseCategory.SVS_CONTRIBUTIONS: {
                'deductible': True,
                'reason': 'SVS/SVA social insurance contributions are deductible'
            },
            ExpenseCategory.DEPRECIATION: {
                'deductible': True,
                'reason': 'Depreciation (AfA) is deductible for business/rental assets'
            }
        },
        UserType.GMBH: {
            ExpenseCategory.OFFICE_SUPPLIES: {
                'deductible': True,
                'reason': 'Office supplies are deductible business expenses for GmbH'
            },
            ExpenseCategory.EQUIPMENT: {
                'deductible': True,
                'reason': 'Equipment is deductible (depreciation for items over €1,000)',
                'requires_review': True
            },
            ExpenseCategory.TRAVEL: {
                'deductible': True,
                'reason': 'Business travel expenses are fully deductible for GmbH'
            },
            ExpenseCategory.MARKETING: {
                'deductible': True,
                'reason': 'Marketing and advertising expenses are deductible'
            },
            ExpenseCategory.PROFESSIONAL_SERVICES: {
                'deductible': True,
                'reason': 'Professional services (accountant, lawyer, notary) are deductible'
            },
            ExpenseCategory.INSURANCE: {
                'deductible': True,
                'reason': 'Business insurance is deductible'
            },
            ExpenseCategory.UTILITIES: {
                'deductible': True,
                'reason': 'Business utilities are deductible'
            },
            ExpenseCategory.MAINTENANCE: {
                'deductible': True,
                'reason': 'Maintenance and repair costs are deductible business expenses'
            },
            ExpenseCategory.PROPERTY_TAX: {
                'deductible': True,
                'reason': 'Property tax on business premises is deductible'
            },
            ExpenseCategory.LOAN_INTEREST: {
                'deductible': True,
                'reason': 'Business loan interest is deductible'
            },
            ExpenseCategory.GROCERIES: {
                'deductible': False,
                'reason': 'Personal purchases are not deductible for GmbH'
            },
            ExpenseCategory.COMMUTING: {
                'deductible': False,
                'reason': 'Personal commuting is not a GmbH expense (use KFZ-Aufwand for business vehicles)'
            },
            ExpenseCategory.HOME_OFFICE: {
                'deductible': True,
                'reason': 'Home office costs can be deductible if properly documented',
                'requires_review': True
            },
            ExpenseCategory.OTHER: {
                'deductible': False,
                'reason': 'Unclassified expenses are not deductible by default',
                'requires_review': True
            },
            ExpenseCategory.VEHICLE: {
                'deductible': True,
                'reason': 'Company vehicle expenses (KFZ-Aufwand) are fully deductible'
            },
            ExpenseCategory.TELECOM: {
                'deductible': True,
                'reason': 'Telecommunications expenses are deductible'
            },
            ExpenseCategory.RENT: {
                'deductible': True,
                'reason': 'Business premises rent is deductible'
            },
            ExpenseCategory.BANK_FEES: {
                'deductible': True,
                'reason': 'Bank fees are deductible business expenses'
            },
            ExpenseCategory.SVS_CONTRIBUTIONS: {
                'deductible': True,
                'reason': 'Social insurance contributions are deductible'
            },
            ExpenseCategory.DEPRECIATION: {
                'deductible': True,
                'reason': 'Depreciation (AfA) is deductible for GmbH'
            }
        }
    }
    
    def check(
        self,
        expense_category: str,
        user_type: str
    ) -> DeductibilityResult:
        """
        Check if an expense category is deductible for a given user type.
        
        Args:
            expense_category: The expense category (string)
            user_type: The user type (string)
        
        Returns:
            DeductibilityResult with deductibility status and reason
        """
        # Convert strings to enums
        try:
            user_type_enum = UserType(user_type.lower())
        except ValueError:
            return DeductibilityResult(
                is_deductible=False,
                reason=f"Unknown user type: {user_type}"
            )
        
        try:
            category_enum = ExpenseCategory(expense_category.lower())
        except ValueError:
            # Unknown category - default to not deductible
            return DeductibilityResult(
                is_deductible=False,
                reason=f"Unknown expense category: {expense_category}",
                requires_review=True
            )
        
        # Get rules for user type
        rules = self.DEDUCTION_RULES.get(user_type_enum, {})
        rule = rules.get(category_enum)
        
        if not rule:
            # No specific rule - default to not deductible
            return DeductibilityResult(
                is_deductible=False,
                reason=f"{expense_category} is not in the deductible list for {user_type}",
                requires_review=True
            )
        
        # Check deductibility
        deductible = rule['deductible']
        reason = rule['reason']
        requires_review = rule.get('requires_review', False)
        max_amount = rule.get('max_amount')
        
        if deductible == 'partial':
            # Partial deductibility - requires user review
            return DeductibilityResult(
                is_deductible=True,
                reason=f"?? {reason}",
                requires_review=True
            )
        elif deductible is False:
            return DeductibilityResult(
                is_deductible=False,
                reason=reason,
                requires_review=False
            )
        else:
            # Fully deductible
            return DeductibilityResult(
                is_deductible=True,
                reason=reason,
                requires_review=requires_review,
                max_amount=max_amount
            )
    
    def is_deductible(
        self,
        expense_category: str,
        user_type: str
    ) -> bool:
        """
        Simple boolean check if expense is deductible.
        
        Args:
            expense_category: The expense category
            user_type: The user type
        
        Returns:
            True if deductible, False otherwise
        """
        result = self.check(expense_category, user_type)
        return result.is_deductible
    
    def get_deduction_rules(
        self,
        user_type: str
    ) -> dict:
        """
        Get all deduction rules for a user type.
        
        Args:
            user_type: The user type
        
        Returns:
            Dictionary of deduction rules
        """
        try:
            user_type_enum = UserType(user_type.lower())
            return self.DEDUCTION_RULES.get(user_type_enum, {})
        except ValueError:
            return {}
    
    def explain_deductibility(
        self,
        expense_category: str,
        user_type: str
    ) -> str:
        """
        Get a human-readable explanation of deductibility.
        
        Args:
            expense_category: The expense category
            user_type: The user type
        
        Returns:
            Explanation string
        """
        result = self.check(expense_category, user_type)
        
        explanation = f"Category: {expense_category}\n"
        explanation += f"User Type: {user_type}\n"
        explanation += f"Deductible: {'Yes' if result.is_deductible else 'No'}\n"
        explanation += f"Reason: {result.reason}\n"
        
        if result.requires_review:
            explanation += "?? This expense requires manual review\n"
        
        if result.max_amount:
            explanation += f"Maximum deductible amount: ?{result.max_amount:.2f}\n"
        
        return explanation


