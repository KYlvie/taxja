"""Public contact form endpoint — no auth required."""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

CONTACT_RECIPIENT = "office@oohk.com"


class ContactRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    message: str = Field(..., min_length=10, max_length=5000)
    language: str = Field(default="en", pattern="^(zh|de|en)$")


def _build_contact_html(data: ContactRequest) -> str:
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:600px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <h2 style="color:#7c3aed;margin:0 0 24px">OOHK — New Contact Inquiry</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b;width:100px">Name</td>
        <td style="padding:8px 12px">{data.name}</td></tr>
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b">Email</td>
        <td style="padding:8px 12px"><a href="mailto:{data.email}">{data.email}</a></td></tr>
    <tr><td style="padding:8px 12px;font-weight:600;color:#64748b">Time</td>
        <td style="padding:8px 12px">{now}</td></tr>
  </table>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
  <div style="white-space:pre-wrap;line-height:1.6;background:#f8fafc;padding:16px;border-radius:8px">{data.message}</div>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
  <p style="font-size:0.75rem;color:#94a3b8">Sent via OOHK contact form</p>
</body></html>"""


def _build_confirmation_html(data: ContactRequest) -> str:
    texts = {
        "zh": {
            "subject": "OOHK — 我们已收到您的消息",
            "hi": f"{data.name}，您好！",
            "body": "感谢您联系 OOHK。我们已收到您的消息，会尽快回复您。",
            "footer": "此邮件由系统自动发送，请勿直接回复。",
        },
        "de": {
            "subject": "OOHK — Wir haben Ihre Nachricht erhalten",
            "hi": f"Hallo {data.name},",
            "body": "Vielen Dank fuer Ihre Nachricht an OOHK. Wir haben sie erhalten und melden uns so bald wie moeglich bei Ihnen.",
            "footer": "Diese E-Mail wurde automatisch versendet. Bitte antworten Sie nicht direkt.",
        },
        "en": {
            "subject": "OOHK — We received your message",
            "hi": f"Hello {data.name},",
            "body": "Thank you for reaching out to OOHK. We have received your message and will get back to you as soon as possible.",
            "footer": "This is an automated email. Please do not reply directly.",
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


@router.post("/contact")
def submit_contact(data: ContactRequest):
    """Public contact form — sends inquiry to office and confirmation to sender."""
    try:
        # 1. Send inquiry to office
        _send_mail(
            to=CONTACT_RECIPIENT,
            subject=f"OOHK Contact: {data.name}",
            html=_build_contact_html(data),
        )
        # 2. Send confirmation to the person who submitted
        lang_subjects = {
            "zh": "OOHK — 我们已收到您的消息",
            "de": "OOHK — Wir haben Ihre Nachricht erhalten",
            "en": "OOHK — We received your message",
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
        raise HTTPException(status_code=500, detail="Failed to send message")
