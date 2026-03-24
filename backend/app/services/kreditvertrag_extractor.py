"""
Kreditvertrag (Loan Contract) Extractor.

Extracts core loan fields from Austrian credit contracts so the OCR pipeline can
build `create_loan` suggestions without falling back to unrelated tax/invoice
extractors.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional


_DATE_PATTERN = r"(\d{2}\.\d{2}\.\d{4})"
_AMOUNT_PATTERN = r"((?:\d{1,3}(?:\.\d{3})+|\d+)(?:,\d{2})?)"
_PERCENT_PATTERN = r"((?:\d{1,2}(?:[.,]\d{1,3})?))"


@dataclass
class KreditvertragData:
    contract_number: Optional[str] = None
    lender_name: Optional[str] = None
    borrower_name: Optional[str] = None
    kreditnehmer: Optional[str] = None
    darlehensnehmer: Optional[str] = None
    loan_amount: Optional[Decimal] = None
    interest_rate: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    first_rate_date: Optional[datetime] = None
    term_years: Optional[int] = None
    term_months: Optional[int] = None
    purpose: Optional[str] = None
    property_address: Optional[str] = None
    annual_interest_amount: Optional[Decimal] = None
    certificate_year: Optional[int] = None
    field_confidence: Dict[str, float] = field(default_factory=dict)
    confidence: float = 0.0


class KreditvertragExtractor:
    """Extract structured loan metadata from OCR/raw PDF text."""

    _SECTION_STOP_PATTERN = r"(?:\n\s*(?:\d+\.\s+[A-ZÄÖÜa-zäöüß]|Kreditnehmer|Darlehensnehmer|Kreditgeber(?:in)?|Darlehensgeber(?:in)?):)"

    def extract(self, text: str) -> KreditvertragData:
        data = KreditvertragData()
        self._extract_contract_number(text, data)
        self._extract_parties(text, data)
        self._extract_loan_amount(text, data)
        self._extract_interest_rate(text, data)
        self._extract_monthly_payment(text, data)
        self._extract_dates(text, data)
        self._extract_term(text, data)
        self._extract_purpose_and_address(text, data)
        self._extract_annual_interest_certificate(text, data)
        data.confidence = self._calculate_confidence(data)
        return data

    def to_dict(self, data: KreditvertragData) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in data.__dict__.items():
            if value is None:
                result[key] = None
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, datetime):
                result[key] = value.date().isoformat()
            elif isinstance(value, dict):
                result[key] = value
            else:
                result[key] = value
        return result

    def _extract_contract_number(self, text: str, data: KreditvertragData) -> None:
        match = re.search(r"Vertragsnummer\s*:?\s*([A-Z0-9\-\/]+)", text, re.IGNORECASE)
        if match:
            data.contract_number = match.group(1).strip()
            data.field_confidence["contract_number"] = 0.95

    def _extract_parties(self, text: str, data: KreditvertragData) -> None:
        lender = self._extract_party_name(
            text,
            labels=("Kreditgeberin", "Kreditgeber", "Darlehensgeberin", "Darlehensgeber"),
            stop_labels=("Kreditnehmer", "Darlehensnehmer", "2. Kreditbetrag", "2. Darlehensbetrag"),
        )
        if lender:
            data.lender_name = lender
            data.field_confidence["lender_name"] = 0.92

        borrower = self._extract_party_name(
            text,
            labels=("Kreditnehmer", "Darlehensnehmer"),
            stop_labels=("2. Kreditbetrag", "2. Darlehensbetrag", "2. Kreditbetrag und Verwendungszweck"),
        )
        if borrower:
            data.borrower_name = borrower
            data.kreditnehmer = borrower
            data.darlehensnehmer = borrower
            data.field_confidence["borrower_name"] = 0.9
            data.field_confidence["kreditnehmer"] = 0.9
            data.field_confidence["darlehensnehmer"] = 0.9

    def _extract_party_name(
        self,
        text: str,
        *,
        labels: tuple[str, ...],
        stop_labels: tuple[str, ...],
    ) -> Optional[str]:
        label_pattern = "|".join(re.escape(label) for label in labels)
        stop_pattern = "|".join(re.escape(label) for label in stop_labels)
        match = re.search(
            rf"(?:{label_pattern})\s*:?\s*(.+?)(?=(?:{stop_pattern})\s*:|{self._SECTION_STOP_PATTERN}|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        segment = match.group(1)
        lines = [self._clean_line(line) for line in segment.splitlines()]
        for line in lines:
            if not line:
                continue
            if self._looks_like_metadata_line(line):
                continue
            return line
        return None

    def _extract_loan_amount(self, text: str, data: KreditvertragData) -> None:
        for label in ("Kreditbetrag", "Darlehensbetrag"):
            match = re.search(
                rf"{label}\s*:?\s*(?:EUR)?\s*{_AMOUNT_PATTERN}",
                text,
                re.IGNORECASE,
            )
            if match:
                amount = self._parse_amount(match.group(1))
                if amount is not None:
                    data.loan_amount = amount
                    data.field_confidence["loan_amount"] = 0.95
                    return

    def _extract_interest_rate(self, text: str, data: KreditvertragData) -> None:
        patterns = (
            rf"Aktueller\s+Zinssatz\s*:?\s*{_PERCENT_PATTERN}\s*%",
            rf"Fixzinssatz\s*:?\s*{_PERCENT_PATTERN}\s*%",
            rf"Nominalzinssatz\s*:?\s*{_PERCENT_PATTERN}\s*%",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                rate = self._parse_percentage(match.group(1))
                if rate is not None:
                    data.interest_rate = rate
                    data.field_confidence["interest_rate"] = 0.92
                    return

    def _extract_monthly_payment(self, text: str, data: KreditvertragData) -> None:
        match = re.search(
            rf"Monatliche\s+Rate\s*:?\s*(?:EUR)?\s*{_AMOUNT_PATTERN}",
            text,
            re.IGNORECASE,
        )
        if match:
            amount = self._parse_amount(match.group(1))
            if amount is not None:
                data.monthly_payment = amount
                data.field_confidence["monthly_payment"] = 0.9

    def _extract_dates(self, text: str, data: KreditvertragData) -> None:
        date_fields = {
            "start_date": "Vertragsbeginn",
            "end_date": "Vertragsende",
            "first_rate_date": "Erste Rate",
        }
        for field, label in date_fields.items():
            match = re.search(rf"{label}\s*:?\s*{_DATE_PATTERN}", text, re.IGNORECASE)
            if not match:
                continue
            parsed = self._parse_date(match.group(1))
            if parsed is not None:
                setattr(data, field, parsed)
                data.field_confidence[field] = 0.9

    def _extract_term(self, text: str, data: KreditvertragData) -> None:
        match = re.search(
            r"Laufzeit\s*:?\s*(\d+)\s+Jahre(?:\s*\((\d+)\s+Monate\))?",
            text,
            re.IGNORECASE,
        )
        if match:
            data.term_years = int(match.group(1))
            if match.group(2):
                data.term_months = int(match.group(2))
            elif data.term_years is not None:
                data.term_months = data.term_years * 12
            data.field_confidence["term_years"] = 0.88
            data.field_confidence["term_months"] = 0.88

    def _extract_purpose_and_address(self, text: str, data: KreditvertragData) -> None:
        match = re.search(
            r"Verwendungszweck\s*:?\s*(.+?)(?=Auszahlungstag|3\.\s+Laufzeit|$)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return

        lines = [self._clean_line(line) for line in match.group(1).splitlines() if self._clean_line(line)]
        if not lines:
            return

        data.purpose = lines[0]
        data.field_confidence["purpose"] = 0.8

        address_pattern = re.compile(
            r"([A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß0-9./\- ]+,\s*\d{4}\s+[A-ZÄÖÜa-zäöüß][A-ZÄÖÜa-zäöüß \-]+)"
        )
        for line in lines[1:]:
            addr = address_pattern.search(line)
            if addr:
                data.property_address = addr.group(1).strip()
                data.field_confidence["property_address"] = 0.82
                return

    def _extract_annual_interest_certificate(self, text: str, data: KreditvertragData) -> None:
        text_lower = text.lower()
        if "zinsbescheinigung" not in text_lower and "zinsaufwand" not in text_lower:
            return

        year_match = re.search(r"(?:kalenderjahr|jahr|für|fuer)\s*(20\d{2})", text, re.IGNORECASE)
        if year_match:
            data.certificate_year = int(year_match.group(1))
            data.field_confidence["certificate_year"] = 0.86

        line_candidates = []
        for line in text.splitlines():
            normalized = self._clean_line(line)
            if not normalized:
                continue
            if "zins" not in normalized.lower():
                continue
            line_candidates.append(normalized)

        patterns = (
            rf"(?:zinsaufwand|zinsen|sollzinsen|bezahlte\s+zinsen|verrechnete\s+zinsen)"
            rf".{{0,40}}?(20\d{{2}})?.{{0,20}}?(?:eur)?\s*{_AMOUNT_PATTERN}",
            rf"(20\d{{2}}).{{0,40}}?(?:zinsaufwand|zinsen).{{0,20}}?(?:eur)?\s*{_AMOUNT_PATTERN}",
        )

        best_amount: Optional[Decimal] = None
        best_year: Optional[int] = None
        for line in line_candidates:
            for pattern in patterns:
                match = re.search(pattern, line, re.IGNORECASE)
                if not match:
                    continue
                groups = [group for group in match.groups() if group]
                parsed_amount = None
                parsed_year = None
                for group in groups:
                    if re.fullmatch(r"20\d{2}", group):
                        parsed_year = int(group)
                    else:
                        parsed_amount = self._parse_amount(group)
                if parsed_amount is None or parsed_amount <= 0:
                    continue
                best_amount = parsed_amount
                best_year = parsed_year
                break
            if best_amount is not None:
                break

        if best_amount is not None:
            data.annual_interest_amount = best_amount
            data.field_confidence["annual_interest_amount"] = 0.88
        if best_year is not None:
            data.certificate_year = best_year
            data.field_confidence["certificate_year"] = max(
                data.field_confidence.get("certificate_year", 0.0),
                0.88,
            )

    def _calculate_confidence(self, data: KreditvertragData) -> float:
        score = 0.0
        if data.loan_amount is not None:
            score += 0.28
        if data.interest_rate is not None:
            score += 0.24
        if data.lender_name:
            score += 0.18
        if data.monthly_payment is not None:
            score += 0.12
        if data.start_date is not None:
            score += 0.06
        if data.end_date is not None:
            score += 0.06
        if data.borrower_name:
            score += 0.06
        return round(min(score, 1.0), 2)

    def _clean_line(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip(" \t\r\n:-")

    def _looks_like_metadata_line(self, value: str) -> bool:
        return bool(
            re.match(
                r"^(?:Am\s+|FN\s+|HG\s+|BLZ\s+|BIC\s+|UID\s+|IBAN\s+|SVNr\.?|geb\.|Stand\s+\d{2}\.\d{2}\.\d{4}|Seite\s+\d+/\d+)",
                value,
                re.IGNORECASE,
            )
        )

    def _parse_amount(self, raw_value: str) -> Optional[Decimal]:
        cleaned = raw_value.replace("EUR", "").replace(" ", "").strip()
        cleaned = cleaned.replace(".", "").replace(",", ".")
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    def _parse_percentage(self, raw_value: str) -> Optional[Decimal]:
        cleaned = raw_value.replace("%", "").replace("p.a.", "").replace(" ", "").strip()
        cleaned = cleaned.replace(",", ".")
        cleaned = re.sub(r"[^0-9.\-]", "", cleaned)
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    def _parse_date(self, raw_value: str) -> Optional[datetime]:
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                return datetime.strptime(raw_value, fmt)
            except ValueError:
                continue
        return None
