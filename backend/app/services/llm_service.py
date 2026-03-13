"""
LLM service for AI Tax Assistant.
Supports GPT-OSS-120B (self-hosted vLLM), OpenAI API, Groq, and Ollama.
"""
import os
import logging
import httpx
from typing import List, Dict, Optional
from openai import OpenAI

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT_TEMPLATE = {
    "de": (
        "Du bist der Taxja AI-Steuerassistent für österreichische Steuerzahler. "
        "Du hilfst bei Fragen zu Einkommensteuer, Umsatzsteuer, SVS-Sozialversicherung, "
        "Absetzbeträgen und Steuererklärungen nach österreichischem Recht (Steuerjahr 2025, Veranlagung 2026). "
        "Wichtig: Unterscheide korrekt zwischen ÖGK (Arbeitnehmer-Sozialversicherung) und SVS (nur für Selbständige/GSVG). "
        "Einkünfte aus Vermietung und Verpachtung (§28 EStG) sind KEINE selbständige Tätigkeit und unterliegen NICHT der SVS. "
        "Antworte präzise, freundlich und auf Deutsch. "
        "Füge KEINEN Haftungsausschluss hinzu — dieser wird automatisch angehängt. "
        "Verwende die bereitgestellten Kontextinformationen, um personalisierte Antworten zu geben."
    ),
    "en": (
        "You are the Taxja AI tax assistant for Austrian taxpayers. "
        "You help with questions about income tax, VAT, SVS social insurance, "
        "deductions and tax returns under Austrian law (tax year 2025, filed 2026). "
        "Important: Correctly distinguish between ÖGK (employee social insurance) and SVS (self-employed only/GSVG). "
        "Rental income (§28 EStG) is NOT self-employment and is NOT subject to SVS. "
        "Answer precisely, friendly and in English. "
        "Do NOT add any disclaimer — it is appended automatically. "
        "Use the provided context information to give personalized answers."
    ),
    "zh": (
        "你是Taxja AI税务助手，专门服务奥地利纳税人。"
        "你帮助解答关于所得税、增值税、SVS社会保险、抵扣和报税的问题，"
        "依据奥地利税法（税务年度2025，2026年申报）。"
        "重要：正确区分ÖGK（雇员社保，由雇主和雇员共同缴纳）和SVS（仅针对自雇人员/GSVG）。"
        "出租收入（§28 EStG）不属于自雇活动，不需要缴纳SVS。"
        "回答要准确、友好，使用中文。"
        "不要添加任何免责声明，系统会自动追加。"
        "使用提供的上下文信息给出个性化回答。"
    ),
}


