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
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/verify-email?token={token}"


def _get_email_tagline(language: str = "de") -> str:
    """Get the localized email footer tagline."""
    taglines = {
        "de": "Taxja - Steuern einfach ja!",
        "en": "Taxja - Taxes made simple!",
        "zh": "Taxja - 轻松报税！",
        "fr": "Taxja - Les impôts en toute simplicité !",
        "ru": "Taxja - Налоги — это просто!",
        "hu": "Taxja - Adózás egyszerűen!",
        "pl": "Taxja - Podatki po prostu!",
        "tr": "Taxja - Vergiler artik kolay!",
        "bs": "Taxja - Porezi jednostavno!",
    }
    return taglines.get(language, taglines["de"])


def _build_verification_html(name: str, token: str, language: str = "de") -> str:
    """Build HTML email body for verification."""
    url = _get_verification_url(token)

    subjects = {
        "de": "Bitte bestätigen Sie Ihre E-Mail-Adresse",
        "en": "Please verify your email address",
        "zh": "请验证您的邮箱地址",
        "fr": "Vérifiez votre adresse e-mail — Taxja",
        "ru": "Подтвердите ваш email — Taxja",
        "hu": "Kérjük, erősítse meg e-mail címét — Taxja",
        "pl": "Proszę zweryfikować swój adres e-mail — Taxja",
        "tr": "Lutfen e-posta adresinizi dogrulayin — Taxja",
        "bs": "Molimo potvrdite vasu e-mail adresu — Taxja",
    }
    headings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
        "fr": f"Bonjour {name},",
        "ru": f"Здравствуйте, {name},",
        "hu": f"Kedves {name},",
        "pl": f"Witaj {name},",
        "tr": f"Merhaba {name},",
        "bs": f"Zdravo {name},",
    }
    bodies = {
        "de": "Vielen Dank für Ihre Registrierung bei Taxja. Bitte klicken Sie auf den Button, um Ihre E-Mail-Adresse zu bestätigen.",
        "en": "Thank you for registering with Taxja. Please click the button below to verify your email address.",
        "zh": "感谢您注册 Taxja。请点击下方按钮验证您的邮箱地址。",
        "fr": "Merci de vous être inscrit(e) sur Taxja. Veuillez cliquer sur le bouton ci-dessous pour vérifier votre adresse e-mail.",
        "ru": "Благодарим Вас за регистрацию в Taxja. Пожалуйста, нажмите на кнопку ниже, чтобы подтвердить Ваш адрес электронной почты.",
        "hu": "Köszönjük, hogy regisztrált a Taxja-ra. Kérjük, kattintson az alábbi gombra az e-mail cím megerősítéséhez.",
        "pl": "Dziękujemy za rejestrację w Taxja. Proszę kliknąć poniższy przycisk, aby zweryfikować swój adres e-mail.",
        "tr": "Taxja'ya kaydoldugunuz icin tesekkur ederiz. Lutfen e-posta adresinizi dogrulamak icin asagidaki dugmeye tiklayin.",
        "bs": "Hvala vam sto ste se registrovali na Taxja. Molimo kliknite na dugme ispod kako biste potvrdili vasu e-mail adresu.",
    }
    buttons = {
        "de": "E-Mail bestätigen",
        "en": "Verify Email",
        "zh": "验证邮箱",
        "fr": "Vérifier l'e-mail",
        "ru": "Подтвердить email",
        "hu": "E-mail megerősítése",
        "pl": "Zweryfikuj e-mail",
        "tr": "E-postayi dogrula",
        "bs": "Potvrdi e-mail",
    }
    footers = {
        "de": "Wenn Sie sich nicht bei Taxja registriert haben, können Sie diese E-Mail ignorieren.",
        "en": "If you did not register for Taxja, you can ignore this email.",
        "zh": "如果您没有注册 Taxja，请忽略此邮件。",
        "fr": "Si vous ne vous êtes pas inscrit(e) sur Taxja, vous pouvez ignorer cet e-mail.",
        "ru": "Если Вы не регистрировались в Taxja, Вы можете проигнорировать это письмо.",
        "hu": "Ha nem regisztrált a Taxja-ra, kérjük, hagyja figyelmen kívül ezt az e-mailt.",
        "pl": "Jeśli nie rejestrowałeś/aś się w Taxja, możesz zignorować tę wiadomość.",
        "tr": "Taxja'ya kaydolmadiysaniz bu e-postayi gormezden gelebilirsiniz.",
        "bs": "Ako se niste registrovali na Taxja, mozete zanemariti ovu e-poruku.",
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
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">{_get_email_tagline(lang)}</p>
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
            "fr": "Vérifiez votre adresse e-mail — Taxja",
            "ru": "Подтвердите ваш email — Taxja",
            "hu": "Taxja: Kérjük, erősítse meg e-mail címét",
            "pl": "Taxja: Proszę zweryfikować swój adres e-mail",
            "tr": "Taxja: Lutfen e-posta adresinizi dogrulayin",
            "bs": "Taxja: Molimo potvrdite vasu e-mail adresu",
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
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/reset-password?token={token}"


def _build_reset_password_html(name: str, token: str, language: str = "de") -> str:
    """Build HTML email body for password reset."""
    url = _get_reset_password_url(token)

    headings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
        "fr": f"Bonjour {name},",
        "ru": f"Здравствуйте, {name},",
        "hu": f"Kedves {name},",
        "pl": f"Witaj {name},",
        "tr": f"Merhaba {name},",
        "bs": f"Zdravo {name},",
    }
    bodies = {
        "de": "Sie haben eine Passwort-Zurücksetzung für Ihr Taxja-Konto angefordert. Klicken Sie auf den Button, um ein neues Passwort festzulegen. Der Link ist 1 Stunde gültig.",
        "en": "You requested a password reset for your Taxja account. Click the button below to set a new password. This link is valid for 1 hour.",
        "zh": "您请求重置 Taxja 账户密码。请点击下方按钮设置新密码。链接有效期为 1 小时。",
        "fr": "Vous avez demandé la réinitialisation du mot de passe de votre compte Taxja. Cliquez sur le bouton ci-dessous pour définir un nouveau mot de passe. Ce lien est valable pendant 1 heure.",
        "ru": "Вы запросили сброс пароля для Вашей учётной записи Taxja. Нажмите на кнопку ниже, чтобы установить новый пароль. Ссылка действительна в течение 1 часа.",
        "hu": "Jelszó-visszaállítást kért a Taxja fiókjához. Kattintson az alábbi gombra az új jelszó beállításához. A link 1 órán keresztül érvényes.",
        "pl": "Poprosiłeś/aś o zresetowanie hasła do konta Taxja. Kliknij poniższy przycisk, aby ustawić nowe hasło. Link jest ważny przez 1 godzinę.",
        "tr": "Taxja hesabiniz icin sifre sifirlama talebinde bulundunuz. Yeni bir sifre belirlemek icin asagidaki dugmeye tiklayin. Bu baglanti 1 saat gecerlidir.",
        "bs": "Zatrazili ste resetovanje lozinke za vas Taxja nalog. Kliknite na dugme ispod da postavite novu lozinku. Ovaj link vazi 1 sat.",
    }
    buttons = {
        "de": "Passwort zurücksetzen",
        "en": "Reset Password",
        "zh": "重置密码",
        "fr": "Réinitialiser le mot de passe",
        "ru": "Сбросить пароль",
        "hu": "Jelszó visszaállítása",
        "pl": "Zresetuj hasło",
        "tr": "Sifreyi sifirla",
        "bs": "Resetuj lozinku",
    }
    footers = {
        "de": "Wenn Sie diese Anfrage nicht gestellt haben, können Sie diese E-Mail ignorieren.",
        "en": "If you did not request this, you can safely ignore this email.",
        "zh": "如果您没有请求重置密码，请忽略此邮件。",
        "fr": "Si vous n'avez pas fait cette demande, vous pouvez ignorer cet e-mail en toute sécurité.",
        "ru": "Если Вы не запрашивали сброс пароля, Вы можете проигнорировать это письмо.",
        "hu": "Ha nem Ön kérte ezt, nyugodtan hagyja figyelmen kívül ezt az e-mailt.",
        "pl": "Jeśli nie prosiłeś/aś o to, możesz bezpiecznie zignorować tę wiadomość.",
        "tr": "Bu istekte bulunmadiysaniz bu e-postayi gormezden gelebilirsiniz.",
        "bs": "Ako niste zatrazili ovo, mozete sigurno zanemariti ovu e-poruku.",
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
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">{_get_email_tagline(lang)}</p>
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
            "fr": "Réinitialisation du mot de passe — Taxja",
            "ru": "Сброс пароля — Taxja",
            "hu": "Taxja: Jelszó visszaállítása",
            "pl": "Taxja: Zresetuj swoje hasło",
            "tr": "Taxja: Sifrenizi sifirlayin",
            "bs": "Taxja: Resetujte vasu lozinku",
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


def _normalize_email_language(language: str | None) -> str:
    supported = {"de", "en", "zh", "fr", "ru", "hu", "pl", "tr", "bs"}
    return language if language in supported else "de"


def _get_subscription_management_url() -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}/subscription/manage"


