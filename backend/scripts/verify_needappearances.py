"""Quick check for NeedAppearances flag."""
import fitz

doc = fitz.open("test_e1_output.pdf")
# Check xref 2 (AcroForm)
obj = doc.xref_object(2)
print("AcroForm object:")
print(obj)
print()
print("NeedAppearances present:", "NeedAppearances" in obj)
doc.close()
