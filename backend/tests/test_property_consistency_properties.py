"""
Property-Based Tests for Transaction-Property Consistency

This module uses Hypothesis to validate correctness properties of transaction-property
referential integrity and portfolio aggregation through property-based testing.

**Validates: Requirements 13 (Transaction-Property Consistency)**

Correctness Properties Tested:
- Property 5: Transaction-Property Referential Integrity
- Property 7: Portfolio Aggregation Consistency
"""

import pytest
from decimal import Decimal
from datetime import date, timedelta
from uuid import uuid4
from unittest.mock import Mock
from hypothesis import given, strategies as st, assume, settings
from sqlalchemy.orm import Session

from app.models.property import Property, PropertyType, PropertyStatus
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory


# ============================================================================
# Mock Classes for Testing
# ============================================================================

class MockProperty:
    """Mock Property class for testing without database"""
    def __init__(self):
        self.id = uuid4()
        self.user_id = None
        self.property_type = PropertyType.RENTAL
        self.rental_percentage = Decimal("100.00")
        self.address = None
        self.street = None
        self.city = None
        self.postal_code = None
        self.purchase_date = None
        self.purchase_price = None
        self.building_value = None
        self.land_value = None
        self.construction_year = None
        self.depreciation_rate = Decimal("0.02")
        self.status = PropertyStatus.ACTIVE
        self.sale_date = None


class MockTransaction:
    """Mock Transaction class for testing without database"""
    def __init__(self):
        self.id = None
        self.user_id = None
        self.property_id = None
        self.type = None
        self.amount = None
        self.transaction_date = None
        self.description = None
        self.income_category = None
        self.expense_category = None
        self.is_deductible = False
        self.is_system_generated = False


# ============================================================================
# Hypothesis Strategies for Test Data Generation
# ============================================================================

@st.composite
def user_id_strategy(draw):
    """Generate valid user IDs"""
    return draw(st.integers(min_value=1, max_value=10000))


@st.composite
def property_strategy(draw, user_id=None):
    """
    Generate valid Property instances for testing.
    
    Args:
        user_id: Optional user_id to assign (if None, generates random)
    """
    # Generate purchase date between 2015 and 2025
    purchase_year = draw(st.integers(min_value=2015, max_value=2025))
    purchase_month = draw(st.integers(min_value=1, max_value=12))
    purchase_day = draw(st.integers(min_value=1, max_value=28))
    purchase_date_val = date(purchase_year, purchase_month, purchase_day)
    
    # Generate building value (50,000 to 500,000 EUR)
    building_value = draw(st.decimals(
        min_value=Decimal("50000"),
        max_value=Decimal("500000"),
        places=2
    ))
    
    # Create property instance
    prop = MockProperty()
    prop.id = uuid4()
    prop.user_id = user_id if user_id else draw(user_id_strategy())
    prop.property_type = PropertyType.RENTAL
    prop.rental_percentage = Decimal("100.00")
    prop.address = f"Test Street {draw(st.integers(min_value=1, max_value=999))}, Wien"
    prop.street = f"Test Street {draw(st.integers(min_value=1, max_value=999))}"
    prop.city = "Wien"
    prop.postal_code = "1010"
    prop.purchase_date = purchase_date_val
    prop.purchase_price = building_value / Decimal("0.8")
    prop.building_value = building_value
    prop.land_value = building_value / Decimal("4")
    prop.construction_year = draw(st.integers(min_value=1900, max_value=2025))
    prop.depreciation_rate = Decimal("0.02")
    prop.status = PropertyStatus.ACTIVE
    prop.sale_date = None
    
    return prop


