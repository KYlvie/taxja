"""Unified proactive reminders with persistent lifecycle state."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.employer_annual_archive import EmployerAnnualArchiveStatus
from app.models.recurring_transaction import RecurringTransaction
from app.models.reminder_state import ReminderState
from app.models.user import User, UserType
from app.services.employer_month_service import EmployerMonthService
from app.services.tax_health_service import TaxHealthService

logger = logging.getLogger(__name__)


TERMINAL_ACTION = "terminal_action"
SNOOZEABLE_CONDITION = "snoozeable_condition"
TIME_BASED_REPEAT = "time_based_repeat"

_DEFAULT_SNOOZE_DAYS = {
    SNOOZEABLE_CONDITION: 14,
    TIME_BASED_REPEAT: 7,
}

_DOCUMENT_LEGACY_TYPES = {
    "create_recurring_income": "recurring_confirm",
    "create_recurring_expense": "recurring_confirm",
    "create_property": "asset_confirm",
    "create_asset": "asset_confirm",
    "create_loan": "reminder",
    "create_loan_repayment": "reminder",
}

_DOCUMENT_BODY_KEYS = {
    "create_recurring_income": "ai.proactive.pendingRecurringIncome",
    "create_recurring_expense": "ai.proactive.pendingRecurringExpense",
    "create_property": "ai.proactive.propertySuggestionPending",
    "create_asset": "ai.proactive.assetFound",
    "create_loan": "ai.proactive.loanSuggestionPending",
    "create_loan_repayment": "ai.proactive.loanRepaymentSuggestionPending",
}


def _normalize_for_fingerprint(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {
            str(key): _normalize_for_fingerprint(inner)
            for key, inner in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_for_fingerprint(inner) for inner in value]
    if isinstance(value, set):
        return sorted(_normalize_for_fingerprint(inner) for inner in value)
    return value


def _make_fingerprint(payload: Dict[str, Any]) -> str:
    normalized = _normalize_for_fingerprint(payload)
    raw = json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _encode_reminder_id(payload: Dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_reminder_id(reminder_id: str) -> Dict[str, Any]:
    padded = reminder_id + "=" * (-len(reminder_id) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
    data = json.loads(decoded)
    if not isinstance(data, dict):
        raise ValueError("invalid reminder id")
    return data


class ProactiveReminderService:
    """Aggregates proactive reminders and persists snooze/resolve state."""

    def __init__(self, db: Session):
        self.db = db

    def get_reminders(self, user: User, tax_year: Optional[int] = None) -> List[Dict[str, Any]]:
        resolved_year = tax_year or (datetime.now().year - 1)
        now = datetime.utcnow()
        reminders: List[Dict[str, Any]] = []
        present_non_document_keys: set[tuple[str, str]] = set()

        for reminder in self._build_document_suggestion_reminders(user, resolved_year):
            reminders.append(self._serialize_document_reminder(reminder))

        for reminder in self._build_recurring_reminders(user):
            present_non_document_keys.add((reminder["kind"], reminder["fingerprint"]))
            serialized = self._apply_state_and_serialize(user.id, reminder, now)
            if serialized:
                reminders.append(serialized)

        for reminder in self._build_health_check_reminders(user, resolved_year):
            present_non_document_keys.add((reminder["kind"], reminder["fingerprint"]))
            serialized = self._apply_state_and_serialize(user.id, reminder, now)
            if serialized:
                reminders.append(serialized)

        for reminder in self._build_employer_reminders(user, resolved_year):
            present_non_document_keys.add((reminder["kind"], reminder["fingerprint"]))
            serialized = self._apply_state_and_serialize(user.id, reminder, now)
            if serialized:
                reminders.append(serialized)

        self._resolve_absent_states(user.id, present_non_document_keys, now)
        self.db.flush()

        reminders.sort(key=self._sort_key)
        return reminders

    def snooze_reminder(self, user_id: int, reminder_id: str, days: Optional[int] = None) -> Dict[str, Any]:
        payload = decode_reminder_id(reminder_id)
        bucket = payload.get("bucket")
        if bucket == TERMINAL_ACTION or payload.get("source_type") == "document_suggestion":
            raise ValueError("terminal reminders cannot be snoozed")

        state = self._get_or_create_state(
            user_id=user_id,
            reminder_kind=str(payload["kind"]),
            bucket=str(bucket),
            fingerprint=str(payload["fingerprint"]),
        )

        snooze_days = int(days or self._default_snooze_days(payload))
        snoozed_until = datetime.utcnow() + timedelta(days=snooze_days)
        state.status = "snoozed"
        state.snoozed_until = snoozed_until
        state.resolved_at = None
        state.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "id": reminder_id,
            "status": "snoozed",
            "snoozed_until": snoozed_until.isoformat(),
            "days": snooze_days,
        }

    def acknowledge_reminder(self, user_id: int, reminder_id: str) -> Dict[str, Any]:
        payload = decode_reminder_id(reminder_id)
        bucket = payload.get("bucket")
        if bucket == TERMINAL_ACTION or payload.get("source_type") == "document_suggestion":
            raise ValueError("terminal reminders cannot be acknowledged here")

        state = self._get_or_create_state(
            user_id=user_id,
            reminder_kind=str(payload["kind"]),
            bucket=str(bucket),
            fingerprint=str(payload["fingerprint"]),
        )
        state.status = "resolved"
        state.snoozed_until = None
        state.resolved_at = datetime.utcnow()
        state.updated_at = datetime.utcnow()
        self.db.commit()

        return {
            "id": reminder_id,
            "status": "resolved",
            "resolved_at": state.resolved_at.isoformat() if state.resolved_at else None,
        }

    def _build_document_suggestion_reminders(self, user: User, tax_year: int) -> List[Dict[str, Any]]:
        reminders: List[Dict[str, Any]] = []
        docs = (
            self.db.query(Document)
            .filter(Document.user_id == user.id, Document.ocr_result.isnot(None))
            .order_by(Document.uploaded_at.desc())
            .all()
        )

        for doc in docs:
            ocr_result = doc.ocr_result if isinstance(doc.ocr_result, dict) else {}
            suggestion = ocr_result.get("import_suggestion")
            if not isinstance(suggestion, dict) or suggestion.get("status") != "pending":
                continue

            suggestion_type = str(suggestion.get("type") or "")
            if not suggestion_type:
                continue

            if not self._is_supported_document_suggestion(suggestion_type):
                continue

            data = suggestion.get("data") if isinstance(suggestion.get("data"), dict) else {}
            description = data.get("description") or data.get("address") or doc.file_name
            amount = data.get("monthly_rent") or data.get("amount")
            body_key = (
                "ai.proactive.pendingTaxForm"
                if suggestion_type.startswith("import_")
                else _DOCUMENT_BODY_KEYS.get(suggestion_type, "ai.proactive.pendingDocumentSuggestion")
            )
            legacy_type = (
                "tax_form_review"
                if suggestion_type.startswith("import_")
                else _DOCUMENT_LEGACY_TYPES.get(suggestion_type, "reminder")
            )
            action = self._build_document_action(suggestion_type, doc.id)
            fingerprint = _make_fingerprint(
                {
                    "document_id": doc.id,
                    "suggestion_type": suggestion_type,
                    "status": suggestion.get("status"),
                    "version": suggestion.get("version"),
                }
            )
            reminders.append(
                {
                    "kind": "document_suggestion",
                    "bucket": TERMINAL_ACTION,
                    "fingerprint": fingerprint,
                    "title_key": "ai.notifications",
                    "body_key": body_key,
                    "params": {
                        "name": doc.file_name,
                        "fileName": doc.file_name,
                        "description": description,
                        "amount": amount,
                        "frequency": data.get("frequency"),
                        "year": data.get("tax_year") or tax_year,
                    },
                    "severity": "medium",
                    "primary_action": {"kind": "confirm"},
                    "secondary_action": {"kind": "dismiss"},
                    "link": f"/documents/{doc.id}",
                    "source_type": "document_suggestion",
                    "document_id": doc.id,
                    "tax_year": data.get("tax_year") or tax_year,
                    "legacy_type": legacy_type,
                    "action_data": {
                        "suggestion_type": suggestion_type,
                        **data,
                    },
                    "action": action,
                }
            )

        return reminders

    def _build_recurring_reminders(self, user: User) -> List[Dict[str, Any]]:
        reminders: List[Dict[str, Any]] = []
        today = date.today()
        soon = today + timedelta(days=30)
        recurrings = (
            self.db.query(RecurringTransaction)
            .filter(RecurringTransaction.user_id == user.id, RecurringTransaction.end_date.isnot(None))
            .all()
        )

        for recurring in recurrings:
            if recurring.end_date is None:
                continue

            if recurring.end_date < today:
                kind = "recurring_expired"
                body_key = "ai.proactive.contractExpired"
                bucket = TIME_BASED_REPEAT
                params = {
                    "description": recurring.description,
                    "endDate": recurring.end_date.isoformat(),
                    "days": (today - recurring.end_date).days,
                }
                severity = "high" if (today - recurring.end_date).days >= 30 else "medium"
            elif recurring.end_date <= soon:
                kind = "recurring_expiring"
                body_key = "ai.proactive.contractExpiring"
                bucket = TIME_BASED_REPEAT
                params = {
                    "description": recurring.description,
                    "endDate": recurring.end_date.isoformat(),
                    "days": (recurring.end_date - today).days,
                }
                severity = "medium"
            else:
                continue

            fingerprint = _make_fingerprint(
                {
                    "recurring_id": recurring.id,
                    "phase": kind,
                    "end_date": recurring.end_date,
                }
            )
            reminders.append(
                {
                    "kind": kind,
                    "bucket": bucket,
                    "fingerprint": fingerprint,
                    "title_key": "ai.notifications",
                    "body_key": body_key,
                    "params": params,
                    "severity": severity,
                    "primary_action": {"kind": "view"},
                    "secondary_action": {"kind": "snooze"},
                    "link": "/recurring",
                    "source_type": "recurring",
                    "recurring_id": recurring.id,
                    "next_due_at": recurring.end_date.isoformat(),
                    "legacy_type": "contract_expired" if kind == "recurring_expired" else "reminder",
                    "action_data": {
                        "description": recurring.description,
                        "end_date": recurring.end_date.isoformat(),
                        "recurring_id": recurring.id,
                    },
                }
            )

        return reminders

    def _build_health_check_reminders(self, user: User, tax_year: int) -> List[Dict[str, Any]]:
        reminders: List[Dict[str, Any]] = []
        health = TaxHealthService(self.db).check_health(user.id, tax_year)
        items = health.get("items", []) if isinstance(health, dict) else []
        score = health.get("score", 100) if isinstance(health, dict) else 100

        for item in items:
            if not isinstance(item, dict):
                continue
            category = str(item.get("category") or "health_check")
            bucket = TIME_BASED_REPEAT if category == "deadline_reminder" else SNOOZEABLE_CONDITION
            reminder_kind = "deadline_reminder" if category == "deadline_reminder" else "health_check_item"
            fingerprint = _make_fingerprint(
                {
                    "category": category,
                    "key": item.get("i18n_key"),
                    "params": item.get("i18n_params"),
                    "tax_year": tax_year,
                    "action_url": item.get("action_url"),
                }
            )
            reminders.append(
                {
                    "kind": reminder_kind,
                    "bucket": bucket,
                    "fingerprint": fingerprint,
                    "title_key": "healthCheck.title",
                    "body_key": item.get("i18n_key") or "healthCheck.title",
                    "params": item.get("i18n_params") or {},
                    "severity": item.get("severity") or "medium",
                    "primary_action": {"kind": "view"},
                    "secondary_action": {"kind": "snooze"},
                    "link": item.get("action_url"),
                    "source_type": "health_check",
                    "tax_year": tax_year,
                    "legacy_type": "health_check",
                    "action_data": {
                        "category": category,
                        "potential_savings": item.get("potential_savings"),
                        "action_label_key": item.get("action_label_key"),
                    },
                }
            )

        if score < 80:
            fingerprint = _make_fingerprint(
                {
                    "kind": "health_summary",
                    "tax_year": tax_year,
                    "score": score,
                    "item_keys": sorted(
                        str(item.get("i18n_key"))
                        for item in items
                        if isinstance(item, dict) and item.get("i18n_key")
                    ),
                }
            )
            reminders.append(
                {
                    "kind": "health_check_summary",
                    "bucket": SNOOZEABLE_CONDITION,
                    "fingerprint": fingerprint,
                    "title_key": "healthCheck.title",
                    "body_key": "ai.proactive.healthSummaryReminder",
                    "params": {
                        "score": score,
                        "count": len(items),
                    },
                    "severity": "high" if score < 50 else "medium",
                    "primary_action": {"kind": "view"},
                    "secondary_action": {"kind": "snooze"},
                    "link": "/dashboard",
                    "source_type": "health_check",
                    "tax_year": tax_year,
                    "legacy_type": "health_check",
                    "action_data": {
                        "score": score,
                        "count": len(items),
                    },
                }
            )

        return reminders

    def _build_employer_reminders(self, user: User, tax_year: int) -> List[Dict[str, Any]]:
        can_check = (
            bool(user.employer_mode)
            and user.employer_mode != "none"
            and user.user_type in (UserType.SELF_EMPLOYED, UserType.MIXED)
        )
        if not can_check:
            return []

        reminders: List[Dict[str, Any]] = []
        service = EmployerMonthService(self.db)
        overview = service.get_overview(user.id, tax_year, user.employer_mode or "none")
        missing_confirmation_months = int(overview.get("missing_confirmation_months") or 0)
        if missing_confirmation_months > 0:
            fingerprint = _make_fingerprint(
                {
                    "kind": "employer_missing_months",
                    "year": tax_year,
                    "count": missing_confirmation_months,
                    "next_deadline": overview.get("next_deadline"),
                }
            )
            reminders.append(
                {
                    "kind": "employer_missing_months",
                    "bucket": SNOOZEABLE_CONDITION,
                    "fingerprint": fingerprint,
                    "title_key": "ai.notifications",
                    "body_key": "ai.proactive.employerMissingMonthsReminder",
                    "params": {
                        "count": missing_confirmation_months,
                        "date": overview.get("next_deadline").isoformat()
                        if overview.get("next_deadline")
                        else None,
                    },
                    "severity": "medium",
                    "primary_action": {"kind": "view"},
                    "secondary_action": {"kind": "snooze"},
                    "link": "/documents",
                    "source_type": "employer",
                    "tax_year": tax_year,
                    "legacy_type": "reminder",
                }
            )

        archives = service.list_annual_archives(user.id)
        pending_archives = [
            archive
            for archive in archives
            if archive.status == EmployerAnnualArchiveStatus.PENDING_CONFIRMATION
        ]
        if pending_archives:
            fingerprint = _make_fingerprint(
                {
                    "kind": "employer_pending_archives",
                    "years": sorted(archive.tax_year for archive in pending_archives),
                }
            )
            reminders.append(
                {
                    "kind": "employer_pending_archives",
                    "bucket": SNOOZEABLE_CONDITION,
                    "fingerprint": fingerprint,
                    "title_key": "ai.notifications",
                    "body_key": "ai.proactive.employerPendingArchivesReminder",
                    "params": {"count": len(pending_archives)},
                    "severity": "medium",
                    "primary_action": {"kind": "view"},
                    "secondary_action": {"kind": "snooze"},
                    "link": "/documents",
                    "source_type": "employer",
                    "tax_year": tax_year,
                    "legacy_type": "reminder",
                }
            )

        return reminders

    def _apply_state_and_serialize(
        self,
        user_id: int,
        reminder: Dict[str, Any],
        now: datetime,
    ) -> Optional[Dict[str, Any]]:
        state = self._get_or_create_state(
            user_id=user_id,
            reminder_kind=reminder["kind"],
            bucket=reminder["bucket"],
            fingerprint=reminder["fingerprint"],
        )

        if state.status == "resolved":
            state.status = "active"
            state.resolved_at = None

        if state.status == "snoozed" and state.snoozed_until and state.snoozed_until > now:
            return None

        if state.status == "snoozed" and (state.snoozed_until is None or state.snoozed_until <= now):
            state.status = "active"
            state.snoozed_until = None
            state.resolved_at = None

        state.last_seen_at = now
        state.updated_at = now
        return self._serialize_non_document_reminder(reminder, state)

    def _resolve_absent_states(
        self,
        user_id: int,
        current_keys: Iterable[tuple[str, str]],
        now: datetime,
    ) -> None:
        current_key_set = set(current_keys)
        states = (
            self.db.query(ReminderState)
            .filter(
                ReminderState.user_id == user_id,
                ReminderState.status.in_(["active", "snoozed"]),
            )
            .all()
        )
        for state in states:
            if (state.reminder_kind, state.fingerprint) in current_key_set:
                continue
            state.status = "resolved"
            state.snoozed_until = None
            state.resolved_at = now
            state.updated_at = now

    def _get_or_create_state(
        self,
        *,
        user_id: int,
        reminder_kind: str,
        bucket: str,
        fingerprint: str,
    ) -> ReminderState:
        state = (
            self.db.query(ReminderState)
            .filter(
                ReminderState.user_id == user_id,
                ReminderState.reminder_kind == reminder_kind,
                ReminderState.fingerprint == fingerprint,
            )
            .first()
        )
        if state:
            return state

        state = ReminderState(
            user_id=user_id,
            reminder_kind=reminder_kind,
            bucket=bucket,
            fingerprint=fingerprint,
            status="active",
        )
        self.db.add(state)
        self.db.flush()
        return state

    def _serialize_document_reminder(self, reminder: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            "kind": reminder["kind"],
            "bucket": reminder["bucket"],
            "fingerprint": reminder["fingerprint"],
            "source_type": reminder["source_type"],
            "document_id": reminder.get("document_id"),
        }
        return {
            **{key: value for key, value in reminder.items() if key != "fingerprint"},
            "id": _encode_reminder_id(payload),
        }

    def _serialize_non_document_reminder(
        self,
        reminder: Dict[str, Any],
        state: ReminderState,
    ) -> Dict[str, Any]:
        payload = {
            "kind": reminder["kind"],
            "bucket": reminder["bucket"],
            "fingerprint": reminder["fingerprint"],
            "source_type": reminder["source_type"],
        }
        return {
            **{key: value for key, value in reminder.items() if key != "fingerprint"},
            "id": _encode_reminder_id(payload),
            "snoozed_until": state.snoozed_until.isoformat() if state.snoozed_until else None,
        }

    def _is_supported_document_suggestion(self, suggestion_type: str) -> bool:
        return suggestion_type.startswith("import_") or suggestion_type in {
            "create_property",
            "create_asset",
            "create_recurring_income",
            "create_recurring_expense",
            "create_loan",
            "create_loan_repayment",
        }

    def _build_document_action(self, suggestion_type: str, document_id: int) -> Optional[Dict[str, Any]]:
        try:
            from app.api.v1.endpoints.documents import _build_action_descriptor

            return _build_action_descriptor(suggestion_type, document_id)
        except Exception:
            logger.warning("Failed to build action descriptor for %s", suggestion_type, exc_info=True)
            return None

    def _default_snooze_days(self, payload: Dict[str, Any]) -> int:
        if payload.get("kind") == "deadline_reminder":
            return 1
        if payload.get("kind") in {"recurring_expired", "recurring_expiring"}:
            return 7
        return _DEFAULT_SNOOZE_DAYS.get(str(payload.get("bucket")), 14)

    def _sort_key(self, reminder: Dict[str, Any]) -> tuple[int, int, str]:
        bucket_priority = {
            TERMINAL_ACTION: 0,
            TIME_BASED_REPEAT: 1,
            SNOOZEABLE_CONDITION: 2,
        }
        severity_priority = {"high": 0, "medium": 1, "low": 2}
        next_due = str(reminder.get("next_due_at") or "")
        return (
            bucket_priority.get(str(reminder.get("bucket")), 9),
            severity_priority.get(str(reminder.get("severity")), 9),
            next_due,
        )
