"""
Bug Condition Exploration Tests — Document Group & Recurring Transaction Properties

These tests encode the EXPECTED (post-fix) behavior. They are designed to
FAIL on the current unfixed code, proving the bugs exist.

Test 1b: _stage_suggest should generate a recurring transaction suggestion
         for VERSICHERUNGSBESTAETIGUNG documents with praemie data.
         Bug: Currently it falls through to the else branch (Receipt/Invoice/Other).

Test 1c: create_loan_from_suggestion should support standalone loans without property_id.
         Bug: Currently it raises ValueError when property_id is missing.

Validates: Requirements 1.3, 1.4, 1.5
"""
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, date
from decimal import Decimal
from hypothesis import given, settings, assume, HealthCheck
from hypothesis import strategies as st


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

praemie_strategy = st.decimals(
    min_value=Decimal("10.00"),
    max_value=Decimal("50000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

frequency_strategy = st.sampled_from(["monthly", "quarterly", "annually"])

insurance_type_strategy = st.sampled_from([
    "Haushaltsversicherung",
    "Haftpflichtversicherung",
    "Lebensversicherung",
    "Krankenversicherung",
    "Unfallversicherung",
    "Rechtsschutzversicherung",
    "KFZ-Versicherung",
])

loan_amount_strategy = st.decimals(
    min_value=Decimal("1000.00"),
    max_value=Decimal("1000000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

interest_rate_strategy = st.decimals(
    min_value=Decimal("0.50"),
    max_value=Decimal("15.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)

monthly_payment_strategy = st.decimals(
    min_value=Decimal("50.00"),
    max_value=Decimal("10000.00"),
    places=2,
    allow_nan=False,
    allow_infinity=False,
)


# ---------------------------------------------------------------------------
# Test 1b: VERSICHERUNGSBESTAETIGUNG should generate recurring suggestion
# ---------------------------------------------------------------------------

class TestBugCondition1b_InsuranceRecurringSuggestion:
    """
    **Validates: Requirements 1.3, 1.5**

    Bug Condition: When a VERSICHERUNGSBESTAETIGUNG document with praemie data
    goes through _stage_suggest, the pipeline does NOT generate a recurring
    transaction suggestion. It falls into the else branch for Receipt/Invoice/Other.

    Expected (post-fix): _stage_suggest should have a dedicated branch for
    VERSICHERUNGSBESTAETIGUNG that generates a create_insurance_recurring suggestion.

    These tests assert the EXPECTED behavior — they will FAIL on unfixed code.
    """

    @given(
        praemie=praemie_strategy,
        frequency=frequency_strategy,
        insurance_type=insurance_type_strategy,
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_stage_suggest_generates_insurance_recurring_suggestion(
        self, praemie, frequency, insurance_type
    ):
        """
        For any VERSICHERUNGSBESTAETIGUNG document with valid praemie data,
        _stage_suggest should produce a suggestion with type containing
        'insurance' or 'recurring' — not just generic transaction suggestions.

        On unfixed code, VERSICHERUNGSBESTAETIGUNG falls into the else branch
        and only generates generic transaction suggestions, so this will FAIL.
        """
        from app.models.document import DocumentType as DBDocumentType

        # Import the orchestrator class
        from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

        # Create mock objects
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = mock_db
        orchestrator.logger = MagicMock()

        # Create a mock document with insurance OCR data
        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.user_id = 1
        mock_document.document_type = DBDocumentType.VERSICHERUNGSBESTAETIGUNG
        mock_document.ocr_result = {
            "praemie": float(praemie),
            "zahlungsfrequenz": frequency,
            "versicherungsart": insurance_type,
        }
        mock_document.uploaded_at = datetime(2024, 1, 15)
        mock_document.file_name = "versicherung_test.pdf"

        # Create a mock pipeline result
        mock_result = MagicMock()
        mock_result.suggestions = []
        mock_result.audit_log = []

        # Run _stage_suggest
        orchestrator._stage_suggest(
            document=mock_document,
            db_type=DBDocumentType.VERSICHERUNGSBESTAETIGUNG,
            ocr_result=mock_document.ocr_result,
            result=mock_result,
        )

        # EXPECTED (post-fix): At least one suggestion should be generated
        # that relates to insurance recurring transactions
        assert len(mock_result.suggestions) > 0, (
            f"Expected _stage_suggest to generate at least one suggestion for "
            f"VERSICHERUNGSBESTAETIGUNG with praemie={praemie}, but got none. "
            f"This confirms Bug Condition 1.3: insurance documents don't generate "
            f"recurring transaction suggestions."
        )

        # Check that at least one suggestion is insurance-related
        suggestion_types = []
        for s in mock_result.suggestions:
            if isinstance(s, dict):
                suggestion_types.append(s.get("type", ""))
            else:
                suggestion_types.append(getattr(s, "type", ""))

        has_insurance_suggestion = any(
            "insurance" in str(t).lower() or "recurring" in str(t).lower()
            for t in suggestion_types
        )
        assert has_insurance_suggestion, (
            f"Expected an insurance/recurring suggestion type, but got: {suggestion_types}. "
            f"This confirms Bug Condition 1.3+1.5: insurance premium data is not utilized."
        )


# ---------------------------------------------------------------------------
# Test 1c: Standalone loan (no property_id) should work
# ---------------------------------------------------------------------------

class TestBugCondition1c_StandaloneLoanRepayment:
    """
    **Validates: Requirements 1.4**

    Bug Condition: create_loan_from_suggestion raises ValueError when
    property_id is missing, because it requires a PropertyLoan which needs
    a property association.

    Expected (post-fix): The system should support creating standalone loan
    repayment recurring transactions without requiring property_id.

    These tests assert the EXPECTED behavior — they will FAIL on unfixed code.
    """

    @given(
        loan_amount=loan_amount_strategy,
        interest_rate=interest_rate_strategy,
        monthly_payment=monthly_payment_strategy,
    )
    @settings(
        max_examples=20,
        suppress_health_check=[HealthCheck.too_slow],
        deadline=None,
    )
    def test_create_loan_without_property_id_should_succeed(
        self, loan_amount, interest_rate, monthly_payment
    ):
        """
        For any valid loan data WITHOUT a property_id, the system should
        successfully create a standalone loan repayment recurring transaction.

        On unfixed code, create_loan_from_suggestion raises ValueError:
        "No property associated with this loan."
        This test will FAIL, confirming Bug Condition 1.4.
        """
        from app.tasks.ocr_tasks import create_loan_from_suggestion

        # Create mock DB session
        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Create mock document
        mock_document = MagicMock()
        mock_document.id = 100
        mock_document.user_id = 1
        mock_document.uploaded_at = datetime(2024, 3, 1)
        mock_document.ocr_result = {
            "loan_amount": float(loan_amount),
            "interest_rate": float(interest_rate),
            "monthly_payment": float(monthly_payment),
            "lender_name": "Test Bank",
        }

        # Suggestion data WITHOUT property_id (standalone loan like car loan)
        suggestion_data = {
            "loan_amount": float(loan_amount),
            "interest_rate": float(interest_rate),
            "monthly_payment": float(monthly_payment),
            "lender_name": "Test Bank",
            "start_date": "2024-03-01",
            "end_date": None,
            "matched_property_id": None,  # No property — standalone loan
        }

        # EXPECTED (post-fix): This should NOT raise an error.
        # On unfixed code, it raises ValueError about missing property.
        try:
            result = create_loan_from_suggestion(mock_db, mock_document, suggestion_data)
            # If we get here, the function succeeded (post-fix behavior)
            assert result is not None, "Expected a result dict from standalone loan creation"
        except ValueError as e:
            if "property" in str(e).lower() or "loan" in str(e).lower():
                # This is the bug! The function requires property_id but shouldn't
                pytest.fail(
                    f"create_loan_from_suggestion raised ValueError for standalone loan "
                    f"(no property_id): {e}. "
                    f"This confirms Bug Condition 1.4: standalone loans can't create "
                    f"loan repayment recurring transactions. "
                    f"Input: loan_amount={loan_amount}, interest_rate={interest_rate}, "
                    f"monthly_payment={monthly_payment}"
                )
            else:
                raise  # Re-raise unexpected ValueError



# ===========================================================================
# Preservation Tests — Task 2
#
# These tests capture the CURRENT (pre-fix) behavior for non-buggy inputs.
# They must PASS on unfixed code and continue to pass after the fix,
# ensuring no regressions.
#
# **Validates: Requirements 3.1, 3.2, 3.3, 3.4, 3.5, 3.6**
# ===========================================================================


# ---------------------------------------------------------------------------
# Preservation 2a: _stage_suggest behavior for non-VERSICHERUNGSBESTAETIGUNG
#                  and non-standalone-loan document types is unchanged
# ---------------------------------------------------------------------------

class TestPreservation2a_StageSuggestBehavior:
    """
    **Validates: Requirements 3.1, 3.2, 3.3, 3.4**

    Preservation: For document types that are NOT VERSICHERUNGSBESTAETIGUNG
    and NOT standalone-loan (LOAN_CONTRACT without property_id), the
    _stage_suggest method should behave exactly as it does today.

    - RENTAL_CONTRACT → calls _build_mietvertrag_suggestion (creates recurring income)
    - PURCHASE_CONTRACT → calls _build_kaufvertrag_suggestion (creates property)
    - LOAN_CONTRACT → calls _build_kreditvertrag_suggestion (creates loan suggestion)
    - Tax form types → calls _build_tax_form_suggestion
    - Others → calls _build_transaction_suggestions (generic transactions)
    """

    # Strategy: pick from document types that have dedicated _stage_suggest branches
    # (excluding VERSICHERUNGSBESTAETIGUNG which is the bug condition)
    non_bug_doc_types = st.sampled_from([
        "RENTAL_CONTRACT",
        "PURCHASE_CONTRACT",
        "LOAN_CONTRACT",
    ])

    @given(doc_type_name=st.just("RENTAL_CONTRACT"))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_rental_contract_calls_mietvertrag_suggestion(self, doc_type_name):
        """
        RENTAL_CONTRACT should route to _build_mietvertrag_suggestion in _stage_suggest.
        This preserves Requirement 3.1: rental contracts auto-generate rental income.
        """
        from app.models.document import DocumentType as DBDocumentType
        from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = mock_db
        orchestrator.logger = MagicMock()

        mock_document = MagicMock()
        mock_document.id = 1
        mock_document.user_id = 1
        mock_document.document_type = DBDocumentType.RENTAL_CONTRACT
        mock_document.ocr_result = {
            "monthly_rent": 850.00,
            "start_date": "2024-01-01",
            "property_address": "Teststraße 1, 1010 Wien",
        }
        mock_document.uploaded_at = datetime(2024, 1, 15)
        mock_document.file_name = "mietvertrag_test.pdf"

        mock_result = MagicMock()
        mock_result.suggestions = []
        mock_result.audit_log = []

        with patch.object(
            orchestrator, "_build_mietvertrag_suggestion", return_value={"type": "create_recurring_income"}
        ) as mock_build:
            orchestrator._stage_suggest(
                document=mock_document,
                db_type=DBDocumentType.RENTAL_CONTRACT,
                ocr_result=mock_document.ocr_result,
                result=mock_result,
            )
            mock_build.assert_called_once()

    @given(doc_type_name=st.just("PURCHASE_CONTRACT"))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_purchase_contract_calls_kaufvertrag_suggestion(self, doc_type_name):
        """
        PURCHASE_CONTRACT should route to _build_kaufvertrag_suggestion in _stage_suggest.
        This preserves Requirement 3.2: purchase contracts generate property creation.
        """
        from app.models.document import DocumentType as DBDocumentType
        from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = mock_db
        orchestrator.logger = MagicMock()

        mock_document = MagicMock()
        mock_document.id = 2
        mock_document.user_id = 1
        mock_document.document_type = DBDocumentType.PURCHASE_CONTRACT
        mock_document.ocr_result = {
            "purchase_price": 250000.00,
            "property_address": "Kaufstraße 5, 1020 Wien",
        }
        mock_document.uploaded_at = datetime(2024, 2, 10)
        mock_document.file_name = "kaufvertrag_test.pdf"

        mock_result = MagicMock()
        mock_result.suggestions = []
        mock_result.audit_log = []

        with patch.object(
            orchestrator, "_build_kaufvertrag_suggestion", return_value={"type": "create_property"}
        ) as mock_build:
            orchestrator._stage_suggest(
                document=mock_document,
                db_type=DBDocumentType.PURCHASE_CONTRACT,
                ocr_result=mock_document.ocr_result,
                result=mock_result,
            )
            mock_build.assert_called_once()

    @given(doc_type_name=st.just("LOAN_CONTRACT"))
    @settings(max_examples=5, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_loan_contract_calls_kreditvertrag_suggestion(self, doc_type_name):
        """
        LOAN_CONTRACT should route to _build_kreditvertrag_suggestion in _stage_suggest.
        This preserves Requirement 3.3: loan contracts with property_id continue
        to support PropertyLoan + loan_interest flow.
        """
        from app.models.document import DocumentType as DBDocumentType
        from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

        mock_db = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = None

        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = mock_db
        orchestrator.logger = MagicMock()

        mock_document = MagicMock()
        mock_document.id = 3
        mock_document.user_id = 1
        mock_document.document_type = DBDocumentType.LOAN_CONTRACT
        mock_document.ocr_result = {
            "loan_amount": 200000.00,
            "interest_rate": 3.5,
            "monthly_payment": 950.00,
        }
        mock_document.uploaded_at = datetime(2024, 3, 1)
        mock_document.file_name = "kreditvertrag_test.pdf"

        mock_result = MagicMock()
        mock_result.suggestions = []
        mock_result.audit_log = []

        with patch.object(
            orchestrator, "_build_kreditvertrag_suggestion", return_value={"type": "create_loan"}
        ) as mock_build:
            orchestrator._stage_suggest(
                document=mock_document,
                db_type=DBDocumentType.LOAN_CONTRACT,
                ocr_result=mock_document.ocr_result,
                result=mock_result,
            )
            mock_build.assert_called_once()

    @given(
        doc_type_name=st.sampled_from([
            "LOHNZETTEL", "L1_FORM", "L1K_BEILAGE", "L1AB_BEILAGE",
            "E1A_BEILAGE", "E1B_BEILAGE", "E1KV_BEILAGE",
            "U1_FORM", "U30_FORM", "JAHRESABSCHLUSS",
            "SVS_NOTICE", "PROPERTY_TAX", "BANK_STATEMENT",
        ])
    )
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_tax_form_types_route_to_tax_form_suggestion(self, doc_type_name):
        """
        All TAX_FORM_DB_TYPES should route to _build_tax_form_suggestion.
        This preserves Requirement 3.4: other group behaviors unchanged.
        """
        from app.models.document import DocumentType as DBDocumentType
        from app.services.document_pipeline_orchestrator import DocumentPipelineOrchestrator

        db_type = getattr(DBDocumentType, doc_type_name)

        mock_db = MagicMock()
        orchestrator = DocumentPipelineOrchestrator.__new__(DocumentPipelineOrchestrator)
        orchestrator.db = mock_db
        orchestrator.logger = MagicMock()

        mock_document = MagicMock()
        mock_document.id = 10
        mock_document.user_id = 1
        mock_document.document_type = db_type
        mock_document.ocr_result = {}
        mock_document.uploaded_at = datetime(2024, 1, 1)

        mock_result = MagicMock()
        mock_result.suggestions = []
        mock_result.audit_log = []
        mock_result.stage_reached = None

        with patch.object(
            orchestrator, "_build_tax_form_suggestion", return_value=None
        ) as mock_build:
            orchestrator._stage_suggest(
                document=mock_document,
                db_type=db_type,
                ocr_result=mock_document.ocr_result,
                result=mock_result,
            )
            mock_build.assert_called_once()


# ---------------------------------------------------------------------------
# Preservation 2b: _generate_transaction_from_recurring behavior for all
#                  existing RecurringTransactionType values
# ---------------------------------------------------------------------------

class TestPreservation2b_GenerateTransactionFromRecurring:
    """
    **Validates: Requirements 3.5**

    Preservation: For all existing RecurringTransactionType values
    (rental_income, loan_interest, depreciation, other_income, other_expense, manual),
    _generate_transaction_from_recurring should produce the correct transaction
    type and category mapping.
    """

    amount_strategy = st.decimals(
        min_value=Decimal("10.00"),
        max_value=Decimal("50000.00"),
        places=2,
        allow_nan=False,
        allow_infinity=False,
    )

    date_strategy = st.dates(
        min_value=date(2020, 1, 1),
        max_value=date(2026, 12, 31),
    )

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_rental_income_generates_income_transaction(self, amount, gen_date):
        """
        RENTAL_INCOME recurring → income transaction with RENTAL category.
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType, IncomeCategory
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 1
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.RENTAL_INCOME
        recurring.transaction_type = "income"
        recurring.amount = amount
        recurring.property_id = "some-uuid"
        recurring.description = "Test rental income"
        recurring.frequency = RecurrenceFrequency.MONTHLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.INCOME
        assert txn.income_category == IncomeCategory.RENTAL
        assert txn.expense_category is None
        assert txn.amount == amount
        assert txn.transaction_date == gen_date
        assert txn.is_system_generated is True

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_loan_interest_generates_expense_transaction(self, amount, gen_date):
        """
        LOAN_INTEREST recurring → expense transaction with LOAN_INTEREST category.
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType, ExpenseCategory
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 2
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.LOAN_INTEREST
        recurring.transaction_type = "expense"
        recurring.amount = amount
        recurring.property_id = None
        recurring.loan_id = 10
        recurring.description = "Test loan interest"
        recurring.frequency = RecurrenceFrequency.MONTHLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.EXPENSE
        assert txn.expense_category == ExpenseCategory.LOAN_INTEREST
        assert txn.income_category is None
        assert txn.amount == amount
        assert txn.is_deductible is True

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_depreciation_generates_expense_transaction(self, amount, gen_date):
        """
        DEPRECIATION recurring → expense transaction with OTHER category
        (since it's not LOAN_INTEREST, the else branch gives OTHER).
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType, ExpenseCategory
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 3
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.DEPRECIATION
        recurring.transaction_type = "expense"
        recurring.amount = amount
        recurring.property_id = "some-uuid"
        recurring.description = "Test depreciation"
        recurring.frequency = RecurrenceFrequency.ANNUALLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.EXPENSE
        assert txn.expense_category == ExpenseCategory.OTHER
        assert txn.is_deductible is True

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_other_income_generates_income_transaction(self, amount, gen_date):
        """
        OTHER_INCOME recurring → income transaction with no specific income category.
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 4
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.OTHER_INCOME
        recurring.transaction_type = "income"
        recurring.amount = amount
        recurring.property_id = None
        recurring.description = "Test other income"
        recurring.frequency = RecurrenceFrequency.MONTHLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.INCOME
        # OTHER_INCOME is not RENTAL_INCOME, so income_category is None
        assert txn.income_category is None
        assert txn.expense_category is None

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_other_expense_generates_expense_transaction(self, amount, gen_date):
        """
        OTHER_EXPENSE recurring → expense transaction with OTHER category.
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType, ExpenseCategory
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 5
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.OTHER_EXPENSE
        recurring.transaction_type = "expense"
        recurring.amount = amount
        recurring.property_id = None
        recurring.description = "Test other expense"
        recurring.frequency = RecurrenceFrequency.MONTHLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.EXPENSE
        assert txn.expense_category == ExpenseCategory.OTHER
        assert txn.is_deductible is True

    @given(amount=amount_strategy, gen_date=date_strategy)
    @settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_manual_generates_correct_transaction(self, amount, gen_date):
        """
        MANUAL recurring with expense type → expense transaction with OTHER category.
        """
        from app.models.recurring_transaction import RecurringTransaction, RecurringTransactionType, RecurrenceFrequency
        from app.models.transaction import TransactionType, ExpenseCategory
        from app.services.recurring_transaction_service import RecurringTransactionService

        mock_db = MagicMock()
        service = RecurringTransactionService(mock_db)

        recurring = MagicMock(spec=RecurringTransaction)
        recurring.id = 6
        recurring.user_id = 1
        recurring.recurring_type = RecurringTransactionType.MANUAL
        recurring.transaction_type = "expense"
        recurring.amount = amount
        recurring.property_id = None
        recurring.description = "Test manual recurring"
        recurring.frequency = RecurrenceFrequency.QUARTERLY

        txn = service._generate_transaction_from_recurring(recurring, gen_date)

        assert txn.type == TransactionType.EXPENSE
        assert txn.expense_category == ExpenseCategory.OTHER
        assert txn.is_deductible is True


# ---------------------------------------------------------------------------
# Preservation 2c: Mortgage loans (with property_id) continue to work
#                  via create_loan_from_suggestion
# ---------------------------------------------------------------------------

class TestPreservation2c_MortgageLoanWithPropertyId:
    """
    **Validates: Requirements 3.3**

    Preservation: Loan contracts WITH a valid property_id should continue
    to successfully create PropertyLoan + loan_interest RecurringTransaction.
    This is the existing flow that must not break.
    """

    @given(
        loan_amount=loan_amount_strategy,
        interest_rate=interest_rate_strategy,
        monthly_payment=monthly_payment_strategy,
    )
    @settings(max_examples=10, suppress_health_check=[HealthCheck.too_slow], deadline=None)
    def test_loan_with_property_id_does_not_raise(
        self, loan_amount, interest_rate, monthly_payment
    ):
        """
        For any valid loan data WITH a property_id, create_loan_from_suggestion
        should NOT raise ValueError about missing property. It should proceed
        to create PropertyLoan (may fail on DB operations, but not on validation).
        """
        from app.tasks.ocr_tasks import create_loan_from_suggestion
        import uuid

        property_id = str(uuid.uuid4())

        mock_db = MagicMock()
        # Mock property lookup to return a valid property
        mock_property = MagicMock()
        mock_property.id = property_id
        mock_db.query.return_value.filter.return_value.first.return_value = mock_property

        mock_document = MagicMock()
        mock_document.id = 200
        mock_document.user_id = 1
        mock_document.uploaded_at = datetime(2024, 3, 1)
        mock_document.ocr_result = {}

        suggestion_data = {
            "loan_amount": float(loan_amount),
            "interest_rate": float(interest_rate),
            "monthly_payment": float(monthly_payment),
            "lender_name": "Test Mortgage Bank",
            "start_date": "2024-03-01",
            "end_date": None,
            "matched_property_id": property_id,
        }

        # Should NOT raise ValueError about missing property
        # It may raise other errors (DB flush, etc.) but not the property validation error
        try:
            result = create_loan_from_suggestion(mock_db, mock_document, suggestion_data)
        except ValueError as e:
            # The only ValueError we should NOT see is the property-related one
            assert "property" not in str(e).lower() or "not found" in str(e).lower(), (
                f"Unexpected property-related ValueError for loan WITH property_id: {e}"
            )
        except Exception:
            # Other exceptions (DB, mock issues) are acceptable — we're only
            # testing that the property_id validation passes
            pass


# ---------------------------------------------------------------------------
# Preservation 2d: RecurringTransactionType enum has exactly the expected values
# ---------------------------------------------------------------------------

class TestPreservation2d_RecurringTransactionTypeEnum:
    """
    **Validates: Requirements 3.5**

    Preservation: The RecurringTransactionType enum should contain at least
    the 6 existing values. After the fix, new values may be added, but
    existing ones must remain.
    """

    def test_existing_enum_values_present(self):
        """All 6 existing RecurringTransactionType values should exist."""
        from app.models.recurring_transaction import RecurringTransactionType

        expected_values = {
            "rental_income",
            "loan_interest",
            "depreciation",
            "other_income",
            "other_expense",
            "manual",
        }
        actual_values = {e.value for e in RecurringTransactionType}
        assert expected_values.issubset(actual_values), (
            f"Missing enum values: {expected_values - actual_values}"
        )

    def test_enum_member_names(self):
        """Enum member names should match expected pattern."""
        from app.models.recurring_transaction import RecurringTransactionType

        assert RecurringTransactionType.RENTAL_INCOME.value == "rental_income"
        assert RecurringTransactionType.LOAN_INTEREST.value == "loan_interest"
        assert RecurringTransactionType.DEPRECIATION.value == "depreciation"
        assert RecurringTransactionType.OTHER_INCOME.value == "other_income"
        assert RecurringTransactionType.OTHER_EXPENSE.value == "other_expense"
        assert RecurringTransactionType.MANUAL.value == "manual"