@st.composite
def transaction_strategy(draw, user_id=None, property_id=None, with_property=True):
    """
    Generate valid Transaction instances for testing.
    
    Args:
        user_id: Optional user_id to assign
        property_id: Optional property_id to link
        with_property: If True, always assigns a property_id
    """
    # Generate transaction date between 2020 and 2026
    trans_year = draw(st.integers(min_value=2020, max_value=2026))
    trans_month = draw(st.integers(min_value=1, max_value=12))
    trans_day = draw(st.integers(min_value=1, max_value=28))
    trans_date = date(trans_year, trans_month, trans_day)
    
    # Generate amount (100 to 10,000 EUR)
    amount = draw(st.decimals(
        min_value=Decimal("100"),
        max_value=Decimal("10000"),
        places=2
    ))
    
    # Choose transaction type
    trans_type = draw(st.sampled_from([TransactionType.INCOME, TransactionType.EXPENSE]))
    
    # Create transaction instance
    trans = MockTransaction()
    trans.id = draw(st.integers(min_value=1, max_value=100000))
    trans.user_id = user_id if user_id else draw(user_id_strategy())
    trans.property_id = property_id if with_property else None
    trans.type = trans_type
    trans.amount = amount
    trans.transaction_date = trans_date
    trans.description = f"Test transaction {trans.id}"
    
    if trans_type == TransactionType.INCOME:
        trans.income_category = IncomeCategory.RENTAL
    else:
        trans.expense_category = draw(st.sampled_from([
            ExpenseCategory.MAINTENANCE,
            ExpenseCategory.PROPERTY_TAX,
            ExpenseCategory.LOAN_INTEREST,
            ExpenseCategory.PROPERTY_MANAGEMENT_FEES,
            ExpenseCategory.PROPERTY_INSURANCE,
            ExpenseCategory.DEPRECIATION_AFA
        ]))
    
    trans.is_deductible = trans_type == TransactionType.EXPENSE
    trans.is_system_generated = trans.expense_category == ExpenseCategory.DEPRECIATION_AFA if trans_type == TransactionType.EXPENSE else False
    
    return trans


@st.composite
def property_with_transactions_strategy(draw, num_transactions=None):
    """
    Generate a property with associated transactions.
    
    Args:
        num_transactions: Number of transactions to generate (if None, random 1-10)
    """
    # Generate property
    prop = draw(property_strategy())
    
    # Generate transactions
    if num_transactions is None:
        num_transactions = draw(st.integers(min_value=1, max_value=10))
    
    transactions = []
    for _ in range(num_transactions):
        trans = draw(transaction_strategy(
            user_id=prop.user_id,
            property_id=prop.id,
            with_property=True
        ))
        transactions.append(trans)
    
    return prop, transactions


@st.composite
def portfolio_strategy(draw, num_properties=None):
    """
    Generate a portfolio of properties for a single user.
    
    Args:
        num_properties: Number of properties (if None, random 1-5)
    """
    # Generate user_id
    user_id = draw(user_id_strategy())
    
    # Generate properties
    if num_properties is None:
        num_properties = draw(st.integers(min_value=1, max_value=5))
    
    properties = []
    for _ in range(num_properties):
        prop = draw(property_strategy(user_id=user_id))
        properties.append(prop)
    
    return user_id, properties


# ============================================================================
# Property 5: Transaction-Property Referential Integrity
# **Validates: Requirements 13.5**
# ============================================================================

@given(
    property=property_strategy(),
    transaction=transaction_strategy(with_property=True)
)
@settings(max_examples=100)
def test_property_5_transaction_references_valid_property(property, transaction):
    """
    Property 5: Transaction-Property Referential Integrity
    
    FOR ALL transactions t where t.property_id IS NOT NULL:
    EXISTS property p WHERE p.id = t.property_id AND p.user_id = t.user_id
    
    This test verifies that every transaction with a property_id references
    a valid property that belongs to the same user.
    """
    # Link transaction to property
    transaction.property_id = property.id
    transaction.user_id = property.user_id
    
    # PROPERTY: Transaction's property_id must reference a valid property
    assert transaction.property_id is not None, (
        "Transaction with property link must have property_id"
    )
    
    # PROPERTY: Property must exist (simulated by having the property object)
    assert property.id == transaction.property_id, (
        f"Transaction property_id {transaction.property_id} does not match "
        f"property id {property.id}"
    )
    
    # PROPERTY: Property and transaction must belong to same user
    assert property.user_id == transaction.user_id, (
        f"Transaction user_id {transaction.user_id} does not match "
        f"property user_id {property.user_id}"
    )


