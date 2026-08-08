# External review — aggressive_debator (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/aggressive_debator.prompt.txt`
> (AMD run, fact sheet as of 2026-08-07) and `.../aggressive_debator.reply.txt`.
> Unlike `external_review/room/aggressive_debator.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/render path — these are **findings, not hypotheses**.
> Note: the blind review audited an **AAPL** corpus (3.0% single-name cap, MSFT/NVDA
> holdings); the real sample here is **AMD** (10.0% cap, DIS/GOOGL/HPQ/NVDA holdings).
> Hypothesis matching below is annotated for that difference.

## 1. Question

Does the Aggressive Debator have enough data in the fact sheet / portfolio block to
do its job to ~95% accuracy?

## 2. Answer

**Yes for the job as scoped in the prompt — the best-served agent in the Room — no
for the compliance-checking job its own role guidance implies.**

The scoped deliverable is tiny: a stance header plus a 2-sentence size push with a
one-line reason, built on the transcript. For that, coverage is close to complete:

- Every mandate cap stated verbatim: drawdown **50%**, single-name **10.0%**, sector
  **20.0%**, open-risk **60.0%**, pace **10/day, 50/week**, max positions **50**,
  cooldown off (prompt lines 47–53).
- The derived drawdown arithmetic is **handed to it**: reference position 10.0% size,
  entry **494.31**, stop **464.65** → contribution ≈ **0.60 pt** of the 50 pt cap
  (line 111). The exact computation DEF066 exists to prevent the model mis-doing.
- Full transcript through the Trader's WAIT proposal (lines 116–160) — the thing it
  is arguing against.
- An opportunity-cost anchor exists in this corpus: Street target **$608.23**
  (line 105) and the Bull's computed **22.9%** upside (line 136).

Estimated accuracy on the scoped deliverable: **~95%**.

The role guidance, however, says "HARD CONSTRAINT: a position's portfolio-drawdown
contribution … **plus existing drawdown** cannot exceed 50%" (line 68), and the
mandate caps it recites are portfolio-level sums. Against *that* full version of the
job — verify the push against live portfolio state before making it — the data caps
out at **~70–75%**: three of the four portfolio-side inputs needed to check the caps
are withheld (§3).

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | Existing portfolio drawdown not supplied | Role guidance's own HARD CONSTRAINT ("plus existing drawdown", line 68) is unverifiable. |
| 2 | Existing open-risk sum / per-position stop distances not supplied | The 60.0% total open-risk cap ("across all open positions, including this one", line 53) cannot be checked; holdings block shows weight + unrealised only (lines 73–76). |
| 3 | Portfolio sector weights not supplied | 20.0% GICS sector cap stated (line 49); AMD is Semiconductors and NVDA (9.4%) visibly is too, but DIS/GOOGL/HPQ sectors are unstated — the running sector total is unknowable. |
| 4 | Trade pace counts not supplied | "10 per day, 50 per week" cap stated (line 52); today's/this week's counts absent. |
| 5 | Conservative + Neutral arguments listed as Inputs (lines 13–14) but absent from the transcript | Structural, not a fetch gap: the Aggressive Debator speaks FIRST in the RISK phase. The role guidance demands inputs that cannot exist at its turn — an invitation to strawman or fabricate. |
| 6 | Opportunity-cost "X%" template (line 20) depends on a target price | Followable **in this corpus** (target $608.23 live; 22.9% in transcript). Unfollowable whenever `analyst_target_price` is a provider gap — the template never degrades. |
| 7 | The reference stop is not the Trader's stop | Line 111's 464.65 stop is a deterministic risk-tier reference (entry × 0.94); the actual Trader proposal here is WAIT with no stop. An agent that treats the reference as the proposal mis-attributes it. The line is labelled "Reference position", so this is a reading-comprehension trap, not a data lie. |

## 4. Supplier check — what the codebase can actually deliver

Prompt assembly: `build_room_messages` — `backend/app/services/room_prompts.py:321-483`.
RISK-phase proposal injection: `room_prompts.py:400-401` + `room_runner.py:3401-3405`.
Reference-position line: `_drawdown_snapshot_line` (`room_prompts.py:280-318`).
Holdings block: `_build_sim_holdings_block` (`room_runner.py:682-771`).
Run context: `_RoomContext` built at `room_runner.py:2853-2898`.
Base prompt: `content/agents/aggressive_debator.md`.

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | Existing drawdown | **FETCHED, NOT RENDERED** | `current_drawdown_pct` is computed per run and sits in `_RoomContext` (`room_runner.py:2882`); it is passed to the verdict/enforcement paths (`room_runner.py:1900`, `:2636`, `:3177`) but never into `build_room_messages`. One render line. |
| 2 | Open-risk sum + stops | **FETCHED, NOT RENDERED** | `_build_room_risk_limit_context` (`room_runner.py:800-826`) → `SimEngine.risk_limit_context` (`sim_engine.py:503-515`), built once per run at `room_runner.py:2864-2869` and consumed by `enforce_safety_floor` (`room_runner.py:1912-1914`, `:3191-3193`). Per-position stops exist in the DB (`Trade.stop`, `backend/app/db/models.py:467`) and feed that sum. The holdings block renders weight/unrealised only (`room_runner.py:752-755`). Render-only. |
| 3 | Sector weights | **FETCHED, RENDERED PM-ONLY** | `_build_room_sector_context` (`room_runner.py:2858-2860`); `_format_sector_allocation` (`room_prompts.py:489-500`) is gated `if agent_id == PORTFOLIO_MANAGER` (`room_prompts.py:453-455`, CR026). Widening the gate to the RISK phase is a one-line change — but note CR026 gated it deliberately; extending it is a scope decision, not an oversight fix. |
| 4 | Pace counts | **FETCHED, NOT RENDERED** | `risk_trade_open_timestamps` in the same context tuple (`room_runner.py:2864-2869`); `trades_since` / `utc_day_start` / `utc_week_start` already exist (`backend/app/trading_math/risk_limits.py:142-155`). Render-only. |
| 5 | Conservative/Neutral args | **NOT AVAILABLE structurally — prompt defect** | RISK phase is sequential, order aggressive → conservative → neutral (`room_runner.py:160-164`). No data change can supply these at the aggressive turn; the `## Inputs` lines in `content/agents/aggressive_debator.md:16-18` are simply wrong for the first speaker. |
| 6 | Opportunity-cost anchor | **ALREADY WIRED (this corpus)** | `analyst_target_price` is an optional live-only field (`room_runner.py:351-354`) rendered by `_analyst_line` (`room_prompts.py:858-872`). When the provider omits it, the field degrades to "not available" and the X% template becomes unfollowable — a template-side degrade gap, not a wiring gap. |
| 7 | Reference vs Trader stop | **ALREADY WIRED as designed** | Reference entry/stop derived at `room_runner.py:2910-2913` (`stop = entry × 0.94`; 494.31 × 0.94 = 464.65 ✓ matches the prompt). The docstring at `room_prompts.py:290-294` states it is deliberately a deterministic reference, not the Trader's live words. Behaviour is intended; the residual risk is the model conflating the two. |

