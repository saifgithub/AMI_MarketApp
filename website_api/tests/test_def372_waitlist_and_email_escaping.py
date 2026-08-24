"""DEF372 (security review M6 + M7) — the two open website_api findings.

**M6 — HTML injection into the operator notification email.** Every line
`notify_team` receives is user-authored (a contact form's subject and body
reach it verbatim) and was interpolated raw into an HTML email sent to
`NOTIFY_EMAIL`. A submitted `<img src=x onerror=…>` renders in whoever opens
the notification: a stored XSS whose target is us, delivered by our own mail.

**M7 — the waitlist had no limiter and no length caps** while every
neighbouring form (`/contact`, `/data_request`, `/concierge`) had one. It
writes a row per call, so unlimited meant an unbounded write amplifier and a
free way to fill the table with addresses nobody consented for.

M4 from the same review — Turnstile failing open on an unset secret — was
already fixed by DEF361 and is covered by its own test; verified, not
re-fixed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.rate_limit import waitlist_rate_limit


@pytest.fixture(autouse=True)
def _reset():
    waitlist_rate_limit.reset()
    yield
    waitlist_rate_limit.reset()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


# ── M6 — the operator's own inbox ────────────────────────────────────────


def test_user_text_cannot_become_markup_in_the_operator_email():
    import asyncio
    from unittest.mock import AsyncMock, patch

    from app.services import email_service

    with patch.object(email_service, "send_email", new=AsyncMock(return_value=True)) as sent, \
         patch.object(email_service.settings, "notify_email", "ops@example.com"):
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            email_service.notify_team(
                subject="New contact",
                lines=["from: a@b.c", '<img src=x onerror="alert(1)">'],
            )
        )
        html = sent.await_args.kwargs["html"]

    assert "<img" not in html, "a user-supplied tag must not survive as markup"
    assert "onerror" not in html or "&lt;img" in html
    assert "&lt;img" in html, "it should still be VISIBLE, escaped — not dropped"
    assert "<br>" in html, "our own separator stays real markup"


def test_the_plain_text_part_is_untouched():
    """Escaping belongs to the HTML part. Escaping the text part too would
    show the operator `&lt;img&gt;` in a plain-text reader, which is a
    different kind of wrong."""
    import asyncio
    from unittest.mock import AsyncMock, patch

    from app.services import email_service

    with patch.object(email_service, "send_email", new=AsyncMock(return_value=True)) as sent, \
         patch.object(email_service.settings, "notify_email", "ops@example.com"):
        asyncio.get_event_loop_policy().new_event_loop().run_until_complete(
            email_service.notify_team(subject="s", lines=["<b>hi</b>"])
        )
        assert sent.await_args.kwargs["text"] == "<b>hi</b>"


# ── M7 — the waitlist ────────────────────────────────────────────────────


def test_the_waitlist_is_rate_limited(client):
    """THE regression: unlimited writes. The limit is looser than contact's
    3/min because a person retrying a typo'd address should not be blocked,
    and this route sends no email."""
    codes = [
        client.post("/waitlist", json={"email": f"a{i}@example.com"}).status_code
        for i in range(15)
    ]
    assert 429 in codes, codes


def test_an_over_long_email_is_refused_before_it_reaches_the_database(client):
    r = client.post("/waitlist", json={"email": "a" * 400 + "@example.com"})
    assert r.status_code == 422, r.text


def test_an_over_long_source_is_refused(client):
    """`source` was never validated at all and goes straight to a DB column."""
    r = client.post(
        "/waitlist",
        json={"email": "ok@example.com", "source": "x" * 500},
    )
    assert r.status_code == 422, r.text


def test_a_normal_signup_still_works(client):
    """The cap must not break the ordinary path — the other way this goes
    wrong."""
    r = client.post("/waitlist", json={"email": "real@example.com", "source": "web"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True
