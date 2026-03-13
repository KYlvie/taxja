"""
Simple test for lightweight RAG with one question.
Run with: python backend/test_simple_rag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.lightweight_rag_service import get_lightweight_tax_rag

def test_single_question():
    """Test with a single simple question."""
    print("=" * 80)
    print("Testing Lightweight Tax RAG - Single Question")
    print("=" * 80)
    
    rag = get_lightweight_tax_rag()
    
    if not rag.available:
        print("\n❌ Model not available!")
        return
    
    print(f"\n✅ Model: {rag.model}")
    print(f"✅ Ollama: {rag.ollama_base_url}")
    
    # Simple question
    question = "Was ist die Einkommensteuer?"
    language = "de"
    year = 2026
    
    print(f"\n{'=' * 80}")
    print(f"Question: {question}")
    print(f"Language: {language}")
    print(f"Year: {year}")
    print(f"{'=' * 80}\n")
    
    try:
        print("Loading knowledge base...")
        knowledge = rag._load_tax_knowledge(year=year)
        print(f"✅ Loaded {len(knowledge)} characters\n")
        
        print("Generating answer (this may take 10-30 seconds on CPU)...")
        answer = rag.answer_tax_question(
            question=question,
            language=language,
            tax_year=year,
        )
        
        print(f"\n{'=' * 80}")
        print("Answer:")
        print(f"{'=' * 80}")
        print(answer)
        print(f"{'=' * 80}\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_single_question()
