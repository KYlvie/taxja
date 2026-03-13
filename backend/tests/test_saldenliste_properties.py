"""
Property-based tests for Saldenliste reports.

Feature: saldenliste-reports
"""

from decimal import Decimal

import pytest
from hypothesis import given, settings, strategies as st

from app.models.user import UserType
from app.models.transaction import TransactionType, IncomeCategory, ExpenseCategory
from app.services.saldenliste_service import get_account_plan, _map_transaction_to_konto, _compute_yearly_balances, _compute_monthly_balances, _compute_deviation, _group_by_kontenklasse, _group_by_kontenklasse_monthly, _build_summary_totals


# EA user types use simplified account plan (Kontenklasse 4 + 7 only)
EA_USER_TYPES = {UserType.EMPLOYEE, UserType.SELF_EMPLOYED, UserType.LANDLORD, UserType.MIXED}


class TestAccountPlanByUserType:
    """
    # Feature: saldenliste-reports, Property 1: 用户类型决定科目体系

    For any user type:
    - EA users (employee, self_employed, landlord, mixed) → only Kontenklasse 4 and 7
    - GmbH users → full Kontenklassen 0-9

    **Validates: Requirements 1.1, 1.2**
    """

    @given(user_type=st.sampled_from(list(UserType)))
    @settings(max_examples=100)
    def test_ea_users_only_have_kontenklasse_4_and_7(self, user_type: UserType):
        """EA users get only Kontenklasse 4 (income) and 7 (expense);
        GmbH users get the full range 0-9."""
        accounts = get_account_plan(user_type)

        assert len(accounts) > 0, "Account plan must not be empty"

        klassen = {a.kontenklasse for a in accounts}

        if user_type in EA_USER_TYPES:
            # EA users: exactly Kontenklasse 4 and 7
            assert klassen == {4, 7}, (
                f"EA user type {user_type.value} should only have Kontenklasse {{4, 7}}, "
                f"got {klassen}"
            )
        else:
            # GmbH: must cover all Kontenklassen 0-9
            assert klassen == set(range(10)), (
                f"GmbH user should have Kontenklassen 0-9, got {klassen}"
            )


class _FakeTransaction:
    """Lightweight stand-in for a Transaction ORM object."""

    __slots__ = ("type", "income_category", "expense_category")

    def __init__(self, type: TransactionType, income_category=None, expense_category=None):
        self.type = type
        self.income_category = income_category
        self.expense_category = expense_category


# Income kontenklassen by plan type
_EA_INCOME_KLASSEN = {4}
_EA_EXPENSE_KLASSEN = {7}
_GMBH_INCOME_KLASSEN = {4}
_GMBH_EXPENSE_KLASSEN = {5, 7, 8}


