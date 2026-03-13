"""
E1 Form (Einkommensteuererklärung) Extractor

Parses OCR text from filled E1 tax declaration forms and extracts
structured data including income, expenses, and deductions by KZ (Kennzahl) codes.

This is different from BescheidExtractor which parses tax assessment results.
E1FormExtractor parses the declaration form that taxpayers fill out.
"""
import re
from decimal import Decimal, InvalidOperation
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field


@dataclass
class RentalPropertyDetail:
    """Detailed rental property information from E1b form"""
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    house_number: Optional[str] = None
    einnahmen: Optional[Decimal] = None  # KZ 9460 - Rental income
    afa: Optional[Decimal] = None  # KZ 9500 - Depreciation
    fremdfinanzierung: Optional[Decimal] = None  # KZ 9510 - Financing costs
    instandhaltung: Optional[Decimal] = None  # KZ 9520 - Maintenance
    uebrige_werbungskosten: Optional[Decimal] = None  # KZ 9530 - Other expenses
    einkuenfte: Optional[Decimal] = None  # KZ 9414 - Net rental income


@dataclass
class TaxCalculationResult:
    """Tax calculation results from Einkommensteuerberechnung"""
    gesamtbetrag_einkuenfte: Optional[Decimal] = None  # Total income
    einkommen: Optional[Decimal] = None  # Taxable income after deductions
    steuer_vor_absetzbetraege: Optional[Decimal] = None  # Tax before credits
    absetzbetraege: Optional[Decimal] = None  # Tax credits
    verkehrsabsetzbetrag: Optional[Decimal] = None  # Commuter credit
    einkommensteuer: Optional[Decimal] = None  # Final income tax
    lohnsteuer: Optional[Decimal] = None  # Wage tax paid
    gutschrift: Optional[Decimal] = None  # Refund amount


@dataclass
class E1FormData:
    """Structured data from an E1 tax declaration form"""
    # Header
    tax_year: Optional[int] = None
    taxpayer_name: Optional[str] = None
    steuernummer: Optional[str] = None
    
    # Personal info
    geschlecht: Optional[str] = None  # weiblich/männlich/inter
    personenstand: Optional[str] = None  # verheiratet/ledig/etc
    
    # Income by KZ codes
    kz_245: Optional[Decimal] = None  # Steuerpflichtige Bezüge (employment income)
    kz_210: Optional[Decimal] = None  # Einkünfte aus selbständiger Arbeit
    kz_220: Optional[Decimal] = None  # Einkünfte aus Gewerbebetrieb
    kz_350: Optional[Decimal] = None  # Einkünfte aus Vermietung und Verpachtung
    kz_370: Optional[Decimal] = None  # Einkünfte aus Kapitalvermögen
    kz_390: Optional[Decimal] = None  # Sonstige Einkünfte
    
    # Deductions (Werbungskosten)
    kz_260: Optional[Decimal] = None  # Werbungskosten bei nichtselbständiger Arbeit
    kz_261: Optional[Decimal] = None  # Pendlerpauschale
    kz_262: Optional[Decimal] = None  # Pendlereuro
    kz_263: Optional[Decimal] = None  # Telearbeitspauschale
    
    # Sonderausgaben (special expenses)
    kz_450: Optional[Decimal] = None  # Topf-Sonderausgaben
    kz_458: Optional[Decimal] = None  # Kirchenbeitrag
    kz_459: Optional[Decimal] = None  # Spenden
    
    # Außergewöhnliche Belastungen (extraordinary expenses)
    kz_730: Optional[Decimal] = None  # Außergewöhnliche Belastungen mit Selbstbehalt
    kz_740: Optional[Decimal] = None  # Außergewöhnliche Belastungen ohne Selbstbehalt
    
    # Family info
    anzahl_kinder: Optional[int] = None
    familienbonus_plus: Optional[Decimal] = None  # KZ 770
    alleinverdiener: Optional[bool] = None
    alleinerzieher: Optional[bool] = None
    
    # Loss carryforward (Verlustvortrag)
    kz_462: Optional[Decimal] = None  # Offene Verlustabzüge aus Vorjahren (total prior year losses)
    kz_332: Optional[Decimal] = None  # Verrechenbare Verluste - eigener Betrieb (business losses used)
    kz_346: Optional[Decimal] = None  # Verrechenbare Verluste - Beteiligungen (investment losses used)
    kz_372: Optional[Decimal] = None  # Verrechenbare Verluste - außerbetrieblich (non-business losses used)
    kz_341: Optional[Decimal] = None  # Nicht ausgleichsfähige Verluste - eigener Betrieb (new business losses)
    kz_342: Optional[Decimal] = None  # Nicht ausgleichsfähige Verluste - Beteiligungen (new investment losses)
    kz_371: Optional[Decimal] = None  # Nicht ausgleichsfähige Verluste - außerbetrieblich (new non-business losses)
    
    # Employment details
    anzahl_arbeitgeber: Optional[int] = None  # Number of employers
    gewerkschaftsbeitraege: Optional[Decimal] = None  # KZ 717 - Union dues
    arbeitsmittel: Optional[Decimal] = None  # KZ 719 - Work equipment
    fachliteratur: Optional[Decimal] = None  # KZ 720 - Professional literature
    reisekosten: Optional[Decimal] = None  # KZ 721 - Travel costs
    fortbildung: Optional[Decimal] = None  # KZ 722 - Training costs
    familienheimfahrten: Optional[Decimal] = None  # KZ 300 - Family home trips
    doppelte_haushaltsfuehrung: Optional[Decimal] = None  # KZ 723 - Double household
    sonstige_werbungskosten: Optional[Decimal] = None  # KZ 724 - Other work expenses
    
    # V+V details (rental properties)
    vermietung_details: List[RentalPropertyDetail] = field(default_factory=list)
    
    # Tax calculation results
    tax_calculation: Optional[TaxCalculationResult] = None
    
    # All extracted KZ values (for debugging)
    all_kz_values: Dict[str, Decimal] = field(default_factory=dict)
    
    # Confidence
    confidence: float = 0.0


