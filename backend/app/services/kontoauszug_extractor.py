"""Kontoauszug (bank statement) extractor.

Extracts transaction list from bank statements (PDF text or CSV).
Supports common Austrian bank formats.
"""
import re
import logging
from dataclasses import dataclass, field, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _parse_decimal(value: str) -> Optional[Decimal]:
    if not value:
        return None
    try:
        cleaned = value.strip().replace(".", "").replace(",", ".")
        cleaned = re.sub(r"[^\d.\-]", "", cleaned)
        if not cleaned or cleaned in (".", "-"):
            return None
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None


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
        text_lower = text.lower()

        # Bank name
        for pattern, name in self.BANK_PATTERNS.items():
            if pattern in text_lower:
                data.bank_name = name
                break

        # IBAN
        iban_m = re.search(r"(AT\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4})", text, re.I)
        if iban_m:
            data.iban = iban_m.group(1).replace(" ", "")

        # Period
        date_pat = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})"
        period_m = re.search(
            rf"(?:Zeitraum|Auszug|Kontoauszug)\s*[:.]?\s*{date_pat}\s*[-–bis]+\s*{date_pat}",
            text, re.I,
        )
        if period_m:
            data.period_start = period_m.group(1)
            data.period_end = period_m.group(2)

        # Balances
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        for kw, attr in [
            ("anfangssaldo", "opening_balance"), ("alter saldo", "opening_balance"),
            ("endsaldo", "closing_balance"), ("neuer saldo", "closing_balance"),
        ]:
            if kw in text_lower and getattr(data, attr) is None:
                idx = text_lower.find(kw)
                window = text[idx:idx + 100]
                amounts = re.findall(amount_pat, window)
                if amounts:
                    val = _parse_decimal(amounts[-1])
                    if val:
                        setattr(data, attr, val)

        # Extract transactions
        self._extract_transactions(text, data)

        data.confidence = self._calculate_confidence(data)
        return data

    def _extract_transactions(self, text: str, data: KontoauszugData) -> None:
        """Extract individual transactions from statement text."""
        date_pat = r"(\d{1,2}[./]\d{1,2}[./]\d{2,4})"
        amount_pat = r"([\-]?[\d]{1,3}(?:[.\s]\d{3})*[,]\d{2})"
        # Pattern: date ... amount (with optional text between)
        tx_pattern = re.compile(
            rf"{date_pat}\s+(.+?)\s+{amount_pat}", re.MULTILINE
        )
        for m in tx_pattern.finditer(text):
            amount = _parse_decimal(m.group(3))
            if amount is None:
                continue
            tx = BankTransaction(
                date=m.group(1),
                counterparty=m.group(2).strip()[:200],
                amount=amount,
                transaction_type="credit" if amount > 0 else "debit",
            )
            data.transactions.append(tx)
            if len(data.transactions) >= 500:  # Safety limit
                break

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
