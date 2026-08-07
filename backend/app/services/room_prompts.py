"""Convene the Room — per-agent prompt composition.

Each agent in a Room run gets a system prompt that combines:
  1. The agent's base prompt (loaded from content/agents/<id>.md and
     wrapped with the user's mandate overlay + safety floor where
     applicable — handled by `agent_prompts.build_agent_prompt`).
  2. A "Room addition" block with the ticker profile, the running
     transcript so far, and a task framing for the current phase.

The user message is a short kickoff ("Convene on AAPL.") — all the real
context lives in the system prompt. This mirrors how `agent_runner`
streams 1-on-1: same gateway, same `ChatMessage` shape, drop-in.

When `gateway.has_real_provider()` is False, callers should fall back
to scripted text from `room_runner._TEMPLATES`. That path keeps the
demo working when the LAN vLLM box is unreachable.
"""

from __future__ import annotations

from typing import Any

from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.mandate import Plan
from app.services.agent_prompts import build_agent_prompt
from app.services.fundamentals import pe_line, peg_part
from app.services.journal_context import build_journal_context_block
from app.services.llm_gateway import ChatMessage
from app.services.technicals import range_position_pct
from app.trading_math.risk import drawdown_contribution
from app.trading_math.sizing import resolved_single_name_cap_pct
from app.trading_math.valuation import net_position_phrase

# ── Phase framing ────────────────────────────────────────────────────────


def _field_is_live(profile: dict[str, Any], key: str) -> bool:
    """CR104/D8: the single provenance check every `(LIVE)` label must pass
    through — no exceptions. A field renders as live only when `field_state`
    (populated in `room_runner._profile_for_ticker`, never by presence alone)
    actually recorded it as such. Round-1 left five render sites checking
    presence only (`if profile.get(...)`), which the round-2 audit rendered
    a `field_state={}` profile against and got four confidently-labelled
    `(LIVE)` lines under a header promising the opposite."""
    return (profile.get("field_state") or {}).get(key) == "live"


_PHASE_FOR_AGENT: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "ANALYSTS",
    AgentId.MARKET_ANALYST: "ANALYSTS",
    AgentId.NEWS_ANALYST: "ANALYSTS",
    AgentId.SOCIAL_MEDIA_ANALYST: "ANALYSTS",
    AgentId.BULL_RESEARCHER: "RESEARCHERS",
    AgentId.BEAR_RESEARCHER: "RESEARCHERS",
    AgentId.RESEARCH_MANAGER: "SYNTHESIS",
    AgentId.TRADER: "EXECUTION",
    AgentId.AGGRESSIVE_DEBATOR: "RISK",
    AgentId.CONSERVATIVE_DEBATOR: "RISK",
    AgentId.NEUTRAL_DEBATOR: "RISK",
    AgentId.PORTFOLIO_MANAGER: "VERDICT",
}


# Soft length budgets per phase (kept short — Matrix Console UI is
# token-paced and the user reads each agent's full contribution before
# the next speaks).
_LENGTH_GUIDE: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "2–4 sentences",
    AgentId.MARKET_ANALYST: "2–4 sentences",
    AgentId.NEWS_ANALYST: "2–3 sentences",
    AgentId.SOCIAL_MEDIA_ANALYST: "2–3 sentences",
    AgentId.BULL_RESEARCHER: "3–5 sentences (thesis + evidence + falsifier)",
    AgentId.BEAR_RESEARCHER: "3–5 sentences (risk + quantification + invalidator)",
    AgentId.RESEARCH_MANAGER: "4–6 sentences (asymmetry numbers + lean + size implication)",
    AgentId.TRADER: "3–4 sentences (instrument + side + size + entry + stop + target + horizon)",
    AgentId.AGGRESSIVE_DEBATOR: "2 sentences (size push + one-line reason)",
    AgentId.CONSERVATIVE_DEBATOR: "2 sentences (size cap + one-line reason)",
    AgentId.NEUTRAL_DEBATOR: "2 sentences (middle size + one-line reason)",
    AgentId.PORTFOLIO_MANAGER: "3–4 sentences inside your JSON verdict's narration field — see the format instruction below",
}