class E1FormExtractor:
    """Extract structured data from E1 tax declaration form OCR text"""
    
    # Supported years
    SUPPORTED_YEARS = [2023, 2024, 2025]
    
    def detect_format(self, text: str) -> str:
        """
        Detect E1 form format
        Returns: 'standard_e1' | 'steuerberechnung' | 'unknown'
        """
        text_start = text[:1000]
        
        if 'E 1-PDF-' in text_start or ('Einkommensteuererklärung für' in text_start and 'E 1,' in text_start):
            return 'standard_e1'
        elif 'Steuerberechnung für' in text_start:
            return 'steuerberechnung'
        else:
            return 'unknown'
    
    def extract(self, text: str) -> E1FormData:
        """Main extraction method"""
        data = E1FormData()
        
        # Detect format
        format_type = self.detect_format(text)
        
        # Check if format is supported
        if format_type == 'steuerberechnung':
            # For now, extract basic info from Steuerberechnung but mark low confidence
            data.tax_year = self._extract_tax_year(text)
            data.taxpayer_name = self._extract_taxpayer_name(text)
            data.steuernummer = self._extract_steuernummer(text)
            data.confidence = 0.5  # Low confidence for unsupported format
            return data
        elif format_type == 'unknown':
            data.confidence = 0.0
            return data
        
        # Standard E1 form extraction
        data.tax_year = self._extract_tax_year(text)
        data.taxpayer_name = self._extract_taxpayer_name(text)
        data.steuernummer = self._extract_steuernummer(text)
        
        self._extract_personal_info(text, data)
        self._extract_kz_values(text, data)
        self._extract_family_info(text, data)
        self._extract_loss_carryforward(text, data)
        self._extract_employment_details(text, data)
        self._extract_rental_details(text, data)
        self._extract_tax_calculation(text, data)
        
        data.confidence = self._calculate_confidence(data)
        return data
    
    def to_dict(self, data: E1FormData) -> Dict[str, Any]:
        """Convert E1FormData to dictionary for storage"""
        result = {}
        for key, value in data.__dict__.items():
            if value is None:
                result[key] = None
            elif isinstance(value, Decimal):
                result[key] = float(value)
            elif isinstance(value, list):
                # Handle list of dataclass objects
                result[key] = []
                for item in value:
                    if hasattr(item, '__dict__'):
                        # It's a dataclass, convert it
                        item_dict = {}
                        for k, v in item.__dict__.items():
                            if isinstance(v, Decimal):
                                item_dict[k] = float(v) if v is not None else None
                            else:
                                item_dict[k] = v
                        result[key].append(item_dict)
                    elif isinstance(item, dict):
                        result[key].append({
                            k: float(v) if isinstance(v, Decimal) else v 
                            for k, v in item.items()
                        })
                    else:
                        result[key].append(item)
            elif isinstance(value, dict):
                result[key] = {
                    k: float(v) if isinstance(v, Decimal) else v 
                    for k, v in value.items()
                }
            elif hasattr(value, '__dict__'):
                # Handle nested dataclass (like TaxCalculationResult)
                nested_dict = {}
                for k, v in value.__dict__.items():
                    if isinstance(v, Decimal):
                        nested_dict[k] = float(v) if v is not None else None
                    else:
                        nested_dict[k] = v
                result[key] = nested_dict
            else:
                result[key] = value
        return result
    
    # --- Header extraction ---
    
    def _extract_tax_year(self, text: str) -> Optional[int]:
        """Extract tax year from E1 form header"""
        # "Einkommensteuererklärung für 2022"
        m = re.search(r"einkommensteuererkl.{1,2}rung\s+f.{1,2}r\s+(\d{4})", text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            # Validate year is reasonable (between 2000 and current year + 1)
            if 2000 <= year <= 2030:
                return year
        
        # "E 1-EDV-2022"
        m = re.search(r"E\s*1-EDV-(\d{4})", text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 2000 <= year <= 2030:
                return year
        
        # Look for "Jahresabschluss 2022" at the beginning
        m = re.search(r"Jahresabschluss\s+(\d{4})", text, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            if 2000 <= year <= 2030:
                return year
        
        return None
    
    def _extract_taxpayer_name(self, text: str) -> Optional[str]:
        """Extract taxpayer name from form"""
        # Pattern 0: Steuerberechnung format — name after tax number, before "FA:"
        # "03 627/7572\nZhang Fenghong\nFA:"
        m = re.search(
            r"\d{2}\s+\d{3}/\d{4}\s*\n\s*([A-Za-zäöüÄÖÜß]+\s+[A-Za-zäöüÄÖÜß]+)\s*\n\s*FA:",
            text,
        )
        if m:
            name = m.group(1).strip()
            if len(name) > 3 and not any(
                x in name.lower()
                for x in ["seite", "formular", "bitte", "graue", "finanzamt", "steuer", "version"]
            ):
                return name

        # Pattern 1: Name appears multiple times in Einkommensteuerberechnung section
        # "Fenghong ZHANG\nSeite 2\nEinkommensteuerberechnung"
        m = re.search(
            r"([A-Z][a-z]+\s+[A-Z]+)\s*\n\s*Seite\s+\d+\s*\n\s*Einkommensteuerberechnung",
            text,
            re.IGNORECASE
        )
        if m:
            name = m.group(1).strip()
            if len(name) > 5 and not any(x in name.lower() for x in ["seite", "formular", "bitte", "graue", "finanzamt", "steuer"]):
                return name
        
        # Pattern 2: Name appears after St.Nr. in Einkommensteuerberechnung
        # "St.Nr. 03 627/7572\nVNR\nFenghong ZHANG"
        m = re.search(
            r"St\.Nr\.\s+\d{2}\s+\d{3}/\d{4}\s*\n\s*VNR\s*\n\s*([A-Z][a-z]+\s+[A-Z]+)",
            text,
            re.IGNORECASE
        )
        if m:
            name = m.group(1).strip()
            if len(name) > 5 and not any(x in name.lower() for x in ["seite", "formular", "bitte", "graue", "finanzamt", "steuer"]):
                return name
        
        # Pattern 3: Name at the very beginning of document
        # "Jahresabschluss 2020\nFenghong ZHANG"
        m = re.search(
            r"^(?:Jahresabschluss|Einkommensteuererklärung).*?\n\s*([A-Z][a-z]+\s+[A-Z]+)",
            text,
            re.IGNORECASE | re.MULTILINE
        )
        if m:
            name = m.group(1).strip()
            if len(name) > 5 and not any(x in name.lower() for x in ["seite", "formular", "bitte", "graue", "finanzamt", "steuer"]):
                return name
        
        # Pattern 4: Look for name in L1 form (Arbeitnehmerveranlagung)
        m = re.search(
            r"1\.1\s+FAMILIEN-\s+ODER\s+NACHNAME\s+1\.2\s+VORNAME.*?([A-Z]+)\s+([A-Z]+)",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if m:
            vorname = m.group(2).strip()
            nachname = m.group(1).strip()
            if vorname and nachname and len(vorname) > 2 and len(nachname) > 2:
                return f"{vorname} {nachname}"
        
        # Pattern 5: Generic pattern - name before "Seite"
        m = re.search(r"^([A-Z][a-z]+\s+[A-Z]+)\s+Seite", text, re.MULTILINE)
        if m:
            name = m.group(1).strip()
            if len(name) > 5 and not any(x in name.lower() for x in ["seite", "formular", "bitte", "steuer", "finanzamt"]):
                return name
        
        return None
    
    def _extract_steuernummer(self, text: str) -> Optional[str]:
        """Extract tax number (Steuernummer)"""
        # Pattern 1: "St.Nr. 03 627/7572" in Einkommensteuerberechnung (most reliable)
        m = re.search(r"St\.Nr\.\s+(\d{2}\s+\d{3}/\d{4})", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        
        # Pattern 2: Number appears BEFORE "St.Nr.:" label (Steuerberechnung format)
        # "03 627/7572Zhang Fenghong\nFA:\nSt.Nr.:"
        m = re.search(r"(\d{2}\s+\d{3}/\d{4}).*?St\.Nr\.", text, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1).strip()
        
        # Pattern 3: "Steuer-Nr.: 03 627/7572" (E1b form format)
        m = re.search(r"Steuer-Nr\.:?\s*(\d{2}\s+\d{3}/\d{4})", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        
        # Pattern 4: Compact format without spaces "036277572" near "Steuer-Nr"
        m = re.search(r"Steuer-Nr.*?(\d{8,12})", text, re.IGNORECASE | re.DOTALL)
        if m:
            num = m.group(1)
            # Format as "XX XXX/XXXX"
            if len(num) >= 9:
                return f"{num[:2]} {num[2:5]}/{num[5:9]}"
        
        # Pattern 5: "Steuernummer: ..."
        m = re.search(r"Steuernummer[:\s]*(\d[\d\s/]+\d)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        
        return None
    
    def _extract_personal_info(self, text: str, data: E1FormData) -> None:
        """Extract personal information (gender, marital status)"""
        text_lower = text.lower()
        
        # Geschlecht
        if re.search(r"[xX✓]\s*weiblich", text):
            data.geschlecht = "weiblich"
        elif re.search(r"[xX✓]\s*männlich", text):
            data.geschlecht = "männlich"
        
        # Personenstand
        if re.search(r"[xX✓]\s*verheiratet", text):
            data.personenstand = "verheiratet"
        elif re.search(r"[xX✓]\s*ledig", text):
            data.personenstand = "ledig"
        elif re.search(r"[xX✓]\s*geschieden", text):
            data.personenstand = "geschieden"
        elif re.search(r"[xX✓]\s*verwitwet", text):
            data.personenstand = "verwitwet"
    
    def _extract_personal_info_from_fields(self, form_section: str, data: E1FormData) -> None:
        """Extract personal info from AcroForm field values"""
        # Look for name fields
        for pattern in [
            r"(?:familien|nach)name[^:]*:\s*(.+)",
            r"vorname[^:]*:\s*(.+)",
        ]:
            m = re.search(pattern, form_section, re.IGNORECASE)
            if m:
                val = m.group(1).strip()
                if val and len(val) > 1 and not data.taxpayer_name:
                    data.taxpayer_name = val

        # Look for Steuernummer in form fields
        m = re.search(r"(?:steuer|st).*?nr[^:]*:\s*(\d[\d\s/]+\d)", form_section, re.IGNORECASE)
        if m and not data.steuernummer:
            data.steuernummer = m.group(1).strip()

        # Gender from form fields (checkbox values like "1" or "Yes")
        if not data.geschlecht:
            m = re.search(r"(?:weiblich|female)[^:]*:\s*(1|[Jj]a|[Yy]es|[Xx]|true)", form_section, re.IGNORECASE)
            if m:
                data.geschlecht = "weiblich"
            else:
                m = re.search(r"(?:männlich|male)[^:]*:\s*(1|[Jj]a|[Yy]es|[Xx]|true)", form_section, re.IGNORECASE)
                if m:
                    data.geschlecht = "männlich"
    
    def _extract_kz_values(self, text: str, data: E1FormData) -> None:
        """Extract all KZ (Kennzahl) values from the form"""
        # Pattern: KZ number followed by amount
        # Examples:
        # "245  11593,33"
        # "KZ 245: 11.593,33"
        # "Kennzahl 245    11593.33"
        
        # Strategy 0: Parse AcroForm field values (from --- FORM FIELDS --- section)
        # These look like "Kz245: 11593,33" or "KZ_245: 11593.33" or "kz245_betrag: 1234,56"
        form_section = ""
        form_marker = "--- FORM FIELDS ---"
        if form_marker in text:
            form_section = text[text.index(form_marker):]
        
        if form_section:
            # Match field names containing KZ/Kz + digits, followed by a value
            form_patterns = [
                # "Kz245: 11593,33" or "KZ_245: 1234.56"
                r"[Kk][Zz][_\s]?(\d{3,4})[^:]*:\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                # Field name with digits, value is a number (e.g. "betrag245: 1234,56")
                r"(?:betrag|feld|field|wert|val)[_\s]?(\d{3,4})[^:]*:\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                # Generic: any field with 3-4 digit code and numeric value
                r"[A-Za-z_]*(\d{3,4})[A-Za-z_]*:\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ]
            for pattern in form_patterns:
                for match in re.finditer(pattern, form_section, re.IGNORECASE):
                    kz_code = match.group(1)
                    # Normalize 4-digit codes (e.g. 0245 -> 245)
                    if len(kz_code) == 4 and kz_code.startswith("0"):
                        kz_code = kz_code[1:]
                    amount_str = match.group(2)
                    amount = self._parse_amount(amount_str)
                    if amount is not None and amount != Decimal("0"):
                        if kz_code not in data.all_kz_values:
                            data.all_kz_values[kz_code] = amount
                            self._map_kz_to_field(kz_code, amount, data)
            
            # Also extract personal info from form fields
            self._extract_personal_info_from_fields(form_section, data)
        
        # Strategy 1: Find explicit KZ patterns with amounts
        patterns = [
            r"(?:KZ|Kennzahl)?\s*(\d{3})\s*[:\s]+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            r"(\d{3})\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
        ]
        
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                kz_code = match.group(1)
                amount_str = match.group(2)
                amount = self._parse_amount(amount_str)
                
                # Filter out obviously wrong values (likely form line numbers)
                # Real tax amounts are typically > 100 EUR or negative
                if amount is not None and amount != Decimal("0"):
                    # Skip small positive amounts that are likely form line numbers (15.10, 15.11, etc.)
                    if Decimal("0") < amount < Decimal("100") and "." in amount_str:
                        continue
                    data.all_kz_values[kz_code] = amount
                    self._map_kz_to_field(kz_code, amount, data)
        
        # Strategy 2: Special handling for KZ 245 (employment income) in Einkommensteuerberechnung
        # Look for "Summe Lohnzettel L16 [KZ 245]" or similar
        if not data.kz_245:
            m = re.search(
                r"Summe\s+Lohnzettel.*?\[KZ\s+245\]\s*\n?\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if m:
                amount = self._parse_amount(m.group(1))
                if amount and amount > 0:
                    data.kz_245 = amount
                    data.all_kz_values["245"] = amount
        
        # Strategy 2b: Steuerberechnung format — "stpfl.Bezüge (245)" then employer, then amount
        if not data.kz_245:
            m = re.search(
                r"stpfl\.Bez.{1,3}ge\s*\(245\).*?(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if m:
                amount = self._parse_amount(m.group(1))
                if amount and amount > 0:
                    data.kz_245 = amount
                    data.all_kz_values["245"] = amount
        
        # Strategy 2c: "Anrechenbare Lohnsteuer (260)" pattern for KZ 260
        if not data.kz_260:
            m = re.search(
                r"Anrechenbare\s+Lohnsteuer\s*\(260\)\s*\n?\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                text,
                re.IGNORECASE | re.DOTALL
            )
            if m:
                amount = self._parse_amount(m.group(1))
                if amount is not None:
                    data.kz_260 = amount
                    data.all_kz_values["260"] = amount
        
        # Strategy 3: Special handling for rental income (KZ 350) in Einkommensteuerberechnung
        # Look for "Einkünfte aus Vermietung und Verpachtung" followed by amount
        m = re.search(
            r"Einkünfte\s+aus\s+Vermietung\s+und\s+Verpachtung\s*\n?\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if m:
            amount = self._parse_amount(m.group(1))
            if amount is not None:  # Can be negative (loss)
                data.kz_350 = amount
                data.all_kz_values["350"] = amount
        
        # Strategy 4: Special handling for "Gesamtbetrag der Einkünfte"
        m = re.search(
            r"Gesamtbetrag\s+der\s+Einkünfte\s*\n?\s*(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            text,
            re.IGNORECASE | re.DOTALL
        )
        if m:
            amount = self._parse_amount(m.group(1))
            if amount is not None:
                # Store as a special key for reference
                data.all_kz_values["gesamtbetrag_einkuenfte"] = amount
    
    def _map_kz_to_field(self, kz_code: str, amount: Decimal, data: E1FormData) -> None:
        """Map KZ code to specific data field"""
        if kz_code == "245":
            data.kz_245 = amount
        elif kz_code == "210":
            data.kz_210 = amount
        elif kz_code == "220":
            data.kz_220 = amount
        elif kz_code == "350" or kz_code == "370":
            data.kz_350 = amount
        elif kz_code == "370":
            data.kz_370 = amount
        elif kz_code == "390":
            data.kz_390 = amount
        elif kz_code == "260":
            data.kz_260 = amount
        elif kz_code == "261":
            data.kz_261 = amount
        elif kz_code == "262":
            data.kz_262 = amount
        elif kz_code == "263":
            data.kz_263 = amount
        elif kz_code == "450":
            data.kz_450 = amount
        elif kz_code == "458":
            data.kz_458 = amount
        elif kz_code == "459":
            data.kz_459 = amount
        elif kz_code == "730":
            data.kz_730 = amount
        elif kz_code == "740":
            data.kz_740 = amount
        elif kz_code == "770":
            data.familienbonus_plus = amount
        # Loss carryforward fields
        elif kz_code == "462":
            data.kz_462 = amount
        elif kz_code == "332":
            data.kz_332 = amount
        elif kz_code == "346":
            data.kz_346 = amount
        elif kz_code == "372":
            data.kz_372 = amount
        elif kz_code == "341":
            data.kz_341 = amount
        elif kz_code == "342":
            data.kz_342 = amount
        elif kz_code == "371":
            data.kz_371 = amount
    
    def _extract_family_info(self, text: str, data: E1FormData) -> None:
        """Extract family-related information"""
        # Anzahl der Kinder
        m = re.search(r"anzahl\s+(?:der\s+)?kinder[:\s]*(\d+)", text, re.IGNORECASE)
        if m:
            data.anzahl_kinder = int(m.group(1))
        
        # Alleinverdiener/Alleinerzieher checkboxes
        if re.search(r"[xX✓]\s*alleinverdiener", text, re.IGNORECASE):
            data.alleinverdiener = True
        if re.search(r"[xX✓]\s*alleinerzieher", text, re.IGNORECASE):
            data.alleinerzieher = True
    
    def _extract_loss_carryforward(self, text: str, data: E1FormData) -> None:
        """Extract loss carryforward information (Verlustvortrag)"""
        # These fields are critical for business owners and self-employed
        
        # KZ 462: Total prior year losses (Offene Verlustabzüge aus Vorjahren)
        # This appears in section 25.3 "Verlustabzug"
        m = re.search(r"462\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_462 = amount
                data.all_kz_values["462"] = amount
        
        # KZ 332: Business losses used this year (Verrechenbare Verluste - eigener Betrieb)
        m = re.search(r"332\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_332 = amount
                data.all_kz_values["332"] = amount
        
        # KZ 346: Investment losses used this year (Verrechenbare Verluste - Beteiligungen)
        m = re.search(r"346\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_346 = amount
                data.all_kz_values["346"] = amount
        
        # KZ 372: Non-business losses used this year (Verrechenbare Verluste - außerbetrieblich)
        m = re.search(r"372\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_372 = amount
                data.all_kz_values["372"] = amount
        
        # KZ 341: New business losses (Nicht ausgleichsfähige Verluste - eigener Betrieb)
        m = re.search(r"341\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_341 = amount
                data.all_kz_values["341"] = amount
        
        # KZ 342: New investment losses (Nicht ausgleichsfähige Verluste - Beteiligungen)
        m = re.search(r"342\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_342 = amount
                data.all_kz_values["342"] = amount
        
        # KZ 371: New non-business losses (Nicht ausgleichsfähige Verluste - außerbetrieblich)
        m = re.search(r"371\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", text, re.IGNORECASE)
        if m:
            amount = self._parse_amount(m.group(1))
            if amount and amount > 0:
                data.kz_371 = amount
                data.all_kz_values["371"] = amount
    
    def _extract_employment_details(self, text: str, data: E1FormData) -> None:
        """Extract detailed employment-related expenses (Werbungskosten)"""
        # Number of employers (KZ 4.1) - look for the actual number, not the year
        m = re.search(r"4\.1\s+Anzahl\s+der\s+inländischen.*?(\d+)", text, re.IGNORECASE | re.DOTALL)
        if m:
            num = int(m.group(1))
            # Filter out year values (2020, 2021, etc.)
            if num < 100:
                data.anzahl_arbeitgeber = num
        
        # Extract specific Werbungskosten line items - only accept amounts > 100 EUR
        werbungskosten_patterns = {
            'gewerkschaftsbeitraege': (r"717\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_717'),
            'arbeitsmittel': (r"719\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_719'),
            'fachliteratur': (r"720\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_720'),
            'reisekosten': (r"721\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_721'),
            'fortbildung': (r"722\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_722'),
            'familienheimfahrten': (r"300\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_300'),
            'doppelte_haushaltsfuehrung': (r"723\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_723'),
            'sonstige_werbungskosten': (r"724\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})", 'kz_724'),
        }
        
        for field_name, (pattern, kz_name) in werbungskosten_patterns.items():
            m = re.search(pattern, text)
            if m:
                amount = self._parse_amount(m.group(1))
                # Only accept amounts > 100 EUR to filter out form line numbers like 15.10, 15.11
                if amount and amount > 100:
                    setattr(data, field_name, amount)
                    data.all_kz_values[kz_name] = amount
    
    def _extract_rental_details(self, text: str, data: E1FormData) -> None:
        """Extract detailed rental property information from E1b form"""
        # Look for E1b form section (Beilage zur E1 für Vermietung und Verpachtung)
        e1b_pattern = r"Beilage zur Eink.*?ommensteuererklärung E 1 für Einkünfte aus Vermietung"
        if not re.search(e1b_pattern, text, re.IGNORECASE | re.DOTALL):
            return
        
        # Split text into E1b sections (each E1b form is 3 pages)
        # Look for "E 1b, Seite 3" followed by amounts to find each property's summary
        e1b_summaries = re.finditer(
            r"E 1b, Seite 3.*?Einnahmenüberschuss oder Werbungskostenüberschuss.*?9414.*?Steuer-Nr.*?(\d{8,12}).*?(\d{1,3}[.,]\d{3}[.,]\d{2})\s+(-?\d{1,3}[.,]\d{3}[.,]\d{2})",
            text,
            re.IGNORECASE | re.DOTALL
        )
        
        for match in e1b_summaries:
            property_detail = RentalPropertyDetail()
            
            # Extract Steuer-Nr (for validation)
            steuernr = match.group(1)
            
            # Extract amounts from page 3 summary
            # Group 2: Total income/expenses (KZ 9460 or total Werbungskosten)
            # Group 3: Net income (KZ 9414)
            amount1_str = match.group(2)
            amount2_str = match.group(3)
            
            amount1 = self._parse_amount(amount1_str)
            amount2 = self._parse_amount(amount2_str)
            
            # amount2 is always the net income (KZ 9414)
            if amount2 and abs(amount2) > 0:
                property_detail.einkuenfte = amount2
                data.all_kz_values['kz_9414'] = amount2
            
            # amount1 could be either income (KZ 9460) or total expenses
            # If net is negative (loss), amount1 is likely total expenses
            # If net is positive, amount1 is likely gross income
            if amount1 and abs(amount1) > 100:
                if amount2 and amount2 < 0:
                    # Loss scenario: amount1 is total expenses
                    property_detail.uebrige_werbungskosten = amount1
                    # Calculate gross income: expenses - abs(loss)
                    gross_income = amount1 - abs(amount2)
                    if gross_income > 0:
                        property_detail.einnahmen = gross_income
                        data.all_kz_values['kz_9460'] = gross_income
                else:
                    # Profit scenario: amount1 is gross income
                    property_detail.einnahmen = amount1
                    data.all_kz_values['kz_9460'] = amount1
            
            # Try to find property address from the same E1b section
            # Look backwards from the summary to find the address on page 1
            section_start = max(0, match.start() - 5000)  # Look back up to 5000 chars
            section_text = text[section_start:match.end()]
            
            # Extract address components
            addr_match = re.search(
                r"Postleitzahl\s+Ort\s+Straße.*?(\d{4})\s+([A-Za-zäöüÄÖÜß\s]+?)(?:\n|Straße)",
                section_text,
                re.IGNORECASE | re.DOTALL
            )
            if addr_match:
                property_detail.postal_code = addr_match.group(1).strip()
                property_detail.city = addr_match.group(2).strip()
            
            # Also try to extract from Steuerberechnung page (page 10)
            # Pattern: "E1b, Address"
            addr_match2 = re.search(
                r"E1b,\s+([^,]+),\s+(\d{4})\s+([A-Za-zäöüÄÖÜß\s]+)",
                text,
                re.IGNORECASE
            )
            if addr_match2 and not property_detail.city:
                property_detail.street = addr_match2.group(1).strip()
                property_detail.postal_code = addr_match2.group(2).strip()
                property_detail.city = addr_match2.group(3).strip()
                property_detail.address = f"{property_detail.street}, {property_detail.postal_code} {property_detail.city}"
            
            # Only add if we found some data
            if any([property_detail.einnahmen, property_detail.einkuenfte, property_detail.uebrige_werbungskosten]):
                data.vermietung_details.append(property_detail)
        
        # Alternative: Extract from Steuerberechnung page (simpler, more reliable)
        # Pattern: "E1b, Address ... amount"
        # Use [^-\d]+ for city to match everything until we hit a digit or minus sign
        steuerberechnung_rentals = re.finditer(
            r"E1b,\s+([^,]+),\s+(\d{4})\s+([^-\d]+)\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            text,
            re.IGNORECASE
        )
        
        rental_from_steuerberechnung = []
        for match in steuerberechnung_rentals:
            street = match.group(1).strip()
            postal_code = match.group(2).strip()
            city = match.group(3).strip()
            net_income = self._parse_amount(match.group(4))
            
            if net_income is not None:  # Include even 0.00 amounts
                rental_from_steuerberechnung.append({
                    'street': street,
                    'postal_code': postal_code,
                    'city': city,
                    'net_income': net_income,
                    'address': f"{street}, {postal_code} {city}"
                })
        
        # If we found rentals from Steuerberechnung but not from E1b summaries,
        # use the Steuerberechnung data
        if rental_from_steuerberechnung and not data.vermietung_details:
            for rental_info in rental_from_steuerberechnung:
                property_detail = RentalPropertyDetail()
                property_detail.street = rental_info['street']
                property_detail.postal_code = rental_info['postal_code']
                property_detail.city = rental_info['city']
                property_detail.address = rental_info['address']
                property_detail.einkuenfte = rental_info['net_income']
                # Only add to all_kz_values if non-zero
                if rental_info['net_income'] != Decimal("0"):
                    kz_key = f"kz_9414_{len(data.vermietung_details) + 1}"
                    data.all_kz_values[kz_key] = rental_info['net_income']
                data.vermietung_details.append(property_detail)
        
        # Calculate total KZ 350 (sum of all rental net incomes)
        if data.vermietung_details:
            total_rental_income = sum(
                (prop.einkuenfte or Decimal("0")) for prop in data.vermietung_details
            )
            if total_rental_income != Decimal("0"):
                data.kz_350 = total_rental_income
                data.all_kz_values["350"] = total_rental_income
    
    def _extract_tax_calculation(self, text: str, data: E1FormData) -> None:
        """Extract tax calculation results from Einkommensteuerberechnung or Steuerberechnung"""
        # Look for tax calculation section (both formats)
        if not re.search(r"(Einkommensteuerberechnung|Steuerberechnung\s+für)", text, re.IGNORECASE):
            return
        
        calc = TaxCalculationResult()
        
        # Extract key tax calculation values with multiple pattern variations
        tax_patterns = {
            'gesamtbetrag_einkuenfte': [
                r"Gesamtbetrag\s+der\s+Einkünfte\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'einkommen': [
                r"Das\s+Einkommen\s+im\s+Jahr\s+\d{4}\s+beträgt\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"Einkommen\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'steuer_vor_absetzbetraege': [
                r"Steuer\s+vor\s+Abzug\s+der\s+Absetzbeträge\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'verkehrsabsetzbetrag': [
                r"Verkehrsabsetzbetrag\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'absetzbetraege': [
                r"Summe\s+Absetzbeträge\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"Steuer\s+nach\s+Abzug\s+der\s+Absetzbeträge\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'einkommensteuer': [
                r"Festgesetzte\s+Einkommensteuer[^-]*?(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"Einkommensteuer\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'lohnsteuer': [
                r"Anrechenbare\s+Lohnsteuer[^-]*?(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"Lohnsteuer\s+\(260\)\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
            'gutschrift': [
                r"Abgabengutschrift\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"Voraussichtliche\s+Abgabengutschrift\s+in\s+Höhe\s+von\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
                r"G\s*u\s*t\s*s\s*c\s*h\s*r\s*i\s*f\s*t\s+(-?\d{1,3}(?:[.,]\d{3})*[.,]\d{2})",
            ],
        }
        
        for field_name, patterns in tax_patterns.items():
            for pattern in patterns:
                m = re.search(pattern, text, re.IGNORECASE)
                if m:
                    amount = self._parse_amount(m.group(1))
                    if amount is not None:
                        setattr(calc, field_name, amount)
                        break  # Found a match, move to next field
        
        # Only set if we found some data
        if any([calc.gesamtbetrag_einkuenfte, calc.einkommen, calc.einkommensteuer, calc.gutschrift]):
            data.tax_calculation = calc
    
    # --- Helpers ---
    
    @staticmethod
    def _parse_amount(text: str) -> Optional[Decimal]:
        """Parse Austrian/German number format: 1.234,56 or 1234,56 -> 1234.56"""
        if not text:
            return None
        try:
            # Remove spaces
            cleaned = text.strip().replace(" ", "")
            # Handle both . and , as thousand separator, and , or . as decimal
            # Austrian format: 1.234,56
            # Also accept: 1234.56 (international)
            
            # Check if it has both . and ,
            if "." in cleaned and "," in cleaned:
                # Austrian format: . is thousand, , is decimal
                cleaned = cleaned.replace(".", "").replace(",", ".")
            elif "," in cleaned:
                # Only comma: assume it's decimal separator
                cleaned = cleaned.replace(",", ".")
            # else: only dots or no separator, keep as is
            
            # Handle negative
            is_negative = cleaned.startswith("-")
            cleaned = cleaned.lstrip("-")
            
            val = Decimal(cleaned)
            if is_negative:
                val = -val
            return val
        except (InvalidOperation, ValueError):
            return None
    
    @staticmethod
    def _calculate_confidence(data: E1FormData) -> float:
        """Calculate overall extraction confidence"""
        score = 0.0
        total_fields = 0
        
        checks = [
            data.tax_year is not None,
            data.taxpayer_name is not None,
            len(data.all_kz_values) > 0,
            data.kz_245 is not None or data.kz_210 is not None or data.kz_220 is not None,
        ]
        
        for check in checks:
            total_fields += 1
            if check:
                score += 1
        
        return round(score / total_fields, 2) if total_fields > 0 else 0.0
