"""Shared normalization helpers for OCR/AI extracted scalar fields."""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


# Fields that contain monetary amounts (for German number format fixing)
_AMOUNT_FIELD_NAMES = {
    "amount", "praemie", "premium", "beitrag_gesamt", "beitragsgrundlage",
    "pensionsversicherung", "krankenversicherung", "unfallversicherung",
    "selbstaendigenvorsorge", "nachzahlung", "gutschrift",
    "net_amount", "vat_amount", "total_amount", "purchase_price",
    "monthly_rent", "loan_amount", "ratenbetrag",
    "versicherungssumme", "deckungssumme", "selbstbehalt",
}


def fix_german_number_formats(data: dict) -> dict:
    """Fix German number format issues in extracted data.

    LLMs processing Austrian/German documents sometimes output numbers
    in German format (1.662,36) or partially parsed (1.662 meaning 1662).

    Rules:
    - Float with exactly 3 decimal places in an amount field (e.g. 1.662)
      is likely a German thousand separator → multiply by 1000
    - String "1.662,36" → parse as 1662.36
    """
    if not isinstance(data, dict):
        return data

    for key, value in list(data.items()):
        if key not in _AMOUNT_FIELD_NAMES:
            continue

        if isinstance(value, str):
            # String with German format: "1.662,36" or "13.087,48"
            if re.match(r'^\d{1,3}(\.\d{3})+(,\d{1,2})?$', value.strip()):
                cleaned = value.strip().replace('.', '').replace(',', '.')
                try:
                    data[key] = float(cleaned)
                except ValueError:
                    pass

        elif isinstance(value, (int, float)):
            # Float that looks like German thousand separator was parsed as decimal
            # e.g. 1.662 (should be 1662), 13.087 (should be 13087)
            fval = float(value)
            str_val = f"{fval:.10g}"
            if '.' in str_val:
                integer_part, decimal_part = str_val.split('.', 1)
                # If decimal part is exactly 3 digits and the result is suspiciously small
                # for an amount field, it's likely a German thousand separator
                if len(decimal_part) == 3 and len(integer_part) <= 2:
                    data[key] = float(f"{integer_part}{decimal_part}")

    return data

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
    "janner": 1,
    "jaenner": 1,
    "janner.": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "marz": 3,
    "maerz": 3,
    "marz.": 3,
    "apr": 4,
    "april": 4,
    "mai": 5,
    "may": 5,
    "jun": 6,
    "june": 6,
    "juni": 6,
    "jul": 7,
    "july": 7,
    "juli": 7,
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
    r"(?P<day>\d{1,2})\.?\s+(?P<month>[A-Za-z.\-]+)\s+(?P<year>\d{4})",
    re.IGNORECASE,
)

_CURRENCY_MAP = {
    "EUR": "EUR",
    "EURO": "EUR",
    "€": "EUR",
    "USD": "USD",
    "$": "USD",
    "GBP": "GBP",
    "£": "GBP",
    "CHF": "CHF",
    "FR": "CHF",
    "SFR": "CHF",
}

_BOOLEAN_TRUE = {
    "1",
    "true",
    "yes",
    "y",
    "ja",
    "j",
    "oui",
    "si",
    "x",
    "checked",
    "bezahlt",
    "paid",
    "deductible",
    "abzugsfaehig",
    "abzugsfahig",
}

_BOOLEAN_FALSE = {
    "0",
    "false",
    "no",
    "n",
    "nein",
    "non",
    "",
    "unchecked",
    "offen",
    "open",
    "not deductible",
    "nicht abzugsfaehig",
    "nicht abzugsfahig",
}

