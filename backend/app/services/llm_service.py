"""
LLM service for AI Tax Assistant.
Supports Groq, OpenAI, Anthropic Claude, GPT-OSS (self-hosted), and Ollama.
"""
import os
import logging
import time
import httpx
from typing import List, Dict, Optional
import anthropic
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
    "fr": (
        "Vous êtes l'assistant fiscal IA Taxja pour les contribuables autrichiens. "
        "Vous aidez à répondre aux questions sur l'impôt sur le revenu, la TVA, l'assurance sociale SVS, "
        "les déductions et les déclarations fiscales selon le droit autrichien (année fiscale 2025, déclaration 2026). "
        "Important : Distinguez correctement entre ÖGK (assurance sociale des salariés) et SVS (uniquement pour les indépendants/GSVG). "
        "Les revenus locatifs (§28 EStG) ne constituent PAS une activité indépendante et ne sont PAS soumis à la SVS. "
        "Répondez de manière précise, aimable et en français. "
        "N'ajoutez AUCUNE clause de non-responsabilité — elle est ajoutée automatiquement. "
        "Utilisez les informations contextuelles fournies pour donner des réponses personnalisées."
    ),
    "ru": (
        "Вы — налоговый ИИ-помощник Taxja для австрийских налогоплательщиков. "
        "Вы помогаете отвечать на вопросы о подоходном налоге, НДС, социальном страховании SVS, "
        "вычетах и налоговых декларациях в соответствии с австрийским законодательством (налоговый год 2025, подача в 2026). "
        "Важно: Правильно различайте ÖGK (социальное страхование наёмных работников) и SVS (только для самозанятых/GSVG). "
        "Доходы от аренды (§28 EStG) НЕ являются самозанятостью и НЕ облагаются SVS. "
        "Отвечайте точно, дружелюбно и на русском языке. "
        "НЕ добавляйте никаких отказов от ответственности — они добавляются автоматически. "
        "Используйте предоставленную контекстную информацию для персонализированных ответов."
    ),
    "hu": (
        "Ön a Taxja AI adótanácsadó az osztrák adófizetők számára. "
        "Segít a jövedelemadóval, áfával, SVS társadalombiztosítással, "
        "levonásokkal és adóbevallásokkal kapcsolatos kérdésekben az osztrák jogszabályok szerint (adóév 2025, bevallás 2026). "
        "Fontos: Helyesen különböztesse meg az ÖGK-t (munkavállalói társadalombiztosítás) és az SVS-t (csak önálló vállalkozók/GSVG). "
        "A bérleti jövedelem (§28 EStG) NEM önálló tevékenység és NEM tartozik az SVS hatálya alá. "
        "Válaszoljon pontosan, barátságosan és magyarul. "
        "NE adjon hozzá jogi nyilatkozatot — az automatikusan hozzáfűződik. "
        "Használja a rendelkezésre álló kontextusinformációkat személyre szabott válaszokhoz."
    ),
    "pl": (
        "Jesteś asystentem podatkowym AI Taxja dla austriackich podatników. "
        "Pomagasz w pytaniach dotyczących podatku dochodowego, VAT, ubezpieczenia społecznego SVS, "
        "odliczeń i zeznań podatkowych zgodnie z prawem austriackim (rok podatkowy 2025, rozliczenie 2026). "
        "Ważne: Prawidłowo rozróżniaj między ÖGK (ubezpieczenie społeczne pracowników) a SVS (tylko dla samozatrudnionych/GSVG). "
        "Dochody z najmu (§28 EStG) NIE są działalnością na własny rachunek i NIE podlegają SVS. "
        "Odpowiadaj precyzyjnie, przyjaźnie i po polsku. "
        "NIE dodawaj żadnych zastrzeżeń prawnych — są dodawane automatycznie. "
        "Wykorzystuj dostarczone informacje kontekstowe do udzielania spersonalizowanych odpowiedzi."
    ),
    "tr": (
        "Siz Avusturyali vergi mukellefleri icin Taxja AI vergi asistanisiniz. "
        "Gelir vergisi, KDV, SVS sosyal sigortasi, indirimler ve vergi beyannameleri hakkindaki sorularda "
        "Avusturya hukukuna gore yardimci olursunuz (vergi yili 2025, beyanname 2026). "
        "Onemli: OeGK (calisan sosyal sigortasi) ile SVS (yalnizca serbest calisanlar/GSVG) arasindaki farki dogru ayirt edin. "
        "Kira geliri (Par. 28 EStG) serbest meslek faaliyeti DEGILDIR ve SVS'ye tabi DEGILDIR. "
        "Kesin, dostca ve Turkce yanit verin. "
        "Hicbir sorumluluk reddi eklemeyin - otomatik olarak eklenir. "
        "Kisisellestirilmis yanitlar vermek icin saglanan baglam bilgilerini kullanin."
    ),
    "bs": (
        "Vi ste Taxja AI porezni asistent za austrijske porezne obveznike. "
        "Pomazete s pitanjima o porezu na dohodak, PDV-u, SVS socijalnom osiguranju, "
        "odbitcima i poreznim prijavama prema austrijskom pravu (porezna godina 2025, prijava 2026). "
        "Vazno: Pravilno razlikujte OeGK (socijalno osiguranje zaposlenika) i SVS (samo za samostalne djelatnike/GSVG). "
        "Prihodi od najma (Par. 28 EStG) NISU samostalna djelatnost i NISU predmet SVS-a. "
        "Odgovarajte precizno, prijateljski i na bosanskom jeziku. "
        "NEMOJTE dodavati nikakvu izjavu o odricanju odgovornosti - ona se dodaje automatski. "
        "Koristite dostavljene kontekstualne informacije za personalizirane odgovore."
    ),
}


