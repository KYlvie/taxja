"""Public contact form endpoint — no auth required."""
import html
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.core.error_messages import get_error_message
from app.core.rate_limiter import rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

CONTACT_RECIPIENT = settings.CONTACT_EMAIL


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=5000)
    language: str = Field(default="en", pattern="^(zh|de|en|fr|ru|hu|pl|tr|bs)$")


def _build_contact_html(data: ContactRequest) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    safe_name = html.escape(data.name)
    safe_email = html.escape(data.email)
    safe_message = html.escape(data.message)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <h2 style="color:#7c3aed;margin:0 0 24px">OOHK — New Contact Inquiry</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b;width:100px">Name</td>
        <td style="padding:8px 12px">{safe_name}</td></tr>
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b">Email</td>
        <td style="padding:8px 12px"><a href="mailto:{safe_email}">{safe_email}</a></td></tr>
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b">Time</td>
        <td style="padding:8px 12px">{now}</td></tr>
  </table>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
  <div style="white-space:pre-wrap;line-height:1.6;background:#f8fafc;padding:16px;border-radius:8px">{safe_message}</div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
  <p style="font-size:0.75rem;color:#94a3b8">Sent via OOHK contact form</p>
</body></html>"""


def _build_confirmation_html(data: ContactRequest) -> str:
    safe_name = html.escape(data.name)
    texts = {
        "zh": {
            "subject": "OOHK — 我们已收到您的消息",
            "hi": f"{safe_name}，您好！",
            "body": "感谢您联系 OOHK。我们已收到您的消息，会尽快回复您。",
            "footer": "此邮件由系统自动发送，请勿直接回复。",
        },
        "de": {
            "subject": "OOHK — Wir haben Ihre Nachricht erhalten",
            "hi": f"Hallo {safe_name},",
            "body": "Vielen Dank fuer Ihre Nachricht an OOHK. Wir haben sie erhalten und melden uns so bald wie moeglich bei Ihnen.",
            "footer": "Diese E-Mail wurde automatisch versendet. Bitte antworten Sie nicht direkt.",
        },
        "en": {
            "subject": "OOHK — We received your message",
            "hi": f"Hello {safe_name},",
            "body": "Thank you for reaching out to OOHK. We have received your message and will get back to you as soon as possible.",
            "footer": "This is an automated email. Please do not reply directly.",
        },
        "fr": {
            "subject": "OOHK — Nous avons reçu votre message",
            "hi": f"Bonjour {safe_name},",
            "body": "Merci de nous avoir contactés. Nous avons reçu votre message et vous répondrons dans les plus brefs délais.",
            "footer": "Cet e-mail a été envoyé automatiquement. Veuillez ne pas répondre directement.",
        },
        "ru": {
            "subject": "OOHK — Мы получили ваше сообщение",
            "hi": f"Здравствуйте, {safe_name},",
            "body": "Спасибо за обращение. Мы получили ваше сообщение и свяжемся с вами как можно скорее.",
            "footer": "Это автоматическое письмо. Пожалуйста, не отвечайте на него.",
        },
        "hu": {
            "subject": "OOHK — Megkaptuk az üzenetét",
            "hi": f"Kedves {safe_name},",
            "body": "Köszönjük, hogy kapcsolatba lépett velünk. Megkaptuk üzenetét, és a lehető leghamarabb válaszolunk.",
            "footer": "Ez egy automatikus e-mail. Kérjük, ne válaszoljon rá közvetlenül.",
        },
        "pl": {
            "subject": "OOHK — Otrzymaliśmy Twoją wiadomość",
            "hi": f"Witaj {safe_name},",
            "body": "Dziękujemy za kontakt. Otrzymaliśmy Twoją wiadomość i odpowiemy najszybciej jak to możliwe.",
            "footer": "To jest wiadomość automatyczna. Proszę nie odpowiadać bezpośrednio.",
        },
        "tr": {
            "subject": "OOHK — Mesajinizi aldik",
            "hi": f"Merhaba {safe_name},",
            "body": "OOHK ile iletisime gectiginiz icin tesekkur ederiz. Mesajinizi aldik ve en kisa surede size geri donecegiz.",
            "footer": "Bu otomatik bir e-postadir. Lutfen dogrudan yanit vermeyin.",
        },
        "bs": {
            "subject": "OOHK — Primili smo vasu poruku",
            "hi": f"Zdravo {safe_name},",
            "body": "Hvala vam sto ste nas kontaktirali. Primili smo vasu poruku i odgovorit cemo vam u najkracem roku.",
            "footer": "Ovo je automatska e-poruka. Molimo ne odgovarajte direktno.",
        },
    }
    t = texts.get(data.language, texts["en"])
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <div style="text-align:center;margin-bottom:24px">
    <h2 style="color:#7c3aed;margin:0">OOHK</h2>
  </div>
  <h3>{t["hi"]}</h3>
  <p style="line-height:1.6">{t["body"]}</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">{t["footer"]}</p>
</body></html>"""


def _send_mail(to: str, subject: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, [to], msg.as_string())


@router.post("/contact", dependencies=[Depends(rate_limit(max_requests=3, window_seconds=60))])
def submit_contact(data: ContactRequest):
    """Public contact form — sends inquiry to office and confirmation to sender."""
    try:
        # 1. Send inquiry to office
        _send_mail(
            to=CONTACT_RECIPIENT,
            subject=f"OOHK Contact: {html.escape(data.name)}",
            html=_build_contact_html(data),
        )
        # 2. Send confirmation to the person who submitted
        lang_subjects = {
            "zh": "OOHK — 我们已收到您的消息",
            "de": "OOHK — Wir haben Ihre Nachricht erhalten",
            "en": "OOHK — We received your message",
            "fr": "OOHK — Nous avons reçu votre message",
            "ru": "OOHK — Мы получили ваше сообщение",
            "hu": "OOHK — Megkaptuk az üzenetét",
            "pl": "OOHK — Otrzymaliśmy Twoją wiadomość",
            "tr": "OOHK — Mesajinizi aldik",
            "bs": "OOHK — Primili smo vasu poruku",
        }
        _send_mail(
            to=data.email,
            subject=lang_subjects.get(data.language, lang_subjects["en"]),
            html=_build_confirmation_html(data),
        )
        logger.info(f"Contact form submitted by {data.email}")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Contact form failed: {e}")
        language = data.language or "de"
        raise HTTPException(status_code=500, detail=get_error_message("failed_send_message", language))