## 5. Caveats before wiring #1 / #2 / #4

1. **Zero new fetch cost.** Unlike the fundamentals gaps (new yfinance statement
   calls), every figure above is *already computed once per run* for
   `enforce_safety_floor` (`room_runner.py:2864-2869`). Rendering them adds no
   provider calls, no rate-limit exposure, no cache requirement. The only data
   freshness involved is the quote marks already pulled for the sector context
   (CachingProvider 60s quote TTL, `market_data.py`) — already incurred.
2. **Staleness symmetry.** The enforcement path and the prompt would read the same
   per-run snapshot — that is the desired property (CR090's "charge == render"
   logic applies: the debator must argue against the same numbers the PM is vetoed
   against).
3. **Failure mode is loud already.** `risk_limit_context` failure returns
   `CONTEXT_NOT_SUPPLIED` and blocks loudly (`room_runner.py:811-826`); a render
   site should mirror that ("open risk unavailable this run") rather than omit.

## 6. Recommended slice (if this becomes a CR)

Cheap, no new provider, no new fetch:

1. Fix the base prompt (`content/agents/aggressive_debator.md`): drop the
   Conservative/Neutral lines from `## Inputs` (or restate as "you speak first —
   anticipate, don't quote"), and remove or reconcile the `Open with:` line against
   the mandatory first-line STANCE header (the live reply violated the header rule
   because of it — §8).
2. Render the already-computed risk context into the RISK-phase mandate snapshot:
   existing open-risk %, current drawdown %, pace counts. One block, render-only.
3. Decide deliberately whether `_format_sector_allocation` extends to debators
   (reversing part of CR026's PM-only gate) or the sector-cap line drops out of
   the debator mandate block.
4. Make the opportunity-cost template conditional on `analyst_target_price` being
   live.

## 7. Relationship to the blind review (`../aggressive_debator.md`)

The blind review audited a different corpus (AAPL); its structural findings carry
over, its numeric ones mostly don't.

- **Confirmed, with live evidence:** the "Open with: I'd push for…" vs mandatory
  first-line STANCE header contradiction — the real reply put the opener on line 1
  and the header on line 3, violating "your VERY FIRST line must be". Its failure
  mode #1 happened, in the mildest form.
- **Confirmed:** bullets-vs-2-sentences contradiction (`room_prompts.py:76` length
  guide vs `_PROSE_FORMAT`). The reply chose prose, no bullets, 3 sentences.
- **Confirmed and upgraded:** "cap data withheld" (its unfollowable items 2–4 —
  drawdown, open-risk stops, sector weights, pace counts). Supplier check shows all
  four are **fetched per run and enforced downstream**; they are render-only gaps,
  not missing feeds. Its CUT-the-caps framing is unnecessary; supply the data.
- **Partially killed:** "opportunity cost X cannot be computed" — true of its AAPL
  corpus; false of the AMD sample (target $608.23 live, 22.9% in the transcript).
  The real defect is narrower: the template doesn't degrade when the target is a
  provider gap (gap #6).
- **Refined:** "no proposed stop supplied" — the prompt *does* supply a labelled
  deterministic reference stop with derived contribution (DEF066 machinery,
  `room_prompts.py:280-318`), which its own corpus quote also shows. What is absent
  is the *Trader's actual* stop (here: WAIT, none exists). The residual issue is
  reference-vs-proposal conflation (gap #7), not absence.
- **New finding it structurally could not see:** the `## Inputs` section lists two
  arguments that cannot exist at this agent's turn (aggressive speaks first,
  `room_runner.py:160-164`) — verified against the phase ordering, and visible in
  the sample transcript ending at `[trader]`.
- **Could not verify:** its AAPL-specific numbers (3.0% cap, MSFT ×40) and token
  counts — different corpus.

## 8. Reply-sample verification (`real_samples/aggressive_debator.reply.txt`)

The actual model response was checked line-by-line against the prompt's data block.

**Numerically clean — GROUNDED.** Every figure in the reply is in the prompt:

| Reply figure | Source in prompt |
|---|---|
| 22.9% | Transcript, bull_researcher (line 136) |
| $608.23 | Fact sheet, analyst consensus (line 105) |
| 50% TTM growth | Line 92 |
| $8,835M net cash | Line 93 (as "$8835M"; comma is reformatting, not a new number) |
| RSI 49 | Line 94 |
| 10.0% cap | Lines 48, 111 |
| $584.73 | Lines 95, 97 |
| 32% bullish | Line 101 |
| PEG 1.12 | Line 103 |
| r/wallstreetbets | Line 102 |

Zero hallucinated numbers. No training-memory leakage detected. (22.9% is a
transcript-derived figure, not a raw fact-sheet line — permitted: the instruction
is "build on the transcript" and "ONLY numbers from the data block above", and the
transcript is inside the block.)

**Format findings (both prompt-caused):**

1. **Header placement violated.** Line 1 is "I'd push for full mandate-allowed
   sizing."; the `[STANCE: …]` header is on line 3. The prompt demands it be the
   VERY FIRST line (line 166) *and* demands the "I'd push for" opener
   (`content/agents/aggressive_debator.md:23`). The model satisfied the base-prompt
   template and broke the header rule — the blind review's contradiction #1,
   confirmed live.
2. **Length/shape violated.** "Write 2 sentences" (line 162) vs body of 3 sentences
   (plus the opener line = 4); "then short bullet points" (line 164) vs zero
   bullets. The two instructions are mutually exclusive for any thesis+evidence
   structure; the model picked prose.

**Other checks:**

- **Stance-evidence tension: minor.** `STANCE: for | CONVICTION: medium` over a
  fully risk-on body ("rational allocation rather than a gamble", "paying a premium
  for certainty"). Medium reads one notch soft for the argument made, but the
  Trader's WAIT and Research Manager's neutral stance justify hedged conviction.
  HEADLINE "22.9% upside to $608.23" = 24 chars ≤ 32 ✓; shape exact ✓; single line,
  top only ✓ (modulo the opener above it).
- **Scope bleed: none under this prompt's own firewall.** The DO NOT list (lines
  26–28) bars exceeding max_drawdown, ignoring risk_score, and meme language —
  there is no domain lane for debators. Citing RSI 49 and the 32% bullish Reddit
  split is building on the transcript, which is instructed. (Contrast
  fundamentals_analyst, where the same cross-domain reach violated a hard lane.)
- **Arithmetic looseness, sourced:** "if we sit at half-size … we leave 22.9% of
  the potential move on the table" — 22.9% is the *full* upside $494.31→$608.23;
  half size forgoes half the portfolio impact, not the whole 22.9%. The number is
  sourced; the framing is the prompt's own template (line 20) taken literally.
- **"Margin of safety"** from 50% growth + net cash — qualitative inference with
  partial support; no fabricated fact. Within tolerance.
- **Repetition rule:** the 22.9%/$608.23 upside restates the Bull's line almost
  verbatim, against "do not repeat what's already been said" — but the
  opportunity-cost template effectively requires that exact figure. Self-inflicted.

**Net:** GROUNDED on facts — zero numbers outside the data block. Both format
violations (header placement, sentence/bullet shape) trace to contradictory prompt
instructions, not model misbehaviour. The prompt's format layer is the defect; the
grounding directive held completely.
