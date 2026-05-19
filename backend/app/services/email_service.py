"""Transactional email via SMTP.

Reads SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM from
settings. When SMTP_HOST is empty the function logs and returns without
sending — callers (magic-link) still work in debug-code-only mode.

Port 465 uses implicit TLS (smtplib.SMTP_SSL). Port 587 uses STARTTLS
(smtplib.SMTP + starttls()). Both are supported; the selection is automatic.
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import logger

_MAGIC_LINK_SUBJECT = "Your AMI Trade sign-in code"

_MAGIC_LINK_HTML = """\
<html><body style="font-family:sans-serif;color:#e2e8f0;background:#0f172a;padding:24px">
  <p style="font-size:16px">Your <strong>AMI Trade</strong> sign-in code:</p>
  <p style="font-size:36px;font-weight:bold;letter-spacing:8px;color:#60a5fa">{code}</p>
  <p style="font-size:13px;color:#94a3b8">This code expires in 15 minutes.<br>
  If you didn't request this, you can ignore the email.</p>
</body></html>"""

_MAGIC_LINK_PLAIN = "Your AMI Trade sign-in code: {code}\n\nExpires in 15 minutes."


def send_magic_link(to: str, code: str) -> None:
    """Send a magic-link 6-digit code to `to`. No-op when SMTP is unconfigured."""
    if not settings.smtp_host:
        logger.info("smtp_not_configured_skip_email", to=to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = _MAGIC_LINK_SUBJECT
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(_MAGIC_LINK_PLAIN.format(code=code), "plain"))
    msg.attach(MIMEText(_MAGIC_LINK_HTML.format(code=code), "html"))

    context = ssl.create_default_context()
    try:
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, 465, context=context) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(msg["From"], to, msg.as_string())
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.sendmail(msg["From"], to, msg.as_string())
        logger.info("magic_link_email_sent", to=to)
    except Exception as exc:
        logger.warning("magic_link_email_failed", to=to, error=str(exc))
