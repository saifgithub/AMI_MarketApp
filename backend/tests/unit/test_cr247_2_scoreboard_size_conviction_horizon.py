"""CR247 Phase 2 items 2.1–2.3 — scoreboard SIZE column, conviction relabel,
horizon discipline line.

2.1: the parsed `argued_size_pct` (CR197, journaled on every transcript
entry) renders as its own SIZE column in `_room_scoreboard`, next to
STANCE/CONVICTION. Seats that never declare a size render '—' (design, not
gap); an officer that argued without declaring one renders `unparsed` — a
loud absence, never an invented figure.

2.2 (D4): one envelope token (CONVICTION) carries three role-specific
meanings. The relabel is header-level only — the envelope format is pinned
byte-for-byte below so a wording drift there fails the build — and the
scoreboard legend maps each Risk Officer seat to its name for the field:
"evidence strength" (Aggressive), "threat specificity" (Conservative),
"evidence clarity" (Balanced). Each debator persona carries the matching
one-sentence register note.

2.3: one mandate-derived horizon discipline line reaches exactly the five
agents that propose or weigh the trade (Execution Desk, the three Risk
Officers, the CIO), branched IN CODE on `mandate.horizon` — long horizons
demote short-term technicals to entry timing; other horizons get the
short-horizon counterpart. The analysts, researchers and Research Manager
get nothing (their overlays already branch, or their turn predates a
proposal), so their prompts stay byte-identical.

Nothing here touches the envelope format, sizing tiers, horizon day-counts,
or the decode budgets (`_LENGTH_GUIDE` / `_AGENT_MAX_TOKENS` pairings are
unchanged — these are input-block additions, and the PM's ask is untouched).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.schemas import AgentId, AgentMessage
from app.services.agent_prompts import load_base_prompt
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import (
    _STANCE_FORMAT,
    _STANCE_FORMAT_RISK,
    _room_scoreboard,
    build_room_messages,
)

TS = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)

_HORIZON_AGENTS = (
    AgentId.TRADER,
    AgentId.AGGRESSIVE_DEBATOR,
    AgentId.CONSERVATIVE_DEBATOR,
    AgentId.NEUTRAL_DEBATOR,
    AgentId.PORTFOLIO_MANAGER,
)

_NOT_HORIZON_AGENTS = (
    AgentId.FUNDAMENTALS_ANALYST,
    AgentId.MARKET_ANALYST,
    AgentId.NEWS_ANALYST,
    AgentId.SOCIAL_MEDIA_ANALYST,
    AgentId.BULL_RESEARCHER,
    AgentId.BEAR_RESEARCHER,
    AgentId.RESEARCH_MANAGER,
)


def _msg(agent_id, stance=None, conviction=None, headline=None, size=None):
    return AgentMessage(
        agent_id=agent_id, role="agent", content="prose body", timestamp=TS,
        stance=stance, conviction=conviction, headline=headline,
        argued_size_pct=size,
    )


def _room(horizon: str = "long"):
    return hydrate_coach_mandate(
        {"plan": "trader", "risk_score": 3, "horizon": horizon}
    )


def _prompt(agent_id, horizon: str = "long") -> str:
    sp, _ = build_room_messages(
        agent_id=agent_id,
        mandate=_room(horizon),
        user_id=None,
        ticker="AAPL",
        profile={"field_state": {}},
        transcript=[
            _msg(AgentId.TRADER, "for", "medium", "Entry on pullback"),
            _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "Cap leaves alpha", size=5.0),
            _msg(AgentId.CONSERVATIVE_DEBATOR, "against", "high", "Air pocket", size=1.0),
            _msg(AgentId.NEUTRAL_DEBATOR, "for", "low", "Half size", size=2.5),
        ],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0},
        agent_size_pct=3.0,
    )
    return sp


# ── 2.1 — the SIZE column ─────────────────────────────────────────────────────


def test_the_size_header_explains_the_column_in_one_clause():
    out = _room_scoreboard([
        _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0),
    ])
    assert "SIZE is the % of portfolio a seat declared in its stance line" in out


def test_a_declared_size_renders_in_the_size_column():
    out = _room_scoreboard([
        _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0),
        _msg(AgentId.FUNDAMENTALS_ANALYST, "for", "high", "x"),
    ])
    lines = {
        ln.split("  ")[0]: ln
        for ln in out.split("\n")
        if ln.startswith(("Risk Officer", "Fundamentals"))
    }
    officer = [c.strip() for c in re.split(r"\s{2,}", lines["Risk Officer — Aggressive"]) if c.strip()]
    analyst = [c.strip() for c in re.split(r"\s{2,}", lines["Fundamentals Analyst"]) if c.strip()]
    assert officer[1:4] == ["for", "5.0%", "high"]
    assert analyst[1:4] == ["for", "—", "high"]


def test_a_seat_that_never_declares_size_gets_the_design_dash_and_a_gloss():
    out = _room_scoreboard([_msg(AgentId.FUNDAMENTALS_ANALYST, "for", "high", "x")])
    assert "'—' is the design, not a gap" in out
    # The gloss names the seat that actually spoke.
    assert "Fundamentals Analyst: no position size had been proposed" in out


def test_an_officer_without_a_declared_size_is_unparsed_not_small():
    out = _room_scoreboard([
        _msg(AgentId.NEUTRAL_DEBATOR, "for", "low", "x"),
    ])
    assert "argued without declaring one" in out
    row = [ln for ln in out.split("\n") if ln.startswith("Risk Officer — Balanced")][0]
    assert "unparsed" in row


def test_no_size_is_ever_invented_for_a_non_officer():
    """The Desk's journaled size (it proposes one in prose, CR197 never asked
    it for an envelope size) must not leak into the column."""
    out = _room_scoreboard([_msg(AgentId.TRADER, "for", "high", "x", size=9.0)])
    row = [ln for ln in out.split("\n") if ln.startswith("Execution Desk")][0]
    assert "9.0%" not in row
    assert "—" in row


# ── 2.2 — the conviction relabel ──────────────────────────────────────────────


def test_the_conviction_legend_notes_one_envelope_three_names():
    out = _room_scoreboard([_msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0)])
    assert "The CONVICTION column is ONE envelope field under three seat-specific names" in out
    assert '"evidence strength"' in out


def test_all_three_seat_specific_names_render_when_all_officers_spoke():
    out = _room_scoreboard([
        _msg(AgentId.FUNDAMENTALS_ANALYST, "for", "high", "x"),
        _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0),
        _msg(AgentId.CONSERVATIVE_DEBATOR, "against", "high", "x", size=1.0),
        _msg(AgentId.NEUTRAL_DEBATOR, "for", "low", "x", size=2.5),
    ])
    for name in ("evidence strength", "threat specificity", "evidence clarity"):
        assert name in out
    # The plain-meaning line covers the non-officer seat that spoke.
    assert "conviction plain — how strongly it holds its stated view" in out


def test_the_plain_meaning_line_is_absent_when_only_officers_spoke():
    out = _room_scoreboard([
        _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0),
    ])
    assert "conviction plain" not in out


def test_the_table_header_keeps_the_envelope_token():
    """Header-level relabel, not a token rename: the column the parser feeds
    still reads CONVICTION."""
    out = _room_scoreboard([_msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0)])
    header = [ln for ln in out.split("\n") if ln.startswith("AGENT")][0]
    assert "CONVICTION" in header
    assert "SIZE" in header


def test_the_envelope_format_is_byte_pinned_unchanged():
    """2.2 is a header-level relabel only — the emitted token stays CONVICTION
    and the SIZE slot stays exactly where CR197 put it. Any wording drift in
    the envelope contract fails here, byte for byte."""
    assert _STANCE_FORMAT == (
        "\n\nBEFORE the thesis sentence, your VERY FIRST line must be this one line, "
        "in exactly this shape, with your prose starting on the line after it:\n"
        "[STANCE: for|against|neutral | CONVICTION: low|medium|high | "
        "HEADLINE: <max 32 characters>]\n"
        "- STANCE: your view on taking this position now — 'for', 'against', or "
        "'neutral' if you genuinely land in the middle.\n"
        "- CONVICTION: how strongly you hold that view.\n"
        "- HEADLINE: the single number or fact that carries your view, in your own "
        "words. Not a summary of your whole argument.\n"
        "- If your role this turn is not to take a side at all, write "
        "'STANCE: none'. Never guess a side to fill the field.\n"
        "- Write this line ONCE, at the top only. Do not repeat it at the end."
    )
    assert _STANCE_FORMAT_RISK == (
        "\n\nBEFORE the thesis sentence, your VERY FIRST line must be this one line, "
        "in exactly this shape, with your prose starting on the line after it:\n"
        "[STANCE: for|against|neutral | CONVICTION: low|medium|high | "
        "SIZE: <n.n>% | HEADLINE: <max 32 characters>]\n"
        "- STANCE: your view on taking this position now — 'for', 'against', or "
        "'neutral' if you genuinely land in the middle.\n"
        "- CONVICTION: how strongly you hold that view.\n"
        "- SIZE: the position size, as a % of the portfolio, that you actually "
        "endorse after reading the numbers in front of you. Your role was handed a "
        "reference figure; this field is where you say what you truly mean, which "
        "may be that same figure or may not. A number, with a % sign.\n"
        "- HEADLINE: the single number or fact that carries your view, in your own "
        "words. Not a summary of your whole argument.\n"
        "- If your role this turn is not to take a side at all, write "
        "'STANCE: none'. Never guess a side to fill the field.\n"
        "- Write this line ONCE, at the top only. Do not repeat it at the end."
    )


def test_each_debator_persona_names_its_relabelled_column():
    """The persona half of the relabel: each Risk Officer's register carries
    one sentence saying what its scoreboard column will be read as, so the
    producer and the consumer use one glossary. Whitespace-normalized: the
    persona source wraps long lines."""
    expected = {
        AgentId.AGGRESSIVE_DEBATOR: "evidence strength",
        AgentId.CONSERVATIVE_DEBATOR: "threat specificity",
        AgentId.NEUTRAL_DEBATOR: "evidence clarity",
    }
    for agent_id, name in expected.items():
        flat = re.sub(r"\s+", " ", load_base_prompt(agent_id))
        assert name in flat, f"{agent_id} persona lost its {name!r} sentence"
        assert "same envelope field" in flat, (
            f"{agent_id} persona does not say the relabel maps to one envelope"
        )


# ── 2.3 — the horizon discipline line ─────────────────────────────────────────


_LONG_LINE = (
    "- Horizon discipline: this mandate's horizon is long — short-term "
    "technical readings inform entry timing only; they cannot validate or "
    "invalidate the thesis."
)
_SHORT_LINE = (
    "- Horizon discipline: this mandate's horizon is short — position "
    "technicals carry weight per that horizon: they can validate or "
    "invalidate the thesis, not just time its entry."
)


def test_long_mandates_demote_short_term_technicals_for_the_five_trade_agents():
    for agent_id in _HORIZON_AGENTS:
        prompt = _prompt(agent_id, horizon="long")
        assert _LONG_LINE in prompt, agent_id
        assert _SHORT_LINE not in prompt, agent_id


def test_very_long_mandands_use_the_same_long_discipline():
    prompt = _prompt(AgentId.PORTFOLIO_MANAGER, horizon="very_long")
    assert "this mandate's horizon is very_long — short-term technical readings inform entry timing only" in prompt


def test_short_mandates_render_the_short_horizon_counterpart():
    for agent_id in _HORIZON_AGENTS:
        prompt = _prompt(agent_id, horizon="short")
        assert _SHORT_LINE in prompt, agent_id
        assert _LONG_LINE not in prompt, agent_id


def test_no_other_agent_gets_the_horizon_line():
    """The analysts' overlays already branch on horizon; the researchers and
    Research Manager speak before a proposal exists. Their prompts stay
    byte-identical — no horizon line leaks in."""
    for agent_id in _NOT_HORIZON_AGENTS:
        prompt = _prompt(agent_id, horizon="long")
        assert "Horizon discipline" not in prompt, agent_id


def test_the_horizon_line_is_mandate_derived_not_generic():
    """The branch is on the stored mandate value in code: the line names the
    mandate's own horizon, and no day-count is hardcoded anywhere in it."""
    for horizon in ("long", "short"):
        prompt = _prompt(AgentId.TRADER, horizon=horizon)
        line = [ln for ln in prompt.splitlines() if ln.startswith("- Horizon discipline")][0]
        assert f"this mandate's horizon is {horizon}" in line
        assert not re.search(r"\b\d{2,4}\s*days?\b", line)


def test_the_risk_officer_assembly_is_out_of_scope():
    """CR247 2.3 names the Trader, the three debators and the CIO. The
    structured Risk Officer (`build_risk_officer_messages`) is a separate
    assembly and gets nothing by this item."""
    from app.services.room_prompts import build_risk_officer_messages

    sp, _, _ = build_risk_officer_messages(
        mandate=_room("long"),
        ticker="AAPL",
        profile={"field_state": {}},
        transcript=[],
        trade_proposal={"size_pct": 3.0, "entry": 100.0, "stop": 94.0},
    )
    assert "Horizon discipline" not in sp
