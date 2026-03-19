"""Helpers for accepting enum values or enum names across transaction flows."""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, TypeVar

from app.models.transaction import ExpenseCategory, IncomeCategory, TransactionType

EnumT = TypeVar("EnumT", bound=Enum)


def _normalize_enum_token(raw_value: Any) -> str:
    token = str(raw_value or "").strip()
    if "." in token:
        token = token.split(".")[-1]
    return re.sub(r"[\s\-/]+", "_", token).strip("_")


def coerce_enum_member(
    enum_cls: type[EnumT],
    raw_value: Any,
    *,
    default: EnumT | None = None,
    strict: bool = False,
) -> EnumT | None:
    """Accept enum instances, values, names, and common string variants."""
    if raw_value is None:
        return default

    if isinstance(raw_value, enum_cls):
        return raw_value

    normalized = _normalize_enum_token(raw_value)
    if not normalized:
        return default

    value_candidates = []
    member_candidates = []

    for candidate in (
        str(raw_value).strip(),
        normalized,
        normalized.lower(),
        normalized.upper(),
    ):
        if candidate and candidate not in value_candidates:
            value_candidates.append(candidate)

    for candidate in (
        normalized,
        normalized.upper(),
    ):
        if candidate and candidate not in member_candidates:
            member_candidates.append(candidate)

    for candidate in value_candidates:
        try:
            return enum_cls(candidate)
        except ValueError:
            continue

    for candidate in member_candidates:
        if candidate in enum_cls.__members__:
            return enum_cls[candidate]

    if strict:
        raise ValueError(f"Invalid {enum_cls.__name__}: {raw_value}")

    return default


def coerce_transaction_type(
    raw_value: Any,
    *,
    default: TransactionType | None = TransactionType.EXPENSE,
    strict: bool = False,
) -> TransactionType | None:
    return coerce_enum_member(TransactionType, raw_value, default=default, strict=strict)


def coerce_income_category(
    raw_value: Any,
    *,
    default: IncomeCategory | None = None,
    strict: bool = False,
) -> IncomeCategory | None:
    return coerce_enum_member(IncomeCategory, raw_value, default=default, strict=strict)


def coerce_expense_category(
    raw_value: Any,
    *,
    default: ExpenseCategory | None = None,
    strict: bool = False,
) -> ExpenseCategory | None:
    return coerce_enum_member(ExpenseCategory, raw_value, default=default, strict=strict)