# DEF125 — the decode budget that pays for the ask above, per agent.
#
# One flat `max_tokens=400` served all 11 streamed agents until 2026-07-29, and
# it did not fit what three of them were asked for. Measured on melehost's
# `llm_audit` (flow='room', error IS NULL, 30 days, ~884 calls/agent; "cut off"
# = the stored text ends on an alphanumeric, i.e. no terminal punctuation):
#
#   research_manager  584/884 = 66.1%   (max 1,880 chars, avg 1,573)
#   bull_researcher   536/885 = 60.6%   (max 1,966 chars, avg 1,550)
#   bear_researcher   226/884 = 25.6%   (max 1,806 chars, avg 1,383)
#   neutral_debator    61/883 =  6.9%
#   trader             19/884 =  2.1%
#   fundamentals       5/885  =  0.6%
#   everything else   ≤1/885  = ≤0.1%
#
# ~1,900 chars ≈ 400 tokens at this model's ratio, and the three worst agents'
# AVERAGES sit against their maxima — the signature of a distribution pinned at
# a ceiling rather than one that happens to be long.
#
# Sized here rather than in `room_runner` deliberately: the ask (`_LENGTH_GUIDE`)
# and the budget that has to pay for it drifted apart precisely because they
# lived in different files. `test_def125_*` fails the build if an agent gains a
# length guide without a budget.
#
# **Why the floor is 600 and not 400 (AT:R65, corrected 2026-07-29).**
#
# The first pass held the five agents measured at ≤0.1% down at 400, on the
# stated grounds that vLLM reserves KV-cache blocks against `max_tokens` when
# scheduling, so headroom would cost concurrency. **That was asserted, not
# measured, and it is wrong for this deployment.** Measured against the host's
# own `/metrics`: `num_preemptions_total` 0, `num_requests_waiting_by_reason
# {reason="capacity"}` 0, `gpu_memory_utilization` 0.5, `num_gpu_blocks` 1664
# against a 262k `max_model_len`. A convene is ~12 requests. Capacity has never
# been the binding constraint on this box, so an unused ceiling costs nothing —
# `max_tokens` is a ceiling, not an allocation, and decode is paid per token
# actually generated.
#
# With the cost gone, the asymmetry decides it: being twenty tokens short
# amputates a turn mid-sentence and — since CR106 B2 — silently costs that
# agent's stance too, because the trailing envelope is the last thing written
# and a cut turn never reaches it. Unused headroom costs nothing. So the floor
# is 600, which is ~75% clear of the 1,531-char (~322-token) worst case those
# five have ever produced, instead of ~15%.
#
# That B2 tail is itself new since the 30-day measurement above: every agent's
# effective budget shrank by ~15-25 tokens the day the envelope shipped, which
# the original numbers do not account for.
_DEFAULT_AGENT_MAX_TOKENS = 600

_AGENT_MAX_TOKENS: dict[AgentId, int] = {
    AgentId.FUNDAMENTALS_ANALYST: 600,
    AgentId.MARKET_ANALYST: 600,
    AgentId.NEWS_ANALYST: 600,
    AgentId.SOCIAL_MEDIA_ANALYST: 600,
    # Thesis + evidence + falsifier, in three-to-five sentences, and both
    # researchers write to the same shape — budget them symmetrically so the
    # Bear case is never the shorter one for a reason the reader cannot see.
    AgentId.BULL_RESEARCHER: 800,
    AgentId.BEAR_RESEARCHER: 800,
    # The worst case and the most damaging: the RM's synthesis is the single
    # input EXECUTION and RISK reason from (DEF095 — the transcript is the
    # contagion vector), and it was cut off in two convenes out of three.
    AgentId.RESEARCH_MANAGER: 900,
    # Only 2.1%, but a truncated Trader loses the level triple that
    # `_LEVEL_PATTERNS` and the whole downstream geometry depend on — the one
    # agent where a cut tail is unparseable rather than merely incomplete.
    AgentId.TRADER: 600,
    AgentId.AGGRESSIVE_DEBATOR: 600,
    AgentId.CONSERVATIVE_DEBATOR: 600,
    AgentId.NEUTRAL_DEBATOR: 600,
    # The PM emits a JSON envelope, not prose, and DEF058 (verdict fails to
    # parse in ~22% of runs) suspected its own 600-token cap clipping the JSON
    # one line from the end. Same family, one line apart in the source.
    AgentId.PORTFOLIO_MANAGER: 900,
}


def max_tokens_for(agent_id: AgentId) -> int:
    """DEF125 — the decode budget for one Room agent's turn.

    Falls back to the flat legacy value for an agent id with no entry rather
    than raising: a new agent should stream at the old budget, not fail to
    speak. The parity test is what stops that fallback becoming permanent.
    """
    return _AGENT_MAX_TOKENS.get(agent_id, _DEFAULT_AGENT_MAX_TOKENS)


# ── Public ───────────────────────────────────────────────────────────────


# PM speaks last and its output is the binding Verdict (DEF056) — it gets a
# structured JSON format instead of the free prose every other agent writes.
# `enforce_safety_floor()` (app/agents/safety_floor.py) re-checks whatever
# action the PM picks; this instruction just tells it the vocabulary and
# shape we can actually parse.
_PM_VERDICT_FORMAT = (
    "\nYou are the final decision-maker. Weigh everything above — every "
    "analyst, the Bull/Bear debate, the Trader's proposal, and the three "
    "Risk Debators — then decide for yourself. Do not just restate the "
    "Trader's numbers; agree or disagree based on the whole debate.\n"
    "This output format REPLACES the 'Verdict:' / 'Output format' block "
    "described earlier in your profile. In the Room you answer here, and only "
    "here.\n"
    "Your ENTIRE reply must be one single JSON object — begin with '{' and "
    "end with '}'. Do not write any prose outside the JSON (your reasoning "
    "belongs inside the narration field); anything outside it is discarded "
    "and your verdict is lost. Shape it exactly like:\n"
    '{"action": "APPROVE" | "PASS",\n'
    ' "size_pct": <number, required if APPROVE — position size as % of portfolio>,\n'
    ' "entry": <number, required if APPROVE>,\n'
    ' "stop": <number, required if APPROVE>,\n'
    ' "target": <number, required if APPROVE>,\n'
    ' "horizon_days": <integer, required if APPROVE>,\n'
    ' "narration": "<3-4 sentences, your rationale, written for the user>"}\n'
    "There are exactly two action values: APPROVE and PASS. A modification IS "
    "an approval — if you want to cut the Trader's size, tighten the stop, or "
    "shift the entry, use action APPROVE with your revised numbers in "
    "size_pct/entry/stop and explain the change in narration. Do NOT write "
    "'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are discarded "
    "and your verdict is lost.\n"
    "Use PASS when the debate does not support entering a position right now "
    "(e.g. the Trader recommended WAIT, or the risk/reward doesn't clear the "
    "bar) — PASS needs only narration, no size/entry/stop/target.\n"
    "The safety floor above still applies regardless of what you decide — "
    "if it detects a violation, output PASS and name the rule in narration."
)

