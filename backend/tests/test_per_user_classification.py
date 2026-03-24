"""Tests for per-user classification rules and transaction line items.

Covers:
1. UserClassificationService: normalize, lookup, upsert, override priority
2. TransactionClassifier: user_rule → rule → ML → LLM fallback chain
3. Transaction.deductible_amount / deductible_items_by_category properties
4. OCR split → single transaction with line items
"""
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock
from types import SimpleNamespace

from app.services.user_classification_service import (
    normalize_description,
    UserClassificationService,
)
from app.services.transaction_classifier import TransactionClassifier, ClassificationResult
from app.models.transaction_line_item import TransactionLineItem
from app.services.ocr_transaction_service import OCRTransactionService


# ── normalize_description ──────────────────────────────────────────

class TestNormalizeDescription:
    def test_basic_lowering(self):
        assert normalize_description("BILLA Wien") == "billa wien"

    def test_strips_long_numbers(self):
        # Card refs, store IDs (4+ digits)
        result = normalize_description("AMAZON EU 123456 Druckerpatrone")
        assert "123456" not in result
        assert "druckerpatrone" in result
        assert "amazon" in result

    def test_strips_dates(self):
        result = normalize_description("BILLA 15.03.2026 Milch")
        assert "15.03.2026" not in result
        assert "milch" in result

    def test_strips_filiale(self):
        result = normalize_description("BILLA Filiale 1234 WIEN")
        assert "filiale" not in result.lower()
        assert "billa" in result
        assert "wien" in result

    def test_different_products_same_merchant(self):
        """Core requirement: same merchant, different products → different keys."""
        key1 = normalize_description("AMAZON EU Druckerpatrone")
        key2 = normalize_description("AMAZON EU Kleidung")
        assert key1 != key2
        assert "druckerpatrone" in key1
        assert "kleidung" in key2

    def test_same_purchase_different_noise(self):
        """Same product with different noise → same key."""
        key1 = normalize_description("BILLA Milch 98765")
        key2 = normalize_description("BILLA Milch 11111")
        assert key1 == key2

    def test_empty_string(self):
        assert normalize_description("") == ""
        assert normalize_description("   ") == ""

    def test_iban_stripped(self):
        result = normalize_description("Überweisung AT123456789 Miete")
        assert "AT123456789" not in result
        assert "miete" in result


# ── UserClassificationService (mocked DB) ──────────────────────────

class TestUserClassificationService:
    def _make_service(self):
        db = MagicMock()
        return UserClassificationService(db), db

    def test_lookup_returns_none_when_no_match(self):
        svc, db = self._make_service()
        db.query.return_value.filter.return_value.first.return_value = None
        result = svc.lookup(user_id=1, description="BILLA Milch", txn_type="expense")
        assert result is None

    def test_lookup_returns_rule_when_matched(self):
        svc, db = self._make_service()
        mock_rule = MagicMock()
        mock_rule.category = "office_supplies"
        mock_rule.normalized_description = "amazon druckerpatrone"
        db.query.return_value.filter.return_value.first.return_value = mock_rule
        result = svc.lookup(user_id=1, description="AMAZON Druckerpatrone 99999", txn_type="expense")
        assert result is not None
        assert result.category == "office_supplies"

    def test_lookup_empty_description_returns_none(self):
        svc, db = self._make_service()
        result = svc.lookup(user_id=1, description="", txn_type="expense")
        assert result is None

    def test_upsert_creates_new_rule(self):
        svc, db = self._make_service()
        db.query.return_value.filter.return_value.first.return_value = None
        rule = svc.upsert_rule(
            user_id=1,
            description="AMAZON Druckerpatrone",
            txn_type="expense",
            category="office_supplies",
        )
        db.add.assert_called_once()
        db.flush.assert_called_once()

    def test_upsert_updates_existing_rule(self):
        svc, db = self._make_service()
        existing = MagicMock()
        existing.hit_count = 2
        existing.category = "other"
        db.query.return_value.filter.return_value.first.return_value = existing
        svc.upsert_rule(
            user_id=1,
            description="AMAZON Druckerpatrone",
            txn_type="expense",
            category="office_supplies",
        )
        assert existing.category == "office_supplies"
        assert existing.hit_count == 3
        db.add.assert_not_called()  # should not add, just update


