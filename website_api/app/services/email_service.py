"""Transactional email via the Resend HTTP API — ported approach from the backend.

Called through httpx directly (no `resend` SDK dep) to keep website_api lean.
Resend is the primary transport because melehost's ISP blocks outbound SMTP.

Degrades loudly-but-safely: when RESEND_API_KEY is unset (local/dev) sends are
logged and skipped, so the whole flow works without secrets. Send failures are
caught and logged — a failed email never breaks the request that triggered it
(the message/row is already stored first).
"""

from __future__ import annotations

from html import escape as html_escape

import httpx

from app.core.config import settings
from app.core.logging import logger

_RESEND_URL = "https://api.resend.com/emails"

# Appended to every user-facing email — never rely on the model to include it.
DISCLAIMER = (
    "AMI Trade is a simulation-only trading-education product. "
    "Nothing here is investment advice."
)


async def send_email(
    *,
    to: str,
    subject: str,
    html: str,
    text: str,
    reply_to: str | None = None,
) -> bool:
    """Send one email. Returns True on send, False on skip/failure."""
    if not settings.resend_api_key:
        logger.info("email_not_configured_skip", to=to, subject=subject)
        return False

    payload: dict[str, object] = {
        "from": settings.resend_from,
        "to": [to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if reply_to:
        payload["reply_to"] = reply_to

    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                _RESEND_URL,
                headers={"Authorization": f"Bearer {settings.resend_api_key}"},
                json=payload,
                timeout=15.0,
            )
        if resp.status_code >= 300:
            logger.warning(
                "email_send_failed", to=to, status=resp.status_code, body=resp.text[:200]
            )
            return False
        logger.info("email_sent", to=to, subject=subject)
        return True
    except Exception as exc:  # never let email break the request
        logger.warning("email_send_error", to=to, error=str(exc))
        return False


def _wrap(body_html: str) -> str:
    return (
        '<html><body style="font-family:sans-serif;color:#e2e8f0;background:#0f172a;'
        'padding:24px;line-height:1.5">'
        f"{body_html}"
        f'<hr style="border:none;border-top:1px solid #334155;margin:24px 0">'
        f'<p style="font-size:12px;color:#64748b">{DISCLAIMER}</p>'
        "</body></html>"
    )


async def send_contact_answer(*, to: str, question: str, answer: str) -> bool:
    """AI FAQ auto-answer. Always carries the disclaimer + human-escalation line."""
    html = _wrap(
        f'<p style="font-size:15px">Thanks for reaching out to AMI. Here\'s an answer '
        f"to your question:</p>"
        f'<blockquote style="color:#94a3b8;border-left:3px solid #3b82f6;padding-left:12px">'
        f"{answer}</blockquote>"
        f'<p style="font-size:13px;color:#94a3b8">Not what you needed? Just reply to this '
        f"email and a human on our team will pick it up.</p>"
    )
    text = (
        f"Thanks for reaching out to AMI.\n\n{answer}\n\n"
        f"Not what you needed? Reply to this email and a human will pick it up.\n\n"
        f"{DISCLAIMER}"
    )
    return await send_email(
        to=to, subject="Re: your question for AMI", html=html, text=text
    )


async def send_contact_ack(*, to: str) -> bool:
    """Plain 'we got it, a human will reply' acknowledgement."""
    html = _wrap(
        '<p style="font-size:15px">Thanks for reaching out to AMI — we\'ve received your '
        "message and a member of our team will get back to you shortly.</p>"
    )
    text = (
        "Thanks for reaching out to AMI. We've received your message and a member of "
        f"our team will get back to you shortly.\n\n{DISCLAIMER}"
    )
    return await send_email(to=to, subject="We received your message", html=html, text=text)


async def send_data_request_ack(*, to: str, request_type: str) -> bool:
    html = _wrap(
        f'<p style="font-size:15px">We\'ve received your <strong>{request_type}</strong> '
        "request and logged it. We’ll action it within 30 days, as required by "
        "applicable privacy law, and email you when it’s complete.</p>"
    )
    text = (
        f"We've received your {request_type} request and logged it. We'll action it "
        f"within 30 days and email you when it's complete.\n\n{DISCLAIMER}"
    )
    return await send_email(
        to=to, subject="Your data request has been received", html=html, text=text
    )


async def notify_team(*, subject: str, lines: list[str]) -> bool:
    """Internal notification to NOTIFY_EMAIL. No-op if unset."""
    if not settings.notify_email:
        logger.info("notify_skip", reason="no NOTIFY_EMAIL", subject=subject)
        return False
    # DEF372 (security review M6) — every line here is USER-AUTHORED (a
    # contact form's subject and body reach this verbatim), and it was
    # interpolated raw into an HTML email sent to the operator. A submitted
    # `<img src=x onerror=...>` or a crafted anchor renders in whoever opens
    # the notification — a stored XSS whose target is us, delivered by our own
    # mail. Escaped per line, then joined with the separator, so the <br> we
    # add stays real markup and nothing the user typed can become markup.
    body = "<br>".join(html_escape(line) for line in lines)
    return await send_email(
        to=settings.notify_email,
        subject=subject,
        html=f'<html><body style="font-family:sans-serif">{body}</body></html>',
        text="\n".join(lines),
    )
