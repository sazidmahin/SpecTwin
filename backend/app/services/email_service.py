from email.message import EmailMessage
from html import escape
import json
import logging
import smtplib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


logger = logging.getLogger(__name__)


class EmailDeliveryError(Exception):
    pass


def send_verification_code(*, email: str, code: str, full_name: str) -> None:
    subject = "Your SRS Diagram Platform verification code"
    body = (
        f"Hi {full_name},\n\n"
        f"Your verification code is: {code}\n\n"
        "This code expires soon. If you did not request this, you can ignore this email."
    )
    html = (
        f"<p>Hi {escape(full_name)},</p>"
        f"<p>Your verification code is: <strong style=\"font-size:20px;letter-spacing:4px\">{escape(code)}</strong></p>"
        "<p>This code expires soon. If you did not request this, you can ignore this email.</p>"
    )
    _deliver(
        to=email,
        subject=subject,
        text=body,
        html=html,
        console_line=f"[email verification] To: {email} Code: {code}",
    )


def send_password_reset(*, email: str, full_name: str, reset_url: str) -> None:
    subject = "Reset your SRS Diagram Platform password"
    expires = settings.password_reset_token_expire_minutes
    body = (
        f"Hi {full_name},\n\n"
        "We received a request to reset your password.\n\n"
        f"Set a new password: {reset_url}\n\n"
        f"This link expires in {expires} minutes. If you did not request this, you can ignore this email."
    )
    html = (
        f"<p>Hi {escape(full_name)},</p>"
        "<p>We received a request to reset your password.</p>"
        f"<p><a href=\"{escape(reset_url)}\" style=\"display:inline-block;padding:10px 18px;"
        "background:#4f46e5;color:#ffffff;border-radius:8px;text-decoration:none;font-weight:600\">"
        "Set a new password</a></p>"
        f"<p>Or open this link: <a href=\"{escape(reset_url)}\">{escape(reset_url)}</a></p>"
        f"<p>This link expires in {expires} minutes. If you did not request this, you can ignore this email.</p>"
    )
    _deliver(
        to=email,
        subject=subject,
        text=body,
        html=html,
        console_line=f"[password reset] To: {email} Link: {reset_url}",
    )


def send_workspace_invitation(
    *, email: str, workspace_name: str, inviter_name: str, role: str, invite_url: str
) -> None:
    subject = f"{inviter_name} invited you to join {workspace_name}"
    body = (
        "Hi,\n\n"
        f"{inviter_name} invited you to join the \"{workspace_name}\" workspace on "
        f"{settings.project_name} as {role}.\n\n"
        f"Accept the invitation: {invite_url}\n\n"
        "If you do not have an account yet, create one with this email address and the "
        "invitation will be waiting for you.\n\n"
        f"This invitation expires in {settings.workspace_invitation_expire_days} days. "
        "If you were not expecting it, you can ignore this email."
    )
    html = (
        "<p>Hi,</p>"
        f"<p><strong>{escape(inviter_name)}</strong> invited you to join the "
        f"<strong>{escape(workspace_name)}</strong> workspace on {escape(settings.project_name)} "
        f"as <strong>{escape(role)}</strong>.</p>"
        f"<p><a href=\"{escape(invite_url)}\" style=\"display:inline-block;padding:10px 18px;"
        "background:#4f46e5;color:#ffffff;border-radius:8px;text-decoration:none;font-weight:600\">"
        "Accept invitation</a></p>"
        f"<p>Or open this link: <a href=\"{escape(invite_url)}\">{escape(invite_url)}</a></p>"
        "<p>If you do not have an account yet, create one with this email address and the "
        "invitation will be waiting for you.</p>"
        f"<p>This invitation expires in {settings.workspace_invitation_expire_days} days. "
        "If you were not expecting it, you can ignore this email.</p>"
    )
    _deliver(
        to=email,
        subject=subject,
        text=body,
        html=html,
        console_line=f"[workspace invitation] To: {email} Link: {invite_url}",
    )


def _deliver(*, to: str, subject: str, text: str, html: str, console_line: str) -> None:
    if settings.email_delivery_mode == "console":
        print(console_line)
        return

    if settings.email_delivery_mode == "resend":
        _send_with_resend(to=to, subject=subject, text=text, html=html)
        return

    if settings.email_delivery_mode != "smtp":
        raise EmailDeliveryError("Unsupported email delivery mode")
    if not settings.smtp_host:
        raise EmailDeliveryError("SMTP_HOST is required for smtp email delivery")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = f"{settings.smtp_from_name} <{settings.smtp_from_email}>"
    message["To"] = to
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
        if settings.smtp_use_tls:
            smtp.starttls()
        if settings.smtp_username and settings.smtp_password:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)


def _send_with_resend(*, to: str, subject: str, text: str, html: str) -> None:
    """Send one email through the Resend HTTP API (https://resend.com/docs/api-reference/emails/send-email)."""
    if not settings.resend_api_key:
        raise EmailDeliveryError("RESEND_API_KEY is required for resend email delivery")

    payload = {
        "from": f"{settings.resend_from_name} <{settings.resend_from_email}>",
        "to": [to],
        "subject": subject,
        "text": text,
        "html": html,
    }
    request = Request(
        settings.resend_api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {settings.resend_api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            # Resend sits behind Cloudflare, which rejects urllib's default User-Agent.
            "User-Agent": "srs-diagram-platform/1.0",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=settings.resend_timeout_seconds) as response:
            response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        logger.error("Resend rejected the email to %s: HTTP %s %s", to, exc.code, detail)
        raise EmailDeliveryError("Could not send the email") from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.error("Could not reach Resend to email %s: %s", to, exc)
        raise EmailDeliveryError("Could not send the email") from exc
