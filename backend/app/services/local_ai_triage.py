"""
AI Triage Service — single Groq call for routing + answering.

One LLM call does everything:
  - System usage question → returns direct answer
  - Tax question → returns intent classification + extracted params

This replaces both the old regex intent detection AND the separate system help handler.
"""

import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

_TRIAGE_PROMPT = """\
You are Taxja AI assistant. Taxja is an Austrian tax management web app.

You must do TWO things in ONE response:
1. Classify the user's question
2. Either answer it (system help) or return structured intent (tax)

## If the user asks about HOW TO USE the app:
Answer directly using this knowledge, then add a line at the very end: [INTENT:system_help]

APP GUIDE:
- Documents: left menu→Documents. Upload(drag/click), PDF/JPG/PNG max 10MB. Auto OCR→classify→extract→suggest. Types: invoice,receipt,payslip(L16),tax forms(E1/L1/E1a/E1b/E1kv/U1/U30),Kaufvertrag,Mietvertrag,loan contract,bank statement,SVS,property tax,Jahresabschluss
- Transactions: left menu→Transactions. +New Transaction for income/expense. AI auto-classifies. Filter/search/export. Link to property
- Properties: left menu→Properties. +Add Property(real estate) or +Add Asset(vehicle/computer/furniture). Auto depreciation(AfA). Upload Kaufvertrag→auto-create property. Upload Mietvertrag→auto-create recurring rent
- Contracts: upload on Documents page. Kaufvertrag→auto property. Mietvertrag→auto rent. Loan→link to property
- Loans: property detail page. Record amount/rate/schedule. Interest deductible
- Tax Tools: left menu→Tax Tools. What-If simulator, flat-rate comparison, property reports
- Reports: left menu→Reports. Auto E/A reports, annual tax summary
- Settings: top-right avatar. Language(zh/de/en), password, user type
- Recurring: left menu→Recurring Transactions. Monthly auto(rent,insurance). Pause/resume
- Delete: transaction→detail→delete. Property→delete icon(impact warning). Document→detail→delete
- AI Assistant: left menu→AI Assistant. Tax questions, calculations, guidance

## If the user asks about TAX/FINANCE:
Do NOT answer the tax question. Instead return ONLY this JSON (nothing else):
{"intent":"<intent>","params":{<extracted_params>}}

Valid intents:
- calculate_tax: income tax calculation. Extract: {"income":<number>}
- calculate_vat: VAT calculation. Extract: {"amount":<number>,"rate":<number>}
- calculate_svs: social insurance. Extract: {"income":<number>}
- calculate_kest: capital gains tax. Extract: {"amount":<number>}
- calculate_immoest: real estate gains tax. Extract: {"amount":<number>}
- check_deduct: check if expense is deductible. Extract: {"description":"<what>"}
- classify_tx: classify a transaction. Extract: {"description":"<what>","amount":<number>}
- optimize_tax: tax saving tips. Extract: {}
- what_if: what-if simulation. Extract: {"change_type":"add_income|add_expense","amount":<number>}
- summarize_status: summarize tax situation. Extract: {}
- explain_doc: explain a document. Extract: {}
- tax_qa: general tax question (default if unsure). Extract: {}

RULES:
- Answer in user's language
- For system help: be concise with emoji+lists, end with [INTENT:system_help]
- For tax: return ONLY the JSON line, nothing else
- If unsure whether system or tax, treat as system help
- Extract numeric params when mentioned (e.g. "50000欧元" → income:50000)
"""


class AITriage:
    """Single Groq call for triage + intent classification + system help answers."""

    def process(self, message: str, language: str = "zh") -> Dict[str, Any]:
        """
        Process user message in a single LLM call.

        Returns dict with:
          - For system help: {"type": "system_help", "answer": "..."}
          - For tax: {"type": "tax", "intent": "calculate_tax", "params": {...}}
          - On failure: {"type": "fallback"}
        """
        try:
            from app.services.llm_service import get_llm_service
            llm = get_llm_service()
            if not llm.is_available:
                return {"type": "fallback"}

            content = llm.generate_simple(
                system_prompt=_TRIAGE_PROMPT,
                user_prompt=message,
                temperature=0.2,
                max_tokens=800,
            )

            if not content:
                return {"type": "fallback"}

            content = content.strip()

            # Try to parse as JSON (tax intent) — check this BEFORE system_help
            try:
                # Try direct JSON parse first (most common case)
                stripped = content.strip()
                if stripped.startswith("{"):
                    data = json.loads(stripped)
                    if "intent" in data:
                        intent = data.get("intent", "tax_qa")
                        params = data.get("params", {})
                        logger.info("AI triage: tax intent=%s params=%s", intent, params)
                        return {"type": "tax", "intent": intent, "params": params}
                # Fallback: find JSON embedded in text
                json_match = re.search(r'\{[^{}]*"intent"[^{}]*\}', content)
                if json_match:
                    data = json.loads(json_match.group())
                    intent = data.get("intent", "tax_qa")
                    params = data.get("params", {})
                    logger.info("AI triage: tax intent=%s params=%s", intent, params)
                    return {"type": "tax", "intent": intent, "params": params}
            except (json.JSONDecodeError, AttributeError):
                pass

            # Check if it's a system help answer (contains [INTENT:system_help])
            if "[INTENT:system_help]" in content:
                answer = content.replace("[INTENT:system_help]", "").strip()
                logger.info("AI triage: system_help (%d chars)", len(answer))
                return {"type": "system_help", "answer": answer}

            # If we can't parse as JSON and it's a long response, treat as system help
            if len(content) > 50:
                logger.info("AI triage: treating as system_help (unparsed)")
                return {"type": "system_help", "answer": content}

            return {"type": "fallback"}

        except Exception as e:
            logger.warning("AI triage failed: %s", e)
            return {"type": "fallback"}


_instance: Optional[AITriage] = None


# Intent name → UserIntent mapping (imported by orchestrator)
def _get_intent_map():
    from app.services.ai_orchestrator import UserIntent
    return {
        "calculate_tax": UserIntent.CALCULATE_TAX,
        "calculate_vat": UserIntent.CALCULATE_VAT,
        "calculate_svs": UserIntent.CALCULATE_SVS,
        "calculate_kest": UserIntent.CALCULATE_KEST,
        "calculate_immoest": UserIntent.CALCULATE_IMMOEST,
        "classify_tx": UserIntent.CLASSIFY_TRANSACTION,
        "check_deduct": UserIntent.CHECK_DEDUCTIBILITY,
        "optimize_tax": UserIntent.OPTIMIZE_TAX,
        "what_if": UserIntent.WHAT_IF,
        "explain_doc": UserIntent.EXPLAIN_DOCUMENT,
        "summarize_status": UserIntent.SUMMARIZE_STATUS,
        "system_help": UserIntent.SYSTEM_HELP,
        "tax_qa": UserIntent.TAX_QA,
    }

_INTENT_MAP = None


def get_intent_map():
    global _INTENT_MAP
    if _INTENT_MAP is None:
        _INTENT_MAP = _get_intent_map()
    return _INTENT_MAP


def get_ai_triage() -> AITriage:
    global _instance
    if _instance is None:
        _instance = AITriage()
    return _instance