class LLMService:
    """Service for LLM-based response generation.
    Priority: GPT-OSS-120B (self-hosted) > Groq > OpenAI > Ollama.
    """

    def __init__(self):
        self.api_key = (
            getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        )
        self.model = (
            getattr(settings, "OPENAI_MODEL", "") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        self.client: Optional[OpenAI] = None

        # GPT-OSS-120B settings (self-hosted via vLLM, highest priority)
        self.gpt_oss_enabled = (
            getattr(settings, "GPT_OSS_ENABLED", False)
            or os.getenv("GPT_OSS_ENABLED", "").lower() == "true"
        )
        self.gpt_oss_base_url = (
            getattr(settings, "GPT_OSS_BASE_URL", "")
            or os.getenv("GPT_OSS_BASE_URL", "http://localhost:8000/v1")
        )
        self.gpt_oss_model = (
            getattr(settings, "GPT_OSS_MODEL", "")
            or os.getenv("GPT_OSS_MODEL", "openai/gpt-oss-120b")
        )
        self.gpt_oss_api_key = (
            getattr(settings, "GPT_OSS_API_KEY", "")
            or os.getenv("GPT_OSS_API_KEY", "not-needed")
        )
        self.gpt_oss_client: Optional[OpenAI] = None

        # Groq settings (fast & free alternative)
        self.groq_enabled = getattr(settings, "GROQ_ENABLED", False) or os.getenv("GROQ_ENABLED", "").lower() == "true"
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.groq_model = getattr(settings, "GROQ_MODEL", "") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_client = None

        # Ollama settings
        self.ollama_enabled = getattr(settings, "OLLAMA_ENABLED", False)
        self.ollama_base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = getattr(settings, "OLLAMA_MODEL", "qwen3:8b")
        self._ollama_ok = False

        # Initialize GPT-OSS-120B client (highest priority - self-hosted, GDPR safe)
        if self.gpt_oss_enabled:
            try:
                self.gpt_oss_client = OpenAI(
                    api_key=self.gpt_oss_api_key,
                    base_url=self.gpt_oss_base_url,
                    timeout=httpx.Timeout(120.0, connect=10.0),
                )
                logger.info(
                    "GPT-OSS-120B enabled: %s at %s",
                    self.gpt_oss_model,
                    self.gpt_oss_base_url,
                )
            except Exception as e:
                logger.warning("GPT-OSS-120B initialization failed: %s", e)

        # Initialize Groq client (priority over OpenAI for speed)
        if self.groq_enabled and self.groq_api_key and not self.gpt_oss_client:
            try:
                self.groq_client = OpenAI(
                    api_key=self.groq_api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("Groq LLM enabled: %s", self.groq_model)
            except Exception as e:
                logger.warning("Groq initialization failed: %s", e)

        # Initialize OpenAI client
        if self.api_key and not self.gpt_oss_client and not self.groq_client:
            self.client = OpenAI(api_key=self.api_key)

        # Check Ollama availability (fallback)
        if (
            self.ollama_enabled
            and not self.client
            and not self.groq_client
            and not self.gpt_oss_client
        ):
            try:
                r = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                if r.status_code == 200:
                    self._ollama_ok = True
                    logger.info("Ollama available: %s", self.ollama_model)
            except Exception as e:
                logger.warning("Ollama not reachable: %s", e)

    @property
    def is_available(self) -> bool:
        return (
            self.gpt_oss_client is not None
            or self.groq_client is not None
            or self.client is not None
            or self._ollama_ok
        )

    @property
    def _use_ollama(self) -> bool:
        return (
            self.gpt_oss_client is None
            and self.groq_client is None
            and self.client is None
            and self._ollama_ok
        )

    @property
    def _use_groq(self) -> bool:
        return self.gpt_oss_client is None and self.groq_client is not None

    @property
    def _use_gpt_oss(self) -> bool:
        return self.gpt_oss_client is not None

    def _get_active_client_and_model(self) -> tuple[OpenAI, str]:
        """Return the highest-priority available client and model name."""
        if self.gpt_oss_client:
            return self.gpt_oss_client, self.gpt_oss_model
        if self.groq_client:
            return self.groq_client, self.groq_model
        if self.client:
            return self.client, self.model
        raise RuntimeError("No LLM service configured")

    def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        think: bool = True,
    ) -> str:
        """Call Ollama native /api/chat endpoint with think control."""
        payload = {
            "model": self.ollama_model,
            "messages": messages,
            "stream": False,
            "think": think,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        resp = httpx.post(
            f"{self.ollama_base_url}/api/chat",
            json=payload,
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def generate_response(
        self,
        user_message: str,
        language: str,
        context_chunks: List[str],
        user_financial_summary: str,
        conversation_history: List[Dict[str, str]],
    ) -> str:
        """Generate a response using the LLM with RAG context."""
        system_prompt = SYSTEM_PROMPT_TEMPLATE.get(language, SYSTEM_PROMPT_TEMPLATE["de"])

        # For Ollama on CPU: add conciseness instruction to reduce generation time
        if self._use_ollama:
            concise_hints = {
                "de": " Antworte kurz und prägnant (max 3-4 Sätze).",
                "en": " Keep answers concise (max 3-4 sentences).",
                "zh": " 回答要简洁（最多3-4句话）。",
            }
            system_prompt += concise_hints.get(language, concise_hints["de"])

        # Build context block
        context_parts: List[str] = []
        if context_chunks:
            context_parts.append("=== Relevante Steuerinformationen / Tax Knowledge ===")
            for i, chunk in enumerate(context_chunks, 1):
                context_parts.append(f"[{i}] {chunk}")
        if user_financial_summary:
            context_parts.append("=== Finanzdaten des Benutzers / User Financial Data ===")
            context_parts.append(user_financial_summary)

        if context_parts:
            system_prompt += "\n\n" + "\n".join(context_parts)

        messages: List[Dict[str, str]] = [{"role": "system", "content": system_prompt}]
        if self._use_ollama:
            # Limit history to last 2 exchanges for CPU speed; strip disclaimers
            trimmed = conversation_history[-4:]
            for msg in trimmed:
                content = msg["content"]
                # Strip disclaimer block to save tokens
                for marker in ("\n\n⚠️ **Haftungsausschluss**", "\n\n⚠️ **Disclaimer**", "\n\n⚠️ **免责声明**"):
                    idx = content.find(marker)
                    if idx > 0:
                        content = content[:idx]
                        break
                messages.append({"role": msg["role"], "content": content})
        else:
            for msg in conversation_history[-6:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        if self._use_ollama:
            # For chat: disable thinking for speed, limit output tokens for CPU
            return self._ollama_chat(messages, temperature=0.3, max_tokens=300, think=False)

        active_client, active_model = self._get_active_client_and_model()
        try:
            response = active_client.chat.completions.create(
                model=active_model,
                messages=messages,
                temperature=0.3,
                max_tokens=2000,
            )
            text = response.choices[0].message.content or ""
            return self._strip_model_disclaimer(text)
        except Exception as e:
            logger.error("LLM generation failed (%s): %s", active_model, e)
            raise

    @staticmethod
    def _strip_model_disclaimer(text: str) -> str:
        """Strip any disclaimer the model generates on its own (code appends one)."""
        import re
        # Match any line starting with ⚠ (warning sign U+26A0, with or without variation selector)
        pattern = r'\n+\s*\u26a0.*$'
        match = re.search(pattern, text, re.DOTALL)
        if match and match.start() > 0:
            logger.info("Stripped model disclaimer at position %d", match.start())
            text = text[:match.start()]
        else:
            logger.info("No model disclaimer found to strip (len=%d)", len(text))
        return text.rstrip()

    def generate_simple(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Simple LLM call. Used for document extraction. Thinking disabled for speed."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if self._use_ollama:
            return self._ollama_chat(
                messages, temperature=temperature, max_tokens=max_tokens, think=False
            )

        active_client, active_model = self._get_active_client_and_model()
        response = active_client.chat.completions.create(
            model=active_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""

    def generate_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Vision LLM call: send an image + text prompt to a VL model.
        Uses OpenAI-compatible multimodal messages format supported by vLLM.
        """
        import base64

        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{mime_type};base64,{b64}"

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": user_prompt},
                ],
            },
        ]

        if self._use_ollama:
            # Ollama also supports multimodal messages
            return self._ollama_chat(
                messages, temperature=temperature, max_tokens=max_tokens, think=False
            )

        active_client, active_model = self._get_active_client_and_model()
        response = active_client.chat.completions.create(
            model=active_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""



# Singleton
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
