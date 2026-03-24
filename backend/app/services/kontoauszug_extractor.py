"""Kontoauszug (bank statement) extractor.

Extracts transaction list from bank statements (PDF text or CSV).
Supports common Austrian bank formats.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

UNICODE_MINUS_TRANSLATION = str.maketrans({
    "\u2212": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2011": "-",
    "\u00a0": " ",
    "\u2009": " ",
    "\u202f": " ",
})

GERMAN_MONTHS = {
    "jaenner": 1,
    "januar": 1,
    "jan": 1,
    "februar": 2,
    "feb": 2,
    "maerz": 3,
    "mrz": 3,
    "april": 4,
    "apr": 4,
    "mai": 5,
    "juni": 6,
    "jun": 6,
    "juli": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "oktober": 10,
    "okt": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "dezember": 12,
    "dez": 12,
    "dec": 12,
}


def _parse_decimal(value: str) -> Optional[Decimal]:
    if not value:
        return None
    try:
        cleaned = value.strip().translate(UNICODE_MINUS_TRANSLATION)
        cleaned = cleaned.replace("EUR", "").replace("\u20ac", "")
        cleaned = re.sub(r"\s+", "", cleaned)
        cleaned = cleaned.replace(".", "").replace(",", ".")
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        if not cleaned or cleaned in (".", "-"):
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


def _normalize_line(value: str) -> str:
    return value.translate(UNICODE_MINUS_TRANSLATION).strip()


def _normalize_token(value: str) -> str:
    normalized = _normalize_line(value).lower()
    normalized = (
        normalized
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
        .replace("ß", "ss")
    )
    normalized = unicodedata.normalize("NFKD", normalized)
    return normalized.encode("ascii", "ignore").decode("ascii")


@dataclass
class BankTransaction:
    date: Optional[str] = None
    amount: Optional[Decimal] = None
    counterparty: Optional[str] = None
    reference: Optional[str] = None
    transaction_type: str = "debit"  # "credit" or "debit"


@dataclass
class KontoauszugData:
    bank_name: Optional[str] = None
    iban: Optional[str] = None
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    opening_balance: Optional[Decimal] = None
    closing_balance: Optional[Decimal] = None
    transactions: List[BankTransaction] = field(default_factory=list)
    confidence: float = 0.0


class KontoauszugExtractor:
    MONTH_HEADER_RE = re.compile(r"^([^\W\d_]+)\s+(\d{4})$", re.I)
    TRANSACTION_START_RE = re.compile(
        r"^(\d{1,2})\.\s*([^\W\d_]+)\.?(?:\s+(\d{4}))?$",
        re.I,
    )
    AMOUNT_RE = re.compile(
        r"(-?\s*(?:EUR|\u20ac)?\s*\d{1,3}(?:[.\s]\d{3})*,\d{2})",
        re.I,
    )

    BANK_PATTERNS = {
        "erste bank": "Erste Bank",
        "sparkasse": "Sparkasse",
        "raiffeisen": "Raiffeisen",
        "bank austria": "Bank Austria",
        "bawag": "BAWAG P.S.K.",
        "volksbank": "Volksbank",
        "oberbank": "Oberbank",
    }

    def extract(self, text: str) -> KontoauszugData:
        if not text or len(text.strip()) < 20:
            return KontoauszugData(confidence=0.0)

        data = KontoauszugData()
        normalized_text = text.translate(UNICODE_MINUS_TRANSLATION)
        text_lower = normalized_text.lower()

        for pattern, name in self.BANK_PATTERNS.items():
            if pattern in text_lower:
                data.bank_name = name
                break

        iban_m = re.search(r"(AT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4})", normalized_text, re.I)
        if iban_m:
            data.iban = iban_m.group(1).replace(" ", "")

        date_pat = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})"
        period_m = re.search(
            rf"(?:Zeitraum|Auszug|Kontoauszug)\s*[:.]?\s*{date_pat}\s*(?:-|bis|to)\s*{date_pat}",
            normalized_text,
            re.I,
        )
        if period_m:
            data.period_start = period_m.group(1)
            data.period_end = period_m.group(2)

        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for kw, attr in [
            ("anfangssaldo", "opening_balance"),
            ("alter saldo", "opening_balance"),
            ("endsaldo", "closing_balance"),
            ("neuer saldo", "closing_balance"),
        ]:
            if kw in text_lower and getattr(data, attr) is None:
                idx = text_lower.find(kw)
                window = normalized_text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val is not None:
                        setattr(data, attr, val)

        self._extract_transactions(normalized_text, data)

        data.confidence = self._calculate_confidence(data)
        return data

    def _extract_transactions(self, text: str, data: KontoauszugData) -> None:
        self._extract_grouped_transactions(text, data)
        if data.transactions:
            return
        self._extract_legacy_transactions(text, data)

    def _extract_grouped_transactions(self, text: str, data: KontoauszugData) -> None:
        current_year: Optional[int] = None
        blocks: List[Dict[str, Any]] = []
        active_block: Optional[Dict[str, Any]] = None

        for raw_line in text.splitlines():
            line = _normalize_line(raw_line)
            if not line or line.startswith("--- PAGE"):
                continue

            month_header = self._parse_month_header(line)
            if month_header is not None:
                current_year = month_header["year"]
                if active_block:
                    blocks.append(active_block)
                    active_block = None
                continue

            if self._is_month_summary_line(line) and active_block is None:
                continue

            tx_start = self._parse_transaction_start(line, current_year)
            if tx_start is not None:
                if active_block:
                    blocks.append(active_block)
                active_block = {"date": tx_start, "lines": []}
                continue

            if active_block is not None:
                active_block["lines"].append(line)

        if active_block:
            blocks.append(active_block)

        seen = set()
        for block in blocks:
            tx = self._build_transaction_from_block(block)
            if tx is None:
                continue
            fingerprint = (
                tx.date,
                str(tx.amount),
                tx.counterparty or "",
                tx.reference or "",
            )
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            data.transactions.append(tx)
            if len(data.transactions) >= 500:
                break

    def _extract_legacy_transactions(self, text: str, data: KontoauszugData) -> None:
        date_pat = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})"
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        tx_pattern = re.compile(rf"{date_pat}\s+(.+?)\s+{amount_pat}", re.MULTILINE)
        for match in tx_pattern.finditer(text):
            amount = _parse_decimal(match.group(3))
            if amount is None:
                continue
            data.transactions.append(
                BankTransaction(
                    date=match.group(1),
                    counterparty=match.group(2).strip()[:200],
                    amount=amount,
                    transaction_type="credit" if amount > 0 else "debit",
                )
            )
            if len(data.transactions) >= 500:
                break

    def _parse_month_header(self, line: str) -> Optional[Dict[str, int]]:
        match = self.MONTH_HEADER_RE.match(line)
        if not match:
            return None
        month_token = _normalize_token(match.group(1))
        month = GERMAN_MONTHS.get(month_token)
        if month is None:
            return None
        return {"month": month, "year": int(match.group(2))}

    def _parse_transaction_start(self, line: str, current_year: Optional[int]) -> Optional[str]:
        match = self.TRANSACTION_START_RE.match(line)
        if not match:
            return None
        month = GERMAN_MONTHS.get(_normalize_token(match.group(2)))
        year = int(match.group(3)) if match.group(3) else current_year
        if month is None or year is None:
            return None
        day = int(match.group(1))
        return f"{day:02d}.{month:02d}.{year}"

    @staticmethod
    def _is_month_summary_line(line: str) -> bool:
        return "kontoausgang" in _normalize_token(line)

    def _build_transaction_from_block(self, block: Dict[str, Any]) -> Optional[BankTransaction]:
        lines = [line for line in block.get("lines", []) if line]
        if not lines:
            return None

        amount: Optional[Decimal] = None
        amount_line_index: Optional[int] = None
        for index in range(len(lines) - 1, -1, -1):
            amount_match = self.AMOUNT_RE.search(lines[index])
            if amount_match:
                amount = _parse_decimal(amount_match.group(1))
                if amount is not None:
                    amount_line_index = index
                    break

        if amount is None:
            return None

        detail_lines = [
            line
            for idx, line in enumerate(lines)
            if idx != amount_line_index and not self._is_month_summary_line(line)
        ]
        detail_lines = [
            line
            for line in detail_lines
            if line and not self.AMOUNT_RE.fullmatch(line)
        ]
        if not detail_lines:
            return None

        counterparty = detail_lines[0][:200]
        reference_lines = detail_lines[1:]
        reference = " ".join(reference_lines).strip()[:500] if reference_lines else None

        return BankTransaction(
            date=block["date"],
            amount=amount,
            counterparty=counterparty or None,
            reference=reference or None,
            transaction_type="credit" if amount > 0 else "debit",
        )

    def _calculate_confidence(self, data: KontoauszugData) -> float:
        score = 0.0
        if data.bank_name:
            score += 0.15
        if data.iban:
            score += 0.15
        if data.period_start and data.period_end:
            score += 0.1
        if data.transactions:
            score += min(len(data.transactions) * 0.02, 0.4)
        if data.opening_balance or data.closing_balance:
            score += 0.1
        return min(score, 1.0)

    def to_dict(self, data: KontoauszugData) -> Dict[str, Any]:
        result = {
            "bank_name": data.bank_name,
            "iban": data.iban,
            "period_start": data.period_start,
            "period_end": data.period_end,
            "opening_balance": float(data.opening_balance) if data.opening_balance else None,
            "closing_balance": float(data.closing_balance) if data.closing_balance else None,
            "confidence": data.confidence,
            "transactions": [],
        }
        for tx in data.transactions:
            result["transactions"].append({
                "date": tx.date,
                "amount": float(tx.amount) if tx.amount else None,
                "counterparty": tx.counterparty,
                "reference": tx.reference,
                "transaction_type": tx.transaction_type,
            })
        return result
