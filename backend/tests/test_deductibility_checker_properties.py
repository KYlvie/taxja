"""Property-based tests for deductibility checker"""
import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from backend.app.services.deductibility_checker import (
    DeductibilityChecker,
    UserType,
    ExpenseCategory
)


class TestDeductibilityRulesProperties:
    """
    Property 13: Expense deductibility rules
    
    **Validates: Requirements 5.1, 5.2, 6.1, 6.2**
    
    This property ensures that the deductibility checker correctly applies
    Austrian tax law rules for different user types and expense categories.
    """
    
    @given(
        user_type=st.sampled_from([ut.value for ut in UserType]),
        expense_category=st.sampled_from([ec.value for ec in ExpenseCategory])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deductibility_check_returns_valid_result(
        self,
        user_type,
        expense_category
    ):
        """
        Property: Deductibility check always returns a valid result
        
        For any valid user type and expense category combination,
        the checker must return a result with all required fields.
        """
        checker = DeductibilityChecker()
        
        result = checker.check(expense_category, user_type)
        
        # Assert result has required attributes
        assert hasattr(result, 'is_deductible')
        assert hasattr(result, 'reason')
        assert hasattr(result, 'requires_review')
        
        # Assert is_deductible is boolean
        assert isinstance(result.is_deductible, bool), \
            "is_deductible must be a boolean"
        
        # Assert reason is non-empty string
        assert isinstance(result.reason, str), \
            "reason must be a string"
        assert len(result.reason) > 0, \
            "reason must not be empty"
        
        # Assert requires_review is boolean
        assert isinstance(result.requires_review, bool), \
            "requires_review must be a boolean"
    
    @given(
        user_type=st.sampled_from([ut.value for ut in UserType]),
        expense_category=st.sampled_from([ec.value for ec in ExpenseCategory])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_deductibility_consistency(
        self,
        user_type,
        expense_category
    ):
        """
        Property: Deductibility check is consistent across multiple calls
        
        Checking the same expense category and user type multiple times
        should always return the same result.
        """
        checker = DeductibilityChecker()
        
        result1 = checker.check(expense_category, user_type)
        result2 = checker.check(expense_category, user_type)
        result3 = checker.check(expense_category, user_type)
        
        # Assert consistency
        assert result1.is_deductible == result2.is_deductible == result3.is_deductible, \
            "Deductibility should be consistent across multiple checks"
        assert result1.reason == result2.reason == result3.reason, \
            "Reason should be consistent across multiple checks"
        assert result1.requires_review == result2.requires_review == result3.requires_review, \
            "requires_review should be consistent across multiple checks"
    
    def test_employee_limited_deductions(self):
        """
        Property: Employees have limited deductible expenses
        
        Requirements 5.1, 5.2: Employees can only deduct commuting and home office.
        Most business expenses are not deductible for employees.
        """
        checker = DeductibilityChecker()
        
        # Deductible for employees
        deductible_categories = [
            ExpenseCategory.COMMUTING,
            ExpenseCategory.HOME_OFFICE
        ]
        
        for category in deductible_categories:
            result = checker.check(category.value, UserType.EMPLOYEE.value)
            assert result.is_deductible, \
                f"{category.value} should be deductible for employees"
        
        # Not deductible for employees
        non_deductible_categories = [
            ExpenseCategory.GROCERIES,
            ExpenseCategory.OFFICE_SUPPLIES,
            ExpenseCategory.EQUIPMENT,
            ExpenseCategory.TRAVEL,
            ExpenseCategory.INSURANCE
        ]
        
        for category in non_deductible_categories:
            result = checker.check(category.value, UserType.EMPLOYEE.value)
            assert not result.is_deductible, \
                f"{category.value} should not be deductible for employees"
    
    def test_self_employed_broad_deductions(self):
        """
        Property: Self-employed have broad deductible expenses
        
        Requirements 6.1, 6.2: Self-employed can deduct most business expenses.
        """
        checker = DeductibilityChecker()
        
        # Fully deductible for self-employed
        deductible_categories = [
            ExpenseCategory.OFFICE_SUPPLIES,
            ExpenseCategory.EQUIPMENT,
            ExpenseCategory.TRAVEL,
            ExpenseCategory.MARKETING,
            ExpenseCategory.PROFESSIONAL_SERVICES,
            ExpenseCategory.INSURANCE,
            ExpenseCategory.UTILITIES,
            ExpenseCategory.HOME_OFFICE
        ]
        
        for category in deductible_categories:
            result = checker.check(category.value, UserType.SELF_EMPLOYED.value)
            assert result.is_deductible, \
                f"{category.value} should be deductible for self-employed"
        
        # Partially deductible (requires review)
        partial_categories = [
            ExpenseCategory.GROCERIES,
            ExpenseCategory.OTHER
        ]
        
        for category in partial_categories:
            result = checker.check(category.value, UserType.SELF_EMPLOYED.value)
            assert result.is_deductible, \
                f"{category.value} should be partially deductible for self-employed"
            assert result.requires_review, \
                f"{category.value} should require review for self-employed"
    
    def test_landlord_property_deductions(self):
        """
        Property: Landlords can deduct property-related expenses
        
        Requirements 5.1, 5.2: Landlords can deduct rental property expenses.
        """
        checker = DeductibilityChecker()
        
        # Deductible for landlords
        deductible_categories = [
            ExpenseCategory.MAINTENANCE,
            ExpenseCategory.PROPERTY_TAX,
            ExpenseCategory.LOAN_INTEREST,
            ExpenseCategory.INSURANCE,
            ExpenseCategory.UTILITIES,
            ExpenseCategory.PROFESSIONAL_SERVICES,
            ExpenseCategory.OFFICE_SUPPLIES
        ]
        
        for category in deductible_categories:
            result = checker.check(category.value, UserType.LANDLORD.value)
            assert result.is_deductible, \
                f"{category.value} should be deductible for landlords"
        
        # Not deductible for landlords
        result = checker.check(ExpenseCategory.GROCERIES.value, UserType.LANDLORD.value)
        assert not result.is_deductible, \
            "Groceries should not be deductible for landlords"
    
    def test_home_office_max_amount_for_employees(self):
        """
        Property: Home office deduction has maximum amount for employees
        
        Requirement 29.3: Home office flat-rate deduction is €300/year for employees.
        """
        checker = DeductibilityChecker()
        
        result = checker.check(
            ExpenseCategory.HOME_OFFICE.value,
            UserType.EMPLOYEE.value
        )
        
        assert result.is_deductible, \
            "Home office should be deductible for employees"
        assert result.max_amount == 300.00, \
            "Home office deduction should have max amount of €300 for employees"
    
    def test_unknown_category_not_deductible(self):
        """
        Property: Unknown expense categories are not deductible
        
        For safety, unknown categories should default to not deductible
        and require review.
        """
        checker = DeductibilityChecker()
        
        result = checker.check('unknown_category', UserType.EMPLOYEE.value)
        
        assert not result.is_deductible, \
            "Unknown category should not be deductible"
        assert result.requires_review, \
            "Unknown category should require review"
    
    def test_unknown_user_type_not_deductible(self):
        """
        Property: Unknown user types result in not deductible
        
        For safety, unknown user types should default to not deductible.
        """
        checker = DeductibilityChecker()
        
        result = checker.check(
            ExpenseCategory.OFFICE_SUPPLIES.value,
            'unknown_user_type'
        )
        
        assert not result.is_deductible, \
            "Unknown user type should result in not deductible"
    
    @given(
        user_type=st.sampled_from([ut.value for ut in UserType])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_is_deductible_matches_check_result(self, user_type):
        """
        Property: is_deductible() method matches check() result
        
        The convenience method is_deductible() should return the same
        boolean as the is_deductible field from check().
        """
        checker = DeductibilityChecker()
        
        for category in ExpenseCategory:
            check_result = checker.check(category.value, user_type)
            is_deductible = checker.is_deductible(category.value, user_type)
            
            assert check_result.is_deductible == is_deductible, \
                f"is_deductible() should match check().is_deductible for {category.value}"
    
    @given(
        user_type=st.sampled_from([ut.value for ut in UserType])
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_explain_deductibility_contains_key_info(self, user_type):
        """
        Property: explain_deductibility() contains all key information
        
        The explanation should include category, user type, deductibility status,
        and reason.
        """
        checker = DeductibilityChecker()
        
        for category in ExpenseCategory:
            explanation = checker.explain_deductibility(category.value, user_type)
            
            # Check that explanation contains key information
            assert category.value in explanation.lower(), \
                "Explanation should contain category"
            assert user_type in explanation.lower(), \
                "Explanation should contain user type"
            assert 'deductible' in explanation.lower(), \
                "Explanation should mention deductibility"
            assert 'reason' in explanation.lower(), \
                "Explanation should include reason"
    
    def test_get_deduction_rules_returns_dict(self):
        """
        Property: get_deduction_rules() returns a dictionary
        
        The method should return a dictionary of rules for the user type.
        """
        checker = DeductibilityChecker()
        
        for user_type in UserType:
            rules = checker.get_deduction_rules(user_type.value)
            
            assert isinstance(rules, dict), \
                f"get_deduction_rules should return dict for {user_type.value}"
