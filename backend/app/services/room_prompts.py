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

import re
from collections.abc import Sequence
from datetime import date, datetime, timezone
from typing import Any

from app.agents.safety_floor import CONTEXT_NOT_SUPPLIED
from app.schemas import AgentId, AgentMessage, Mandate, agent_display_name
from app.schemas.mandate import Plan
from app.services.agent_prompts import build_agent_prompt
from app.services.fundamentals import (
    analyst_consensus_line,
    balance_sheet_line,
    dividend_line,
    earnings_power_line,
    identity_line,
    buyback_line,
    capital_return_line,
    day_move_line,
    liquidity_line,
    margin_structure_line,
    margin_trend_line,
    primary_trend_line,
    relative_strength_line,
    risk_profile_line,
    short_interest_line,
    ownership_line,
    pe_line,
    peg_part,
    returns_line,
)
from app.core.config import settings
from app.services.journal_context import build_journal_context_block
from app.services.llm_gateway import ChatMessage
from app.services.technicals import range_position_pct
from app.trading_math.option_ladder import LadderOption, build_option_ladder
from app.trading_math.portfolio import shares_for_size
from app.trading_math.risk import drawdown_contribution
# DEF263 — the SAME window helpers `enforce_safety_floor` counts with. A second
# implementation of "today" is how the prompt and the brake come to disagree.
#
# CR219 R49 extends that list to the RESOLVERS and the cooldown predicate, for
# the same reason: `_floor_state_preview` states what the floor will DECIDE, and
# a second implementation of "in cooldown" or "the day cap is N" is how the
# preview comes to promise one thing while `enforce_safety_floor` does another.
# These are the identical symbols `safety_floor.py` imports (its aliases are
# `_`-prefixed; same functions).
from app.trading_math.risk_limits import (
    cooldown_lifts_at,
    in_cooldown,
    resolved_max_open_risk_pct,
    resolved_max_trades_per_day,
    resolved_max_trades_per_week,
    resolved_post_loss_cooldown_hours,
    trades_since,
    utc_day_start,
    utc_week_start,
)
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
#
# ── DEF289 (AT:R68, CR179 Leg 2) — the ratio above is wrong, by ~50% ────────
#
# Everything above stands EXCEPT its one unmeasured input. `~1,900 chars ≈ 400
# tokens` is **4.75 chars per token**, and it was never measured — it is the
# arithmetic that every budget in this dict was then derived from, so being
# wrong about it is wrong about all twelve at once.
#
# It is measurable from our own data with no tokenizer at all, because a
# truncated turn is a turn that hit `max_tokens` EXACTLY: its length in chars,
# divided by that agent's cap, IS the ratio. Over the committed 2026-08-13
# epoch (`corpus/llm_audit_2026-08-13-epoch.json`, 482 rows, same "ends on an
# alphanumeric" test as the 30-day measurement above), six turns were cut:
#
#   bull_researcher    3,057 chars / 800  = 3.82      bear_researcher 2,705 / 800  = 3.38
#   bull_researcher    3,220 chars / 800  = 4.03      bear_researcher 2,769 / 800  = 3.46
#   neutral_debator    2,144 chars / 600  = 3.57      portfolio_mgr   3,456 / 1100 = 3.14
#
# **3.14–4.03, mean 3.52 — not 4.75.** A token buys ~34% fewer characters than
# the comment claims, so every cap here is ~34% short in the only unit that
# matters. The spread is not noise either: the PM is the low end because it
# emits JSON, and quotes, braces and field names tokenize worse than prose.
#
# The consequence was live and measured, not theoretical: **6/482 = 1.2% of
# turns were being amputated mid-word** — bull 2/40, bear 2/40, neutral 1/40,
# PM 1/42 — which is CR106 B2's silent stance loss on the prose agents and, on
# the PM, DEF258/DEF261's unparseable envelope failing safe to PASS. This is
# also DEF236's acceptance finally being RUN: it raised the PM to 1100 "derived
# from the new ask, not measured", and the answer is that 1100 was still short.
#
# **The derivation now, stated so the next sheet growth can re-run it.** Caps
# are `max_observed_chars ÷ 3.14 × factor`, rounded up to the nearest 100:
#
#   - **3.14**, the single worst measured ratio across both output shapes, so
#     no agent is sized on a ratio its own output can beat.
#   - **factor 1.5 where the agent truncated** — its observed maximum is
#     CENSORED (the cap itself produced that number), so the true maximum is
#     unknown and larger; bull, bear, neutral, PM.
#   - **factor 1.25 where it did not** — the maximum is a real observation, and
#     40 turns of it; the eight others.
#
# Raising remains free on this host for the reason measured above (`max_tokens`
# is a ceiling, not an allocation; `num_preemptions_total` 0), and the cap was
# never the verbosity control — `_LENGTH_GUIDE` is, and DEF236 closed it at
# 7.1% over-guide. A cap that binds does not shorten a turn, it guillotines
# one. NOT claimed: that truncation reaches 0. That is a post-promotion
# re-measure on the Leg 5 corpus, and asserting it here is the CR105
# Amendment-1 trap this build exists to stop repeating.
#
# **The floor moves too, and for the same arithmetic.** DEF125 set 600 because
# it *"clears the 1,531-char (~322-token) worst case those five have ever
# produced"* by ~75%. 1,531 chars is **488** tokens at the measured ratio, not
# 322, so the real margin was ~23% and `test_no_agent_is_budgeted_below_the_floor`
# had been asserting a 1.5× headroom the number could not deliver. 488 × 1.5 =
# 732 → **800**. The 1,531-char figure is kept rather than replaced by this
# epoch's 1,289: it comes from ~884 calls per agent against 40 here, and the
# larger sample is the better worst case.
_DEFAULT_AGENT_MAX_TOKENS = 800

# The measured worst-case characters-per-token, from the six truncated turns
# above. Named rather than inlined because `test_cr179_token_budget_derivation`
# re-runs the whole derivation against it — a future edit to a cap has to move
# this number or fail.
_CHARS_PER_TOKEN_WORST_CASE = 3.14