def _format_money_from_cents(amount_cents: int | None, currency: str | None) -> str:
    amount = (amount_cents or 0) / 100
    code = (currency or "EUR").upper()
    return f"{amount:.2f} {code}"


def _format_short_date(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.strftime("%Y-%m-%d")


def _send_html_email(email: str, subject: str, html: str, dev_label: str) -> bool:
    if not settings.ENABLE_EMAIL_NOTIFICATIONS:
        logger.info(f"[DEV] {dev_label} email for {email}: {subject}")
        print(f"\n{'='*60}")
        print(f"  {dev_label.upper()} (dev mode - no SMTP)")
        print(f"  To: {email}")
        print(f"  Subject: {subject}")
        print(f"{'='*60}\n")
        return True

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
        msg["To"] = email
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
            if settings.SMTP_USE_TLS:
                server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, [email], msg.as_string())

        logger.info("%s email sent to %s", dev_label, email)
        return True
    except Exception as e:
        logger.error("Failed to send %s email to %s: %s", dev_label, email, e)
        return False


def _build_subscription_notification_html(
    *,
    greeting: str,
    intro: str,
    items: list[tuple[str, str]],
    cta_label: str,
    cta_url: str,
    outro: str,
    language: str,
) -> str:
    items_html = "".join(
        f'<tr><td style="padding:8px 0;color:#64748b">{label}</td><td style="padding:8px 0;text-align:right;color:#0f172a;font-weight:600">{value}</td></tr>'
        for label, value in items
    )
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:system-ui,sans-serif;max-width:560px;margin:0 auto;padding:32px 16px;color:#1e293b">
  <div style="text-align:center;margin-bottom:24px">
    <h2 style="color:#0ea5e9;margin:0">Taxja</h2>
  </div>
  <h3 style="margin-bottom:12px">{greeting}</h3>
  <p style="line-height:1.6;margin:0 0 20px">{intro}</p>
  <table style="width:100%;border-collapse:collapse;background:#f8fafc;border:1px solid #e2e8f0;border-radius:12px;padding:12px 16px">
    {items_html}
  </table>
  <div style="text-align:center;margin:28px 0">
    <a href="{cta_url}" style="display:inline-block;padding:14px 28px;background:#0f172a;color:#fff;text-decoration:none;border-radius:8px;font-weight:600">{cta_label}</a>
  </div>
  <p style="line-height:1.6;color:#475569">{outro}</p>
  <hr style="border:none;border-top:1px solid #e2e8f0;margin:24px 0">
  <p style="font-size:0.75rem;color:#94a3b8;text-align:center">{_get_email_tagline(language)}</p>