class LLMService:
    """Service for LLM-based response generation.
    Text priority: Groq > OpenAI > GPT-OSS > Ollama.
    Vision priority: OpenAI > Anthropic > GPT-OSS > Groq > Ollama.
    """

    def __init__(self):
        self.api_key = (
            getattr(settings, "OPENAI_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
        )
        self.model = (
            getattr(settings, "OPENAI_MODEL", "") or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        )
        self.client: Optional[OpenAI] = None
        self.anthropic_api_key = (
            getattr(settings, "ANTHROPIC_API_KEY", "")
            or os.getenv("ANTHROPIC_API_KEY", "")
        )
        self.anthropic_model = (
            getattr(settings, "ANTHROPIC_MODEL", "")
            or os.getenv("ANTHROPIC_MODEL", "claude-opus-4-1-20250805")
        )
        self.anthropic_vision_model = (
            getattr(settings, "ANTHROPIC_VISION_MODEL", "")
            or os.getenv("ANTHROPIC_VISION_MODEL", self.anthropic_model)
        )
        self.anthropic_client: Optional[anthropic.Anthropic] = None

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

        if self.anthropic_api_key:
            try:
                self.anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
                logger.info("Anthropic vision enabled: %s", self.anthropic_vision_model)
            except Exception as e:
                logger.warning("Anthropic initialization failed: %s", e)

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
            or self.anthropic_client is not None
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

        Priority: OpenAI (GPT-4o) > Groq > GPT-OSS
        Changed from Groq-first to OpenAI-first for better classification accuracy.
        """
        if prefer_vision:
            if self.client:
                return self.client, self.model
            if self.anthropic_client:
                raise RuntimeError(
                    "Anthropic vision is available via generate_vision(), "
                    "not via the OpenAI-compatible client selector"
                )
            if self.groq_client:
                return self.groq_client, self.groq_vision_model
            if self.gpt_oss_client:
                return self.gpt_oss_client, self.gpt_oss_model
        else:
            if self.client:
                return self.client, self.model
            if self.groq_client:
                return self.groq_client, self.groq_model
            if self.gpt_oss_client:
                return self.gpt_oss_client, self.gpt_oss_model
        raise RuntimeError("No LLM service configured")

    def _build_vision_provider_chain(self, prefer_provider: Optional[str] = None) -> list[dict]:
        """Build ordered vision provider chain.

        Default order prioritizes OCR accuracy: OpenAI → Anthropic → GPT-OSS → Groq.
        `prefer_provider` can move one configured provider to the front for
        manual high-accuracy reruns without changing the rest of the fallback order.
        """
        chain: list[dict] = []
        if self.client:
            chain.append({"name": "openai", "client": self.client, "model": self.model})
        if self.anthropic_client:
            chain.append(
                {
                    "name": "anthropic",
                    "client": self.anthropic_client,
                    "model": self.anthropic_vision_model,
                }
            )
        if self.gpt_oss_client:
            chain.append(
                {
                    "name": "gpt-oss",
                    "client": self.gpt_oss_client,
                    "model": self.gpt_oss_model,
                }
            )
        if self.groq_client:
            chain.append(
                {
                    "name": "groq",
                    "client": self.groq_client,
                    "model": self.groq_vision_model,
                }
            )

        if prefer_provider:
            preferred_index = next(
                (index for index, provider in enumerate(chain) if provider["name"] == prefer_provider),
                None,
            )
            if preferred_index is not None:
                chain.insert(0, chain.pop(preferred_index))

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

    @staticmethod
    def _extract_anthropic_text(response) -> str:
        """Extract concatenated text blocks from an Anthropic response."""
        chunks: list[str] = []
        for block in getattr(response, "content", []) or []:
            if getattr(block, "type", None) == "text" and getattr(block, "text", None):
                chunks.append(block.text)
            elif isinstance(block, dict) and block.get("type") == "text" and block.get("text"):
                chunks.append(block["text"])
        return "\n".join(chunk.strip() for chunk in chunks if chunk and chunk.strip()).strip()

    def _anthropic_vision(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Call Anthropic vision with a single image."""
        if not self.anthropic_client:
            return ""

        import base64

        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime_type,
                                "data": base64.b64encode(image_bytes).decode("utf-8"),
                            },
                        },
                        {"type": "text", "text": user_prompt},
                    ],
                }
            ],
        )
        return self._extract_anthropic_text(response)

    def _anthropic_vision_multi(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        images: list[tuple[bytes, str]],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Call Anthropic vision with multiple images in a single request."""
        if not self.anthropic_client:
            return ""

        import base64

        content: list[dict] = []
        for img_bytes, mime_type in images:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime_type,
                        "data": base64.b64encode(img_bytes).decode("utf-8"),
                    },
                }
            )
        content.append({"type": "text", "text": user_prompt})

        response = self.anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": content}],
        )
        return self._extract_anthropic_text(response)

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
                "fr": " Repondez de maniere concise (max 3-4 phrases).",
                "ru": " Отвечайте кратко и по существу (макс. 3-4 предложения).",
                "hu": " Valaszoljon roviden es tomoren (max. 3-4 mondat).",
                "pl": " Odpowiadaj zwiezle (maks. 3-4 zdania).",
                "tr": " Kisa ve oz yanitlayin (maks. 3-4 cumle).",
                "bs": " Odgovarajte kratko i jezgrovito (maks. 3-4 recenice).",
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

    def _build_text_provider_chain(self, prefer_provider: Optional[str] = None) -> list:
        """Build ordered provider chain for text tasks.

        Default order: OpenAI → Anthropic → Groq → GPT-OSS.
        OpenAI (GPT-4o) is primary for accuracy; Anthropic (Claude) is fallback;
        Groq and GPT-OSS are last-resort options.
        `prefer_provider` can move one configured provider to the front.
        """
        providers = []
        if self.client:
            providers.append(("OpenAI", self.client, self.model))
        if self.anthropic_client:
            providers.append(("Anthropic", self.anthropic_client, self.anthropic_model))
        if self.groq_client:
            providers.append(("Groq", self.groq_client, self.groq_model))
        if self.gpt_oss_client:
            providers.append(("GPT-OSS", self.gpt_oss_client, self.gpt_oss_model))

        if prefer_provider:
            normalized_preference = prefer_provider.strip().lower()
            preferred = None
            remainder = []
            for provider_name, client, model in providers:
                if preferred is None and provider_name.lower() == normalized_preference:
                    preferred = (provider_name, client, model)
                else:
                    remainder.append((provider_name, client, model))
            if preferred is not None:
                return [preferred, *remainder]
        return providers

    def _anthropic_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        temperature: float,
        max_tokens: int,
        extra_messages: Optional[list] = None,
    ) -> str:
        """Call Anthropic text generation."""
        if not self.anthropic_client:
            raise RuntimeError("Anthropic client not configured")

        anthropic_messages: list = []
        if extra_messages:
            for msg in extra_messages:
                anthropic_messages.append({
                    "role": msg["role"],
                    "content": [{"type": "text", "text": msg["content"]}],
                })
        anthropic_messages.append({
            "role": "user",
            "content": [{"type": "text", "text": user_prompt}],
        })

        response = self.anthropic_client.messages.create(
            model=model,
            system=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            messages=anthropic_messages,
        )
        return self._extract_anthropic_text(response)

    def generate_simple(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        provider_preference: Optional[str] = None,
        extra_messages: Optional[list] = None,
    ) -> str:
        """Simple LLM call with rate-limit retry and provider fallback.

        On 429 (rate limit): wait retry-after seconds (max 30s) and retry once
        on the same provider before falling back to the next one.
        Empty responses trigger fallback to next provider.

        extra_messages: optional list of {"role": "user"|"assistant", "content": "..."}
            inserted between system and the final user message for multi-turn context.
        """
        # Safety cap: trim extra_messages if total input chars exceed ~6000
        # (~2000 tokens), dropping oldest messages first to stay within
        # context limits for smaller models (e.g. Mixtral on Groq).
        trimmed_extras = list(extra_messages) if extra_messages else []
        if trimmed_extras:
            base_chars = len(system_prompt) + len(user_prompt)
            max_extra_chars = max(0, 6000 - base_chars)
            while trimmed_extras:
                total = sum(len(m.get("content", "")) for m in trimmed_extras)
                if total <= max_extra_chars:
                    break
                trimmed_extras.pop(0)  # drop oldest first

        messages = [{"role": "system", "content": system_prompt}]
        if trimmed_extras:
            messages.extend(trimmed_extras)
        messages.append({"role": "user", "content": user_prompt})

        if self._use_ollama:
            return self._ollama_chat(
                messages, temperature=temperature, max_tokens=max_tokens, think=False
            )

        clients_to_try = self._build_text_provider_chain(provider_preference)

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
                    if provider_name == "Anthropic":
                        result = self._anthropic_text(
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            temperature=temperature,
                            max_tokens=max_tokens,
                            extra_messages=extra_messages,
                        )
                    else:
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
        provider_preference: Optional[str] = None,
    ) -> str:
        """Vision LLM call: send an image + text prompt to a VL model.

        Provider chain: OpenAI → Anthropic → GPT-OSS → Groq, then Ollama as last resort.
        Automatically retries with next provider on errors.
        """
        import base64
        from openai import BadRequestError

        # 1️⃣ Cloud providers first, ordered for OCR accuracy.
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

        chain = self._build_vision_provider_chain(provider_preference)
        if not chain:
            raise RuntimeError("No vision LLM provider configured")

        last_err = None
        for provider in chain:
            client = provider["client"]
            model = provider["model"]
            name = provider["name"]
            attempts = [max_tokens, max_tokens // 2]
            for attempt_tokens in attempts:
                try:
                    if name == "anthropic":
                        result = self._anthropic_vision(
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            image_bytes=image_bytes,
                            mime_type=mime_type,
                            temperature=temperature,
                            max_tokens=attempt_tokens,
                        )
                    else:
                        response = client.chat.completions.create(
                            model=model,
                            messages=messages,
                            temperature=temperature,
                            max_tokens=attempt_tokens,
                        )
                        result = response.choices[0].message.content or ""
                    if not result.strip():
                        logger.warning("Vision %s returned empty, trying next provider", name)
                        break
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
        provider_preference: Optional[str] = None,
    ) -> str:
        """Vision LLM call with multiple images in a single request.

        Provider chain: OpenAI → Anthropic → GPT-OSS → Groq, then Ollama as last resort.
        Args:
            images: list of (image_bytes, mime_type) tuples
        """
        import base64
        from openai import BadRequestError

        # 1️⃣ Cloud providers first, ordered for OCR accuracy.
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

        chain = self._build_vision_provider_chain(provider_preference)
        if not chain:
            raise RuntimeError("No vision LLM provider configured")

        last_err = None
        for provider in chain:
            client = provider["client"]
            model = provider["model"]
            name = provider["name"]
            attempts = [max_tokens, max_tokens // 2]
            for attempt_tokens in attempts:
                try:
                    if name == "anthropic":
                        result = self._anthropic_vision_multi(
                            model=model,
                            system_prompt=system_prompt,
                            user_prompt=user_prompt,
                            images=images,
                            temperature=temperature,
                            max_tokens=attempt_tokens,
                        )
                    else:
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

        if self._ollama_ok and getattr(self, "_ollama_vision_ok", False):
            logger.info("All cloud multi-image vision providers failed, trying Ollama (local fallback)")
            result = self._ollama_vision_multi(
                system_prompt, user_prompt, images, temperature, max_tokens
            )
            if result.strip():
                return result

        if last_err:
            raise last_err
        return ""

    def generate_vision_strict_provider(
        self,
        *,
        provider_name: str,
        system_prompt: str,
        user_prompt: str,
        image_bytes: bytes,
        mime_type: str = "image/jpeg",
        temperature: float = 0.1,
        max_tokens: int = 2000,
    ) -> str:
        """Run a single-image vision request against exactly one provider."""
        import base64
        from openai import BadRequestError

        target = next(
            (
                provider
                for provider in self._build_vision_provider_chain()
                if provider["name"].lower() == provider_name.strip().lower()
            ),
            None,
        )
        if target is None:
            raise RuntimeError(f"Vision provider '{provider_name}' is not configured")

        name = target["name"]
        client = target["client"]
        model = target["model"]
        attempts = [max_tokens, max(256, max_tokens // 2)]

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

        last_err = None
        for attempt_tokens in [max_tokens, max(256, max_tokens // 2)]:
            try:
                if name == "anthropic":
                    result = self._anthropic_vision(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                else:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                    result = response.choices[0].message.content or ""
                if result.strip():
                    logger.info("Strict vision success via %s", name)
                    return result
            except BadRequestError as e:
                last_err = e
                logger.warning("Strict vision failed via %s: %s", name, e)
            except Exception as e:
                last_err = e
                logger.warning("Strict vision failed via %s: %s", name, e)

        if last_err:
            raise last_err
        return ""

    def generate_vision_multi_strict_provider(
        self,
        *,
        provider_name: str,
        system_prompt: str,
        user_prompt: str,
        images: list[tuple[bytes, str]],
        temperature: float = 0.1,
        max_tokens: int = 4000,
    ) -> str:
        """Run a multi-image vision request against exactly one provider."""
        import base64
        from openai import BadRequestError

        target = next(
            (
                provider
                for provider in self._build_vision_provider_chain()
                if provider["name"].lower() == provider_name.strip().lower()
            ),
            None,
        )
        if target is None:
            raise RuntimeError(f"Vision provider '{provider_name}' is not configured")

        name = target["name"]
        client = target["client"]
        model = target["model"]

        content: list[dict] = []
        for img_bytes, mime in images:
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "high"},
                }
            )
        content.append({"type": "text", "text": user_prompt})
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ]

        last_err = None
        for attempt_tokens in [max_tokens, max(512, max_tokens // 2)]:
            try:
                if name == "anthropic":
                    result = self._anthropic_vision_multi(
                        model=model,
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        images=images,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                else:
                    response = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        temperature=temperature,
                        max_tokens=attempt_tokens,
                    )
                    result = response.choices[0].message.content or ""
                if result.strip():
                    logger.info("Strict multi-vision success via %s", name)
                    return result
            except BadRequestError as e:
                last_err = e
                logger.warning("Strict multi-vision failed via %s: %s", name, e)
            except Exception as e:
                last_err = e
                logger.warning("Strict multi-vision failed via %s: %s", name, e)

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