_SEMANTIC_FLAG_PATTERNS = (
    ("reverse_charge", re.compile(r"\breverse charge\b|steuerschuldnerschaft des leistungsempf", re.IGNORECASE)),
    ("credit_note", re.compile(r"\bcredit note\b|\bgutschrift\b", re.IGNORECASE)),
    ("refund", re.compile(r"\brefund\b|\berstattung\b|\brueckerstattung\b|\bruckerstattung\b", re.IGNORECASE)),
    ("proforma", re.compile(r"\bproforma\b|\bpro forma\b", re.IGNORECASE)),
    ("delivery_note", re.compile(r"\bdelivery note\b|\blieferschein\b", re.IGNORECASE)),
    ("cancelled", re.compile(r"\bstorniert\b|\bcancelled\b|\bvoid\b", re.IGNORECASE)),
    ("paid", re.compile(r"\bbezahlt\b|\bpaid\b", re.IGNORECASE)),
    ("open", re.compile(r"\boffen\b|\bopen\b|\bunpaid\b", re.IGNORECASE)),
    ("vat_exempt", re.compile(r"\bsteuerfrei\b|\bvat exempt\b|\btax exempt\b", re.IGNORECASE)),
    ("intra_community", re.compile(r"\bintra-community\b|\binnergemeinschaft", re.IGNORECASE)),
)


def _strip_accents(text: str) -> str:
    """Collapse a few common OCR month accents into ASCII."""
    return (
        text.replace("ä", "a")
        .replace("ö", "o")
        .replace("ü", "u")
        .replace("Ä", "A")
        .replace("Ö", "O")
        .replace("Ü", "U")
        .replace("ß", "ss")
    )


def normalize_amount(value: Any) -> Decimal | None:
    """Normalize OCR/AI amount strings into Decimal."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return None
    if isinstance(value, dict):
        for key in ("total", "amount", "gross", "net", "value"):
            if key in value:
                return normalize_amount(value.get(key))
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
        .replace("−", "-")
        .replace("–", "-")
        .replace("—", "-")
        .strip()
    )
    text = text.replace("€", "").replace("£", "").replace("$", "")
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


def normalize_quantity(value: Any) -> int | None:
    """Normalize OCR/AI quantity values to positive integers when safe."""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, Decimal):
        if value <= 0 or value != value.to_integral_value():
            return None
        return int(value)
    if isinstance(value, float):
        if value <= 0 or int(value) != value:
            return None
        return int(value)
    if not isinstance(value, str):
        return None

    raw = value.strip()
    if not raw:
        return None

    match = re.search(r"(?<!\d)(\d+(?:[.,]\d+)?)", raw)
    if not match:
        return None

    normalized = normalize_amount(match.group(1))
    if normalized is None or normalized <= 0:
        return None
    if normalized != normalized.to_integral_value():
        return None
    return int(normalized)


def normalize_currency(value: Any) -> str | None:
    """Normalize OCR/AI currency markers to ISO-style codes."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)

    raw = value.strip().upper()
    if not raw:
        return None

    compact = raw.replace(".", "").replace(" ", "")
    for token, normalized in _CURRENCY_MAP.items():
        if token in raw or token in compact:
            return normalized
    return None


def normalize_boolean_flag(value: Any) -> bool | None:
    """Normalize OCR/AI boolean-like values."""
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, Decimal)):
        if value == 1:
            return True
        if value == 0:
            return False
        return None
    if not isinstance(value, str):
        return None

    raw = _strip_accents(value.strip().lower())
    if raw in _BOOLEAN_TRUE:
        return True
    if raw in _BOOLEAN_FALSE:
        return False
    return None


def normalize_semantic_flags(*values: Any) -> list[str]:
    """Extract canonical semantic flags from OCR/AI text fragments."""
    collected: set[str] = set()
    for value in values:
        if value is None:
            continue
        if isinstance(value, (list, tuple, set)):
            collected.update(normalize_semantic_flags(*list(value)))
            continue
        text = _strip_accents(str(value))
        for flag, pattern in _SEMANTIC_FLAG_PATTERNS:
            if pattern.search(text):
                collected.add(flag)
    return sorted(collected)


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

    named_match = _NAMED_DATE_RE.search(_strip_accents(raw))
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
