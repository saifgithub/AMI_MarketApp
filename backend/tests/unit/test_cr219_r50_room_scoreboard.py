"""CR219 R50 — the Room scoreboard is minted by AMI, not summarised by a model.

The stance envelopes are already machine-parsed per turn and carried on every
transcript entry (CR106 B2), then read back by the CIO only as prose buried in
eleven turns. This tabulates them in code and hands the table to the one agent
that must weigh the whole Room.

Two properties are worth pinning, and only two:

1. **Deterministic.** Same transcript in, same bytes out — asserted against an
   exact expected table, not against "contains". A scoreboard that drifts with
   dict ordering or float formatting is a number the CIO cannot rely on.

2. **A missing envelope is LOUD.** DEF251 measured ~20% of debator turns
   emitting no envelope at all. A scoreboard that silently dropped those rows
   would render a 9-agent Room as unanimous when two of its voices were never
   counted — manufacturing consensus out of a parser gap. That is the CR106
   T-SUM11 rule (count what STATED a view, never a total that always sums to
   the roster) and the CR040 degrade-loudly rule, in one table.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import AgentId, AgentMessage
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_prompts import _room_scoreboard, build_room_messages

TS = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def _msg(agent_id, stance=None, conviction=None, headline=None, role="agent",
         size=None):
    return AgentMessage(
        agent_id=agent_id, role=role, content="prose body", timestamp=TS,
        stance=stance, conviction=conviction, headline=headline,
        argued_size_pct=size,
    )


def _full_transcript():
    return [
        _msg(AgentId.MARKET_ANALYST, "for", "high", "Reclaimed the 200-day on volume"),
        _msg(AgentId.FUNDAMENTALS_ANALYST, "against", "medium", "Margins compressed 2 quarters"),
        _msg(AgentId.NEUTRAL_DEBATOR, "neutral", "low", "Wait for the print", size=2.0),
    ]


# ── deterministic, exact ──────────────────────────────────────────────────────


def test_the_table_is_exact_and_column_aligned():
    """Pinned byte for byte. Columns are padded to the widest cell, so a new
    agent with a longer display name reflows the table rather than breaking it
    — and this test says so out loud when it does.

    CR160: rows are labelled by DISPLAY name, matching `_format_transcript`, so
    the table and the transcript beneath it name the same speakers. A wire id
    here would resurface a retired name beside prose that uses the new one.
    """
    out = _room_scoreboard(_full_transcript())
    body = out.split("\n")
    assert body[2] == (
        "AGENT                    STANCE          CONVICTION  HEADLINE"
    )
    assert body[3] == "-----------------------  --------------  ----------  --------"
    assert body[4] == (
        "Technical Strategist     for             high        Reclaimed the 200-day on volume"
    )
    assert body[5] == (
        "Fundamentals Analyst     against         medium      Margins compressed 2 quarters"
    )
    assert body[6] == (
        "Risk Officer — Balanced  neutral @ 2.0%  low         Wait for the print"
    )


def test_the_same_transcript_renders_the_same_bytes():
    assert _room_scoreboard(_full_transcript()) == _room_scoreboard(_full_transcript())


def test_rows_follow_the_order_the_room_spoke_in():
    reordered = list(reversed(_full_transcript()))
    assert _room_scoreboard(reordered) != _room_scoreboard(_full_transcript())
    first_row = _room_scoreboard(reordered).split("\n")[4]
    assert first_row.startswith("Risk Officer — Balanced")


def test_an_empty_transcript_renders_nothing():
    assert _room_scoreboard([]) == ""


# ── a missing envelope is loud, never dropped (DEF251 / CR040) ────────────────


def test_a_malformed_envelope_renders_an_unparsed_row_in_position():
    """The row stays, in the order it spoke. Dropping it is what would let a
    parser gap read as agreement."""
    transcript = _full_transcript()
    transcript.insert(1, _msg(AgentId.AGGRESSIVE_DEBATOR))
    out = _room_scoreboard(transcript)
    rows = out.split("\n\nWhat STANCE")[0].split("\n")[4:]
    assert rows[1].startswith("Risk Officer — Aggressive")
    assert rows[1].count("unparsed") == 3  # stance, conviction and headline
    assert len([r for r in rows if r.strip()]) == 4  # nothing dropped


def test_the_caption_counts_only_agents_that_stated_a_view():
    transcript = _full_transcript() + [_msg(AgentId.BULL_RESEARCHER)]
    out = _room_scoreboard(transcript)
    assert "3 of 4 stated a view" in out
    assert "1 emitted no readable position" in out
    assert "absent, NOT neutral, and not evidence of agreement" in out


def test_a_full_room_caption_says_nothing_about_unparsed_rows():
    out = _room_scoreboard(_full_transcript())
    assert "3 of 3 stated a view." in out
    assert "unparsed" not in out


def test_a_partial_envelope_marks_only_the_missing_fields():
    """One mangled field costs one field — `parse_stance_envelope` reads them
    independently, and the table must not escalate a missing headline into a
    missing stance."""
    out = _room_scoreboard([_msg(AgentId.TRADER, "for", "high", None)])
    row = out.split("\n")[4]
    assert row.startswith("Execution Desk")
    assert "for" in row and "high" in row
    assert row.count("unparsed") == 1
    assert "1 of 1 stated a view." in out


def test_a_stance_with_no_conviction_still_counts_as_a_stated_view():
    out = _room_scoreboard([_msg(AgentId.TRADER, "against", None, "No setup")])
    assert "1 of 1 stated a view." in out


# ── only real voices are scored ───────────────────────────────────────────────


def test_non_agent_entries_are_not_voices_in_the_room():
    """A user or system entry landing in the denominator would understate how
    much of the Room actually spoke."""
    transcript = _full_transcript() + [_msg(AgentId.TRADER, role="user")]
    assert "3 of 3 stated a view." in _room_scoreboard(transcript)


# ── the copy the user might read says AMI ─────────────────────────────────────


def test_the_copy_names_ami_and_never_the_llm():
    out = _room_scoreboard(_full_transcript())
    assert "AMI" in out
    for banned in ("the LLM", "the AI", "the model"):
        assert banned not in out


def test_it_is_declared_a_tally_rather_than_another_voice():
    """R20's philosophy, stated in the block itself: AMI mints the aggregate,
    so the CIO does not read it as a thirteenth opinion."""
    out = _room_scoreboard(_full_transcript())
    assert "not a summary, and not another voice" in out


# ── DEF448: what a STANCE means differs by seat ───────────────────────────────

import re  # noqa: E402

_ALL_SEATS = [
    _msg(AgentId.FUNDAMENTALS_ANALYST, "for", "high", "x"),
    _msg(AgentId.MARKET_ANALYST, "for", "high", "x"),
    _msg(AgentId.NEWS_ANALYST, "neutral", "low", "x"),
    _msg(AgentId.SOCIAL_MEDIA_ANALYST, "against", "low", "x"),
    _msg(AgentId.BULL_RESEARCHER, "for", "high", "x"),
    _msg(AgentId.BEAR_RESEARCHER, "against", "high", "x"),
    _msg(AgentId.RESEARCH_MANAGER, "for", "medium", "x"),
    _msg(AgentId.TRADER, "for", "medium", "x"),
    _msg(AgentId.AGGRESSIVE_DEBATOR, "for", "high", "x", size=5.0),
    _msg(AgentId.CONSERVATIVE_DEBATOR, "against", "high", "x", size=1.0),
    _msg(AgentId.NEUTRAL_DEBATOR, "for", "low", "x", size=2.5),
]


def _legend(out):
    return out.split("What STANCE refers to in each seat")[1]


def test_a_full_room_gets_one_gloss_line_per_seat_group():
    legend = _legend(_room_scoreboard(_ALL_SEATS))
    lines = [ln for ln in legend.split("\n") if ln.startswith("- ")]
    assert lines[0].startswith(
        "- Fundamentals Analyst / Technical Strategist / Macro & Events / "
        "Flow & Positioning: a directional read"
    )
    assert lines[1].startswith("- Bull Researcher / Bear Researcher: argues the side")
    assert lines[2].startswith("- Research Manager: its recommended stance")
    assert "mandate" in lines[2]
    assert lines[3].startswith("- Execution Desk: whether to act")
    assert "HOLD/WAIT" in lines[3]
    assert lines[4].startswith(
        "- Risk Officer — Aggressive / Risk Officer — Conservative: stance is "
        "settled by role"
    )
    assert lines[5].startswith("- Risk Officer — Balanced: the one Risk Officer")
    assert len(lines) == 6


def test_the_legend_names_only_the_seats_that_spoke():
    legend = _legend(_room_scoreboard(_full_transcript()))
    assert "Technical Strategist / Fundamentals Analyst" not in legend
    assert "- Fundamentals Analyst / Technical Strategist: a directional read" in legend
    assert "- Risk Officer — Balanced:" in legend
    for absent in ("Bull Researcher", "Execution Desk", "Aggressive"):
        assert absent not in legend


def test_the_legend_forbids_a_tally_rather_than_offering_one():
    """CR106 T-VOTE: the seats are not equal votes, so the CIO gets a gloss,
    never a consensus figure — no 'N of M for', no stance next to a %."""
    out = _room_scoreboard(_ALL_SEATS)
    legend = _legend(out)
    assert "not equal votes, so do not add them up into a count or a percentage" in legend
    tally = re.compile(r"\d+\s*(of\s*\d+\s*)?(for|against|neutral)\b", re.I)
    assert not tally.search(legend)
    assert not re.search(r"(for|against|neutral)\W{0,3}\(?\d+(\.\d+)?%", legend, re.I)
    assert "consensus" not in out.lower()


def test_a_risk_officer_stance_carries_its_argued_size():
    """The SIZE is stripped from the prose with the envelope — the scoreboard
    is the only place the CIO can see it."""
    out = _room_scoreboard(_ALL_SEATS)
    assert "for @ 5.0%" in out
    assert "against @ 1.0%" in out
    assert "for @ 2.5%" in out


def test_a_missing_size_is_loud_and_only_officers_get_one():
    out = _room_scoreboard([
        _msg(AgentId.CONSERVATIVE_DEBATOR, "against", "high", "x"),
        _msg(AgentId.TRADER, "for", "high", "x", size=3.0),
    ])
    assert "against @ size unparsed" in out
    assert "@ 3.0%" not in out
    assert "1 emitted no readable position" not in out


def test_no_agent_rows_means_no_legend():
    assert _room_scoreboard([_msg(AgentId.TRADER, role="user")]) == ""


# ── wiring: the CIO gets it, the eleven arguing agents do not ─────────────────


def _prompt(agent_id):
    sp, _ = build_room_messages(
        agent_id=agent_id,
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        user_id=None, ticker="AAPL", profile={"field_state": {}},
        transcript=_full_transcript(),
    )
    return sp


def test_the_cio_prompt_carries_the_scoreboard_above_the_transcript():
    sp = _prompt(AgentId.PORTFOLIO_MANAGER)
    assert "Room scoreboard" in sp
    assert sp.index("Room scoreboard") < sp.index("Transcript so far:")


def test_the_arguing_agents_do_not_get_the_scoreboard():
    """Handing the aggregate to an agent whose turn is to state its OWN
    position replaces the judgement that turn exists to exercise — the same
    scoping CR197 gives the option ladder."""
    for agent_id in (
        AgentId.NEUTRAL_DEBATOR, AgentId.TRADER, AgentId.RESEARCH_MANAGER,
        AgentId.BULL_RESEARCHER,
    ):
        assert "Room scoreboard" not in _prompt(agent_id), agent_id