_PROSE_FORMAT = (
    "\nFormat: lead with a one-sentence thesis, then short bullet "
    "points for supporting evidence. Use **bold** for key metrics "
    "(numbers, levels, deadlines). Plain text otherwise — no headings, "
    "no tables, no code fences. The Markdown is rendered live in the app."
)


# CR106 B2 — the per-agent stance envelope, as a TRAILING LINE rather than a
# JSON wrapper around the prose.
#
# The CR proposed wrapping each turn in `{"stance": …, "body": "<the prose>"}`,
# following the PM's JSON precedent. Deliberately not built that way, for one
# reason: **failure mode**. The PM's envelope is never shown to the user raw —
# `_parse_pm_verdict` extracts a narration and a parse failure fails safe to a
# PASS. An agent's prose IS the product. Wrap it in JSON and a single unescaped
# quote, or one length-stop mid-string (DEF125 measured that at 66% of Research
# Manager turns before it was fixed), makes the whole turn unparseable and the
# user reads raw JSON in the transcript. DEF058 measured the same contract
# failing to parse in ~22% of PM runs — that is the precedent's real rate.
#
# A single line degrades PARTIALLY instead: an unparseable or absent envelope
# costs the stance and nothing else, the prose is untouched, and the agent
# lands in the comb's "NOT STATED" gutter — which is exactly the degradation
# CR106 §3.4 already designed for a null stance. The wire contract the client
# sees is unchanged from the CR: stance · conviction · headline, each nullable.
#
# DEF147 — it shipped TRAILING, and the position was the defect. A machine
# field written after the prose in a length-capped generation is the first
# thing a truncation eats, so it was lost precisely on the longest, most
# substantive turns: 3 of 11 agents on live Alpha the day it shipped (27%),
# worse than the ~22% the JSON shape was rejected over. DEF125's larger budgets
# move that cliff without changing which side the field sits on. It now LEADS
# the turn, so what truncation eats is prose — which degrades gracefully and is
# already marked `[AMI: …incomplete]`. The cost is real and accepted: the agent
# names its stance before writing the argument for it, so the stance is a prior
# the prose then defends rather than a conclusion the prose reaches. It is
# smallest exactly where it would be worst — the eleven voices' roles and the
# transcript already in context largely fix the side each takes.


#
# Quantisation is in the ENVELOPE, not the renderer (CR106 B2): the model picks
# one of three words. No number is ever produced, so no widget can be tempted
# to render a false precision from one.
STANCE_HEADLINE_MAX_CHARS = 32
"""§3.3 measured the collapsed row's gist budget at ~32 Latin characters. The
server nulls a headline longer than this rather than sending one the client
must cut: a headline is an ASSERTION, and a truncated assertion can invert its
own meaning — which is the DEF059 class the CR rejected first-sentence
truncation over. An over-length headline falls back to the row's other sources
(the agent's own first **bold** span), which are quotations, and a truncated
quotation reads as the fragment it is."""

_STANCE_FORMAT = (
    "\n\nBEFORE the thesis sentence, your VERY FIRST line must be this one line, "
    "in exactly this shape, with your prose starting on the line after it:\n"
    "[STANCE: for|against|neutral | CONVICTION: low|medium|high | HEADLINE: <max "
    f"{STANCE_HEADLINE_MAX_CHARS} characters>]\n"
    "- STANCE: your view on taking this position now — 'for', 'against', or "
    "'neutral' if you genuinely land in the middle.\n"
    "- CONVICTION: how strongly you hold that view.\n"
    "- HEADLINE: the single number or fact that carries your view, in your own "
    "words. Not a summary of your whole argument.\n"
    "- If your role this turn is not to take a side at all, write "
    "'STANCE: none'. Never guess a side to fill the field.\n"
    "- Write this line ONCE, at the top only. Do not repeat it at the end."
)


def _drawdown_snapshot_line(mandate: Mandate, trade_proposal: dict[str, Any] | None) -> str:
    """The mandate-snapshot drawdown line (DEF066).

    Always states that the cap is portfolio-level, not a per-trade stop budget.
    When a concrete reference proposal is supplied (RISK / VERDICT phases), it also
    hands the agent the *derived* contribution figure so no agent has to do — or
    mis-do — the arithmetic that made 16 names un-buyable in the CR035 benchmark
    (a stop distance was compared directly against the cap, ~20x overstating the
    risk).

    Audit D-e: the numbers are a DETERMINISTIC reference position (the risk-tier
    ceiling at a reference entry/stop), computed before the debate — not the live
    Trader's exact words, which live only in the transcript. Labelled as a
    reference so the figure is honest rather than attributed to a proposal the
    Trader may not have made."""
    cap = mandate.max_drawdown_pct
    line = (
        f"- max_drawdown_pct: {cap} — PORTFOLIO-level cap on total drawdown, NOT a "
        f"per-trade stop budget. A position of size P% with a stop S% below entry "
        f"contributes about P×S/100 percentage points to portfolio drawdown."
    )
    if not trade_proposal:
        return line
    size = float(trade_proposal.get("size_pct") or 0)
    entry = float(trade_proposal.get("entry") or 0)
    stop = float(trade_proposal.get("stop") or 0)
    dc = drawdown_contribution(size, entry, stop)
    if dc:
        stop_dist = dc.stop_distance_pct
        contrib = dc.contribution_pts
        pct_of_cap = contrib / cap * 100 if cap else 0
        line += (
            f"\n  Reference position (risk-tier ceiling {size:.1f}% size, entry "
            f"{entry:.2f}, stop {stop:.2f}) → stop {stop_dist:.1f}% below entry → "
            f"portfolio-drawdown contribution ≈ {contrib:.2f} pt of the {cap:.0f} pt "
            f"cap (~{pct_of_cap:.0f}% of it). Size the actual trade against THIS "
            f"figure, not the raw stop distance."
        )
    return line


