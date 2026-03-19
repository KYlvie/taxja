"""
LLM service for AI Tax Assistant.
Supports Groq, OpenAI, GPT-OSS (self-hosted), and Ollama.
"""
import os
import logging
import time
import httpx
from typing import List, Dict, Optional
from openai import OpenAI, RateLimitError

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
    Priority: Groq > OpenAI > GPT-OSS > Ollama.
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
        self.groq_api_key = getattr(settings, "GROQ_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
        self.groq_model = getattr(settings, "GROQ_MODEL", "") or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.groq_vision_model = (
            getattr(settings, "GROQ_VISION_MODEL", "")
            or os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
        )
        self.groq_client = None

        # Ollama settings (local LLM with vision support)
        self.ollama_enabled = getattr(settings, "OLLAMA_ENABLED", False)
        self.ollama_base_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        self.ollama_model = getattr(settings, "OLLAMA_MODEL", "qwen3:8b")
        self.ollama_vision_model = getattr(settings, "OLLAMA_VISION_MODEL", "qwen3-vl:8b")
        self._ollama_ok = False
        self._ollama_vision_ok = False

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

        # Initialize Groq client (fast cloud LLM for text tasks)
        # Always initialize if enabled — works alongside GPT-OSS
        # GPT-OSS handles vision (OCR), Groq handles text (classification, chat)
        if self.groq_enabled and self.groq_api_key:
            try:
                self.groq_client = OpenAI(
                    api_key=self.groq_api_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                logger.info("Groq LLM enabled: %s", self.groq_model)
            except Exception as e:
                logger.warning("Groq initialization failed: %s", e)

        # Initialize OpenAI client (always when key available — needed for vision)
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key)

        # Check Ollama availability (independent — used for local vision + text fallback)
        if self.ollama_enabled:
            try:
                r = httpx.get(f"{self.ollama_base_url}/api/tags", timeout=5)
                if r.status_code == 200:
                    models = [m.get("name", "") for m in r.json().get("models", [])]
                    self._ollama_ok = True
                    # Check if vision model is available locally
                    self._ollama_vision_ok = any(
                        self.ollama_vision_model.split(":")[0] in m
                        for m in models
                    )
                    logger.info(
                        "Ollama available: text=%s, vision=%s (vision_ready=%s)",
                        self.ollama_model,
                        self.ollama_vision_model,
                        self._ollama_vision_ok,
                    )
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
    def is_ollama_mode(self) -> bool:
        """True only when Ollama is the sole available provider."""
        return self._use_ollama

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

    def _get_active_client_and_model(self, prefer_vision: bool = False) -> tuple[OpenAI, str]:
        """Return the highest-priority available client and model name.

        For text tasks (prefer_vision=False): Groq > OpenAI > GPT-OSS
        For vision tasks (prefer_vision=True): Groq > OpenAI > GPT-OSS
        """
        if prefer_vision:
            if self.groq_client:
                return self.groq_client, self.groq_vision_model
            if self.client:
                return self.client, self.model
            if self.gpt_oss_client:
                return self.gpt_oss_client, self.gpt_oss_model
        else:
            if self.groq_client:
                return self.groq_client, self.groq_model
            if self.client:
                return self.client, self.model
            if self.gpt_oss_client:
                return self.gpt_oss_client, self.gpt_oss_model
        raise RuntimeError("No LLM service configured")

    def _build_vision_provider_chain(self) -> list:
        """Build ordered list of (client, model, name) for vision calls.

        Order: Groq (llama-4-scout, fast) → GPT-OSS → OpenAI (gpt-4o, reliable)
        """
        chain = []
        if self.groq_client:
            chain.append((self.groq_client, self.groq_vision_model, "groq"))
        if self.gpt_oss_client:
            chain.append((self.gpt_oss_client, self.gpt_oss_model, "gpt-oss"))
        if self.client:
            chain.append((self.client, self.model, "openai"))
        return chain

    def _ollama_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        think: bool = True,
        model_override: Optional[str] = None,
    ) -> str:
        """Call Ollama native /api/chat endpoint with think control."""
        payload = {
            "model": model_override or self.ollama_model,
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
            timeout=180,
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def _ollama_vision(
        self,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Call Ollama vision model (qwen3-vl) with an image.

        Uses the native /api/chat endpoint with base64 images.
        Returns empty string if vision model is not available.
        """
        if not self._ollama_vision_ok:
            return ""

        import base64

        b64 = base64.b64encode(image_bytes).decode("utf-8")

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt,
                "images": [b64],
            },
        ]

        try:
            t0 = time.time()
            result = self._ollama_chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                think=False,
                model_override=self.ollama_vision_model,
            )
            elapsed = time.time() - t0
            logger.info(
                "Ollama vision (%s) completed in %.1fs (%d chars)",
                self.ollama_vision_model, elapsed, len(result),
            )
            return result
        except Exception as e:
            logger.warning("Ollama vision failed: %s", e)
            return ""

    def _ollama_vision_multi(
        self,
        system_prompt: str,
        user_prompt: str,
        images: list[tuple[bytes, str]],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Call Ollama vision model with multiple images."""
        if not self._ollama_vision_ok:
            return ""

        import base64

        b64_images = [base64.b64encode(img_bytes).decode("utf-8") for img_bytes, _ in images]

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": user_prompt,
                "images": b64_images,
            },
        ]

        try:
            t0 = time.time()
            result = self._ollama_chat(
                messages,
                temperature=temperature,
                max_tokens=max_tokens,
                think=False,
                model_override=self.ollama_vision_model,
            )
            elapsed = time.time() - t0
            logger.info(
                "Ollama vision multi (%s) completed in %.1fs (%d chars, %d images)",
                self.ollama_vision_model, elapsed, len(result), len(images),
            )
            return result
        except Exception as e:
            logger.warning("Ollama vision multi failed: %s", e)
            return ""

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

        clients_to_try = self._build_text_provider_chain()

        if not clients_to_try:
            raise RuntimeError("No LLM service configured")

        last_err = None
        for provider_name, client, model in clients_to_try:
            for attempt in range(2):
                try:
                    logger.info(
                        "Chat via %s (%s)%s",
                        provider_name, model,
                        " [retry]" if attempt else "",
                    )
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=0.3,
                        max_tokens=2000,
                    )
                    text = response.choices[0].message.content or ""
                    return self._strip_model_disclaimer(text)
                except RateLimitError as e:
                    wait = self._get_retry_after(e)
                    logger.warning(
                        "Rate limit hit on %s chat (%s), retry-after=%ds",
                        provider_name, model, wait,
                    )
                    last_err = e
                    if attempt == 0 and wait <= 30:
                        time.sleep(wait)
                        continue
                    break
                except Exception as e:
                    logger.warning("Chat failed via %s (%s): %s", provider_name, model, e)
                    last_err = e
                    break

        logger.error("All LLM providers failed for chat")
        raise last_err

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

    @staticmethod
    def _get_retry_after(err: RateLimitError) -> int:
        """Extract retry-after seconds from a RateLimitError, default 5s."""
        try:
            if hasattr(err, "response") and err.response is not None:
                val = err.response.headers.get("retry-after")
                if val:
                    return min(int(float(val)), 60)
        except Exception:
            pass
        return 5

    def _build_text_provider_chain(self) -> list:
        """Build ordered provider chain for text tasks.

        Order: Groq (fast LPU) → OpenAI (gpt-4o) → GPT-OSS
        Empty responses auto-fallback to next provider.
        """
        providers = []
        if self.groq_client:
            providers.append(("Groq", self.groq_client, self.groq_model))
        if self.client:
            providers.append(("OpenAI", self.client, self.model))
        if self.gpt_oss_client:
            providers.append(("GPT-OSS", self.gpt_oss_client, self.gpt_oss_model))
        return providers

    def generate_simple(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Simple LLM call with rate-limit retry and provider fallback.

        On 429 (rate limit): wait retry-after seconds (max 30s) and retry once
        on the same provider before falling back to the next one.
        Empty responses trigger fallback to next provider.
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        if self._use_ollama:
            return self._ollama_chat(
                messages, temperature=temperature, max_tokens=max_tokens, think=False
            )

        clients_to_try = self._build_text_provider_chain()

        if not clients_to_try:
            raise RuntimeError("No LLM service configured")

        last_err = None
        for provider_name, client, model in clients_to_try:
            for attempt in range(2):  # max 1 retry on rate limit
                try:
                    logger.info(
                        "LLM generate_simple via %s (%s)%s",
                        provider_name, model,
                        " [retry]" if attempt else "",
                    )
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                    result = response.choices[0].message.content or ""
                    if not result.strip():
                        logger.warning(
                            "LLM generate_simple got empty response from %s (%s), "
                            "trying next provider",
                            provider_name, model,
                        )
                        last_err = RuntimeError(f"Empty response from {provider_name}")
                        break  # try next provider
                    logger.info(
                        "LLM generate_simple success via %s (%d chars)",
                        provider_name, len(result),
                    )
                    return result
                except RateLimitError as e:
                    wait = self._get_retry_after(e)
                    logger.warning(
                        "Rate limit hit on %s (%s), retry-after=%ds: %s",
                        provider_name, model, wait, e,
                    )
                    last_err = e
                    if attempt == 0 and wait <= 30:
                        time.sleep(wait)
                        continue
                    break
                except Exception as e:
                    logger.warning(
                        "LLM generate_simple failed via %s (%s): %s",
                        provider_name, model, e,
                    )
                    last_err = e
                    break

        logger.error("All LLM providers failed for generate_simple")
        raise last_err


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

        Provider chain: Ollama qwen3-vl (local, free) → Groq (fast) → OpenAI (reliable).
        Automatically retries with next provider on errors.
        """
        import base64
        from openai import BadRequestError

        # 1️⃣ Cloud providers first (fast): Groq → GPT-OSS → OpenAI
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

        chain = self._build_vision_provider_chain()
        if not chain:
            raise RuntimeError("No vision LLM provider configured")

        last_err = None
        for client, model, name in chain:
            attempts = [max_tokens, max_tokens // 2]
            for attempt_tokens in attempts:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                    result = response.choices[0].message.content or ""
                    if not result.strip():
                        logger.warning("Vision %s returned empty, trying next provider", name)
                        break  # empty → try next provider
                    return result
                except BadRequestError as e:
                    last_err = e
                    err_msg = str(e)
                    if "context length" in err_msg or "maximum input length" in err_msg:
                        logger.warning(
                            "Vision %s exceeded context with max_tokens=%d, retrying",
                            name, attempt_tokens,
                        )
                        continue
                    # Non-context error → try next provider
                    logger.warning("Vision %s failed: %s, trying next provider", name, e)
                    break
                except Exception as e:
                    last_err = e
                    logger.warning("Vision %s error: %s, trying next provider", name, e)
                    break

        # 2️⃣ All cloud providers failed — try Ollama as last resort (slow but works offline)
        if self._ollama_ok and getattr(self, "_ollama_vision_ok", False):
            logger.info("All cloud vision providers failed, trying Ollama (local fallback)")
            result = self._ollama_vision(
                system_prompt, user_prompt, image_bytes, mime_type,
                temperature, max_tokens,
            )
            if result.strip():
                return result

        if last_err:
            raise last_err
        return ""

    def generate_vision_multi(
        self,
        system_prompt: str,
        user_prompt: str,
        images: list[tuple[bytes, str]],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Vision LLM call with multiple images in a single request.

        Provider chain: Ollama qwen3-vl (local) → Groq (fast, max 5 images) → OpenAI (gpt-4o).
        Args:
            images: list of (image_bytes, mime_type) tuples
        """
        import base64
        from openai import BadRequestError

        # 1️⃣ Cloud providers first (fast): Groq → GPT-OSS → OpenAI
        content: list[dict] = []
        for img_bytes, mime in images:
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
            })
        content.append({"type": "text", "text": user_prompt})

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

        chain = self._build_vision_provider_chain()
        if not chain:
            raise RuntimeError("No vision LLM provider configured")

        last_err = None
        for client, model, name in chain:
            attempts = [max_tokens, max_tokens // 2]
            for attempt_tokens in attempts:
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                    result = response.choices[0].message.content or ""
                    if not result.strip():
                        logger.warning(
                            "Vision multi %s returned empty, trying next provider", name
                        )
                        break
                    return result
                except BadRequestError as e:
                    last_err = e
                    err_msg = str(e)
                    if "context length" in err_msg or "maximum input length" in err_msg:
                        logger.warning(
                            "Vision multi %s exceeded context with max_tokens=%d, retrying",
                            name, attempt_tokens,
                        )
                        continue
                    logger.warning(
                        "Vision multi %s failed: %s, trying next provider", name, e
                    )
                    break
                except Exception as e:
                    last_err = e
                    logger.warning(
                        "Vision multi %s error: %s, trying next provider", name, e
                    )
                    break

        if last_err:
            raise last_err
        return ""





# Singleton
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
