"""Field extraction from OCR text - improved for Amazon/Booking/Austrian invoices"""
import re
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

from app.services.document_classifier import DocumentType


@dataclass
class ExtractedField:
    """Represents an extracted field with confidence"""

    value: Any
    confidence: float
    raw_text: Optional[str] = None


class FieldExtractor:
    """Extract structured fields from OCR text"""

    def extract_fields(self, text: str, doc_type: DocumentType) -> Dict[str, Any]:
        """Route to appropriate extractor based on document type"""
        # Route to specialized extractors
        if doc_type == DocumentType.EINKOMMENSTEUERBESCHEID:
            return self._extract_bescheid_fields(text)
        elif doc_type == DocumentType.RECEIPT:
            return self._extract_receipt_fields(text)
        elif doc_type == DocumentType.PAYSLIP or doc_type == DocumentType.LOHNZETTEL:
            return self._extract_payslip_fields(text)
        elif doc_type == DocumentType.INVOICE:
            return self._extract_invoice_fields(text)
        elif doc_type == DocumentType.SVS_NOTICE:
            return self._extract_svs_fields(text)
        else:
            return self._extract_generic_fields(text)

    def _extract_receipt_fields(self, text: str) -> Dict[str, Any]:
        fields = {}
        date_field = self.extract_date(text)
        fields["date"] = date_field.value
        fields["date_confidence"] = date_field.confidence
        amount_field = self.extract_total_amount(text)
        fields["amount"] = amount_field.value
        fields["amount_confidence"] = amount_field.confidence
        merchant_field = self.extract_merchant(text)
        fields["merchant"] = merchant_field.value
        fields["merchant_confidence"] = merchant_field.confidence
        items = self.extract_line_items(text)
        fields["items"] = items
        fields["items_count"] = len(items)
        vat_amounts = self.extract_vat_amounts(text)
        fields["vat_amounts"] = vat_amounts
        fields["vat_20"] = vat_amounts.get("20%")
        fields["vat_10"] = vat_amounts.get("10%")
        # Extract product description summary
        fields["product_summary"] = self._extract_product_summary(text)
        return fields

    def _extract_payslip_fields(self, text: str) -> Dict[str, Any]:
        fields = {}

        # Try column-aware extraction first (Austrian Gehaltszettel has labels then amounts)
        column_fields = self._extract_payslip_columns(text)

        if column_fields.get("gross_income"):
            fields["gross_income"] = column_fields["gross_income"]
            fields["gross_income_confidence"] = 0.9
        else:
            gross_field = self.extract_gross_income(text)
            fields["gross_income"] = gross_field.value
            fields["gross_income_confidence"] = gross_field.confidence

        if column_fields.get("net_income"):
            fields["net_income"] = column_fields["net_income"]
            fields["net_income_confidence"] = 0.9
        else:
            net_field = self.extract_net_income(text)
            fields["net_income"] = net_field.value
            fields["net_income_confidence"] = net_field.confidence

        if column_fields.get("withheld_tax"):
            fields["withheld_tax"] = column_fields["withheld_tax"]
            fields["withheld_tax_confidence"] = 0.9
        else:
            tax_field = self.extract_withheld_tax(text)
            fields["withheld_tax"] = tax_field.value
            fields["withheld_tax_confidence"] = tax_field.confidence

        if column_fields.get("social_insurance"):
            fields["social_insurance"] = column_fields["social_insurance"]
            fields["social_insurance_confidence"] = 0.9
        else:
            svs_field = self.extract_social_insurance(text)
            fields["social_insurance"] = svs_field.value
            fields["social_insurance_confidence"] = svs_field.confidence

        employer_field = self.extract_employer(text)
        fields["employer"] = employer_field.value
        fields["employer_confidence"] = employer_field.confidence

        # Payslip-specific date: try "Auszahlungsmonat: MM.YYYY" first
        date_field = self._extract_payslip_date(text)
        if date_field.value is None:
            date_field = self.extract_date(text)
        fields["date"] = date_field.value
        fields["date_confidence"] = date_field.confidence
        return fields

    def _extract_payslip_columns(self, text: str) -> Dict[str, Optional[Decimal]]:
        """Extract fields from Austrian Gehaltszettel column layout.
        The format has labels listed first, then amounts in the same order:
          SV/KFA-Beitrag
          WFB
          Lohnsteuer
          Personalvert.Uml.
          911,63
          39,87
          985,05
          5,29
        """
        result: Dict[str, Optional[Decimal]] = {}
        lines = text.split("\n")
        amount_re = re.compile(r"^\s*(\d{1,3}(?:\.\d{3})*,\d{2})\s*$")

        # --- Deductions block: find "Abzuege" section (ASCII-safe matching) ---
        deduction_labels = []
        deduction_amounts = []
        in_deductions = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            low = stripped.lower()
            # Match "Abz\u00fcge" or "Abzuege" - use regex for umlaut safety
            if re.match(r"^abz.{1,2}ge$", low):
                in_deductions = True
                continue
            if in_deductions:
                if low.startswith("s u m m e") or re.match(r"^summe abz.{1,2}ge", low):
                    break
                m = amount_re.match(stripped)
                if m:
                    val = Decimal(m.group(1).replace(".", "").replace(",", "."))
                    deduction_amounts.append(val)
                elif stripped and not low.startswith("betrag") and not low.startswith("nach-"):
                    deduction_labels.append(low)

        # Map labels to amounts by position
        label_amount = {}
        for idx, label in enumerate(deduction_labels):
            if idx < len(deduction_amounts):
                label_amount[label] = deduction_amounts[idx]

        # Match known fields
        for label, amount in label_amount.items():
            if "lohnsteuer" in label and "basis" not in label:
                result["withheld_tax"] = amount
            elif "sv" in label or "kfa" in label:
                result["social_insurance"] = amount

        # --- Gross income: "Summe Bez\u00fcge: EUR X.XXX,XX" (ASCII-safe) ---
        for i, line in enumerate(lines):
            low_line = line.lower()
            # Match "summe bez\u00fcge" or "summe bezuege" with umlaut-safe regex
            if re.search(r"summe\s+bez.{1,2}ge", low_line) or "summe bezuege" in low_line:
                # Look for amount in next few lines
                for j in range(i, min(i + 4, len(lines))):
                    m = amount_re.match(lines[j].strip())
                    if m:
                        result["gross_income"] = Decimal(
                            m.group(1).replace(".", "").replace(",", ".")
                        )
                        break
                break

        # --- Net income: "AUSZAHLUNGSBETRAG: EUR X.XXX,XX" ---
        for i, line in enumerate(lines):
            if "auszahlungsbetrag" in line.lower():
                for j in range(i, min(i + 4, len(lines))):
                    m = amount_re.match(lines[j].strip())
                    if m:
                        result["net_income"] = Decimal(
                            m.group(1).replace(".", "").replace(",", ".")
                        )
                        break
                break

        return result

    def _extract_payslip_date(self, text: str) -> ExtractedField:
        """Extract date from Austrian payslip - handles MM.YYYY and MM/YYYY formats."""
        # "Auszahlungsmonat: 01.2026" or "Auszahlungsmonat: 01/2026"
        pattern = r"auszahlungsmonat[:\s]*(\d{1,2})[./](\d{4})"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            month, year = int(match.group(1)), int(match.group(2))
            try:
                d = datetime(year, month, 1)
                return ExtractedField(value=d, confidence=0.95)
            except ValueError:
                pass
        # "Gehaltsperiode: J\u00e4nner 2026" or similar - use ASCII-safe month matching
        period_pattern = r"(?:gehaltsperiode|lohnperiode|monat)[:\s]*(\w+)\s+(\d{4})"
        period_match = re.search(period_pattern, text, re.IGNORECASE)
        if period_match:
            month_name = period_match.group(1).lower()
            year = int(period_match.group(2))
            # ASCII-safe month map: use regex matching for umlaut variants
            month_num = self._match_german_month(month_name)
            if month_num:
                try:
                    d = datetime(year, month_num, 1)
                    return ExtractedField(value=d, confidence=0.9)
                except ValueError:
                    pass
        return ExtractedField(value=None, confidence=0.0)

    @staticmethod
    def _match_german_month(name: str) -> Optional[int]:
        """Match German month name, handling umlauts safely."""
        patterns = [
            (r"^j.{1,2}n", 1),       # J\u00e4nner / Januar
            (r"^januar", 1),
            (r"^feb", 2),
            (r"^m.{1,2}rz$", 3),     # M\u00e4rz
            (r"^march$", 3),
            (r"^apr", 4),
            (r"^mai$", 5),
            (r"^may$", 5),
            (r"^jun", 6),
            (r"^jul", 7),
            (r"^aug", 8),
            (r"^sep", 9),
            (r"^okt", 10),
            (r"^oct", 10),
            (r"^nov", 11),
            (r"^dez", 12),
            (r"^dec", 12),
        ]
        for pat, num in patterns:
            if re.match(pat, name, re.IGNORECASE):
                return num
        return None

    def _extract_invoice_fields(self, text: str) -> Dict[str, Any]:
        fields = {}
        invoice_num_field = self.extract_invoice_number(text)
        fields["invoice_number"] = invoice_num_field.value
        fields["invoice_number_confidence"] = invoice_num_field.confidence
        date_field = self.extract_date(text)
        fields["date"] = date_field.value
        fields["date_confidence"] = date_field.confidence
        amount_field = self.extract_total_amount(text)
        fields["amount"] = amount_field.value
        fields["amount_confidence"] = amount_field.confidence
        vat_amounts = self.extract_vat_amounts(text)
        fields["vat_amounts"] = vat_amounts
        total_vat = sum(vat_amounts.values())
        fields["vat_total"] = total_vat
        supplier_field = self.extract_supplier(text)
        fields["supplier"] = supplier_field.value
        fields["supplier_confidence"] = supplier_field.confidence
        # Also store as merchant for OCR transaction service compatibility
        fields["merchant"] = supplier_field.value
        fields["merchant_confidence"] = supplier_field.confidence
        # Extract product description summary
        fields["product_summary"] = self._extract_product_summary(text)
        return fields

    def _extract_svs_fields(self, text: str) -> Dict[str, Any]:
        fields = {}
        fields["pension_contribution"] = self._extract_amount_near_keyword(
            text, ["pensionsversicherung", "pv"]
        )
        fields["health_contribution"] = self._extract_amount_near_keyword(
            text, ["krankenversicherung", "kv"]
        )
        fields["accident_contribution"] = self._extract_amount_near_keyword(
            text, ["unfallversicherung", "uv"]
        )
        amount_field = self.extract_total_amount(text)
        fields["total_contribution"] = amount_field.value
        date_field = self.extract_date(text)
        fields["date"] = date_field.value
        return fields

    def _extract_bescheid_fields(self, text: str) -> Dict[str, Any]:
        """Extract fields from Einkommensteuerbescheid using BescheidExtractor"""
        from app.services.bescheid_extractor import BescheidExtractor

        extractor = BescheidExtractor()
        data = extractor.extract(text)
        return extractor.to_dict(data)

    def _extract_generic_fields(self, text: str) -> Dict[str, Any]:
        fields = {}
        date_field = self.extract_date(text)
        fields["date"] = date_field.value
        amount_field = self.extract_total_amount(text)
        fields["amount"] = amount_field.value
        supplier_field = self.extract_supplier(text)
        fields["supplier"] = supplier_field.value
        fields["merchant"] = supplier_field.value
        fields["product_summary"] = self._extract_product_summary(text)
        return fields

    # ========== Individual field extractors ==========

    # German month names for "22 November 2024" format
    # Use ASCII-safe keys where umlauts might be corrupted
    GERMAN_MONTHS = {
        "januar": 1, "february": 2, "februar": 2, "march": 3,
        "april": 4, "may": 5, "mai": 5, "june": 6, "juni": 6,
        "july": 7, "juli": 7, "august": 8, "september": 9,
        "october": 10, "oktober": 10, "november": 11, "december": 12, "dezember": 12,
    }

    def extract_date(self, text: str) -> ExtractedField:
        """
        Extract date from text. Supports multiple formats:
        - DD.MM.YYYY (Austrian standard)
        - DD/MM/YYYY
        - DD Month YYYY (e.g. "22 November 2024")
        - YYYY-MM-DD (ISO)
        """
        text_lower = text.lower()

        # 0. Try labeled date patterns first (highest reliability)
        # "Date: 08.11.2024", "Datum: 08.11.2024", "Rechnungsdatum: ..."
        labeled_date_pattern = r"(?:date|datum|rechnungsdatum|belegdatum|ausstellungsdatum)[:\s]+(\d{1,2})[./](\d{1,2})[./](\d{4})"
        labeled_match = re.search(labeled_date_pattern, text, re.IGNORECASE)
        if labeled_match:
            day, month, year = labeled_match.group(1), labeled_match.group(2), labeled_match.group(3)
            try:
                d = datetime(int(year), int(month), int(day))
                if datetime(2020, 1, 1) <= d <= datetime.now():
                    return ExtractedField(
                        value=d, confidence=0.95, raw_text=f"{day}.{month}.{year}"
                    )
            except ValueError:
                pass

        # 1. Try "DD Month YYYY" or "DD. Month YYYY" (common in Amazon invoices)
        month_pattern = (
            r"(\d{1,2})\.?\s+("
            + "|".join(self.GERMAN_MONTHS.keys())
            + r")\s+(\d{4})"
        )
        month_matches = re.findall(month_pattern, text_lower)
        if month_matches:
            for day_str, month_name, year_str in month_matches:
                try:
                    month_num = self.GERMAN_MONTHS.get(month_name)
                    if month_num:
                        d = datetime(int(year_str), month_num, int(day_str))
                        if datetime(2020, 1, 1) <= d <= datetime.now():
                            return ExtractedField(
                                value=d, confidence=0.95,
                                raw_text=f"{day_str} {month_name} {year_str}",
                            )
                except ValueError:
                    continue

        # 2. Try DD.MM.YYYY (Austrian standard)
        dot_pattern = r"(\d{1,2})\.(\d{1,2})\.(\d{4})"
        dot_matches = re.findall(dot_pattern, text)
        if dot_matches:
            for day, month, year in dot_matches:
                try:
                    d = datetime(int(year), int(month), int(day))
                    if datetime(2020, 1, 1) <= d <= datetime.now():
                        return ExtractedField(
                            value=d, confidence=0.9, raw_text=f"{day}.{month}.{year}"
                        )
                except ValueError:
                    continue

        # 3. Try DD/MM/YYYY
        slash_pattern = r"(\d{1,2})/(\d{1,2})/(\d{4})"
        slash_matches = re.findall(slash_pattern, text)
        if slash_matches:
            for day, month, year in slash_matches:
                try:
                    d = datetime(int(year), int(month), int(day))
                    if datetime(2020, 1, 1) <= d <= datetime.now():
                        return ExtractedField(
                            value=d, confidence=0.85, raw_text=f"{day}/{month}/{year}"
                        )
                except ValueError:
                    continue

        # 4. Try YYYY-MM-DD (ISO)
        iso_pattern = r"(\d{4})-(\d{2})-(\d{2})"
        iso_matches = re.findall(iso_pattern, text)
        if iso_matches:
            for year, month, day in iso_matches:
                try:
                    d = datetime(int(year), int(month), int(day))
                    if datetime(2020, 1, 1) <= d <= datetime.now():
                        return ExtractedField(
                            value=d, confidence=0.9, raw_text=f"{year}-{month}-{day}"
                        )
                except ValueError:
                    continue

        return ExtractedField(value=None, confidence=0.0)

    def extract_total_amount(self, text: str) -> ExtractedField:
        """Extract total amount. Prioritizes labeled totals over raw amounts."""
        text_lower = text.lower()

        # Priority 1: Labeled total amounts (most reliable)
        # Use .{0,2} to match euro sign which may be corrupted
        labeled_patterns = [
            r"zahlbetrag[:\s]*.{0,2}\s*(\d+[,\.]\d{2})",
            r"gesamtpreis[:\s]*.{0,2}\s*(\d+[,\.]\d{2})",
            r"rechnungsbetrag[:\s]*.{0,2}\s*(\d+[,\.]\d{2})",
            r"total\s+amount\s+due[:\s]*(?:eur|.{0,2})?\s*(\d+[,\.]\d{2})",
            r"total[,.]?\s+payment[^0-9]{0,30}(\d+[,\.]\d{2})",
            r"(?:summe|gesamt|total|betrag)[:\s,]*.{0,2}\s*(\d+[,\.]\d{2})",
        ]

        for pattern in labeled_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    amount_str = match.group(1).replace(",", ".")
                    amount = Decimal(amount_str)
                    if amount > 0:
                        return ExtractedField(value=amount, confidence=0.95)
                except (ValueError, TypeError):
                    continue

        # Priority 2: Amount with euro symbol (use . to match possibly corrupted euro sign)
        euro_amounts = []
        # "123,45 EUR" or "123.45 <euro>"
        euro_pattern = r"(\d+[,\.]\d{2})\s*(?:eur|EUR)"
        for match in re.finditer(euro_pattern, text):
            try:
                amount_str = match.group(1).replace(",", ".")
                amount = Decimal(amount_str)
                if amount > 0:
                    euro_amounts.append(amount)
            except (ValueError, TypeError):
                continue

        # Also try "EUR amount" pattern
        euro_pattern2 = r"(?:eur|EUR)\s*(\d+[,\.]\d{2})"
        for match in re.finditer(euro_pattern2, text):
            try:
                amount_str = match.group(1).replace(",", ".")
                amount = Decimal(amount_str)
                if amount > 0:
                    euro_amounts.append(amount)
            except (ValueError, TypeError):
                continue

        if euro_amounts:
            max_amount = max(euro_amounts)
            confidence = 0.8 if len(euro_amounts) > 1 else 0.9
            return ExtractedField(value=max_amount, confidence=confidence)

        return ExtractedField(value=None, confidence=0.0)

    def extract_merchant(self, text: str) -> ExtractedField:
        """Extract merchant name from receipt/invoice"""
        text_lower = text.lower()

        # Known merchants/companies (expanded)
        merchants = {
            "easypark": ("EasyPark", 0.95),
            "apcoa": ("APCOA Parking", 0.95),
            "wipark": ("WIPARK", 0.95),
            "parkhaus": ("Parkhaus", 0.85),
            "parkgarage": ("Parkgarage", 0.85),
            "kurzparkzone": ("Kurzparkzone", 0.85),
            "amazon": ("Amazon", 0.95),
            "billa": ("BILLA", 0.95),
            "spar": ("SPAR", 0.95),
            "hofer": ("HOFER", 0.95),
            "lidl": ("Lidl", 0.95),
            "merkur": ("MERKUR", 0.95),
            "penny": ("PENNY", 0.95),
            "interspar": ("INTERSPAR", 0.95),
            "obi": ("OBI", 0.9),
            "bauhaus": ("BAUHAUS", 0.9),
            "hornbach": ("HORNBACH", 0.9),
            "dm drogerie": ("dm", 0.9),
            "booking.com": ("Booking.com", 0.95),
            "airbnb": ("Airbnb", 0.95),
            "ikea": ("IKEA", 0.95),
            "mediamarkt": ("MediaMarkt", 0.95),
            "saturn": ("Saturn", 0.95),
            "zalando": ("Zalando", 0.9),
            "dpd": ("DPD", 0.9),
            "gls": ("GLS", 0.85),
            "eni": ("ENI", 0.9),
            "shell": ("Shell", 0.9),
            "omv": ("OMV", 0.9),
            "wipark": ("WIPARK", 0.9),
            "apcoa": ("APCOA", 0.9),
        }

        for key, (official_name, confidence) in merchants.items():
            if key in text_lower:
                return ExtractedField(value=official_name, confidence=confidence)

        # Regex-based merchants (need word boundary or URL context to avoid false positives)
        regex_merchants = [
            (r"\bpost\.at\b|österreichische\s+post|oesterreichische\s+post", "Oesterreichische Post", 0.9),
            (r"\bbp\s", "BP", 0.9),
        ]
        for pattern, official_name, confidence in regex_merchants:
            if re.search(pattern, text_lower):
                return ExtractedField(value=official_name, confidence=confidence)

        # Try "Verkauft von" pattern (Amazon invoices)
        sold_by = re.search(
            r"verkauft\s+von\s+(.+?)(?:\n|$)", text, re.IGNORECASE
        )
        if sold_by:
            name = sold_by.group(1).strip()
            if len(name) > 2 and name.lower() not in ("rechnung",):
                return ExtractedField(value=name, confidence=0.85)

        # Try company suffixes - use \w for umlaut-safe matching
        company_pattern = r"([\w][\w\s\.\-&]+(?:GmbH|AG|KG|OG|e\.U\.|Ltd|Inc)\.?)"
        company_match = re.search(company_pattern, text)
        if company_match:
            name = company_match.group(1).strip()
            if len(name) > 3:
                return ExtractedField(value=name, confidence=0.8)

        # Fallback: first non-trivial line that isn't "Rechnung"
        lines = text.split("\n")[:8]
        for line in lines:
            line = line.strip()
            if (
                len(line) > 3
                and not line[0].isdigit()
                and line.lower() not in (
                    "rechnung", "invoice", "receipt", "kassenbon", "seite"
                )
                and not line.startswith("Seite")
            ):
                return ExtractedField(value=line, confidence=0.5)

        return ExtractedField(value=None, confidence=0.0)

    def extract_line_items(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items from receipt/invoice"""
        items = []
        lines = text.split("\n")

        # Pattern: "Item name  1,23 A" or "Item name  1x 1,23"
        item_pattern = r"^(.+?)\s+(\d+[,\.]\d{2})\s*[A-Z]?\s*$"

        for line in lines:
            line = line.strip()
            match = re.match(item_pattern, line)
            if match:
                item_name = match.group(1).strip()
                price_str = match.group(2).replace(",", ".")
                try:
                    price = Decimal(price_str)
                    items.append({"name": item_name, "price": price})
                except (ValueError, TypeError):
                    continue

        return items

    def extract_vat_amounts(self, text: str) -> Dict[str, Decimal]:
        """Extract VAT amounts (20%, 10%, 13%)"""
        vat_amounts = {}
        text_lower = text.lower()

        # Patterns for VAT extraction - use .{0,2} for euro sign safety
        vat_patterns = [
            (r"(?:ust|mwst)\.?\s*(?:gesamt)?\s*\n?\s*\d+[,\.]\d{2}\s*.{0,2}\s*(\d+[,\.]\d{2})", "20%"),
            (r"20%?\s*(?:ust|mwst).*?(?:eur|.{0,2})\s*(\d+[,\.]\d{2})", "20%"),
            (r"(?:ust|mwst)\s*20%.*?(?:eur|.{0,2})\s*(\d+[,\.]\d{2})", "20%"),
            (r"10%?\s*(?:ust|mwst).*?(?:eur|.{0,2})\s*(\d+[,\.]\d{2})", "10%"),
            (r"(?:ust|mwst)\s*10%.*?(?:eur|.{0,2})\s*(\d+[,\.]\d{2})", "10%"),
            (r"13%?\s*(?:ust|mwst).*?(?:eur|.{0,2})\s*(\d+[,\.]\d{2})", "13%"),
        ]

        for pattern, rate in vat_patterns:
            if rate not in vat_amounts:
                match = re.search(pattern, text_lower)
                if match:
                    try:
                        amount_str = match.group(1).replace(",", ".")
                        vat_amounts[rate] = Decimal(amount_str)
                    except (ValueError, TypeError):
                        continue

        return vat_amounts

    def extract_gross_income(self, text: str) -> ExtractedField:
        return self._extract_amount_near_keyword(
            text,
            [
                "bruttogehalt", "bruttobezug", "brutto",
                "summe bezuege", "gehalt/entsch",
            ],
        )

    def extract_net_income(self, text: str) -> ExtractedField:
        return self._extract_amount_near_keyword(
            text,
            [
                "auszahlungsbetrag", "nettobezug", "nettogehalt", "netto",
            ],
        )

    def extract_withheld_tax(self, text: str) -> ExtractedField:
        return self._extract_amount_near_keyword(
            text, ["lohnsteuer", "einkommensteuer", "lst-basis"]
        )

    def extract_social_insurance(self, text: str) -> ExtractedField:
        return self._extract_amount_near_keyword(
            text,
            [
                "sv/kfa-beitrag", "sv/kfa", "sv-beitrag", "sv beitrag",
                "sozialversicherung", "kfa-beitrag",
            ],
        )

    def extract_employer(self, text: str) -> ExtractedField:
        # Austrian public employer patterns - use .{1,2} for umlaut safety
        employer_patterns = [
            r"(?:arbeitgeber|firma|dienstgeber):\s*(.+?)(?:\n|$)",
            r"(stadt\s+wien[^\n]*)",
            r"(magistrat[^\n]*)",
            r"(land\s+\w+[^\n]*)",
            r"(bundesministerium[^\n]*)",
            r"(universit.{1,2}t[^\n]*)",
        ]
        text_lower = text.lower()
        for pattern in employer_patterns:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                employer = match.group(1).strip().title()
                return ExtractedField(value=employer, confidence=0.85)
        # Fallback: look for "Abs.:" line (common in Austrian official letters)
        abs_match = re.search(r"Abs\.?:\s*(.+?)(?:\n|$)", text)
        if abs_match:
            return ExtractedField(value=abs_match.group(1).strip(), confidence=0.7)
        return ExtractedField(value=None, confidence=0.0)

    def extract_invoice_number(self, text: str) -> ExtractedField:
        """Extract invoice number - supports multi-line patterns"""
        # Single-line: "Rechnungsnummer: LU4627183AEUI"
        pattern = r"(?:rechnungsnummer|rechnungs-nr|invoice\s*(?:no|number))[.:\s]*([A-Z0-9][\w\-]+)"
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return ExtractedField(value=match.group(1).strip(), confidence=0.9)

        # Multi-line: "Rechnungsnummer\nLU4627183AEUI"
        ml_pattern = r"(?:rechnungsnummer|rechnungs-nr|invoice\s*(?:no|number))\s*\n\s*([A-Z0-9][\w\-]+)"
        ml_match = re.search(ml_pattern, text, re.IGNORECASE)
        if ml_match:
            return ExtractedField(value=ml_match.group(1).strip(), confidence=0.85)

        return ExtractedField(value=None, confidence=0.0)

    def extract_supplier(self, text: str) -> ExtractedField:
        """Extract supplier name from invoice"""
        return self.extract_merchant(text)

    def _extract_product_summary(self, text: str) -> Optional[str]:
        """
        Extract a short product/item description from the document text.
        This is used to build a meaningful transaction description.
        """
        # Try "Beschreibung" section (Amazon invoices) - use .{1,2} for umlaut in Stueckpreis
        desc_pattern = r"Beschreibung\s*\n(.+?)(?:\n\s*(?:ASIN|EAN|Menge|St.{1,2}ckpreis|Versand))"
        desc_match = re.search(desc_pattern, text, re.DOTALL)
        if desc_match:
            desc = desc_match.group(1).strip()
            for line in desc.split("\n"):
                line = line.strip()
                if len(line) > 10 and not line.startswith("ASIN") and not line.startswith("EAN"):
                    if len(line) > 80:
                        line = line[:77] + "..."
                    return line

        # Try product name patterns from Amazon
        product_pattern = r"\[PR\d+[^\]]*\]\s*(.+?)(?:\n|$)"
        product_match = re.search(product_pattern, text)
        if product_match:
            name = product_match.group(1).strip()
            if len(name) > 80:
                name = name[:77] + "..."
            return name

        # Try "Amazon-Marke:" or brand patterns
        brand_pattern = r"(?:Amazon-Marke|Marke):\s*(.+?)(?:\n|$)"
        brand_match = re.search(brand_pattern, text)
        if brand_match:
            return brand_match.group(1).strip()[:80]

        # Look for item descriptions with product keywords (ASCII-safe)
        product_keywords = [
            "reinig", "seife", "shampoo",
            "heizung", "heizer", "infrarot", "schneeschaufel", "schaufel",
            "salz", "streusalz", "diesel", "benzin", "treibstoff",
            "handtuch", "matratze", "kissen",
            "pfanne", "topf", "messer", "gabel", "besteck",
            "teller", "glas", "tasse", "becher",
            "schuhe", "schuh", "stiefel", "sneaker",
            "duschgel", "duschvorhang", "seifenspender", "rituals",
            "lebensmittel", "food", "grocery",
        ]

        lines = text.split("\n")
        for line in lines:
            line_stripped = line.strip()
            line_lower = line_stripped.lower()
            if len(line_stripped) > 15:
                for kw in product_keywords:
                    if kw in line_lower:
                        if len(line_stripped) > 80:
                            line_stripped = line_stripped[:77] + "..."
                        return line_stripped

        return None

    def _extract_amount_near_keyword(
        self, text: str, keywords: List[str]
    ) -> ExtractedField:
        """Extract a monetary amount near a keyword, handling European number format.
        European format: 1.234,56 (dot=thousands, comma=decimal)
        """
        text_lower = text.lower()
        for keyword in keywords:
            # Match European amounts like 5.315,59 or 985,05 or 3.373,75
            pattern = rf"{keyword}[^\d]{{0,50}}?(\d{{1,3}}(?:\.\d{{3}})*,\d{{2}})"
            match = re.search(pattern, text_lower)
            if match:
                try:
                    amount_str = match.group(1).replace(".", "").replace(",", ".")
                    amount = Decimal(amount_str)
                    return ExtractedField(value=amount, confidence=0.85)
                except (ValueError, TypeError):
                    continue
            # Fallback: simple format like 985,05 or 21,00
            pattern2 = rf"{keyword}[^\d]{{0,50}}?(\d+,\d{{2}})"
            match2 = re.search(pattern2, text_lower)
            if match2:
                try:
                    amount_str = match2.group(1).replace(",", ".")
                    amount = Decimal(amount_str)
                    return ExtractedField(value=amount, confidence=0.8)
                except (ValueError, TypeError):
                    continue
        return ExtractedField(value=None, confidence=0.0)

    # ========== Multi-receipt segmentation ==========

    # Patterns that indicate the start of a new receipt/invoice within a document
    _RECEIPT_BOUNDARY_PATTERNS = [
        r"--- PAGE \d+ ---",                        # PDF page markers
        r"(?:^|\n)(?:Rechnung|Invoice|Receipt|Beleg|Quittung)\s*(?:\||:|\b)",
        r"(?:^|\n)(?:Rechnungsnummer|Invoice\s*(?:No|Number)|Receipt\s*reference)[:\s]",
    ]

    def segment_multi_receipts(self, text: str) -> List[str]:
        """
        Detect and split text containing multiple receipts/invoices.

        Strategy:
        1. Split by page markers first
        2. Within pages, look for repeated receipt headers
        3. Each segment must have at least one amount to be valid

        Returns:
            List of text segments, one per receipt. Returns [text] if only one found.
        """
        # Step 1: Split by page markers
        pages = re.split(r"--- PAGE \d+ ---\n?", text)
        pages = [p.strip() for p in pages if p.strip()]

        if len(pages) <= 1:
            # Single page — try to detect multiple receipts within it
            return self._split_within_page(text)

        # Step 2: For multi-page, check if each page is a separate receipt
        # by verifying each page has its own amount/total
        amount_pattern = r"\d+[,\.]\d{2}\s*(?:eur|EUR|€)"
        valid_pages = []
        for page in pages:
            if re.search(amount_pattern, page):
                valid_pages.append(page)

        if len(valid_pages) >= 2:
            # Verify pages are truly separate receipts (not continuation)
            # by checking if each has its own total/summe/amount line
            total_pattern = r"(?:summe|total|gesamt|betrag|zahlbetrag|rechnungsbetrag)[:\s,]"
            pages_with_totals = [
                p for p in valid_pages
                if re.search(total_pattern, p, re.IGNORECASE)
            ]
            if len(pages_with_totals) >= 2:
                return pages_with_totals

        # Pages don't look like separate receipts — treat as single document
        return [text]

    def _split_within_page(self, text: str) -> List[str]:
        """Try to detect multiple receipts within a single page of text."""
        # Look for repeated receipt/invoice headers
        header_pattern = r"(?:Rechnung|Invoice|Receipt|Beleg|Quittung)\s*(?:\||:|\b)"
        matches = list(re.finditer(header_pattern, text, re.IGNORECASE))

        if len(matches) >= 2:
            segments = []
            for i, match in enumerate(matches):
                start = match.start()
                end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
                segment = text[start:end].strip()
                # Validate: segment must have an amount
                if re.search(r"\d+[,\.]\d{2}", segment):
                    segments.append(segment)
            if len(segments) >= 2:
                return segments

        return [text]

    def extract_multi_receipt_fields(self, text: str, doc_type: DocumentType) -> List[Dict[str, Any]]:
        """
        Extract fields from text that may contain multiple receipts/invoices.

        Returns:
            List of extracted field dicts, one per detected receipt.
        """
        if doc_type not in (DocumentType.RECEIPT, DocumentType.INVOICE):
            return [self.extract_fields(text, doc_type)]

        segments = self.segment_multi_receipts(text)
        if len(segments) <= 1:
            return [self.extract_fields(text, doc_type)]

        results = []
        for segment in segments:
            fields = self.extract_fields(segment, doc_type)
            # Only include segments that extracted a valid amount
            if fields.get("amount") is not None:
                results.append(fields)

        return results if results else [self.extract_fields(text, doc_type)]



