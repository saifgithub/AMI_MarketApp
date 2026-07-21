"""Contact-form tests — store-first intake, AI-answer vs escalate, rate limit.

No LLM configured (no VLLM_BASE_URL), so 'answered' comes from a confident scripted
match and everything else escalates. Turnstile is bypassed (no secret set).
"""

from app.db.session import get_session
from app.models import ContactMessage


def _rows():
    """Materialize rows to plain dicts inside the session (avoid detached access)."""
    with get_session() as s:
        return [
            {"email": r.email, "status": r.status, "ai_answer": r.ai_answer}
            for r in s.query(ContactMessage).all()
        ]


def test_contact_auto_answers_faq(client):
    r = client.post("/contact", json={"email": "a@b.co", "message": "How much does it cost?"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "answered": True}
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["status"] == "answered"
    assert rows[0]["ai_answer"]


def test_contact_escalates_unknown_question(client):
    r = client.post("/contact", json={"email": "a@b.co", "message": "Do you have an affiliate program?"})
    assert r.status_code == 200
    assert r.json() == {"ok": True, "answered": False}
    assert _rows()[0]["status"] == "escalated"


def test_contact_advice_is_escalated(client):
    r = client.post("/contact", json={"email": "a@b.co", "message": "Should I buy Tesla?"})
    assert r.json()["answered"] is False
    assert _rows()[0]["status"] == "escalated"


def test_contact_stores_even_on_escalation(client):
    client.post("/contact", json={"email": "keep@me.co", "message": "random unmatched question here"})
    rows = _rows()
    assert len(rows) == 1
    assert rows[0]["email"] == "keep@me.co"


def test_contact_invalid_email(client):
    r = client.post("/contact", json={"email": "nope", "message": "hi there"})
    assert r.status_code == 422


def test_contact_rate_limited(client):
    body = {"email": "a@b.co", "message": "How much does it cost?"}
    codes = [client.post("/contact", json=body).status_code for _ in range(4)]
    assert codes[:3] == [200, 200, 200]
    assert codes[3] == 429
