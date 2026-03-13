"""FinanzOnline XML generator for Austrian tax filing"""
import logging
import xml.etree.ElementTree as ET
from xml.dom import minidom
from typing import Dict, Optional
from decimal import Decimal

logger = logging.getLogger(__name__)


class FinanzOnlineXMLGenerator:
    """
    FinanzOnline XML generator for Austrian tax filing.
    
    Generates XML according to FinanzOnline 2026 schema for:
    - Einkommensteuererklärung (Income Tax Declaration)
    - Taxpayer information
    - Income sections (employment, rental, self-employment)
    - Deductions (SVS, Pendlerpauschale, etc.)
    - Tax calculation
    """
    
    def generate(
        self,
        user_data: Dict,
        tax_data: Dict,
        tax_year: int
    ) -> str:
        """
        Generate FinanzOnline XML for tax filing.
        
        Args:
            user_data: User information (name, tax_number, address, user_type)
            tax_data: Tax calculation data
            tax_year: Tax year
            
        Returns:
            Formatted XML string
        """
        # Create root element
        root = ET.Element('Einkommensteuererklärung')
        root.set('Jahr', str(tax_year))
        root.set('Version', '2026.1')
        root.set('xmlns', 'http://www.bmf.gv.at/egovportal/finanzonline')
        
        # Taxpayer information
        self._add_taxpayer_info(root, user_data)
        
        # Income sections
        self._add_income_sections(root, tax_data)
        
        # Deductions
        self._add_deductions(root, tax_data)
        
        # Tax calculation
        self._add_tax_calculation(root, tax_data)
        
        # Format and return XML
        return self._prettify_xml(root)
    
    def _add_taxpayer_info(self, root: ET.Element, user_data: Dict):
        """Add taxpayer information section"""
        taxpayer = ET.SubElement(root, 'Steuerpflichtiger')
        
        # Tax number (Steuernummer)
        if user_data.get('tax_number'):
            steuernummer = ET.SubElement(taxpayer, 'Steuernummer')
            steuernummer.text = self._sanitize_xml_text(str(user_data['tax_number']))
        
        # Name
        if user_data.get('name'):
            name = ET.SubElement(taxpayer, 'Name')
            name.text = self._sanitize_xml_text(str(user_data['name']))
        
        # Address
        if user_data.get('address'):
            adresse = ET.SubElement(taxpayer, 'Adresse')
            adresse.text = self._sanitize_xml_text(str(user_data['address']))
        
        # VAT number (if applicable)
        if user_data.get('vat_number'):
            uid = ET.SubElement(taxpayer, 'UID')
            uid.text = self._sanitize_xml_text(str(user_data['vat_number']))
    
    def _add_income_sections(self, root: ET.Element, tax_data: Dict):
        """Add income sections"""
        income_summary = tax_data.get('income_summary', {})
        
        # Only add Einkünfte section if there is income
        if income_summary.get('total', 0) > 0:
            einkuenfte = ET.SubElement(root, 'Einkünfte')
            
            # Employment income (Nichtselbständige Arbeit)
            employment_income = income_summary.get('employment', 0)
            if employment_income > 0:
                nichtselbstaendig = ET.SubElement(einkuenfte, 'NichtselbständigeArbeit')
                betrag = ET.SubElement(nichtselbstaendig, 'Betrag')
                betrag.text = self._format_amount(employment_income)
            
            # Rental income (Vermietung und Verpachtung)
            rental_income = income_summary.get('rental', 0)
            if rental_income > 0:
                vermietung = ET.SubElement(einkuenfte, 'VermietungUndVerpachtung')
                
                # Income
                einnahmen = ET.SubElement(vermietung, 'Einnahmen')
                einnahmen.text = self._format_amount(rental_income)
                
                # Expenses (Werbungskosten)
                expense_summary = tax_data.get('expense_summary', {})
                rental_expenses = expense_summary.get('deductible', 0)  # Simplified
                if rental_expenses > 0:
                    werbungskosten = ET.SubElement(vermietung, 'Werbungskosten')
                    werbungskosten.text = self._format_amount(rental_expenses)
            
            # Self-employment income (Selbständige Arbeit)
            self_employment_income = income_summary.get('self_employment', 0)
            if self_employment_income > 0:
                selbstaendig = ET.SubElement(einkuenfte, 'SelbständigeArbeit')
                
                # Income
                einnahmen = ET.SubElement(selbstaendig, 'Einnahmen')
                einnahmen.text = self._format_amount(self_employment_income)
                
                # Business expenses (Betriebsausgaben)
                expense_summary = tax_data.get('expense_summary', {})
                business_expenses = expense_summary.get('deductible', 0)  # Simplified
                if business_expenses > 0:
                    betriebsausgaben = ET.SubElement(selbstaendig, 'Betriebsausgaben')
                    betriebsausgaben.text = self._format_amount(business_expenses)
            
            # Capital gains (Kapitalerträge)
            capital_gains = income_summary.get('capital_gains', 0)
            if capital_gains > 0:
                kapital = ET.SubElement(einkuenfte, 'Kapitalerträge')
                betrag = ET.SubElement(kapital, 'Betrag')
                betrag.text = self._format_amount(capital_gains)
    
    def _add_deductions(self, root: ET.Element, tax_data: Dict):
        """Add deductions section (Sonderausgaben)"""
        deductions = tax_data.get('deductions', {})
        
        # Only add Sonderausgaben if there are deductions
        if deductions.get('total', 0) > 0:
            sonderausgaben = ET.SubElement(root, 'Sonderausgaben')
            
            # SVS contributions (Sozialversicherung)
            svs = deductions.get('svs_contributions', 0)
            if svs > 0:
                sozialversicherung = ET.SubElement(sonderausgaben, 'Sozialversicherung')
                sozialversicherung.text = self._format_amount(svs)
            
            # Commuting allowance (Pendlerpauschale)
            commuting = deductions.get('commuting_allowance', 0)
            if commuting > 0:
                pendler = ET.SubElement(sonderausgaben, 'Pendlerpauschale')
                pendler.text = self._format_amount(commuting)
            
            # Home office deduction (Homeoffice-Pauschale)
            home_office = deductions.get('home_office', 0)
            if home_office > 0:
                homeoffice = ET.SubElement(sonderausgaben, 'HomeofficePauschale')
                homeoffice.text = self._format_amount(home_office)
            
            # Family deductions (Kinderabsetzbetrag)
            family = deductions.get('family_deductions', 0)
            if family > 0:
                kinder = ET.SubElement(sonderausgaben, 'Kinderabsetzbetrag')
                kinder.text = self._format_amount(family)
    
    def _add_tax_calculation(self, root: ET.Element, tax_data: Dict):
        """Add tax calculation section"""
        tax_calc = tax_data.get('tax_calculation', {})
        
        steuerberechnung = ET.SubElement(root, 'Steuerberechnung')
        
        # Total income (Einkommen)
        total_income = tax_calc.get('gross_income', 0)
        if total_income > 0:
            einkommen = ET.SubElement(steuerberechnung, 'Einkommen')
            einkommen.text = self._format_amount(total_income)
        
        # Deductions (Abzüge)
        total_deductions = tax_calc.get('deductions', 0)
        if total_deductions > 0:
            abzuege = ET.SubElement(steuerberechnung, 'Abzüge')
            abzuege.text = self._format_amount(total_deductions)
        
        # Taxable income (Zu versteuerndes Einkommen)
        taxable_income = tax_calc.get('taxable_income', 0)
        if taxable_income > 0:
            zu_versteuern = ET.SubElement(steuerberechnung, 'ZuVersteuerndesEinkommen')
            zu_versteuern.text = self._format_amount(taxable_income)
        
        # Income tax (Einkommensteuer)
        income_tax = tax_calc.get('income_tax', 0)
        einkommensteuer = ET.SubElement(steuerberechnung, 'Einkommensteuer')
        einkommensteuer.text = self._format_amount(income_tax)
        
        # VAT (Umsatzsteuer) - if applicable
        if not tax_calc.get('vat_exempt', True):
            vat = tax_calc.get('vat', 0)
            if vat > 0:
                umsatzsteuer = ET.SubElement(steuerberechnung, 'Umsatzsteuer')
                umsatzsteuer.text = self._format_amount(vat)
        
        # SVS contributions
        svs = tax_calc.get('svs', 0)
        if svs > 0:
            svs_elem = ET.SubElement(steuerberechnung, 'SVSBeiträge')
            svs_elem.text = self._format_amount(svs)
        
        # Total tax (Gesamtsteuer)
        total_tax = tax_calc.get('total_tax', 0)
        gesamtsteuer = ET.SubElement(steuerberechnung, 'Gesamtsteuer')
        gesamtsteuer.text = self._format_amount(total_tax)
        
        # Net income (Nettoeinkommen)
        net_income = tax_calc.get('net_income', 0)
        nettoeinkommen = ET.SubElement(steuerberechnung, 'Nettoeinkommen')
        nettoeinkommen.text = self._format_amount(net_income)
    
    def _format_amount(self, amount) -> str:
        """
        Format amount for XML (2 decimal places).
        
        Args:
            amount: Amount to format
            
        Returns:
            Formatted amount string
        """
        if isinstance(amount, Decimal):
            return f"{amount:.2f}"
        elif isinstance(amount, (int, float)):
            return f"{float(amount):.2f}"
        else:
            return "0.00"
    
    def _sanitize_xml_text(self, text: str) -> str:
        """
        Sanitize text for XML by removing invalid characters.
        
        XML 1.0 only allows certain characters:
        - #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text safe for XML
        """
        import re
        # Remove invalid XML characters
        # Valid: tab (0x09), newline (0x0A), carriage return (0x0D), and >= 0x20
        invalid_chars = re.compile(r'[\x00-\x08\x0B\x0C\x0E-\x1F]')
        return invalid_chars.sub('', text)
    
    def _prettify_xml(self, elem: ET.Element) -> str:
        """
        Return a pretty-printed XML string.
        
        Args:
            elem: XML element
            
        Returns:
            Formatted XML string
        """
        rough_string = ET.tostring(elem, encoding='unicode', method='xml')
        reparsed = minidom.parseString(rough_string)
        return reparsed.toprettyxml(indent="  ")
    
    def validate(self, xml_string: str, schema_path: Optional[str] = None) -> bool:
        """
        Validate XML against FinanzOnline schema.
        
        Args:
            xml_string: XML string to validate
            schema_path: Path to XSD schema file (optional)
            
        Returns:
            True if valid, raises ValueError if invalid
        """
        # Parse XML to check if it's well-formed
        try:
            ET.fromstring(xml_string)
        except ET.ParseError as e:
            raise ValueError(f"XML is malformed: {e}")

        # XSD schema validation (requires lxml)
        if schema_path:
            try:
                from lxml import etree as lxml_etree

                with open(schema_path, "rb") as f:
                    schema_doc = lxml_etree.parse(f)
                schema = lxml_etree.XMLSchema(schema_doc)
                doc = lxml_etree.fromstring(xml_string.encode("utf-8"))
                schema.assertValid(doc)
            except ImportError:
                logger.warning(
                    "lxml not installed — skipping XSD validation. "
                    "Install with: pip install lxml"
                )
            except lxml_etree.DocumentInvalid as e:
                raise ValueError(f"XML schema validation failed: {e}")

        return True