class TestTransactionToKontoMapping:
    """
    # Feature: saldenliste-reports, Property 2: 交易到科目的映射一致性

    For any valid transaction with an income_category or expense_category,
    `_map_transaction_to_konto` returns a konto that exists in the account plan
    and belongs to the correct Kontenklasse (income → income accounts,
    expense → expense accounts).

    **Validates: Requirements 1.3**
    """

    @given(
        user_type=st.sampled_from(list(UserType)),
        income_category=st.sampled_from(list(IncomeCategory)),
    )
    @settings(max_examples=100)
    def test_income_transaction_maps_to_valid_income_konto(
        self, user_type: UserType, income_category: IncomeCategory
    ):
        """An income transaction maps to a konto that exists in the plan
        and belongs to an income-type Kontenklasse."""
        account_plan = get_account_plan(user_type)
        txn = _FakeTransaction(
            type=TransactionType.INCOME,
            income_category=income_category,
            expense_category=None,
        )

        konto = _map_transaction_to_konto(txn, account_plan)

        # The returned konto must exist in the account plan
        plan_kontos = {a.konto for a in account_plan}
        assert konto in plan_kontos, (
            f"Mapped konto '{konto}' not found in account plan for {user_type.value}"
        )

        # The konto must belong to an income-type Kontenklasse
        matched = next(a for a in account_plan if a.konto == konto)
        if user_type in EA_USER_TYPES:
            expected_klassen = _EA_INCOME_KLASSEN
        else:
            expected_klassen = _GMBH_INCOME_KLASSEN

        assert matched.kontenklasse in expected_klassen, (
            f"Income transaction mapped to Kontenklasse {matched.kontenklasse} "
            f"(expected one of {expected_klassen}) for {user_type.value}"
        )

    @given(
        user_type=st.sampled_from(list(UserType)),
        expense_category=st.sampled_from(list(ExpenseCategory)),
    )
    @settings(max_examples=100)
    def test_expense_transaction_maps_to_valid_expense_konto(
        self, user_type: UserType, expense_category: ExpenseCategory
    ):
        """An expense transaction maps to a konto that exists in the plan
        and belongs to an expense-type Kontenklasse."""
        account_plan = get_account_plan(user_type)
        txn = _FakeTransaction(
            type=TransactionType.EXPENSE,
            income_category=None,
            expense_category=expense_category,
        )

        konto = _map_transaction_to_konto(txn, account_plan)

        # The returned konto must exist in the account plan
        plan_kontos = {a.konto for a in account_plan}
        assert konto in plan_kontos, (
            f"Mapped konto '{konto}' not found in account plan for {user_type.value}"
        )

        # The konto must belong to an expense-type Kontenklasse
        matched = next(a for a in account_plan if a.konto == konto)
        if user_type in EA_USER_TYPES:
            expected_klassen = _EA_EXPENSE_KLASSEN
        else:
            expected_klassen = _GMBH_EXPENSE_KLASSEN

        assert matched.kontenklasse in expected_klassen, (
            f"Expense transaction mapped to Kontenklasse {matched.kontenklasse} "
            f"(expected one of {expected_klassen}) for {user_type.value}"
        )


class TestAccountLabelCompleteness:
    """
    # Feature: saldenliste-reports, Property 11: 科目三语标签完整性

    For any account definition in both EA and GmbH account plans,
    label_de, label_en, and label_zh must all be non-empty strings.

    **Validates: Requirements 8.1**
    """

    @given(user_type=st.sampled_from(list(UserType)))
    @settings(max_examples=100)
    def test_all_accounts_have_non_empty_trilingual_labels(self, user_type: UserType):
        """Every account returned by get_account_plan must have non-empty
        label_de, label_en, and label_zh strings."""
        accounts = get_account_plan(user_type)

        for account in accounts:
            assert isinstance(account.label_de, str) and len(account.label_de) > 0, (
                f"Account {account.konto}: label_de is empty or not a string"
            )
            assert isinstance(account.label_en, str) and len(account.label_en) > 0, (
                f"Account {account.konto}: label_en is empty or not a string"
            )
            assert isinstance(account.label_zh, str) and len(account.label_zh) > 0, (
                f"Account {account.konto}: label_zh is empty or not a string"
            )


class _FakeTransactionWithAmount:
    """Lightweight stand-in for a Transaction ORM object, including amount."""

    __slots__ = ("type", "income_category", "expense_category", "amount")

    def __init__(
        self,
        type: TransactionType,
        income_category=None,
        expense_category=None,
        amount: Decimal = Decimal("0"),
    ):
        self.type = type
        self.income_category = income_category
        self.expense_category = expense_category
        self.amount = amount


@st.composite
def transaction_list(draw):
    """Generate a (user_type, list-of-transactions) pair for property testing."""
    user_type = draw(st.sampled_from(list(UserType)))
    n = draw(st.integers(min_value=0, max_value=20))
    txns = []
    for _ in range(n):
        is_income = draw(st.booleans())
        if is_income:
            cat = draw(st.sampled_from(list(IncomeCategory)))
            txn = _FakeTransactionWithAmount(
                type=TransactionType.INCOME,
                income_category=cat,
                expense_category=None,
                amount=Decimal(
                    str(
                        draw(
                            st.floats(
                                min_value=0.01,
                                max_value=100000,
                                allow_nan=False,
                                allow_infinity=False,
                            )
                        )
                    )
                ),
            )
        else:
            cat = draw(st.sampled_from(list(ExpenseCategory)))
            txn = _FakeTransactionWithAmount(
                type=TransactionType.EXPENSE,
                income_category=None,
                expense_category=cat,
                amount=Decimal(
                    str(
                        draw(
                            st.floats(
                                min_value=0.01,
                                max_value=100000,
                                allow_nan=False,
                                allow_infinity=False,
                            )
                        )
                    )
                ),
            )
        txns.append(txn)
    return user_type, txns


