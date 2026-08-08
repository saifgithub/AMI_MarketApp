# External review — research_manager (data sufficiency + supplier check)

> Reviewer: `kimi-for-coding` · Kimi track K session.
> Corpus reviewed: `docs/forward_planning/CR143_agent_prompt_audit/real_samples/research_manager.prompt.txt`
> and `…/research_manager.reply.txt` (AMD convene, SYNTHESIS phase).
> Unlike `external_review/room/research_manager.md` (blind prompt-coherence audit),
> this review had codebase access. Every availability claim below is verified against
> the actual fetch/render path — these are **findings, not hypotheses**.

## 1. Question

Does the Research Manager have enough data in its prompt to do its job to
~95% accuracy?

## 2. Answer

**Yes for adjudication, no for the quantified synthesis the prompt actually asks for.**

The scoped job — weigh the Bull and Bear arguments and produce a
mandate-consistent stance — is well supplied:

- The full transcript is present: all four analysts plus both researchers
  (prompt lines 119–142). The blind review's "adjudicator with nothing to
  adjudicate" scenario does not exist in this sample; on current code the RM
  always speaks after the RESEARCHERS phase and reads the live transcript
  (`room_runner.py:157-158`, sequential path `room_runner.py:3541-3554`).
- Mandate is over-supplied if anything: full mandate block, mandate snapshot,
  hard compliance constraints, and the enforced **10.0%** single-name cap
  (prompt line 116, rendered by `room_prompts.py:416-428`).
- Real portfolio block (cash, four open positions with weights, AMD not held).

But the turn instruction demands "**asymmetry numbers** + lean + size
implication" (`_LENGTH_GUIDE`, `room_prompts.py:74`), and the prompt contains
**no asymmetry numbers, no trade geometry, and no verifiable history**. The
model is asked to quantify a risk/reward it was never given.

Estimated accuracy on the scoped deliverable (a stance + evidence-backed
adjudication): **~85–90%**. Against the full job as written (quantified
asymmetry + honest size implication): **~60–65%**.

## 3. Data gaps (from the prompt alone)

| # | Gap | Impact |
|---|---|---|
| 1 | No asymmetry / upside-downside figures anywhere | The length guide's first demand ("asymmetry numbers") is unfulfillable except by ad-hoc arithmetic on range vs target — which the reply then did, and got wrong (§8). |
| 2 | No trade geometry at synthesis time | Entry/stop/target don't exist yet (Trader speaks after, `room_runner.py:159`). "Size implication" degrades to a bare % with no risk budget attached. |
| 3 | Decision Journal not visible to the RM | The Bear's strongest exhibit ("decision journal shows prior AMD positions hit stop losses around **$502.59**", prompt line 142) is unverifiable by the adjudicator — the journal block is injected for Bull/Bear only. The RM must take a factual claim about the user's own history on faith. |
| 4 | No sector labels/weights for existing holdings | The mandate carries a **20.0%** sector cap; the portfolio block gives weights (NVDA **9.4%**, HPQ **6.3%**) but no sectors. A ~10% AMD add to a book already ~15.7% in plausibly-Technology names would breach the safety floor — the one mandate constraint that could bind here, invisible to the agent asked for a "size implication". |
| 5 | Stance vocabulary contradiction | Role guidance says "Lean long / lean short / pass / wait" (prompt line 23); the mandatory envelope says `for\|against\|neutral` (lines 148-153); "lean short" also collides with LONG-ONLY. Both strings ship. |
| 6 | Duplicate mandate snapshot | The "User mandate snapshot" block (lines 110-114) restates the full mandate above it — pure token cost on the agent with the worst historical truncation rate (66.1% pre-DEF125, `room_prompts.py:90`). |

## 4. Supplier check — what the codebase can actually deliver

Turn/prompt assembly: `build_room_messages` (`room_prompts.py:321-483`);
transcript renderer `_format_transcript` (`room_prompts.py:886-893`);
fact-sheet renderer `_format_profile` (`room_prompts.py:503`); per-field
provenance `field_state` populated at `room_runner.py:337-612`.

