"""
Test E1 filling with sample data to verify the pipeline works.
Run: python scripts/test_e1_fill.py
"""
import sys
sys.path.insert(0, ".")

from app.services.e1_template_filler import fill_e1_from_template, FIELD_TO_KZ

# Build reverse mapping
KZ_TO_FIELD = {}
for fn, kz in FIELD_TO_KZ.items():
    if "_umw" not in kz and "_sum" not in kz and "_text" not in kz:
        if kz not in KZ_TO_FIELD:
            KZ_TO_FIELD[kz] = fn

# Simulate form_data with non-zero values
form_data = {
    "form_type": "E1",
    "tax_year": 2024,
    "user_name": "Max Mustermann",
    "tax_number": "09-123/4567",
    "fields": [
        {"kz": "330", "value": 45000.00},
        {"kz": "370", "value": 12000.00},
        {"kz": "320", "value": 8000.00},
        {"kz": "717", "value": 200.00},
        {"kz": "718", "value": 1500.00},
        {"kz": "724", "value": 600.00},
        {"kz": "245", "value": 2},
    ],
}

print("=== Testing E1 Fill ===")
print(f"Fields to fill: {len(form_data['fields'])}")

# Check which KZs will match
for f in form_data["fields"]:
    kz = f["kz"]
    field_name = KZ_TO_FIELD.get(kz)
    print(f"  KZ {kz} (value={f['value']}) -> field: {field_name or 'NO MATCH'}")

result = fill_e1_from_template(form_data)
if result:
    out_path = "test_e1_output.pdf"
    with open(out_path, "wb") as fp:
        fp.write(result)
    print(f"\n✓ Output written to {out_path} ({len(result)} bytes)")
    print("Open this PDF to verify fields are filled.")
else:
    print("\n✗ fill_e1_from_template returned None!")
