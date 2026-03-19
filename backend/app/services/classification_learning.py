"""Classification learning service for managing corrections and ML retraining."""

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.classification_correction import ClassificationCorrection
from app.models.transaction import Transaction
from app.services.ml_classifier import MLClassifier


class ClassificationLearningService:
    """Manage correction storage, training-data extraction, and retraining metadata."""

    TRAINABLE_SOURCES = {"human_verified", "llm_consensus"}

    def __init__(self, db: Session, model_path: Optional[str] = None):
        self.db = db
        self.ml_classifier = MLClassifier(model_path=model_path)
        self.model_path = self.ml_classifier.model_path
        self.min_corrections_for_retrain = 50
        self._last_trained_at_path = os.path.join(
            self.model_path, "classification_last_trained_at.json"
        )

    def _ensure_model_dir(self) -> None:
        os.makedirs(self.model_path, exist_ok=True)

    def _save_last_trained_at(self, value: datetime) -> None:
        self._ensure_model_dir()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        with open(self._last_trained_at_path, "w", encoding="utf-8") as f:
            json.dump({"last_trained_at": value.isoformat()}, f)

    def get_last_trained_at(self) -> Optional[datetime]:
        if not os.path.exists(self._last_trained_at_path):
            return None
        try:
            with open(self._last_trained_at_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
            raw = payload.get("last_trained_at")
            return datetime.fromisoformat(raw) if raw else None
        except Exception:
            return None

    def store_correction(
        self,
        transaction_id: int,
        user_id: int,
        original_category: str,
        correct_category: str,
        original_confidence: Optional[str] = None,
        source: str = "human_verified",
    ) -> ClassificationCorrection:
        """Persist a correction row."""
        correction = ClassificationCorrection(
            transaction_id=transaction_id,
            user_id=user_id,
            original_category=original_category,
            correct_category=correct_category,
            original_confidence=original_confidence,
            source=source,
        )
        self.db.add(correction)
        self.db.commit()
        self.db.refresh(correction)
        return correction

    def get_corrections_count(self) -> int:
        """Return total correction count."""
        return self.db.query(ClassificationCorrection).count()

    def get_corrections_since_last_training(self) -> int:
        """Count corrections created since the last persisted training timestamp."""
        last_trained_at = self.get_last_trained_at()
        if last_trained_at is None:
            return self.get_corrections_count()

        return (
            self.db.query(ClassificationCorrection)
            .filter(ClassificationCorrection.created_at > last_trained_at)
            .count()
        )

    def should_retrain(self) -> bool:
        """Check if retraining threshold has been reached."""
        return self.get_corrections_since_last_training() >= self.min_corrections_for_retrain

    def get_training_data(self) -> List[Tuple[str, float, str, str]]:
        """Build model training tuples from trusted corrections only."""
        corrections = (
            self.db.query(ClassificationCorrection)
            .join(Transaction, ClassificationCorrection.transaction_id == Transaction.id)
            .filter(
                or_(
                    ClassificationCorrection.source.in_(self.TRAINABLE_SOURCES),
                    ClassificationCorrection.source.is_(None),
                )
            )
            .all()
        )

        training_data: List[Tuple[str, float, str, str]] = []
        for correction in corrections:
            transaction = correction.transaction
            txn_type = getattr(getattr(transaction, "type", None), "value", None) or str(
                getattr(transaction, "type", "expense")
            )
            normalized_type = "income" if "income" in str(txn_type).lower() else "expense"
            training_data.append(
                (
                    transaction.description or "",
                    float(transaction.amount),
                    correction.correct_category,
                    normalized_type,
                )
            )
        return training_data

    def retrain_model(self) -> bool:
        """Retrain ML model and persist the training timestamp on success."""
        training_data = self.get_training_data()
        if len(training_data) < self.ml_classifier.min_training_samples:
            return False

        success = self.ml_classifier.train_model(training_data)
        if success:
            self._save_last_trained_at(datetime.now(timezone.utc))
        return success

    def get_correction_stats(self) -> Dict[str, Any]:
        """Return high-level correction statistics."""
        total_corrections = self.get_corrections_count()
        most_corrected = (
            self.db.query(
                ClassificationCorrection.original_category,
                func.count(ClassificationCorrection.id).label("count"),
            )
            .group_by(ClassificationCorrection.original_category)
            .order_by(func.count(ClassificationCorrection.id).desc())
            .limit(5)
            .all()
        )
        return {
            "total_corrections": total_corrections,
            "most_corrected_categories": [
                {"category": category, "count": count} for category, count in most_corrected
            ],
            "should_retrain": self.should_retrain(),
        }

    def get_training_audit_report(self) -> Dict[str, Any]:
        """Return source-distribution and trainability metrics for corrections."""
        rows = (
            self.db.query(
                ClassificationCorrection.source,
                func.count(ClassificationCorrection.id),
            )
            .group_by(ClassificationCorrection.source)
            .all()
        )

        by_source: Dict[str, Dict[str, Any]] = {}
        total = 0
        trainable = 0
        for source, count in rows:
            key = "legacy_null" if source is None else str(source)
            total += count
            is_trainable = source is None or source in self.TRAINABLE_SOURCES
            if is_trainable:
                trainable += count
            by_source[key] = {
                "count": count,
                "trainable": is_trainable,
            }

        excluded = total - trainable
        return {
            "total_corrections": total,
            "trainable_count": trainable,
            "excluded_count": excluded,
            "by_source": by_source,
            "ready_to_retrain": trainable >= self.min_corrections_for_retrain,
            "net_trainable_ratio": round(trainable / total, 4) if total else 0.0,
        }

    def auto_retrain_if_needed(self) -> Dict[str, Any]:
        """Retrain automatically when enough new corrections are available."""
        new_corrections = self.get_corrections_since_last_training()
        total_corrections = self.get_corrections_count()
        if new_corrections < self.min_corrections_for_retrain:
            return {
                "retrained": False,
                "reason": "Not enough corrections for retraining",
                "new_corrections": new_corrections,
                "total_corrections": total_corrections,
                "min_required": self.min_corrections_for_retrain,
            }

        success = self.retrain_model()
        if success:
            last_trained_at = self.get_last_trained_at()
            return {
                "retrained": True,
                "new_corrections": new_corrections,
                "total_corrections": total_corrections,
                "last_trained_at": last_trained_at.isoformat() if last_trained_at else None,
                "message": "Model retrained successfully",
            }

        return {
            "retrained": False,
            "reason": "Retraining failed",
            "new_corrections": new_corrections,
            "total_corrections": total_corrections,
        }

    def record_ocr_correction(
        self,
        document_id: int,
        previous_data: dict,
        corrected_data: dict,
        user_id: int,
    ) -> bool:
        """Record OCR correction metadata for later accuracy reporting."""
        from app.models.document import Document
        from sqlalchemy.orm.attributes import flag_modified

        document = self.db.query(Document).filter(Document.id == document_id).first()
        if not document:
            return False

        ocr_result = document.ocr_result or {}
        ocr_result.setdefault("learning_data", []).append(
            {
                "corrected_by": user_id,
                "previous_data": previous_data,
                "corrected_data": corrected_data,
                "correction_timestamp": str(self.db.execute("SELECT NOW()").scalar()),
            }
        )
        document.ocr_result = ocr_result
        flag_modified(document, "ocr_result")
        self.db.commit()
        return True

    def get_extraction_accuracy(self) -> Dict[str, Any]:
        """Calculate OCR extraction accuracy statistics from stored learning data."""
        from app.models.document import Document

        documents = self.db.query(Document).filter(Document.ocr_result.isnot(None)).all()
        by_document_type: Dict[str, Dict[str, Any]] = {}
        total_corrections = 0

        for document in documents:
            ocr_result = getattr(document, "ocr_result", None) or {}
            learning_data = ocr_result.get("learning_data") or []
            if not learning_data:
                continue

            document_type = (
                getattr(getattr(document, "document_type", None), "value", None) or "unknown"
            )
            document_stats = by_document_type.setdefault(
                document_type,
                {"total_corrections": 0, "fields": {}},
            )

            for entry in learning_data:
                previous_data = entry.get("previous_data") or {}
                corrected_data = entry.get("corrected_data") or {}
                field_names = set(previous_data.keys()) | set(corrected_data.keys())
                if not field_names:
                    continue

                total_corrections += 1
                document_stats["total_corrections"] += 1

                for field_name in field_names:
                    field_stats = document_stats["fields"].setdefault(
                        field_name,
                        {"total": 0, "changed": 0, "accuracy": 1.0},
                    )
                    field_stats["total"] += 1
                    if previous_data.get(field_name) != corrected_data.get(field_name):
                        field_stats["changed"] += 1

        low_accuracy_fields = []
        for document_type, document_stats in by_document_type.items():
            for field_name, field_stats in document_stats["fields"].items():
                total = field_stats["total"]
                changed = field_stats["changed"]
                accuracy = round((total - changed) / total, 4) if total else 1.0
                field_stats["accuracy"] = accuracy
                if total >= 5 and accuracy < 0.8:
                    low_accuracy_fields.append(
                        {
                            "document_type": document_type,
                            "field": field_name,
                            "total": total,
                            "changed": changed,
                            "accuracy": accuracy,
                        }
                    )

        low_accuracy_fields.sort(key=lambda item: (item["accuracy"], -item["total"], item["field"]))
        return {
            "total_corrections": total_corrections,
            "by_document_type": by_document_type,
            "low_accuracy_fields": low_accuracy_fields,
        }