| # | Item | Verdict | Evidence / effort |
|---|---|---|---|
| 1 | Asymmetry numbers | **AVAILABLE, NOT WIRED** | `trade_asymmetry(entry, stop, target)` exists (`backend/app/trading_math/trade.py:47`, M08) and is already computed every run (`room_runner.py:2923`) — but only injected into the scripted `_TEMPLATES` fallback formatter (`room_runner.py:2959-2963`). `_format_profile` never renders it (no `upside`/`downside`/`bear_quant` reference in `room_prompts.py`). Same class: `bear_quant` (multiple-compression downside, computed `room_runner.py:643-648` when fundamentals live) is also template-only. Caveat: the reference geometry is scripted-path heuristic (base price, −6% stop, +13% target, `room_runner.py:2910-2912`) — wiring it into the LLM prompt needs honest "reference levels" labelling, not a new provider. |
| 2 | Reference drawdown contribution | **AVAILABLE, NOT WIRED** | `drawdown_contribution` (`backend/app/trading_math/risk.py:24`) already feeds `_drawdown_snapshot_line` (`room_prompts.py:280-318`), which renders the derived P×S/100 figure — but the proposal is only supplied for RISK/VERDICT phases (`room_prompts.py:400`). Extending the deterministic reference position to SYNTHESIS is a one-line gate change; gives "size implication" a real risk budget. |
| 3 | Decision Journal for the RM | **ALREADY WIRED, GATED OFF** | `build_journal_context_block` (`journal_context.py:78-98`) fetches real per-ticker history (date/title/outcome/summary/user_note, plan-gated window) and is already injected — for Bull/Bear only (`room_prompts.py:382-385`). Adding the RM is a one-condition change. Token cost is the only real consideration. |
| 4 | Sector weights for holdings | **ALREADY WIRED, PM-GATED** | `sector_weights`/`sector_holdings` are computed per run (`room_runner.py:302-305`) and rendered by `_format_sector_allocation` (`room_prompts.py:489-500`) — gated to PORTFOLIO_MANAGER only (`room_prompts.py:454-455`). One-condition change to share with the RM (and arguably the researchers). |
| 5 | Stance vocabulary | **DEFECT IN PROMPT, NOT DATA** | "Lean long / lean short / pass / wait" lives in the base prompt (`content/agents/` research_manager); `for\|against\|neutral` in `_STANCE_FORMAT` (`room_prompts.py:264-277`). No fetch path involved — a text fix. |
| 6 | Bull/Bear absence (blind review's core hypothesis) | **NOT REPRODUCIBLE ON CURRENT CODE** | "(You are first to speak.)" renders only for an empty transcript (`room_prompts.py:887-888`); the RM is the sole SYNTHESIS-phase agent running sequentially after RESEARCHERS (`room_runner.py:157-158`, `3541-3554`), and even failed turns enter the transcript with an `[AMI …]` mark (`room_runner.py:3437`). The corpus prompt the blind review saw is not in `corpus/` (only fundamentals_analyst and PM samples exist there) and cannot be produced by the current Room path — likely a 1-on-1 or hand-built variant. |

## 5. Structural caveats before wiring #1 / #3 / #4

1. **The RM is the truncation-worst agent.** 66.1% of its turns were cut off
   pre-DEF125 (`room_prompts.py:90`); its decode budget is now 900 tokens
   (`room_prompts.py:145`). Every block added to its prompt should be paired
   with cutting the duplicate mandate snapshot (gap #6) — net token delta
   matters here more than for any other agent.
2. **Reference levels are heuristics, not measurements.** Wiring
   `trade_asymmetry` output into the RM prompt imports the scripted −6%/+13%
   geometry. It must render labelled as a deterministic reference (the
   `_drawdown_snapshot_line` "Reference position" phrasing at
   `room_prompts.py:311-317` is the existing pattern to copy), or the RM will
   quote AMI-computed numbers as if they were the Trader's.
3. **Journal wiring inherits plan-gating.** The block's lookback window is
   retention-by-plan (DEF054/DEF055, `journal_context.py:37-57`); the RM on
   FLOOR_PASS may see a shorter history than the researchers' arguments
   implied. Degrades cleanly to "no history yet" — never raises
   (`journal_context.py:20-21, 45-57`).
4. **Provider-side caching is unchanged by all three wirings** — journal
   (Postgres read), sector weights (computed in-run), and asymmetry
   (arithmetic on numbers already fetched) add zero provider calls. The
   existing TTLs stand: quotes 60s (`market_data.py:400-421`), news 5-min
   (`market_data.py:463`), earnings 6h (`market_data.py:476`), social 24h
   durable Postgres + 300s L1 (`social_context.py:8-9, 39-41, 68`).
   Fundamentals remain the one uncached path — `fundamentals.py` has no cache
   at all, every convene hits `yf.Ticker().info` live.

## 6. Recommended slice (if this becomes a CR)

Cheap, no new provider, ordered by yield:

1. Extend the deterministic reference position + `trade_asymmetry` render to
   the SYNTHESIS phase (one-line gate at `room_prompts.py:400`, plus a
   labelled line in the RM prompt). Directly closes the "asymmetry numbers"
   demand.
2. Un-gate `build_journal_context_block` for RESEARCH_MANAGER
   (`room_prompts.py:382-385`) so the adjudicator can check the researchers'
   history claims.
3. Share `_format_sector_allocation` with the RM (`room_prompts.py:454`).
4. Delete the duplicate mandate snapshot from the room addition
   (`room_prompts.py:462-467`) to pay for 1–3 in tokens.
5. Fix the stance vocabulary in the base prompt ("Lean long / lean short /
   pass / wait" → the envelope's `for/against/neutral` + long-only-safe
   wording).

## 7. Relationship to the blind review (`../research_manager.md`)

| Blind-review claim | Verdict here |
|---|---|
| "Role requires Bull/Bear inputs, but the agent is told it is first to speak" + failure mode 1 (hallucinated Bull/Bear content) | **KILLED for the Room path.** The real prompt carries the full six-turn transcript; current code makes an empty RM transcript unreachable (§4 row 6). The real reply fabricates no Bull/Bear content — every attributed claim matches the transcript. The corpus prompt behind this hypothesis is not reproducible from the codebase. |
| 3-part structure vs thesis+bullets+STANCE-line format collision (failure mode 2) | **CONFIRMED — and observed live.** The real reply answered with the 1-on-1 three-part structure ("Points of agreement / Points of dispute / Recommended stance") inside the Room, ignoring the explicit "In the Room, follow the format instruction appended at the end of your prompt instead" (prompt lines 17-19). No thesis sentence, no bullets. |
| Stance vocabulary mismatch ("lean long/short/pass/wait" vs `for/against/neutral`) | **CONFIRMED in code.** Both strings ship (§4 row 5). |
| "Asymmetry numbers" never defined, not in data block | **CONFIRMED and traced.** The numbers exist one layer down — `trade_asymmetry` is computed every run and fed only to the scripted fallback (§4 row 1). |
| "Size implication" unfollowable — no sizing authority, no tool | **CONFIRMED, with nuance.** The RM does get the enforced 10.0% cap note (CR055, `room_prompts.py:416-428`), so a ceiling exists; what's missing is any risk budget or geometry to size against (gaps #2, #4). |
| Compliance drift risk ("lean short" vs LONG-ONLY) | **NOT TRIGGERED in the sample.** The reply chose `neutral` + "wait", which is the mandate-compliant negative framing. |
| "Build on the transcript" unfollowable (empty transcript) | **KILLED** with the empty-transcript premise. |
| CUT list (1-on-1 section, Q&A routing, duplicate snapshot, Voice block) | **ENDORSED by evidence.** The duplicate mandate snapshot is real (prompt lines 110-114), and the live reply proves the 1-on-1 section is not inert noise — the model preferred it over the Room format. Cutting it removes the collision, not just tokens. |

## 8. Reply-sample verification (`real_samples/research_manager.reply.txt`)

Line-by-line against the data block.

**Numerically clean.** Every figure in the reply is verifiably in the prompt:
**$494.31**, **126.4**, **50%**, **$8,835M**, **$608.23**, **PEG 1.12**,
**EV/EBITDA 82.6x**, **P/S 19.5x**, **$424.03**, **RSI 49**, **88 days**,
**2026-11-03**, **10.0%**, NVDA **9.4%**, **$584.73**. Zero hallucinated
numbers. No fabricated Bull/Bear attributions — each side's paraphrase matches
its transcript turn. The grounding directive held on facts.

**One arithmetic claim contradicted by the prompt's own numbers.** "The
**$494.31** price sits exactly between the **$424.03** support and **$608.23**
target, creating a symmetric risk-reward that offers no edge" — false on the
block's figures: upside to target is **+23.0%** (608.23/494.31 − 1), downside
to support is **−14.2%**, and the range midpoint is 516.13, not 494.31. The
numbers are asymmetric *in favour of the long side*; the "no edge" premise the
neutral stance rests on is the one quantitative judgement the model had to make
itself — exactly the arithmetic `trade_asymmetry` exists to take off the
model's plate (§4 row 1). Also: "a break below **$424.03** (bullish
confirmation of dip)" is incoherent — a break below support is a breakdown;
the transcript's Market Analyst framed both directions as neutral-required
confirmation.

**Format non-compliance — blind-review failure mode 2 confirmed live:**

1. Used the 1-on-1 three-part structure in the Room; no one-sentence thesis,
   zero bullet points (mandated: "lead with a one-sentence thesis, then short
   bullet points").
2. Bold paragraph labels ("**Points of agreement.**" etc.) function as
   headings despite "no headings".
3. ~7–8 sentences vs the mandated "4–6 sentences".
4. Stance line missing its closing `]` — `[STANCE: neutral | CONVICTION:
   medium | HEADLINE: 494.31 / 608.23`. Functionally harmless (the parser is
   per-field and bracket-tolerant, `room_runner.py:1693, 1705-1710`; stance,
   conviction and the 15-char headline all extract), but a violation of "in
   exactly this shape". HEADLINE is also two numbers against "the single
   number or fact".
5. No explicit asymmetry numbers and no size implication — the two content
   items the length guide names (`room_prompts.py:74`).

**Scope bleed — moderate.** "Wait for a break below **$424.03** … or above
**$584.73** (momentum confirmation) before committing capital" issues entry
triggers — the Trader's domain (entry/stop/target/horizon) borrowing the
Market Analyst's momentum vocabulary. The RM's lane is the lean; trigger
levels belong to EXECUTION.

**Stance-evidence tension.** `STANCE: neutral | CONVICTION: medium` with a
"wait" recommendation is mandate-coherent (LONG-ONLY → negative views framed
as avoid/wait — compliant, not drift). But the neutrality is argued from the
false symmetry premise above; read strictly off the block (+23.0% vs −14.2%),
the evidence leans long, so the header is weaker than its own numbers. The
"**10.0%** single-name cap already active in the portfolio (via NVDA at
**9.4%**)" line is also muddled — the cap is per-name and does not bind a new
AMD position; the constraint that actually could (the 20% sector cap) was
invisible to the agent (gap #4).

**Net: GROUNDED on facts — zero invented numbers, zero fabricated
attributions — but NOT fully compliant**: wrong self-computed asymmetry
premise, four-plus format violations, one moderate scope bleed. The
hallucination class the blind review feared (invented Bull/Bear content) did
not occur; the defect class that did occur is self-service arithmetic in place
of the unwired `trade_asymmetry` figures.
