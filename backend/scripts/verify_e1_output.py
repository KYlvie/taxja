"""
Verify the filled E1 PDF actually has values in its fields.
Run: python scripts/verify_e1_output.py
"""
import fitz

doc = fitz.open("test_e1_output.pdf")
print("=== Verifying filled PDF ===\n")

filled_count = 0
empty_count = 0
target_fields = {"Zahl86a", "Zahl131", "Zahl75", "Zahl104_02", "Zahl104_01", "Zahl104_10", "Zahl25", "Zahl07_01", "Zahl03", "Zahl02_1", "Zahl02_2"}

for page_idx, page in enumerate(doc):
    for w in page.widgets():
        fn = w.field_name or ""
        if fn in target_fields:
            val = w.field_value or ""
            has_ap = bool(w.rect)  # Check if widget has appearance
            print(f"  Page {page_idx}: {fn} = '{val}' (type={w.field_type_string})")
            if val:
                filled_count += 1
            else:
                empty_count += 1

print(f"\nFilled: {filled_count}, Empty: {empty_count}")

# Also check if the NeedAppearances flag is set
# This is critical - without it, PDF viewers may not render the values
try:
    xref_count = doc.xref_length()
    for i in range(1, min(xref_count, 50)):
        obj = doc.xref_object(i)
        if "AcroForm" in obj or "NeedAppearances" in obj:
            print(f"\nxref {i}: {obj[:300]}")
except Exception as e:
    print(f"Error: {e}")

doc.close()