# ── TransactionClassifier: user_rule priority ──────────────────────

def _make_txn(description="Test", amount=100, txn_type="expense", user_id=1, txn_id=1):
    """Helper to create a mock transaction."""
    txn = SimpleNamespace(
        id=txn_id,
        user_id=user_id,
        description=description,
        amount=Decimal(str(amount)),
        type=SimpleNamespace(value=txn_type),
    )
    return txn


class TestClassifierUserRulePriority:
    def test_user_rule_takes_priority_over_global_rule(self):
        """If user has a rule, it should be used even if global rule matches."""
        mock_db = MagicMock()
        classifier = TransactionClassifier(db=mock_db)

        # Mock user service to return a rule
        mock_rule = MagicMock()
        mock_rule.category = "office_supplies"
        mock_rule.confidence = Decimal("1.00")
        mock_rule.normalized_description = "billa druckerpapier"
        mock_rule.hit_count = 3
        classifier._user_svc = MagicMock()
        classifier._user_svc.lookup.return_value = mock_rule

        txn = _make_txn(description="BILLA Druckerpapier 1234")
        result = classifier.classify_transaction(txn)

        assert result.method == "user_rule"
        assert result.category == "office_supplies"
        assert result.confidence == Decimal("1.00")

    def test_falls_through_when_no_user_rule(self):
        """Without user rule, should fall through to rule/ML/LLM."""
        mock_db = MagicMock()
        classifier = TransactionClassifier(db=mock_db)
        classifier._user_svc = MagicMock()
        classifier._user_svc.lookup.return_value = None

        txn = _make_txn(description="BILLA Filiale 999")
        result = classifier.classify_transaction(txn)

        # Should get a result from rule-based (BILLA → groceries)
        assert result.method in ("rule", "ml")
        assert result.category is not None

    def test_no_user_rule_without_user_id(self):
        """Transaction without user_id should skip user rule lookup."""
        mock_db = MagicMock()
        classifier = TransactionClassifier(db=mock_db)
        classifier._user_svc = MagicMock()

        txn = _make_txn(description="BILLA Milch")
        txn.user_id = None
        result = classifier.classify_transaction(txn)

        classifier._user_svc.lookup.assert_not_called()
        assert result.method in ("rule", "ml")

    def test_no_db_means_no_user_service(self):
        """Classifier without db should have no user service."""
        classifier = TransactionClassifier(db=None)
        assert classifier._user_svc is None

        txn = _make_txn(description="BILLA Milch")
        result = classifier.classify_transaction(txn)
        assert result.method in ("rule", "ml")


# ── Transaction computed properties (line items) ───────────────────

def _make_line_item(description="Item", amount="10.00", quantity=1,
                    category="office_supplies", is_deductible=True):
    """Helper to create a line-item-like object for property tests."""
    return SimpleNamespace(
        description=description,
        amount=Decimal(amount),
        quantity=quantity,
        category=category,
        is_deductible=is_deductible,
    )


# Lightweight stand-in for Transaction that carries the real computed
# properties but doesn't trigger SQLAlchemy instrumentation.
from app.models.transaction import Transaction as _RealTxn

class _FakeTransaction:
    has_line_items = _RealTxn.has_line_items
    deductible_amount = _RealTxn.deductible_amount
    non_deductible_amount = _RealTxn.non_deductible_amount
    deductible_items_by_category = _RealTxn.deductible_items_by_category

    def __init__(self, amount, is_deductible=False, expense_category=None, line_items=None):
        self.amount = Decimal(str(amount))
        self.is_deductible = is_deductible
        self.expense_category = expense_category
        self.line_items = line_items or []


