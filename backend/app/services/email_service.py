"""Email service for sending verification and notification emails."""
import logging
import smtplib
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


def generate_verification_token() -> str:
    """Generate a secure random token for email verification."""
    return secrets.token_urlsafe(32)


def _get_verification_url(token: str) -> str:
    """Build the frontend verification URL."""
    # In production, use a proper domain; in dev, use localhost:5173
    base = "http://localhost:5173"
    return f"{base}/verify-email?token={token}"


def _build_verification_html(name: str, token: str, language: str = "de") -> str:
    """Build HTML email body for verification."""
    url = _get_verification_url(token)

    subjects = {
        "de": "Bitte bestätigen Sie Ihre E-Mail-Adresse",
        "en": "Please verify your email address",
        "zh": "请验证您的邮箱地址",
    }
    headings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
    }
    bodies = {
        "de": "Vielen Dank für Ihre Registrierung bei Taxja. Bitte klicken Sie auf den Button, um Ihre E-Mail-Adresse zu bestätigen.",
        "en": "Thank you for registering with Taxja. Please click the button below to verify your email address.",
        "zh": "感谢您注册 Taxja。请点击下方按钮验证您的邮箱地址。",
    }
    buttons = {
        "de": "E-Mail bestätigen",
        "en": "Verify Email",
        "zh": "验证邮箱",
    }
    footers = {
        "de": "Wenn Sie sich nicht bei Taxja registriert haben, können Sie diese E-Mail ignorieren.",
        "en": "If you did not register for Taxja, you can ignore this email.",
        "zh": "如果您没有注册 Taxja，请忽略此邮件。",
    }

    lang = language if language in subjects else "de"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <div style="text-align:center;margin-bottom:24px">
    <h2 style="color:#0ea5e9;margin:0">Taxja</h2>
  </div>
  <h3>{headings[lang]}</h3>
  <p style="line-height:1.6">{bodies[lang]}</p>
  <div style="text-align:center;margin:32px 0">
    <a href="{url}" style="display:inline-block;padding:14px 32px;background:#0ea5e9;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">{buttons[lang]}</a>
  </div>
  <p style="font-size:0.85rem;color:#64748b">{footers[lang]}</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">Taxja - Steuern einfach ja!</p>
</body></html>"""


def send_verification_email(email: str, name: str, token: str, language: str = "de") -> bool:
    """Send verification email. Returns True if sent successfully."""
    if not settings.ENABLE_EMAIL_NOTIFICATIONS:
        # Dev mode: log the verification URL instead of sending
        url = _get_verification_url(token)
        logger.info(f"[DEV] Verification email for {email}: {url}")
        print(f"\n{'='*60}")
        print(f"  EMAIL VERIFICATION (dev mode - no SMTP)")
        print(f"  To: {email}")
        print(f"  URL: {url}")
        print(f"{'='*60}\n")
        return True

    try:
        subjects = {
            "de": "Taxja: Bitte bestätigen Sie Ihre E-Mail-Adresse",
            "en": "Taxja: Please verify your email address",
            "zh": "Taxja: 请验证您的邮箱地址",
        }
        lang = language if language in subjects else "de"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subjects[lang]
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = email

        html = _build_verification_html(name, token, lang)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [email], msg.as_string())

        logger.info(f"Verification email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email to {email}: {e}")
        return False


def _get_reset_password_url(token: str) -> str:
    """Build the frontend password reset URL."""
    base = "http://localhost:5173"
    return f"{base}/reset-password?token={token}"


def _build_reset_password_html(name: str, token: str, language: str = "de") -> str:
    """Build HTML email body for password reset."""
    url = _get_reset_password_url(token)

    headings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
    }
    bodies = {
        "de": "Sie haben eine Passwort-Zurücksetzung für Ihr Taxja-Konto angefordert. Klicken Sie auf den Button, um ein neues Passwort festzulegen. Der Link ist 1 Stunde gültig.",
        "en": "You requested a password reset for your Taxja account. Click the button below to set a new password. This link is valid for 1 hour.",
        "zh": "您请求重置 Taxja 账户密码。请点击下方按钮设置新密码。链接有效期为 1 小时。",
    }
    buttons = {
        "de": "Passwort zurücksetzen",
        "en": "Reset Password",
        "zh": "重置密码",
    }
    footers = {
        "de": "Wenn Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.",
        "en": "If you did not request this, you can safely ignore this email.",
        "zh": "如果您没有请求重置密码，请忽略此邮件。",
    }

    lang = language if language in headings else "de"

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:520px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <div style="text-align:center;margin-bottom:24px">
    <h2 style="color:#0ea5e9;margin:0">Taxja</h2>
  </div>
  <h3>{headings[lang]}</h3>
  <p style="line-height:1.6">{bodies[lang]}</p>
  <div style="text-align:center;margin:32px 0">
    <a href="{url}" style="display:inline-block;padding:14px 32px;background:#0ea5e9;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">{buttons[lang]}</a>
  </div>
  <p style="font-size:0.85rem;color:#64748b">{footers[lang]}</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">Taxja - Steuern einfach ja!</p>
</body></html>"""


def send_password_reset_email(email: str, name: str, token: str, language: str = "de") -> bool:
    """Send password reset email. Returns True if sent successfully."""
    if not settings.ENABLE_EMAIL_NOTIFICATIONS:
        url = _get_reset_password_url(token)
        logger.info(f"[DEV] Password reset email for {email}: {url}")
        print(f"\n{'='*60}")
        print(f"  PASSWORD RESET (dev mode - no SMTP)")
        print(f"  To: {email}")
        print(f"  URL: {url}")
        print(f"{'='*60}\n")
        return True

    try:
        subjects = {
            "de": "Taxja: Passwort zurücksetzen",
            "en": "Taxja: Reset your password",
            "zh": "Taxja: 重置密码",
        }
        lang = language if language in subjects else "de"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subjects[lang]
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = email

        html = _build_reset_password_html(name, token, lang)
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [email], msg.as_string())

        logger.info(f"Password reset email sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email to {email}: {e}")
        return False
