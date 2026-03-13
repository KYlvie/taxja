"""
Email notification service using SMTP.

Sends transactional emails for events like depreciation generation,
subscription changes, and security alerts.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Lightweight SMTP email sender"""

    def send(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP.

        Returns True on success, False on failure (never raises).
        """
        if not settings.ENABLE_EMAIL_NOTIFICATIONS:
            logger.debug("Email notifications disabled, skipping send to %s", to_email)
            return False

        msg = MIMEMultipart("alternative")
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = to_email
        msg["Subject"] = subject

        if body_text:
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html", "utf-8"))

        try:
            if settings.SMTP_USE_TLS:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
                server.starttls()
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)

            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
            server.quit()
            logger.info("Email sent to %s: %s", to_email, subject)
            return True
        except Exception as e:
            logger.error("Failed to send email to %s: %s", to_email, e)
            return False

    # ── Convenience helpers ──────────────────────────────────────────

    def send_depreciation_notification(
        self, to_email: str, user_name: str, year: int, property_count: int, total_amount: float
    ) -> bool:
        subject = f"Taxja – Jahresabschreibung {year} generiert"
        body_html = (
            f"<p>Sehr geehrte/r {user_name},</p>"
            f"<p>Die automatische Abschreibung (AfA) für das Jahr <strong>{year}</strong> "
            f"wurde erfolgreich generiert.</p>"
            f"<p><strong>Zusammenfassung:</strong></p>"
            f"<ul>"
            f"<li>Anzahl Immobilien: {property_count}</li>"
            f"<li>Gesamtabschreibung: €{total_amount:,.2f}</li>"
            f"</ul>"
            f"<p>Sie können die Details in Ihrem "
            f"<a href='https://app.taxja.at/transactions'>Taxja-Dashboard</a> einsehen.</p>"
            f"<p>Mit freundlichen Grüßen,<br/>Ihr Taxja Team</p>"
        )
        body_text = (
            f"Sehr geehrte/r {user_name},\n\n"
            f"Die automatische Abschreibung (AfA) für {year} wurde generiert.\n"
            f"Immobilien: {property_count}, Gesamt: €{total_amount:,.2f}\n\n"
            f"Details: https://app.taxja.at/transactions\n\n"
            f"Ihr Taxja Team"
        )
        return self.send(to_email, subject, body_html, body_text)

    def send_subscription_confirmation(
        self, to_email: str, user_name: str, plan_name: str
    ) -> bool:
        subject = f"Taxja – Abo bestätigt: {plan_name}"
        body_html = (
            f"<p>Hallo {user_name},</p>"
            f"<p>Ihr <strong>{plan_name}</strong>-Abo ist jetzt aktiv.</p>"
            f"<p><a href='https://app.taxja.at/dashboard'>Zum Dashboard</a></p>"
            f"<p>Ihr Taxja Team</p>"
        )
        return self.send(to_email, subject, body_html)


# Module-level singleton
email_service = EmailService()
