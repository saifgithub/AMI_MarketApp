"""CR266 — the card channel must be COMPLETE, not merely present.

Measured on the ami pilot, only 14/19 early rooms filed complete evidence:
`_cards_channel_absent` used to trigger repair only for zero-parseable-card
blocks, so partial blocks (missing items) and duplicated items were accepted
as-is — leaving exactly the holes the evidence gate's 20-card contract then
fails closed on. `_cards_channel_complete` is now the enforcement bar for
BOTH the initial repair trigger and the retry's adoption: a partial or
duplicated channel earns the same single bounded re-ask an absent one does,
and a still-incomplete retry is rejected, leaving the original state.

Gate OFF and non-card-desk behaviour are untouched (the whole block sits
behind `settings.room_cards_envelope_enabled`).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from app.core.config import settings
from app.schemas import AgentId
from app.services.room_runner import (
    _attempt_cards_repair,
    _cards_channel_complete,
    _compute_agent_text,
    parse_claim_cards,
)

# ── the completeness predicate ──────────────────────────────────────────────


def _cards(text: str):
    _, cards = parse_claim_cards(text)
    return cards


_COMPLETE = (
    "[CLAIMS]\n"
    "item=eq dir=support grade=well data=yes claim=c nums=1\n"
    "item=vc dir=support grade=partial data=yes claim=c nums=1\n"
    "item=vh dir=support grade=well data=yes claim=c nums=1\n"
    "item=bs dir=oppose grade=partial data=yes claim=c nums=1\n"
    "item=moat dir=support grade=well data=yes claim=c nums=1\n"
    "[/CLAIMS]"
)
_PARTIAL = (
    "[CLAIMS]\n"
    "item=eq dir=support grade=well data=yes claim=c nums=1\n"
    "item=vc dir=support grade=partial data=yes claim=c nums=1\n"
    "item=bs dir=oppose grade=partial data=yes claim=c nums=1\n"
    "[/CLAIMS]"
)
_DUPLICATE = (
    "[CLAIMS]\n"
    "item=eq dir=support grade=well data=yes claim=c nums=1\n"
    "item=eq dir=support grade=well data=yes claim=c nums=1\n"
    "item=vc dir=support grade=partial data=yes claim=c nums=1\n"
    "item=vh dir=support grade=well data=yes claim=c nums=1\n"
    "item=bs dir=oppose grade=partial data=yes claim=c nums=1\n"
    "item=moat dir=support grade=well data=yes claim=c nums=1\n"
    "[/CLAIMS]"
)


def test_complete_means_exactly_one_card_per_item_no_duplicates():
    assert _cards_channel_complete(_cards(_COMPLETE)) is True
    assert _cards_channel_complete(_cards(_PARTIAL)) is False  # vh/moat missing
    assert _cards_channel_complete(_cards(_DUPLICATE)) is False  # eq twice
    assert _cards_channel_complete(None) is False
    # A block whose lines all fail the grammar parses to zero cards.
    assert _cards_channel_complete(
        _cards("[CLAIMS]\ngarbage line\ngarbage line\n[/CLAIMS]")
    ) is False
    # A five-line block that is merely a reorder is still complete.
    reordered = (
        "[CLAIMS]\n"
        "item=moat dir=support grade=well data=yes claim=c nums=1\n"
        "item=bs dir=oppose grade=partial data=yes claim=c nums=1\n"
        "item=vh dir=support grade=well data=yes claim=c nums=1\n"
        "item=vc dir=support grade=partial data=yes claim=c nums=1\n"
        "item=eq dir=support grade=well data=yes claim=c nums=1\n"
        "[/CLAIMS]"
    )
    assert _cards_channel_complete(_cards(reordered)) is True


# ── the retry's adoption bar ────────────────────────────────────────────────


class _RepairGateway:
    """Serves one scripted reply per call, recording audit kwargs."""

    def __init__(self, replies: list[str]):
        self._replies = list(replies)
        self.calls: list[dict] = []

    def has_real_provider(self) -> bool:
        return True

    async def stream_chat(self, **kwargs):
        self.calls.append({"audit": kwargs})
        if self._replies:
            yield self._replies.pop(0)


def _repair_kwargs(gateway) -> dict:
    return {
        "gateway": gateway,  # type: ignore[arg-type]
        "system_prompt": "sys",
        "messages": [],
        "tier": None,
        "locale": "en",
        "user_id": uuid4(),
        "agent_id": AgentId.FUNDAMENTALS_ANALYST,
        "ticker": "AAPL",
        "max_tokens": 1024,
        "timeout_s": 30.0,
        "profile": {},
    }


def _msg_content(m) -> str:
    return str(getattr(m, "content", ""))


def test_a_complete_retry_is_adopted():
    gw = _RepairGateway([_COMPLETE])
    out = asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw)))
    assert out is not None
    prose, env, cards = out
    assert cards is not None and len(cards.cards) == 5
    assert gw.calls[0]["audit"]["audit_flow"] == "room_cards_repair"


def test_a_partial_retry_is_rejected_and_leaves_none():
    gw = _RepairGateway([_PARTIAL])
    assert asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw))) is None


def test_a_duplicate_retry_is_rejected_and_leaves_none():
    gw = _RepairGateway([_DUPLICATE])
    assert asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw))) is None


def test_a_retry_without_any_block_is_rejected_and_leaves_none():
    gw = _RepairGateway(["Just prose, no machine channel at all."])
    assert asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw))) is None


def test_the_repair_note_names_incomplete_and_the_exactly_five_rule():
    gw = _RepairGateway([_COMPLETE])
    asyncio.run(_attempt_cards_repair(**_repair_kwargs(gw)))
    note = _msg_content(gw.calls[0]["audit"]["messages"][-1])
    assert "did not carry a parseable CLAIMS block" in note
    assert "incomplete" in note
    assert "File all five items, one per line" in note
    assert "no duplicates" in note


# ── the initial trigger through _compute_agent_text ─────────────────────────


@pytest.fixture
def cards_envelope_on(monkeypatch):
    monkeypatch.setattr(settings, "room_cards_envelope_enabled", True)
    yield
    monkeypatch.undo()


def _ctx():
    from app.services.coach_engine import hydrate_coach_mandate
    from app.services.room_runner import _RoomContext

    mandate = hydrate_coach_mandate({"plan": "trader", "risk_score": 3})
    return _RoomContext(
        ticker="AAPL",
        mandate=mandate,
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        halal_universe=set(),
        classification_universe=None,
        locale_allowed_universe=None,
        user_id=uuid4(),
    )


def _turn(block: str) -> str:
    return (
        "[STANCE: for | CONVICTION: high | HEADLINE: the desk view]\n"
        "The desk analysis, argued in full.\n" + block
    )


def _run_agent(gateway):
    ctx = _ctx()
    text, *_ = asyncio.run(_compute_agent_text(
        agent_id=AgentId.FUNDAMENTALS_ANALYST, ctx=ctx, profile={},
        formatter={}, transcript=[], gateway=gateway, live=True,
        agent_timeout_s=30.0,
    ))
    return ctx, text


def test_a_partial_initial_channel_triggers_repair_and_adopts_a_complete_retry(
    cards_envelope_on,
):
    gw = _RepairGateway([_turn(_PARTIAL), _turn(_COMPLETE)])
    ctx, text = _run_agent(gw)

    flows = [c["audit"].get("audit_flow") for c in gw.calls]
    assert flows == ["room", "room_cards_repair"], flows
    assert len(ctx.claim_cards[AgentId.FUNDAMENTALS_ANALYST].cards) == 5
    assert "The desk analysis" in text


def test_a_duplicate_initial_channel_triggers_repair(cards_envelope_on):
    gw = _RepairGateway([_turn(_DUPLICATE), _turn(_COMPLETE)])
    ctx, _ = _run_agent(gw)

    flows = [c["audit"].get("audit_flow") for c in gw.calls]
    assert flows == ["room", "room_cards_repair"], flows
    assert len(ctx.claim_cards[AgentId.FUNDAMENTALS_ANALYST].cards) == 5


def test_a_complete_five_card_channel_never_repairs(cards_envelope_on):
    gw = _RepairGateway([_turn(_COMPLETE)])
    ctx, _ = _run_agent(gw)

    flows = [c["audit"].get("audit_flow") for c in gw.calls]
    assert flows == ["room"], flows
    assert len(ctx.claim_cards[AgentId.FUNDAMENTALS_ANALYST].cards) == 5


def test_a_still_partial_retry_leaves_the_original_turn(cards_envelope_on):
    gw = _RepairGateway([_turn(_PARTIAL), _turn(_PARTIAL)])
    ctx, text = _run_agent(gw)

    flows = [c["audit"].get("audit_flow") for c in gw.calls]
    assert flows == ["room", "room_cards_repair"], "exactly one repair"
    # The original PARTIAL channel stands (the incomplete retry is not
    # adopted): three cards, with the holes the evidence gate will fail
    # closed on — never a silently completed record.
    kept = ctx.claim_cards.get(AgentId.FUNDAMENTALS_ANALYST)
    assert kept is not None and len(kept.cards) == 3
    assert "The desk analysis" in text
