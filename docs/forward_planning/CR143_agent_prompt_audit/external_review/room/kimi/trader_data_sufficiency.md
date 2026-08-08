# External review — trader (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/trader.prompt.txt`
> (AMD, fact sheet as of 2026-08-07) and `real_samples/trader.reply.txt`.
> Unlike `external_review/room/trader.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/enforcement path — these are **findings, not hypotheses**.
> Note: the blind review audited an older corpus (AAPL, 3.0% cap, empty transcript);
> where its items are stale against the current prompt, that is stated explicitly.

## 1. Question

Does the Trader have enough data in the prompt to do its job — a specific,
mandate-compliant trade proposal (side, size, entry, target, stop, horizon, R:R) —
to ~95% accuracy?

## 2. Answer

**Yes for a direction/sizing opinion; no for a verifiably mandate-compliant ticket.**

The prompt delivers the analytical half well:

- Full transcript including the Research Manager's synthesis (prompt lines 126–155)
  — the Trader's primary declared input.
- Mandate caps, single-sourced from the enforcement resolver: single-name **10.0%**,
  sector **20.0%**, drawdown **50%**, open-risk **60.0%**, pace **10/day 50/week**,
  cooldown **off** (lines 57–63). Shown == enforced (`overlay_generator.py:78-111`
  reads the same `resolved_single_name_cap_pct` the PM clamp uses,
  `room_runner.py:663-672`).
- Portfolio state: cash **$7,161.28**, value **$9,411.21**, four positions with
  weights and unrealised P&L, explicit "You hold 0% of AMD" (lines 82–90).

But the compliance half is unverifiable from the prompt: the Trader is told the
caps, never the current consumption against three of them, and is promised one
input ("remaining drawdown capacity", line 14) that is never rendered.

Estimated accuracy on the scoped deliverable (a defensible side + size + levels,
or a reasoned WAIT): **~85–90%** — the sample reply is a coherent, mostly-grounded
WAIT. Against the full job (a sized BUY that is *verifiably* within open-risk,
pace, and drawdown caps, with a volatility-appropriate stop): **~60–65%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No stops on open positions; no current open-risk sum | The 60.0% total-open-risk cap (line 63) is defined as a sum across all open positions "including this one", but positions are listed without stops (lines 85–88). The new trade's compliance is uncomputable. |
| 2 | No trade-pace state (trades today/this week) and no last-stop-out timestamp | The pace cap (line 62) and the cooldown mechanic can't be checked. Moot in this sample (cooldown off, line 60) but structural: a set cooldown would be narrated as a "hard block" the agent cannot evaluate. |
| 3 | "Remaining drawdown capacity" promised, never delivered | `## Inputs` (line 14) names it as a Trader input; no current-drawdown figure appears anywhere in the prompt. |
| 4 | No volatility measure (ATR or similar) | The role demands a concrete stop ("Stop: ${price} (max acceptable loss)", line 25) with only static ranges ($424.03–$584.73, $149.22–$584.73) to place it against. Any stop is an inference dressed as a number — the exact collision with the grounding directive (lines 2, 157) the blind review flags. |
| 5 | No decision-journal history for this ticker | The Bear cited prior AMD stop-outs at **$502.59** (line 150) — dangerously close to the $494.31 entry — from a journal block the Trader never sees. For an execution agent, "this name stopped us out near this level before" is first-order sizing evidence. |
| 6 | Role guidance contradicts phase order: "Inputs: Risk Debators' arguments" (line 13) and "You DO NOT … Ignore the Risk Debators' arguments — your size must reflect what they collectively allow" (line 37) | The Trader speaks in EXECUTION (phase 4); the three Risk Debators speak AFTER it (phase 5). The arguments the Trader is told to size against do not exist yet at its turn. Structural, not cosmetic. |
| 7 | Dual output schema | The early code-fenced ticket template (lines 17–30) vs the late stance-header + bullets format (lines 159–167). Both live in the same prompt; the reply emitted both (see §6). |

