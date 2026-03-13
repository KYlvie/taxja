"""
Quick test to verify PDF loading functionality.
Run with: python backend/test_pdf_loading.py
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.lightweight_rag_service import LightweightTaxRAG

def test_pdf_extraction():
    """Test PDF text extraction."""
    print("=" * 80)
    print("Testing PDF Extraction")
    print("=" * 80)
    
    rag = LightweightTaxRAG()
    docs_dir = Path(__file__).parent / "docs" / "austrian_tax"
    
    # Find all PDFs
    pdf_files = list(docs_dir.glob("*.pdf"))
    print(f"\nFound {len(pdf_files)} PDF files:")
    for pdf in pdf_files:
        print(f"  - {pdf.name}")
    
    if not pdf_files:
        print("\n❌ No PDF files found!")
        return
    
    # Test extraction on first PDF
    test_pdf = pdf_files[0]
    print(f"\n{'=' * 80}")
    print(f"Testing extraction: {test_pdf.name}")
    print(f"{'=' * 80}")
    
    try:
        text = rag._extract_text_from_pdf(test_pdf, max_pages=3)
        
        if text:
            print(f"\n✅ Successfully extracted {len(text)} characters")
            print(f"\nFirst 500 characters:")
            print("-" * 80)
            print(text[:500])
            print("-" * 80)
        else:
            print("\n❌ No text extracted!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def test_knowledge_loading():
    """Test full knowledge base loading."""
    print("\n" + "=" * 80)
    print("Testing Knowledge Base Loading")
    print("=" * 80)
    
    rag = LightweightTaxRAG()
    
    # Test loading for specific year
    print("\nLoading knowledge for year 2026...")
    knowledge = rag._load_tax_knowledge(year=2026)
    
    if knowledge:
        print(f"✅ Loaded {len(knowledge)} characters")
        print(f"\nFirst 800 characters:")
        print("-" * 80)
        print(knowledge[:800])
        print("-" * 80)
    else:
        print("❌ No knowledge loaded!")


if __name__ == "__main__":
    test_pdf_extraction()
    test_knowledge_loading()
    
    print("\n" + "=" * 80)
    print("Test Complete!")
    print("=" * 80)
