"""Test with the actual full text from the API response"""
import sys
sys.path.insert(0, 'backend')

from app.services.e1_form_extractor import E1FormExtractor

# The actual raw_text from your API response
full_text = """Jahresabschluss 2020
Fenghong ZHANG

Seite
Einkommensteuererklärung
3
Beilage zur E1 (VuV)
11
Arbeitnehmerveranlagung
14
Gesamtbelastung
18
Einkommensteuerberechnung (E1)
19
Einkommensteuerberechnung (L1)
21

BITTE DIESES GRAUE FELD  
NICHT BESCHRIFTEN
E 1-EDV-2020 printcom electronic forms - vom BMF genehmigt
E 1, Seite 1, Version vom 24.03.2021
Einkommensteuererklärung für 2020 sowie"""

extractor = E1FormExtractor()
data = extractor.extract(full_text)

print("=== Tax Year Extraction Test ===")
print(f"Tax Year: {data.tax_year}")
print(f"Expected: 2020 (from 'Einkommensteuererklärung für 2020')")
print()

# But the file name says 2022!
print("Note: The PDF filename is 'Einkommensteuererklärung für 2022.pdf'")
print("This suggests the PDF content might be from 2020 but the file was renamed for 2022")
