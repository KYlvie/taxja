"""
Demo data generator for Taxja

Creates sample users with different profiles and realistic Austrian tax scenarios.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import List
import random

from sqlalchemy.orm import Session
from app.models.user import User, UserType
from app.models.transaction import Transaction, TransactionType, IncomeCategory, ExpenseCategory
from app.models.document import Document, DocumentType
from app.models.tax_configuration import TaxConfiguration
from app.models.property import Property, PropertyType, PropertyStatus
from app.core.security import get_password_hash


class DemoDataGenerator:
    """Generate realistic demo data for different user profiles"""

    def __init__(self, db: Session):
        self.db = db

    def create_demo_users(self) -> List[User]:
        """Create demo users with different profiles"""
        users = []

        # 1. Employee (Arbeitnehmer)
        employee = User(
            email="employee@demo.taxja.at",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Maria Müller",
            user_type=UserType.EMPLOYEE,
            tax_number="12-345/6789",
            address="Hauptstraße 1, 1010 Wien",
            family_info={
                "num_children": 2,
                "is_single_parent": False
            },
            commuting_info={
                "distance_km": 35,
                "public_transport_available": True
            }
        )
        users.append(employee)

        # 2. Self-Employed (Selbständiger)
        self_employed = User(
            email="selfemployed@demo.taxja.at",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Thomas Weber",
            user_type=UserType.SELF_EMPLOYED,
            tax_number="98-765/4321",
            vat_number="ATU12345678",
            address="Mariahilfer Straße 50, 1070 Wien",
            family_info={
                "num_children": 0,
                "is_single_parent": False
            }
        )
        users.append(self_employed)

        # 3. Landlord (Vermieter)
        landlord = User(
            email="landlord@demo.taxja.at",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Anna Schmidt",
            user_type=UserType.LANDLORD,
            tax_number="55-555/5555",
            address="Ringstraße 10, 1010 Wien",
            family_info={
                "num_children": 1,
                "is_single_parent": True
            }
        )
        users.append(landlord)

        # 4. Mixed Income (Employee + Landlord)
        mixed = User(
            email="mixed@demo.taxja.at",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Peter Gruber",
            user_type=UserType.EMPLOYEE,  # Primary type
            tax_number="77-777/7777",
            address="Praterstraße 25, 1020 Wien",
            family_info={
                "num_children": 3,
                "is_single_parent": False
            },
            commuting_info={
                "distance_km": 45,
                "public_transport_available": False
            }
        )
        users.append(mixed)

        self.db.add_all(users)
        self.db.commit()

        for user in users:
            self.db.refresh(user)

        return users

    def create_employee_transactions(self, user: User, year: int = 2026):
        """Create realistic transactions for an employee"""
        transactions = []
        start_date = datetime(year, 1, 1)

        # Monthly salary (January - February)
        for month in range(1, 3):
            date = datetime(year, month, 25)
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.INCOME,
                amount=Decimal("3500.00"),
                date=date,
                description=f"Gehalt {date.strftime('%B %Y')}",
                category=IncomeCategory.EMPLOYMENT,
                is_deductible=False
            ))

        # Commuting expenses (public transport card)
        for month in range(1, 3):
            date = datetime(year, month, 1)
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("51.00"),
                date=date,
                description="Wiener Linien Monatskarte",
                category=ExpenseCategory.COMMUTING,
                is_deductible=True
            ))

        # Work equipment
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("450.00"),
            date=datetime(year, 1, 15),
            description="Laptop für Homeoffice",
            category=ExpenseCategory.EQUIPMENT,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("75.00")
        ))

        # Professional literature
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("89.90"),
            date=datetime(year, 2, 5),
            description="Fachbücher IT",
            category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
            vat_rate=Decimal("0.10"),
            vat_amount=Decimal("8.17")
        ))

        self.db.add_all(transactions)
        self.db.commit()

    def create_self_employed_transactions(self, user: User, year: int = 2026):
        """Create realistic transactions for self-employed"""
        transactions = []

        # Client invoices (income)
        clients = ["Firma ABC GmbH", "XYZ Solutions", "Tech Startup Wien"]
        for month in range(1, 3):
            for i, client in enumerate(clients):
                date = datetime(year, month, 10 + i * 5)
                amount = Decimal(random.randint(1500, 4500))
                vat = amount * Decimal("0.20")
                transactions.append(Transaction(
                    user_id=user.id,
                    type=TransactionType.INCOME,
                    amount=amount,
                    date=date,
                    description=f"Rechnung {client}",
                    category=IncomeCategory.SELF_EMPLOYMENT,
                    is_deductible=False,
                    vat_rate=Decimal("0.20"),
                    vat_amount=vat
                ))

        # Office supplies
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("125.50"),
            date=datetime(year, 1, 8),
            description="Büromaterial Staples",
            category=ExpenseCategory.OFFICE_SUPPLIES,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("20.92")
        ))

        # Software subscriptions
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("59.99"),
            date=datetime(year, 1, 1),
            description="Adobe Creative Cloud Abo",
            category=ExpenseCategory.EQUIPMENT,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("10.00")
        ))

        # Marketing expenses
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("350.00"),
            date=datetime(year, 1, 20),
            description="Google Ads Kampagne",
            category=ExpenseCategory.MARKETING,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("58.33")
        ))

        # Professional services (accountant)
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("180.00"),
            date=datetime(year, 2, 1),
            description="Steuerberater Beratung",
            category=ExpenseCategory.PROFESSIONAL_SERVICES,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("30.00")
        ))

        # Business travel
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("245.00"),
            date=datetime(year, 2, 15),
            description="Geschäftsreise Salzburg (Hotel + Bahn)",
            category=ExpenseCategory.TRAVEL,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("40.83")
        ))

        # Equipment
        transactions.append(Transaction(
            user_id=user.id,
            type=TransactionType.EXPENSE,
            amount=Decimal("1200.00"),
            date=datetime(year, 1, 25),
            description="MacBook Pro",
            category=ExpenseCategory.EQUIPMENT,
            is_deductible=True,
            vat_rate=Decimal("0.20"),
            vat_amount=Decimal("200.00")
        ))

        self.db.add_all(transactions)
        self.db.commit()

    def create_landlord_transactions(self, user: User, properties: List[Property] = None, year: int = 2026):
        """Create realistic transactions for a landlord"""
        transactions = []

        # If no properties provided, create transactions without property links
        if not properties:
            # Monthly rental income (unlinked)
            for month in range(1, 3):
                date = datetime(year, month, 1)
                transactions.append(Transaction(
                    user_id=user.id,
                    type=TransactionType.INCOME,
                    amount=Decimal("1200.00"),
                    date=date,
                    description=f"Mieteinnahme Wohnung Praterstraße {date.strftime('%B')}",
                    category=IncomeCategory.RENTAL,
                    is_deductible=False,
                    vat_rate=Decimal("0.10"),  # Residential rental
                    vat_amount=Decimal("109.09")
                ))
        else:
            # Link rental income to properties
            # Property 1: Praterstraße 45 - €1200/month
            property1 = next((p for p in properties if "Praterstraße 45" in p.address), None)
            if property1:
                for month in range(1, 3):
                    date = datetime(year, month, 1)
                    transactions.append(Transaction(
                        user_id=user.id,
                        property_id=property1.id,
                        type=TransactionType.INCOME,
                        amount=Decimal("1200.00"),
                        date=date,
                        description=f"Mieteinnahme {property1.address} {date.strftime('%B')}",
                        category=IncomeCategory.RENTAL,
                        is_deductible=False,
                        vat_rate=Decimal("0.10"),
                        vat_amount=Decimal("109.09")
                    ))

            # Property 2: Mariahilfer Straße 88 - €900/month (mixed-use, 50% rental)
            property2 = next((p for p in properties if "Mariahilfer Straße 88" in p.address), None)
            if property2:
                for month in range(1, 3):
                    date = datetime(year, month, 1)
                    transactions.append(Transaction(
                        user_id=user.id,
                        property_id=property2.id,
                        type=TransactionType.INCOME,
                        amount=Decimal("900.00"),
                        date=date,
                        description=f"Mieteinnahme {property2.address} {date.strftime('%B')}",
                        category=IncomeCategory.RENTAL,
                        is_deductible=False,
                        vat_rate=Decimal("0.10"),
                        vat_amount=Decimal("81.82")
                    ))

            # Property 4: Wollzeile 15 - €1500/month (newer property, higher rent)
            property4 = next((p for p in properties if "Wollzeile 15" in p.address), None)
            if property4:
                for month in range(1, 3):
                    date = datetime(year, month, 1)
                    transactions.append(Transaction(
                        user_id=user.id,
                        property_id=property4.id,
                        type=TransactionType.INCOME,
                        amount=Decimal("1500.00"),
                        date=date,
                        description=f"Mieteinnahme {property4.address} {date.strftime('%B')}",
                        category=IncomeCategory.RENTAL,
                        is_deductible=False,
                        vat_rate=Decimal("0.10"),
                        vat_amount=Decimal("136.36")
                    ))

        # Property maintenance - link to Property 1
        if properties and len(properties) > 0:
            property1 = next((p for p in properties if "Praterstraße 45" in p.address), None)
            transactions.append(Transaction(
                user_id=user.id,
                property_id=property1.id if property1 else None,
                type=TransactionType.EXPENSE,
                amount=Decimal("450.00"),
                date=datetime(year, 1, 15),
                description="Reparatur Heizung",
                category=ExpenseCategory.MAINTENANCE,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("75.00")
            ))
        else:
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("450.00"),
                date=datetime(year, 1, 15),
                description="Reparatur Heizung",
                category=ExpenseCategory.MAINTENANCE,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("75.00")
            ))

        # Property management - link to Property 2
        if properties and len(properties) > 1:
            property2 = next((p for p in properties if "Mariahilfer Straße 88" in p.address), None)
            transactions.append(Transaction(
                user_id=user.id,
                property_id=property2.id if property2 else None,
                type=TransactionType.EXPENSE,
                amount=Decimal("120.00"),
                date=datetime(year, 1, 1),
                description="Hausverwaltung Gebühr Q1",
                category=ExpenseCategory.PROFESSIONAL_SERVICES,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("20.00")
            ))
        else:
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("120.00"),
                date=datetime(year, 1, 1),
                description="Hausverwaltung Gebühr Q1",
                category=ExpenseCategory.PROFESSIONAL_SERVICES,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("20.00")
            ))

        # Property insurance - link to Property 4
        if properties and len(properties) > 3:
            property4 = next((p for p in properties if "Wollzeile 15" in p.address), None)
            transactions.append(Transaction(
                user_id=user.id,
                property_id=property4.id if property4 else None,
                type=TransactionType.EXPENSE,
                amount=Decimal("380.00"),
                date=datetime(year, 1, 10),
                description="Gebäudeversicherung Jahresprämie",
                category=ExpenseCategory.INSURANCE,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("63.33")
            ))
        else:
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("380.00"),
                date=datetime(year, 1, 10),
                description="Gebäudeversicherung Jahresprämie",
                category=ExpenseCategory.INSURANCE,
                is_deductible=True,
                vat_rate=Decimal("0.20"),
                vat_amount=Decimal("63.33")
            ))

        # Loan interest - link to Property 1
        if properties and len(properties) > 0:
            property1 = next((p for p in properties if "Praterstraße 45" in p.address), None)
            transactions.append(Transaction(
                user_id=user.id,
                property_id=property1.id if property1 else None,
                type=TransactionType.EXPENSE,
                amount=Decimal("650.00"),
                date=datetime(year, 1, 5),
                description="Hypothekenzinsen Januar",
                category=ExpenseCategory.LOAN_INTEREST,
                is_deductible=True
            ))

            transactions.append(Transaction(
                user_id=user.id,
                property_id=property1.id if property1 else None,
                type=TransactionType.EXPENSE,
                amount=Decimal("650.00"),
                date=datetime(year, 2, 5),
                description="Hypothekenzinsen Februar",
                category=ExpenseCategory.LOAN_INTEREST,
                is_deductible=True
            ))
        else:
            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("650.00"),
                date=datetime(year, 1, 5),
                description="Hypothekenzinsen Januar",
                category=ExpenseCategory.LOAN_INTEREST,
                is_deductible=True
            ))

            transactions.append(Transaction(
                user_id=user.id,
                type=TransactionType.EXPENSE,
                amount=Decimal("650.00"),
                date=datetime(year, 2, 5),
                description="Hypothekenzinsen Februar",
                category=ExpenseCategory.LOAN_INTEREST,
                is_deductible=True
            ))

        self.db.add_all(transactions)
        self.db.commit()

    def create_demo_documents(self, user: User):
        """Create sample documents for a user"""
        documents = []

        # Payslip
        if user.user_type == UserType.EMPLOYEE:
            documents.append(Document(
                user_id=user.id,
                document_type=DocumentType.PAYSLIP,
                file_path=f"demo/documents/user_{user.id}/lohnzettel_jan_2026.pdf",
                ocr_status="completed",
                confidence_score=Decimal("0.95"),
                extracted_data={
                    "gross_income": "3500.00",
                    "net_income": "2450.00",
                    "withheld_tax": "650.00",
                    "social_insurance": "400.00",
                    "employer": "Demo Firma GmbH"
                },
                raw_text="LOHNZETTEL\nBrutto: €3,500.00\nNetto: €2,450.00..."
            ))

        # Receipt
        documents.append(Document(
            user_id=user.id,
            document_type=DocumentType.RECEIPT,
            file_path=f"demo/documents/user_{user.id}/receipt_billa_001.jpg",
            ocr_status="completed",
            confidence_score=Decimal("0.88"),
            extracted_data={
                "date": "2026-01-15",
                "amount": "45.80",
                "merchant": "BILLA AG",
                "items": [
                    {"name": "Milch", "amount": "1.50"},
                    {"name": "Brot", "amount": "2.30"}
                ],
                "vat_amounts": {"20%": "7.63"}
            },
            raw_text="BILLA AG\nDatum: 15.01.2026\nSumme: €45.80..."
        ))

        # Invoice
        if user.user_type in [UserType.SELF_EMPLOYED, UserType.LANDLORD]:
            documents.append(Document(
                user_id=user.id,
                document_type=DocumentType.INVOICE,
                file_path=f"demo/documents/user_{user.id}/invoice_001.pdf",
                ocr_status="completed",
                confidence_score=Decimal("0.92"),
                extracted_data={
                    "invoice_number": "RE-2026-001",
                    "date": "2026-01-20",
                    "amount": "1500.00",
                    "vat_amount": "250.00",
                    "supplier": "Tech Supplies GmbH"
                },
                raw_text="RECHNUNG\nRE-2026-001\nBetrag: €1,500.00..."
            ))

        self.db.add_all(documents)
        self.db.commit()

    def create_demo_properties(self, user: User) -> List[Property]:
        """Create sample properties for landlord users"""
        properties = []

        # Property 1: Rental apartment in Vienna (purchased 2020)
        property1 = Property(
            user_id=user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Praterstraße 45",
            city="Wien",
            postal_code="1020",
            address="Praterstraße 45, 1020 Wien",
            purchase_date=datetime(2020, 6, 15).date(),
            purchase_price=Decimal("350000.00"),
            building_value=Decimal("280000.00"),  # 80% of purchase price
            land_value=Decimal("70000.00"),  # 20% of purchase price
            construction_year=1985,
            depreciation_rate=Decimal("0.0200"),  # 2% for buildings after 1915
            grunderwerbsteuer=Decimal("12250.00"),  # 3.5% property transfer tax
            notary_fees=Decimal("3500.00"),
            registry_fees=Decimal("1225.00"),
            status=PropertyStatus.ACTIVE,
            created_at=datetime(2020, 6, 15),
            updated_at=datetime(2020, 6, 15)
        )
        properties.append(property1)

        # Property 2: Mixed-use property (rental + owner-occupied)
        property2 = Property(
            user_id=user.id,
            property_type=PropertyType.MIXED_USE,
            rental_percentage=Decimal("50.00"),  # 50% rental, 50% personal use
            street="Mariahilfer Straße 88",
            city="Wien",
            postal_code="1070",
            address="Mariahilfer Straße 88, 1070 Wien",
            purchase_date=datetime(2018, 3, 1).date(),
            purchase_price=Decimal("480000.00"),
            building_value=Decimal("384000.00"),  # 80% of purchase price
            land_value=Decimal("96000.00"),  # 20% of purchase price
            construction_year=1910,
            depreciation_rate=Decimal("0.0150"),  # 1.5% for buildings before 1915
            grunderwerbsteuer=Decimal("16800.00"),  # 3.5% property transfer tax
            notary_fees=Decimal("4800.00"),
            registry_fees=Decimal("1680.00"),
            status=PropertyStatus.ACTIVE,
            created_at=datetime(2018, 3, 1),
            updated_at=datetime(2018, 3, 1)
        )
        properties.append(property2)

        # Property 3: Sold property (for historical data demonstration)
        property3 = Property(
            user_id=user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Landstraßer Hauptstraße 120",
            city="Wien",
            postal_code="1030",
            address="Landstraßer Hauptstraße 120, 1030 Wien",
            purchase_date=datetime(2015, 9, 10).date(),
            purchase_price=Decimal("280000.00"),
            building_value=Decimal("224000.00"),  # 80% of purchase price
            land_value=Decimal("56000.00"),  # 20% of purchase price
            construction_year=1995,
            depreciation_rate=Decimal("0.0200"),  # 2% for buildings after 1915
            grunderwerbsteuer=Decimal("9800.00"),  # 3.5% property transfer tax
            notary_fees=Decimal("2800.00"),
            registry_fees=Decimal("980.00"),
            status=PropertyStatus.SOLD,
            sale_date=datetime(2025, 11, 30).date(),
            created_at=datetime(2015, 9, 10),
            updated_at=datetime(2025, 11, 30)
        )
        properties.append(property3)

        # Property 4: Recently purchased property (2023) - for historical depreciation backfill demo
        # This property was purchased 3 years ago and needs historical depreciation for 2023, 2024, 2025
        property4 = Property(
            user_id=user.id,
            property_type=PropertyType.RENTAL,
            rental_percentage=Decimal("100.00"),
            street="Wollzeile 15",
            city="Wien",
            postal_code="1010",
            address="Wollzeile 15, 1010 Wien",
            purchase_date=datetime(2023, 4, 20).date(),  # Purchased in April 2023
            purchase_price=Decimal("420000.00"),
            building_value=Decimal("336000.00"),  # 80% of purchase price
            land_value=Decimal("84000.00"),  # 20% of purchase price
            construction_year=2005,
            depreciation_rate=Decimal("0.0200"),  # 2% for buildings after 1915
            grunderwerbsteuer=Decimal("14700.00"),  # 3.5% property transfer tax
            notary_fees=Decimal("4200.00"),
            registry_fees=Decimal("1470.00"),
            status=PropertyStatus.ACTIVE,
            created_at=datetime(2023, 4, 20),
            updated_at=datetime(2023, 4, 20)
        )
        properties.append(property4)

        self.db.add_all(properties)
        self.db.commit()

        for prop in properties:
            self.db.refresh(prop)

        return properties
    def create_depreciation_transactions(self, user: User, properties: List[Property]):
        """
        Create depreciation (AfA) transactions for demo properties.

        Generates historical depreciation transactions for properties purchased in previous years,
        demonstrating the Austrian tax law depreciation calculation.
        """
        from app.services.afa_calculator import AfACalculator

        afa_calculator = AfACalculator(self.db)
        transactions = []
        current_year = datetime.now().year

        for property in properties:
            # Skip sold properties - only generate up to sale year
            end_year = property.sale_date.year if property.sale_date else current_year

            # Generate depreciation for each year from purchase to current/sale year
            for year in range(property.purchase_date.year, end_year + 1):
                # Calculate annual depreciation for this year
                annual_depreciation = afa_calculator.calculate_annual_depreciation(property, year)

                if annual_depreciation > 0:
                    # Create depreciation transaction dated December 31 of the year
                    transaction = Transaction(
                        user_id=user.id,
                        property_id=property.id,
                        type=TransactionType.EXPENSE,
                        amount=annual_depreciation,
                        date=datetime(year, 12, 31),
                        description=f"AfA {property.address} ({year})",
                        category=ExpenseCategory.DEPRECIATION_AFA,
                        is_deductible=True,
                        is_system_generated=True,
                        import_source="demo_data"
                    )
                    transactions.append(transaction)

        self.db.add_all(transactions)
        self.db.commit()

        print(f"  Created {len(transactions)} depreciation transactions")
        return transactions

    def generate_all_demo_data(self):
        """Generate complete demo dataset"""
        print("Creating demo users...")
        users = self.create_demo_users()

        print("Creating properties...")
        user_properties = {}
        for user in users:
            if user.user_type == UserType.LANDLORD:
                properties = self.create_demo_properties(user)
                user_properties[user.id] = properties
                print(f"  Created {len(properties)} properties for {user.full_name}")

        print("Creating transactions...")
        for user in users:
            if user.user_type == UserType.EMPLOYEE:
                self.create_employee_transactions(user)
            elif user.user_type == UserType.SELF_EMPLOYED:
                self.create_self_employed_transactions(user)
            elif user.user_type == UserType.LANDLORD:
                # Pass properties to link transactions
                properties = user_properties.get(user.id, [])
                self.create_landlord_transactions(user, properties)

        print("Creating depreciation transactions...")
        for user in users:
            if user.user_type == UserType.LANDLORD:
                properties = user_properties.get(user.id, [])
                if properties:
                    self.create_depreciation_transactions(user, properties)

        print("Creating documents...")
        for user in users:
            self.create_demo_documents(user)

        print("Demo data generation complete!")
        print("\nDemo Users:")
        print("=" * 60)
        for user in users:
            print(f"Email: {user.email}")
            print(f"Password: Demo2026!")
            print(f"Type: {user.user_type.value}")
            print(f"Name: {user.full_name}")
            print("-" * 60)


def seed_demo_data(db: Session):
    """Main function to seed demo data"""
    generator = DemoDataGenerator(db)
    generator.generate_all_demo_data()


if __name__ == "__main__":
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        seed_demo_data(db)
    finally:
        db.close()
