"""Website Concierge answer engine — shared by the chat widget and the contact form.

Structural safety floor (CR038: prompt instructions are NOT controls):

  1. `classify_escalation()` is a DETERMINISTIC pre-filter. Anything that reads as
     advice-seeking (buy/sell/price target/…), account-specific (billing, password,
     my subscription), or legal/privacy is NEVER auto-answered by the model — it is
     routed to a human regardless of what the LLM would say. This holds even if the
     model ignores its instructions.
  2. Everything the bot does say is grounded ONLY in `knowledge/faq.md`.
  3. The simulation-only / not-investment-advice disclaimer is appended by the server
     (here and in email_service), never left to the model to remember.

When the on-prem model is unavailable the engine returns a scripted KB reply rather
than a dead "offline" message (degrade loudly, CR040).
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from functools import lru_cache
from pathlib import Path

from app.core.logging import logger
from app.services.llm_client import ChatMessage, get_llm_client

_FAQ_PATH = Path(__file__).resolve().parent.parent / "knowledge" / "faq.md"

DISCLAIMER_LINE = "\n\n_Simulation only — not investment advice._"

SUPPORT_EMAIL = "support.ai@agenticmarketintel.ai"

# Sentinel the model is asked to emit when it can't answer from the FAQ.
_ESCALATE_SENTINEL = "ESCALATE"


# ── Deterministic escalation pre-filter (the safety floor) ──────────────────

# Advice-seeking: never auto-answer, never let the widget look like a stock tipster.
_ADVICE_RE = re.compile(
    r"\b(buy|sell|short|long|go long|should i (buy|sell|invest|trade)|"
    r"is it (a )?(good|bad) (buy|investment|time)|worth (it|buying|investing)|"
    r"(good|great|solid|smart|bad) (investment|buy|stock|pick|play)|"
    r"price target|will .* (go up|go down|rise|crash|moon|pump|dump)|"
    r"what should i (buy|invest|trade)|which stock|hot stock|stock tip|"
    r"portfolio allocation|how much should i (invest|put))\b",
    re.IGNORECASE,
)

# Account/billing-specific: needs the user's account — a human/self-serve flow.
_ACCOUNT_RE = re.compile(
    r"\b(my account|my subscription|my plan|my billing|refund|charge(d)?|"
    r"cancel( my)?|unsubscribe|password|can'?t (log|sign) ?in|reset|"
    r"upgrade|downgrade|invoice|receipt|payment)\b",
    re.IGNORECASE,
)

# Religious / values-based compliance. Its own category rather than a branch of
# `legal` because the honest answer is a product fact, not a data-rights pointer:
# DEF084 established the halal flag was a curated demonstration universe, not a
# screen, and CR069 tracks sourcing a real compliance indicator. Nothing here may
# be left to the model — a user asking "is X halal?" is making an observance
# decision, which is the one thing a confident-sounding wrong answer must never
# touch (CR038: prompt instructions are not controls).
_COMPLIANCE_RE = re.compile(
    r"\b(halal|haram|shari'?ah?|sharia|syariah|islamic (finance|investing|screen)|"
    r"riba|gharar|zakat|purification|aaoifi|sukuk|"
    r"(sharia|shariah|islamic|faith|values|ethical)[- ]?(compliant|compliance|screen(ing|ed)?))\b",
    re.IGNORECASE,
)

# Legal / privacy / data-rights: compliance-tracked, human only.
_LEGAL_RE = re.compile(
    r"\b(gdpr|ccpa|cpra|lawsuit|legal|complaint|regulat|delete my (data|account)|"
    r"data (deletion|request|access|erasure)|right to be forgotten|dpo|"
    r"data protection)\b",
    re.IGNORECASE,
)


def classify_escalation(message: str) -> str | None:
    """Return an escalation category ('advice'|'compliance'|'account'|'legal'), or None.

    Order matters: compliance is checked before advice so "is AAPL a good halal
    buy?" gets the accurate answer about what AMI does not screen, rather than the
    generic no-investment-advice line.
    """
    if _COMPLIANCE_RE.search(message):
        return "compliance"
    if _ADVICE_RE.search(message):
        return "advice"
    if _LEGAL_RE.search(message):
        return "legal"
    if _ACCOUNT_RE.search(message):
        return "account"
    return None


def escalation_reply(category: str) -> str:
    if category == "advice":
        return (
            "I can't help with buy/sell calls or investment advice — AMI Trade is a "
            "simulation-only training tool, not a brokerage. Questions about a specific "
            "stock are exactly what the in-app analyst team is built for. For anything "
            f"else, email {SUPPORT_EMAIL}."
        )
    if category == "compliance":
        return (
            "AMI Trade teaches Islamic finance — there's a 10-lesson track on Sharia "
            "investing principles — but it does not run a Sharia compliance screen, and "
            "it can't tell you whether a particular security is halal. Anything the app "
            "shows for teaching purposes is a curated demonstration set, not a screen, "
            "and nothing in AMI Trade is a ruling. For an observance decision, please "
            "consult a qualified scholar or a recognised screening provider. If you want "
            f"to know what we're building here, email {SUPPORT_EMAIL} and a human will "
            "answer."
        )
    if category == "legal":
        return (
            "For privacy, legal, or data requests, please use the Data Request form "
            f"(linked in the footer) or email {SUPPORT_EMAIL} — a human on our team "
            "handles these within 30 days."
        )
    # account
    return (
        "For anything about your account, subscription, or billing, please email "
        f"{SUPPORT_EMAIL} and a human will help. To access or delete your data, use "
        "the Data Request form in the footer."
    )


# ── KB + prompt ─────────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def load_faq() -> str:
    try:
        return _FAQ_PATH.read_text(encoding="utf-8")
    except Exception as exc:  # pragma: no cover - only if the file is missing
        logger.error("faq_load_failed", error=str(exc))
        return ""


def _system_prompt() -> str:
    return (
        "You are the AMI Concierge on the AMI marketing website. You help visitors "
        "understand AMI and AMI Trade. Always call the product AMI (never 'the AI').\n\n"
        "RULES:\n"
        "- Answer ONLY from the KNOWLEDGE below. Do not invent features, prices, dates, "
        "or numbers.\n"
        "- Never give investment, trading, or financial advice. Never discuss whether a "
        "specific stock is a good buy. AMI Trade is simulation-only.\n"
        "- Keep replies to 1–4 short sentences, friendly and concrete.\n"
        f"- If a question cannot be answered from the KNOWLEDGE, reply with exactly: "
        f"{_ESCALATE_SENTINEL}\n\n"
        "─── KNOWLEDGE ───\n"
        f"{load_faq()}"
    )


def _to_history(history: list[dict] | None) -> list[ChatMessage]:
    """Coerce client-supplied history into ChatMessages, capped and role-validated."""
    out: list[ChatMessage] = []
    for turn in (history or [])[-8:]:
        role = turn.get("role")
        content = (turn.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            out.append(ChatMessage(role=role, content=content[:2000]))
    return out


# ── Scripted fallback (no LLM) ──────────────────────────────────────────────

_SCRIPTED = [
    (re.compile(r"\b(price|cost|pricing|how much|free|subscription|tier|plan)\b", re.I),
     "AMI Trade is free to start on the Floor Pass tier. Two paid tiers — Trader and "
     "Floor Manager — unlock more, plus credit packs. Exact pricing is announced at launch."),
    (re.compile(r"\b(how (does|do) (it|ami|this) work|what (is|does)|agents?|analyst)\b", re.I),
     "AMI Trade puts a team of AI analyst agents in your pocket — they research and "
     "debate a stock (fundamentals, technicals, news, sentiment, a Bull and Bear, risk, "
     "and a Portfolio Manager), then you make the final call. It's simulation-only."),
    (re.compile(r"\b(start|sign ?up|get started|download|available|launch|waitlist)\b", re.I),
     "AMI Trade is preparing for launch — you can join the early-access waitlist right "
     "here on the site. Onboarding is anonymous-first; you set your goals up front."),
    (re.compile(r"\b(market|stock|us equit|country|region|language|platform|ios|android)\b", re.I),
     "At launch AMI Trade covers US equities on iOS and Android, in English. GCC/Bursa "
     "markets, Arabic, and Malay are planned for later."),
    (re.compile(r"\b(privacy|data|terms|policy)\b", re.I),
     "Our Privacy Policy and Terms are linked in the footer. To access or delete your "
     "data, use the Data Request form in the footer."),
]

_SCRIPTED_DEFAULT = (
    "AMI Trade is a simulation-only app where an AI analyst team debates a stock and you "
    f"make the final call. Ask me about how it works, pricing, or getting started — or "
    f"email {SUPPORT_EMAIL}."
)


def scripted_reply(message: str) -> tuple[str, bool]:
    """Deterministic KB reply. Returns (text, matched_confidently)."""
    for pattern, reply in _SCRIPTED:
        if pattern.search(message):
            return reply, True
    return _SCRIPTED_DEFAULT, False


# ── Public: chat streaming (concierge widget) ───────────────────────────────


async def stream_answer(
    message: str, history: list[dict] | None = None
) -> AsyncIterator[str]:
    """Yield the concierge's answer as text chunks, disclaimer appended at the end."""
    category = classify_escalation(message)
    if category:
        logger.info("concierge_escalate", category=category)
        yield escalation_reply(category)
        yield DISCLAIMER_LINE
        return

    client = get_llm_client()
    if client.available():
        got_text = False
        try:
            async for chunk in client.stream_chat(
                system_prompt=_system_prompt(),
                messages=_to_history(history) + [ChatMessage(role="user", content=message[:2000])],
                max_tokens=512,
            ):
                got_text = True
                yield chunk
        except Exception as exc:
            logger.warning("concierge_llm_error", error=str(exc))
            if not got_text:
                text, _ = scripted_reply(message)
                yield text
        else:
            if not got_text:
                text, _ = scripted_reply(message)
                yield text
        yield DISCLAIMER_LINE
        return

    # No model configured — scripted KB reply.
    text, _ = scripted_reply(message)
    yield text
    yield DISCLAIMER_LINE


# ── Public: single-shot answer (contact-form auto-answer) ───────────────────


async def answer_for_email(question: str) -> tuple[bool, str | None]:
    """Return (handled, answer). handled=False → route to a human instead."""
    if classify_escalation(question):
        return False, None

    client = get_llm_client()
    if client.available():
        try:
            answer = await client.complete(
                system_prompt=_system_prompt(),
                messages=[ChatMessage(role="user", content=question[:2000])],
                max_tokens=512,
            )
        except Exception as exc:
            logger.warning("email_answer_llm_error", error=str(exc))
            answer = ""
        if answer and _ESCALATE_SENTINEL not in answer.upper()[:20]:
            return True, answer
        return False, None

    # No model — only auto-answer if a scripted pattern matched confidently.
    text, matched = scripted_reply(question)
    if matched:
        return True, text
    return False, None