class TestYearlyBalanceCorrectness:
    """
    # Feature: saldenliste-reports, Property 3: 年度余额计算正确性

    For any set of transactions and account plan, the Saldo computed by
    `_compute_yearly_balances` for each konto must equal the sum of amounts
    of all transactions that map to that konto.

    **Validates: Requirements 2.2, 2.3**
    """

    @given(data=transaction_list())
    @settings(max_examples=100)
    def test_yearly_balance_equals_sum_of_mapped_amounts(self, data):
        """Each konto's Saldo equals the sum of amounts of transactions mapped to it."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        # Compute balances using the service function under test
        balances = _compute_yearly_balances(txns, account_plan)

        # Manually compute expected balances by mapping each transaction
        expected: dict[str, Decimal] = {acct.konto: Decimal("0") for acct in account_plan}
        for txn in txns:
            konto = _map_transaction_to_konto(txn, account_plan)
            expected[konto] += txn.amount

        # Assert every konto matches
        for konto, expected_saldo in expected.items():
            actual_saldo = balances.get(konto, Decimal("0"))
            assert actual_saldo == expected_saldo, (
                f"Konto {konto}: expected {expected_saldo}, got {actual_saldo} "
                f"(user_type={user_type.value}, {len(txns)} transactions)"
            )

        # Also verify no extra kontos appear in the result
        plan_kontos = {acct.konto for acct in account_plan}
        for konto in balances:
            assert konto in plan_kontos, (
                f"Unexpected konto '{konto}' in balances (not in account plan)"
            )


# Strategy for generating finite Decimal values with 2 decimal places
_decimal_strategy = st.decimals(
    min_value=-1000000, max_value=1000000, allow_nan=False, allow_infinity=False, places=2
)


class TestDeviationCalculation:
    """
    # Feature: saldenliste-reports, Property 4: 偏差计算正确性（含除零保护）

    For any two Decimal values current and prior:
    - Absolute deviation = current - prior
    - When prior != 0: percentage = (current - prior) / prior * 100
    - When prior == 0: percentage is None (division-by-zero protection)

    **Validates: Requirements 2.4, 2.5**
    """

    @given(current=_decimal_strategy, prior=_decimal_strategy.filter(lambda x: x != Decimal("0")))
    @settings(max_examples=100)
    def test_deviation_with_nonzero_prior(self, current: Decimal, prior: Decimal):
        """When prior != 0, abs deviation = current - prior and
        pct deviation = (current - prior) / prior * 100."""
        result = _compute_deviation(current, prior)

        expected_abs = current - prior
        expected_pct = (current - prior) / prior * Decimal("100")

        assert result["abs"] == expected_abs, (
            f"Absolute deviation: expected {expected_abs}, got {result['abs']}"
        )
        assert result["pct"] == expected_pct, (
            f"Percentage deviation: expected {expected_pct}, got {result['pct']}"
        )

    @given(current=_decimal_strategy)
    @settings(max_examples=100)
    def test_deviation_with_zero_prior(self, current: Decimal):
        """When prior == 0, abs deviation = current - 0 = current and
        pct deviation is None (division-by-zero protection)."""
        result = _compute_deviation(current, Decimal("0"))

        assert result["abs"] == current, (
            f"Absolute deviation with zero prior: expected {current}, got {result['abs']}"
        )
        assert result["pct"] is None, (
            f"Percentage deviation should be None when prior is 0, got {result['pct']}"
        )


class TestKontenklasseGroupInvariant:
    """
    # Feature: saldenliste-reports, Property 5: Kontenklasse 分组不变量

    For any set of account balances grouped by Kontenklasse:
    - Every account within a group has the same Kontenklasse as the group
    - All accounts from the plan appear exactly once across all groups
      (no duplicates, no missing)

    **Validates: Requirements 2.6, 3.4**
    """

    @given(data=transaction_list())
    @settings(max_examples=100)
    def test_group_accounts_share_kontenklasse_and_cover_plan(self, data):
        """Each group's accounts share the group's Kontenklasse, and every
        account in the plan appears exactly once across all groups."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        # Build balances from transactions, then group
        balances = _compute_yearly_balances(txns, account_plan)
        groups = _group_by_kontenklasse(balances, account_plan)

        # Build a lookup: konto -> expected kontenklasse
        konto_to_kk = {acct.konto: acct.kontenklasse for acct in account_plan}

        # 1) Every account in a group must have the same Kontenklasse as the group
        seen_kontos: list[str] = []
        for group in groups:
            group_kk = group["kontenklasse"]
            for account in group["accounts"]:
                konto = account["konto"]
                assert konto in konto_to_kk, (
                    f"Konto '{konto}' in group {group_kk} not found in account plan"
                )
                assert konto_to_kk[konto] == group_kk, (
                    f"Konto '{konto}' has Kontenklasse {konto_to_kk[konto]} "
                    f"but is placed in group {group_kk}"
                )
                seen_kontos.append(konto)

        # 2) All accounts from the plan appear exactly once (no duplicates, no missing)
        plan_kontos = sorted(acct.konto for acct in account_plan)
        seen_sorted = sorted(seen_kontos)

        assert seen_sorted == plan_kontos, (
            f"Account coverage mismatch.\n"
            f"  Missing: {sorted(set(plan_kontos) - set(seen_kontos))}\n"
            f"  Duplicates: {sorted(k for k in seen_kontos if seen_kontos.count(k) > 1)}\n"
            f"  Extra: {sorted(set(seen_kontos) - set(plan_kontos))}"
        )


