"""
Test data generator for UAT testing.

Creates realistic test data for landlord users to test property management features.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict
import random


class UATTestDataGenerator:
    """Generate realistic test data for UAT"""
    
    AUSTRIAN_ADDRESSES = [
        {
            "street": "Hauptstraße 123",
            "city": "Wien",
            "postal_code": "1010",
        },
        {
            "street": "Mariahilfer Straße 45",
            "city": "Wien",
            "postal_code": "1060",
        },
        {
            "street": "Linzer Straße 78",
            "city": "Salzburg",
            "postal_code": "5020",
        },
        {
            "street": "Grazer Straße 12",
            "city": "Graz",
            "postal_code": "8010",
        },
        {
            "street": "Innsbrucker Straße 56",
            "city": "Innsbruck",
            "postal_code": "6020",
        },
    ]
    
    @staticmethod
    def generate_property_data(
        purchase_year: int = 2020,
        property_type: str = "rental",
    ) -> Dict:
        """Generate realistic property data"""
        address = random.choice(UATTestDataGenerator.AUSTRIAN_ADDRESSES)
        
        purchase_price = Decimal(random.randint(200000, 500000))
        building_value = purchase_price * Decimal("0.80")
        construction_year = random.randint(1950, 2010)
        
        # Determine depreciation rate based on construction year
        depreciation_rate = Decimal("0.015") if construction_year < 1915 else Decimal("0.020")
        
        return {
            "property_type": property_type,
            "rental_percentage": 100.0 if property_type == "rental" else 50.0,
            "street": address["street"],
            "city": address["city"],
            "postal_code": address["postal_code"],
            "purchase_date": date(purchase_year, random.randint(1, 12), 1),
            "purchase_price": float(purchase_price),
            "building_value": float(building_value),
            "construction_year": construction_year,
            "depreciation_rate": float(depreciation_rate),
        }
    
    @staticmethod
    def generate_rental_income_transactions(
        property_id: str,
        year: int = 2026,
        monthly_rent: Decimal = Decimal("1200"),
    ) -> List[Dict]:
        """Generate monthly rental income transactions"""
        transactions = []
        
        for month in range(1, 13):
            transactions.append({
                "property_id": property_id,
                "type": "income",
                "amount": float(monthly_rent),
                "transaction_date": date(year, month, 1),
                "description": f"Miete {month}/{year}",
                "income_category": "rental_income",
                "is_deductible": False,
            })
        
        return transactions
    
    @staticmethod
    def generate_property_expense_transactions(
        property_id: str,
        year: int = 2026,
    ) -> List[Dict]:
        """Generate realistic property expense transactions"""
        transactions = []
        
        # Property insurance (annual)
        transactions.append({
            "property_id": property_id,
            "type": "expense",
            "amount": float(Decimal(random.randint(800, 1500))),
            "transaction_date": date(year, 1, 15),
            "description": "Gebäudeversicherung",
            "expense_category": "property_insurance",
            "is_deductible": True,
        })
        
        # Property tax (quarterly)
        property_tax_quarterly = Decimal(random.randint(200, 400))
        for quarter in [3, 6, 9, 12]:
            transactions.append({
                "property_id": property_id,
                "type": "expense",
                "amount": float(property_tax_quarterly),
                "transaction_date": date(year, quarter, 15),
                "description": "Grundsteuer",
                "expense_category": "property_tax",
                "is_deductible": True,
            })
        
        # Maintenance and repairs (random throughout year)
        maintenance_events = random.randint(2, 5)
        for _ in range(maintenance_events):
            month = random.randint(1, 12)
            transactions.append({
                "property_id": property_id,
                "type": "expense",
                "amount": float(Decimal(random.randint(200, 2000))),
                "transaction_date": date(year, month, random.randint(1, 28)),
                "description": random.choice([
                    "Reparatur Heizung",
                    "Malerarbeiten",
                    "Sanitär Reparatur",
                    "Elektrik Wartung",
                    "Dachreparatur",
                ]),
                "expense_category": "maintenance_repairs",
                "is_deductible": True,
            })
        
        # Property management fees (monthly)
        management_fee = Decimal(random.randint(80, 150))
        for month in range(1, 13):
            transactions.append({
                "property_id": property_id,
                "type": "expense",
                "amount": float(management_fee),
                "transaction_date": date(year, month, 1),
                "description": "Hausverwaltung",
                "expense_category": "property_management_fees",
                "is_deductible": True,
            })
        
        # Utilities (if landlord pays)
        if random.choice([True, False]):
            utility_cost = Decimal(random.randint(50, 150))
            for month in range(1, 13):
                transactions.append({
                    "property_id": property_id,
                    "type": "expense",
                    "amount": float(utility_cost),
                    "transaction_date": date(year, month, 15),
                    "description": "Betriebskosten",
                    "expense_category": "utilities",
                    "is_deductible": True,
                })
        
        return transactions
    
    @staticmethod
    def generate_test_scenario_data(scenario: str) -> Dict:
        """Generate data specific to a test scenario"""
        
        if scenario == "property_registration":
            return {
                "property": UATTestDataGenerator.generate_property_data(
                    purchase_year=2020,
                    property_type="rental"
                )
            }
        
        elif scenario == "historical_backfill":
            return {
                "property": UATTestDataGenerator.generate_property_data(
                    purchase_year=2018,  # Old property for backfill
                    property_type="rental"
                )
            }
        
        elif scenario == "transaction_linking":
            property_data = UATTestDataGenerator.generate_property_data()
            return {
                "property": property_data,
                "transactions": (
                    UATTestDataGenerator.generate_rental_income_transactions(
                        property_id="placeholder",
                        monthly_rent=Decimal("1200")
                    ) +
                    UATTestDataGenerator.generate_property_expense_transactions(
                        property_id="placeholder"
                    )
                )
            }
        
        elif scenario == "multi_property":
            return {
                "properties": [
                    UATTestDataGenerator.generate_property_data(
                        purchase_year=year,
                        property_type="rental"
                    )
                    for year in [2018, 2020, 2022]
                ]
            }
        
        elif scenario == "mixed_use_property":
            return {
                "property": UATTestDataGenerator.generate_property_data(
                    purchase_year=2020,
                    property_type="mixed_use"
                )
            }
        
        else:
            return {
                "property": UATTestDataGenerator.generate_property_data()
            }


def create_uat_test_accounts(db_session, count: int = 10) -> List[Dict]:
    """
    Create test user accounts for UAT participants.
    
    Returns list of created accounts with credentials.
    """
    from app.models.user import User
    from app.core.security import get_password_hash
    
    test_accounts = []
    
    for i in range(1, count + 1):
        email = f"uat-landlord-{i:02d}@taxja.at"
        password = f"UAT2026Test{i:02d}!"
        
        # Check if user already exists
        existing_user = db_session.query(User).filter(User.email == email).first()
        if existing_user:
            continue
        
        user = User(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=f"UAT Test Landlord {i}",
            user_type="landlord",
            is_active=True,
            is_verified=True,
        )
        
        db_session.add(user)
        
        test_accounts.append({
            "email": email,
            "password": password,
            "user_id": None,  # Will be set after commit
        })
    
    db_session.commit()
    
    # Update user IDs
    for account in test_accounts:
        user = db_session.query(User).filter(User.email == account["email"]).first()
        if user:
            account["user_id"] = user.id
    
    return test_accounts


def generate_uat_welcome_email(account: Dict) -> str:
    """Generate welcome email content for UAT participant"""
    
    return f"""
Willkommen zum Taxja Property Management UAT!

Vielen Dank, dass Sie an unserem User Acceptance Testing teilnehmen.

Ihre Test-Zugangsdaten:
Email: {account['email']}
Passwort: {account['password']}

Staging-URL: https://staging.taxja.at

Bitte führen Sie die folgenden Test-Szenarien durch:
1. Immobilie registrieren
2. Historische AfA nachbuchen
3. Transaktionen verknüpfen
4. Immobilien-Metriken prüfen
5. Berichte generieren
6. Mehrere Immobilien verwalten
7. Immobilie archivieren

Feedback:
Bitte nutzen Sie das Feedback-Widget (💬 Button unten rechts) um Ihre Erfahrungen zu teilen.

Bei Fragen: uat-support@taxja.at

Vielen Dank für Ihre Unterstützung!
Das Taxja Team
"""
