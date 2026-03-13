"""
Test script for lightweight tax RAG service.
Run with: python -m backend.test_lightweight_rag
"""
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.lightweight_rag_service import get_lightweight_tax_rag


def test_lightweight_rag():
    """Test the lightweight tax RAG with various questions."""
    
    print("=" * 80)
    print("Testing Lightweight Tax RAG Service")
    print("=" * 80)
    
    rag = get_lightweight_tax_rag()
    
    if not rag.available:
        print("\n❌ Lightweight model not available!")
        print("Please install with: ollama pull qwen2.5:3b")
        return
    
    print(f"\n✅ Model available: {rag.model}")
    print(f"✅ Ollama URL: {rag.ollama_base_url}")
    
    # Test questions in different languages
    test_cases = [
        # German questions
        ("Was ist die Einkommensteuer in Österreich?", "de", None),
        ("Wie hoch ist der Steuersatz für €50.000 Jahreseinkommen?", "de", 2026),
        ("Was kann ich als Selbständiger absetzen?", "de", None),
        
        # English questions
        ("What is the VAT rate in Austria?", "en", None),
        ("How much is the small business exemption limit?", "en", 2026),
        
        # Chinese questions
        ("什么是奥地利的所得税?", "zh", None),
        ("2026年的税率是多少?", "zh", 2026),
        ("我可以抵扣哪些费用?", "zh", None),
        ("SVS社保缴费是多少?", "zh", 2026),
    ]
    
    for i, (question, language, year) in enumerate(test_cases, 1):
        print(f"\n{'=' * 80}")
        print(f"Test {i}/{len(test_cases)}")
        print(f"{'=' * 80}")
        print(f"Question: {question}")
        print(f"Language: {language}")
        print(f"Year: {year or 'All years'}")
        print(f"\n{'-' * 80}")
        
        try:
            answer = rag.answer_tax_question(
                question=question,
                language=language,
                tax_year=year,
            )
            print(f"Answer:\n{answer}")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    print(f"\n{'=' * 80}")
    print("Testing Complete!")
    print(f"{'=' * 80}")


if __name__ == "__main__":
    test_lightweight_rag()
