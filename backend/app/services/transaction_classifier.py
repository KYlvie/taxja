"""Hybrid transaction classifier combining user rules, rule-based, ML, and LLM approaches."""

from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from .ml_classifier import MLClassifier
from .rule_based_classifier import RuleBasedClassifier


class ClassificationResult:
    """Result of transaction classification."""

    def __init__(
        self,
        category: Optional[str],
        confidence: Decimal,
        category_type: Optional[str] = None,
        method: str = "unknown",
    ):
        self.category = category
        self.confidence = confidence
        self.category_type = category_type
        self.method = method

    def __repr__(self):
        return (
            f"<ClassificationResult(category={self.category}, "
            f"confidence={self.confidence}, method={self.method})>"
        )


class TransactionClassifier:
    """
    Hybrid transaction classifier.

    Order of precedence:
    1. Per-user override rules
    2. Global rule-based classifier
    3. ML classifier
    4. LLM fallback when confidence is still low
    """

    HIGH_CONFIDENCE_THRESHOLD = Decimal("0.8")
    LLM_CORRECTION_STORAGE_THRESHOLD = Decimal("0.60")
    LLM_RULE_PROMOTION_THRESHOLD = Decimal("0.85")
    SOFT_RULE_CONFIDENCE_CAP = Decimal("0.80")

    def __init__(self, model_path: Optional[str] = None, db: Optional[Session] = None):
        self.rule_classifier = RuleBasedClassifier()
        self.ml_classifier = MLClassifier(model_path=model_path)
        self.db = db

        if db is not None:
            from .user_classification_service import UserClassificationService

            self._user_svc = UserClassificationService(db)
        else:
            self._user_svc = None

    def classify_transaction(
        self, transaction, user_context=None, *, _store_side_effects: bool = True
    ) -> ClassificationResult:
        """Classify a transaction using the hybrid pipeline.

        Args:
            _store_side_effects: When False, skip LLM correction storage.
                Used by learn_from_correction to avoid creating a duplicate
                ClassificationCorrection record.
        """
        if not getattr(transaction, "description", None):
            return ClassificationResult(
                category=None,
                confidence=Decimal("0.0"),
                method="none",
            )

        user_override = self._try_user_override(transaction)
        if user_override is not None:
            return user_override

        rule_result = self.rule_classifier.classify(transaction)
        if rule_result.confidence >= self.HIGH_CONFIDENCE_THRESHOLD:
            return ClassificationResult(
                category=rule_result.category,
                confidence=rule_result.confidence,
                category_type=rule_result.category_type,
                method="rule",
            )

        ml_result = self.ml_classifier.classify(transaction, user_context)
        if ml_result.confidence > rule_result.confidence:
            best_result = ClassificationResult(
                category=ml_result.category,
                confidence=ml_result.confidence,
                category_type=ml_result.category_type,
                method="ml",
            )
        else:
            best_result = ClassificationResult(
                category=rule_result.category,
                confidence=rule_result.confidence,
                category_type=rule_result.category_type,
                method="rule",
            )

        if best_result.confidence < Decimal("0.90"):
            llm_result = self._try_llm_classify(
                transaction, user_context, _store=_store_side_effects
            )
            if llm_result is not None and llm_result.confidence > best_result.confidence:
                return llm_result

        return best_result

    def get_confidence_score(self, transaction) -> Decimal:
        """Get confidence score for transaction classification."""
        return self.classify_transaction(transaction).confidence

    def learn_from_correction(self, transaction, correct_category: str, user_id: int):
        """Learn from a human correction and persist strict user rules when possible."""
        if self.db is None:
            self.ml_classifier.add_training_example(transaction, correct_category, user_id)
            return

        from app.models.classification_correction import ClassificationCorrection

        original_result = self.classify_transaction(transaction, _store_side_effects=False)
        correction = ClassificationCorrection(
            transaction_id=transaction.id,
            user_id=user_id,
            original_category=original_result.category or "unknown",
            correct_category=correct_category,
            original_confidence=str(original_result.confidence),
            source="human_verified",
        )
        self.db.add(correction)

        user_service = getattr(self, "_user_svc", None)
        if user_service is not None and getattr(transaction, "description", None):
            existing_rule = user_service.lookup(
                user_id=user_id,
                description=transaction.description,
                txn_type=self._get_txn_type(transaction),
            )
            if existing_rule is not None and existing_rule.category != correct_category:
                user_service.record_conflict(existing_rule)

            user_service.upsert_rule(
                user_id=user_id,
                description=transaction.description,
                txn_type=self._get_txn_type(transaction),
                category=correct_category,
                rule_type="strict",
            )

        self.db.commit()

    def should_retrain(self) -> bool:
        """Check if ML model should be retrained."""
        return self.ml_classifier.should_retrain()

    def retrain(self, training_data):
        """Retrain ML model with new data."""
        return self.ml_classifier.train_model(training_data)

    def _try_user_override(self, transaction) -> Optional[ClassificationResult]:
        """Apply a per-user override rule before global classifiers."""
        user_service = getattr(self, "_user_svc", None)
        if user_service is None:
            return None

        user_id = getattr(transaction, "user_id", None)
        description = getattr(transaction, "description", None)
        if not user_id or not description:
            return None

        rule = user_service.lookup(
            user_id=user_id,
            description=description,
            txn_type=self._get_txn_type(transaction),
        )
        if rule is None:
            return None

        if getattr(rule, "frozen", False) is True:
            return None

        category = getattr(rule, "category", None)
        if not isinstance(category, str) or not category:
            return None

        try:
            confidence = Decimal(str(getattr(rule, "confidence", Decimal("1.00"))))
        except Exception:
            return None

        user_service.record_hit(rule)

        rule_type = getattr(rule, "rule_type", "strict")
        if rule_type == "soft":
            return ClassificationResult(
                category=category,
                confidence=min(confidence, self.SOFT_RULE_CONFIDENCE_CAP),
                category_type=self._get_txn_type(transaction),
                method="user_rule_soft",
            )

        return ClassificationResult(
            category=category,
            confidence=confidence,
            category_type=self._get_txn_type(transaction),
            method="user_rule",
        )

    @staticmethod
    def _get_txn_type(transaction) -> str:
        """Normalize enum-like or raw transaction types to strings."""
        txn_type = getattr(transaction, "type", "expense")
        return str(getattr(txn_type, "value", txn_type))

    @staticmethod
    def _extract_user_profile(user_context) -> Tuple[str, str, str]:
        """Extract user profile fields from dicts or ORM-like objects."""

        def _resolve(value, default: str = "") -> str:
            if value is None:
                return default
            return str(getattr(value, "value", value))

        if user_context is None:
            return "employee", "", ""

        if isinstance(user_context, dict):
            return (
                _resolve(user_context.get("user_type"), "employee") or "employee",
                _resolve(user_context.get("business_type"), ""),
                _resolve(
                    user_context.get("business_industry", user_context.get("industry")),
                    "",
                ),
            )

        return (
            _resolve(getattr(user_context, "user_type", None), "employee") or "employee",
            _resolve(getattr(user_context, "business_type", None), ""),
            _resolve(
                getattr(
                    user_context,
                    "business_industry",
                    getattr(user_context, "industry", None),
                ),
                "",
            ),
        )

    def _store_llm_correction(self, transaction, llm_result, user_type: str = "employee") -> None:
        """Persist LLM output and optionally promote it into a soft user rule."""
        if self.db is None:
            return

        transaction_id = getattr(transaction, "id", None)
        user_id = getattr(transaction, "user_id", None)
        description = getattr(transaction, "description", None)
        if not transaction_id or not user_id or not description:
            return

        confidence = Decimal(str(getattr(llm_result, "confidence", Decimal("0.0"))))
        if confidence < self.LLM_CORRECTION_STORAGE_THRESHOLD:
            return

        from app.models.classification_correction import ClassificationCorrection

        source = (
            "llm_verified"
            if confidence >= self.LLM_RULE_PROMOTION_THRESHOLD
            else "llm_unverified"
        )

        correction = ClassificationCorrection(
            transaction_id=transaction_id,
            user_id=user_id,
            original_category="unknown",
            correct_category=llm_result.category,
            original_confidence=str(confidence),
            source=source,
        )

        try:
            self.db.add(correction)

            user_service = getattr(self, "_user_svc", None)
            if (
                user_service is not None
                and confidence >= self.LLM_RULE_PROMOTION_THRESHOLD
            ):
                user_service.upsert_rule(
                    user_id=user_id,
                    description=description,
                    txn_type=self._get_txn_type(transaction),
                    category=llm_result.category,
                    rule_type="soft",
                )

            self.db.commit()
        except Exception:
            self.db.rollback()

    def _try_llm_classify(
        self, transaction, user_context=None, *, _store: bool = True
    ) -> Optional[ClassificationResult]:
        """Try the LLM-backed classifier when rule+ML confidence stays low."""
        try:
            from app.services.llm_classifier import get_llm_classifier

            llm = get_llm_classifier()
            if not llm.is_available:
                return None

            user_type, business_type, business_industry = self._extract_user_profile(
                user_context
            )
            llm_result = llm.classify(
                description=getattr(transaction, "description", "") or "",
                amount=float(getattr(transaction, "amount", 0) or 0),
                txn_type=self._get_txn_type(transaction),
                user_type=user_type,
                business_type=business_type,
                business_industry=business_industry,
            )
            if llm_result is None:
                return None

            result = ClassificationResult(
                category=llm_result.category,
                confidence=Decimal(str(llm_result.confidence)),
                category_type=llm_result.category_type,
                method="llm",
            )
            result.is_deductible = getattr(llm_result, "is_deductible", None)
            result.deduction_reason = getattr(llm_result, "deduction_reason", None)

            if _store:
                self._store_llm_correction(transaction, llm_result, user_type)
            return result
        except Exception:
            return None
