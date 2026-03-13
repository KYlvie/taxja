"""
Test data generator for E1/Bescheid import UAT testing.

Creates realistic E1 forms and Bescheid documents with property addresses
for testing property matching and linking workflows.
"""

from datetime import date
from decimal import Decimal
from typing import Dict, List, Optional
import random


class E1BescheidTestDataGenerator:
    """Generate realistic E1 and Bescheid test data for UAT"""
    
    # Test property addresses for matching scenarios
    TEST_PROPERTIES = [
        {
            "id": "exact_match",
            "street": "Hauptstraße 123",
            "city": "Wien",
            "postal_code": "1010",
            "description": "Exact match scenario - address matches exactly"
        },
        {
            "id": "fuzzy_match",
            "street": "Mariahilfer Str. 45",  # Abbreviated
            "city": "Wien",
            "postal_code": "1060",
            "description": "Fuzzy match scenario - abbreviated street name"
        },
        {
            "id": "no_match",
            "street": "Linzer Straße 78",
            "city": "Salzburg",
            "postal_code": "5020",
            "description": "No match scenario - property not registered"
        },
        {
            "id": "multiple_1",
            "street": "Grazer Straße 12",
            "city": "Graz",
            "postal_code": "8010",
            "description": "Multi-property scenario - property 1"
        },
        {
            "id": "multiple_2",
            "street": "Innsbrucker Straße 56",
            "city": "Innsbruck",
            "postal_code": "6020",
            "description": "Multi-property scenario - property 2"
        },
    ]
    
    @staticmethod
    def generate_e1_form_text(
        scenario: str,
        tax_year: int = 2025,
        taxpayer_name: str = "Max Mustermann",
        steuernummer: str = "12-345/6789"
    ) -> str:
        """
        Generate E1 form OCR text for different test scenarios.
        
        Scenarios:
        - "exact_match": Single property with exact address match
        - "fuzzy_match": Single property with fuzzy address match
        - "no_match": Property not registered (should create new)
        - "multiple": Multiple properties
        - "no_address": Rental income without property address
        """
        
        if scenario == "exact_match":
            return E1BescheidTestDataGenerator._generate_e1_exact_match(
                tax_year, taxpayer_name, steuernummer
            )
        elif scenario == "fuzzy_match":
            return E1BescheidTestDataGenerator._generate_e1_fuzzy_match(
                tax_year, taxpayer_name, steuernummer
            )
        elif scenario == "no_match":
            return E1BescheidTestDataGenerator._generate_e1_no_match(
                tax_year, taxpayer_name, steuernummer
            )
        elif scenario == "multiple":
            return E1BescheidTestDataGenerator._generate_e1_multiple(
                tax_year, taxpayer_name, steuernummer
            )
        elif scenario == "no_address":
            return E1BescheidTestDataGenerator._generate_e1_no_address(
                tax_year, taxpayer_name, steuernummer
            )
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
    
    @staticmethod
    def _generate_e1_exact_match(
        tax_year: int, taxpayer_name: str, steuernummer: str
    ) -> str:
        """E1 form with exact property address match"""
        return f"""
EINKOMMENSTEUERERKLÄRUNG {tax_year}
E1 Formular

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

KZ 245 - Einkünfte aus nichtselbständiger Arbeit
Betrag: 45.000,00 EUR

KZ 350 - Einkünfte aus Vermietung und Verpachtung
Betrag: 14.400,00 EUR

Vermietungsdetails:
Objekt: Hauptstraße 123, 1010 Wien
Monatliche Miete: 1.200,00 EUR
Jahresmiete: 14.400,00 EUR

WERBUNGSKOSTEN:

KZ 260 - Werbungskosten
Betrag: 1.500,00 EUR

Datum: {date(tax_year, 12, 31).strftime('%d.%m.%Y')}
Unterschrift: {taxpayer_name}
"""
    
    @staticmethod
    def _generate_e1_fuzzy_match(
        tax_year: int, taxpayer_name: str, steuernummer: str
    ) -> str:
        """E1 form with fuzzy property address match (full street name vs abbreviated)"""
        return f"""
EINKOMMENSTEUERERKLÄRUNG {tax_year}
E1 Formular

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

KZ 245 - Einkünfte aus nichtselbständiger Arbeit
Betrag: 52.000,00 EUR

KZ 350 - Einkünfte aus Vermietung und Verpachtung
Betrag: 16.800,00 EUR

Vermietungsdetails:
Objekt: Mariahilfer Straße 45, 1060 Wien
Monatliche Miete: 1.400,00 EUR
Jahresmiete: 16.800,00 EUR

WERBUNGSKOSTEN:

KZ 260 - Werbungskosten
Betrag: 2.000,00 EUR

Datum: {date(tax_year, 12, 31).strftime('%d.%m.%Y')}
Unterschrift: {taxpayer_name}
"""
    
    @staticmethod
    def _generate_e1_no_match(
        tax_year: int, taxpayer_name: str, steuernummer: str
    ) -> str:
        """E1 form with property address that doesn't match any registered property"""
        return f"""
EINKOMMENSTEUERERKLÄRUNG {tax_year}
E1 Formular

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

KZ 245 - Einkünfte aus nichtselbständiger Arbeit
Betrag: 48.000,00 EUR

KZ 350 - Einkünfte aus Vermietung und Verpachtung
Betrag: 18.000,00 EUR

Vermietungsdetails:
Objekt: Linzer Straße 78, 5020 Salzburg
Monatliche Miete: 1.500,00 EUR
Jahresmiete: 18.000,00 EUR

WERBUNGSKOSTEN:

KZ 260 - Werbungskosten
Betrag: 1.800,00 EUR

Datum: {date(tax_year, 12, 31).strftime('%d.%m.%Y')}
Unterschrift: {taxpayer_name}
"""
    
    @staticmethod
    def _generate_e1_multiple(
        tax_year: int, taxpayer_name: str, steuernummer: str
    ) -> str:
        """E1 form with multiple rental properties"""
        return f"""
EINKOMMENSTEUERERKLÄRUNG {tax_year}
E1 Formular

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

KZ 245 - Einkünfte aus nichtselbständiger Arbeit
Betrag: 55.000,00 EUR

KZ 350 - Einkünfte aus Vermietung und Verpachtung
Betrag: 28.800,00 EUR

Vermietungsdetails:
Objekt 1: Hauptstraße 123, 1010 Wien
Monatliche Miete: 1.200,00 EUR
Jahresmiete: 14.400,00 EUR

Objekt 2: Mariahilfer Straße 45, 1060 Wien
Monatliche Miete: 1.200,00 EUR
Jahresmiete: 14.400,00 EUR

WERBUNGSKOSTEN:

KZ 260 - Werbungskosten
Betrag: 2.500,00 EUR

Datum: {date(tax_year, 12, 31).strftime('%d.%m.%Y')}
Unterschrift: {taxpayer_name}
"""
    
    @staticmethod
    def _generate_e1_no_address(
        tax_year: int, taxpayer_name: str, steuernummer: str
    ) -> str:
        """E1 form with rental income but no property address details"""
        return f"""
EINKOMMENSTEUERERKLÄRUNG {tax_year}
E1 Formular

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

KZ 245 - Einkünfte aus nichtselbständiger Arbeit
Betrag: 50.000,00 EUR

KZ 350 - Einkünfte aus Vermietung und Verpachtung
Betrag: 15.600,00 EUR

WERBUNGSKOSTEN:

KZ 260 - Werbungskosten
Betrag: 1.700,00 EUR

Datum: {date(tax_year, 12, 31).strftime('%d.%m.%Y')}
Unterschrift: {taxpayer_name}
"""
    
    @staticmethod
    def generate_bescheid_text(
        scenario: str,
        tax_year: int = 2025,
        taxpayer_name: str = "Max Mustermann",
        steuernummer: str = "12-345/6789",
        finanzamt: str = "Wien 1/23"
    ) -> str:
        """
        Generate Bescheid OCR text for different test scenarios.
        
        Scenarios:
        - "exact_match": Single property with exact address match
        - "fuzzy_match": Single property with fuzzy address match
        - "no_match": Property not registered
        - "multiple": Multiple properties
        - "no_address": Rental income without property address
        """
        
        if scenario == "exact_match":
            return E1BescheidTestDataGenerator._generate_bescheid_exact_match(
                tax_year, taxpayer_name, steuernummer, finanzamt
            )
        elif scenario == "fuzzy_match":
            return E1BescheidTestDataGenerator._generate_bescheid_fuzzy_match(
                tax_year, taxpayer_name, steuernummer, finanzamt
            )
        elif scenario == "no_match":
            return E1BescheidTestDataGenerator._generate_bescheid_no_match(
                tax_year, taxpayer_name, steuernummer, finanzamt
            )
        elif scenario == "multiple":
            return E1BescheidTestDataGenerator._generate_bescheid_multiple(
                tax_year, taxpayer_name, steuernummer, finanzamt
            )
        elif scenario == "no_address":
            return E1BescheidTestDataGenerator._generate_bescheid_no_address(
                tax_year, taxpayer_name, steuernummer, finanzamt
            )
        else:
            raise ValueError(f"Unknown scenario: {scenario}")
    
    @staticmethod
    def _generate_bescheid_exact_match(
        tax_year: int, taxpayer_name: str, steuernummer: str, finanzamt: str
    ) -> str:
        """Bescheid with exact property address match"""
        return f"""
REPUBLIK ÖSTERREICH
EINKOMMENSTEUERBESCHEID {tax_year}

Finanzamt: {finanzamt}
Bescheiddatum: {date(tax_year + 1, 6, 15).strftime('%d.%m.%Y')}

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}
Adresse: Teststraße 1, 1010 Wien

EINKÜNFTE:

Einkünfte aus nichtselbständiger Arbeit: 45.000,00 EUR
Einkünfte aus Vermietung und Verpachtung: 14.400,00 EUR
  - Hauptstraße 123, 1010 Wien: 14.400,00 EUR

Gesamtbetrag der Einkünfte: 59.400,00 EUR

ABZÜGE:

Werbungskosten: 1.500,00 EUR
Sonderausgaben: 500,00 EUR

Einkommen: 57.400,00 EUR

STEUERBERECHNUNG:

Einkommensteuer: 8.250,00 EUR
Lohnsteuer (bereits bezahlt): 9.450,00 EUR

FESTSETZUNG:

Festgesetzte Einkommensteuer: 8.250,00 EUR
Abgabengutschrift: 1.200,00 EUR

Zahlungsfrist: {date(tax_year + 1, 8, 31).strftime('%d.%m.%Y')}

Finanzamt {finanzamt}
"""
    
    @staticmethod
    def _generate_bescheid_fuzzy_match(
        tax_year: int, taxpayer_name: str, steuernummer: str, finanzamt: str
    ) -> str:
        """Bescheid with fuzzy property address match"""
        return f"""
REPUBLIK ÖSTERREICH
EINKOMMENSTEUERBESCHEID {tax_year}

Finanzamt: {finanzamt}
Bescheiddatum: {date(tax_year + 1, 6, 20).strftime('%d.%m.%Y')}

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

Einkünfte aus nichtselbständiger Arbeit: 52.000,00 EUR
Einkünfte aus Vermietung und Verpachtung: 16.800,00 EUR
  - Mariahilfer Straße 45, 1060 Wien: 16.800,00 EUR

Gesamtbetrag der Einkünfte: 68.800,00 EUR

ABZÜGE:

Werbungskosten: 2.000,00 EUR
Sonderausgaben: 600,00 EUR

Einkommen: 66.200,00 EUR

STEUERBERECHNUNG:

Einkommensteuer: 11.500,00 EUR
Lohnsteuer (bereits bezahlt): 12.200,00 EUR

FESTSETZUNG:

Festgesetzte Einkommensteuer: 11.500,00 EUR
Abgabengutschrift: 700,00 EUR

Finanzamt {finanzamt}
"""
    
    @staticmethod
    def _generate_bescheid_no_match(
        tax_year: int, taxpayer_name: str, steuernummer: str, finanzamt: str
    ) -> str:
        """Bescheid with property address that doesn't match"""
        return f"""
REPUBLIK ÖSTERREICH
EINKOMMENSTEUERBESCHEID {tax_year}

Finanzamt: Salzburg
Bescheiddatum: {date(tax_year + 1, 6, 25).strftime('%d.%m.%Y')}

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

Einkünfte aus nichtselbständiger Arbeit: 48.000,00 EUR
Einkünfte aus Vermietung und Verpachtung: 18.000,00 EUR
  - Linzer Straße 78, 5020 Salzburg: 18.000,00 EUR

Gesamtbetrag der Einkünfte: 66.000,00 EUR

ABZÜGE:

Werbungskosten: 1.800,00 EUR
Sonderausgaben: 550,00 EUR

Einkommen: 63.650,00 EUR

STEUERBERECHNUNG:

Einkommensteuer: 10.800,00 EUR
Lohnsteuer (bereits bezahlt): 11.500,00 EUR

FESTSETZUNG:

Festgesetzte Einkommensteuer: 10.800,00 EUR
Abgabengutschrift: 700,00 EUR

Finanzamt Salzburg
"""
    
    @staticmethod
    def _generate_bescheid_multiple(
        tax_year: int, taxpayer_name: str, steuernummer: str, finanzamt: str
    ) -> str:
        """Bescheid with multiple rental properties"""
        return f"""
REPUBLIK ÖSTERREICH
EINKOMMENSTEUERBESCHEID {tax_year}

Finanzamt: {finanzamt}
Bescheiddatum: {date(tax_year + 1, 7, 1).strftime('%d.%m.%Y')}

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

Einkünfte aus nichtselbständiger Arbeit: 55.000,00 EUR
Einkünfte aus Vermietung und Verpachtung: 28.800,00 EUR
  - Hauptstraße 123, 1010 Wien: 14.400,00 EUR
  - Mariahilfer Str. 45, 1060 Wien: 14.400,00 EUR

Gesamtbetrag der Einkünfte: 83.800,00 EUR

ABZÜGE:

Werbungskosten: 2.500,00 EUR
Sonderausgaben: 700,00 EUR

Einkommen: 80.600,00 EUR

STEUERBERECHNUNG:

Einkommensteuer: 16.200,00 EUR
Lohnsteuer (bereits bezahlt): 15.800,00 EUR

FESTSETZUNG:

Festgesetzte Einkommensteuer: 16.200,00 EUR
Abgabennachforderung: 400,00 EUR

Zahlungsfrist: {date(tax_year + 1, 9, 30).strftime('%d.%m.%Y')}

Finanzamt {finanzamt}
"""
    
    @staticmethod
    def _generate_bescheid_no_address(
        tax_year: int, taxpayer_name: str, steuernummer: str, finanzamt: str
    ) -> str:
        """Bescheid with rental income but no property address"""
        return f"""
REPUBLIK ÖSTERREICH
EINKOMMENSTEUERBESCHEID {tax_year}

Finanzamt: {finanzamt}
Bescheiddatum: {date(tax_year + 1, 6, 18).strftime('%d.%m.%Y')}

Steuerpflichtige/r: {taxpayer_name}
Steuernummer: {steuernummer}

EINKÜNFTE:

Einkünfte aus nichtselbständiger Arbeit: 50.000,00 EUR
Einkünfte aus Vermietung und Verpachtung: 15.600,00 EUR

Gesamtbetrag der Einkünfte: 65.600,00 EUR

ABZÜGE:

Werbungskosten: 1.700,00 EUR
Sonderausgaben: 550,00 EUR

Einkommen: 63.350,00 EUR

STEUERBERECHNUNG:

Einkommensteuer: 10.500,00 EUR
Lohnsteuer (bereits bezahlt): 11.200,00 EUR

FESTSETZUNG:

Festgesetzte Einkommensteuer: 10.500,00 EUR
Abgabengutschrift: 700,00 EUR

Finanzamt {finanzamt}
"""
    
    @staticmethod
    def get_test_scenarios() -> List[Dict[str, str]]:
        """Get list of all test scenarios with descriptions"""
        return [
            {
                "id": "exact_match",
                "name": "Exact Address Match",
                "description": "Property address matches exactly - should auto-link with high confidence",
                "expected_confidence": ">0.9",
                "expected_action": "auto_link"
            },
            {
                "id": "fuzzy_match",
                "name": "Fuzzy Address Match",
                "description": "Property address similar but not exact (Str. vs Straße) - should suggest with medium confidence",
                "expected_confidence": "0.7-0.9",
                "expected_action": "suggest"
            },
            {
                "id": "no_match",
                "name": "No Match - Create New",
                "description": "Property not registered - should prompt to create new property",
                "expected_confidence": "0.0",
                "expected_action": "create_new"
            },
            {
                "id": "multiple",
                "name": "Multiple Properties",
                "description": "Multiple rental properties in one document - should handle each separately",
                "expected_confidence": "varies",
                "expected_action": "varies"
            },
            {
                "id": "no_address",
                "name": "No Address Details",
                "description": "Rental income without property address - should prompt manual selection",
                "expected_confidence": "0.0",
                "expected_action": "manual_select"
            },
        ]


