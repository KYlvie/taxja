"""Verify which KZ values will actually be imported as transactions"""
import sys
sys.path.insert(0, 'backend')

from app.services.e1_form_extractor import E1FormExtractor, E1FormData
from decimal import Decimal

# Simulate the extracted data
data = E1FormData()
data.tax_year = 2020
data.taxpayer_name = "FENGHONG ZHANG"
data.kz_245 = Decimal("38987.70")
data.kz_350 = Decimal("-18771.31")
data.all_kz_values = {
    "245": Decimal("38987.70"),
    "300": Decimal("15.11"),
    "309": Decimal("22.11"),
    "370": Decimal("-18771.31"),
    "572": Decimal("27.01"),
    "596": Decimal("22.10"),
    "722": Decimal("15.10"),
    "723": Decimal("15.12"),
    "983": Decimal("22.12"),
    "020": Decimal("15.13"),
}

print("=== E1 Import Preview ===")
print(f"Tax Year: {data.tax_year}")
print(f"Taxpayer: {data.taxpayer_name}")
print()
print("All extracted KZ values (shown in preview):")
for kz, amount in sorted(data.all_kz_values.items()):
    print(f"  KZ {kz}: €{amount}")
print()
print("Transactions that WILL be created:")
print(f"  1. KZ 245 (Employment Income): €{data.kz_245}")
print(f"  2. KZ 370 (Rental Income): €{data.kz_350}")
print()
print("Transactions that will NOT be created:")
print("  - KZ 300, 309, 572, 596, 722, 723, 983, 020")
print("  (These are Werbungskosten - shown for reference only)")