class TestSubtotalEqualsAccountSum:
    """
    # Feature: saldenliste-reports, Property 6: 小计等于组内科目之和

    For any Kontenklasse group produced by `_group_by_kontenklasse`,
    the group's subtotal must equal the sum of all account saldos
    within that group:
    - subtotal == Σ account["saldo"] for each group

    **Validates: Requirements 2.7, 3.5**
    """

    @given(data=transaction_list())
    @settings(max_examples=100)
    def test_subtotal_equals_sum_of_account_saldos(self, data):
        """Each group's subtotal equals the sum of its accounts' saldo values."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        # Compute balances and group them
        balances = _compute_yearly_balances(txns, account_plan)
        groups = _group_by_kontenklasse(balances, account_plan)

        for group in groups:
            expected_subtotal = sum(
                (acct["saldo"] for acct in group["accounts"]), Decimal("0")
            )
            assert group["subtotal"] == expected_subtotal, (
                f"Kontenklasse {group['kontenklasse']}: "
                f"subtotal {group['subtotal']} != sum of saldos {expected_subtotal} "
                f"(user_type={user_type.value}, {len(txns)} transactions)"
            )


class TestGewinnVerlustEqualsErtragMinusAufwand:
    """
    # Feature: saldenliste-reports, Property 7: Gewinn/Verlust = Ertrag - Aufwand

    For any set of transactions and user type, the summary row's
    gewinn_verlust must equal ertrag minus aufwand.

    **Validates: Requirements 2.8, 3.6**
    """

    @given(data=transaction_list())
    @settings(max_examples=100)
    def test_gewinn_verlust_equals_ertrag_minus_aufwand(self, data):
        """Summary gewinn_verlust == ertrag - aufwand for any transaction set."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        balances = _compute_yearly_balances(txns, account_plan)
        groups = _group_by_kontenklasse(balances, account_plan)
        summary = _build_summary_totals(groups, user_type)

        expected = summary["ertrag"] - summary["aufwand"]
        assert summary["gewinn_verlust"] == expected, (
            f"gewinn_verlust {summary['gewinn_verlust']} != "
            f"ertrag {summary['ertrag']} - aufwand {summary['aufwand']} = {expected} "
            f"(user_type={user_type.value}, {len(txns)} transactions)"
        )


# ── Helpers for monthly balance tests ────────────────────────────────────


class _FakeDate:
    """Lightweight stand-in for a date object with a .month attribute."""

    __slots__ = ("month",)

    def __init__(self, month: int):
        self.month = month


