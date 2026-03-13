"""
Lightweight RAG service for Austrian tax Q&A.
Uses small local LLM (3B params) + tax knowledge base only.
Optimized for CPU-only environments.
Supports both PDF and Markdown documents.
"""
import os
import logging
from typing import List, Dict, Optional
from pathlib import Path
import httpx
import PyPDF2

logger = logging.getLogger(__name__)


class LightweightTaxRAG:
    """
    Lightweight RAG service specifically for Austrian tax questions.
    Uses small local model (qwen2.5:3b or phi3:mini) with tax knowledge only.
    """

    def __init__(self):
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # Use lightweight model for CPU
        self.model = os.getenv("LIGHTWEIGHT_TAX_MODEL", "qwen2.5:3b")
        self.available = False
        
        # Check if model is available
        try:
            resp = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                model_names = [m.get("name", "") for m in models]
                if any(self.model in name for name in model_names):
                    self.available = True
                    logger.info(f"Lightweight tax RAG available: {self.model}")
                else:
                    logger.warning(
                        f"Model {self.model} not found. "
                        f"Install with: ollama pull {self.model}"
                    )
        except Exception as e:
            logger.warning(f"Ollama not reachable: {e}")

    def _extract_text_from_pdf(self, pdf_path: Path, max_pages: int = 50) -> str:
        """
        Extract text from PDF file.
        
        Args:
            pdf_path: Path to PDF file
            max_pages: Maximum pages to extract (to avoid context overflow)
            
        Returns:
            Extracted text
        """
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                pages_to_read = min(total_pages, max_pages)
                
                text_parts = []
                for page_num in range(pages_to_read):
                    page = pdf_reader.pages[page_num]
                    text = page.extract_text()
                    if text.strip():
                        text_parts.append(f"--- Seite {page_num + 1} ---\n{text}")
                
                if total_pages > max_pages:
                    text_parts.append(
                        f"\n[Hinweis: Nur erste {max_pages} von {total_pages} Seiten geladen]"
                    )
                
                return "\n\n".join(text_parts)
        except Exception as e:
            logger.error(f"Failed to extract PDF {pdf_path}: {e}")
            return ""

    def _load_tax_knowledge(self, year: Optional[int] = None) -> str:
        """
        Load Austrian tax knowledge from markdown files (fast, structured).
        PDF extraction is skipped for CPU performance — markdown guides contain
        the same curated information in a more compact form.
        """
        target_year = year or 2026
        cache_key = f"tax_knowledge_{target_year}"

        # Return cached knowledge if available
        if hasattr(self, "_knowledge_cache") and cache_key in self._knowledge_cache:
            return self._knowledge_cache[cache_key]

        docs_dir = Path(__file__).parent.parent.parent / "docs" / "austrian_tax"
        if not docs_dir.exists():
            logger.warning(f"Tax knowledge directory not found: {docs_dir}")
            return ""

        knowledge_parts: list[str] = []
        char_budget = 2500  # Leave room for system prompt + user context + answer
        used = 0

        # 1. Year-specific tax rates (most important)
        md_file = docs_dir / f"tax_rates_{target_year}.md"
        if md_file.exists():
            text = md_file.read_text(encoding="utf-8")
            knowledge_parts.append(f"=== Steuersätze {target_year} ===\n{text}")
            used += len(text) + 30

        # 2. General guides (deductions, property, VAT, SVS) — fit as many as budget allows
        for guide_file in sorted(docs_dir.glob("*.md")):
            if guide_file.name.startswith("tax_rates_"):
                continue
            if used >= char_budget:
                break
            text = guide_file.read_text(encoding="utf-8")
            remaining = char_budget - used
            if len(text) > remaining:
                text = text[:remaining] + "\n[...]"
            knowledge_parts.append(f"=== {guide_file.stem} ===\n{text}")
            used += len(text) + 30

        result = "\n\n".join(knowledge_parts)

        # Cache for subsequent calls
        if not hasattr(self, "_knowledge_cache"):
            self._knowledge_cache: dict[str, str] = {}
        self._knowledge_cache[cache_key] = result

        return result
        return full_text

    def _build_system_prompt(self, language: str, knowledge: str) -> str:
        """Build system prompt with tax knowledge embedded."""
        base_prompts = {
            "de": (
                "Du bist ein Steuerassistent für österreichische Steuerzahler. "
                "Beantworte Fragen NUR basierend auf den bereitgestellten Steuerinformationen. "
                "Wenn die Antwort nicht in den Informationen steht, sage das ehrlich. "
                "Antworte kurz und präzise (max 3-4 Sätze). "
                "Du bist KEIN Steuerberater - weise bei komplexen Fällen auf Steuerberater hin."
            ),
            "en": (
                "You are a tax assistant for Austrian taxpayers. "
                "Answer questions ONLY based on the provided tax information. "
                "If the answer is not in the information, say so honestly. "
                "Keep answers short and precise (max 3-4 sentences). "
                "You are NOT a tax advisor - refer complex cases to tax professionals."
            ),
            "zh": (
                "你是奥地利纳税人的税务助手。"
                "只根据提供的税务信息回答问题。"
                "如果信息中没有答案，请诚实说明。"
                "回答要简短精确（最多3-4句话）。"
                "你不是税务顾问 - 复杂情况请建议咨询专业人士。"
            ),
        }
        
        prompt = base_prompts.get(language, base_prompts["de"])
        
        if knowledge:
            prompt += f"\n\n=== Österreichische Steuerinformationen ===\n{knowledge}"
        
        return prompt

    def answer_tax_question(
        self,
        question: str,
        language: str = "de",
        tax_year: Optional[int] = None,
        user_context: Optional[str] = None,
    ) -> str:
        """
        Answer a tax question using lightweight local model + tax knowledge.
        
        Args:
            question: User's tax question
            language: Response language (de/en/zh)
            tax_year: Specific tax year to focus on (optional)
            user_context: User's financial context (optional)
            
        Returns:
            Answer string
        """
        if not self.available:
            return self._fallback_response(language)
        
        # Load relevant tax knowledge
        knowledge = self._load_tax_knowledge(year=tax_year)
        
        # Build system prompt with embedded knowledge
        system_prompt = self._build_system_prompt(language, knowledge)
        
        # Add user context if provided
        if user_context:
            system_prompt += f"\n\n=== Benutzerdaten ===\n{user_context}"
        
        # Build messages
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question},
        ]
        
        # Call Ollama with optimized settings for CPU
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,  # Low temperature for factual answers
                    "num_predict": 150,  # Short answers only
                    "top_p": 0.9,
                    "top_k": 40,
                    "num_ctx": 2048,  # Small context window for speed on CPU
                },
            }
            
            resp = httpx.post(
                f"{self.ollama_base_url}/api/chat",
                json=payload,
                timeout=90,  # 90 seconds max for CPU inference
            )
            resp.raise_for_status()
            
            data = resp.json()
            answer = data.get("message", {}).get("content", "")
            
            # Add disclaimer
            disclaimer = self._get_disclaimer(language)
            return f"{answer}\n\n{disclaimer}"
            
        except Exception as e:
            logger.error(f"Lightweight RAG failed: {e}")
            return self._fallback_response(language)

    def _get_disclaimer(self, language: str) -> str:
        """Get disclaimer in appropriate language."""
        disclaimers = {
            "de": (
                "⚠️ Dies ist keine Steuerberatung. "
                "Für verbindliche Auskünfte wenden Sie sich an FinanzOnline oder einen Steuerberater."
            ),
            "en": (
                "⚠️ This is not tax advice. "
                "For binding information, consult FinanzOnline or a tax advisor."
            ),
            "zh": (
                "⚠️ 这不是税务建议。"
                "如需权威信息，请咨询 FinanzOnline 或税务顾问。"
            ),
        }
        return disclaimers.get(language, disclaimers["de"])

    def _fallback_response(self, language: str) -> str:
        """Fallback response when model is not available."""
        responses = {
            "de": (
                "Der lokale Steuerassistent ist derzeit nicht verfügbar. "
                "Bitte versuchen Sie es später erneut."
            ),
            "en": (
                "The local tax assistant is currently unavailable. "
                "Please try again later."
            ),
            "zh": (
                "本地税务助手当前不可用，请稍后再试。"
            ),
        }
        return responses.get(language, responses["de"])


# Singleton instance
_lightweight_rag: Optional[LightweightTaxRAG] = None


def get_lightweight_tax_rag() -> LightweightTaxRAG:
    """Get or create the lightweight tax RAG service."""
    global _lightweight_rag
    if _lightweight_rag is None:
        _lightweight_rag = LightweightTaxRAG()
    return _lightweight_rag
