"""Transactional email — Resend (primary) with SMTP fallback.

Priority:
  1. RESEND_API_KEY set → Resend HTTP API (immune to ISP port blocks)
  2. SMTP_HOST set      → smtplib (port 465 SSL / 587 STARTTLS)
  3. Neither            → log + no-op (alpha debug-code-only mode)
"""

from __future__ import annotations

import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend

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
    """Send a magic-link 6-digit code to `to`. No-op when neither Resend nor SMTP is configured."""
    if settings.resend_api_key:
        _send_via_resend(to, code)
    elif settings.smtp_host:
        _send_via_smtp(to, code)
    else:
        logger.info("email_not_configured_skip", to=to)


def _send_via_resend(to: str, code: str) -> None:
    resend.api_key = settings.resend_api_key
    from_addr = settings.smtp_from or "noreply@agenticmarketintel.ai"
    try:
        resend.Emails.send({
            "from": f"AMI Trade <{from_addr}>",
            "to": [to],
            "subject": _MAGIC_LINK_SUBJECT,
            "html": _MAGIC_LINK_HTML.format(code=code),
            "text": _MAGIC_LINK_PLAIN.format(code=code),
        })
        logger.info("magic_link_email_sent", to=to, transport="resend")
    except Exception as exc:
        logger.warning("magic_link_email_failed", to=to, transport="resend", error=str(exc))


def _send_via_smtp(to: str, code: str) -> None:
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
        logger.info("magic_link_email_sent", to=to, transport="smtp")
    except Exception as exc:
        logger.warning("magic_link_email_failed", to=to, transport="smtp", error=str(exc))


# ── CR095 — daily-challenge reminder ────────────────────────────────────────
#
# Free-tier channel (push is paid-tier only — see daily_reminder.py). AMI is
# named by name in every string here per CLAUDE.md's "the AI is called AMI"
# rule. New copy — flagged for ar/ms translation alongside the push strings
# in daily_reminder.py; there is no existing i18n plumbing for backend-
# generated push/email copy (the price-alert notify() call site CR027 shipped
# is English-only too), so this ships English-only like it, same as every
# other notify()/email call site in the codebase today.

_DAILY_REMINDER_SUBJECT = "Your AMI daily challenge is waiting"

_DAILY_REMINDER_HTML = """\
<html><body style="font-family:sans-serif;color:#e2e8f0;background:#0f172a;padding:24px">
  <p style="font-size:16px">Today's daily challenge from <strong>AMI</strong> is live:</p>
  <p style="font-size:18px;color:#60a5fa">{teaser}</p>
  <p style="font-size:13px;color:#94a3b8">Open the app to answer it before it resets.</p>
</body></html>"""

_DAILY_REMINDER_PLAIN = (
    "Today's daily challenge from AMI is live: {teaser}\n\n"
    "Open the app to answer it before it resets."
)


def send_daily_reminder(to: str, teaser: str) -> bool:
    """Send the daily-challenge reminder email. `teaser` is a short,
    pre-truncated preview of today's challenge question.

    Returns True when a transport (Resend or SMTP) was configured and the
    send was attempted, False when neither is configured (the same
    debug-no-op mode `send_magic_link` falls into). CR095's
    `daily_reminder.send_due_reminders` uses this return value to tell
    "we emailed them" apart from "there was no channel at all" — delivery
    success *within* a configured transport is still best-effort/logged
    only, same contract as `send_magic_link`.
    """
    if settings.resend_api_key:
        _send_daily_reminder_via_resend(to, teaser)
        return True
    elif settings.smtp_host:
        _send_daily_reminder_via_smtp(to, teaser)
        return True
    else:
        logger.info("daily_reminder_email_not_configured_skip", to=to)
        return False


def _send_daily_reminder_via_resend(to: str, teaser: str) -> None:
    resend.api_key = settings.resend_api_key
    from_addr = settings.smtp_from or "noreply@agenticmarketintel.ai"
    try:
        resend.Emails.send({
            "from": f"AMI Trade <{from_addr}>",
            "to": [to],
            "subject": _DAILY_REMINDER_SUBJECT,
            "html": _DAILY_REMINDER_HTML.format(teaser=teaser),
            "text": _DAILY_REMINDER_PLAIN.format(teaser=teaser),
        })
        logger.info("daily_reminder_email_sent", to=to, transport="resend")
    except Exception as exc:
        logger.warning("daily_reminder_email_failed", to=to, transport="resend", error=str(exc))


def _send_daily_reminder_via_smtp(to: str, teaser: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = _DAILY_REMINDER_SUBJECT
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg.attach(MIMEText(_DAILY_REMINDER_PLAIN.format(teaser=teaser), "plain"))
    msg.attach(MIMEText(_DAILY_REMINDER_HTML.format(teaser=teaser), "html"))

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
        logger.info("daily_reminder_email_sent", to=to, transport="smtp")
    except Exception as exc:
        logger.warning("daily_reminder_email_failed", to=to, transport="smtp", error=str(exc))