class _FakeTransactionWithDate:
    """Lightweight stand-in for a Transaction ORM object, including amount and date."""

    __slots__ = ("type", "income_category", "expense_category", "amount", "transaction_date")

    def __init__(
        self,
        type: TransactionType,
        income_category=None,
        expense_category=None,
        amount: Decimal = Decimal("0"),
        transaction_date=None,
    ):
        self.type = type
        self.income_category = income_category
        self.expense_category = expense_category
        self.amount = amount
        self.transaction_date = transaction_date


@st.composite
def monthly_transaction_list(draw):
    """Generate a (user_type, list-of-transactions-with-dates) pair for monthly property testing."""
    user_type = draw(st.sampled_from(list(UserType)))
    n = draw(st.integers(min_value=0, max_value=20))
    txns = []
    for _ in range(n):
        month = draw(st.integers(min_value=1, max_value=12))
        is_income = draw(st.booleans())
        if is_income:
            cat = draw(st.sampled_from(list(IncomeCategory)))
            txn = _FakeTransactionWithDate(
                type=TransactionType.INCOME,
                income_category=cat,
                expense_category=None,
                amount=Decimal(
                    str(
                        draw(
                            st.floats(
                                min_value=0.01,
                                max_value=100000,
                                allow_nan=False,
                                allow_infinity=False,
                            )
                        )
                    )
                ),
                transaction_date=_FakeDate(month),
            )
        else:
            cat = draw(st.sampled_from(list(ExpenseCategory)))
            txn = _FakeTransactionWithDate(
                type=TransactionType.EXPENSE,
                income_category=None,
                expense_category=cat,
                amount=Decimal(
                    str(
                        draw(
                            st.floats(
                                min_value=0.01,
                                max_value=100000,
                                allow_nan=False,
                                allow_infinity=False,
                            )
                        )
                    )
                ),
                transaction_date=_FakeDate(month),
            )
        txns.append(txn)
    return user_type, txns


class TestMonthlyBalanceCorrectness:
    """
    # Feature: saldenliste-reports, Property 8: 月度金额计算正确性

    For any set of transactions with dates and account plan,
    `_compute_monthly_balances` must produce per-konto per-month amounts
    that equal the sum of all transaction amounts mapped to that konto
    in that month.

    **Validates: Requirements 3.2**
    """

    @given(data=monthly_transaction_list())
    @settings(max_examples=100)
    def test_monthly_balance_equals_sum_of_mapped_amounts_per_month(self, data):
        """Each konto's monthly amount equals the sum of amounts of
        transactions mapped to it in that month."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        # Compute monthly balances using the service function under test
        monthly_balances = _compute_monthly_balances(txns, account_plan)

        # Manually compute expected monthly balances
        expected: dict[str, dict[int, Decimal]] = {
            acct.konto: {m: Decimal("0") for m in range(1, 13)} for acct in account_plan
        }
        for txn in txns:
            konto = _map_transaction_to_konto(txn, account_plan)
            month = txn.transaction_date.month
            expected[konto][month] += txn.amount

        # Assert every konto + month matches
        for konto, months in expected.items():
            for month, expected_amount in months.items():
                actual_amount = monthly_balances.get(konto, {}).get(month, Decimal("0"))
                assert actual_amount == expected_amount, (
                    f"Konto {konto}, month {month}: "
                    f"expected {expected_amount}, got {actual_amount} "
                    f"(user_type={user_type.value}, {len(txns)} transactions)"
                )

        # Verify no extra kontos appear in the result
        plan_kontos = {acct.konto for acct in account_plan}
        for konto in monthly_balances:
            assert konto in plan_kontos, (
                f"Unexpected konto '{konto}' in monthly balances (not in account plan)"
            )


class TestYearlyTotalConsistency:
    """
    # Feature: saldenliste-reports, Property 9: 年度合计一致性

    For any account in the Periodensaldenliste grouped data:
    - gesamt == sum(months[0:12])
    - subtotal_gesamt == sum(subtotal_months[0:12])

    **Validates: Requirements 3.3, 3.7**
    """

    @given(data=monthly_transaction_list())
    @settings(max_examples=100)
    def test_account_gesamt_equals_sum_of_twelve_months(self, data):
        """Each account's gesamt must equal the sum of its 12 monthly amounts."""
        user_type, txns = data
        account_plan = get_account_plan(user_type)

        monthly_balances = _compute_monthly_balances(txns, account_plan)
        groups = _group_by_kontenklasse_monthly(monthly_balances, account_plan)

        for group in groups:
            # Verify each account: gesamt == sum(months)
            for account in group["accounts"]:
                expected_gesamt = sum(account["months"], Decimal("0"))
                assert account["gesamt"] == expected_gesamt, (
                    f"Konto {account['konto']}: "
                    f"gesamt {account['gesamt']} != sum(months) {expected_gesamt} "
                    f"(user_type={user_type.value}, {len(txns)} transactions)"
                )

            # Verify group subtotal: subtotal_gesamt == sum(subtotal_months)
            expected_subtotal_gesamt = sum(group["subtotal_months"], Decimal("0"))
            assert group["subtotal_gesamt"] == expected_subtotal_gesamt, (
                f"Kontenklasse {group['kontenklasse']}: "
                f"subtotal_gesamt {group['subtotal_gesamt']} != "
                f"sum(subtotal_months) {expected_subtotal_gesamt} "
                f"(user_type={user_type.value}, {len(txns)} transactions)"
            )


