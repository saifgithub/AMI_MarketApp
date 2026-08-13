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

from datetime import date, datetime, timezone
from typing import Any

from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED
from app.schemas import AgentId, AgentMessage, Mandate
from app.schemas.mandate import Plan
from app.services.agent_prompts import build_agent_prompt
from app.services.fundamentals import (
    analyst_consensus_line,
    balance_sheet_line,
    dividend_line,
    earnings_power_line,
    identity_line,
    margin_structure_line,
    ownership_line,
    pe_line,
    peg_part,
    returns_line,
)
from app.services.journal_context import build_journal_context_block
from app.services.llm_gateway import ChatMessage
from app.services.technicals import range_position_pct
from app.trading_math.risk import drawdown_contribution
# DEF263 — the SAME window helpers `enforce_safety_floor` counts with. A second
# implementation of "today" is how the prompt and the brake come to disagree.
from app.trading_math.risk_limits import trades_since, utc_day_start, utc_week_start
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
#
# DEF236 — stated in BULLETS, because bullets are what the agent is asked to
# write. Until 2026-08-11 this counted SENTENCES while `_PROSE_FORMAT`, five
# lines below, asked for "a one-sentence thesis, then short bullet points":
# two instructions in two different units, both live in the same assembled
# string, and a stance envelope plus a thesis plus bullet *points* does not fit
# in the two sentences the Aggressive Debator was told to write. Measured on the
# 2026-08-07 epoch (n=198): the model obeyed the bullets and discarded the
# count — neutral_debator median 5 sentences against a guide of 2 (100% over,
# 94% using bullets), research_manager median 9 against 4–6 (61% over).
#
# That mattered beyond tidiness: `_AGENT_MAX_TOKENS` below was sized by DEF125
# to fit THIS dict, so every decode budget in the Room was calibrated against a
# target the model was structurally unable to meet.
#
# Counting the unit the structure is already written in makes the ask
# satisfiable. It is not a relaxation — for the researchers and the Research
# Manager it asks for materially LESS than the medians above, which is the
# point: the Research Manager's turn is the single input the EXECUTION and RISK
# phases reason from (DEF095), and its verbosity is inherited by every prompt
# downstream of it.
_LENGTH_GUIDE: dict[AgentId, str] = {
    AgentId.FUNDAMENTALS_ANALYST: "one thesis sentence, then up to 3 short bullets",
    AgentId.MARKET_ANALYST: "one thesis sentence, then up to 3 short bullets",
    AgentId.NEWS_ANALYST: "one thesis sentence, then up to 3 short bullets",
    AgentId.SOCIAL_MEDIA_ANALYST: "one thesis sentence, then up to 3 short bullets",
    AgentId.BULL_RESEARCHER: (
        "one thesis sentence, then up to 4 short bullets — evidence first, "
        "your falsifier last"
    ),
    AgentId.BEAR_RESEARCHER: (
        "one thesis sentence, then up to 4 short bullets — risk and its "
        "quantification first, your invalidator last"
    ),
    AgentId.RESEARCH_MANAGER: (
        "one thesis sentence, then up to 4 short bullets — asymmetry numbers, "
        "lean, size implication"
    ),
    # The Trader's labelled block IS its structure (see `_NO_FENCE_CLAUSE`).
    AgentId.TRADER: (
        "your labelled output block — instrument, side, size, entry, stop, "
        "target, horizon — then up to 3 short bullets of rationale"
    ),
    AgentId.AGGRESSIVE_DEBATOR: (
        "one thesis sentence, then up to 3 short bullets (the size push and "
        "what pays for it)"
    ),
    AgentId.CONSERVATIVE_DEBATOR: (
        "one thesis sentence, then up to 3 short bullets (the size cap and "
        "what it protects against)"
    ),
    AgentId.NEUTRAL_DEBATOR: (
        "one thesis sentence, then up to 3 short bullets (the middle size and "
        "what each side gives up)"
    ),
    AgentId.PORTFOLIO_MANAGER: (
        "one decision sentence, then up to 6 short bullets, all inside your "
        "JSON verdict's narration field — see the format instruction below"
    ),
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
    #
    # DEF236 raised this one from 900. It is the only budget the batch moved,
    # and the only one whose ASK grew: the narration went from "3–4 sentences"
    # to a decision sentence plus up to 6 bullets. Derived from the new ask, not
    # measured — the post-promotion re-measurement is the acceptance. Raising it
    # is nearly free (DEF125 measured this host's `num_preemptions_total` at 0
    # and `max_tokens` is a ceiling, not an allocation) and being short here is
    # uniquely expensive: a clipped JSON envelope is unparseable rather than
    # merely incomplete, and `_parse_pm_verdict` fails safe to PASS, so the cost
    # of twenty tokens too few is a discarded APPROVE.
    AgentId.PORTFOLIO_MANAGER: 1100,
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
    # CR156 B — the REPLACES sentence covered the OUTPUT BLOCK only, so the
    # 'Decision sequence' three lines above it still said REJECT, in two layers,
    # against this format's "exactly two action values". The parser survived it
    # (`_normalize_pm_action` maps REJECT→PASS); the USER did not — the wire
    # action colours the card and the prose is what they read, so a card marked
    # PASS carried a narration opening "REJECT:". Measured 4 of 14 on the
    # 2026-08-11 post-promotion batch, against the 6/18 CR156 was filed on.
    # Both layers now say PASS, and this sentence names the decision sequence so
    # a future edit to either one cannot quietly reopen the gap.
    "This output format and its two action values REPLACE **both** the "
    "'Verdict:' / 'Output format' block AND the 'Decision sequence' described "
    "earlier in your profile and mandate overlay. Wherever those say REJECT, "
    "the action you emit here is PASS — name the rule that failed in your "
    "narration. In the Room you answer here, and only here.\n"
    "Your ENTIRE reply must be one single JSON object — begin with '{' and "
    "end with '}'. Do not write any prose outside the JSON (your reasoning "
    "belongs inside the narration field); anything outside it is discarded "
    "and your verdict is lost. Shape it exactly like:\n"
    '{"action": "APPROVE" | "PASS",\n'
    ' "size_pct": <number, required if APPROVE — position size as % of portfolio>,\n'
    ' "entry": <number, required if APPROVE>,\n'
    ' "stop": <number, required if APPROVE>,\n'
    ' "target": <number, required if APPROVE>,\n'
    # DEF255 — `horizon_days` is the THESIS horizon: how long this specific
    # trade needs to work. It is NOT the mandate's investment horizon. The PM
    # emitted 1095 (the `Horizon.LONG` label restated as a number) in 4 of 13
    # approvals while the code's own fallback is 42 days — a 26× disagreement on
    # the same field, and the number the stop is judged against.
    ' "horizon_days": <integer, required if APPROVE — how long THIS trade needs '
    "to work out, not the user's investment horizon. Anchor it to the evidence "
    "you were actually given: 3 months of price history, TTM fundamentals and a "
    "52-week range support a thesis measured in weeks to a few months. A "
    "multi-year number is not supported by anything on your fact sheet>,\n"
    ' "narration": "<one decision sentence, then up to 6 short bullets — your '
    'rationale, written for the user>"}\n'
    "Write any line break inside narration as the two characters \\n, never as a "
    "real line break — a raw newline inside a JSON string is what makes a whole "
    "verdict unparseable.\n"
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

# DEF236 — STYLE only. The shape (a thesis sentence, then how many bullets) is
# stated once, in `_LENGTH_GUIDE`, and no longer restated here in a different
# unit. See that dict for what the contradiction cost.
_PROSE_FORMAT = (
    "\nFormat: use **bold** for key metrics (numbers, levels, deadlines). "
    "Plain text otherwise — no headings, no tables. The Markdown is "
    "rendered live in the app."
)

# Appended for every prose agent EXCEPT the Trader, whose own profile specifies
# a labelled block as its output structure and whose levels `_LEVEL_PATTERNS`
# reads back out of it. Telling that agent "no code fences" while its profile
# demands one is the same DEF236 contradiction a layer up, and the resolution
# runs the other way here: the block is load-bearing, so the blanket ban stops
# being asserted at the Trader rather than the block being dropped. Whether the
# block survives at all is CR152 Tier A.4's call, and that is gated on parser
# hardening (DEF242/DEF237) which has not shipped — deleting it first takes the
# full level triple from 2/18 to 0/18.
_NO_FENCE_CLAUSE = " Do not wrap your reply in a code fence."


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


def _risk_state_block(
    mandate: Mandate,
    current_drawdown_pct: float | None,
    existing_open_risk_pct: Any,
    last_loss_closed_at: Any,
    trade_open_timestamps: Any,
) -> str:
    """Where the user's risk budget ACTUALLY stands, right now.

    The deduped tier of CR153 B ≡ CR154 B ≡ CR155 C ≡ CR156 C — four CRs filed
    the same finding against four different agents, and CR156 states the dedupe
    rule: thread it into the shared mandate snapshot ONCE rather than four times.

    Until now the snapshot carried only the *limits* (`max_drawdown_pct: 20`) and
    never the *consumption*. Every agent argued about how much risk to add while
    blind to how much was already spent, which makes "sized against the cap"
    unanswerable: 3% more is prudent at 2% drawdown and reckless at 19%.

    Three distinct absences, kept distinct (CR040 / DEF059):

    - `CONTEXT_NOT_SUPPLIED` — the computation FAILED. Says so, and says the
      floor is blocking on it. A real "no prior loss" and an outage computing
      one must never render identically; that is the whole reason the sentinel
      exists rather than `None`.
    - `None` — not supplied by this caller (non-Room surfaces, older tests).
      Renders nothing rather than claiming zero.
    - a real `0.0` — genuinely no open risk. Stated as a fact.

    Open risk is labelled *"across open positions carrying a stop"* because that
    is what `_risk_limit_context` actually sums: a position with no stop
    contributes nothing to the figure, so an unqualified "open risk 4.2%" would
    read as complete when the book may hold unstopped positions the number
    cannot see. The holdings block names those positions individually.
    """
    lines: list[str] = []

    if current_drawdown_pct is not None:
        cap = mandate.max_drawdown_pct
        headroom = cap - current_drawdown_pct
        lines.append(
            f"- Drawdown USED: {current_drawdown_pct:.1f} pt of the {cap:.0f} pt cap "
            f"— {headroom:.1f} pt of headroom remains. Size against the headroom, "
            f"not against the cap."
        )

    # DEF263 — this branch was UNREACHABLE from the Room and the outage rendered
    # as silence. The bug was NOT here: the three-way distinction below is right
    # for a renderer, which genuinely cannot tell an outage from a caller that
    # never asked. It was at the call site — `_build_room_risk_limit_context`
    # returns `(CONTEXT_NOT_SUPPLIED, None, None)`, so open risk reached the
    # prompt as a plain `None` that means "computation failed" while looking
    # identical to "not supplied". The runner now translates its own `None` into
    # the sentinel before calling here (see `_prompt_open_risk`), because the
    # runner is the only layer that knows which of the two it meant.
    #
    # Collapsing `None` into this branch HERE was the wrong fix and was tried
    # first: `prompt_version.py` and any non-Room caller omit these kwargs
    # entirely, so it would have had them announce that the safety floor is
    # blocking a BUY nobody proposed — a fabricated alarm, which is the same
    # class of harm as the silence it replaced, pointed the other way.
    if existing_open_risk_pct is CONTEXT_NOT_SUPPLIED:
        lines.append(
            "- Open risk: COULD NOT BE COMPUTED this run. Treat it as unknown, not "
            "as zero — the safety floor is blocking on this, and you should not "
            "argue for added size as if the book were flat."
        )
    elif existing_open_risk_pct is not None:
        lines.append(
            f"- Open risk already committed: {float(existing_open_risk_pct):.1f}% "
            f"across open positions carrying a stop. Positions with no stop "
            f"recorded are NOT in this figure — see the portfolio block."
        )

    if last_loss_closed_at is CONTEXT_NOT_SUPPLIED:
        lines.append(
            "- Last stop-out: COULD NOT BE COMPUTED this run — unknown, not "
            "'none'. Any cooldown limit is being enforced blind."
        )
    elif last_loss_closed_at is not None:
        lines.append(f"- Last losing trade closed: {last_loss_closed_at}.")

    if isinstance(trade_open_timestamps, list):
        # DEF263 — this printed `len()` of the WHOLE list under the label "in the
        # recent window". `_risk_limit_context` builds it as `list_trades(user_id)`
        # with no date filter, so it is a LIFETIME count and the floor windows it
        # itself. Measured end-to-end: a book of 40 trades all opened 90–130 days
        # ago rendered "40" while the day brake counted 0 and the week brake
        # counted 0. A number labelled as the thing a limit counts, that the limit
        # does not count — the DEF235 class, in the block whose sibling line was
        # carefully qualified.
        #
        # Windowed with the floor's OWN helpers rather than a second
        # implementation, against the same UTC day boundary and Monday-00:00-UTC
        # ISO week the brakes use, so the two can never disagree about what
        # "today" means.
        now = datetime.now(timezone.utc)
        today = trades_since(trade_open_timestamps, utc_day_start(now))
        this_week = trades_since(trade_open_timestamps, utc_week_start(now))
        lines.append(
            f"- Trades opened today: {today}; this ISO week (from Monday 00:00 "
            f"UTC): {this_week}. These are the two counts an over-trading limit "
            f"actually brakes on."
        )

    if not lines:
        return ""
    return (
        "\nLive risk state — what the budget has ALREADY spent:\n" + "\n".join(lines) + "\n"
    )


def _drawdown_snapshot_line(
    mandate: Mandate,
    trade_proposal: dict[str, Any] | None,
    agent_size_pct: float | None = None,
) -> str:
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
        # DEF241 — the reference figure above is for the risk-tier CEILING, and a
        # debator argues for its OWN size, so it was still doing the arithmetic
        # itself. Measured over the epoch: the Conservative states a numeric
        # cap-consumption figure in 9 of 18 turns and 4 are WRONG, one of them
        # reproducing DEF066's exact error with DEF066's own warning rendered in
        # the same prompt; the Bull put 33 pt where the truth was 48.3 of a 50 pt
        # cap and closed with "stays within the safety floor". Nothing checks any
        # of it — `_verify_and_annotate_geometry` needs a full level triple and
        # fires 0/18 on these agents. So hand each one the figure for the size it
        # is actually arguing, and say the number is AMI's.
        #
        # This is P5 ("an LLM asked to compute a number it presents as fact") and
        # the THIRD appearance of DEF066: DEF066 was the formula, DEF235 was the
        # parser feeding it a wrong input, this is the agent doing it in prose.
        # Saiful's ruling, 2026-08-08: "File a DEF, fix in code."
        # CR166 Tier D — DEF066's class, a FOURTH time, and it slipped the guard
        # directly above. That guard appended the "AMI computed this" line only
        # when the agent's size DIFFERED from the reference ceiling, on the
        # reasoning that an agent arguing the ceiling already has its figure on
        # the reference line. It does — and it still got it wrong: on the AAPL
        # run of 2026-08-11 10:46 UTC the Aggressive debator argued the 3.0%
        # ceiling with a 6.0% stop and stated "0.30 pt" where the reference line
        # in its own prompt said 0.18, while the Conservative (1.5%, off-ceiling,
        # so it received the YOUR-position line) and the Neutral both quoted
        # 0.18 correctly. Reading a figure off a line addressed to "the reference
        # position" is not the same act as reading one addressed to YOU.
        #
        # So the equality carve-out goes: every debator with a size gets the
        # line naming its own number. The cost is one redundant line for the
        # ceiling-arguing agent; the benefit is that no agent is left to infer
        # that the reference figure is also its own. Per DEF243, DEF241's guard
        # is NOT edited to accommodate this — a case is added beside it.
        if agent_size_pct is not None and agent_size_pct > 0:
            own = drawdown_contribution(agent_size_pct, entry, stop)
            if own:
                own_pct_of_cap = own.contribution_pts / cap * 100 if cap else 0
                line += (
                    f"\n  YOUR position — the size YOUR role argues for "
                    f"({agent_size_pct:.1f}%) at that same stop → portfolio-drawdown "
                    f"contribution ≈ {own.contribution_pts:.2f} pt of the {cap:.0f} pt "
                    f"cap (~{own_pct_of_cap:.0f}% of it). AMI computed this. Quote it; "
                    f"do not recompute it, and do not compare the raw stop distance "
                    f"against the cap."
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
    agent_size_pct: float | None = None,
    current_drawdown_pct: float | None = None,
    existing_open_risk_pct: Any = None,
    last_loss_closed_at: Any = None,
    trade_open_timestamps: Any = None,
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
    profile_block = _format_profile(profile, agent_id)

    journal_note = ""
    if agent_id in (AgentId.BULL_RESEARCHER, AgentId.BEAR_RESEARCHER):
        journal_block = build_journal_context_block(user_id, ticker, plan or Plan.FLOOR_PASS)
        if journal_block:
            journal_note = f"\n\n{journal_block}\n"

    # CR106 B2: the eleven prose agents also close with a stance tail. The PM is
    # deliberately excluded — it is not one of the eleven voices in the comb
    # (its position IS the hero tile), and its output is a JSON verdict that a
    # trailing line would corrupt.
    if agent_id == AgentId.PORTFOLIO_MANAGER:
        format_instruction = _PM_VERDICT_FORMAT
    else:
        prose_format = _PROSE_FORMAT
        if agent_id != AgentId.TRADER:
            prose_format += _NO_FENCE_CLAUSE
        format_instruction = prose_format + _STANCE_FORMAT

    # DEF066: only agents that judge the proposed trade (RISK debators, the PM's
    # VERDICT) get the derived contribution figure; earlier phases have no
    # proposal yet, so they see the portfolio-cap clarification only.
    # DEF241 RESIDUE — DEFERRED DELIBERATELY, not overlooked (AT:R68, Batch 7).
    #
    # This gate is why `bull_researcher` (RESEARCHERS) and `research_manager`
    # (SYNTHESIS) are still byte-identical to pre-DEF241: they get the raw
    # `P×S/100` formula and no worked figure. Batch 7 considered widening it and
    # did not, because CR151 already adjudicated exactly this and rejected it:
    # extending the deterministic reference position to SYNTHESIS "would hand the
    # RM a drawdown-contribution figure derived from a −6% stop nobody proposed,
    # labelled as a reference and read as a measurement."
    #
    # The reason is structural, not stylistic: at RESEARCHERS and SYNTHESIS the
    # Trader has not spoken, so there IS no proposal — any figure here would be
    # minted from an invented stop, which is the DEF235 class this programme
    # keeps closing. What those two phases actually lacked was the risk budget's
    # consumption, and `_risk_state_block` above gives them that at every phase,
    # ungated. That is the half that is real.
    #
    # So DEF241 does NOT close on this batch. Its row records the residue as
    # open with this reasoning, rather than letting a re-scope pass as a fix.
    proposal = trade_proposal if phase in ("RISK", "VERDICT") else None
    # DEF241: `agent_size_pct` is the size THIS agent's role argues for, supplied
    # by the caller from `risk_debator_sizes` — never parsed back out of prose,
    # which is the surface DEF235 closed.
    drawdown_line = _drawdown_snapshot_line(
        mandate, proposal, agent_size_pct if proposal else None
    )
    # The deduped risk-state tier. Deliberately NOT gated on phase: the
    # consumption figures are real at every phase (unlike `proposal`, which does
    # not exist before EXECUTION), so every agent that argues about size gets
    # them — which is the finding all four of CR153/154/155/156 filed.
    risk_state_block = _risk_state_block(
        mandate,
        current_drawdown_pct,
        existing_open_risk_pct,
        last_loss_closed_at,
        trade_open_timestamps,
    )

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
        f"{risk_state_block}"
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

    # CR156 D — `base` already ends with `append_safety_floor(...)`, so on THIS
    # surface the floor sits in the MIDDLE of the prompt: everything above is
    # appended after it. `safety_floor.md` used to claim the floor is last and
    # therefore dominant; that is true on the 1-on-1 path and false here, on the
    # one surface where a verdict is parsed and acted on. Both the doc and this
    # line now say so.
    #
    # Not reordered: putting the JSON output contract before the transcript it
    # must summarise would be worse, and ordering was never the control —
    # `enforce_safety_floor()` is. CR038 measured prompt-level instructions at
    # ~30%, so "it is last, therefore it wins" is exactly the belief P2 forbids.
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


# CR145 Tier C — the lane matrix. `_format_profile` used to take no `agent_id`
# at all, so all twelve agents received a BYTE-IDENTICAL fact sheet carrying
# every domain's numbers. Measured over 18 convenes / 72 analyst turns, they
# used them: news_analyst cited valuation 16/18 and technicals 13/18,
# social_media_analyst cited technicals 13/18, fundamentals_analyst cited
# technicals 8/18. The four-analyst separation exists to produce four
# INDEPENDENT lenses; that is the product's core claim, and it was leaking.
#
# The matrix Saiful chose (2026-08-11) is DEFAULT-OPEN: only the four upstream
# analysts are firewalled. Bull, Bear, Research Manager, Trader, PM and the
# three Risk Debators keep the full sheet, because their job IS the cross-lane
# join — a Bull that cannot see technicals cannot weigh a thesis against them.
# An agent absent from this dict sees everything, so adding an agent fails open
# rather than silently starving it.
#
# CR143 Phase 3b rejected this concern using the M2b differentiation result (the
# four analysts were the least-similar pairing at 0.128). That was the wrong
# instrument and CR145 says so: agents can differ sharply in vocabulary while
# still borrowing each other's facts. Differentiation is not lane discipline.
_ALL_DOMAINS = frozenset({"fundamentals", "technicals", "news", "social"})

_AGENT_LANES: dict[AgentId, frozenset[str]] = {
    AgentId.FUNDAMENTALS_ANALYST: frozenset({"fundamentals"}),
    AgentId.MARKET_ANALYST: frozenset({"technicals"}),
    # `next_earnings` rides the news lane as well as the fundamentals one: a
    # scheduled earnings date IS a forward catalyst, which is the News Analyst's
    # own job description, not another desk's number.
    AgentId.NEWS_ANALYST: frozenset({"news"}),
    AgentId.SOCIAL_MEDIA_ANALYST: frozenset({"social"}),
}

_DOMAIN_LABELS = {
    "fundamentals": "company fundamentals and valuation",
    "technicals": "market technicals (RSI, trend, ranges, volume)",
    "news": "news and catalysts",
    "social": "retail sentiment and community activity",
}


def _lane_for(agent_id: AgentId | None) -> frozenset[str]:
    if agent_id is None:
        return _ALL_DOMAINS
    return _AGENT_LANES.get(agent_id, _ALL_DOMAINS)


def _out_of_lane_line(lane: frozenset[str]) -> str | None:
    """CR040 — a withheld lane announces itself, and says WHO has it.

    Silently omitting technicals from the News Analyst's sheet would leave it to
    conclude no technicals exist, and the next honest thing it does is tell the
    Room they are unavailable. That is a fabrication in the other direction: the
    data is live, it is simply another analyst's to speak to. This line is the
    difference between a firewall and a data gap.
    """
    missing = [_DOMAIN_LABELS[d] for d in ("fundamentals", "technicals", "news", "social")
               if d not in lane]
    if not missing:
        return None
    return (
        "Not in your lane this call: " + "; ".join(missing) + ". Another analyst "
        "on this desk holds each of those and will speak to it — this is a "
        "division of labour, NOT missing data. Do not estimate or infer them, "
        "do not ask for them, and do not tell the Room they are unavailable."
    )


def _format_profile(profile: dict[str, Any], agent_id: AgentId | None = None) -> str:
    """A compact ticker fact-sheet the agent can quote from.

    `agent_id=None` renders the FULL sheet and is the default: non-Room callers
    and `test_prompt_data_parity.py` ask "is this computed field rendered
    anywhere at all", which the lane split must not change the answer to. The
    Room always passes a real agent id (CR145 Tier C).

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
    lane = _lane_for(agent_id)

    def _in_lane(domain: str) -> bool:
        return domain in lane

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
    if not _in_lane("fundamentals"):
        pass  # out of lane — named in the lane line below, not disclosed as absent
    elif fundamentals_any_live:
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
    if not _in_lane("technicals"):
        pass  # out of lane — named in the lane line below, not disclosed as absent
    elif market_withheld:
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
    if not _in_lane("news"):
        pass  # out of lane — named in the lane line below, not disclosed as absent
    elif news_withheld_tenure:
        pass  # stripped below; no scaffolding line to contradict it with
    elif news_live:
        header_lines.append(
            # CR147 Tier B.1 — "as of this call" was the fetch's timing, never
            # the article's. SNOA's newest headline was 354 days old under this
            # exact line. `fetch_live_news` now drops anything past a 7-day
            # floor, so the claim the header makes is the one the filter
            # enforces; if nothing survives, this branch is not taken at all
            # and the synthetic-catalyst disclosure below runs instead.
            "- Recent catalyst/headline: LIVE, real news published within the "
            "last 7 days (publisher + per-item age shown below; anything older "
            "was dropped, not shown). Some headlines may carry a sentiment tag; "
            "treat it as one input, not a verdict."
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
    if not _in_lane("social"):
        pass  # out of lane — named in the lane line below, not disclosed as absent
    elif social_withheld_tenure:
        pass  # stripped below; no scaffolding line to contradict it with
    elif social_live:
        header_lines.append(
            # CR148 Tier B — "as of this call" was false for most turns: the
            # cache served rows averaging 20.2 days old (93% over a week) under
            # this sentence. The snapshot's real date is now rendered in the
            # detail block, so the header points at it instead of asserting a
            # freshness it never checked.
            "- Retail sentiment/mention/community fields: LIVE, real Reddit "
            "aggregate data — a point-in-time snapshot whose fetch date is "
            "shown with it below; read it as of THAT date, not as of now "
            "(Reddit only — no Twitter/X, StockTwits, Google Trends, or "
            "Discord data exists)."
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
    # DEF268 — gated on the NEWS lane, because the countdown it promises renders
    # only inside `_catalyst_line`, which is news-lane-gated. Ungated, this
    # bullet told the Fundamentals, Market and Social analysts that a real
    # forward catalyst was in their sheet when the lane split had removed it —
    # an affirmative-direction fabrication prompt, and worse than the
    # "unavailable" case this function's own CR098 comment designs against,
    # because an agent invited to use a catalyst it cannot see has to invent one.
    # Introduced by the lane split itself: before CR145 Tier C the bullet and the
    # body were both present for everyone.
    if _in_lane("news"):
        header_lines.append(
            "- Forward catalyst: the FOMC decision countdown below is REAL, "
            "from the Fed's published calendar."
        )
    lane_line = _out_of_lane_line(lane)
    if lane_line:
        header_lines.append(lane_line)
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
    # CR168 (folded into CR166) — WHICH instrument this sheet describes.
    # Deliberately NOT lane-gated: identity is the subject of the run, not one
    # desk's data, and an agent that cannot name the company it is analysing is
    # not firewalled, it is lost. It is also the reason the union-of-lanes test
    # still passes with it — a line every agent gets reaches every agent.
    lines.append(
        identity_line(
            profile.get("long_name") if _is("long_name", "live") else None,
            profile.get("ticker", ""),
            profile.get("exchange_name") if _is("exchange_name", "live") else None,
        )
    )
    # DEF262 — the reconciliation clause is TECHNICALS data and must obey the
    # lane, not just `field_state`. `last_close` is the final candle of the
    # 3-month price history; handing it to the News or Social Analyst put the
    # sheet in direct self-contradiction — *"market technicals … are not in your
    # lane this call. Do not estimate or infer them"* three lines above *"use
    # the last close for anything you compute."* The live quote itself stays
    # unconditional: a price is shared core every agent needs to read the
    # portfolio block, and it is not what the firewall withholds.
    lines.append(
        _reference_price_line(profile, technicals_live and _in_lane("technicals"))
    )
    if _in_lane("fundamentals"):
        # DEF233: both bases, each gated on its own `field_state` entry — a
        # provider gap on one is stated, never papered over with the other.
        lines.append(
            pe_line(
                profile.get("pe") if _is("pe", "live") else None,
                profile.get("forward_pe") if _is("forward_pe", "live") else None,
            )
        )
        # CR166 Tier B — the net margin moved OFF this line and onto
        # `Margin structure` below, which states it as the third term of
        # gross → operating → net. Stating one figure twice is the defect
        # `_reference_price_line` exists to reconcile for price; growth keeps
        # its own line because it has no structure to belong to.
        lines.append(
            f"TTM revenue growth: {profile.get('rev_growth')}%" if _is("rev_growth", "live")
            else "TTM revenue growth: not available"
        )
        lines.append(_net_position_line(profile))
        size_line = _company_size_line(profile)
        if size_line:
            lines.append(size_line)
        # CR166 Tier B — five groups, all from the same `.info` call that already
        # served every line above, all discarded at this render site until now.
        # Each is `field_state`-gated per field (CR104) and absent rather than
        # labelled when nothing in the group is live (DEF053).
        for extra in (
            margin_structure_line(
                profile.get("gross_margin") if _is("gross_margin", "live") else None,
                profile.get("operating_margin") if _is("operating_margin", "live") else None,
                profile.get("profit_margin") if _is("profit_margin", "live") else None,
            ),
            earnings_power_line(
                profile.get("trailing_eps") if _is("trailing_eps", "live") else None,
                profile.get("revenue_ttm") if _is("revenue_ttm", "live") else None,
                profile.get("revenue_per_share") if _is("revenue_per_share", "live") else None,
            ),
            returns_line(
                profile.get("return_on_equity") if _is("return_on_equity", "live") else None,
                profile.get("return_on_assets") if _is("return_on_assets", "live") else None,
            ),
            balance_sheet_line(
                profile.get("current_ratio") if _is("current_ratio", "live") else None,
                profile.get("quick_ratio") if _is("quick_ratio", "live") else None,
                profile.get("debt_to_equity") if _is("debt_to_equity", "live") else None,
            ),
            ownership_line(
                profile.get("held_pct_institutions") if _is("held_pct_institutions", "live") else None,
                profile.get("held_pct_insiders") if _is("held_pct_insiders", "live") else None,
                profile.get("shares_outstanding") if _is("shares_outstanding", "live") else None,
                profile.get("float_shares") if _is("float_shares", "live") else None,
            ),
        ):
            if extra:
                lines.append(extra)
    if not _in_lane("technicals"):
        pass
    elif market_withheld:
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
        lines.append(_moving_average_line(profile))
        lines.append(_volume_line(profile))
    else:
        lines.append("Market technicals: not available this call.")
    # 52-week range is a fundamentals field, independent of technicals —
    # `fetch_live_fundamentals` only sets `week52` LIVE when yfinance's real
    # fiftyTwoWeekLow/High fields were used, never for the ±5%-of-price
    # placeholder it falls back to internally (that placeholder is a derived
    # guess, not a measurement, so it earns no "52-week" label here).
    # Dual-lane, on DOMAIN rather than provenance: `week52` arrives from
    # `fetch_live_fundamentals`, but a 52-week high/low is a PRICE RANGE, which
    # is the Market Analyst's subject by any reading — and it already receives
    # the 50-day range. Gating it out would leave the range desk reasoning about
    # ranges with less context than the sheet holds, which is not lane
    # discipline, just an accident of which fetcher happened to return it.
    if (_in_lane("fundamentals") or _in_lane("technicals")) and _is("week52", "live"):
        # DEF262 — the LINE is dual-lane; its ANCHOR is not. On the Fundamentals
        # sheet this rendered "from the last close $268.4: -33.4% vs the high",
        # handing a technicals number to a desk firewalled out of technicals
        # inside a line that legitimately belongs to it. The percentages now
        # measure from the reference price there, and say so.
        lines.append(_week52_line(profile, technicals_in_lane=_in_lane("technicals")))
    if not _in_lane("news"):
        pass
    elif news_withheld_tenure:
        lines.append(
            "Recent catalyst/headline: not included in this session."
        )
    else:
        lines.append(_catalyst_line(profile))
    if not _in_lane("social"):
        pass
    elif social_withheld_tenure:
        lines.append(
            "Retail sentiment: not included in this session."
        )
    else:
        lines.append(
            f"Retail sentiment: {profile.get('sentiment_tone')} ({profile.get('sentiment_score')})"
        )
        lines += _social_detail_lines(profile)
    if _in_lane("fundamentals"):
        for extra in (_valuation_line(profile), _sector_line(profile),
                      _capital_allocation_line(profile), _analyst_line(profile)):
            if extra:
                lines.append(extra)
    # CR151 Tier A — the asymmetry, from two numbers already on the sheet.
    # Rendered for the FULL-SHEET agents only, which is the reconciliation
    # CR151 asked for explicitly ("say so in CR145 Tier C's matrix rather than
    # letting the two decisions drift"): the line is a cross-lane JOIN, so
    # rendering it to a firewalled analyst would hand back the very numbers the
    # firewall removes. CR151's own rationale for not gating it to SYNTHESIS is
    # that the errors originate upstream at the Bull and Bear — and Bull, Bear
    # and the Research Manager all keep the full sheet, so they still get it.
    if lane == _ALL_DOMAINS:
        asymmetry = _asymmetry_line(profile)
        if asymmetry:
            lines.append(asymmetry)
    if (
        (_in_lane("fundamentals") or _in_lane("news"))
        and profile.get("next_earnings_date")
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
    rendered verbatim as indented detail under 'Retail sentiment:', never recomputed.

    CR148 Tier A/B extends the same treatment to the rest of the payload, which
    arrived on the identical API call and was discarded: the classified split
    (whose neutral residue is the majority class and ran 42–71% unstated), the
    engagement dimension, the per-community breakdown, the small-sample caveat,
    and the snapshot's real age. Ordering is deliberate — the freshness label
    goes FIRST, because everything under it is only as true as its date."""
    if (profile.get("field_state") or {}).get("social") != "live":
        return []
    out: list[str] = []
    if profile.get("social_fetched_age"):
        out.append(f"  Snapshot: {profile['social_fetched_age']}")
    if profile.get("mention_trend"):
        out.append(f"  Mentions: {profile['mention_trend']}")
    if profile.get("pattern"):
        out.append(f"  {profile['pattern']}")
    if profile.get("sentiment_split"):
        out.append(f"  Classified: {profile['sentiment_split']}")
    if profile.get("social_engagement"):
        out.append(f"  Engagement: {profile['social_engagement']}")
    if profile.get("influencer_take"):
        out.append(f"  Communities: {profile['influencer_take']}")
    for line in (profile.get("subreddit_split") or ()):
        out.append(f"    {line}")
    if profile.get("subreddit_split"):
        # The prohibition sits WITH the data rather than in the agent profile,
        # where the same rule already exists and was broken in 9 of 18 turns.
        # The load-bearing half is the data above it; this line only names the
        # boundary of what was supplied (P2 — the sentence is not the control).
        out.append("    (No other community's numbers were supplied. Do not "
                   "attribute a figure, tone or trend to one that is not listed.)")
    if profile.get("social_sample_caveat"):
        out.append(f"  {profile['social_sample_caveat']}")
    return out


def _net_position_line(profile: dict[str, Any]) -> str:
    """Balance-sheet line, sign-aware: net cash vs net debt (never 'Net cash: $-42000M').

    CR179 Leg 0 — this read `net_cash` on presence alone, so a profile carrying
    `field_state["net_cash"] == "unavailable"` still rendered `Net debt $42000M`
    as fact, directly beneath a header saying none was available live this call.
    `_profile_for_ticker` does not currently produce that combination, but this
    function's contract is that it makes no assumption about its caller, and the
    runner writes the key on every path (`room_runner.py:524-529`) — an
    unreachable-today bug guarded by nothing is how CR104's other presence-only
    residue survived to be found here.
    """
    net_cash = profile.get("net_cash") if _field_is_live(profile, "net_cash") else None
    phrase = net_position_phrase(net_cash)
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
    CR104/D8: gated on `field_state`, not presence alone.

    CR179 Leg 0 — the gate covered `sector` and not `industry`, so a profile
    whose `field_state["industry"]` said `unavailable` still rendered the value
    under a `(LIVE)` label: `Sector/industry (LIVE): Technology / GHOST-INDUSTRY`.
    The runner has always written that key (`room_runner.py:541-545`); nothing
    read it. Presence-only gating is the exact residue CR104 exists to remove,
    and a `(LIVE)` label over an unavailable value is worse than no line — it is
    the fabrication the label was introduced to prevent.
    """
    if not profile.get("sector") or not _field_is_live(profile, "sector"):
        return None
    industry = (
        profile.get("industry") if _field_is_live(profile, "industry") else None
    )
    return f"Sector/industry (LIVE): {profile['sector']} / {industry or '—'}"


def _capital_allocation_line(profile: dict[str, Any]) -> str | None:
    """Dividend yield, rate, cover and ex-date (DEF053, extended by CR166 Tier B).

    Buybacks/M&A still have no yfinance field and stay undisclosed rather than
    fabricated — CR145 Tier D owns the `.cashflow` call that would change that.
    What CR166 adds is the half that makes the yield mean something: the payout
    ratio (can it keep paying?) and the ex-date, both already fetched — the
    latter on the `EarningsInfo` object this sheet's next-earnings line comes
    off (CR030). CR104/D8: every part gated on `field_state`, not presence.
    """
    return dividend_line(
        profile.get("dividend_yield") if _field_is_live(profile, "dividend_yield") else None,
        profile.get("dividend_rate") if _field_is_live(profile, "dividend_rate") else None,
        profile.get("payout_ratio") if _field_is_live(profile, "payout_ratio") else None,
        profile.get("ex_dividend_date") if _field_is_live(profile, "ex_dividend_date") else None,
        today=_run_date(profile),
    )


def _analyst_line(profile: dict[str, Any]) -> str | None:
    """Real analyst consensus (DEF053) — the closest honest proxy for
    'forward guidance' available. Explicitly labeled as the Street's view,
    not the company's own guidance (which yfinance doesn't expose). CR104/D8:
    gated on `field_state` — target price and rating are fetched together, so
    either one's provenance recorded live is sufficient to label the line.

    CR166 Tier B adds the DISPERSION. *"buy, target $322.82"* reads as a
    precision the consensus does not have: the same consensus is 41 analysts
    spanning $215–$400 with the mean below the median. All five figures were in
    the dict already fetched, and all five ride CR035's suppression flag with
    the mean — an ablation arm that stripped the target but left the range
    standing would leak the figure it exists to remove.
    """
    has_target = profile.get("analyst_target_price") and _field_is_live(profile, "analyst_target_price")
    has_rating = profile.get("analyst_rating") and _field_is_live(profile, "analyst_rating")
    if not has_target and not has_rating:
        return None
    return analyst_consensus_line(
        profile.get("analyst_rating") if has_rating else None,
        profile.get("analyst_target_price") if has_target else None,
        profile.get("analyst_opinion_count") if _field_is_live(profile, "analyst_opinion_count") else None,
        profile.get("analyst_target_high") if _field_is_live(profile, "analyst_target_high") else None,
        profile.get("analyst_target_low") if _field_is_live(profile, "analyst_target_low") else None,
        profile.get("analyst_target_median") if _field_is_live(profile, "analyst_target_median") else None,
        profile.get("analyst_rating_score") if _field_is_live(profile, "analyst_rating_score") else None,
    )


def _run_date(profile: dict[str, Any]) -> date | None:
    """The sheet's own run-date anchor as a `date`, or None if it isn't live.

    DEF124/D2 made `run_date` the single anchor every other absolute date on the
    sheet is measured from; this is the accessor for the render sites that need
    to compute an interval rather than print one.
    """
    raw = profile.get("run_date")
    if not raw or not _field_is_live(profile, "run_date"):
        return None
    try:
        return date.fromisoformat(str(raw))
    except ValueError:
        return None


def _reference_price_line(profile: dict[str, Any], technicals_live: bool) -> str:
    """CR146 Tier B — the sheet carried TWO prices for the same thing.

    `Reference price` is the quote; `last close` is the final candle of the
    3-month history. They diverge in **7 of 16** post-fix prompts — small (max
    0.27%, NBIS $189.22 vs $189.31) but real, and one turn read them as two
    facts: *"Price at $189.31 … and the final close $189.22 firmly inside this
    wide band"*. Two prices on a sheet read by the agent whose entire job is
    price.

    Neither is deleted — they are genuinely different measurements from
    different sources, and dropping one would hide a real provider disagreement.
    They are RECONCILED: when both are live and they differ, one line says what
    each is and that they are the same instrument. When they agree, or only one
    exists, there is nothing to reconcile and the extra words would be noise.
    """
    if not _field_is_live(profile, "base_price"):
        return "Reference price: not available"
    base = profile.get("base_price")
    line = f"Reference price: ${base}"
    last_close = profile.get("last_close")
    if not technicals_live or last_close is None:
        return line
    b, lc = _safe_num(base), _safe_num(last_close)
    if b is None or lc is None or b == lc:
        return line
    return (
        f"{line} (the live quote) and ${last_close} (the last close, final "
        "candle of the 3-month history) — the SAME instrument measured by two "
        "sources, not two facts. Use the last close for anything you compute."
    )


def _company_size_line(profile: dict[str, Any]) -> str | None:
    """CR145 Tier A / CR150 A2 — market cap, FCF in dollars, gross debt.

    All three were fetched and discarded: market cap and FCF were consumed as
    the denominator and numerator of `fcf_yield`, gross debt inside `net_cash`.

    Market cap is the one that changes what an agent can do. The mandate carries
    *"Liquid only. Avoid microcaps (< $500M market cap)"* as a HARD constraint in
    **17 of 18** prompts, **0 of 18** fact sheets stated a market cap, and the
    same prompt forbids recalling one from training memory. The rule was
    unfollowable by construction; this is what makes it checkable.

    Each part is independently `field_state`-gated (CR104), and the line is
    absent rather than labelled when nothing is live (DEF053).
    """
    parts = []
    if profile.get("market_cap") is not None and _field_is_live(profile, "market_cap"):
        parts.append(f"market cap ${profile['market_cap']:,}M")
    if profile.get("free_cash_flow") is not None and _field_is_live(profile, "free_cash_flow"):
        parts.append(f"FCF ${profile['free_cash_flow']:,}M (TTM)")
    if profile.get("total_debt") is not None and _field_is_live(profile, "total_debt"):
        # Gross, beside the netted figure on the line above. A netted number
        # hides leverage: $40B cash against $45B debt and $1B against $6B both
        # render as "net debt $5,000M", and they are not the same balance sheet.
        parts.append(f"gross debt ${profile['total_debt']:,}M")
    if not parts:
        return None
    return "Company size (LIVE): " + ", ".join(parts)


def _week52_line(profile: dict[str, Any], *, technicals_in_lane: bool = True) -> str:
    """CR150 A3 — the 52-week range with where price sits against BOTH ends.

    Arithmetic on numbers already on the sheet, same justification as DEF228 and
    `_asymmetry_line`. This is specifically the figure the Bear reaches for and
    gets wrong: on SNDK it wrote **83%** for an actual **−48.0%** below the high,
    and that became the stance headline the comb rendered.

    Anchored on the same price `_asymmetry_line` uses and named the same way, so
    the two derived lines can never disagree about what "price" meant.
    """
    low, high = profile.get("low"), profile.get("high")
    base = f"52-week range: ${low}–${high}"
    anchor, anchor_name = _price_anchor(profile, technicals_in_lane=technicals_in_lane)
    lo, hi = _safe_num(low), _safe_num(high)
    if anchor is None or lo is None or hi is None or lo <= 0 or hi <= 0:
        return base
    return (
        f"{base}; from {anchor_name} ${anchor}: "
        f"{(anchor - hi) / hi * 100:+.1f}% vs the high, "
        f"{(anchor - lo) / lo * 100:+.1f}% vs the low"
    )


def _moving_average_line(profile: dict[str, Any]) -> str:
    """CR146 Tier B — the two averages `trend` is a bucketing of.

    `compute_technicals` derives `trend` from `price > sma_short > sma_long` and
    then throws both away, so an agent told *"uptrend"* cannot say whether price
    is 0.4% or 14% above the 50-day. They ride `field_state["technicals"]` with
    the rest of the block, so this is only called when that is live.
    """
    short, long = _safe_num(profile.get("sma_short")), _safe_num(profile.get("sma_long"))
    if short is None or long is None:
        return f"Trend: {profile.get('trend')} (20/50-day moving averages not available)"
    line = f"20-day SMA: ${short}, 50-day SMA: ${long}"
    anchor, name = _price_anchor(profile)
    if anchor is not None and long > 0:
        # DEF262 — PRINT the anchor's name, never the literal "last close".
        # This line bound the name and discarded it, so on a sheet where the
        # anchor had fallen back to the reference price it announced a
        # comparison against a "last close" the sheet never stated — the exact
        # DEF228 shape `_price_anchor` exists to prevent, reintroduced by the
        # commit that introduced `_price_anchor`.
        line += f" — {name} is {(anchor - long) / long * 100:+.1f}% vs the 50-day"
    return line


def _volume_line(profile: dict[str, Any]) -> str:
    """The volume ratio the tone is a bucketing of (>1.1 / <0.9 / else). Same
    reason as `_moving_average_line`: "above 20-day average" is true at 1.11×
    and at 9×, and those are not the same tape."""
    ratio = _safe_num(profile.get("volume_ratio"))
    tone = profile.get("volume_tone")
    if ratio is None:
        return f"Volume: {tone}"
    return f"Volume: {tone} ({ratio:.2f}× the 20-day average, 5-day mean)"


def _price_anchor(
    profile: dict[str, Any], *, technicals_in_lane: bool = True
) -> tuple[float | None, str]:
    """The ONE price every derived line measures from, and its name.

    DEF228 happened because the fact sheet carries two prices — `Reference
    price` (fundamentals) and `last close` (technicals) — and a derived figure
    took one half from each. Every derived line routes through here so they
    cannot disagree, and each one prints the name so the reader knows which.

    **DEF262 — the anchor obeys the lane.** The last close is the final candle
    of the 3-month price history, so it is technicals data, and an agent
    firewalled out of technicals must not receive it through the back door of a
    derived line. `_week52_line` is the case that proved this: the 52-week range
    is DUAL-lane (a price range the Market Analyst needs, a valuation bound the
    Fundamentals Analyst needs), so it renders on the fundamentals sheet — and it
    anchored on the last close, quietly handing that desk a technicals number
    inside a legitimately-in-lane line. The line stays; only its anchor moves.

    The name is not decoration. It is what makes the fallback legible: a reader
    told *"-33.4% vs the high"* cannot tell which of two prices that came from,
    and printing the wrong name is the DEF228 failure with extra steps.
    """
    if (
        technicals_in_lane
        and _field_is_live(profile, "technicals")
        and profile.get("last_close")
    ):
        return _safe_num(profile.get("last_close")), "the last close"
    if _field_is_live(profile, "base_price") and profile.get("base_price"):
        return _safe_num(profile.get("base_price")), "the reference price"
    return None, ""


def _asymmetry_line(profile: dict[str, Any]) -> str | None:
    """CR151 Tier A — the up/down asymmetry, computed rather than left to be
    joined wrong.

    No new provider, no new fetch, no new field: the anchor price, the Street's
    consensus target and the 50-day range low are all already rendered and
    already labelled `(LIVE)`. The precedent is exact — DEF228 added the
    range-position figure on the reasoning *"this is arithmetic on two numbers
    already on the sheet — it asserts nothing new"*, for the same reason: an
    agent joined two rendered numbers wrongly and the whole Room adopted it.
    Not to be confused with `trading_math.trade.trade_asymmetry`, which measures
    a PROPOSED TRADE's geometry (entry/stop/target) and is read by two post-hoc
    call sites only (`room_runner.py:1380`, `:3461`) — it is rendered into no
    prompt, so no agent has ever seen an asymmetry figure of any kind. This line
    is the market's asymmetry around a price, computed before a trade exists,
    which is what the researchers argue over.

    **One anchor, named in the line.** The sheet carries two prices —
    `Reference price` (fundamentals) and `last close` (technicals) — and
    deriving one half from each is precisely how DEF228 happened. `last_close`
    is used when technicals are live, `base_price` otherwise, and the line says
    which. Each half is independently gated (CR104): a missing target drops the
    upside clause, not the line.
    """
    technicals_live = _field_is_live(profile, "technicals")
    # CR146 Tier B: `_price_anchor` is the single source of truth for which of
    # the sheet's two prices a derived line measured from — shared with
    # `_week52_line` and `_moving_average_line` so they cannot disagree.
    anchor, anchor_name = _price_anchor(profile)
    if not anchor or anchor <= 0:
        return None

    target = (
        _safe_num(profile.get("analyst_target_price"))
        if _field_is_live(profile, "analyst_target_price") else None
    )
    support = _safe_num(profile.get("support")) if technicals_live else None

    clauses = []
    if target and target > 0:
        clauses.append(
            f"**{(target - anchor) / anchor * 100:+.1f}%** to the consensus target ${target}"
        )
    if support and support > 0:
        clauses.append(
            f"**{(support - anchor) / anchor * 100:+.1f}%** to the 50-day range low ${support}"
        )
    if not clauses:
        return None
    return (
        f"Asymmetry from {anchor_name} ${anchor}: " + ", ".join(clauses) + ". "
        "AMI's arithmetic on the two lines above — the Street's target is not a "
        "trade target and the range low is not a stop."
    )


def _safe_num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