class TestTransactionLineItemProperties:
    """Test Transaction.deductible_amount, non_deductible_amount, deductible_items_by_category."""

    def _make_transaction(self, amount="100.00", is_deductible=False,
                          expense_category=None, line_items=None):
        return _FakeTransaction(amount, is_deductible, expense_category, line_items)

    def test_no_line_items_deductible(self):
        """Transaction without line items, is_deductible=True → full amount deductible."""
        txn = self._make_transaction(amount="50.00", is_deductible=True)
        assert txn.has_line_items is False
        assert txn.deductible_amount == Decimal("50.00")
        assert txn.non_deductible_amount == Decimal("0.00")

    def test_no_line_items_not_deductible(self):
        """Transaction without line items, is_deductible=False → nothing deductible."""
        txn = self._make_transaction(amount="50.00", is_deductible=False)
        assert txn.deductible_amount == Decimal("0.00")
        assert txn.non_deductible_amount == Decimal("50.00")

    def test_with_mixed_line_items(self):
        """Line items with mixed deductibility."""
        items = [
            _make_line_item("Druckerpapier", "12.50", 1, "office_supplies", True),
            _make_line_item("Milch", "3.00", 2, "groceries", False),
            _make_line_item("Toner", "25.00", 1, "office_supplies", True),
        ]
        txn = self._make_transaction(amount="43.50", line_items=items)
        assert txn.has_line_items is True
        # Deductible: 12.50*1 + 25.00*1 = 37.50
        assert txn.deductible_amount == Decimal("37.50")
        # Non-deductible: 3.00*2 = 6.00
        assert txn.non_deductible_amount == Decimal("6.00")

    def test_all_deductible_line_items(self):
        items = [
            _make_line_item("Papier", "10.00", 1, "office_supplies", True),
            _make_line_item("Stifte", "5.00", 3, "office_supplies", True),
        ]
        txn = self._make_transaction(amount="25.00", line_items=items)
        assert txn.deductible_amount == Decimal("25.00")
        assert txn.non_deductible_amount == Decimal("0.00")

    def test_no_deductible_line_items(self):
        items = [
            _make_line_item("Milch", "3.00", 1, "groceries", False),
            _make_line_item("Brot", "2.50", 1, "groceries", False),
        ]
        txn = self._make_transaction(amount="5.50", line_items=items)
        assert txn.deductible_amount == Decimal("0.00")
        assert txn.non_deductible_amount == Decimal("5.50")

    def test_deductible_items_by_category_with_line_items(self):
        """deductible_items_by_category groups deductible items by category."""
        items = [
            _make_line_item("Papier", "10.00", 1, "office_supplies", True),
            _make_line_item("Reiniger", "5.00", 2, "cleaning", True),
            _make_line_item("Milch", "3.00", 1, "groceries", False),
            _make_line_item("Toner", "20.00", 1, "office_supplies", True),
        ]
        txn = self._make_transaction(amount="41.00", line_items=items)
        result = txn.deductible_items_by_category
        assert result == {
            "office_supplies": Decimal("30.00"),  # 10 + 20
            "cleaning": Decimal("10.00"),          # 5 * 2
        }
        assert "groceries" not in result

    def test_deductible_items_by_category_no_line_items_deductible(self):
        """Without line items, falls back to expense_category."""
        from app.models.transaction import ExpenseCategory
        txn = self._make_transaction(
            amount="100.00", is_deductible=True,
            expense_category=ExpenseCategory.OFFICE_SUPPLIES,
        )
        result = txn.deductible_items_by_category
        assert result == {"office_supplies": Decimal("100.00")}

    def test_deductible_items_by_category_no_line_items_not_deductible(self):
        """Without line items and not deductible → empty dict."""
        txn = self._make_transaction(amount="100.00", is_deductible=False)
        assert txn.deductible_items_by_category == {}

    def test_quantity_multiplied_correctly(self):
        """amount * quantity should be used in totals."""
        items = [
            _make_line_item("Papier", "5.00", 4, "office_supplies", True),
        ]
        txn = self._make_transaction(amount="20.00", line_items=items)
        assert txn.deductible_amount == Decimal("20.00")


# ── OCR split → single transaction with line items ─────────────────