_AGENT_MAX_TOKENS: dict[AgentId, int] = {
    # The four analysts are the only agents that never approached their cap:
    # observed maxima 1,112–1,289 chars, i.e. 354–410 tokens. They sit at the
    # floor, and the floor is what moved.
    AgentId.FUNDAMENTALS_ANALYST: 800,
    AgentId.MARKET_ANALYST: 800,
    AgentId.NEWS_ANALYST: 800,
    AgentId.SOCIAL_MEDIA_ANALYST: 800,
    # Thesis + evidence + falsifier, in three-to-five sentences, and both
    # researchers write to the same shape — budget them symmetrically so the
    # Bear case is never the shorter one for a reason the reader cannot see.
    #
    # DEF289: both truncate at 5% (2/40 each). Symmetry is kept as a rule but
    # it is no longer kept by giving them the SAME number — the Bull's censored
    # maximum is 3,220 chars against the Bear's 2,769, so an equal cap would
    # bind the Bull first and reintroduce exactly the invisible asymmetry this
    # comment exists to prevent. Equal treatment is the same derivation, not
    # the same integer.
    AgentId.BULL_RESEARCHER: 1600,
    AgentId.BEAR_RESEARCHER: 1400,
    # The worst case and the most damaging: the RM's synthesis is the single
    # input EXECUTION and RISK reason from (DEF095 — the transcript is the
    # contagion vector), and it was cut off in two convenes out of three.
    #
    # DEF289: 0/40 truncated at 900 — the one agent the previous pass fixed
    # outright. But its uncensored maximum is 3,114 chars, which needs 992
    # tokens at the worst ratio: it finished inside the cap on this epoch with
    # ~0 to spare, and Legs 2–3 grow its sheet.
    #
    # Its own derivation lands at 1,300, and it is held at the Bull's 1,600
    # instead. DEF125 requires the RM to hold the most headroom of the three
    # because its synthesis is the only input EXECUTION and RISK see, and that
    # damage argument is untouched by this defect — what changed is only that
    # the RM is no longer the *most truncated* of the three, which was never
    # the reason it was ranked first.
    AgentId.RESEARCH_MANAGER: 1600,
    # Only 2.1%, but a truncated Trader loses the level triple that
    # `_LEVEL_PATTERNS` and the whole downstream geometry depend on — the one
    # agent where a cut tail is unparseable rather than merely incomplete.
    #
    # DEF289: 0/40 now, but at 1,881 chars observed it sat at 1.05× of 600 —
    # one long turn from the failure its own comment names.
    AgentId.TRADER: 800,
    # DEF289: 0/40 each, and all three sat between 1.05× and 1.20× — the
    # Neutral is the one that actually crossed (1/40), and it crossed because
    # it argues the middle and has to restate both sides to do it.
    #
    # DEF303 — the Leg 5 acceptance, run on the post-fix epoch DEF289 said would
    # be the real test. The Conservative is now the ONLY agent whose cap binds:
    # 1/39 turns finished at exactly 800/800 output tokens, headroom 1.00×,
    # against 1.34–3.43× for the other eleven. Its observation is therefore
    # CENSORED and its true maximum is unknown — factor 1.5, not 1.25.
    #
    # The two instruments bracket 1200–1300 and the wider is taken. Measured
    # tokens say 800 × 1.5 = 1200; the codified character rule (2,538 chars ÷
    # 3.14 × 1.5) says 1300. Applied verbatim rather than re-tuned, per DEF243's
    # corollary.
    #
    # The Aggressive is deliberately NOT raised, and that is the same
    # measurement disagreeing with itself. The character rule demands 1000 for
    # it; the tokens say 599 of 800, a clean observation needing 800. The proxy
    # over-states it because 3.14 is the GLOBAL worst ratio, measured off the
    # PM's JSON envelope, while this agent's own prose runs at 3.95 chars/token
    # — sizing a prose agent on the JSON agent's ratio is DEF289's own 4.75
    # mistake pointed the other way.
    AgentId.AGGRESSIVE_DEBATOR: 800,
    AgentId.CONSERVATIVE_DEBATOR: 1300,
    AgentId.NEUTRAL_DEBATOR: 1100,
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
    #
    # DEF289 ran that acceptance: 1/42 still clipped at 1100, and the PM is the
    # agent with the worst chars-per-token of the twelve (3.14) precisely
    # because of the JSON its cost paragraph is about.
    AgentId.PORTFOLIO_MANAGER: 1700,
    # CR201 — the structured Risk Officer (internal compute agent, not one of the
    # twelve; absent from `_LENGTH_GUIDE` deliberately — its length contract is the
    # JSON schema in `risk_officer.build_risk_officer_instruction`, not a prose
    # guide, and the DEF125 roster test pins the guide at exactly twelve).
    #
    # Derived by CR179's rule, from the only measured corpus of this agent that
    # exists: CR197's v8 arm ran this exact contract 136 times on the serving
    # model under a 1,200-token ceiling
    # (`docs/forward_planning/CR197_risk_debate_effectiveness/ablation/`), and
    # 2/136 replies failed to parse. The committed artifact records the PM's
    # replies, not the officer's, so whether those two failures were ceiling
    # hits is UNKNOWABLE from it — which makes 1,200 a censored observation by
    # CR179's own rule (a maximum whose ceiling may have produced it earns 1.5,
    # not 1.25): 1200 × 1.5 = **1800**.
    #
    # Cross-checked against the char proxy on the closest measured JSON shape:
    # this agent emits a JSON envelope like the PM, whose measured worst ratio
    # (3.14 chars/token) and censored 3,456-char maximum derived the PM's 1700.
    # The officer's ask (3 options × two one-sentence cases + a quoted figure,
    # plus 3 scalar fields) is bounded by the PM's shape, and 1800 clears it.
    # Raising is free on this host (`max_tokens` is a ceiling, not an
    # allocation; `num_preemptions_total` 0) and being short is uniquely
    # expensive here: a clipped JSON reply is unparseable rather than merely
    # incomplete, and costs the run the whole assessment (fallback floor 11.8%
    # vs 16.4% — measured, CR197), not one voice's tail.
    AgentId.RISK_OFFICER: 1800,
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
    "analyst, the Bull/Bear debate, the Execution Desk's proposal, and the three "
    "Risk Officers — then decide for yourself. Do not just restate the "
    "Execution Desk's numbers; agree or disagree based on the whole debate.\n"
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
    'rationale, written for the user>",\n'
    # CR219 R52 — the kill criterion. Required on BOTH actions: an APPROVE
    # without one is a position with no exit thesis, and a PASS without one is a
    # refusal the user cannot ever revisit ("what would have to change for you to
    # buy this?" is the question a PASS leaves open).
    #
    # The "from the data block above" clause is the load-bearing half. WP02 R11's
    # vocabulary rule applies: a criterion naming a quantity nothing fetches
    # ("if guidance is cut at the analyst day") is unfalsifiable at the next
    # convene, so it teaches the user nothing and cannot be scored. Anchoring it
    # to the sheet is what makes it checkable — by the user, by the next
    # convene's delta line, and by a harness scorer.
    ' "kill_criterion": "<one sentence: the specific, observable change that '
    "would reverse this call. It MUST name a quantity from the data block above "
    "— a price level, a moving average, a margin or growth rate, a multiple, a "
    "short-interest or ownership figure — and state the direction and the "
    # Single quotes in the examples, deliberately: this sentence sits INSIDE a
    # JSON string in a shape the model is copying, and a literal double quote
    # here reads as the end of that string. The CIO already loses whole verdicts
    # to JSON it broke itself (a raw newline in narration, warned about two
    # lines below) — an escaping trap in our own template would be ours.
    "threshold that would flip you. 'A second consecutive quarter of operating "
    "margin below 11.2%' and 'a daily close under the 200-day SMA at $769.48' "
    "are criteria; 'deteriorating fundamentals' and 'if sentiment worsens' are "
    "not, because nothing on your sheet can ever settle them. Write one for a "
    'PASS too — say what would make you buy>"}\n'
    "Write any line break inside narration as the two characters \\n, never as a "
    "real line break — a raw newline inside a JSON string is what makes a whole "
    "verdict unparseable.\n"
    "There are exactly two action values: APPROVE and PASS. A modification IS "
    "an approval — if you want to cut the Trader's size, tighten the stop, or "
    "shift the entry, use action APPROVE with your revised numbers in "
    "size_pct/entry/stop and explain the change in narration. Do NOT write "
    "'MODIFY', 'MODIFY-AND-APPROVE', or any other value — they are coerced to "
    "APPROVE at your stated numbers, which is very likely not what you meant "
    "by 'modify'.\n"
    "Use PASS when the debate does not support entering a position right now "
    "(e.g. the Trader recommended WAIT, or the risk/reward doesn't clear the "
    "bar) — PASS needs only narration, no size/entry/stop/target.\n"
    "The safety floor above still applies regardless of what you decide — "
    "if it detects a violation, output PASS and name the rule in narration."
)

# CR172 §10 step 2 — appended to `_PM_VERDICT_FORMAT` ONLY when the run issued a
# candidate menu. A mandate that does not permit derivatives issues none, so its
# PM prompt is byte-identical to what it was before this CR — which is also what
# keeps the CR201 ablation corpus comparable.
#
# The key is an INDEX and nothing else. §10's rule is that AMI computes and the
# PM picks; a model that states a strike, a premium or a greek has computed a
# number it presents as fact, which is P5's definition of the defect. So the
# format never asks for one, and `_parse_pm_verdict` reads every figure back off
# the candidate rather than out of the reply.
_PM_STRUCTURE_FORMAT = (
    "\nOne more optional key, because this run carries costed option "
    "structures (listed above):\n"
    ' "structure_id": <the bracketed number of ONE structure from that list, '
    "or omit the key entirely for a plain share position>\n"
    "Rules for it, all four of which are enforced after you reply:\n"
    "- It is an INDEX into that list. Never write a strike, a premium, a "
    "greek, a contract count or an expiry of your own — every figure of the "
    "structure comes from the list, and one you state instead is discarded.\n"
    "- Only on an APPROVE. A PASS opens nothing, so a structure on it is "
    "meaningless.\n"
    "- A number that is not in the list, or a structure the list marks "
    "FORBIDDEN, turns your whole verdict into a PASS. If the structure you "
    "want is forbidden, say so in your narration and approve the shares "
    "instead, or PASS — do not name it.\n"
    "- size_pct/entry/stop/target stay REQUIRED and keep describing the "
    "underlying view. The structure is how the view is expressed, not a "
    "replacement for it.\n"
    "Omitting the key is a perfectly good answer: shares are the right "
    "instrument for most theses, and an option is only better when its "
    "specific shape — a floor, a cap, a paid premium — is what the debate "
    "argued for. Say in your narration why the structure you picked fits.\n"
)

# CR210 — the bound on the PM's `narration`, and it is USER-VISIBLE text.
#
# `narration` is what `_pm_narration` returns as the displayed verdict and as
# `Verdict.reason` — the string rendered as the decision's justification. A
# `maxLength` hit chops MID-WORD on this backend (verified 2026-08-25) while
# still closing the JSON validly, so it is a SILENT truncation: `finish_reason`
# is "stop" and none of the three existing disclosure paths fire. Hence both a
# generous bound and the exact detector in `_parse_pm_verdict`.
#
# 3600, not CR196's 1200, and the two derivations agree:
#   * From the ask. `_LENGTH_GUIDE[PORTFOLIO_MANAGER]` is "one decision sentence,
#     then up to 6 short bullets" — roughly 1,300-1,400 chars. CR179's
#     censored-observation factor of 1.5 on top of a 2x margin lands near 3,500.
#   * From the measurement. The PM's recorded censored maximum is 3,456 chars for
#     the whole envelope, of which scaffolding and numbers are ~120.
# And it stays under the budget, which is the property the bound exists for:
# 3600 + ~140 scaffolding = 3,740 < 1700 * 3.14 = 5,338. The grammar terminates
# before the decode budget does.
PM_NARRATION_MAX_CHARS = 3600


def pm_verdict_schema(option_candidates: Sequence[Any] | None = None) -> dict[str, Any]:
    """CR210 — the machine half of `_PM_VERDICT_FORMAT`, as a decoding grammar.

    Mirrors that instruction key for key, and the mirror is TESTED
    (`test_cr210_pm_schema_matches_the_prompt`): two descriptions of one contract
    in two languages is exactly how DEF236 shipped, a length guide counting
    sentences beside a format asking for bullets.

    `action` is exactly `["APPROVE", "PASS"]`. `_normalize_pm_action`'s
    REJECT/MODIFY coercion stays for the providers that cannot enforce a grammar,
    and becomes unreachable on vLLM — which is the point. CR156 B's user-visible
    defect (a card marked PASS whose narration opens "REJECT:") and the four
    off-contract actions measured in production (`MODIFY-AND-APPROVE` x3,
    `MODIFY` x1 over 136 convenes) both become structurally impossible rather
    than discouraged in three places.

    EVERY property is in `required`, with nullable unions for the ones that only
    apply to an APPROVE. Two concrete reasons, not style:
      * `strict: true` on the OpenAI json_schema wrapper is specified to require
        exactly that, and a schema this server will not compile returns an
        in-band error frame (DEF376), not a helpful message.
      * `if/then/allOf` — the natural way to say "size_pct required when action
        is APPROVE" — has UNVERIFIED support on this backend. That rule already
        lives, tested, in `_parse_pm_verdict`, which refuses an APPROVE with no
        usable size. Trading a tested rule for an untested one buys nothing.

    The alternative — `required: ["action", "narration"]` with the rest genuinely
    optional — was TRIED against the live model on 2026-08-27 and is worse. On a
    PASS-shaped prompt it returned `{"action": "APPROVE", "target": null,
    "narration": …}`: a haphazard subset, one nulled field and no size, where the
    all-required schema on the same prompt shape filled every field coherently.
    Making a key optional does not make the model consider it.

    Worth stating because it bounds what this buys: that same reply narrated a
    WAIT while emitting `action: "APPROVE"`. A grammar guarantees FORM. It has
    nothing to say about a verdict whose action contradicts its own prose — what
    catches that is `_parse_pm_verdict` refusing an APPROVE with no usable
    `size_pct` and failing safe to PASS, which is unchanged and still load-bearing.

    `structure_id` exists ONLY when the run issued a menu, exactly as
    `_PM_STRUCTURE_FORMAT` is appended only then. On a run with no menu the key
    is not merely discouraged but unrepresentable; when there IS a menu,
    `minimum`/`maximum` bound it to the issued set, making the first of
    `_resolve_pm_structure`'s three rejections impossible. The other two (a
    FORBIDDEN candidate, a structure with no legs) stay in Python, where the
    knowledge lives.
    """
    properties: dict[str, Any] = {
        "action": {"type": "string", "enum": ["APPROVE", "PASS"]},
        "size_pct": {"type": ["number", "null"]},
        "entry": {"type": ["number", "null"]},
        "stop": {"type": ["number", "null"]},
        "target": {"type": ["number", "null"]},
        "horizon_days": {"type": ["integer", "null"]},
        # minLength alongside maxLength: `score_S4.has_narration` is
        # `bool(obj.get("narration"))`, and a maxLength-only string admits "".
        # A grammar that permits an empty rationale would satisfy every
        # structural check while removing the only thing the user reads.
        "narration": {
            "type": "string", "minLength": 1, "maxLength": PM_NARRATION_MAX_CHARS,
        },
        # CR219 R52 — a plain bounded string, NOT a `prefixItems` array or an
        # enum. The CR210 acceptance-3 note is the reason that is worth saying:
        # both measured regressions there came from a grammar that constrained
        # the WRONG thing (a shared-enum `items` that pinned vocabulary but not
        # uniqueness; a Side alternation that dropped a line it should have
        # pinned), and each scored WORSE than no grammar at all with the model
        # behaving no differently. What is structural about a kill criterion is
        # that it EXISTS and is one sentence — both expressible as length bounds.
        # Whether it names a sheet quantity is semantic, so it is asked for in
        # the prompt and measured by a scorer, never faked as a grammar.
        "kill_criterion": {
            "type": "string",
            "minLength": PM_KILL_CRITERION_MIN_CHARS,
            "maxLength": PM_KILL_CRITERION_MAX_CHARS,
        },
    }
    if option_candidates:
        properties["structure_id"] = {
            "type": ["integer", "null"],
            "minimum": 0,
            "maximum": len(option_candidates) - 1,
        }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties),
        "properties": properties,
    }


