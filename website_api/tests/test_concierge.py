"""Concierge chatbot tests — no LLM configured, so the scripted/escalation paths run.

The deterministic escalation floor is the safety-critical bit: advice/compliance/
account/legal questions must NEVER reach the model, regardless of provider state.
"""

from app.services.faq_answer import classify_escalation


# ── Unit: the deterministic escalation floor ────────────────────────────────

def test_classify_advice():
    assert classify_escalation("Should I buy AAPL now?") == "advice"
    assert classify_escalation("Is Tesla a good investment?") == "advice"
    assert classify_escalation("what should i invest in") == "advice"


def test_classify_account():
    assert classify_escalation("I want a refund on my subscription") == "account"
    assert classify_escalation("I can't log in and need a password reset") == "account"


def test_classify_legal():
    assert classify_escalation("I want to delete my data under GDPR") == "legal"


def test_classify_compliance():
    """CR072/DEF084 — AMI runs no Sharia screen, so it never answers these itself."""
    for q in (
        "Is AAPL halal?",
        "Does AMI Trade do Sharia screening?",
        "is this shariah compliant",
        "Do you support Islamic investing?",
        "how is zakat purification calculated in the app",
        "Is Tesla a good halal buy?",  # advice-shaped too — compliance must win
    ):
        assert classify_escalation(q) == "compliance", q


def test_classify_safe():
    assert classify_escalation("How does AMI Trade work?") is None
    assert classify_escalation("How much does it cost?") is None


# ── Route: SSE streaming ────────────────────────────────────────────────────

def _sse_text(client, message):
    r = client.post("/concierge/message", json={"message": message})
    assert r.status_code == 200
    assert "event: done" in r.text
    return r.text


def test_advice_is_escalated_not_answered(client):
    text = _sse_text(client, "Should I buy AAPL now?")
    assert "buy/sell calls" in text            # the advice-escalation reply
    assert "final call" not in text            # NOT the scripted product pitch


def test_normal_question_scripted_reply(client):
    text = _sse_text(client, "How does AMI Trade work?")
    assert "analyst" in text.lower()
    # server-appended disclaimer, not left to the model
    assert "Simulation only" in text
    assert "not investment advice" in text


def test_account_question_escalated(client):
    text = _sse_text(client, "How do I cancel my subscription and get a refund?")
    assert "account" in text.lower()
    assert "support.ai@agenticmarketintel.ai" in text


def test_halal_question_never_asserts_a_screen(client):
    """The one answer that must not be left to a model — it's an observance decision."""
    text = _sse_text(client, "Is AAPL halal according to AMI Trade?")
    assert "does not run a Sharia compliance screen" in text
    assert "qualified scholar" in text
    # never the scripted product pitch, and never an implied screen
    assert "final call" not in text
    assert "we screen" not in text.lower()