class TestOCRBuildSplitSuggestions:
    """Test _build_split_suggestions returns 1 transaction with N line items."""

    def _make_service(self):
        db = MagicMock()
        svc = OCRTransactionService.__new__(OCRTransactionService)
        svc.db = db
        svc.classifier = MagicMock()
        svc.deductibility_checker = MagicMock()
        return svc

    def _make_document(self, doc_id=1):
        doc = MagicMock()
        doc.id = doc_id
        doc.document_type = MagicMock()
        doc.document_type.value = "receipt"
        return doc

    def test_returns_single_suggestion_with_line_items(self):
        svc = self._make_service()
        doc = self._make_document()

        transaction_data = {
            "amount": Decimal("25.00"),
            "date": "2026-03-15",
            "description": "BILLA Wien",
        }
        classification = {
            "transaction_type": "expense",
            "category": "office_supplies",
            "is_deductible": True,
            "deduction_reason": "Betriebsausgabe",
            "confidence": 0.85,
        }
        split = {
            "has_split": True,
            "deductible_amount": 15.00,
            "non_deductible_amount": 10.00,
            "deductible_items": "Druckerpapier",
            "non_deductible_items": "Milch",
            "deductible_reason": "Betriebsausgabe",
            "non_deductible_reason": "Privat",
            "tax_tip": "",
        }
        ocr_data = {
            "merchant": "BILLA",
            "line_items": [
                {"name": "Druckerpapier A4", "total_price": 15.00, "quantity": 1},
                {"name": "Milch 1L", "total_price": 10.00, "quantity": 1},
            ],
        }

        result = svc._build_split_suggestions(
            doc, transaction_data, classification, split, ocr_data
        )

        assert len(result) == 1
        suggestion = result[0]
        assert suggestion["amount"] == "25.00"
        assert "line_items" in suggestion
        assert len(suggestion["line_items"]) == 2

        # Check deductible item
        deductible_items = [li for li in suggestion["line_items"] if li["is_deductible"]]
        non_deductible_items = [li for li in suggestion["line_items"] if not li["is_deductible"]]
        assert len(deductible_items) == 1
        assert len(non_deductible_items) == 1
        assert "druckerpapier" in deductible_items[0]["description"].lower()

    def test_falls_back_to_single_when_amounts_mismatch(self):
        """If split amounts don't add up, fall back to single suggestion."""
        svc = self._make_service()
        doc = self._make_document()

        transaction_data = {
            "amount": Decimal("100.00"),
            "date": "2026-03-15",
            "description": "Test",
        }
        classification = {
            "transaction_type": "expense",
            "category": "other",
            "is_deductible": False,
            "deduction_reason": "",
            "confidence": 0.5,
        }
        split = {
            "has_split": True,
            "deductible_amount": 10.00,
            "non_deductible_amount": 10.00,  # total=20, but txn=100 → diff=80 > 2
            "deductible_items": "A",
            "non_deductible_items": "B",
            "deductible_reason": "R",
            "non_deductible_reason": "NR",
        }
        ocr_data = {"merchant": "X", "line_items": []}

        result = svc._build_split_suggestions(
            doc, transaction_data, classification, split, ocr_data
        )

        # Should fall back to single suggestion without line_items key
        assert len(result) == 1
        assert "line_items" not in result[0] or result[0].get("line_items") is None

    def test_summary_line_items_when_no_ocr_items(self):
        """When OCR has no line_items, should create summary deductible/non-deductible items."""
        svc = self._make_service()
        doc = self._make_document()

        transaction_data = {
            "amount": Decimal("30.00"),
            "date": "2026-03-15",
            "description": "BILLA",
        }
        classification = {
            "transaction_type": "expense",
            "category": "office_supplies",
            "is_deductible": True,
            "deduction_reason": "Betriebsausgabe",
            "confidence": 0.85,
        }
        split = {
            "has_split": True,
            "deductible_amount": 20.00,
            "non_deductible_amount": 10.00,
            "deductible_items": "Bürobedarf",
            "non_deductible_items": "Lebensmittel",
            "deductible_reason": "Betriebsausgabe",
            "non_deductible_reason": "Privat",
        }
        ocr_data = {"merchant": "BILLA", "line_items": []}

        result = svc._build_split_suggestions(
            doc, transaction_data, classification, split, ocr_data
        )

        assert len(result) == 1
        suggestion = result[0]
        items = suggestion["line_items"]
        assert len(items) == 2
        deductible = [i for i in items if i["is_deductible"]]
        assert len(deductible) == 1
        assert Decimal(deductible[0]["amount"]) == Decimal("20.00")


