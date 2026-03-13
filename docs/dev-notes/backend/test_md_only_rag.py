"""
Test RAG with Markdown only (faster than PDF).
Run with: python backend/test_md_only_rag.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from app.services.lightweight_rag_service import LightweightTaxRAG

def test_markdown_only():
    """Test with Markdown files only (no PDF)."""
    print("=" * 80)
    print("Testing Lightweight RAG - Markdown Only")
    print("=" * 80)
    
    rag = LightweightTaxRAG()
    
    if not rag.available:
        print("\n❌ Model not available!")
        return
    
    print(f"\n✅ Model: {rag.model}")
    
    # Load only markdown (faster)
    docs_dir = Path(__file__).parent / "docs" / "austrian_tax"
    
    knowledge_parts = []
    
    # Load only one markdown file for speed
    md_file = docs_dir / "tax_rates_2026.md"
    if md_file.exists():
        knowledge_parts.append(f"=== Steuersätze 2026 ===")
        knowledge_parts.append(md_file.read_text(encoding="utf-8"))
    
    knowledge = "\n\n".join(knowledge_parts)
    print(f"✅ Loaded {len(knowledge)} characters from Markdown\n")
    
    # Build system prompt
    system_prompt = (
        "Du bist ein Steuerassistent für österreichische Steuerzahler. "
        "Beantworte Fragen NUR basierend auf den bereitgestellten Steuerinformationen. "
        "Antworte kurz und präzise (max 2-3 Sätze)."
        f"\n\n=== Österreichische Steuerinformationen ===\n{knowledge}"
    )
    
    question = "Wie hoch ist der Steuersatz für €50.000 Jahreseinkommen in 2026?"
    
    print(f"Question: {question}\n")
    print("Generating answer (10-30 seconds)...\n")
    
    try:
        import httpx
        
        payload = {
            "model": rag.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question},
            ],
            "stream": False,
            "options": {
                "temperature": 0.1,
                "num_predict": 100,  # Very short answer
                "num_ctx": 2048,  # Smaller context
            },
        }
        
        resp = httpx.post(
            f"{rag.ollama_base_url}/api/chat",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        
        data = resp.json()
        answer = data.get("message", {}).get("content", "")
        
        print("=" * 80)
        print("Answer:")
        print("=" * 80)
        print(answer)
        print("=" * 80)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_markdown_only()
