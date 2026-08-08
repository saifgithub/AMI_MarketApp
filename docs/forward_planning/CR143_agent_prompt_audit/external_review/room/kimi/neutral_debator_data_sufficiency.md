# External review — neutral_debator (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/neutral_debator.prompt.txt`
> and `…/neutral_debator.reply.txt` (AMD run, fact sheet as of 2026-08-07).
> Unlike `external_review/room/neutral_debator.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/assembly path — these are **findings, not hypotheses**.
> Note: the blind review audited an older AAPL corpus (3.0% cap, 5.0% reference, no
> transcript). The production prompt reviewed here differs materially; several blind
> findings are killed by that alone.

## 1. Question

Does the Neutral Debator have enough data in the prompt to do its job — synthesise
the Aggressive and Conservative extremes into a middle-path size/entry/stop/hedge
that respects the mandate — to ~95% accuracy?

## 2. Answer

**Yes for the job as scoped, with one unverifiable mandate cap.**

The decisive fact the blind review could not see: the RISK phase runs **sequentially**
(`PHASES`, `room_runner.py:160-164`; only ANALYSTS is parallel, `room_runner.py:151-156`),
so by the time the Neutral Debator speaks, the transcript already contains the Trader's
proposal and both debators' arguments — rendered via `_format_transcript` into
`Transcript so far:` (`room_prompts.py:378, 470`). The real prompt carries all three
(lines 146–169). The blind review's core "missing inputs" finding does not apply to
the production prompt.

What the scoped deliverable ("Write 2 sentences — middle size + one-line reason",
`_LENGTH_GUIDE`, `room_prompts.py:78`) needs:

- Both extremes' positions: **present** — Aggressive at **10.0%** (line 166),
  Conservative at **4.0%** with stop **$464.65** (line 169).
- Trader's proposal: **present** (WAIT, lines 146–161) plus a deterministic reference
  position in the mandate snapshot (line 112: 10.0% size, entry 494.31, stop 464.65,
  → 0.60 pt of the 50 pt cap).
- All mandate caps: **present** (lines 39–57) — except one is unverifiable (Gap 1).
- Portfolio state: **present** (lines 71–79) — sizes and unrealised P&L, no stops.

Estimated accuracy on the scoped deliverable: **~90–95%**.
Against the full job as the base prompt states it (verify every mandate cap,
"propose specific compromise: size, entry, stop, **hedge**"): **~65–70%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No stop distances (or open-risk contributions) for existing positions | Total open-risk cap (60.0%, line 53) is defined as the sum of size%×stop% across ALL open positions; the block gives DIS/GOOGL/HPQ/NVDA weights (lines 74–77) but zero stops. The cap is uncheckable by the agent — blind review Unfollowable C, confirmed. The reply asserts compliance with it anyway. |
| 2 | No sector labels/weights for holdings | Sector cap is 20.0% (line 49); Conservative's "sector correlation risk" (line 169) and the Trader's concentration argument (line 150) are unverifiable from the block — NVDA is never labelled Semiconductors in the portfolio section. |
| 3 | No hedge instruments | The output style demands "Propose specific compromise: size, entry, stop, hedge" (line 22) but the mandate is LONG-ONLY (line 56) and no options/derivatives data exists anywhere in the sheet. The only producible "hedge" is a smaller size — role guidance contradicts the available inputs and the compliance rules. |
| 4 | AMI's own deterministic debator size spread is not shown | The run computes Aggressive/Conservative/Neutral sizing positions (see §4, G4); the LLM debators never see them, so each invents its own numbers (Aggressive said 10.0%, Conservative 4.0%, Neutral 5.0% — none matching the computed spread). Minor: the transcript debate is the intended mechanism, but the computed neutral size (10.0% = Trader's size) would have changed the answer. |

## 4. Supplier check — what the codebase can actually deliver

Prompt assembly: `build_room_messages` (`room_prompts.py:321-483`) — transcript at
`room_prompts.py:378, 470`; mandate snapshot + reference position via
`_drawdown_snapshot_line` (`room_prompts.py:280-318`), fed only in RISK/VERDICT
phases (`room_prompts.py:400-401`); portfolio block via `_build_sim_holdings_block`
(`room_runner.py:682-771`). Reference position is deterministic:
`ctx.trader_size_pct = _risk_tier_size_ceiling(mandate)` (`room_runner.py:2913`),
entry = base price (`:2910`), stop = entry×0.94 (`:2911`) — shown == enforced
(`room_runner.py:670-672`).

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | Per-position stops / existing open-risk total | **ALREADY WIRED, NOT SURFACED** | Every open `sim_trades` row carries its own stop; `_risk_limit_context` sums size%×stop% into `existing_open_risk_pct` (`sim_engine.py:481-501`), which the Room already fetches (`room_runner.py:2864, 2894`) and hands to the safety floor (`room_runner.py:1914`; floor fails closed when absent, `safety_floor.py:520-534`). Only the render is missing: `_build_sim_holdings_block` emits qty/weight/unrealised only (`room_runner.py:752-755`). One render-key change — no new fetch. |
| 2 | Sector weights per holding | **AVAILABLE, NOT WIRED (for this agent)** | Computed once per run as `ctx.sector_weights` (`_build_room_sector_context`, `room_runner.py:774-789`) but rendered only for the PORTFOLIO_MANAGER (`room_prompts.py:453-455`, CR026). Widening the gate to the three RISK debators is a one-line change against an already-computed dict. |
| 3 | Hedge instruments | **NOT AVAILABLE** | No options/derivatives provider anywhere in the repo; the entire yfinance surface is `.info`/`.fast_info`/`.history()`/`.news`/`.calendar`. A real hedge needs a new provider — and LONG-ONLY compliance plus the debator's own role firewall make it questionable regardless. Correct fix is editorial: rewrite the output-style line in `content/agents/neutral_debator.md:26` to "protective measure (size/stop)", not data wiring. |
| 4 | Deterministic debator size spread | **COMPUTED, USED ONLY BY SCRIPTED TEMPLATES** | `risk_debator_sizes(trader_size)` → aggressive +2, conservative −1.5, neutral = trader size (`trading_math/sizing.py:111-127`); stored at `room_runner.py:2915-2918` and exposed as `agg_size`/`cons_size`/`neu_size` in the f-string formatter dict (`room_runner.py:2954-2956`) — which feeds the canned `_TEMPLATES` (`room_runner.py:174`), not `build_room_messages`. Surfacing `neu_size` in the mandate snapshot is one render line; whether it SHOULD be shown (it biases the "judgment-based mediator" toward AMI's own answer) is a design call, not a data gap. |

## 5. Caveats

1. **Gaps 1–2 are render-only changes against data already in process memory** — no
   new provider calls, no rate-limit exposure, no caching implications (unlike the
   fundamentals_analyst findings, where wiring statement endpoints would multiply
   Yahoo calls).
2. **The open-risk sum exists per open TRADE ROW, not per aggregated holding**
   (`sim_engine.py:481-483`) — the portfolio block aggregates lots per ticker, so
   rendering stops honestly means rendering per-lot or rendering the precomputed
   `existing_open_risk_pct` total, not re-deriving from the aggregated rows.
3. Rows can have `stop=None` (`sim_engine.py:493`) — those contribute 0 to the sum.
   If stops are surfaced, that absence must render loudly, or the agent will assume
   a protected position that isn't.

## 6. Recommended slice (if this becomes a CR)

Cheap, no new provider:

1. Render `existing_open_risk_pct` (and ideally per-lot stops) into the portfolio
   block for RISK/VERDICT-phase agents — makes the 60% cap verifiable.
2. Widen the `sector_weights` render gate from PM-only to PM + the three debators.
3. Editorial (pairs with the blind review's CUT list): fix the STANCE-first vs
   "Open with" ordering conflict, the "2 sentences" vs bullets budget, and the
   "hedge" demand in `content/agents/neutral_debator.md:23-26`.

Do NOT surface `neu_size` without a design decision — it collapses the mediator's
judgment into AMI's pre-computed answer.

## 7. Relationship to the blind review (`../neutral_debator.md`)

The blind review audited an older AAPL corpus; against the production AMD prompt:

**Killed:**
- *Unfollowable A/B* (Aggressive/Conservative/Trader inputs "not supplied"; compromise
  impossible): the production prompt carries all three in `Transcript so far:`
  (lines 146–169), assembled at `room_prompts.py:470` over a sequential RISK phase
  (`room_runner.py:160-164`). Its Failure Mode 1 (hallucinated synthesis) did not
  materialise — the reply synthesises the actual transcript.
- *Contradiction D* (5.0% reference vs 3.0% cap): structurally impossible in current
  code — the reference size IS the enforced ceiling (`room_runner.py:2913`,
  `room_runner.py:670-672`). Production sample: cap 10.0%, reference 10.0%. Its
  Failure Mode 3 (oversized from the reference) is dead with it.
- *Failure Mode 3's "stop derived from the generic reference"* variant: partially
  alive — the reply's stop **$464.65** is exactly the deterministic reference stop,
  not an AAPL-specific level, but that reference is AMD's real entry×0.94, so it is
  a legitimate level here.

**Confirmed live in the real sample/reply:**
- *Contradiction A* (STANCE-first vs "Open with: Splitting the difference"): both
  instructions present (`room_prompts.py:258-277` vs `content/agents/neutral_debator.md:23`);
  the reply put the opener first and the STANCE line second — direct violation of
  "your VERY FIRST line must be this one line". The aggressive_debator's transcript
  entry (lines 162–164) shows the identical violation — systemic across debators.
- *Contradiction B* (2-sentence budget vs required bullets/details): `_LENGTH_GUIDE`
  (`room_prompts.py:78`) vs `_PROSE_FORMAT`; the reply wrote a thesis + 3 bullets
  (~7 sentences). Its Failure Mode 2 (format collision) confirmed.
- *Contradictions C/E* (tabular tone vs no-tables; senior-PM voice vs minimise-prose):
  both present verbatim (lines 30–32 vs 62, 173). Editorial, not data.
- *Unfollowable C* (open-risk cap unverifiable): confirmed as Gap 1 — and the reply
  proves it matters by asserting compliance it cannot compute.

**Could not see / out of scope for this review:** the blind review's CUT list is
largely editorial and stands; this review adds only that its "5.0% reference" cut is
already moot in code.

## 8. Reply-sample verification (`real_samples/neutral_debator.reply.txt`)

Line-by-line against the data block.

**Numbers:** every cited figure is in the block — $464.65/-6.0% (line 112, 169),
50% growth, $8,835M, 126.4, 82.6x, $608.23, 22.9% (lines 137/164), $584.73/$424.03,
88 days, $494.31, 32% bullish, 10.0% cap, 60.0% open-risk limit, 14.2% (line 169).
**Two numbers are NOT in the block: `5.0%` and `0.30%`.** Both are derivations, not
training-memory leakage: 5.0% = half the 10.0% cap (a judgment call, sitting between
Aggressive's 10.0% and Conservative's 4.0%); 0.30% = 5.0×6.0/100, arithmetically
correct and exactly the computation pattern the prompt's own reference position
models (line 112). They violate the letter of "ONLY numbers from the data block"
but are the class of derived sizing the role exists to produce. No hallucinated
facts.

**Three non-numeric defects:**

1. **Misattribution.** "the **14.2%** drawdown risk the Bear highlights" — 14.2%
   appears only in the **conservative_debator's** turn (line 169); the Bear's turn
   (line 140) never states it. Wrong source, right number.
2. **Unverifiable compliance claim.** "keeps total open risk within the **60.0%**
   limit" — uncomputable from the block (Gap 1: no stops on the four existing
   positions). Blind-review Unfollowable C surfacing as a live ungrounded assertion.
3. **Internal tension.** Line 1 proposes a "**conditional** 5.0% position"; bullet 2
   says "enter now at **$494.31**". Conditional vs immediate is never resolved.

**Stance-evidence:** `STANCE: for | CONVICTION: medium` over a conditional-buy body —
defensible (the role explicitly permits leaning one way, lines 26–28), though both
the Trader (WAIT) and Research Manager (Neutral) in the transcript landed the other
way, and the "conditional" framing sits awkwardly under an unqualified "for".

**Format compliance:**
- STANCE line: present once, correct shape, HEADLINE 21 chars ≤ 32 — but it is the
  **second** line, not the mandated VERY FIRST (the opener instruction won the
  collision — blind-review Contradiction A, live).
- Length: mandated "2 sentences"; delivered thesis + 3 bullets ≈ 7 sentences
  (Contradiction B, live — the bullet-format instruction won).
- Bold on key metrics: compliant. No headings/tables/fences: compliant. No
  preface/"Speaking as": compliant.

**Scope bleed:** none in the analyst sense — debators exist to synthesise the
transcript, so citing the social analyst's 32% or the fundamentals multiples is in-role.

**Net:** GROUNDED on facts — zero training-memory numbers; the only non-block figures
are two correct arithmetic derivations the role is supposed to produce. NOT
format-compliant (STANCE placement, sentence budget), with one misattribution and
one compliance claim the data cannot support.