# ── _build_line_items_from_split mapping ───────────────────────────

class TestBuildLineItemsFromSplit:
    """Test the OCR item → classified line item mapping."""

    def _make_service(self):
        svc = OCRTransactionService.__new__(OCRTransactionService)
        svc.db = MagicMock()
        svc.classifier = MagicMock()
        svc.deductibility_checker = MagicMock()
        return svc

    def test_maps_items_correctly(self):
        svc = self._make_service()
        ocr_items = [
            {"name": "Druckerpapier A4", "total_price": 12.50, "quantity": 1},
            {"name": "Milch 1L", "total_price": 3.00, "quantity": 2},
            {"name": "Toner HP", "total_price": 25.00, "quantity": 1},
        ]
        split = {
            "deductible_items": "Druckerpapier A4, Toner HP",
            "non_deductible_items": "Milch 1L",
        }

        items = svc._build_line_items_from_split(
            ocr_items, split, "office_supplies", "Betriebsausgabe", "Privat"
        )

        assert len(items) == 3
        # Druckerpapier → deductible
        paper = next(i for i in items if "druckerpapier" in i["description"].lower())
        assert paper["is_deductible"] is True
        assert paper["category"] == "office_supplies"

        # Milch → not deductible
        milk = next(i for i in items if "milch" in i["description"].lower())
        assert milk["is_deductible"] is False
        assert milk["category"] == "groceries"

        # Toner → deductible
        toner = next(i for i in items if "toner" in i["description"].lower())
        assert toner["is_deductible"] is True

    def test_empty_ocr_items_returns_empty(self):
        svc = self._make_service()
        result = svc._build_line_items_from_split([], {}, "other", "R", "NR")
        assert result == []

    def test_items_without_name_skipped(self):
        svc = self._make_service()
        ocr_items = [
            {"name": "", "total_price": 5.00},
            {"name": "Papier", "total_price": 10.00},
        ]
        split = {"deductible_items": "Papier", "non_deductible_items": ""}
        items = svc._build_line_items_from_split(
            ocr_items, split, "office_supplies", "R", "NR"
        )
        assert len(items) == 1
        assert items[0]["description"] == "Papier"

    def test_ambiguous_item_defaults_to_non_deductible(self):
        """Item matched in both lists or neither → defaults to non-deductible (safer)."""
        svc = self._make_service()
        ocr_items = [{"name": "Mystery Item", "total_price": 10.00, "quantity": 1}]
        split = {
            "deductible_items": "",
            "non_deductible_items": "",
        }
        items = svc._build_line_items_from_split(
            ocr_items, split, "office_supplies", "R", "NR"
        )
        assert len(items) == 1
        assert items[0]["is_deductible"] is False


# ── create_transaction_from_suggestion with line items ─────────────

class TestCreateTransactionFromSuggestion:
    """Test that create_transaction_from_suggestion creates line items."""

    def test_creates_transaction_with_line_items(self):
        db = MagicMock()
        svc = OCRTransactionService.__new__(OCRTransactionService)
        svc.db = db
        svc.classifier = MagicMock()
        svc.deductibility_checker = MagicMock()

        # Mock db.flush to assign an ID
        def set_id_on_flush():
            for call in db.add.call_args_list:
                obj = call[0][0]
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = 42
        db.flush.side_effect = set_id_on_flush

        # Mock db.query for document update
        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        suggestion = {
            "document_id": 1,
            "transaction_type": "expense",
            "amount": "25.00",
            "date": "2026-03-15",
            "description": "BILLA Wien",
            "category": "office_supplies",
            "is_deductible": True,
            "deduction_reason": "Betriebsausgabe",
            "confidence": 0.85,
            "needs_review": False,
            "line_items": [
                {
                    "description": "Druckerpapier",
                    "amount": "15.00",
                    "quantity": 1,
                    "category": "office_supplies",
                    "is_deductible": True,
                    "deduction_reason": "Betriebsausgabe",
                    "sort_order": 0,
                },
                {
                    "description": "Milch",
                    "amount": "10.00",
                    "quantity": 1,
                    "category": "groceries",
                    "is_deductible": False,
                    "deduction_reason": "Privat",
                    "sort_order": 1,
                },
            ],
        }

        txn = svc.create_transaction_from_suggestion(suggestion, user_id=1)

        # Transaction should be added
        assert db.add.call_count >= 3  # 1 transaction + 2 line items
        assert db.commit.called

    def test_creates_transaction_without_line_items(self):
        """Backward compat: suggestion without line_items still works."""
        db = MagicMock()
        svc = OCRTransactionService.__new__(OCRTransactionService)
        svc.db = db
        svc.classifier = MagicMock()
        svc.deductibility_checker = MagicMock()

        def set_id_on_flush():
            for call in db.add.call_args_list:
                obj = call[0][0]
                if hasattr(obj, 'id') and obj.id is None:
                    obj.id = 99
        db.flush.side_effect = set_id_on_flush

        db.query.return_value.filter.return_value.first.return_value = MagicMock()

        suggestion = {
            "document_id": 2,
            "transaction_type": "expense",
            "amount": "50.00",
            "date": "2026-03-15",
            "description": "Amazon Bestellung",
            "category": "equipment",
            "is_deductible": True,
            "deduction_reason": "Betriebsausgabe",
            "confidence": 0.90,
            "needs_review": False,
        }

        txn = svc.create_transaction_from_suggestion(suggestion, user_id=1)

        # Canonical layer now always persists a mirror line item as well.
        assert db.add.call_count >= 2
        assert db.commit.called


