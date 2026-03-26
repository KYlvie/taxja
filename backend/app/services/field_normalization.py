"""Shared normalization helpers for OCR/AI extracted scalar fields."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%d.%m.%Y",
    "%d.%m.%y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%Y/%m/%d",
    "%Y/%m/%d %H:%M:%S",
)

_NAMED_MONTHS = {
    "jan": 1,
    "january": 1,
    "jänner": 1,
    "jaenner": 1,
    "feb": 2,
    "february": 2,
    "mär": 3,
    "maerz": 3,
    "märz": 3,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "juni": 6,
    "june": 6,
    "jul": 7,
    "juli": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "okt": 10,
    "oct": 10,
    "oktober": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dez": 12,
    "dec": 12,
    "dezember": 12,
    "december": 12,
}

_NUMBER_TOKEN_RE = re.compile(r"[-+()]?\s*[0-9][0-9.,\s]*")
_NAMED_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})\.?\s+(?P<month>[A-Za-zÄÖÜäöüß\.]+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)


def normalize_amount(value: Any) -> Decimal | None:
    """Normalize OCR/AI amount strings into Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    text = (
        raw.replace("\u00a0", " ")
        .replace("€", "")
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )
    text = re.sub(r"(?i)\b(?:eur|usd|gbp|chf)\b", "", text).strip()

    match = _NUMBER_TOKEN_RE.search(text)
    if not match:
        return None
    token = match.group(0).strip().replace(" ", "")

    negative = False
    if token.startswith("(") and token.endswith(")"):
        negative = True
        token = token[1:-1]
    if token.startswith("-"):
        negative = True
        token = token[1:]
    if token.endswith("-"):
        negative = True
        token = token[:-1]
    if token.startswith("+"):
        token = token[1:]

    if "," in token and "." in token:
        if token.rfind(",") > token.rfind("."):
            token = token.replace(".", "").replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "," in token:
        parts = token.split(",")
        if len(parts) == 2 and len(parts[1]) in (1, 2):
            token = token.replace(",", ".")
        else:
            token = token.replace(",", "")
    elif "." in token:
        parts = token.split(".")
        if not (len(parts) == 2 and len(parts[1]) in (1, 2)):
            token = token.replace(".", "")

    try:
        amount = Decimal(token)
    except (InvalidOperation, ValueError):
        return None

    return -amount if negative else amount


def normalize_vat_rate(value: Any) -> Decimal | None:
    """Normalize VAT rate into percentage points, e.g. 20 or 10."""
    rate = normalize_amount(value)
    if rate is None:
        return None

    if rate < 0:
        rate = -rate
    if rate <= Decimal("1"):
        rate *= Decimal("100")

    return rate


def normalize_date(value: Any) -> date | None:
    """Normalize OCR/AI date values into date."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    for separator in (" - ", " – ", " — ", " bis ", " to "):
        if separator in raw:
            for part in raw.split(separator):
                parsed = normalize_date(part)
                if parsed:
                    return parsed

    iso_candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue

    named_match = _NAMED_DATE_RE.search(raw)
    if named_match:
        month_key = named_match.group("month").strip(".").lower()
        month = _NAMED_MONTHS.get(month_key)
        if month:
            return date(
                int(named_match.group("year")),
                month,
                int(named_match.group("day")),
            )

    return None