def build_room_messages(
    *,
    agent_id: AgentId,
    mandate: Mandate,
    user_id: Any = None,
    ticker: str,
    profile: dict[str, Any],
    transcript: list[AgentMessage],
    portfolio_snapshot: str | None = None,
    plan: Any = None,
    trade_proposal: dict[str, Any] | None = None,
    halal_universe: Any = None,
    parallel_phase: bool = False,
    sector_weights: dict[str, float] | None = None,
) -> tuple[str, list[ChatMessage]]:
    """Compose (system_prompt, [user_message]) for one agent's Room turn.

    The Portfolio Manager is the one agent whose output is parsed back into
    a structured `Verdict` (DEF056) — it gets `_PM_VERDICT_FORMAT` instead of
    `_PROSE_FORMAT` and no forced action; `enforce_safety_floor()` vetoes its
    decision afterward, it doesn't dictate it beforehand.

    `portfolio_snapshot` is the always-present, sim-sourced holdings block the runner
    builds once per run (CR055); it is injected after user_overlay through
    `build_agent_prompt`'s portfolio slot so every agent sees the user's real
    holdings (or an explicit "no open positions" for a new user, or a loud
    "unavailable" line on failure — never silence).

    `plan` gates the Decision Journal lookback window (DEF054/DEF055) for
    Bull/Bear Researcher — same retention-by-plan rule journal_store
    already applies everywhere else it's read.

    `halal_universe` is the run's `HalalUniverse` (`_RoomContext.halal_universe`) —
    the same object `enforce_safety_floor` decides against. Passing it here is what
    lets the agents narrate the sourced verdict for `ticker` instead of a bare flag
    (CR069); a Room turn that omits it makes the overlay say the screen could not be
    attached, which is the loud degrade, not a silent one.

    `parallel_phase` (CR077 Phase 2) is True only when this agent runs CONCURRENTLY
    with its phase-mates (the ANALYSTS phase) — it sees the transcript as of phase
    start, which for the first phase is empty. The runner's `_Phase.parallel` flag
    is the single source of truth; it is threaded here, not re-derived from the
    agent id. When True, the "build on the transcript — do not repeat" instruction
    (a lie for an agent with no transcript to build on) is rescoped to sharpen the
    analyst's own-domain lens instead. Sequential phases (the default) keep the
    original line — it is load-bearing where each turn answers the last.
    """
    base = build_agent_prompt(
        agent_id,
        mandate,
        user_id=user_id,
        portfolio_snapshot=portfolio_snapshot,
        halal_universe=halal_universe,
        ticker=ticker,
    )
    phase = _PHASE_FOR_AGENT[agent_id]
    length = _LENGTH_GUIDE[agent_id]
    transcript_text = _format_transcript(transcript)
    profile_block = _format_profile(profile)

    journal_note = ""
    if agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
        journal_block = build_journal_context_block(user_id, ticker, plan or Plan.FLOOR_PASS)
        if journal_block:
            journal_note = f"\n\n{journal_block}\n"

    # CR106 B2: the eleven prose agents also close with a stance tail. The PM is
    # deliberately excluded — it is not one of the eleven voices in the comb
    # (its position IS the hero tile), and its output is a JSON verdict that a
    # trailing line would corrupt.
    format_instruction = (
        _PM_VERDICT_FORMAT
        if agent_id == AgentId.PORTFOLIO_MANAGER
        else _PROSE_FORMAT + _STANCE_FORMAT
    )

    # DEF066: only agents that judge the proposed trade (RISK debators, the PM's
    # VERDICT) get the derived contribution figure; earlier phases have no
    # proposal yet, so they see the portfolio-cap clarification only.
    proposal = trade_proposal if phase in ("RISK", "VERDICT") else None
    drawdown_line = _drawdown_snapshot_line(mandate, proposal)

    # CR055: long_only, said plainly. The bare compliance flag was misread by a Trader
    # as forbidding a second entry in a name already held — long_only only bars shorts.
    long_only_line = ""
    if mandate.compliance.long_only:
        long_only_line = (
            "- long_only: long-only = no short/negative positions. It does NOT forbid "
            "buying, adding to, or holding a name.\n"
        )

    # CR055 (extends CR046 M03 to the researchers): the Bull/Bear/Research-Manager
    # propose a size but did NOT carry the enforced single-name cap the Trader & PM see,
    # so they routinely suggested ~4x what the system enforces (the 10–15%-vs-3.0%
    # incoherence that seeded the SCHD phantom-holding). Hand them the same ceiling.
    researcher_cap_note = ""
    if agent_id in (
        AgentId.BULL_RESEARCHER,
        AgentId.BEAR_RESEARCHER,
        AgentId.RESEARCH_MANAGER,
    ):
        cap = resolved_single_name_cap_pct(mandate.risk_score, mandate.single_name_cap_pct)
        researcher_cap_note = (
            f"\nSizing ceiling: any position size you suggest must respect the enforced "
            f"single-name cap of {cap:.1f}% of portfolio (risk_score={mandate.risk_score}). "
            f"Do NOT propose a larger allocation — the system clamps to this cap, so a "
            f"bigger number is both wrong and misleading.\n"
        )

    # CR077 §Build 5: for a concurrent analyst the transcript is empty (it speaks
    # at the same time as its phase-mates), so "build on the transcript — do not
    # repeat" would instruct it to build on nothing. Rescope it to sharpen the
    # own-domain lens — which is what actually cuts the cross-analyst repetition
    # that already exists (§Evidence: -7% margin / -1.4% FCF repeated in 3 of 4
    # analyst turns TODAY, sequentially, despite the original line). The line is
    # unchanged for every sequential phase, where it is load-bearing.
    if parallel_phase:
        collaboration_line = (
            "You are speaking AT THE SAME TIME as the other analysts and cannot "
            "see their contributions — the transcript above is empty by design. "
            "Do not reference, defer to, or assume another analyst's read. Stay "
            "strictly inside your OWN domain (per your job description above) and "
            "give only your lens on the data; that discipline is what keeps the "
            "four analyst contributions from overlapping."
        )
    else:
        collaboration_line = (
            "Build on the transcript — do not repeat what's already been said."
        )
    # CR026: the PM gatekeeps the trade, so it sees the REAL sector allocation of the
    # portfolio it approves against — concentration reasoning from data, not a guess.
    # Gated to the PORTFOLIO_MANAGER (the agent whose verdict the sector cap vetoes).
    sector_line = ""
    if agent_id == AgentId.PORTFOLIO_MANAGER:
        sector_line = _format_sector_allocation(sector_weights) + "\n"

    room_addition = (
        f"\n\n─── CONVENE THE ROOM — {phase} PHASE ───\n"
        f"Ticker: {ticker}\n"
        f"{profile_block}\n"
        f"\n"
        f"User mandate snapshot:\n"
        f"- risk_score: {mandate.risk_score} (1=most conservative, 5=most aggressive)\n"
        f"{drawdown_line}\n"
        f"{long_only_line}"
        f"- locale: {mandate.locale}\n"
        f"{sector_line}"
        f"{researcher_cap_note}"
        f"\n"
        f"Transcript so far:\n{transcript_text}\n"
        f"{journal_note}"
        f"\nYour turn. Speak as the {agent_id.value.replace('_', ' ').title()}. "
        f"Write {length}. Use specific numbers wherever possible — but ONLY "
        f"numbers from the data block above. Do NOT cite figures (P/E, growth, "
        f"price targets, market cap) from training memory; if a number isn't "
        f"in the block above, qualify your claim or omit it. {collaboration_line} "
        f"Do not preface with 'As the X' or 'Speaking as'. Speak directly.\n"
        f"{format_instruction}"
    )

    system_prompt = base + room_addition
    user_message = ChatMessage(role="user", content=f"Convene on {ticker}.")
    return system_prompt, [user_message]


