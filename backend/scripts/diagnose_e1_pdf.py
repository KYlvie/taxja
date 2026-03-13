"""
Diagnose E1 PDF template to understand field types and fillability.
Run: python scripts/diagnose_e1_pdf.py
"""
import fitz
from pathlib import Path
import sys

TEMPLATE_DIR = Path(__file__).parent.parent / "app" / "templates"


def diagnose(pdf_path: str):
    doc = fitz.open(pdf_path)
    print(f"=== Diagnosing: {pdf_path} ===")
    print(f"Pages: {len(doc)}")
    print(f"Is PDF: {doc.is_pdf}")

    # Check for XFA
    has_xfa = False
    try:
        cat = doc.pdf_catalog()
        trailer = doc.pdf_trailer()
        # Check if AcroForm has XFA key
        xref_count = doc.xref_length()
        for i in range(1, xref_count):
            try:
                obj = doc.xref_object(i)
                if "XFA" in obj:
                    has_xfa = True
                    print(f"\n*** XFA DETECTED in xref {i} ***")
                    print(f"Object snippet: {obj[:200]}")
                    break
            except Exception:
                continue
    except Exception as e:
        print(f"Error checking XFA: {e}")

    print(f"\nHas XFA: {has_xfa}")

    # Count widgets
    total_widgets = 0
    widget_types = {}
    field_names = []

    for page_idx, page in enumerate(doc):
        page_widgets = 0
        for widget in page.widgets():
            total_widgets += 1
            page_widgets += 1
            fn = widget.field_name or "(unnamed)"
            ft = widget.field_type_string or "(unknown)"
            fv = widget.field_value or ""
            widget_types[ft] = widget_types.get(ft, 0) + 1
            field_names.append((page_idx, fn, ft, fv))

        if page_widgets > 0:
            print(f"Page {page_idx}: {page_widgets} widgets")

    print(f"\nTotal widgets: {total_widgets}")
    print(f"Widget types: {widget_types}")

    if total_widgets > 0:
        print(f"\nFirst 30 fields:")
        for page_idx, fn, ft, fv in field_names[:30]:
            print(f"  Page {page_idx}: [{ft}] {fn} = '{fv}'")

    # Try to fill a test field
    if total_widgets > 0 and field_names:
        print("\n=== Fill Test ===")
        test_fn = field_names[0][1]
        print(f"Trying to fill field: {test_fn}")
        try:
            page = doc[field_names[0][0]]
            for w in page.widgets():
                if w.field_name == test_fn:
                    old_val = w.field_value
                    w.field_value = "TEST123"
                    w.update()
                    # Re-read
                    for w2 in page.widgets():
                        if w2.field_name == test_fn:
                            print(f"  Before: '{old_val}' -> After: '{w2.field_value}'")
                            if w2.field_value == "TEST123":
                                print("  ✓ AcroForm filling WORKS")
                            else:
                                print("  ✗ AcroForm filling FAILED - value not retained")
                            break
                    break
        except Exception as e:
            print(f"  ✗ Fill error: {e}")

    doc.close()


if __name__ == "__main__":
    templates = list(TEMPLATE_DIR.glob("E1_*.pdf"))
    if not templates:
        print("No E1 templates found in", TEMPLATE_DIR)
        sys.exit(1)

    for t in sorted(templates):
        diagnose(str(t))
        print()