</body></html>"""


def send_subscription_activated_email(
    email: str,
    name: str,
    plan_name: str,
    billing_cycle: str | None,
    current_period_end: datetime | None,
    language: str = "de",
) -> bool:
    lang = _normalize_email_language(language)
    subjects = {
        "de": "Taxja: Ihr Abonnement ist jetzt aktiv",
        "en": "Taxja: Your subscription is now active",
        "zh": "Taxja: 您的订阅已激活",
    }
    greetings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
    }
    intros = {
        "de": f"vielen Dank fuer Ihr Vertrauen. Ihr {plan_name}-Abo ist jetzt aktiv und Sie koennen alle freigeschalteten Funktionen sofort nutzen.",
        "en": f"thank you for subscribing. Your {plan_name} plan is now active and all included features are ready to use.",
        "zh": f"感谢您的订阅。您的 {plan_name} 套餐现已激活，相关功能可以立即使用。",
    }
    cycle_labels = {
        "de": {"monthly": "Monatlich", "yearly": "Jaehrlich", None: "-"},
        "en": {"monthly": "Monthly", "yearly": "Yearly", None: "-"},
        "zh": {"monthly": "按月", "yearly": "按年", None: "-"},
    }
    item_labels = {
        "de": ("Plan", "Abrechnung", "Naechste Verlaengerung"),
        "en": ("Plan", "Billing", "Next renewal"),
        "zh": ("套餐", "计费周期", "下次续费"),
    }
    ctas = {
        "de": "Abo verwalten",
        "en": "Manage subscription",
        "zh": "管理订阅",
    }
    outros = {
        "de": "Sie koennen Ihr Abonnement jederzeit in Ihrem Konto verwalten.",
        "en": "You can manage your subscription anytime from your account.",
        "zh": "您可以随时在账户中管理您的订阅。",
    }
    copy_lang = lang if lang in subjects else "en"
    labels = item_labels[copy_lang]
    html = _build_subscription_notification_html(
        greeting=greetings[copy_lang],
        intro=intros[copy_lang],
        items=[
            (labels[0], plan_name),
            (labels[1], cycle_labels[copy_lang].get(billing_cycle, "-")),
            (labels[2], _format_short_date(current_period_end)),
        ],
        cta_label=ctas[copy_lang],
        cta_url=_get_subscription_management_url(),
        outro=outros[copy_lang],
        language=lang,
    )
    return _send_html_email(email, subjects[copy_lang], html, "subscription activation")


def send_subscription_renewal_email(
    email: str,
    name: str,
    plan_name: str,
    amount_paid_cents: int | None,
    currency: str | None,
    current_period_end: datetime | None,
    invoice_url: str | None,
    language: str = "de",
) -> bool:
    lang = _normalize_email_language(language)
    subjects = {
        "de": "Taxja: Ihre Zahlung wurde bestaetigt",
        "en": "Taxja: Your payment was confirmed",
        "zh": "Taxja: 您的付款已确认",
    }
    greetings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
    }
    intros = {
        "de": f"wir haben Ihre Zahlung fuer Ihr {plan_name}-Abo erfolgreich erhalten.",
        "en": f"we successfully received your payment for the {plan_name} plan.",
        "zh": f"我们已成功收到您 {plan_name} 套餐的付款。",
    }
    item_labels = {
        "de": ("Plan", "Betrag", "Naechste Verlaengerung"),
        "en": ("Plan", "Amount", "Next renewal"),
        "zh": ("套餐", "金额", "下次续费"),
    }
    ctas = {
        "de": "Rechnung ansehen",
        "en": "View invoice",
        "zh": "查看账单",
    }
    outros = {
        "de": "Vielen Dank, dass Sie Taxja nutzen.",
        "en": "Thank you for using Taxja.",
        "zh": "感谢您使用 Taxja。",
    }
    copy_lang = lang if lang in subjects else "en"
    labels = item_labels[copy_lang]
    html = _build_subscription_notification_html(
        greeting=greetings[copy_lang],
        intro=intros[copy_lang],
        items=[
            (labels[0], plan_name),
            (labels[1], _format_money_from_cents(amount_paid_cents, currency)),
            (labels[2], _format_short_date(current_period_end)),
        ],
        cta_label=ctas[copy_lang],
        cta_url=invoice_url or _get_subscription_management_url(),
        outro=outros[copy_lang],
        language=lang,
    )
    return _send_html_email(email, subjects[copy_lang], html, "subscription renewal")


def send_subscription_payment_failed_email(
    email: str,
    name: str,
    plan_name: str,
    amount_due_cents: int | None,
    currency: str | None,
    invoice_url: str | None,
    language: str = "de",
) -> bool:
    lang = _normalize_email_language(language)
    subjects = {
        "de": "Taxja: Ihre Zahlung konnte nicht verarbeitet werden",
        "en": "Taxja: We could not process your payment",
        "zh": "Taxja: 您的付款未能成功处理",
    }
    greetings = {
        "de": f"Hallo {name},",
        "en": f"Hello {name},",
        "zh": f"{name}，您好！",
    }
    intros = {
        "de": f"wir konnten die aktuelle Zahlung fuer Ihr {plan_name}-Abo leider nicht abbuchen. Bitte pruefen Sie Ihre Zahlungsmethode, damit Ihr Zugang ohne Unterbrechung aktiv bleibt.",
        "en": f"we could not process the latest payment for your {plan_name} plan. Please review your payment method to keep access uninterrupted.",
        "zh": f"我们未能完成您 {plan_name} 套餐的本次付款。请检查付款方式，以免影响后续使用。",
    }
    item_labels = {
        "de": ("Plan", "Offener Betrag", "Aktion"),
        "en": ("Plan", "Outstanding amount", "Action"),
        "zh": ("套餐", "待支付金额", "处理方式"),
    }
    action_values = {
        "de": "Zahlungsmethode aktualisieren",
        "en": "Update payment method",
        "zh": "更新付款方式",
    }
    ctas = {
        "de": "Zahlung pruefen",
        "en": "Review payment",
        "zh": "检查付款",
    }
    outros = {
        "de": "Wenn Sie die Zahlung bereits aktualisiert haben, koennen Sie diese Nachricht ignorieren.",
        "en": "If you already updated your billing details, you can ignore this message.",
        "zh": "如果您已经更新了付款信息，可以忽略这封邮件。",
    }
    copy_lang = lang if lang in subjects else "en"
    labels = item_labels[copy_lang]
    html = _build_subscription_notification_html(
        greeting=greetings[copy_lang],
        intro=intros[copy_lang],
        items=[
            (labels[0], plan_name),
            (labels[1], _format_money_from_cents(amount_due_cents, currency)),
            (labels[2], action_values[copy_lang]),
        ],
        cta_label=ctas[copy_lang],
        cta_url=invoice_url or _get_subscription_management_url(),
        outro=outros[copy_lang],
        language=lang,
    )
    return _send_html_email(email, subjects[copy_lang], html, "subscription payment failed")