class TestUserDataIsolation:
    """
    # Feature: saldenliste-reports, Property 10: 用户数据隔离

    For any two independent sets of transactions (user A and user B),
    computing balances for user A's transactions must only reflect
    user A's data — none of user B's transaction amounts should appear
    in user A's balances.

    **Validates: Requirements 4.4**
    """

    @given(data_a=transaction_list(), data_b=transaction_list())
    @settings(max_examples=100)
    def test_user_a_balances_exclude_user_b_transactions(self, data_a, data_b):
        """Balances computed from user A's transactions must not include
        any of user B's transaction amounts."""
        user_type_a, txns_a = data_a
        _user_type_b, txns_b = data_b

        account_plan_a = get_account_plan(user_type_a)

        # Compute balances using ONLY user A's transactions
        balances_a = _compute_yearly_balances(txns_a, account_plan_a)

        # Manually compute expected balances from user A's transactions only
        expected: dict[str, Decimal] = {acct.konto: Decimal("0") for acct in account_plan_a}
        for txn in txns_a:
            konto = _map_transaction_to_konto(txn, account_plan_a)
            expected[konto] += txn.amount

        # The balances must match exactly what user A's transactions produce —
        # no contamination from user B's data
        for konto, expected_saldo in expected.items():
            actual_saldo = balances_a.get(konto, Decimal("0"))
            assert actual_saldo == expected_saldo, (
                f"Konto {konto}: expected {expected_saldo} from user A's transactions, "
                f"got {actual_saldo} — possible data leakage from user B"
            )

        # Total across all kontos must equal sum of user A's amounts only
        total_balance = sum(balances_a.values(), Decimal("0"))
        total_a_amounts = sum((txn.amount for txn in txns_a), Decimal("0"))
        assert total_balance == total_a_amounts, (
            f"Total balance {total_balance} != sum of user A amounts {total_a_amounts} — "
            f"possible data leakage from user B (user B total: "
            f"{sum((txn.amount for txn in txns_b), Decimal('0'))})"
        )

        # Verify that user B's unique amounts (not shared with user A) are absent
        # from user A's per-konto balances when user B has transactions
        if txns_b:
            # Compute what user B's balances would be on the same plan
            balances_b = _compute_yearly_balances(txns_b, account_plan_a)

            # Compute combined balances to show they would differ
            combined = _compute_yearly_balances(txns_a + txns_b, account_plan_a)

            # If user B has any non-zero balances, the combined result must
            # differ from user A's isolated result (proving isolation works)
            b_has_nonzero = any(v != Decimal("0") for v in balances_b.values())
            if b_has_nonzero:
                assert balances_a != combined, (
                    "User A's isolated balances should differ from combined balances "
                    "when user B has non-zero transactions — isolation not working"
                )