# ── Helpers ──────────────────────────────────────────────────────────────


def _format_sector_allocation(sector_weights: dict[str, float] | None) -> str:
    """The PM's current sector-allocation line (CR026). Real weights, not silence —
    an empty portfolio says so explicitly rather than omitting the line."""
    if not sector_weights:
        return "- sector allocation: no open positions yet (0% in every sector)."
    parts = ", ".join(
        f"{sec} {weight * 100:.0f}%"
        for sec, weight in sorted(
            sector_weights.items(), key=lambda kv: kv[1], reverse=True
        )
    )
    return f"- current sector allocation (of invested value): {parts}."


def _format_profile(profile: dict[str, Any]) -> str:
    """A compact ticker fact-sheet the agent can quote from.

    CR104 (closes DEF123) — provenance is PER FIELD, not per block, and this
    is the ONLY provenance mechanism in the renderer: `profile["field_state"]`
    maps a field/domain name to a `LiveDataState` value ("live" /
    "withheld_paid" / "withheld_tenure" / "unavailable"). A numeric field
    renders ONLY when its state says "live" — there is no rng-seeded
    fallback left to render, and no second, block-level flag (the old
    `data_source` / `technicals_state` / `news_state` / `social_state` keys)
    that could disagree with it. Before CR104, `data_source="yfinance_live"`
    asserted the WHOLE fundamentals block was live even when yfinance
    supplied only some of the fields — DEF123: 178 of 842 live-declared
    prompts carried a fabricated P/E. The disclosure header below is true
    by construction now, not by assertion: it can only describe what
    `field_state` actually recorded.

    Fields absent from `field_state` entirely (non-Room callers / hand-built
    profiles in older tests) render as not-available — refusal is the
    default, not a special case.

    Granular by design (AT:R57, CR023/CR024): a single profile can have live
    fundamentals AND live news AND live social sentiment (or any subset
    thereof, down to individual fundamentals fields) at once. Macro/Fed tone
    and the sector-earnings half of forward catalyst had no real source at
    all and were removed at source (CR038) — only the real FOMC-date half of
    forward catalyst remains.
    """
    field_state: dict[str, Any] = profile.get("field_state") or {}

    def _is(key: str, state: str) -> bool:
        return field_state.get(key) == state

    fundamentals_any_live = any(
        _is(f, "live") for f in ("base_price", "pe", "rev_growth", "profit_margin", "net_cash")
    )
    technicals_live = _is("technicals", "live")
    news_live = _is("news", "live")
    social_live = _is("social", "live")
    # CR090's 3-state live-data marker, now per-field via `field_state`
    # instead of the old `news_state` / `social_state` block keys (D1 — this
    # header line is the ANTI-FABRICATION measure only: it stops the agent
    # inventing news / sentiment to paper over the gap. The user-facing
    # guarantee is the structural `live_data_notice` event the runner emits
    # with the model out of the loop (D3) — NOT this prompt string, which
    # agents drop ~70% of the time).
    news_withheld = _is("news", "withheld_paid")
    social_withheld = _is("social", "withheld_paid")
    # CR098 round-2 fix (MINOR 3), preserved under the per-field model — a
    # roster-withheld domain's header line must not describe fields the
    # fact-sheet body has already stripped (see market_withheld /
    # news_withheld_tenure / social_withheld_tenure below). Computed here
    # (ahead of their first use further down) so the header can skip the
    # withheld domain's line entirely.
    market_withheld = _is("technicals", "withheld_tenure")
    news_withheld_tenure = _is("news", "withheld_tenure")
    social_withheld_tenure = _is("social", "withheld_tenure")

    header_lines = []
    # DEF124/D2: ONE run-date anchor for every other absolute date in the
    # fact sheet, gated on the same per-field `field_state` scheme as every
    # other fact (not an ungated string bolted beside it) — the clock is a
    # real, always-live source, so this is the one field that should never
    # render "not available" once the profile pipeline sets it. A hand-built
    # profile with no recorded provenance still renders nothing here,
    # matching every other field's refuse-by-default behaviour.
    if profile.get("run_date") and _is("run_date", "live"):
        header_lines.append(
            f"Fact sheet as of {profile['run_date']} (UTC) — every other "
            "date in this sheet is anchored to this one; do not estimate "
            "how far away a date is from your own sense of the current date."
        )
    header_lines.append(
        "Data source disclosure — every fact below is tagged with where it "
        "came from. A field with no live source is marked not available "
        "below, never silently filled in — do NOT estimate, recall from "
        "training memory, or invent a number for it:"
    )
    if fundamentals_any_live:
        header_lines.append(
            "- Numeric fundamentals (price, P/E, growth, margin, net cash, "
            "52-week range): each field below is tagged individually — a "
            "provider gap on one field does not make the others fake. Only "
            "the fields explicitly marked available/LIVE below are real; "
            "any field marked 'not available' has no data behind it."
        )
    else:
        header_lines.append(
            "- Numeric fundamentals (price, P/E, growth, margin, net cash): "
            "none available live this call — every such field below is "
            "marked not available."
        )
    if market_withheld:
        pass  # stripped below; no scaffolding line to contradict it with
    elif technicals_live:
        header_lines.append(
            "- RSI, trend, volume, 50-day range: LIVE, computed from "
            "real yfinance price history as of this call. No MACD, "
            "moving-average crossover signal, or Bollinger Bands are "
            "computed — do not cite them."
        )
    else:
        header_lines.append(
            "- RSI, trend, volume, 50-day range: not available this "
            "call — do not compute or estimate them yourself."
        )
    if news_withheld_tenure:
        pass  # stripped below; no scaffolding line to contradict it with
    elif news_live:
        header_lines.append(
            "- Recent catalyst/headline: LIVE, real news as of this call "
            "(publisher + recency shown below). Some headlines may carry a "
            "sentiment tag; treat it as one input, not a verdict."
        )
    elif news_withheld:
        header_lines.append(
            "- Recent catalyst/headline: a LIVE news feed IS available for this "
            "ticker but is a PAID feature this user has not purchased for this "
            "run — it is withheld. The catalyst/headline field below is alpha "
            "simulation scaffolding, NOT real news. Do NOT invent headlines, a "
            "sentiment tag, or a catalyst to fill the gap, and do NOT imply the "
            "live feed was consulted."
        )
    else:
        header_lines.append(
            "- Recent catalyst/headline: alpha simulation scaffolding — NOT "
            "a live news feed."
        )
    if social_withheld_tenure:
        pass  # stripped below; no scaffolding line to contradict it with
    elif social_live:
        header_lines.append(
            "- Retail sentiment/mention/community fields: LIVE, real Reddit "
            "aggregate data as of this call (Reddit only — no Twitter/X, "
            "StockTwits, Google Trends, or Discord data exists)."
        )
    elif social_withheld:
        header_lines.append(
            "- Retail sentiment/mention/community fields: a LIVE Reddit "
            "sentiment feed IS available for this ticker but is a PAID feature "
            "this user has not purchased for this run — it is withheld. The "
            "sentiment/mention fields below are alpha simulation scaffolding, "
            "NOT real social data. Do NOT invent a sentiment score, mention "
            "count, or community read to fill the gap."
        )
    else:
        header_lines.append(
            "- Retail sentiment/mention/influencer fields: alpha simulation "
            "scaffolding — NOT a live social feed."
        )
    header_lines.append(
        "- Forward catalyst: the FOMC decision countdown below is REAL, "
        "from the Fed's published calendar."
    )
    header = "\n".join(header_lines)

    # CR098 Amendment 1 — a roster-withheld domain's fact-sheet lines are
    # OMITTED, not rendered with synthetic numbers under a disclosure header.
    # Skipping only the fetch (as CR090's WITHHELD_PAID already does) leaves
    # the rng-seeded scaffolding on screen — no FOMO, no decode saving, and a
    # CR040 violation. Each stripped block is replaced by one declared line
    # (never a synthetic stand-in — acceptance #6 asserts on the exact string).
    # market_withheld/news_withheld_tenure/social_withheld_tenure are computed
    # above, ahead of the header, so the header can skip the withheld domain's
    # scaffolding line too (MINOR 3).

    lines = [header, ""]
    lines.append(
        f"Reference price: ${profile.get('base_price')}" if _is("base_price", "live")
        else "Reference price: not available"
    )
    # DEF233: both bases, each gated on its own `field_state` entry — a
    # provider gap on one is stated, never papered over with the other.
    lines.append(
        pe_line(
            profile.get("pe") if _is("pe", "live") else None,
            profile.get("forward_pe") if _is("forward_pe", "live") else None,
        )
    )
    lines.append(
        (f"TTM revenue growth: {profile.get('rev_growth')}%" if _is("rev_growth", "live")
         else "TTM revenue growth: not available")
        + ", "
        + (f"profit margin: {profile.get('profit_margin')}%" if _is("profit_margin", "live")
           else "profit margin: not available")
    )
    lines.append(_net_position_line(profile))
    if market_withheld:
        lines.append(
            "Market technicals: not included in this session."
        )
    elif technicals_live:
        lines.append(
            f"RSI: {profile.get('rsi')} ({profile.get('rsi_tone')}), trend: {profile.get('trend')}"
        )
        # DEF074: the recent-range floor is the computed technical support
        # (profile['support'], the 50-day min that compute_technicals produced and
        # the 1-on-1 path already shows) — NOT the 52-week low, which is a
        # separately-sourced fundamentals field (see week52 below).
        # DEF228: state where price sits in that range. The Room fact sheet
        # carries a Reference price line, but it is a separately-sourced
        # quote several lines up, and on live Alpha the agent joined the two
        # wrong and invented a breakdown the whole Room then adopted. This
        # is arithmetic on two numbers already on the sheet — it asserts
        # nothing new. DEF229(b): "breakout" is a 50-day high, named as one.
        lines.append(_range_line(profile))
        lines.append(f"Volume: {profile.get('volume_tone')}")
    else:
        lines.append("Market technicals: not available this call.")
    # 52-week range is a fundamentals field, independent of technicals —
    # `fetch_live_fundamentals` only sets `week52` LIVE when yfinance's real
    # fiftyTwoWeekLow/High fields were used, never for the ±5%-of-price
    # placeholder it falls back to internally (that placeholder is a derived
    # guess, not a measurement, so it earns no "52-week" label here).
    if _is("week52", "live"):
        lines.append(f"52-week range: ${profile.get('low')}–${profile.get('high')}")
    if news_withheld_tenure:
        lines.append(
            "Recent catalyst/headline: not included in this session."
        )
    else:
        lines.append(_catalyst_line(profile))
    if social_withheld_tenure:
        lines.append(
            "Retail sentiment: not included in this session."
        )
    else:
        lines.append(
            f"Retail sentiment: {profile.get('sentiment_tone')} ({profile.get('sentiment_score')})"
        )
        lines += _social_detail_lines(profile)
    for extra in (_valuation_line(profile), _sector_line(profile),
                  _capital_allocation_line(profile), _analyst_line(profile)):
        if extra:
            lines.append(extra)
    if (
        profile.get("next_earnings_date")
        and _is("next_earnings", "live")
        and profile.get("next_earnings_interval")
    ):
        # DEF124/D1/acceptance-6: render the interval ALONGSIDE the absolute
        # date, never instead of it — the date is what a user cross-checks,
        # the interval is what stops the model guessing. Computed in Python
        # (`app.core.time.relative_day_phrase`), never asked of the model.
        # The interval is required, not optional decoration: an absolute
        # date with no anchor is exactly the DEF124 bug, so a profile that
        # somehow carries a live earnings date without its computed interval
        # (should never happen via `_profile_for_ticker`, but this renderer
        # makes no assumption about its caller) omits the line entirely
        # rather than emit an unanchored date.
        lines.append(
            f"Next earnings (LIVE): {profile['next_earnings_date']}"
            + (f" ({profile['next_earnings_quarter']})" if profile.get("next_earnings_quarter") else "")
            + (f" — {profile['next_earnings_interval']}" if profile.get("next_earnings_interval") else "")
            + (f", consensus EPS est. ${profile['next_earnings_eps_estimate']}"
               if profile.get("next_earnings_eps_estimate") is not None else "")
        )
    return "\n".join(lines)