# ── Backward compatibility ─────────────────────────────────────────

class TestBackwardCompatibility:
    """Ensure transactions without line items still work correctly."""

    def test_transaction_without_line_items_has_correct_defaults(self):
        from app.models.transaction import Transaction, TransactionType, ExpenseCategory
        txn = Transaction()
        txn.amount = Decimal("100.00")
        txn.is_deductible = True
        txn.expense_category = ExpenseCategory.EQUIPMENT
        txn.line_items = []

        assert txn.has_line_items is False
        assert txn.deductible_amount == Decimal("100.00")
        assert txn.non_deductible_amount == Decimal("0.00")
        assert txn.deductible_items_by_category == {"equipment": Decimal("100.00")}

    def test_transaction_response_schema_without_line_items(self):
        """TransactionResponse should work with empty line_items."""
        from app.schemas.transaction import TransactionResponse
        data = {
            "id": 1,
            "user_id": 1,
            "type": "expense",
            "amount": "100.00",
            "transaction_date": "2026-03-15",
            "description": "Test",
            "expense_category": "equipment",
            "is_deductible": True,
            "deduction_reason": "Test",
            "created_at": "2026-03-15T00:00:00",
            "updated_at": "2026-03-15T00:00:00",
            "line_items": [],
            "deductible_amount": "100.00",
            "non_deductible_amount": "0.00",
        }
        resp = TransactionResponse(**data)
        assert resp.line_items == []
        assert resp.deductible_amount == Decimal("100.00")

    def test_transaction_response_schema_with_line_items(self):
        """TransactionResponse should serialize line items."""
        from app.schemas.transaction import TransactionResponse
        data = {
            "id": 2,
            "user_id": 1,
            "type": "expense",
            "amount": "25.00",
            "transaction_date": "2026-03-15",
            "description": "BILLA",
            "expense_category": "office_supplies",
            "is_deductible": True,
            "deduction_reason": "Betriebsausgabe",
            "created_at": "2026-03-15T00:00:00",
            "updated_at": "2026-03-15T00:00:00",
            "line_items": [
                {
                    "id": 1,
                    "description": "Papier",
                    "amount": "15.00",
                    "quantity": 1,
                    "category": "office_supplies",
                    "is_deductible": True,
                    "sort_order": 0,
                },
                {
                    "id": 2,
                    "description": "Milch",
                    "amount": "10.00",
                    "quantity": 1,
                    "category": "groceries",
                    "is_deductible": False,
                    "sort_order": 1,
                },
            ],
            "deductible_amount": "15.00",
            "non_deductible_amount": "10.00",
        }
        resp = TransactionResponse(**data)
        assert len(resp.line_items) == 2
        assert resp.line_items[0].is_deductible is True
        assert resp.line_items[1].is_deductible is False