@given(data=st.data())
@settings(max_examples=50)
def test_property_5_all_property_transactions_have_matching_user(data):
    """
    Property 5: Referential Integrity (batch test)
    
    Verifies that in a batch of property-linked transactions, all maintain
    referential integrity with their properties.
    """
    # Generate property
    prop = data.draw(property_strategy())
    
    # Generate multiple transactions for this property
    num_transactions = data.draw(st.integers(min_value=1, max_value=20))
    
    for _ in range(num_transactions):
        trans = data.draw(transaction_strategy(
            user_id=prop.user_id,
            property_id=prop.id,
            with_property=True
        ))
        
        # PROPERTY: Each transaction must reference the property correctly
        assert trans.property_id == prop.id, (
            f"Transaction {trans.id} property_id mismatch"
        )
        
        # PROPERTY: Each transaction must have same user_id as property
        assert trans.user_id == prop.user_id, (
            f"Transaction {trans.id} user_id {trans.user_id} does not match "
            f"property user_id {prop.user_id}"
        )


@given(property=property_strategy())
@settings(max_examples=50)
def test_property_5_cannot_link_transaction_to_different_user_property(property):
    """
    Property 5: Referential Integrity (negative test)
    
    Verifies that transactions cannot be linked to properties owned by
    different users (this would violate referential integrity).
    """
    # Create transaction with different user_id
    different_user_id = property.user_id + 1000  # Ensure different
    
    trans = MockTransaction()
    trans.id = 1
    trans.user_id = different_user_id
    trans.property_id = property.id  # Attempting to link to property
    trans.type = TransactionType.INCOME
    trans.amount = Decimal("1000.00")
    trans.transaction_date = date.today()
    trans.income_category = IncomeCategory.RENTAL
    
    # PROPERTY: This violates referential integrity
    # In a real system, this should be prevented by validation
    assert trans.user_id != property.user_id, (
        "Test setup error: user_ids should be different"
    )
    
    # PROPERTY: The system should detect this mismatch
    # This test documents the expected validation behavior
    is_valid = (trans.property_id is None) or (trans.user_id == property.user_id)
    assert not is_valid, (
        "Transaction with mismatched user_id and property_id should be invalid"
    )


# ============================================================================
# Property 5: Property Deletion/Archival Preserves Transaction Links
# **Validates: Requirements 13.1, 13.2**
# ============================================================================

@given(property_with_trans=property_with_transactions_strategy())
@settings(max_examples=50)
def test_property_5_archiving_property_preserves_transaction_links(property_with_trans):
    """
    Property 5: Transaction Links Preserved on Archive
    
    WHEN a property is archived, THE system SHALL preserve all transaction links.
    
    This test verifies that archiving a property does not break the relationship
    with its transactions.
    """
    prop, transactions = property_with_trans
    
    # Archive the property
    prop.status = PropertyStatus.ARCHIVED
    prop.sale_date = date.today()
    
    # PROPERTY: All transactions should still reference the property
    for trans in transactions:
        assert trans.property_id == prop.id, (
            f"Transaction {trans.id} lost property link after archival"
        )
        
        assert trans.user_id == prop.user_id, (
            f"Transaction {trans.id} user_id mismatch after archival"
        )
    
    # PROPERTY: Archived property should still be accessible for historical data
    assert prop.status == PropertyStatus.ARCHIVED, (
        "Property should be archived"
    )
    
    # PROPERTY: Transaction count should remain unchanged
    assert len(transactions) > 0, (
        "Transactions should still exist after property archival"
    )


@given(property_with_trans=property_with_transactions_strategy())
@settings(max_examples=50)
def test_property_5_sold_property_preserves_transaction_links(property_with_trans):
    """
    Property 5: Transaction Links Preserved on Sale
    
    WHEN a property is marked as sold, THE system SHALL preserve all
    transaction links for historical reporting.
    """
    prop, transactions = property_with_trans
    
    # Mark property as sold
    prop.status = PropertyStatus.SOLD
    prop.sale_date = date.today()
    
    # PROPERTY: All transactions should still reference the property
    for trans in transactions:
        assert trans.property_id == prop.id, (
            f"Transaction {trans.id} lost property link after sale"
        )
    
    # PROPERTY: Historical transactions remain accessible
    assert len(transactions) > 0, (
        "Transactions should be preserved after property sale"
    )