# DEF236 — STYLE only. The shape (a thesis sentence, then how many bullets) is
# stated once, in `_LENGTH_GUIDE`, and no longer restated here in a different
# unit. See that dict for what the contradiction cost.
#
# R20 (CR219, ruled in QWEN's review track) — the global derivation policy,
# stated once here rather than per-persona: agents never do arithmetic on sheet
# figures; AMI mints and labels every derived number, the same way the
# `Asymmetry` line already does ("AMI's arithmetic on the two lines above").
# This is the shared tail every prose agent (all eleven, not the PM's separate
# JSON contract) receives last, so it is the one place a policy sentence
# reaches every debate/analysis voice without being restated eleven times and
# risking the eleven copies drifting apart (the DEF236 lesson, one layer over).
# `failure_patterns` P2/CR038 still apply — this is prose, not a control — but
# where a persona ALSO implies computing (the R19 debators were the known
# case, closed by DEF241's precomputed contribution line; bear_researcher.md's
# own "derive the percentage" instruction is the other case this WP found and
# fixed in the same commit), this sentence is what tells the model the correct
# figure is already in front of it rather than something to work out.
_PROSE_FORMAT = (
    "\nFormat: use **bold** for key metrics (numbers, levels, deadlines). "
    "Plain text otherwise — no headings, no tables. The Markdown is "
    "rendered live in the app.\n"
    "Quote figures from the data above; never compute a new one. Where a "
    "ratio, a percentage move or a drawdown contribution matters, AMI has "
    "already derived and labelled it (e.g. the Asymmetry line) — cite that "
    "line rather than doing the arithmetic yourself."
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

# CR219 R52 — the kill criterion's bound, and it is a real constraint rather
# than a round number.
#
# Bounded at BOTH ends for the reason `narration` is (a maxLength-only string
# admits ""), and the floor is 24 rather than 1: a criterion is a sentence
# naming a quantity, a direction and a threshold, and nothing that short can
# carry all three. "No" and "None" satisfy a minLength of 1 while removing the
# entire field, which would pass every structural check.
#
# The ceiling is set by the decode budget, which is what the CIO's bounds exist
# to respect (`test_the_grammar_terminates_before_the_decode_budget_does`):
# 3600 (narration) + 240 (this) + ~150 scaffolding = 3,990 < 1700 x 3.14 =
# 5,338. It is also an ASK, not just a cap — one sentence, so a CIO that starts
# writing a second paragraph of hedging is stopped by the grammar rather than
# being allowed to bury the criterion in it.
PM_KILL_CRITERION_MAX_CHARS = 240
PM_KILL_CRITERION_MIN_CHARS = 24
"""§3.3 measured the collapsed row's gist budget at ~32 Latin characters. The
server nulls a headline longer than this rather than sending one the client
must cut: a headline is an ASSERTION, and a truncated assertion can invert its
own meaning — which is the DEF059 class the CR rejected first-sentence
truncation over. An over-length headline falls back to the row's other sources
(the agent's own first **bold** span), which are quotations, and a truncated
quotation reads as the fragment it is."""

def _build_stance_format(*, with_size: bool) -> str:
    """The machine channel's contract, in one place for both variants.

    CR197 adds a SIZE field for the three Risk Debators only. Both variants are
    generated from this one body so the shared fields cannot drift apart — the
    parser reads fields independently, so a wording change on one side that never
    reached the other would degrade silently rather than fail.
    """
    size_slot = "SIZE: <n.n>% | " if with_size else ""
    size_bullet = (
        "- SIZE: the position size, as a % of the portfolio, that you actually "
        "endorse after reading the numbers in front of you. Your role was handed a "
        "reference figure; this field is where you say what you truly mean, which "
        "may be that same figure or may not. A number, with a % sign.\n"
        if with_size
        else ""
    )
    return (
        "\n\nBEFORE the thesis sentence, your VERY FIRST line must be this one line, "
        "in exactly this shape, with your prose starting on the line after it:\n"
        f"[STANCE: for|against|neutral | CONVICTION: low|medium|high | {size_slot}"
        f"HEADLINE: <max {STANCE_HEADLINE_MAX_CHARS} characters>]\n"
        "- STANCE: your view on taking this position now — 'for', 'against', or "
        "'neutral' if you genuinely land in the middle.\n"
        "- CONVICTION: how strongly you hold that view.\n"
        f"{size_bullet}"
        "- HEADLINE: the single number or fact that carries your view, in your own "
        "words. Not a summary of your whole argument.\n"
        "- If your role this turn is not to take a side at all, write "
        "'STANCE: none'. Never guess a side to fill the field.\n"
        "- Write this line ONCE, at the top only. Do not repeat it at the end."
    )


_STANCE_FORMAT = _build_stance_format(with_size=False)


def trader_block_regex(*, ticker: str) -> str:
    r"""CR210 — the Execution Desk's turn as a decoding grammar.

    The money block is the surface with a real measured production failure:
    over 136 recorded convenes on `ami-llm`, only 99 (73%) carried a `Side:` line
    the frozen CR196 pattern could read, 119 (88%) allowing for the markdown
    bolding `_PROSE_FORMAT` asks every prose agent for. So ~12% of Execution Desk
    turns render with no labelled block at all.

    Derived from CR196's `regex_S5` and deliberately DIFFERENT in five places.
    That regex was written against the eval harness; this one has to be read back
    by production parsers, and shipping it verbatim would have the grammar
    manufacture defects:

      1. **`R:R` is forced to `N.NN:1`.** CR196 emits a bare `R:R: 2.50`, and
         `_extract_stated_rr("R:R: 2.50")` returns None (measured) because
         `_rr_ratio` needs a trailing `:N` / ` to N` / `x`. With no stated ratio
         `_annotate_rr_against_levels` prints "the proposal stated no R:R, so AMI
         rendered it" under "These are the figures of record" — DEF288's exact
         false claim about a proposal that did state one. `:1` makes both
         `_extract_stated_rr` and `_RR_CLAIM_RE` fire.
      2. **HEADLINE is bounded at STANCE_HEADLINE_MAX_CHARS**, not CR196's 90. At
         90 the grammar would legalise headlines the envelope parser then nulls —
         manufacturing gutter entries by construction.
      3. **STANCE allows all four values** `_build_stance_format` offers. CR196
         allowed `for|against` only, which would force the model to claim a side
         on every turn it genuinely lands in the middle.
      4. **A no-position side gets its own branch, with no Size/Entry/Target/
         Stop/R:R.** CR196 has one branch with every field mandatory, so a Desk
         that wants to WAIT is FORCED to state a price triple it does not believe
         in — the grammar manufacturing the fabrication class this codebase
         exists to refuse. Nothing downstream needs those levels:
         `ctx.trader_entry/stop/target/size_pct` are seeded deterministically from
         the profile before the Desk speaks, and are never parsed back out of its
         prose (DEF235). HOLD rides with WAIT because `recipe16_trader` already
         sizes both at 0.0 — neither opens a position.
      5. **The instrument is pinned to THIS run's ticker** (`re.escape`, because
         BRK.B has a dot), not `[A-Z.]{1,6}`. A proposal for a name the run is not
         about becomes unrepresentable, for free.

    `Entry: market` is ALLOWED, matching `content/agents/trader.md` verbatim.
    Forbidding it would tighten the parse — `_match_level` would always find an
    entry — at the price of pressuring the model to invent a price when it means a
    market order. That is buying a parser guarantee with a fabricated number. If
    the option should go, it goes from `trader.md` first and this follows; the
    drift guard enforces that direction.

    Thousand separators are forbidden inside the block. DEF234/DEF242 exist
    because the model writes `$1,507.00`; both parsers now cope, and forbidding it
    here removes the class from this surface at no cost.

    The trailing `[\s\S]*` is unbounded, and that is safe — unlike an unbounded
    JSON string. `*` matches empty, so EOS is legal the instant the block closes
    and the model stops where it naturally would. In JSON, EOS is illegal
    mid-string, which is what makes an unbounded string a state the grammar can
    always extend forever.
    """
    money = r"\$\d{1,6}\.\d{2}"
    return (
        r"\[STANCE: (?:for|against|neutral|none) \| "
        r"CONVICTION: (?:low|medium|high) \| "
        rf"HEADLINE: [^\]\n]{{1,{STANCE_HEADLINE_MAX_CHARS}}}\]\n"
        rf"Instrument: +{re.escape(ticker.upper())}\n"
        r"(?:"
        r"Side: +BUY\n"
        r"Size: +\d{1,2}\.\d{1,2}% of portfolio\n"
        rf"Entry: +(?:{money}|market)\n"
        rf"Target: +{money}\n"
        rf"Stop: +{money}\n"
        r"Time horizon: +[^\n]{1,24}\n"
        r"R:R: +\d{1,2}\.\d{1,2}:1\n"
        r"|"
        r"Side: +(?:HOLD|WAIT)\n"
        # MEASURED. This branch originally dropped the Size line too, on the
        # reasoning that a no-position turn should not be forced to state
        # numbers. Run over the 68 held-out S5 prompts on 2026-08-27 that scored
        # `size_within_cap` **47/68 (69%)** against an UNCONSTRAINED baseline of
        # **68/68 (100%)** — and NEITHER arm ever exceeded the cap. All 21
        # failures were rows with no Size line at all, which the check reads as
        # a failure rather than as not-applicable. The grammar had converted a
        # perfect score into a 31% failure rate without the model doing anything
        # differently.
        #
        # `Size: 0.00% of portfolio` is not a fabricated number — it is the
        # honest statement that no position is opened, and `recipe16_trader.py`
        # renders exactly that for HOLD/WAIT. Entry/Target/Stop on a WAIT WOULD
        # be fabrication, which is why those stay out.
        r"Size: +0\.0{1,2}% of portfolio\n"
        r"Time horizon: +[^\n]{1,24}\n"
        r")"
        r"[\s\S]*"
    )

# CR197 — the RISK phase's variant. The three debators are the only agents whose
# job is to advocate a SIZE, and until now nothing read one back: the spread they
# "debate" is computed in code (`risk_debator_sizes`) and handed to them, so the
# quantity worth capturing is not the spread itself but whether the agent endorses
# the figure it was given or moves off it. That delta is the signal; the spread
# alone is a constant and always was.
#
# This is a prompt-level instruction, so P2 applies: it is a MEASUREMENT channel,
# never a control. Compliance is itself a number to report (DEF251 measured 20% of
# debator turns emitting no envelope at all), and nothing downstream may assume the
# field is present.
_STANCE_FORMAT_RISK = _build_stance_format(with_size=True)

_SIZE_DECLARING_AGENTS = frozenset(
    {AgentId.AGGRESSIVE_DEBATOR, AgentId.CONSERVATIVE_DEBATOR, AgentId.NEUTRAL_DEBATOR}
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


# CR219 R49 — the VERDICT-phase floor-state preview.
#
# `enforce_safety_floor` deterministically overrides the CIO's verdict on three
# limits the CIO could not see: the post-loss cooldown (safety_floor.py 6c), the
# over-trading brake (6e) and the total open-risk cap (6f). `_risk_state_block`
# above hands every agent the raw INPUTS to those checks — the last stop-out
# timestamp, the two windowed trade counts, the committed open risk — but never
# the floor's own resolved LIMITS, and never the verdict those inputs produce.
# So the CIO could read "Last losing trade closed: <t>" and still have no way to
# know a BUY is already blocked, argue for one, and be overridden after the fact.
# The user then reads a transcript that approves against a verdict that blocks.
#
# What this is NOT: a second enforcement site. It decides nothing, blocks
# nothing, and returns a string. `enforce_safety_floor` remains the sole vetoer
# (DEF059), unchanged. This only stops the CIO being blind to it.
#
# Every number here comes from the SAME `trading_math.risk_limits` functions the
# floor calls — imported, never reimplemented. That is DEF263's lesson applied
# one layer up: DEF263 was a prompt counting trades over a different window than
# the brake, and the fix was to import the brake's own helpers rather than to
# match its arithmetic by eye. A resolver has three inputs (an explicit mandate
# override, a risk-tier preset table, and CR129's per-user drawdown derivation
# for open risk); restating any of them here would drift on the next tier-table
# edit, silently, in the direction of promising headroom the floor will refuse.
#
# Scoped to the VERDICT phase because it is a statement about a decision only
# the CIO makes. The eleven arguing agents already get the consumption figures
# from `_risk_state_block` at every phase, which is the half that is theirs.
def _floor_state_preview(
    mandate: Mandate,
    existing_open_risk_pct: Any,
    last_loss_closed_at: Any,
    trade_open_timestamps: Any,
    *,
    now: datetime | None = None,
) -> str:
    """What the deterministic safety floor will decide about a BUY, right now.

    Three absences kept distinct, exactly as `_risk_state_block` keeps them
    (CR040 / DEF059): `CONTEXT_NOT_SUPPLIED` means the computation FAILED and
    the floor hard-blocks on it, so the preview says so; `None` means this
    caller never supplied it (non-Room surfaces, older tests) and renders
    nothing rather than claiming a state; a real value is stated as fact.

    Returns "" for a caller that supplied NO risk context at all — every one of
    the three arguments left at its `None` default. That gate is load-bearing
    and is the same one `_risk_state_block`'s DEF263 note records: on the floor's
    own contract `trade_open_timestamps=None` means "the caller did not supply
    trade history, so hard-block" (safety_floor.py 6e), which is TRUE for the
    Room and FALSE for `prompt_version.py` and every non-Room caller that never
    passes these kwargs. Without the gate those callers would render a preview
    announcing that the floor is blocking a BUY nobody proposed — a fabricated
    alarm, the same class of harm as silence, pointed the other way. Exactly the
    wrong fix that was tried first on `_risk_state_block`.

    Note the asymmetry, which is the floor's and not this function's:
    `last_loss_closed_at=None` is a REAL value ("this user has never had a
    loss"), which is why the sentinel exists for the absent case at all.
    """
    if (
        existing_open_risk_pct is None
        and last_loss_closed_at is None
        and trade_open_timestamps is None
    ):
        return ""

    now_ = now if now is not None else datetime.now(timezone.utc)
    lines: list[str] = []

    # 6c — post-loss cooldown. CR129: an unset mandate field resolves to the
    # risk-tier preset (always > 0), so this check is ALWAYS active; "off" is
    # expressible only as an explicit 0 override (the Day Trader preset).
    cooldown_hours = resolved_post_loss_cooldown_hours(
        mandate.risk_score, mandate.post_loss_cooldown_hours
    )
    if cooldown_hours > 0:
        if last_loss_closed_at is CONTEXT_NOT_SUPPLIED:
            lines.append(
                f"- Post-loss cooldown ({cooldown_hours:g}h): loss history COULD NOT BE "
                f"READ this run, so the floor will BLOCK any BUY rather than skip the "
                f"check. Treat an entry as unavailable and say so."
            )
        elif last_loss_closed_at is not None and in_cooldown(
            now_, last_loss_closed_at, cooldown_hours
        ):
            lifts_at = cooldown_lifts_at(last_loss_closed_at, cooldown_hours)
            lines.append(
                f"- IN POST-LOSS COOLDOWN until {lifts_at.isoformat()} "
                f"({cooldown_hours:g}h after the last stop-out). The floor will BLOCK "
                f"any BUY until then. An APPROVE here will be overridden to PASS."
            )
        elif last_loss_closed_at is not None:
            lifts_at = cooldown_lifts_at(last_loss_closed_at, cooldown_hours)
            lines.append(
                f"- Post-loss cooldown ({cooldown_hours:g}h): CLEAR — it lifted at "
                f"{lifts_at.isoformat()}."
            )
        else:
            lines.append(
                f"- Post-loss cooldown ({cooldown_hours:g}h): CLEAR — no losing trade "
                f"on record."
            )

    # 6e — the over-trading brake. Both windows are independent; either at its
    # cap blocks. `>=` matches the floor's own comparison: the cap is reached,
    # not exceeded, because THIS proposal would be the one over.
    per_day = resolved_max_trades_per_day(mandate.risk_score, mandate.max_trades_per_day)
    per_week = resolved_max_trades_per_week(mandate.risk_score, mandate.max_trades_per_week)
    if trade_open_timestamps is None:
        lines.append(
            f"- Over-trading brake ({per_day}/day, {per_week}/ISO week): trade history "
            f"COULD NOT BE READ this run, so the floor will BLOCK any BUY rather than "
            f"skip the check."
        )
    elif isinstance(trade_open_timestamps, list):
        today = trades_since(trade_open_timestamps, utc_day_start(now_))
        week = trades_since(trade_open_timestamps, utc_week_start(now_))
        blocked = [
            label for label, count, cap in (
                ("day", today, per_day), ("ISO week", week, per_week),
            ) if count >= cap
        ]
        if blocked:
            lines.append(
                f"- OVER-TRADING BRAKE ALREADY AT ITS CAP for the {' and '.join(blocked)} "
                f"({today}/{per_day} today, {week}/{per_week} this ISO week). The floor "
                f"will BLOCK any BUY. An APPROVE here will be overridden to PASS."
            )
        else:
            lines.append(
                f"- Over-trading brake: {today}/{per_day} trades today, "
                f"{week}/{per_week} this ISO week — room for {per_day - today} more "
                f"today, {per_week - week} more this week."
            )

    # 6f — the total open-risk cap. CR129 derives the unset case from THIS
    # mandate's own `max_drawdown_pct`, so the cap is per-user, not a constant.
    open_risk_cap = resolved_max_open_risk_pct(
        mandate.risk_score, mandate.max_drawdown_pct, mandate.max_open_risk_pct
    )
    if existing_open_risk_pct is CONTEXT_NOT_SUPPLIED:
        lines.append(
            f"- Open-risk cap ({open_risk_cap:g}%): committed open risk COULD NOT BE "
            f"COMPUTED this run, so the floor will BLOCK any BUY rather than skip the "
            f"check."
        )
    elif existing_open_risk_pct is not None:
        headroom = open_risk_cap - float(existing_open_risk_pct)
        if headroom <= 0:
            lines.append(
                f"- OPEN-RISK CAP ALREADY EXCEEDED: {float(existing_open_risk_pct):.2f}% "
                f"committed against a {open_risk_cap:g}% cap. Any BUY carrying a stop "
                f"adds to that sum, so the floor will BLOCK it."
            )
        else:
            lines.append(
                f"- Open-risk headroom: {headroom:.2f} pt "
                f"({float(existing_open_risk_pct):.2f}% committed of a "
                f"{open_risk_cap:g}% cap). A BUY's own contribution is its size% x "
                f"stop-distance% / 100; that sum must stay under the cap."
            )

    if not lines:
        return ""
    return (
        "\nSafety-floor pre-check — what the deterministic floor will do with a BUY, "
        "computed by AMI from the same functions the floor itself calls. This is not "
        "advice and not a vote; it is the arithmetic of your own verdict, already "
        "settled. Do not argue for an entry a line below says is blocked — say plainly "
        "that it is blocked and why.\n" + "\n".join(lines) + "\n"
    )


def _share_of_cap_phrase(contribution_pts: float, cap: float) -> str:
    """What share of the drawdown cap a contribution consumes, said so that two
    different contributions cannot read as the same number (DEF292).

    Both contribution lines used to render `~{pts / cap * 100:.0f}% of it`. On a
    30 pt cap every realistic single-name contribution is under 1 pt, so that
    format has exactly two reachable outputs: `~0%` and `~1%`. Measured on the
    committed 2026-08-13 epoch, over the 240 contribution lines in 160 prompts:

    - **40 lines state `(~0% of it)` for a NONZERO contribution.** DEF053's rule
      is that absent beats meaningless, and a rendered zero is worse than either:
      the Aggressive debator that read `0.09 pt … (~0% of it)` opened with *"the
      risk budget is effectively empty and ours to fill"*.
    - **40 prompts — a quarter of those carrying the line — print the reference
      position and YOUR position with DIFFERENT pt figures and the SAME `~1%`.**
      The whole point of DEF241's second line is that the agent's own position is
      not the reference one; rounding them onto the same percentage says they are.

    One decimal, and an explicit floor below it, so the two lines are computed by
    ONE function and cannot be worded differently for the same quantity."""
    if cap <= 0:
        return ""
    share = contribution_pts / cap * 100
    if 0 < share < 0.05:
        return " (<0.1% of it)"
    return f" ({share:.1f}% of it)"


def _render_option_ladder(rows: list[LadderOption], cap: float) -> str:
    """CR197 — the sized-option menu the CIO chooses from, as a prompt block.

    Rendered here rather than beside `build_option_ladder` so the share-of-cap
    wording comes from `_share_of_cap_phrase` above. That function's one-decimal
    floor is DEF292's fix for a `:.0f` that printed "(~0% of it)" for 40 nonzero
    contributions, and a second formatter would be a second chance to reintroduce
    it.

    The closing sentence matters as much as the table. Measured over 43 baseline
    approvals, 32 land exactly on a computed rung and 11 land between them (2.0,
    2.5, 4.0 against a 1.5/3.0/5.0 ladder) — so a menu presented as closed would be
    MORE constraining than the prose it replaces. The job is to supply the
    arithmetic, not to narrow the choice.
    """
    if not rows:
        return ""
    lines = [
        "## Sized options — AMI computed every figure below",
        (
            f"Each row is a size you may approve, with what it costs against the "
            f"{cap:.0f} pt portfolio-drawdown cap. Quote these figures; do not "
            f"recompute them, and never compare a raw stop distance against the cap."
        ),
        "",
    ]
    for r in rows:
        parts = [f"- **{r.label}** — size {r.size_pct:.1f}% of portfolio"]
        if r.contribution_pts is not None:
            parts.append(
                f"drawdown contribution ≈ {r.contribution_pts:.2f} pt of the "
                f"{cap:.0f} pt cap{_share_of_cap_phrase(r.contribution_pts, cap)}"
            )
        if r.headroom_after_pts is not None:
            parts.append(
                f"{r.headroom_after_pts:.2f} pt of the cap unused once it is on"
            )
        if r.reward_risk is not None:
            parts.append(f"reward:risk {r.reward_risk:.2f}:1")
        lines.append(" · ".join(parts))
    lines.append("")
    lines.append(
        "These rungs are reference points, not the only sizes permitted — land "
        "between them if the evidence puts you there, and say why. Whatever you "
        "choose remains bound by the mandate's ceilings and the safety floor."
    )
    return "\n".join(lines)


def _money(value: float) -> str:
    """A dollar total, as the card renders it. Negative reads as a credit."""
    if value < 0:
        return f"${abs(value):,.0f} credit"
    return f"${value:,.0f}"


def _render_option_candidates(candidates: Sequence[Any], spot: float | None) -> str:
    """CR172 §10 step 2 — the costed structure menu, as a prompt block.

    Rendered here for the same reason `_render_option_ladder` is: this is where
    the wording of a figure lives, so the two menus the CIO reads in one prompt
    cannot describe the same mandate in two vocabularies.

    Two things this block must get right, both of which are about what the
    reader ends up believing rather than about the arithmetic:

    * **A forbidden structure is listed, marked, with its rule named.** §10 is
      explicit that hiding it deletes the teaching moment — the PM should be
      able to say "the natural structure here is a naked call, which your
      mandate forbids". The mark is loud enough that picking one anyway reads
      as a mistake, and `_parse_pm_verdict` makes it one.
    * **An absent figure says why.** `max_loss` is None for an unbounded
      structure AND for one whose loss is bounded by shares already held —
      opposite facts that a blank would render identically, which is the CR040
      question asked of a card instead of a fallback.
    """
    if not candidates:
        return ""
    lines = [
        "## Option structures — AMI costed every figure below",
        (
            "You may express an APPROVE through one of these instead of buying "
            "shares. Pick it by the number in brackets; every strike, premium "
            "and greek below is AMI's arithmetic off the live chain, so quote "
            "these figures and never state one of your own."
        ),
    ]
    if spot:
        lines.append(f"Underlying last: {spot:,.2f}.")
    lines.append("")
    for index, c in enumerate(candidates):
        m = c.metrics
        head = (
            f"- **[{index}] {c.strategy_name.replace('_', ' ')}** — "
            f"{c.contracts} contract{'s' if c.contracts != 1 else ''}, "
            f"expiry {c.expiry} ({c.days_to_expiry}d)"
        )
        parts = [f"net {_money(m.net_cost)}"]
        if m.unbounded_loss:
            parts.append("max loss UNBOUNDED")
        elif m.covered_by_shares:
            parts.append("loss bounded by the shares held, not by the legs")
        elif m.max_loss is not None:
            parts.append(f"max loss {_money(m.max_loss)}")
        if m.unbounded_gain:
            parts.append("max gain uncapped")
        elif m.max_gain is not None:
            parts.append(f"max gain {_money(m.max_gain)}")
        if m.break_evens:
            parts.append(
                "break-even "
                + " / ".join(f"{b:,.2f}" for b in m.break_evens)
            )
        if m.collateral_required:
            parts.append(f"collateral {_money(m.collateral_required)}")
        lines.append(head)
        lines.append(f"  {' · '.join(parts)}")
        if c.legs:
            lines.append(
                "  legs: "
                + ", ".join(
                    f"{'long' if leg.quantity > 0 else 'short'} "
                    f"{abs(leg.quantity):g} {leg.strike:g} {leg.right} "
                    f"@ {leg.premium:.2f}"
                    for leg in c.legs
                )
            )
        if c.net_greeks is not None:
            g = c.net_greeks
            lines.append(
                f"  net delta {g.delta:+.2f} · theta {g.theta_per_day:+.2f}/day "
                f"· vega {g.vega_per_point:+.2f}/pt"
            )
        if c.rationale:
            lines.append(f"  {c.rationale}")
        if c.mandate_violations:
            lines.append(
                "  **FORBIDDEN — this structure cannot be opened under the "
                "mandate: " + " ".join(c.mandate_violations) + "** Naming it "
                "turns your verdict into a PASS; explain it if it teaches "
                "something, but do not pick it."
            )
        # DEF354 second half — `not_evaluated` is where the per-candidate
        # sizing reason and the floor's own unevaluable checks live, and this
        # renderer dropped it while rendering `advisories`. The route already
        # sends it to the ticket, so the user could read a caveat the agent
        # deciding the trade could not. Both audiences get it now.
        for note in c.not_evaluated:
            lines.append(f"  Caveat: {note}")
        for note in c.advisories:
            lines.append(f"  Note: {note}")
    lines.append("")
    lines.append(
        "Shares remain available and are the default — omit structure_id "
        "entirely to approve the underlying, exactly as you always have."
    )
    return "\n".join(lines)


def _headroom_after_clause(
    contribution_pts: float, cap: float, current_drawdown_pct: float | None
) -> str:
    """The cap that is left AFTER this position — precomputed, not left as a
    subtraction (CR179 Leg 4).

    `_risk_state_block` hands every agent the headroom BEFORE the trade
    (*"Drawdown USED: 0.0 pt of the 30 pt cap — 30.0 pt of headroom remains"*)
    and `_drawdown_snapshot_line` hands it the position's contribution. The
    figure an agent actually argues from is the difference, and nothing supplied
    it — so the agent did the subtraction, which is the fifth appearance of the
    DEF066 → DEF235 → DEF241 → CR166-Tier-D class and the one this leg exists to
    close. Measured on the committed 2026-08-13 epoch: of 92 turns stating a
    pt-or-cap figure, **7 state one that appears nowhere in their own prompt**,
    and every one of the seven is this subtraction or a rescaling of it. At least
    one is wrong — a Conservative arguing 1.5% wrote *"a 5.0% size at the
    proposed 6.0% stop distance; this leaves 29.82 pt of headroom"*, which is
    `30 − 0.18` (the REFERENCE position's figure) attached to the Aggressive's
    size while its own line said 0.09.

    CR040 / DEF053: when `current_drawdown_pct` is None the caller never supplied
    what has already been spent, so there is no honest remainder to state and
    this renders NOTHING. Assuming a flat book would fabricate exactly the
    "effectively empty" reading DEF292 found."""
    if cap <= 0 or current_drawdown_pct is None:
        return ""
    remaining = cap - float(current_drawdown_pct) - contribution_pts
    return (
        f" With {float(current_drawdown_pct):.1f} pt of the cap already spent, "
        f"that leaves {remaining:.2f} pt of the {cap:.0f} pt cap unused once this "
        f"position is on. AMI computed this too — do not subtract it yourself."
    )


def _drawdown_snapshot_line(
    mandate: Mandate,
    trade_proposal: dict[str, Any] | None,
    agent_size_pct: float | None = None,
    current_drawdown_pct: float | None = None,
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
        # DEF302 — the stop distance is bound to the pair it was measured from,
        # inline. It used to read "→ stop 6.0% below entry →", and on the SNOA
        # run of 2026-08-14 the Conservative attached that 6.0% to a level of
        # its own: "a hard stop at the 50-day range low $1.03 (6.0% below
        # entry)", where $1.03 against the $1.34 close is -23.1%. The same turn
        # states -23.1% correctly elsewhere, so the agent could compute it — it
        # simply had a bare percentage in scope and reached for it. A percentage
        # whose referent is named two clauses upstream is a percentage that can
        # travel; naming the pair on the same clause is what stops it, and is
        # DEF292's fix (one function, one referent) applied to the sentence
        # rather than to the number.
        line += (
            f"\n  Reference position (risk-tier ceiling {size:.1f}% size, entry "
            f"{entry:.2f}, stop {stop:.2f}) → stop {stop_dist:.1f}% below THAT "
            f"entry ({stop:.2f} from {entry:.2f}; this percentage describes that "
            f"pair only) → portfolio-drawdown contribution ≈ {contrib:.2f} pt of "
            f"the {cap:.0f} pt cap{_share_of_cap_phrase(contrib, cap)}. Size the "
            f"actual trade against THIS figure, not the raw stop distance."
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
        own = (
            drawdown_contribution(agent_size_pct, entry, stop)
            if agent_size_pct is not None and agent_size_pct > 0
            else None
        )
        if own:
            line += (
                f"\n  YOUR position — the size YOUR role argues for "
                f"({agent_size_pct:.1f}%) at that same stop → portfolio-drawdown "
                f"contribution ≈ {own.contribution_pts:.2f} pt of the {cap:.0f} pt "
                f"cap{_share_of_cap_phrase(own.contribution_pts, cap)}. AMI computed "
                f"this. Quote it; do not recompute it, and do not compare the raw "
                f"stop distance against the cap."
            )
        # CR179 Leg 4 — the remainder goes on whichever line describes the
        # position this agent is arguing, and on ONE of them only. Stating it
        # twice would put two different remainders in the same prompt (the
        # reference size and the role's size differ), which is the collision
        # DEF292 has just closed on the neighbouring clause.
        line += _headroom_after_clause(
            own.contribution_pts if own else contrib, cap, current_drawdown_pct
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
    # CR179 Leg 3 / CR152 D7 — the sourced sector/industry exclusion universe.
    # Fetched every run and enforced since DEF061; it reached the mandate CHECK
    # and never the prompt, so agents were told the exclusion existed and never
    # what it had decided about this name.
    classification_universe: Any = None,
    # CR152 D8 — the locale universe, which `safety_floor.py:336` can veto a
    # trade on with `blocked_by="locale"` while no agent was told it exists.
    locale_allowed_universe: Any = None,
    # CR166 Tier C — the portfolio value the single-name cap is a percentage OF.
    # `shares_for_size` has existed in `trading_math/portfolio.py` since CR046
    # and is called only by the mandate check, so the conversion an agent needs
    # to size a trade has never appeared in a prompt.
    portfolio_value: float | None = None,
    parallel_phase: bool = False,
    sector_weights: dict[str, float] | None = None,
    agent_size_pct: float | None = None,
    current_drawdown_pct: float | None = None,
    existing_open_risk_pct: Any = None,
    last_loss_closed_at: Any = None,
    trade_open_timestamps: Any = None,
    # CR172 §10 step 2 — the costed structure menu this run issued, or None.
    # Rendered for the PM's VERDICT turn only, for the same reason CR197 scopes
    # the size ladder there: the agent that must CHOOSE gets the menu, and the
    # eleven that argue keep the judgement their turn exists to exercise. The
    # runner builds it only when the mandate permits derivatives, so None is the
    # ordinary case and the prompt is then byte-identical to pre-CR172.
    option_candidates: Sequence[Any] | None = None,
    option_spot: float | None = None,
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
        classification_universe=classification_universe,
        locale_allowed_universe=locale_allowed_universe,
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
    option_candidate_block = ""
    if agent_id == AgentId.PORTFOLIO_MANAGER:
        format_instruction = _PM_VERDICT_FORMAT
        if option_candidates:
            option_candidate_block = _render_option_candidates(
                option_candidates, option_spot
            )
            # Appended, not interpolated: the structure key is meaningless
            # without the list, so the two arrive together or neither does.
            format_instruction += _PM_STRUCTURE_FORMAT
    else:
        prose_format = _PROSE_FORMAT
        if agent_id != AgentId.TRADER:
            prose_format += _NO_FENCE_CLAUSE
        format_instruction = prose_format + (
            _STANCE_FORMAT_RISK if agent_id in _SIZE_DECLARING_AGENTS else _STANCE_FORMAT
        )

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
    # CR179 Leg 4: `current_drawdown_pct` reaches BOTH tiers now. `_risk_state_block`
    # states the headroom before the trade and this line states the contribution;
    # the agent was left to subtract one from the other, and 7 of the 92 epoch turns
    # stating a pt figure state that subtraction, one of them wrong.
    drawdown_line = _drawdown_snapshot_line(
        mandate,
        proposal,
        agent_size_pct if proposal else None,
        current_drawdown_pct=(
            current_drawdown_pct
            if isinstance(current_drawdown_pct, (int, float)) else None
        ),
    )
    # CR197 — the sized-option ladder, VERDICT phase only.
    #
    # Scope is deliberate. The ablation measured that stripping the risk debate costs
    # the CIO 12 net approvals (p=0.004) because it is left with the Execution Desk's
    # single size and no computed alternatives; the officers' own turns already carry
    # their own figure via `agent_size_pct` above, so they do not need the table and
    # handing it to them would replace the judgement their turn exists to exercise.
    # Only the agent that must CHOOSE a size gets the menu.
    # Gated OFF by default: the ladder measurably shifts the approval rate (16.3% →
    # 21.1% over 136 replayed convenes) and thins interpolation, so it is an operator
    # decision rather than a silent upgrade. See `Settings.pm_option_ladder_enabled`
    # for both readings of that shift.
    option_ladder_block = ""
    if settings.pm_option_ladder_enabled and phase == "VERDICT" and proposal:
        _entry = float(proposal.get("entry") or 0)
        _stop = float(proposal.get("stop") or 0)
        _size = float(proposal.get("size_pct") or 0)
        if _size > 0 and _entry > 0 and 0 < _stop < _entry:
            option_ladder_block = _render_option_ladder(
                build_option_ladder(
                    reference_size_pct=_size,
                    entry=_entry,
                    stop=_stop,
                    target=(
                        float(proposal["target"])
                        if proposal.get("target") not in (None, "")
                        else None
                    ),
                    cap_pts=mandate.max_drawdown_pct,
                    current_drawdown_pct=(
                        current_drawdown_pct
                        if isinstance(current_drawdown_pct, (int, float)) else None
                    ),
                ),
                mandate.max_drawdown_pct,
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

    # CR219 R49 — VERDICT phase only: the floor's own resolved limits and the
    # verdict they already imply. See `_floor_state_preview` for why this is
    # scoped to the one agent whose verdict the floor overrides.
    floor_preview_block = ""
    scoreboard_block = ""
    if phase == "VERDICT":
        floor_preview_block = _floor_state_preview(
            mandate,
            existing_open_risk_pct,
            last_loss_closed_at,
            trade_open_timestamps,
        )
        # CR219 R50 — the parsed envelopes, tabulated in code. VERDICT only:
        # this is a cross-Room aggregate for the agent that must weigh the whole
        # Room, and handing it to an agent whose turn is to state its OWN
        # position would replace the judgement that turn exists to exercise
        # (the same scoping CR197 gives the option ladder).
        scoreboard_block = _room_scoreboard(transcript)

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
            f"bigger number is both wrong and misleading."
            f"{_cap_in_shares_clause(cap, portfolio_value, profile)}\n"
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
    #
    # CR152 D9 / CR179 Leg 3 — widened from PM-only to every FULL-SHEET agent.
    # All twelve are told the sector-concentration RULE in the mandate block
    # (*"the SAME ceiling the safety floor blocks a proposed BUY against"*), and
    # eleven of them were never told the current STATE — the CR145 Tier A shape
    # exactly, where a hard constraint was unfollowable because the number it
    # ranges over was never supplied.
    #
    # It is worse than a plain gap here, because CR055 injects the real holdings
    # into every agent's prompt unconditionally. So an agent could read `GME
    # x500` a few lines up and still have no way to know that is 95% of one
    # sector. It had the evidence and not the aggregate.
    #
    # Gated on the full sheet rather than named per agent: this is cross-lane
    # PORTFOLIO context, and the full-sheet set is exactly the set whose job is
    # the cross-lane join and who propose or veto a size (Bull, Bear, RM,
    # Trader, PM, the three Risk Debators). The four analysts stay firewalled —
    # they are not asked for a size, and CR145 Tier C's measured 97.5% is what
    # that firewall bought. A thirteenth agent added later fails OPEN, the same
    # direction `_lane_for` already chose.
    sector_line = ""
    if _lane_for(agent_id) == _ALL_DOMAINS:
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
        # CR219 R49 — directly under the consumption figures it is the verdict
        # of, and above the transcript for CR197's reason: this is AMI's
        # arithmetic about the mandate, and computed figures placed after eleven
        # turns of prose read as one more voice's claim.
        f"{floor_preview_block}"
        f"{sector_line}"
        f"{researcher_cap_note}"
        f"\n"
        # CR197 — before the transcript, not after it. The menu is a fact about the
        # mandate, of a piece with the snapshot above it; the transcript is opinion.
        # Putting computed figures after eleven turns of prose also invites the model
        # to read them as one more voice's claim rather than as AMI's arithmetic.
        f"{option_ladder_block}"
        f"{chr(10) if option_ladder_block else ''}"
        # CR172 §10 step 2 — beside the size ladder and before the transcript,
        # for CR197's reason: both are AMI's arithmetic about the mandate, and
        # computed figures placed after eleven turns of prose read as one more
        # voice's claim rather than as the figures of record.
        f"{option_candidate_block}"
        f"{chr(10) if option_candidate_block else ''}"
        # CR219 R50 — immediately above the transcript it is computed FROM, so
        # the CIO reads the tally and the prose it summarises as one thing.
        f"{scoreboard_block}"
        f"Transcript so far:\n{transcript_text}\n"
        f"{journal_note}"
        f"\nYour turn. Speak as the {agent_display_name(agent_id)}. "
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


def build_risk_officer_messages(
    *,
    mandate: Mandate,
    ticker: str,
    profile: dict[str, Any],
    transcript: list[AgentMessage],
    trade_proposal: dict[str, Any],
    portfolio_snapshot: str | None = None,
    sector_weights: dict[str, float] | None = None,
    current_drawdown_pct: float | None = None,
    existing_open_risk_pct: Any = None,
    last_loss_closed_at: Any = None,
    trade_open_timestamps: Any = None,
) -> tuple[str, list[ChatMessage], list[LadderOption]]:
    """CR201 — the structured Risk Officer's one prompt, plus the ladder it fills in.

    Same evidence the three debators saw, different contract: persona fronted
    instead of a role brief, the computed option ladder rendered in full, and a
    JSON instruction (`build_risk_officer_instruction`) in place of the prose +
    stance-envelope format. Deliberately NOT routed through `build_room_messages`:
    that assembly exists for the twelve display agents (phase framing, length
    guide, stance envelope, "Speak as the …" turn line), and every one of those
    parts is wrong for an internal compute agent whose entire reply is parsed.

    The returned `rows` are the SAME `LadderOption` list rendered into the prompt
    — the caller renders the three display turns from these rows and never from
    the model's payload, which is what keeps an invented size un-renderable.

    Not included, deliberately: the safety floor (the officer decides nothing —
    `enforce_safety_floor` stays on the PM, DEF059); Brief overlays (the officer
    is not a briefable display agent); and the mandate/compliance overlay
    (`generate_overlay` is built for the twelve display roles — the sourced
    Sharia/locale verdicts stay in the CIO's prompt and the floor's veto; the
    officer sizes options, it does not screen instruments). The grounding
    directive is prepended by the gateway on every call, as for every other
    agent.
    """
    from app.services.risk_officer import (
        RISK_OFFICER_PERSONA,
        build_risk_officer_instruction,
    )

    size = float(trade_proposal.get("size_pct") or 0)
    entry = float(trade_proposal.get("entry") or 0)
    stop = float(trade_proposal.get("stop") or 0)
    target = trade_proposal.get("target")
    if not (size > 0 and entry > 0 and 0 < stop < entry):
        # Degrade loudly (CR040): a ladder from an incoherent reference triple
        # would price nothing real. The caller falls back per its designed path.
        raise ValueError(
            f"risk officer needs a coherent reference proposal, got "
            f"size={size} entry={entry} stop={stop}"
        )
    rows = build_option_ladder(
        reference_size_pct=size,
        entry=entry,
        stop=stop,
        target=float(target) if target not in (None, "") else None,
        cap_pts=mandate.max_drawdown_pct,
        current_drawdown_pct=(
            current_drawdown_pct
            if isinstance(current_drawdown_pct, (int, float)) else None
        ),
    )

    profile_block = _format_profile(profile, AgentId.RISK_OFFICER)
    drawdown_line = _drawdown_snapshot_line(
        mandate,
        trade_proposal,
        None,
        current_drawdown_pct=(
            current_drawdown_pct
            if isinstance(current_drawdown_pct, (int, float)) else None
        ),
    )
    risk_state_block = _risk_state_block(
        mandate,
        current_drawdown_pct,
        existing_open_risk_pct,
        last_loss_closed_at,
        trade_open_timestamps,
    )
    long_only_line = ""
    if mandate.compliance.long_only:
        long_only_line = (
            "- long_only: long-only = no short/negative positions. It does NOT forbid "
            "buying, adding to, or holding a name.\n"
        )
    sector_line = _format_sector_allocation(sector_weights) + "\n"
    portfolio_block = f"{portfolio_snapshot}\n\n" if portfolio_snapshot else ""

    system_prompt = (
        f"{RISK_OFFICER_PERSONA}\n\n"
        f"─── CONVENE THE ROOM — RISK PHASE ───\n"
        f"Ticker: {ticker}\n"
        f"{profile_block}\n"
        f"\n"
        f"{portfolio_block}"
        f"User mandate snapshot:\n"
        f"- risk_score: {mandate.risk_score} (1=most conservative, 5=most aggressive)\n"
        f"{drawdown_line}\n"
        f"{long_only_line}"
        f"- locale: {mandate.locale}\n"
        f"{risk_state_block}"
        f"{sector_line}"
        f"\n"
        f"{_render_option_ladder(rows, mandate.max_drawdown_pct)}\n"
        f"\n"
        f"Transcript so far:\n{_format_transcript(transcript)}\n"
        f"{build_risk_officer_instruction(rows)}"
    )
    return (
        system_prompt,
        [ChatMessage(role="user", content=f"Assess risk on {ticker}.")],
        rows,
    )


# ── Helpers ──────────────────────────────────────────────────────────────


def _cap_in_shares_clause(
    cap_pct: float, portfolio_value: float | None, profile: dict[str, Any]
) -> str:
    """CR166 Tier C — what the single-name cap actually BUYS, in dollars and shares.

    The cap is stated as a percentage in every prompt, and a percentage of an
    unstated base is not a quantity. `shares_for_size` has converted it since
    CR046 — for the mandate CHECK, never for a prompt — so the agent proposing
    the size and the code enforcing it were working in different units.

    Precomputed rather than handed over as three operands and an instruction to
    multiply and divide: that is the class DEF066 -> DEF235 -> DEF241 -> CR166
    Tier D is a four-instance record of, and this is a new figure being born
    into it rather than an old one being rescued.

    Renders nothing when either input is missing — a share count against an
    unknown portfolio value or an unknown price is a fabricated quantity, which
    is worse than the abstraction it would replace (CR104/DEF053).
    """
    if not portfolio_value or portfolio_value <= 0:
        return ""
    anchor, anchor_name = _price_anchor(profile)
    dollars = portfolio_value * cap_pct / 100.0
    clause = f" At this portfolio's value that cap is ${dollars:,.0f}"
    if anchor is not None and anchor > 0:
        # `_price_anchor` returns the name WITH its article ("the last close" /
        # "the reference price"), so no article is added here.
        clause += (
            f", about {shares_for_size(portfolio_value, cap_pct, anchor):,} shares "
            f"at {anchor_name} of ${anchor}"
        )
    return clause + "."


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


# CR164 — what a reconstructed sheet structurally cannot carry, by lane.
# These are not provider gaps that vary by ticker: they are absent for EVERY
# ticker on EVERY past date, which is why they are declared once as a set
# rather than as a "not available" line per field. Each entry says WHY, so the
# agent can tell an unreconstructable field from an unfetched one.
_HISTORICAL_MODE_ABSENT: dict[str, tuple[str, ...]] = {
    "fundamentals": (
        "analyst consensus — rating, score, analyst count, and the mean, "
        "median and low-high target range",
        "forward P/E and PEG, both of which are built on consensus forward "
        "earnings",
        "sector and industry classification",
        "institutional and insider ownership, and free float",
        "the next scheduled earnings date and its consensus EPS estimate",
        "the forward indicated dividend rate and the next ex-dividend date "
        "(the trailing yield and payout ratio ARE stated where available)",
    ),
    "technicals": (
        "beta — the provider's figure is a five-year monthly measure and the "
        "stored history is shorter; a one-year figure is a different number "
        "wearing the same name",
        "short interest — percent of float, and days to cover",
    ),
}


def _historical_mode_line(profile: dict[str, Any], lane: frozenset[str]) -> str | None:
    """CR164 — state what a past date cannot carry, instead of omitting it.

    In as-of mode ~20 fields the live sheet carries cannot be reconstructed,
    and the render path drops an absent optional field silently. Silence reads
    as "nobody fetched it", which invites the agent to supply the number from
    training memory — the CR104/DEF123 failure this codebase spent a CR
    closing everywhere else.

    Lane-filtered, so the Fundamentals Analyst is not told about beta and the
    Market Analyst is not told about consensus; those are already covered by
    `_out_of_lane_line`, and repeating them here would have the two lines
    making different claims about the same field.

    The closing clause deliberately contradicts `_out_of_lane_line`'s "another
    analyst holds each of those" FOR THIS SET — otherwise the two bullets
    disagree, and a prompt that disagrees with itself is the P4 class this
    whole programme exists to remove.
    """
    if not profile.get("historical_mode"):
        return None
    absent: list[str] = []
    for domain in ("fundamentals", "technicals"):
        if domain in lane:
            absent.extend(_HISTORICAL_MODE_ABSENT[domain])
    if not absent:
        return None
    return (
        "- HISTORICAL MODE. This sheet is reconstructed as of the run date "
        "above: from SEC filings whose filed date is on or before it, and from "
        "price bars up to it. A field marked LIVE means \"measured from what "
        "was knowable on that date\", not \"as of now\". These are NOT "
        "reconstructable for a past date and are absent from this sheet: "
        + "; ".join(absent)
        + ". No other analyst holds them either — for these, this is not a "
        "division of labour. Do not estimate them, do not recall them from "
        "training memory, and do not tell the Room they merely were not fetched."
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
    historical_line = _historical_mode_line(profile, lane)
    if historical_line:
        header_lines.append(historical_line)
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
            # CR145 Tier D — the direction, immediately under the levels, so
            # the two bases are read together rather than a page apart.
            margin_trend_line(
                profile.get("gross_margin_trend_bps")
                if _is("gross_margin_trend_bps", "live") else None,
                profile.get("operating_margin_trend_bps")
                if _is("operating_margin_trend_bps", "live") else None,
                profile.get("net_margin_trend_bps")
                if _is("net_margin_trend_bps", "live") else None,
                profile.get("margin_trend_basis")
                if _is("margin_trend_basis", "live") else None,
            ),
            buyback_line(
                profile.get("buyback_ttm") if _is("buyback_ttm", "live") else None,
                profile.get("buyback_yield") if _is("buyback_yield", "live") else None,
            ),
            capital_return_line(
                profile.get("capital_return_ttm")
                if _is("capital_return_ttm", "live") else None,
                profile.get("buyback_ttm") if _is("buyback_ttm", "live") else None,
                profile.get("dividends_paid_ttm")
                if _is("dividends_paid_ttm", "live") else None,
                profile.get("capital_return_pct_fcf")
                if _is("capital_return_pct_fcf", "live") else None,
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
        lines.append(_period_trend_line(profile))
        lines.append(_volume_line(profile))
    else:
        lines.append("Market technicals: not available this call.")
    # CR179 Leg 3 — the `.info`-sourced technicals, OUTSIDE the branch above on
    # purpose. `field_state["technicals"]` is all-or-nothing because
    # `compute_technicals` cannot return "RSI but not trend"; these arrive from
    # a different endpoint entirely, so an OHLCV outage that blanks the block
    # above must not also hide a 200-day average that is genuinely live. Each is
    # independently CR104-gated. Still lane-gated: this is the technicals desk's
    # subject matter, whatever fetcher happened to return it — the same DOMAIN-
    # not-provenance rule `week52` is placed by, a few lines down.
    if _in_lane("technicals") and not market_withheld:
        for extra in (
            day_move_line(
                profile.get("day_change_pct") if _is("day_change_pct", "live") else None,
                profile.get("market_state") if _is("market_state", "live") else None,
            ),
            primary_trend_line(
                profile.get("sma_200") if _is("sma_200", "live") else None,
                profile.get("price_vs_sma_200_pct")
                if _is("price_vs_sma_200_pct", "live") else None,
            ),
            relative_strength_line(
                profile.get("change_52w_pct") if _is("change_52w_pct", "live") else None,
                profile.get("change_52w_sp500_pct")
                if _is("change_52w_sp500_pct", "live") else None,
                profile.get("relative_strength_52w_pct")
                if _is("relative_strength_52w_pct", "live") else None,
            ),
            liquidity_line(
                profile.get("volume_today") if _is("volume_today", "live") else None,
                profile.get("volume_avg_3m") if _is("volume_avg_3m", "live") else None,
            ),
            risk_profile_line(profile.get("beta") if _is("beta", "live") else None),
            short_interest_line(
                profile.get("short_pct_float") if _is("short_pct_float", "live") else None,
                profile.get("short_days_to_cover")
                if _is("short_days_to_cover", "live") else None,
                profile.get("short_interest_date")
                if _is("short_interest_date", "live") else None,
            ),
        ):
            if extra:
                lines.append(extra)
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
    if profile.get("total_cash") is not None and _field_is_live(profile, "total_cash"):
        # CR179 Leg 3 — and the other half of that same argument, which shipped
        # without it. The two balance sheets the comment above distinguishes are
        # distinguished by the CASH; "how long can this fund itself" is a
        # different question from "how levered is it", and only one of them was
        # answerable. Invisible to both guards until Leg 0's perturbation probe:
        # the census counts `totalCash` as consumed because it IS read (into
        # `net_cash`), and parity can only ask about a field that is produced.
        parts.append(f"gross cash ${profile['total_cash']:,}M")
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


def _period_trend_line(profile: dict[str, Any]) -> str:
    """CR146 Tier C — the quarterly trend read, from the series already fetched.

    `overlay_generator.py:317` tells 18/18 prompts to *"Emphasise
    monthly/quarterly trend"*, and until now the sheet carried one day's price
    and two smoothed levels to do it with. One quarter of candles cannot produce
    a quarterly trend if only the last one is read.

    **The candle COUNT is stated, not the nominal period.** The window is
    trading days: a holiday-shortened quarter and a full one both answer to
    "3 months" and are not the same measurement. `_HISTORY_PERIOD` is the ask;
    this is what arrived.

    Rides `field_state["technicals"]` with the rest of the block — the series
    that produces it is the series that produces the RSI.
    """
    pct = _safe_num(profile.get("return_period_pct"))
    candles = profile.get("period_candles")
    if pct is None or not candles:
        return "Trend over the fetched window: not available"
    from app.services.technicals import window_trend_phrase

    return f"Window trend: {window_trend_phrase(pct, candles)}"


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
    # CR166 Tier C — the distance to the SHORT average too. The line stated one
    # of the two distances the pair implies, and the 20-day is the one a
    # near-term entry or invalidation is argued against; leaving it out meant
    # the agent either dropped the argument or did the subtraction itself, and
    # doing the subtraction itself is the class Leg 4 exists to close.
    # DEF262 — PRINT the anchor's name, never the literal "last close". This
    # line bound the name and discarded it, so on a sheet where the anchor had
    # fallen back to the reference price it announced a comparison against a
    # "last close" the sheet never stated — the exact DEF228 shape
    # `_price_anchor` exists to prevent, reintroduced by the commit that
    # introduced `_price_anchor`.
    #
    # Both distances share ONE naming clause rather than repeating it: the
    # anchor is the same number for both, and saying so twice invites the
    # reading that they were measured against two different prices, which is
    # the two-prices confusion this sheet has already had to reconcile once.
    parts = []
    if anchor is not None and short > 0:
        parts.append(f"{(anchor - short) / short * 100:+.1f}% vs the 20-day")
    if anchor is not None and long > 0:
        parts.append(f"{(anchor - long) / long * 100:+.1f}% vs the 50-day")
    if parts:
        line += f" — {name} is " + " and ".join(parts)
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
    # DEF291 — when nothing in the feed names this company, say so. An
    # off-ticker article under a "Catalysts — recent" label is not noise the
    # agent can route around; the label ASSERTS that this is the catalyst for
    # the name under discussion, which is a fabricated fact rather than a
    # missing one. `False` only ever comes from a real feed that was searched
    # and produced no match, so the caveat cannot fire on an absent feed.
    if profile.get("catalyst_on_ticker") is False:
        line += (
            " — NOTE: no headline in this feed names this company, so this item is "
            "recent market coverage, NOT a catalyst for this ticker. Do not attribute "
            "it to the company or treat it as company news."
        )
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
        # CR160 — label speakers by display name, not wire id: these tags are
        # how agents cite each other, and citing "[trader]" would resurface the
        # retired name in generated prose the user reads.
        lines.append(f"[{agent_display_name(m.agent_id)}] {m.content}")
    return "\n".join(lines)


# CR219 R50 — the Room scoreboard, minted by AMI from the parsed envelopes.
#
# The stance envelopes are already machine-parsed per turn (`parse_stance_envelope`)
# and carried on every transcript entry as `stance`/`conviction`/`headline`
# (CR106 B2). By the VERDICT phase the CIO reads them back only as prose, buried
# in eleven turns, and weighs whatever recency left salient.
#
# This is R20's philosophy at the Room level: where an aggregate can be computed,
# AMI computes it rather than asking a model to summarise. Zero extra LLM calls.
#
# Degrade loudly (CR040), and this is the specific reason the row is never
# dropped: DEF251 measured ~20% of debator turns emitting NO envelope at all. A
# scoreboard that silently omits those rows would show a 9-agent Room as
# unanimous when two of its voices were never counted — inventing consensus out
# of a parser gap, which is the exact failure DEF251 and CR106's T-SUM11 gutter
# rule both exist to prevent. So a turn with no parseable stance renders as
# `unparsed`, in position, and the header states how many.
_SCOREBOARD_UNPARSED = "unparsed"


def _scoreboard_cell(value: str | None) -> str:
    """A field the agent did not state renders as `unparsed`, never as blank
    and never as a default. `none` is the prompt's own opt-out and reaches here
    as `None` too — same destination: the CIO is told the view was not stated,
    not handed a fabricated neutral."""
    return value if value else _SCOREBOARD_UNPARSED


def _room_scoreboard(transcript: list[AgentMessage]) -> str:
    """A fixed-width agent | stance | conviction | headline table.

    Deterministic: same transcript in, same bytes out. Nothing here calls a
    model, and nothing here re-parses prose — it reads the envelope fields the
    runner already parsed at the moment each turn was produced.

    Rows are in transcript order (the order the Room actually spoke). Only
    `role == "agent"` entries are scored; a user or system entry is not a voice
    in the Room and would land in the count as one.
    """
    rows = [m for m in transcript if m.role == "agent"]
    if not rows:
        return ""

    cells = [
        (
            agent_display_name(m.agent_id),
            _scoreboard_cell(m.stance),
            _scoreboard_cell(m.conviction),
            _scoreboard_cell(m.headline),
        )
        for m in rows
    ]
    stated = sum(1 for _, stance, _, _ in cells if stance != _SCOREBOARD_UNPARSED)
    unparsed = len(cells) - stated

    headers = ("AGENT", "STANCE", "CONVICTION", "HEADLINE")
    widths = [
        max(len(headers[i]), max(len(c[i]) for c in cells))
        for i in range(3)
    ]

    def _row(c: Sequence[str]) -> str:
        return "  ".join(
            [c[i].ljust(widths[i]) for i in range(3)] + [c[3]]
        ).rstrip()

    lines = [_row(headers), "  ".join("-" * w for w in widths) + "  " + "-" * 8]
    lines.extend(_row(c) for c in cells)

    # The caption states the denominator the same way the Verdict Board does
    # (CR106 T-SUM11): a count over agents that STATED a view, never a total
    # that always sums to the roster size.
    caption = (
        f"{stated} of {len(cells)} stated a view"
        + (
            f"; {unparsed} emitted no readable position and are shown as "
            f"`{_SCOREBOARD_UNPARSED}` — absent, NOT neutral, and not evidence "
            f"of agreement"
            if unparsed else ""
        )
    )
    return (
        "\nRoom scoreboard — every position stated so far, tabulated by AMI from "
        "the agents' own stance lines (not a summary, and not another voice; "
        f"this is the transcript below, counted). {caption}.\n"
        + "\n".join(lines)
        + "\n"
    )