def _social_detail_lines(profile: dict[str, Any]) -> list[str]:
    """The live-Reddit fields the Adanos pipeline computes and _format_profile used to
    DROP (DEF096): mention volume + trend, buzz score + numeric bullish/bearish split,
    and the most-active communities — the exact Inputs the Social Media Analyst's job
    names (content/agents/social_media_analyst.md:16,23). In the Room only tone + score
    were rendered, so the analyst reached for a price-volume figure it wasn't given.

    Rendered only when social is LIVE — the synthetic path surfaces nothing (the
    data-source disclosure header already declares social live/not-live, so no
    fabricated social numbers leak; CR040). These are pre-formatted upstream by the
    Adanos formatters (format_mention_trend / format_pattern / format_community_read) —
    rendered verbatim as indented detail under 'Retail sentiment:', never recomputed."""
    if (profile.get("field_state") or {}).get("social") != "live":
        return []
    out: list[str] = []
    if profile.get("mention_trend"):
        out.append(f"  Mentions: {profile['mention_trend']}")
    if profile.get("pattern"):
        out.append(f"  {profile['pattern']}")
    if profile.get("influencer_take"):
        out.append(f"  Communities: {profile['influencer_take']}")
    return out


def _net_position_line(profile: dict[str, Any]) -> str:
    """Balance-sheet line, sign-aware: net cash vs net debt (never 'Net cash: $-42000M')."""
    phrase = net_position_phrase(profile.get("net_cash"))
    if phrase is None:
        return "Balance sheet: net cash not available"
    return phrase[:1].upper() + phrase[1:]