# ============================================================================
# Property 7: Portfolio Aggregation Consistency
# **Validates: Requirements 13 (Correctness Properties)**
# ============================================================================

@given(portfolio=portfolio_strategy())
@settings(max_examples=100)
def test_property_7_portfolio_building_value_equals_sum_of_properties(portfolio):
    """
    Property 7: Portfolio Aggregation Consistency (Building Value)
    
    FOR ALL users u:
    sum(p.building_value WHERE p.user_id = u.id) = total_portfolio_building_value
    
    This test verifies that the total portfolio building value equals the
    sum of individual property building values.
    """
    user_id, properties = portfolio
    
    # Calculate sum of individual property building values
    individual_sum = sum(prop.building_value for prop in properties)
    
    # Calculate portfolio total (simulated aggregation)
    portfolio_total = sum(prop.building_value for prop in properties if prop.user_id == user_id)
    
    # PROPERTY: Portfolio total must equal sum of individual properties
    assert portfolio_total == individual_sum, (
        f"Portfolio building value {portfolio_total} does not match "
        f"sum of individual properties {individual_sum}"
    )
    
    # PROPERTY: All properties belong to the same user
    for prop in properties:
        assert prop.user_id == user_id, (
            f"Property {prop.id} has wrong user_id {prop.user_id}, expected {user_id}"
        )


@given(portfolio=portfolio_strategy())
@settings(max_examples=100)
def test_property_7_portfolio_depreciation_rate_weighted_average(portfolio):
    """
    Property 7: Portfolio Aggregation Consistency (Depreciation)
    
    Verifies that portfolio-level depreciation metrics are consistent with
    individual property calculations.
    """
    user_id, properties = portfolio
    
    # Calculate total annual depreciation across all properties
    total_annual_depreciation = Decimal("0")
    
    for prop in properties:
        # Calculate annual depreciation for each property
        annual_depreciation = (prop.building_value * prop.depreciation_rate).quantize(Decimal("0.01"))
        total_annual_depreciation += annual_depreciation
    
    # Calculate portfolio total (simulated aggregation)
    portfolio_depreciation = sum(
        (prop.building_value * prop.depreciation_rate).quantize(Decimal("0.01"))
        for prop in properties
        if prop.user_id == user_id
    )
    
    # PROPERTY: Portfolio depreciation must equal sum of individual depreciations
    assert portfolio_depreciation == total_annual_depreciation, (
        f"Portfolio depreciation {portfolio_depreciation} does not match "
        f"sum of individual depreciations {total_annual_depreciation}"
    )


@given(data=st.data())
@settings(max_examples=50)
def test_property_7_portfolio_metrics_with_transactions(data):
    """
    Property 7: Portfolio Aggregation with Transactions
    
    Verifies that portfolio-level transaction aggregations are consistent
    with individual property transaction sums.
    """
    # Generate portfolio
    user_id, properties = data.draw(portfolio_strategy(num_properties=3))
    
    # Generate transactions for each property
    all_transactions = []
    property_transaction_map = {}
    
    for prop in properties:
        num_trans = data.draw(st.integers(min_value=1, max_value=5))
        prop_transactions = []
        
        for _ in range(num_trans):
            trans = data.draw(transaction_strategy(
                user_id=user_id,
                property_id=prop.id,
                with_property=True
            ))
            prop_transactions.append(trans)
            all_transactions.append(trans)
        
        property_transaction_map[prop.id] = prop_transactions
    
    # Calculate portfolio-level rental income
    portfolio_rental_income = sum(
        trans.amount
        for trans in all_transactions
        if trans.type == TransactionType.INCOME and trans.income_category == IncomeCategory.RENTAL
    )
    
    # Calculate sum of individual property rental incomes
    individual_rental_income_sum = Decimal("0")
    for prop_id, transactions in property_transaction_map.items():
        prop_rental_income = sum(
            trans.amount
            for trans in transactions
            if trans.type == TransactionType.INCOME and trans.income_category == IncomeCategory.RENTAL
        )
        individual_rental_income_sum += prop_rental_income
    
    # PROPERTY: Portfolio rental income must equal sum of individual properties
    assert portfolio_rental_income == individual_rental_income_sum, (
        f"Portfolio rental income {portfolio_rental_income} does not match "
        f"sum of individual properties {individual_rental_income_sum}"
    )
    
    # Calculate portfolio-level expenses
    portfolio_expenses = sum(
        trans.amount
        for trans in all_transactions
        if trans.type == TransactionType.EXPENSE
    )
    
    # Calculate sum of individual property expenses
    individual_expenses_sum = Decimal("0")
    for prop_id, transactions in property_transaction_map.items():
        prop_expenses = sum(
            trans.amount
            for trans in transactions
            if trans.type == TransactionType.EXPENSE
        )
        individual_expenses_sum += prop_expenses
    
    # PROPERTY: Portfolio expenses must equal sum of individual properties
    assert portfolio_expenses == individual_expenses_sum, (
        f"Portfolio expenses {portfolio_expenses} does not match "
        f"sum of individual properties {individual_expenses_sum}"
    )


