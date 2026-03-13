#!/usr/bin/env python3
"""Test E1 form extraction from the 2023 PDF"""
import fitz
from app.services.e1_form_extractor import E1FormExtractor

# Read PDF
pdf_path = "Einkommensteuererklärung für 2023.PDF"
doc = fitz.open(pdf_path)

print(f"PDF Info:")
print(f"  Pages: {len(doc)}")
print(f"  Metadata: {doc.metadata}")
print()

# Extract text from all pages
text_parts = []
for i, page in enumerate(doc):
    page_text = page.get_text()
    text_parts.append(page_text)
    print(f"Page {i+1} text length: {len(page_text)}")

doc.close()

raw_text = "\n".join(text_parts)
print(f"\nTotal text length: {len(raw_text)}")
print(f"\n=== First 2000 characters ===")
print(raw_text[:2000])

# Extract with E1FormExtractor
print("\n" + "="*60)
print("E1 FORM EXTRACTION RESULTS")
print("="*60)

extractor = E1FormExtractor()
data = extractor.extract(raw_text)

print(f"\nBasic Info:")
print(f"  Tax Year: {data.tax_year}")
print(f"  Name: {data.taxpayer_name}")
print(f"  Steuernummer: {data.steuernummer}")
print(f"  Confidence: {data.confidence}")

print(f"\nAll KZ Values ({len(data.all_kz_values)} found):")
for kz, value in sorted(data.all_kz_values.items()):
    print(f"  KZ {kz}: €{value}")

print(f"\nMain Income Fields:")
print(f"  KZ 245 (Employment): {data.kz_245}")
print(f"  KZ 350 (Rental): {data.kz_350}")
print(f"  KZ 260 (Work Expenses): {data.kz_260}")
print(f"  KZ 261 (Commuter): {data.kz_261}")
print(f"  KZ 262 (Commuter Euro): {data.kz_262}")
print(f"  KZ 263 (Telework): {data.kz_263}")