def _range_line(profile: dict[str, Any]) -> str:
    """The 50-day range with the last close's position inside it (DEF228).

    `last_close` rides the same `field_state["technicals"]` gate as the range
    itself — it is the final candle of the very series the range was measured
    over — so it is present whenever this line renders. Falls back to the
    bare range if a caller ever supplies one without the other, rather than
    printing a position derived from a missing number.
    """
    support = profile.get("support")
    breakout = profile.get("breakout")
    last_close = profile.get("last_close")
    line = f"50-day range: ${support}–${breakout}"
    if last_close is None:
        return line
    pct = range_position_pct(last_close, support, breakout)
    if pct is None:
        return f"{line}, last close ${last_close}"
    return f"{line}, last close ${last_close} ({pct}% of that range)"


def _valuation_line(profile: dict[str, Any]) -> str | None:
    """Real valuation multiples beyond P/E (DEF053). None when nothing live —
    no fabricated peer/sector multiple is ever shown. CR104/D8: each part is
    gated on its own `field_state` entry, not presence — a part whose
    provenance wasn't recorded is dropped, never silently included under the
    line's `(LIVE)` label."""
    parts = []
    if profile.get("price_to_sales") and _field_is_live(profile, "price_to_sales"):
        parts.append(f"P/S {profile['price_to_sales']}x")
    if profile.get("ev_to_ebitda") and _field_is_live(profile, "ev_to_ebitda"):
        parts.append(f"EV/EBITDA {profile['ev_to_ebitda']}x")
    if profile.get("peg_ratio") and _field_is_live(profile, "peg_ratio"):
        # DEF233: the basis rides its own field_state entry — an unlabelled PEG
        # is claimed as bare, never labelled from an unrecorded provenance.
        basis = profile.get("peg_basis") if _field_is_live(profile, "peg_basis") else None
        parts.append(peg_part(profile["peg_ratio"], basis))
    if profile.get("fcf_yield") is not None and _field_is_live(profile, "fcf_yield"):
        parts.append(f"FCF yield {profile['fcf_yield']}%")
    if not parts:
        return None
    return "Valuation (LIVE): " + ", ".join(parts)


