"""Check if appearance streams are properly generated."""
import fitz

doc = fitz.open("test_e1_output.pdf")

# Check NeedAppearances in AcroForm
for i in range(1, min(doc.xref_length(), 100)):
    try:
        obj = doc.xref_object(i)
        if "/AcroForm" in obj or "NeedAppearances" in obj or "/Fields" in obj:
            if "/Fields" in obj:
                print(f"AcroForm dict (xref {i}):")
                # Show first 500 chars
                print(f"  {obj[:500]}")
                if "NeedAppearances" in obj:
                    print("  -> NeedAppearances IS set")
                else:
                    print("  -> NeedAppearances NOT set")
                break
    except:
        continue

# Check a specific filled field's appearance
target = "Zahl86a"
for page in doc:
    for w in page.widgets():
        if w.field_name == target:
            print(f"\nField '{target}':")
            print(f"  Value: {w.field_value}")
            print(f"  Rect: {w.rect}")
            print(f"  Field type: {w.field_type_string}")
            print(f"  Field flags: {w.field_flags}")
            # Check xref for appearance stream
            xref = w.xref
            if xref:
                obj = doc.xref_object(xref)
                has_ap = "/AP" in obj
                print(f"  Has /AP (appearance): {has_ap}")
                if has_ap:
                    print(f"  Object: {obj[:400]}")
            break

doc.close()