## 4. Supplier check — what the codebase can actually deliver

Assembly path: base prompt `content/agents/trader.md` (role/inputs/output-schema/
DO-NOT text) → mandate block `overlay_generator._mandate_common_block`
(`backend/app/agents/overlay_generator.py:78-111`) + `_trader_block`
(`overlay_generator.py:392-395`) → Room turn `room_prompts.build_room_messages`
(`backend/app/services/room_prompts.py:321-483`) → portfolio block
`room_runner._build_sim_holdings_block` (`room_runner.py:682-771`) → phase order
`PHASES` (`room_runner.py:144-166`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | Per-position stops + open-risk sum | **STORED, NOT RENDERED** | Every open trade row carries `stop` (`sim_engine.py:111,132`); the aggregate `existing_open_risk_pct` is already computed per run (`sim_engine.py:481-501`, `risk_limit_context` at `sim_engine.py:503`) and threaded through the Room context (`room_runner.py:800-826`, `:312-314`). It is consumed ONLY by enforcement (`check_mandate_compliance` at `room_runner.py:1969-1971`; `enforce_safety_floor` at `room_runner.py:3248-3250`). `build_room_messages` has no parameter for it (`room_prompts.py:321-335`). Rendering the per-position stop in `_build_sim_holdings_block` (one line per position, `room_runner.py:752-755`) plus the current open-risk sum is a small, zero-new-fetch change. |
| 2 | Pace/cooldown state | **COMPUTED, NOT RENDERED** | `last_loss_closed_at` and `trade_open_timestamps` are built by the same `_build_room_risk_limit_context` (`room_runner.py:800-826`) and likewise go only to enforcement. Same one-render class as #1. |
| 3 | Current drawdown % | **COMPUTED, NOT RENDERED** | `ctx.current_drawdown_pct` (`room_runner.py:290`) is passed to `enforce_safety_floor` (`room_runner.py:3269`) but never enters any prompt. The `## Inputs` promise is undelivered today. |
| 4 | ATR / volatility | **AVAILABLE via existing provider, not computed** | `compute_technicals` (`technicals.py:75-152`) already pulls daily OHLC history through the cached market-data provider; `trading_math/indicators.py` implements only `rsi`, `rsi_tone`, `sma` (lines 20-50). ATR is a new pure-math function over data already in hand — no new provider, no new fetch. It inherits the existing quote/candle TTLs (60s quotes via `CachingProvider`), so no new rate-limit exposure. |
| 5 | Decision-journal history | **FETCHED, GATED AWAY** | `build_journal_context_block` (`journal_context.py:78-98`) fetches real entries (incl. summaries with prior stops — the Bear's $502.59) but is gated Bull/Bear only (`room_prompts.py:382-385`). Extending the gate to the Trader is a one-condition change with an established retention-by-plan contract. |
| 6 | Debator inputs before they exist | **STRUCTURAL CONTRADICTION — CONFIRMED IN CODE** | `PHASES` puts EXECUTION before RISK (`room_runner.py:159-164`). The debators react to the Trader (they receive `trade_proposal`, `room_prompts.py:397-400`), never the reverse. No wiring can fix this; either the base-prompt Inputs/DO-NOT lines get rewritten ("the debators will challenge your proposal — pre-empt them") or the phase order changes (a much bigger decision). |
| 7 | Dual output schema | **PROMPT-ONLY DEFECT — CONFIRMED LIVE** | Early template from `content/agents/trader.md` (verbatim at prompt lines 17-30); late format from `_PROSE_FORMAT + _STANCE_FORMAT` (`room_prompts.py:391-395`). The sample reply emitted BOTH (stance block, then the ticket block + "Rationale:"). Fix is deleting or rewriting the early block; no code change. |

Two further wiring findings the blind review could not see:

- **The live Trader's numbers are prose-only.** `ctx.trader_entry/stop/target/size_pct`
  are set ONCE from scripted defaults — stop = base × 0.94, target = base × 1.13,
  size = risk-tier ceiling (`room_runner.py:2967-2970`) — and never updated from the
  live Trader turn (the only assignments in the file). So the `trade_proposal` the
  Risk debators and PM reason against (`room_runner.py:3458-3462`,
  `room_prompts.py:400-401`), and the PM's entry fallback with `"trader"` provenance
  (`room_runner.py:979-980`), are the canned ~6%-stop/~13%-target numbers even when
  the live Trader stated different levels — or, as in this sample, stated WAIT with
  no levels at all. Provenance labelled "trader" is actually "scripted default".
- **The Trader's proposal is never compliance-checked.** `enforce_safety_floor`
  (with the open-risk/cooldown/pace context) runs only on the PM's parsed APPROVE
  (`room_runner.py:3231-3252`). The Trader can narrate a 50% position or a missing
  stop and nothing in the system reacts at its turn — the mandate text in its prompt
  is advisory prose; enforcement happens one phase later on a different agent's
  output. That is defensible design (the PM is the gatekeeper), but it makes the
  Trader's "You DO NOT size over the cap" line unenforced guidance, not a control.

## 5. Caveats

1. **Rendering risk state widens the grounding surface, not the fetch load.** Items
   #1–#3 reuse values already computed once per run (`room_runner.py:2921`); no new
   provider calls, no new caching concern. Item #4 (ATR) rides the same candle fetch
   `compute_technicals` already makes.
2. **Rendering stops per open position needs a None-story.** Trades opened before
   stops were attached, or via paths that allow `stop=None` (`sim_engine.py:560`),
   must render as "no stop recorded" — otherwise the Trader infers zero risk on the
   riskiest legs. The UNAVAILABLE-provenance pattern (`field_state`,
   `room_runner.py:337-354`) already exists for exactly this.
3. **Journal gating change leaks Bear-context into execution.** Prior stop-outs are
   sizing evidence, but the same block carries past synthesis prose; the Trader
   echoing old reasoning verbatim is the DEF095-class contagion the journal
   formatter already worries about (`journal_context.py:65-70`).

## 6. Reply-sample verification (`real_samples/trader.reply.txt`)

Line-by-line against the data block.

**Numbers.** Every figure except one is verifiably in the prompt: $494.31 (l.102),
$424.03 (l.107), $608.23 (l.117), 10.0% (l.58), $584.73 (l.107/109), RSI 49 (l.106),
126.4 (l.103), 88 days (l.118), 2026-11-03 (l.118), EV/EBITDA 82.6x (l.115), 50%
(l.104), NVDA 9.4% (l.88). The one exception:

- **"0.00:1.00" — fabricated, and arithmetically wrong.** No R:R figure exists in
  the data block or transcript. Worse, the claim it dresses up is false: from
  $494.31, upside to $608.23 is **+23.1%**, downside to $424.03 is **−14.2%** —
  reward:risk ≈ **1.6:1 in the buyer's favour**, not "perfectly symmetric". The
  midpoint of $424.03–$608.23 is $516.13; the price sits *below* it, closer to
  support. The Research Manager originated "exactly between … symmetric
  risk-reward" (prompt l.155); the Trader echoed it and hardened it into a
  precise-looking ratio that violates the grounding directive ("ONLY numbers from
  the data block above", l.157). This is transcript-contagion: an upstream agent's
  unlabeled inference became downstream "fact".

**Unlabeled inference.**

- "adding AMD … merely increases sector concentration in Semiconductors" (bullet 3)
  presumes **NVDA is a semiconductor name** — a categorical fact nowhere in the
  prompt (AMD's sector is given at l.116; NVDA's is not). Training-memory leakage
  of a non-numeric fact. The arithmetic would otherwise be checkable: 9.4% + ≤10%
  ≤ 19.4%, just under the 20.0% sector cap.
- "NVDA already … hitting the 10.0% single-name cap" — NVDA is at 9.4%; "hitting"
  is imprecise, inherited from the RM's looser phrasing (l.155). Minor.

**Scope bleed.** None of the fundamentals/news/social kind seen in the
fundamentals_analyst reply. Risk-reward and sizing reasoning is the Trader's own
domain (R:R is in its output schema, l.28).

**Stance-evidence tension.** `STANCE: neutral` over a body that opens "**Wait.**",
says a new position "violates the discipline", and calls the risk "excessive" —
the body reads `against` (entering now). Defensible under "'neutral' if you
genuinely land in the middle" (l.163), but the header is softer than the argument.

**Format compliance.**

- Stance line: first line, exact shape, HEADLINE "Symmetric standoff at $494.31" =
  29 chars ≤ 32 ✓ (`STANCE_HEADLINE_MAX_CHARS`, `room_prompts.py:255`).
- **Dual-format failure — blind-review failure mode #1 confirmed live.** After a
  compliant stance header + thesis + 3 bullets, the reply appends the overridden
  early ticket template ("Instrument: AMD / Side: WAIT / Size: 0% …") AND a
  "Rationale:" paragraph. It avoided code fences (no ```), so it satisfies the
  letter of the late format while also satisfying the early one — exactly what a
  prompt carrying two incompatible schemas invites.
- "Build on the transcript — do not repeat what's already been said" (l.157): the
  first sentence and bullet 1 are a paraphrase of the RM's recommended stance
  (l.155). Marginal — translation is the job — but the repetition is near-verbatim.
- Side `WAIT`: consistent with long-only ("frame negative views as 'avoid' /
  'wait'", l.66) ✓. The `SELL`-in-schema contradiction did not bite this turn.

**Net: NOT GROUNDED — one fabricated number.** The `0.00:1.00` ratio is a
precise, decisive-sounding figure that is absent from the prompt and
arithmetically false, and it carries the entire thesis sentence. Plus one
non-numeric training-memory leak (NVDA's sector). Everything else is bound to the
block. The failure pattern is different from fundamentals_analyst (which was
grounded on numbers but bled scope): here the domain discipline held and the
numeric discipline broke — once, at the load-bearing point.

## 7. Relationship to the blind review (`../trader.md`)

The blind review audited an older corpus (AAPL; MSFT/NVDA book; 3.0% cap; 30%
drawdown; 10.5% open-risk; 1.0h cooldown; "(You are first to speak.)" transcript).
Against the current prompt and code:

- **Confirmed (still live):** the dual output schema (its contradiction #1) — now
  with empirical proof, since the real reply emitted both formats. The `SELL`
  option vs long-only (its #2) — unchanged in `content/agents/trader.md`. The
  concreteness-vs-grounding collision on stop/target (its #4) — corroborated by
  code: the scripted path itself invents levels (`room_runner.py:2967-2970`), so
  the system models the behaviour the grounding rule forbids.
- **Confirmed and upgraded from hypothesis to finding:** unfollowable #2 (open-risk
  cap unverifiable — stops stored, sum computed, neither rendered) and #4
  (pace/cooldown unverifiable — computed, enforcement-only). Both are one-render
  fixes, not new providers.
- **Killed as stated:** unfollowable #1 (empty transcript). The Trader now speaks
  8th with the full synthesis transcript. BUT the code reveals the deeper version
  the blind review couldn't see: the Trader still speaks *before* the Risk
  Debators, so "size must reflect what they collectively allow" remains
  structurally impossible — the fix moved the problem, didn't close it.
- **Could not see (new, from code):** live Trader numbers never propagate —
  downstream phases and the PM's "trader"-provenance fallback use scripted
  defaults; and the Trader turn is never compliance-checked (floor runs on the PM
  only).

The two reviews compose as before: its CUT list (delete the early template,
de-duplicate the mandate restatements) is the prompt-side fix; this supplier check
says the data to make the Trader's compliance claims real already exists one
render away — and that the fabricated `0.00:1.00` is what the current gap costs
in production.
