"""Bank statement import and review workbench service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from difflib import SequenceMatcher
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.bank_statement_import import (
    BankStatementImport,
    BankStatementImportSourceType,
    BankStatementLine,
    BankStatementLineStatus,
    BankStatementSuggestedAction,
)
from app.models.document import Document
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.csv_parser import BankFormat, CSVParser
from app.services.duplicate_detector import DuplicateDetector
from app.services.mt940_parser import MT940Parser
from app.services.transaction_classifier import TransactionClassifier


class ImportFormat(str, Enum):
    """Supported import file formats."""

    CSV = "csv"
    MT940 = "mt940"


@dataclass
class ImportResult:
    """Summary of a bank import batch."""

    import_id: int
    total_count: int = 0
    auto_created_count: int = 0
    matched_existing_count: int = 0
    pending_review_count: int = 0
    ignored_count: int = 0
    transactions: List[Transaction] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "import_id": self.import_id,
            "total_count": self.total_count,
            "auto_created_count": self.auto_created_count,
            "matched_existing_count": self.matched_existing_count,
            "pending_review_count": self.pending_review_count,
            "ignored_count": self.ignored_count,
            "transactions": [
                {
                    "id": transaction.id,
                    "date": transaction.transaction_date.isoformat(),
                    "amount": str(transaction.amount),
                    "description": transaction.description,
                    "category": transaction.income_category or transaction.expense_category,
                    "classification_confidence": (
                        str(transaction.classification_confidence)
                        if transaction.classification_confidence is not None
                        else None
                    ),
                    "bank_reconciled": transaction.bank_reconciled,
                }
                for transaction in self.transactions
            ],
        }


class BankImportService:
    """Service for importing, reviewing, and reconciling bank statement lines."""

    AUTO_CREATE_THRESHOLD = Decimal("0.90")
    AUTO_MATCH_SIMILARITY = 0.82
    SUGGEST_MATCH_SIMILARITY = 0.55
    DATE_TOLERANCE_DAYS = 3

    def __init__(
        self,
        db: Optional[Session] = None,
        csv_parser: Optional[CSVParser] = None,
        mt940_parser: Optional[MT940Parser] = None,
        classifier: Optional[TransactionClassifier] = None,
        duplicate_detector: Optional[DuplicateDetector] = None,
    ):
        self.db = db
        self.csv_parser = csv_parser or CSVParser()
        self.mt940_parser = mt940_parser or MT940Parser()
        self.classifier = classifier or TransactionClassifier(db=db)
        self.duplicate_detector = (
            duplicate_detector or (DuplicateDetector(db) if db is not None else None)
        )

    # ------------------------------------------------------------------
    # Public import entry points
    # ------------------------------------------------------------------
    def import_transactions(
        self,
        file_content: str,
        import_format: ImportFormat,
        user: User,
        tax_year: int,
        auto_classify: bool = True,
        skip_duplicates: bool = True,
        bank_format: Optional[BankFormat] = None,
    ) -> ImportResult:
        """Create a persisted bank import batch from uploaded file content."""

        if self.db is None:
            raise ValueError("Database session is required to import bank statements")

        parsed_transactions = self._parse_transactions(
            file_content=file_content,
            import_format=import_format,
            bank_format=bank_format,
        )

        statement_import = BankStatementImport(
            user_id=user.id,
            source_type=(
                BankStatementImportSourceType.CSV
                if import_format == ImportFormat.CSV
                else BankStatementImportSourceType.MT940
            ),
            tax_year=tax_year,
            statement_period=self._build_statement_period(parsed_transactions),
        )
        self.db.add(statement_import)
        self.db.flush()

        for parsed_transaction in parsed_transactions:
            statement_import.lines.append(self._build_line_from_parsed(parsed_transaction))

        self.db.flush()
        result = self._auto_process_import(
            statement_import=statement_import,
            user=user,
            tax_year=tax_year,
            auto_classify=auto_classify,
            ignore_duplicates=skip_duplicates,
        )
        self.db.commit()
        self.db.refresh(statement_import)
        result.import_id = statement_import.id
        return result

    def initialize_document_import(self, document: Document, user: User) -> BankStatementImport:
        """Initialize or refresh a bank import batch from a bank-statement document."""

        if self.db is None:
            raise ValueError("Database session is required to initialize document imports")

        suggestion_payload = self._extract_document_suggestion_payload(document)
        parsed_transactions = suggestion_payload["transactions"]
        tax_year = suggestion_payload.get("tax_year")

        existing_import = (
            self.db.query(BankStatementImport)
            .filter(
                BankStatementImport.user_id == user.id,
                BankStatementImport.source_document_id == document.id,
            )
            .order_by(BankStatementImport.id.desc())
            .first()
        )

        if existing_import is None:
            existing_import = BankStatementImport(
                user_id=user.id,
                source_type=BankStatementImportSourceType.DOCUMENT,
                source_document_id=document.id,
            )
            self.db.add(existing_import)
            self.db.flush()
        else:
            source_updated_at = (
                getattr(document, "updated_at", None)
                or getattr(document, "processed_at", None)
                or getattr(document, "created_at", None)
            )
            import_updated_at = existing_import.updated_at or existing_import.created_at
            has_existing_lines = bool(existing_import.lines)

            if has_existing_lines and (
                source_updated_at is None
                or import_updated_at is None
                or source_updated_at <= import_updated_at
            ):
                return existing_import

        # Rebuild the batch from the latest OCR suggestion to keep document reprocesses coherent.
        for line in list(existing_import.lines):
            self.db.delete(line)
        self.db.flush()

        existing_import.bank_name = suggestion_payload.get("bank_name")
        existing_import.iban = suggestion_payload.get("iban")
        existing_import.tax_year = tax_year
        existing_import.statement_period = suggestion_payload.get("statement_period") or self._build_statement_period(parsed_transactions)
        existing_import.updated_at = datetime.utcnow()

        for parsed_transaction in parsed_transactions:
            existing_import.lines.append(self._build_line_from_parsed(parsed_transaction))

        self.db.flush()
        self._auto_process_import(
            statement_import=existing_import,
            user=user,
            tax_year=tax_year,
            auto_classify=True,
            ignore_duplicates=True,
        )
        self.db.commit()
        self.db.refresh(existing_import)
        return existing_import

    def get_import_for_user(self, import_id: int, user_id: int) -> BankStatementImport:
        if self.db is None:
            raise ValueError("Database session is required")
        statement_import = (
            self.db.query(BankStatementImport)
            .filter(BankStatementImport.id == import_id, BankStatementImport.user_id == user_id)
            .first()
        )
        if statement_import is None:
            raise ValueError("Bank statement import not found")
        return statement_import

    def get_lines_for_import(self, import_id: int, user_id: int) -> List[BankStatementLine]:
        statement_import = self.get_import_for_user(import_id, user_id)
        return list(statement_import.lines)

    def confirm_create_line(self, line_id: int, user: User) -> Tuple[BankStatementLine, Transaction]:
        line = self._get_line_for_user(line_id, user.id)
        if line.created_transaction is not None:
            return line, line.created_transaction
        if line.linked_transaction is not None and line.review_status == BankStatementLineStatus.MATCHED_EXISTING:
            return line, line.linked_transaction

        transaction, classification_confidence = self._create_transaction_for_line(line, user, auto_classify=True)
        line.created_transaction_id = transaction.id
        line.linked_transaction_id = transaction.id
        line.review_status = BankStatementLineStatus.AUTO_CREATED
        line.suggested_action = BankStatementSuggestedAction.CREATE_NEW
        line.confidence_score = classification_confidence
        line.reviewed_at = datetime.utcnow()
        line.reviewed_by = user.id
        self.db.commit()
        self.db.refresh(line)
        return line, transaction

    def match_existing_line(
        self,
        line_id: int,
        user: User,
        transaction_id: Optional[int] = None,
    ) -> Tuple[BankStatementLine, Transaction]:
        line = self._get_line_for_user(line_id, user.id)
        target_transaction = None

        if transaction_id is not None:
            target_transaction = (
                self.db.query(Transaction)
                .filter(Transaction.id == transaction_id, Transaction.user_id == user.id)
                .first()
            )
        if target_transaction is None:
            target_transaction, _similarity = self._find_best_existing_transaction(
                line=line,
                user_id=user.id,
                tax_year=line.statement_import.tax_year,
                require_threshold=False,
            )

        if target_transaction is None:
            raise ValueError("No matching transaction found for this bank statement line")

        self._mark_transaction_reconciled(target_transaction)
        line.linked_transaction_id = target_transaction.id
        line.review_status = BankStatementLineStatus.MATCHED_EXISTING
        line.suggested_action = BankStatementSuggestedAction.MATCH_EXISTING
        line.reviewed_at = datetime.utcnow()
        line.reviewed_by = user.id
        self.db.commit()
        self.db.refresh(line)
        return line, target_transaction

    def ignore_line(self, line_id: int, user: User) -> BankStatementLine:
        line = self._get_line_for_user(line_id, user.id)
        line.review_status = BankStatementLineStatus.IGNORED_DUPLICATE
        line.suggested_action = BankStatementSuggestedAction.IGNORE
        line.reviewed_at = datetime.utcnow()
        line.reviewed_by = user.id
        self.db.commit()
        self.db.refresh(line)
        return line

    # ------------------------------------------------------------------
    # Preview support
    # ------------------------------------------------------------------
    def preview_import(
        self,
        file_content: str,
        import_format: ImportFormat,
        bank_format: Optional[BankFormat] = None,
    ) -> Dict[str, Any]:
        """Preview a bank import without persisting it."""

        try:
            if import_format == ImportFormat.CSV:
                if bank_format:
                    self.csv_parser.bank_format = bank_format
                validation = self.csv_parser.validate_csv(file_content)
            elif import_format == ImportFormat.MT940:
                validation = self.mt940_parser.validate_mt940(file_content)
            else:
                raise ValueError(f"Unsupported import format: {import_format}")

            if not validation["valid"]:
                return {
                    "valid": False,
                    "error": validation.get("error", "Unknown error"),
                }

            parsed_transactions = self._parse_transactions(
                file_content=file_content,
                import_format=import_format,
                bank_format=bank_format,
            )

            income_count = sum(1 for item in parsed_transactions if item["amount"] >= 0)
            expense_count = sum(1 for item in parsed_transactions if item["amount"] < 0)
            total_income = sum(item["amount"] for item in parsed_transactions if item["amount"] >= 0)
            total_expenses = sum(abs(item["amount"]) for item in parsed_transactions if item["amount"] < 0)

            return {
                "valid": True,
                "total_count": len(parsed_transactions),
                "income_count": income_count,
                "expense_count": expense_count,
                "total_income": str(total_income),
                "total_expenses": str(total_expenses),
                "date_range": self._build_statement_period(parsed_transactions),
                "detected_format": validation.get("detected_format"),
                "sample_transactions": [
                    {
                        "date": item["date"].isoformat(),
                        "amount": str(item["amount"]),
                        "description": item["description"],
                    }
                    for item in parsed_transactions[:5]
                ],
            }
        except Exception as exc:
            return {"valid": False, "error": str(exc)}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _parse_transactions(
        self,
        file_content: str,
        import_format: ImportFormat,
        bank_format: Optional[BankFormat] = None,
    ) -> List[Dict[str, Any]]:
        if import_format == ImportFormat.CSV:
            if bank_format:
                self.csv_parser.bank_format = bank_format
            return self.csv_parser.parse(file_content)
        if import_format == ImportFormat.MT940:
            return self.mt940_parser.parse(file_content)
        raise ValueError(f"Unsupported import format: {import_format}")

    def _extract_document_suggestion_payload(self, document: Document) -> Dict[str, Any]:
        ocr_result = document.ocr_result or {}
        suggestion = ocr_result.get("import_suggestion") if isinstance(ocr_result, dict) else None
        if not isinstance(suggestion, dict) or suggestion.get("type") != "import_bank_statement":
            raise ValueError("The document does not contain a bank statement import suggestion")

        payload = suggestion.get("data") or {}
        raw_transactions = payload.get("transactions") or []
        parsed_transactions = []
        for item in raw_transactions:
            parsed = self._normalize_transaction_candidate(item)
            if parsed is not None:
                parsed_transactions.append(parsed)

        if not parsed_transactions:
            raise ValueError("No bank statement lines were found in the document suggestion")

        return {
            "bank_name": payload.get("bank_name") or ocr_result.get("bank_name"),
            "iban": payload.get("iban") or ocr_result.get("iban"),
            "statement_period": payload.get("statement_period"),
            "tax_year": payload.get("tax_year") or self._infer_tax_year(parsed_transactions),
            "transactions": parsed_transactions,
        }

    def _normalize_transaction_candidate(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not isinstance(payload, dict):
            return None
        raw_date = payload.get("date")
        raw_amount = payload.get("amount")
        if raw_date is None or raw_amount is None:
            return None

        parsed_date = self._coerce_to_date(raw_date)
        parsed_amount = self._coerce_to_decimal(raw_amount)
        if parsed_date is None or parsed_amount is None:
            return None

        description = (
            payload.get("purpose")
            or payload.get("description")
            or payload.get("counterparty")
            or payload.get("reference")
            or ""
        )
        return {
            "date": parsed_date,
            "amount": parsed_amount,
            "description": str(description).strip(),
            "counterparty": (payload.get("counterparty") or payload.get("description") or None),
            "purpose": payload.get("purpose") or payload.get("description") or None,
            "reference": payload.get("reference") or payload.get("raw_reference") or None,
        }

    def _build_line_from_parsed(self, parsed_transaction: Dict[str, Any]) -> BankStatementLine:
        return BankStatementLine(
            line_date=parsed_transaction["date"],
            amount=parsed_transaction["amount"],
            counterparty=(parsed_transaction.get("counterparty") or None),
            purpose=(parsed_transaction.get("purpose") or parsed_transaction.get("description") or None),
            raw_reference=(parsed_transaction.get("reference") or None),
            normalized_fingerprint=self._build_fingerprint(parsed_transaction),
            review_status=BankStatementLineStatus.PENDING_REVIEW,
            suggested_action=BankStatementSuggestedAction.CREATE_NEW,
            confidence_score=Decimal("0"),
        )

    def _auto_process_import(
        self,
        statement_import: BankStatementImport,
        user: User,
        tax_year: Optional[int],
        auto_classify: bool,
        ignore_duplicates: bool,
    ) -> ImportResult:
        result = ImportResult(import_id=statement_import.id, total_count=len(statement_import.lines))

        for line in statement_import.lines:
            best_match, similarity = self._find_best_existing_transaction(
                line=line,
                user_id=user.id,
                tax_year=tax_year,
                require_threshold=False,
            )

            if (
                ignore_duplicates
                and best_match is not None
                and similarity >= self.AUTO_MATCH_SIMILARITY
            ):
                self._mark_transaction_reconciled(best_match)
                line.linked_transaction_id = best_match.id
                line.review_status = BankStatementLineStatus.MATCHED_EXISTING
                line.suggested_action = BankStatementSuggestedAction.MATCH_EXISTING
                line.confidence_score = Decimal(str(round(similarity, 3)))
                result.matched_existing_count += 1
                continue

            if best_match is not None and similarity >= self.SUGGEST_MATCH_SIMILARITY:
                line.linked_transaction_id = best_match.id
                line.suggested_action = BankStatementSuggestedAction.MATCH_EXISTING
                line.confidence_score = Decimal(str(round(similarity, 3)))
                line.review_status = BankStatementLineStatus.PENDING_REVIEW
                result.pending_review_count += 1
                continue

            if auto_classify:
                preview_transaction, classification_confidence = self._build_preview_transaction(line, user)
                if classification_confidence >= self.AUTO_CREATE_THRESHOLD:
                    transaction, _ = self._create_transaction_for_preview(
                        preview_transaction=preview_transaction,
                        line=line,
                        classification_confidence=classification_confidence,
                    )
                    line.created_transaction_id = transaction.id
                    line.linked_transaction_id = transaction.id
                    line.review_status = BankStatementLineStatus.AUTO_CREATED
                    line.suggested_action = BankStatementSuggestedAction.CREATE_NEW
                    line.confidence_score = classification_confidence
                    result.auto_created_count += 1
                    result.transactions.append(transaction)
                    continue

                line.suggested_action = BankStatementSuggestedAction.CREATE_NEW
                line.confidence_score = classification_confidence
                line.review_status = BankStatementLineStatus.PENDING_REVIEW
                result.pending_review_count += 1
                continue

            line.suggested_action = BankStatementSuggestedAction.CREATE_NEW
            line.review_status = BankStatementLineStatus.PENDING_REVIEW
            line.confidence_score = Decimal("0")
            result.pending_review_count += 1

        result.ignored_count = sum(
            1 for line in statement_import.lines if line.review_status == BankStatementLineStatus.IGNORED_DUPLICATE
        )
        return result

    def _find_best_existing_transaction(
        self,
        line: BankStatementLine,
        user_id: int,
        tax_year: Optional[int],
        require_threshold: bool,
    ) -> Tuple[Optional[Transaction], float]:
        existing_transactions = self._get_existing_transactions(user_id=user_id, tax_year=tax_year, reference_date=line.line_date)
        best_match = None
        best_similarity = 0.0
        for transaction in existing_transactions:
            if not self._amounts_match(line.amount, transaction.amount):
                continue
            if self._date_distance(line.line_date, transaction.transaction_date) > self.DATE_TOLERANCE_DAYS:
                continue
            similarity = self._match_similarity(line, transaction)
            if similarity > best_similarity:
                best_match = transaction
                best_similarity = similarity

        if require_threshold and best_similarity < self.AUTO_MATCH_SIMILARITY:
            return None, best_similarity
        return best_match, best_similarity

    def _get_existing_transactions(
        self,
        user_id: int,
        tax_year: Optional[int] = None,
        reference_date: Optional[date] = None,
    ) -> List[Transaction]:
        if self.db is None:
            return []

        query = self.db.query(Transaction).filter(Transaction.user_id == user_id)

        if reference_date is not None:
            query = query.filter(
                Transaction.transaction_date >= reference_date - timedelta(days=self.DATE_TOLERANCE_DAYS),
                Transaction.transaction_date <= reference_date + timedelta(days=self.DATE_TOLERANCE_DAYS),
            )
        elif tax_year:
            query = query.filter(
                Transaction.transaction_date >= date(tax_year, 1, 1),
                Transaction.transaction_date <= date(tax_year, 12, 31),
            )

        return query.order_by(Transaction.transaction_date.desc(), Transaction.id.desc()).all()

    def _build_preview_transaction(
        self,
        line: BankStatementLine,
        user: User,
    ) -> Tuple[Transaction, Decimal]:
        transaction_type = TransactionType.INCOME if line.amount >= 0 else TransactionType.EXPENSE
        amount = abs(Decimal(str(line.amount)))
        preview_transaction = Transaction(
            user_id=user.id,
            transaction_date=line.line_date,
            amount=amount,
            description=(line.purpose or line.counterparty or line.raw_reference or "").strip() or "Bank statement import",
            type=transaction_type,
            import_source="bank_statement",
        )

        classification_confidence = Decimal("0")
        classification_result = self.classifier.classify_transaction(
            preview_transaction,
            user_context={
                "user_type": user.user_type,
                "user_id": user.id,
                "business_type": getattr(user, "business_type", "") or "",
                "business_industry": getattr(user, "business_industry", "") or "",
            },
        )
        if classification_result.category:
            if transaction_type == TransactionType.INCOME:
                preview_transaction.income_category = classification_result.category
            else:
                preview_transaction.expense_category = classification_result.category
            preview_transaction.classification_method = classification_result.method
            preview_transaction.classification_confidence = classification_result.confidence
            classification_confidence = Decimal(str(classification_result.confidence))

        return preview_transaction, classification_confidence

    def _create_transaction_for_line(
        self,
        line: BankStatementLine,
        user: User,
        auto_classify: bool,
    ) -> Tuple[Transaction, Decimal]:
        preview_transaction, classification_confidence = self._build_preview_transaction(line, user)
        if not auto_classify:
            classification_confidence = Decimal("0")
        transaction, classification_confidence = self._create_transaction_for_preview(
            preview_transaction=preview_transaction,
            line=line,
            classification_confidence=classification_confidence,
        )
        return transaction, classification_confidence

    def _create_transaction_for_preview(
        self,
        preview_transaction: Transaction,
        line: BankStatementLine,
        classification_confidence: Decimal,
    ) -> Tuple[Transaction, Decimal]:
        self._mark_transaction_reconciled(preview_transaction)
        self.db.add(preview_transaction)
        self.db.flush()
        preview_transaction.document_id = line.statement_import.source_document_id
        return preview_transaction, classification_confidence

    def _mark_transaction_reconciled(self, transaction: Transaction) -> None:
        transaction.bank_reconciled = True
        transaction.bank_reconciled_at = datetime.utcnow()

    def _get_line_for_user(self, line_id: int, user_id: int) -> BankStatementLine:
        if self.db is None:
            raise ValueError("Database session is required")
        line = (
            self.db.query(BankStatementLine)
            .join(BankStatementImport, BankStatementImport.id == BankStatementLine.import_id)
            .filter(BankStatementLine.id == line_id, BankStatementImport.user_id == user_id)
            .first()
        )
        if line is None:
            raise ValueError("Bank statement line not found")
        return line

    def _match_similarity(self, line: BankStatementLine, transaction: Transaction) -> float:
        line_text = " ".join(filter(None, [line.counterparty or "", line.purpose or "", line.raw_reference or ""])).strip()
        transaction_text = (transaction.description or "").strip()
        if not line_text and not transaction_text:
            return 1.0
        if not line_text or not transaction_text:
            return 0.0

        normalized_line = line_text.lower()
        normalized_transaction = transaction_text.lower()
        if self.duplicate_detector is not None and hasattr(self.duplicate_detector, "_is_similar_description"):
            matcher = SequenceMatcher(None, normalized_line, normalized_transaction)
            return matcher.ratio()

        return SequenceMatcher(None, normalized_line, normalized_transaction).ratio()

    @staticmethod
    def _amounts_match(lhs: Decimal, rhs: Decimal) -> bool:
        return abs(Decimal(str(lhs))) == abs(Decimal(str(rhs)))

    @staticmethod
    def _date_distance(lhs: date, rhs: date) -> int:
        return abs((lhs - rhs).days)

    @staticmethod
    def _coerce_to_decimal(value: Any) -> Optional[Decimal]:
        if value is None or value == "":
            return None
        try:
            text = str(value).strip().replace("EUR", "").replace("€", "")
            if "," in text and "." in text:
                text = text.replace(".", "").replace(",", ".")
            else:
                text = text.replace(",", ".")
            return Decimal(text)
        except Exception:
            return None

    @staticmethod
    def _coerce_to_date(value: Any) -> Optional[date]:
        if isinstance(value, date):
            return value
        if isinstance(value, datetime):
            return value.date()
        if value is None:
            return None
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @staticmethod
    def _build_statement_period(transactions: Iterable[Dict[str, Any]]) -> Optional[Dict[str, str]]:
        dates = [item["date"] for item in transactions if item.get("date") is not None]
        if not dates:
            return None
        start_date = min(dates)
        end_date = max(dates)
        return {"start": start_date.isoformat(), "end": end_date.isoformat()}

    @staticmethod
    def _infer_tax_year(transactions: Iterable[Dict[str, Any]]) -> Optional[int]:
        dates = [item["date"] for item in transactions if item.get("date") is not None]
        return max(dates).year if dates else None

    @staticmethod
    def _build_fingerprint(parsed_transaction: Dict[str, Any]) -> str:
        description = (
            parsed_transaction.get("description")
            or parsed_transaction.get("purpose")
            or parsed_transaction.get("counterparty")
            or ""
        )
        normalized = " ".join(str(description).lower().split())
        raw_reference = (parsed_transaction.get("reference") or "").strip().lower()
        return "|".join(
            [
                parsed_transaction["date"].isoformat(),
                str(abs(Decimal(str(parsed_transaction["amount"])))),
                normalized,
                raw_reference,
            ]
        )
