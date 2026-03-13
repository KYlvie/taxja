"""Test E1 parser with the actual PDF text"""
import sys
sys.path.insert(0, 'backend')

from app.services.e1_form_extractor import E1FormExtractor

# Sample text from the PDF
sample_text = """
Einkommensteuererklärung für 2020

FENGHONG ZHANG

14. Einkünfte aus nichtselbständiger Arbeit
Summe der Einkünfte aus nichtselbständiger Arbeit (muss nicht ausgefüllt werden)
E 1 - Seite 5 
Steuer-Nr.
38.987,70
03 627/7572
38.987,70

17. Einkünfte aus Vermietung und Verpachtung
Summe aus 17.1 bis 17.5
370
E 1 - Seite 6 
Steuer-Nr.
03 627/7572
-18.771,31
-18.771,31
"""

extractor = E1FormExtractor()
data = extractor.extract(sample_text)

print("=== Extraction Results ===")
print(f"Tax Year: {data.tax_year}")
print(f"Taxpayer Name: {data.taxpayer_name}")
print(f"KZ 245 (Employment): {data.kz_245}")
print(f"KZ 370 (Rental): {data.kz_350}")  # Note: 370 in text but should map to 350
print(f"All KZ Values: {data.all_kz_values}")
print(f"Confidence: {data.confidence}")