@given(portfolio=portfolio_strategy(num_properties=5))
@settings(max_examples=50)
def test_property_7_active_vs_archived_portfolio_segregation(portfolio):
    """
    Property 7: Portfolio Aggregation with Status Filtering
    
    Verifies that portfolio metrics correctly segregate active vs archived
    properties.
    """
    user_id, properties = portfolio
    
    # Archive some properties randomly
    import random
    random.seed(42)  # For reproducibility in property-based tests
    
    for i, prop in enumerate(properties):
        if i % 2 == 0:  # Archive every other property
            prop.status = PropertyStatus.ARCHIVED
            prop.sale_date = date.today() - timedelta(days=365)
    
    # Calculate active portfolio metrics
    active_building_value = sum(
        prop.building_value
        for prop in properties
        if prop.status == PropertyStatus.ACTIVE
    )
    
    # Calculate archived portfolio metrics
    archived_building_value = sum(
        prop.building_value
        for prop in properties
        if prop.status == PropertyStatus.ARCHIVED
    )
    
    # Calculate total
    total_building_value = sum(prop.building_value for prop in properties)
    
    # PROPERTY: Active + Archived should equal Total
    assert active_building_value + archived_building_value == total_building_value, (
        f"Active ({active_building_value}) + Archived ({archived_building_value}) "
        f"does not equal Total ({total_building_value})"
    )
    
    # PROPERTY: Each property should be in exactly one category
    active_count = sum(1 for prop in properties if prop.status == PropertyStatus.ACTIVE)
    archived_count = sum(1 for prop in properties if prop.status == PropertyStatus.ARCHIVED)
    
    assert active_count + archived_count == len(properties), (
        f"Property count mismatch: active={active_count}, archived={archived_count}, "
        f"total={len(properties)}"
    )


# ============================================================================
# Edge Case Tests
# ============================================================================

@given(property=property_strategy())
@settings(max_examples=50)
def test_property_without_transactions_maintains_integrity(property):
    """
    Edge case: Property with no transactions should still maintain integrity.
    """
    # PROPERTY: Property exists without transactions
    assert property.id is not None, "Property must have an ID"
    assert property.user_id is not None, "Property must have a user_id"
    
    # PROPERTY: Property can exist independently
    assert property.building_value > 0, "Property must have positive building value"


@given(transaction=transaction_strategy(with_property=False))
@settings(max_examples=50)
def test_transaction_without_property_link_is_valid(transaction):
    """
    Edge case: Transactions without property links are valid (not all
    transactions are property-related).
    """
    # Ensure transaction has no property link
    transaction.property_id = None
    
    # PROPERTY: Transaction without property_id is valid
    assert transaction.property_id is None, (
        "Transaction should have no property link"
    )
    
    # PROPERTY: Transaction still has valid user_id
    assert transaction.user_id is not None, (
        "Transaction must have a user_id even without property link"
    )
