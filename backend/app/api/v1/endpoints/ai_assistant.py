"""
AI Tax Assistant API endpoints.
Uses RAG (knowledge base + user data + LLM) when OPENAI_API_KEY is configured,
falls back to rule-based responses otherwise.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.base import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.chat_message import MessageRole
from app.schemas.ai_assistant import (
    ChatMessageCreate,
    ChatResponse,
    ChatMessageResponse,
    ConversationHistory,
)
from app.services.chat_history_service import get_chat_history_service

logger = logging.getLogger(__name__)

router = APIRouter()

# Disclaimers appended to every response
DISCLAIMERS = {
    "de": (
        "\n\n⚠️ **Haftungsausschluss**: Diese Antwort dient nur zu Informationszwecken "
        "und stellt keine Steuerberatung dar. Bitte verwenden Sie FinanzOnline für die "
        "Steuererklärung. Bei komplexen Fällen konsultieren Sie einen Steuerberater."
    ),
    "en": (
        "\n\n⚠️ **Disclaimer**: This response is for informational purposes only and "
        "does not constitute tax advice. Please use FinanzOnline for tax filing. "
        "For complex cases, consult a Steuerberater."
    ),
    "zh": (
        "\n\n⚠️ **免责声明**：本回答仅供参考，不构成税务咨询。"
        "请以FinanzOnline最终结果为准。复杂情况请咨询Steuerberater。"
    ),
}


# ---------------------------------------------------------------------------
# Rule-based fallback (kept for when no LLM key is configured)
# ---------------------------------------------------------------------------

def _generate_rule_based_response(message: str, language: str, user_context: dict) -> str:
    """Generate a rule-based response for common tax questions."""
    msg_lower = message.lower()

    if any(kw in msg_lower for kw in [
        "steuer", "tax", "bracket", "rate", "税率", "税", "einkommensteuer",
    ]):
        responses = {
            "de": (
                "Die österreichischen Einkommensteuersätze 2026 (USP):\n"
                "• €0 - €13.539: 0%\n• €13.539 - €21.992: 20%\n"
                "• €21.992 - €36.458: 30%\n• €36.458 - €70.365: 40%\n"
                "• €70.365 - €104.859: 48%\n• €104.859 - €1.000.000: 50%\n"
                "• Über €1.000.000: 55%"
            ),
            "en": (
                "Austrian income tax rates 2026 (USP):\n"
                "• €0 - €13,539: 0%\n• €13,539 - €21,992: 20%\n"
                "• €21,992 - €36,458: 30%\n• €36,458 - €70,365: 40%\n"
                "• €70,365 - €104,859: 48%\n• €104,859 - €1,000,000: 50%\n"
                "• Over €1,000,000: 55%"
            ),
            "zh": (
                "2026年奥地利所得税税率（USP）：\n"
                "• €0 - €13,539：0%\n• €13,539 - €21,992：20%\n"
                "• €21,992 - €36,458：30%\n• €36,458 - €70,365：40%\n"
                "• €70,365 - €104,859：48%\n• €104,859 - €1,000,000：50%\n"
                "• 超过€1,000,000：55%"
            ),
        }
        return responses.get(language, responses["de"])

    if any(kw in msg_lower for kw in [
        "vat", "ust", "umsatzsteuer", "mehrwertsteuer", "增值税", "小企业",
    ]):
        responses = {
            "de": (
                "Kleinunternehmerregelung: Umsatz bis €55.000 ist USt-befreit. "
                "Toleranzgrenze: €60.500. Standard-USt-Satz: 20%. Wohnungsvermietung: 10%."
            ),
            "en": (
                "Small business exemption: Turnover up to €55,000 is VAT-exempt. "
                "Tolerance: €60,500. Standard VAT: 20%. Residential rental: 10%."
            ),
            "zh": (
                "小企业免税：营业额不超过€55,000免征增值税。"
                "容忍阈值：€60,500。标准增值税率：20%。住宅租赁：10%。"
            ),
        }
        return responses.get(language, responses["de"])

    if any(kw in msg_lower for kw in [
        "svs", "sozialversicherung", "social insurance", "社保", "保险",
    ]):
        responses = {
            "de": (
                "SVS-Beiträge für Selbständige:\n"
                "• Krankenversicherung: 6,80%\n• Pensionsversicherung: 18,50%\n"
                "• Unfallversicherung: Fixbetrag\n• Selbständigenvorsorge: 1,53%\n"
                "Beiträge sind als Sonderausgaben absetzbar."
            ),
            "en": (
                "SVS contributions for self-employed:\n"
                "• Health insurance: 6.80%\n• Pension insurance: 18.50%\n"
                "• Accident insurance: Fixed amount\n• Self-employed provision: 1.53%\n"
                "Contributions are deductible as special expenses."
            ),
            "zh": (
                "自雇人员SVS社保缴费：\n"
                "• 医疗保险：6.80%\n• 养老保险：18.50%\n"
                "• 意外保险：固定金额\n• 自雇预备金：1.53%\n"
                "缴费可作为特殊支出抵扣。"
            ),
        }
        return responses.get(language, responses["de"])

    if any(kw in msg_lower for kw in [
        "absetz", "deduct", "abzug", "pendler", "home office", "抵扣", "扣除",
    ]):
        responses = {
            "de": (
                "Häufige Absetzbeträge:\n"
                "• Pendlerpauschale: je nach Entfernung\n"
                "• Home-Office-Pauschale: bis €300/Jahr\n"
                "• Familienbonus Plus: €2.000/Kind/Jahr\n"
                "• Alleinverdiener/Alleinerzieher-Absetzbetrag\n"
                "• Sonderausgaben (Versicherungen, Spenden)"
            ),
            "en": (
                "Common deductions:\n"
                "• Commuting allowance: Based on distance\n"
                "• Home office flat rate: Up to €300/year\n"
                "• Family bonus plus: €2,000/child/year\n"
                "• Sole earner/single parent deduction\n"
                "• Special expenses (insurance, donations)"
            ),
            "zh": (
                "常见抵扣项目：\n"
                "• 通勤补贴：根据距离\n"
                "• 居家办公补贴：最高€300/年\n"
                "• 家庭奖金Plus：€2,000/孩子/年\n"
                "• 单收入者/单亲抵扣\n"
                "• 特殊支出（保险、捐赠）"
            ),
        }
        return responses.get(language, responses["de"])

    # Default
    defaults = {
        "de": (
            "Ich bin der Taxja AI-Assistent und kann Ihnen bei österreichischen "
            "Steuerfragen helfen. Fragen Sie mich zu:\n"
            "• Einkommensteuersätze\n• Umsatzsteuer & Kleinunternehmerregelung\n"
            "• SVS-Sozialversicherung\n• Absetzbeträge & Abzüge\n"
            "• Ihre aktuelle Steuersituation"
        ),
        "en": (
            "I'm the Taxja AI assistant and can help with Austrian tax questions. "
            "Ask me about:\n• Income tax rates\n• VAT & small business exemption\n"
            "• SVS social insurance\n• Deductions & allowances\n"
            "• Your current tax situation"
        ),
        "zh": (
            "我是Taxja AI助手，可以帮助您解答奥地利税务问题。您可以问我：\n"
            "• 所得税税率\n• 增值税和小企业免税\n"
            "• SVS社保缴费\n• 抵扣和补贴\n"
            "• 您当前的税务情况"
        ),
    }
    return defaults.get(language, defaults["de"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/chat", response_model=ChatResponse)
def chat_with_assistant(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    message_in: ChatMessageCreate,
):
    """
    Send a message to the AI Tax Assistant.

    The orchestrator automatically detects intent and routes to the best handler:
    - Calculation requests → direct engine calls (instant, no LLM needed)
    - Tax Q&A → RAG (LLM + knowledge base + user data)
    - Deductibility / classification → specialized services
    - Fallback → rule-based responses
    """
    from app.services.ai_orchestrator import AIOrchestrator

    chat_service = get_chat_history_service(db)

    # Save user message
    user_message = chat_service.save_message(
        user_id=current_user.id,
        role=MessageRole.USER,
        content=message_in.message,
        language=message_in.language,
    )

    # Get conversation history for context
    recent_msgs = chat_service.get_conversation_history(
        user_id=current_user.id, limit=6, offset=0
    )
    conversation_history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in reversed(recent_msgs)
    ]

    # Run through orchestrator
    orchestrator = AIOrchestrator(db=db, user_id=current_user.id)
    result = orchestrator.handle_message(
        message=message_in.message,
        language=message_in.language,
        conversation_history=conversation_history,
    )

    # Save assistant message
    assistant_message = chat_service.save_message(
        user_id=current_user.id,
        role=MessageRole.ASSISTANT,
        content=result.text,
        language=message_in.language,
    )

    return ChatResponse(
        message=result.text,
        message_id=assistant_message.id,
        timestamp=assistant_message.created_at,
        intent=result.intent.value if result.intent else None,
        data=result.data,
        suggestions=result.suggestions,
    )


def _build_user_context(db: Session, user: User) -> str:
    """Build user financial context for personalized answers."""
    from app.models.transaction import Transaction
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Get recent transaction summary
    year = datetime.now().year
    start_date = datetime(year, 1, 1)
    
    income_total = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_type == "income",
        Transaction.date >= start_date,
    ).scalar() or 0
    
    expense_total = db.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user.id,
        Transaction.transaction_type == "expense",
        Transaction.date >= start_date,
    ).scalar() or 0
    
    # Get property count
    from app.models.property import Property
    property_count = db.query(func.count(Property.id)).filter(
        Property.user_id == user.id
    ).scalar() or 0
    
    context_parts = [
        f"Benutzer: {user.email}",
        f"Steuerjahr: {year}",
        f"Einkommen (YTD): €{income_total:,.2f}",
        f"Ausgaben (YTD): €{expense_total:,.2f}",
    ]
    
    if property_count > 0:
        context_parts.append(f"Immobilien: {property_count}")
    
    return "\n".join(context_parts)


@router.get("/history", response_model=ConversationHistory)
def get_chat_history(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
):
    """Get conversation history for the current user."""
    chat_service = get_chat_history_service(db)
    messages = chat_service.get_conversation_history(
        user_id=current_user.id, limit=limit, offset=offset
    )
    total_count = chat_service.get_message_count(user_id=current_user.id)
    has_more = (offset + len(messages)) < total_count

    return ConversationHistory(
        messages=[ChatMessageResponse.model_validate(msg) for msg in messages],
        total_count=total_count,
        has_more=has_more,
    )


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
def clear_chat_history(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Clear all chat history for the current user."""
    chat_service = get_chat_history_service(db)
    chat_service.clear_history(user_id=current_user.id)