def _sector_line(profile: dict[str, Any]) -> str | None:
    """Real sector/industry classification (DEF053) — replaces the old
    always-fake numeric `sector_pe`; this is a category, not a fabricated
    peer-average P/E (yfinance has no peer-basket P/E to compute one from).
    CR104/D8: gated on `field_state`, not presence alone."""
    if not profile.get("sector") or not _field_is_live(profile, "sector"):
        return None
    return f"Sector/industry (LIVE): {profile['sector']} / {profile.get('industry', '—')}"


def _capital_allocation_line(profile: dict[str, Any]) -> str | None:
    """Real dividend yield only (DEF053) — buybacks/M&A have no yfinance
    field and stay undisclosed rather than fabricated. CR104/D8: gated on
    `field_state`, not presence alone."""
    if profile.get("dividend_yield") is None or not _field_is_live(profile, "dividend_yield"):
        return None
    return f"Dividend yield (LIVE): {profile['dividend_yield']}% (buybacks/M&A: not available, not claimed)"


def _analyst_line(profile: dict[str, Any]) -> str | None:
    """Real analyst consensus (DEF053) — the closest honest proxy for
    'forward guidance' available. Explicitly labeled as the Street's view,
    not the company's own guidance (which yfinance doesn't expose). CR104/D8:
    gated on `field_state` — target price and rating are fetched together, so
    either one's provenance recorded live is sufficient to label the line."""
    has_target = profile.get("analyst_target_price") and _field_is_live(profile, "analyst_target_price")
    has_rating = profile.get("analyst_rating") and _field_is_live(profile, "analyst_rating")
    if not has_target and not has_rating:
        return None
    return (
        f"Analyst consensus (LIVE, Street view — NOT company guidance): "
        f"{profile.get('analyst_rating', '—')}, target ${profile.get('analyst_target_price', '—')}"
    )


def _catalyst_line(profile: dict[str, Any]) -> str:
    from app.services.news_context import format_headline

    line = f"Catalysts — recent: {profile.get('catalyst')}"
    extra_headlines = (profile.get("news_headlines") or [])[1:]
    if extra_headlines:
        extra = "; ".join(format_headline(h) for h in extra_headlines)
        line += f"; other recent coverage: {extra}"
    line += f"; forward (REAL, Fed's published calendar): {profile.get('forward_catalyst')}"
    return line


def _format_transcript(transcript: list[AgentMessage]) -> str:
    if not transcript:
        return "(You are first to speak.)"
    lines: list[str] = []
    for m in transcript:
        aid = m.agent_id.value if hasattr(m.agent_id, "value") else str(m.agent_id)
        lines.append(f"[{aid}] {m.content}")
    return "\n".join(lines)