def generate_uat_test_files(output_dir: str = "backend/tests/uat/test_documents/"):
    """
    Generate all test E1 and Bescheid text files for UAT.
    
    Creates text files that can be used to simulate OCR output.
    """
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    scenarios = E1BescheidTestDataGenerator.get_test_scenarios()
    
    for scenario in scenarios:
        scenario_id = scenario["id"]
        
        # Generate E1 form
        e1_text = E1BescheidTestDataGenerator.generate_e1_form_text(scenario_id)
        e1_filename = f"{output_dir}e1_form_{scenario_id}.txt"
        with open(e1_filename, "w", encoding="utf-8") as f:
            f.write(e1_text)
        print(f"Created: {e1_filename}")
        
        # Generate Bescheid
        bescheid_text = E1BescheidTestDataGenerator.generate_bescheid_text(scenario_id)
        bescheid_filename = f"{output_dir}bescheid_{scenario_id}.txt"
        with open(bescheid_filename, "w", encoding="utf-8") as f:
            f.write(bescheid_text)
        print(f"Created: {bescheid_filename}")
    
    print(f"\nGenerated {len(scenarios) * 2} test files in {output_dir}")


if __name__ == "__main__":
    # Generate test files when run directly
    generate_uat_test_files()
    
    # Print test scenarios
    print("\n" + "="*80)
    print("TEST SCENARIOS")
    print("="*80)
    
    for scenario in E1BescheidTestDataGenerator.get_test_scenarios():
        print(f"\n{scenario['name']} ({scenario['id']})")
        print(f"  Description: {scenario['description']}")
        print(f"  Expected Confidence: {scenario['expected_confidence']}")
        print(f"  Expected Action: {scenario['expected_action']}")
