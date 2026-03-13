"""
Diagnose KZ matching between form_data fields and PDF template fields.
Run: python scripts/diagnose_e1_matching.py
"""
import fitz
from pathlib import Path

TEMPLATE_DIR = Path(__file__).parent.parent / "app" / "templates"

# From e1_template_filler.py - the FIELD_TO_KZ mapping (reversed to KZ_TO_FIELD)
FIELD_TO_KZ = {
    "Zahl50": "311", "Zahl62": "321", "Zahl76": "327",
    "Zahl54": "312", "Zahl66": "322", "Zahl80": "328",
    "Zahl61": "310", "Zahl75": "320", "Zahl86a": "330",
    "Zahl104_00": "725", "Zahl104_01": "718", "Zahl104_02": "717",
    "Zahl104_04": "169", "Zahl104_04a": "719", "Zahl104_05": "720",
    "Zahl104_06": "721", "Zahl104_07": "722", "Zahl104_09": "723",
    "Zahl104_10": "724", "Zahl131": "370", "Zahl130_01": "373",
    "Zahl160": "462", "Zahl25": "245", "Zahl181": "449",
}

# KZ numbers that _generate_e1_form actually produces
FORM_DATA_KZS = {
    "245": "Einkuenfte aus nichtselbstaendiger Arbeit",
    "330": "Einkuenfte aus Gewerbebetrieb",
    "370": "Einkuenfte aus selbstaendiger Arbeit",  # NOTE: mapped to V&V in FIELD_TO_KZ!
    "320": "Einkuenfte aus Vermietung",
    "981": "Einkuenfte aus Kapitalvermoegen",
    "717": "Spenden",
    "718": "Personenversicherungen",
    "724": "Kirchenbeitrag",
    "775": "Werbungskosten",
    "225": "Familienbonus Plus",
}

# Build reverse: KZ -> field_name
KZ_TO_FIELD = {}
for fn, kz in FIELD_TO_KZ.items():
    if kz not in KZ_TO_FIELD:
        KZ_TO_FIELD[kz] = fn

print("=== KZ Matching Analysis ===\n")
print("KZ numbers from _generate_e1_form vs FIELD_TO_KZ mapping:\n")

for kz, desc in FORM_DATA_KZS.items():
    field_name = KZ_TO_FIELD.get(kz)
    if field_name:
        print(f"  ✓ KZ {kz} ({desc}) -> field '{field_name}'")
    else:
        print(f"  ✗ KZ {kz} ({desc}) -> NO MAPPING FOUND!")

# Now check which fields actually exist in the PDF
print("\n=== PDF Field Verification (E1_2024.pdf) ===\n")
pdf_path = TEMPLATE_DIR / "E1_2024.pdf"
if pdf_path.exists():
    doc = fitz.open(str(pdf_path))
    all_field_names = set()
    for page in doc:
        for w in page.widgets():
            if w.field_name:
                all_field_names.add(w.field_name)
    doc.close()

    # Check which mapped fields exist in PDF
    mapped_fields_needed = set()
    for kz, desc in FORM_DATA_KZS.items():
        fn = KZ_TO_FIELD.get(kz)
        if fn:
            mapped_fields_needed.add(fn)

    print(f"Total unique field names in PDF: {len(all_field_names)}")
    print(f"Mapped fields needed: {mapped_fields_needed}")
    print()
    for fn in sorted(mapped_fields_needed):
        if fn in all_field_names:
            print(f"  ✓ Field '{fn}' EXISTS in PDF")
        else:
            print(f"  ✗ Field '{fn}' NOT FOUND in PDF")

    # List all Zahl* fields in PDF for reference
    print(f"\nAll 'Zahl' fields in PDF:")
    zahl_fields = sorted([f for f in all_field_names if f.startswith("Zahl")])
    for f in zahl_fields:
        kz = FIELD_TO_KZ.get(f, "???")
        print(f"  {f} -> KZ {kz}")
else:
    print(f"Template not found: {pdf_path}")
