"""
AI Tax Assistant API endpoints.
Uses RAG (knowledge base + user data + LLM) when OPENAI_API_KEY is configured,
falls back to rule-based responses otherwise.
"""
import logging
import json
from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, File, Form, status, BackgroundTasks
from sqlalchemy.orm import Session
from datetime import datetime

from app.db.base import get_db
from app.core.security import get_current_user
from app.api.deps import require_feature
from app.services.feature_gate_service import Feature
from app.services.credit_service import CreditService, InsufficientCreditsError
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


def _deduct_ai_conversation_credits(db: Session, user_id: int):
    """Deduct credits for one AI conversation or raise HTTP 402."""
    credit_service = CreditService(db, redis_client=None)
    try:
        deduction = credit_service.check_and_deduct(
            user_id=user_id,
            operation="ai_conversation",
        )
    except InsufficientCreditsError as e:
        raise HTTPException(
            status_code=402,
            detail=f"Insufficient credits: {e.required} required, {e.available} available",
        ) from e

    return credit_service, deduction


def _refund_ai_conversation_credits(
    db: Session,
    credit_service: CreditService,
    user_id: int,
    refund_key: str,
) -> None:
    """Persist AI credit refunds when processing fails after chat history was saved."""
    try:
        credit_service.refund_credits(
            user_id=user_id,
            operation="ai_conversation",
            reason="processing_failed",
            refund_key=refund_key,
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Failed to persist AI credit refund for user %s", user_id)

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


def _format_ai_context(context: dict | None) -> str:
    """Turn structured page/document context into a compact prompt block."""
    if not context:
        return ""

    allowed_keys = [
        "page",
        "documentId",
        "document_type_detected",
        "document_type",
        "suggestion_type",
        "candidate_month",
        "payroll_signal",
        "year",
        "user_employer_profile",
    ]
    parts: list[str] = []
    for key in allowed_keys:
        value = context.get(key)
        if value in (None, "", [], {}):
            continue
        parts.append(f"{key}: {value}")

    if not parts:
        return ""

    return "Workflow context:\n" + "\n".join(parts)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/chat",
    response_model=ChatResponse,
    dependencies=[Depends(require_feature(Feature.AI_ASSISTANT))],
)
def chat_with_assistant(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    message_in: ChatMessageCreate,
    response: Response,
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

    # --- Credit deduction ---
    credit_service, deduction = _deduct_ai_conversation_credits(
        db, current_user.id
    )

    chat_service = get_chat_history_service(db)

    enhanced_message = message_in.message
    context_block = _format_ai_context(message_in.context)
    if context_block:
        enhanced_message = f"{context_block}\n\nUser request:\n{message_in.message}"

    # Inject suggestion context if provided (for suggestion-aware chat responses)
    if message_in.suggestion_context:
        sc = message_in.suggestion_context
        suggestion_context_block = (
            f"\n[Suggestion Context]\n"
            f"The user has a pending '{sc.suggestion_type}' suggestion "
            f"from document #{sc.document_id}.\n"
            f"Key data: {sc.summary}\n"
        )
        if sc.pending_questions:
            suggestion_context_block += f"Unanswered questions: {', '.join(sc.pending_questions)}\n"
        suggestion_context_block += (
            "Answer the user's question in the context of this specific document/suggestion.\n"
        )
        enhanced_message = suggestion_context_block + "\n" + enhanced_message

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
    try:
        result = orchestrator.handle_message(
            message=enhanced_message,
            language=message_in.language,
            conversation_history=conversation_history,
        )
    except Exception:
        _refund_ai_conversation_credits(
            db=db,
            credit_service=credit_service,
            user_id=current_user.id,
            refund_key=f"refund:ai:{current_user.id}:{user_message.id}",
        )
        raise

    # Save assistant message
    assistant_message = chat_service.save_message(
        user_id=current_user.id,
        role=MessageRole.ASSISTANT,
        content=result.text,
        language=message_in.language,
    )

    response.headers["X-Credits-Remaining"] = str(
        deduction.balance_after.available_without_overage
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
        f"Benutzer: user_{user.id}",
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


@router.post(
    "/chat-with-file",
    response_model=ChatResponse,
    dependencies=[Depends(require_feature(Feature.AI_ASSISTANT))],
)
async def chat_with_file(
    *,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    message: str = Form(default=""),
    language: str = Form(default="de"),
    context: str = Form(default=""),
    response: Response = None,
):
    """
    Send a message with an attached file to the AI Tax Assistant.
    Supports images (JPG/PNG) and PDFs — runs OCR to extract text,
    then passes the content to the AI orchestrator alongside the user message.
    """
    # Whitelist supported languages
    if language not in ("de", "en", "zh"):
        language = "de"

    from app.services.ai_orchestrator import AIOrchestrator

    credit_service, deduction = _deduct_ai_conversation_credits(
        db, current_user.id
    )

    ALLOWED_TYPES = {
        "image/jpeg", "image/png", "image/gif", "image/webp",
        "application/pdf",
        "text/csv",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.ms-excel",
    }
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}",
        )

    file_content = await file.read()
    if len(file_content) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File too large. Maximum size is 10 MB.",
        )

    # Try to extract text from the file
    extracted_text = ""
    try:
        if file.content_type in (
            "image/jpeg", "image/png", "image/gif", "image/webp", "application/pdf",
        ):
            from app.services.ocr_engine import OCREngine
            engine = OCREngine()
            ocr_result = engine.process_document(file_content, mime_type=file.content_type)
            extracted_text = getattr(ocr_result, "raw_text", "") or ""
        elif file.content_type == "text/csv":
            extracted_text = file_content.decode("utf-8", errors="replace")[:5000]
    except Exception as e:
        logger.warning("Failed to extract text from uploaded file: %s", e)
        extracted_text = ""

    # Build the combined message
    file_context = f"[Attached file: {file.filename}]"
    if extracted_text:
        # Truncate to avoid overwhelming the model
        truncated = extracted_text[:3000]
        file_context += f"\n\nExtracted content:\n{truncated}"

    parsed_context = None
    if context.strip():
        try:
            parsed_context = json.loads(context)
        except json.JSONDecodeError:
            parsed_context = None

    combined_message = f"{file_context}\n\n{message}" if message.strip() else file_context
    context_block = _format_ai_context(parsed_context)
    if context_block:
        combined_message = f"{context_block}\n\n{combined_message}"

    chat_service = get_chat_history_service(db)

    # Save user message
    user_message = chat_service.save_message(
        user_id=current_user.id,
        role=MessageRole.USER,
        content=combined_message,
        language=language,
    )

    # Get conversation history
    recent_msgs = chat_service.get_conversation_history(
        user_id=current_user.id, limit=6, offset=0
    )
    conversation_history = [
        {"role": msg.role.value, "content": msg.content}
        for msg in reversed(recent_msgs)
    ]

    # Run through orchestrator
    orchestrator = AIOrchestrator(db=db, user_id=current_user.id)
    try:
        result = orchestrator.handle_message(
            message=combined_message,
            language=language,
            conversation_history=conversation_history,
        )
    except Exception:
        _refund_ai_conversation_credits(
            db=db,
            credit_service=credit_service,
            user_id=current_user.id,
            refund_key=f"refund:ai-file:{current_user.id}:{user_message.id}",
        )
        raise

    # Save assistant response
    assistant_message = chat_service.save_message(
        user_id=current_user.id,
        role=MessageRole.ASSISTANT,
        content=result.text,
        language=language,
    )

    if response is not None:
        response.headers["X-Credits-Remaining"] = str(
            deduction.balance_after.available_without_overage
        )

    return ChatResponse(
        message=result.text,
        message_id=assistant_message.id,
        timestamp=assistant_message.created_at,
        intent=result.intent.value if result.intent else None,
        data=result.data,
        suggestions=result.suggestions,
    )
