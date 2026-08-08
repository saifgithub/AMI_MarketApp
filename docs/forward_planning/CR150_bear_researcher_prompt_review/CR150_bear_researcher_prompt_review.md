# CR150 — Bear Researcher: give the downside case a real number, and delete the one we invented

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.

**Source:** CR143 Phase 1/3b, plus two independent reviews of the Bear Researcher — a blind
prompt-coherence audit ([`external_review/room/bear_researcher.md`](../CR143_agent_prompt_audit/external_review/room/bear_researcher.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/bear_researcher_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/bear_researcher_data_sufficiency.md)).
Both were treated as **hypotheses**. Every claim below carries a supplier check (does the code inject
the data the prompt claims?) and a parser check (does anything read the output this instruction
shapes?) before it became scope. The five that failed those checks are listed, with the evidence, in
**Rejected claims** — that section is the point of the method, not an appendix.

## Why

The Bear Researcher is the one agent in the Room whose deliverable is a **quantity**: *"Quantify
downside."* Everyone else can do their job with adjectives. The Bear cannot — a risk without a
magnitude is the FUD its own `## You DO NOT` block forbids.

The fact sheet supplies no magnitude. It supplies a price, a set of multiples, two ranges and a
consensus target; it supplies no volatility, no beta, no scenario impact, no peer baseline, and no
market cap. So the prompt asks for a number the system does not have — and then, three lines above
the grounding directive that forbids exactly this, it shows the model one:

> `Quantify downside: "if X happens, we're looking at -25%, and X is more likely than consensus thinks because..."`
> — [`content/agents/bear_researcher.md:27`](../../../content/agents/bear_researcher.md#L27)

**That number is in the permanent record.** Measured against
[`backend/tests/unit/fixtures/pm_verdict_corpus.txt`](../../../backend/tests/unit/fixtures/pm_verdict_corpus.txt)
— the P16 guard's frozen fixture, which is *every* real `room_runs.verdict->>'reason'` on Alpha
carrying a `$` figure as of 2026-08-08, 811 deduplicated rows:

| measure | value |
|---|---|
| verdicts containing `-25%` | **22 of 811 (2.7%)** |
| of those, attributing the figure to the Bear | **12** — *"the Bear's -25% downside to $53"*, *"the bear case for a -25% drawdown to $11.00"*, *"the Bear scenario's -25% downside to ~$95, which would breach the cap"* |
| `-25%` as a share of all downside-context magnitudes in the fixture | **18 occurrences — the most frequent value, 2.6× the next (`30%`, 7)** |

The verdict `reason` is what CR106 renders as the decision's justification and what
`build_journal_entry_for_run` writes into the Decision Journal. So a worked example's placeholder
travels: base prompt → Bear's prose → transcript → PM verdict → the user's permanent record, wearing
an attribution ("the Bear's") and a decimal point it never earned. This is failure pattern **P5**
(a fabricated figure asserted as a measurement) arriving through the one door nobody guards —
the *example*, not the data.

The second problem is the mirror of the first: **the evidence the Bear is told it has is capped,
undisclosed, or fetched and thrown away.** Its prompt names the user's Decision Journal history as a
headline input (DEF054/DEF055 exist because that claim was once false); the supplier silently caps at
five entries, silently applies a plan retention window, and renders nothing at all when it comes back
empty — so "the user has no history" and "the store errored" reach the model as the same silence. Its
mandate states a **total open-risk cap** that is a sum over stop distances the portfolio block does
not render, while the exact figure is already computed one module away for the PM's path. Its
compliance block bars microcaps below a market cap that `fundamentals.py` fetches on every convene and
uses only as a division denominator.

The Bear is not short of judgement. It is short of arithmetic — and every missing input it needs is
either already in the process or one unread dict key away.

## What was measured

Corpus: [`corpus/llm_audit_2026-08-07-epoch.json`](../CR143_agent_prompt_audit/corpus/llm_audit_2026-08-07-epoch.json)
(216 turns) and [`corpus/room_runs_2026-08-07-epoch.json`](../CR143_agent_prompt_audit/corpus/room_runs_2026-08-07-epoch.json)
(18 convenes). **n = 18 Bear turns.** Every rate below was computed for this CR; none is inherited or
estimated.

| measure | value | note |
|---|---|---|
| assembled prompt size | 12,479 / **13,443** / 14,966 chars (min/median/max) | CR143's 13,899 single sample sits inside this |
| length guide vs measured | guide 3–5 sentences · median **5** · over budget **4/18 = 22%** | the guide/format conflict is DEF236, owned by CR145 |
| bullet usage | **6/18 = 33%** | `_PROSE_FORMAT` mandates bullets; DEF236 |
| stance envelope emitted | **18/18** · headline nulled for over-length **1/18** | healthy — see Rejected #1 |
| stance value | **`against` 18/18** (Bull: `for` 18/18) | role-determined; carries no information |
| conviction | high 10 / medium 8 / **low 0** | a Bear that is unconvinced never says so |
| numbers stated that appear nowhere in its own prompt | **18 of 351 tokens = 5.1%** | CR143's 6.0% used the narrower fact-sheet∪transcript denominator |
| turns carrying ≥1 unsourced **downside magnitude** | **8/18 = 44%** | e.g. *"a mean EV/EBITDA of 25x… could contract ~77%"*, *"a historical norm of 30x implies a -40% downside"* |
| fact sheets rendering market cap | **0/18** — while **17/18** carry *"Avoid microcaps (< $500M market cap)"* | |
| portfolio blocks rendering a stop | **0/18**, across **31** open-position rows — while **18/18** state a Total open-risk cap | |
| prompts carrying a Decision Journal block | **3/18** · at the 5-entry cap **2 of those 3** · block cited by the agent **2 of 3** | |
| turns disclosing "no journal history for this ticker" when none was supplied | **0 of 15** | the role text asks for exactly this |
| price move compared directly against the portfolio drawdown cap | **3/18 = 17%** | e.g. *"a -32% downside, which violates your 30% portfolio drawdown cap"* — at the enforced 3% size it contributes **0.96 pt of 30** |
| turns engaging the Bull's counter explicitly | **4/18 = 22%** | the instruction appears twice (base file + `_bear_block`) |
| turns delivering the invalidator `_LENGTH_GUIDE` asks for | **3/18 = 17%** | the base role file never asks for one at all |
| range-label conflation (50-day number called "52-week") | **1/18** | on the one prompt still using the pre-DEF228 *"Recent range"* label |

**One arithmetic error worth naming on its own.** On SNDK the Bear wrote "the stock has collapsed
**83%** from its high of **$2354.39**" and headlined the turn "83% range decay". The actual
decline from that high is **−48.0%** ($1,224.51 ÷ $2,354.39). The 83% is the complement of DEF228's
"last close $1224.51 (17% of that range)" — the agent read a range-position percentage as a
drawdown percentage. Both numbers were on the sheet; the one the Bear actually wanted (% below the
high) was not, so it manufactured it from the one that was.

**Epoch caveat.** The 18 convenes straddle a promotion: the 13:33 run renders *"Recent range"*, the
19:26 run renders *"50-day range … (35% of that range)"* (DEF228). None of the 18 carries the
two-basis P/E line — DEF233's `pe_line` is on `main` and in
[`assembled/room/bear_researcher.txt`](../CR143_agent_prompt_audit/assembled/room/bear_researcher.txt)
but was not deployed for this epoch. Post-promotion re-measurement must re-derive, not diff.

## Scope — four tiers, ordered by cost

### Tier A — delete one number, render six that already exist (no new provider, no new fetch)

| # | change, and the supplier evidence for it |
|---|---|
| A1 | **Delete `-25%` from the style example** (`content/agents/bear_researcher.md:27`). Replace with: quantify only from the block; if no impact number exists, say so. Evidence: 22/811 verdicts carry it, 12 attributed to the Bear. |
| A2 | **Render market cap.** `marketCap` read at `fundamentals.py:248`, used only as the FCF-yield denominator, never rendered. Makes *"Avoid microcaps (< $500M)"* checkable for the first time. **Shared with CR145 Tier A** — whichever lands first satisfies both. |
| A3 | **Render % below the 52-week high and % above the 52-week low.** Pure arithmetic on `profile['base_price']` and the `week52`-gated `low`/`high` already on the sheet. This is the number the Bear reaches for and gets wrong (SNDK, −48% written as 83%), and the one legal, sourced downside anchor available today. |
| A4 | **Render the run's total open risk.** `sim_engine.existing_open_risk_pct(user_id, portfolio_value=…, quotes=…)` is a **public** method returning the exact sum the mandate's cap is enforced against (`sim_engine.py:491-501, 517-526`); `_build_sim_holdings_block` (`room_runner.py:735-771`) already holds both arguments (`total`, `marks`) and renders only weight + unrealised. Per-position stop distance is on the row (`SimTrade.stop`, `sim_engine.py:109`). Same *shown == enforced* principle as CR101's `[[CAP]]`. |
| A5 | **Disclose the journal window.** `journal_context.fetch_recent_journal_entries` calls `list_for_user(…, limit=5)` and destructures `entries, _, _` — **discarding the total count and the retention days the store already returns** (`journal_store.py:193, 220`). The cap bound in 2 of the 3 prompts that had a block. Floor Pass retention is 30 days (`journal_store.py:45`); the AMD sample's oldest entry was 28 days old. |
| A6 | **Say when there is no history, structurally.** `build_journal_context_block` returns `None` on empty, on `user_id is None`, **and on a store exception** (`journal_context.py:52-57`), and the prompt then contains nothing at all. The role text tells the agent to *"say so rather than inventing a past decision"* — 0 of 15 did. Emit a one-line block for the empty case, the way CR098 emits `live_data_notice` with the model out of the loop, rather than trusting the instruction. Distinguish "no entries" from "lookup failed" (CR040). |
| A7 | **Give the RESEARCHERS phase the drawdown-contribution arithmetic.** `_drawdown_snapshot_line(mandate, proposal)` injects the derived `P×S/100` figure only when `phase in ("RISK","VERDICT")` (`room_prompts.py:400`) — so the agent *whose job is quantifying downside against caps* is the one denied the computed figure, and 3/18 of its turns then compare a raw price move against the portfolio cap. No Trader proposal exists yet at RESEARCHERS time, but the enforced single-name cap is already printed to this same agent by `researcher_cap_note` (`room_prompts.py:416-428`) and `drawdown_contribution` already exists — a reference contribution at the cap size is computable with what is in hand. |

A2/A4 change a block **every agent sees**, so they carry CR145 Tier B's blast radius, not Tier A's
independence; A4's render line also belongs to the per-agent visibility matrix CR145 Tier C will own.
A1, A3, A5, A6 are Bear-local and independent.

### Tier B — free from fetches already made (one unread dict, one candle series)

The Bear's canonical evidence classes are volatility ("how far does this thing actually move?") and
positioning ("who is short?"). Both are reachable without a new provider **and without a new call**:

- **Beta, short interest, ownership.** `fetch_live_fundamentals` consumes ~15 keys of the
  `yf.Ticker(t).info` dict it already fetches (`fundamentals.py:141`). Verified unread anywhere in
  `backend/app/`: `beta`, `sharesShort`, `shortRatio`, `shortPercentOfFloat`, `heldPercentInsiders`,
  `heldPercentInstitutions`, `floatShares`, `averageVolume`. (The `beta` in
  `trading_math/portfolio_risk.py` is CR136's *portfolio* beta from a covariance matrix — a different
  quantity, not this one.)
- **ATR / realised volatility.** `compute_technicals` already pulls `_HISTORY_PERIOD = "3m"` of OHLCV
  (~65 candles, highs/lows/closes/volumes all in hand, `technicals.py:88-108`) and that pull is cached
  (`CachingProvider._history_cache`, 60 s). No `atr` or true-range computation exists anywhere in the
  backend today. `annualize_vol` already exists (`trading_math/portfolio_risk.py:524`).

Conditions, all mandatory:

1. Each new field gets its own `field_state` entry — a gap renders "not available", never a blank
   (CR104/DEF123).
2. **Short interest is exchange-reported twice-monthly.** It ships with a *"reported as of, not live"*
   label or it does not ship. A stale figure under the LIVE header is DEF123 again.
3. This tier adds **no** fetch, so CR145 Tier D's cache blocker does not bind here — but
   `fundamentals.py` still has **zero caching of any kind** (verified: no cache in the module; quotes,
   history, news and earnings all have TTLs). Nothing in this tier may become the excuse to add a
   second fundamentals call.

### Tier C — decisions, not code

- **The short clause is dead, and one branch of it is a lie.** `content/agents/bear_researcher.md:30`
  says *"If short selling is allowed, propose specific short structure (size, stop, hedge)."* Verified
  end-to-end: **`sim_engine` has no concept of a short.** The word appears nowhere in the module; a
  SELL beyond the held quantity is rejected with `blocked_by="long_only"` **unconditionally**, not
  gated on `mandate.compliance.long_only` (`sim_engine.py:671-680, 862-870`), and the PM verdict schema
  is a long setup (size/entry/stop/target) whose R:R helper returns None for anything else. So no short
  is executable for any user under any mandate. Yet `overlay_generator._bear_block` still emits
  *"Explicit short recommendations allowed, sized to risk_score"* when `long_only` is false, and
  `concierge_engine._parse_constraints` sets `long_only` **false** whenever the onboarding answer
  doesn't contain "long only"/"no short" (`concierge_engine.py:396`) — the default is `True` in the
  schema but the interview can turn it off by omission. **Decision needed:** delete both short paths
  (base file + overlay else-branch), or state the product rule that shorts are out of scope forever.
  Do not leave an instruction whose only possible outcome is an unexecutable recommendation.
  **Test trap:** `test_overlay_generator.py::test_long_only_off_allows_shorts_in_bear` asserts
  `"Explicit short recommendations allowed" in overlay or "shorts" in overlay.lower()`. A replacement
  containing the word "shorts" keeps it **green while asserting nothing** — precisely the CR105
  Amendment-1 trap. The test must be rewritten to the new contract in the same commit.
- **The stance field is role-determined for both researchers.** 18/18 `against`, 18/18 `for`. The comb
  renders a stance hex for the Bear that can only ever say one thing, next to hexes where it is a
  judgement. Conviction (10 high / 8 medium / 0 low) and the 32-char headline are the fields that
  actually carry signal. Either the Bear's envelope should drop `STANCE` (the format already supports
  `STANCE: none`) or the client should stop rendering it as a verdict for the two researchers.
  Design call, not a defect.
- **The invalidator has no owner.** `_LENGTH_GUIDE[BEAR_RESEARCHER]` asks for *"risk + quantification +
  invalidator"*; the base role file's `## Output style` never mentions an invalidator — it asks for
  *"anticipate the Bull's counter"* instead. Delivered in 3/18 turns. Two prompt layers ask for two
  different third elements; pick one. (The *mechanism* by which the third element gets dropped is the
  three-way format conflict — DEF236, owned by CR145. Which element is being asked for is this CR's.)

### Tier D — not available; explicitly not scoped

| gap | why it stays out |
|---|---|
| Peer / sector valuation baseline | `fundamentals.py:263-268` already says so: yfinance has no peer-basket multiple; sector is a label. Needs a peer mapping — a dataset, not a feed. This is the source of the corpus's *"historical norm of 30x"* and *"mean EV/EBITDA of 25x"* inventions; until it exists, the honest fix is A1 + a "no peer baseline is available" disclosure, not a fabricated anchor. |
| Segment / geographic revenue | No yfinance surface. SEC EDGAR or equivalent — a separate provider decision, same conclusion as CR145. |
| Options-implied move, put/call ratio | No options endpoint is used anywhere in the backend. |
| Insider-transaction history | Not on Yahoo's free surface (aggregate `heldPercentInsiders` in Tier B is a different, much weaker fact and must not be narrated as insider *activity*). |

## Verified findings

1. **The `-25%` example reaches the permanent record.** 22 of 811 real PM verdicts carry it, 12
   attributing it to the Bear; it is the most frequent downside magnitude in the entire historical
   verdict population. Supplier check: no scenario-impact magnitude exists in any fact sheet.
   *Fix: A1 + A3 + A7.*
2. **44% of Bear turns (8/18) state a downside magnitude sourced from nothing in their own prompt** —
   and the arithmetic is usually right while the *anchor* is invented ("revert to a mean EV/EBITDA of
   25x" → "~77%" is correct division on a fabricated 25x). Overall 5.1% of the Bear's numeric tokens
   (18/351) appear nowhere in its prompt.
3. **A range-position figure was published as a drawdown.** SNDK: *"collapsed 83% from its high"*,
   actual −48.0%, and it became the stance headline the comb renders. *Fix: A3.*
4. **17% of turns (3/18) compare a single-name price move directly against the portfolio drawdown
   cap**, the DEF066 error, despite the DEF066 clarification paragraph being present in all 18
   prompts. The one turn that got it right (SNDK, *"for a max-sized 3.0% position, this contributes
   0.555% to portfolio drawdown"*) did the exact arithmetic DEF066 injects for the RISK/VERDICT phases
   and withholds from this one. *Fix: A7.* Prompt instructions are not controls — CLAUDE.md.
5. **The open-risk cap is unverifiable by construction.** 18/18 prompts state it; 0/18 portfolio
   blocks render a stop, across 31 open-position rows. The figure itself is already computed and
   already public (`existing_open_risk_pct`). *Fix: A4.* Disclosure caveat: `_risk_limit_context`
   skips rows where `stop is None`, so the sum can understate — the render must say what it covers.
6. **The microcap rule is unfollowable.** 17/18 prompts carry it as a HARD compliance constraint;
   0/18 fact sheets carry a market cap; the same prompt forbids recalling one. *Fix: A2.* Honest
   limit: the corpus's one true microcap (SNOA, $1.44, −45.3% FCF yield) belonged to the one user
   **without** the rule, so the harm is structural, not observed at n=18.
7. **The journal is real but silently windowed.** Present in 3/18 prompts (per-ticker, as designed),
   at the 5-entry cap in 2 of those 3, with the total count and retention days already returned by
   the store and discarded by the caller. Absence is rendered as nothing at all — and an exception
   produces byte-identical silence. 0 of 15 history-free turns said so. *Fix: A5 + A6.*
8. **The short-structure instruction has no legal exit path in any configuration** — verified down to
   `sim_engine`, not merely to the mandate flag. *Fix: Tier C.*

## Rejected claims and why

Both reviews' remaining claims were checked and **do not become scope**:

1. **REJECTED — "the stance envelope / format collapse loses the Bear's stance."** Replaying the real
   `parse_stance_envelope` logic over all 18 stored turns: **18/18 parse a valid stance**, 0 envelope
   remnants leak into the prose, 1/18 headline nulled for exceeding the 32-char cap (TSLA, 33 chars —
   the guard behaving as designed). The blind review's failure mode #3 (missing `[STANCE:]` line) did
   not occur once. Several turns omit the closing `]`; the field regexes are line-terminated and cost
   nothing for it, exactly as their comment claims.
2. **REJECTED — "the Bear's levels can be mis-parsed by `_LEVEL_PATTERNS`."** `_verify_and_annotate_geometry`
   runs unconditionally on **every** agent's text (`room_runner.py:3469`), so the concern was
   plausible. Measured: `entry` matches 1/18 turns, `target` 3/18, `stop` **0/18**, the full triple
   required to trigger annotation **0/18**. The specific case I expected to fire — *"prior AMD
   positions hit stop losses around $502.59"* — does **not** match: the pattern allows 15 digit-free
   characters after the label and this phrase has 17. DEF235 is a Trader problem; it is not a Bear
   problem, and no Bear-side change is warranted. *(This is the CR105 lesson landing: the fix I would
   have written from the prompt alone would have been solving a non-problem.)*
3. **REJECTED — "the Bear leaks short recommendations under a long-only mandate."** Blind review
   failure mode #1. 18/18 prompts carry the long-only overlay, 0 carry the short-allowed branch, and
   0/18 turns propose a short structure. The one regex hit was *"hedge with"* inside a legitimate
   avoid framing. The clause is **dead text**, not an active leak — which is why it lands in Tier C as
   a decision, not in Tier A as a fix.
4. **REJECTED — "the Bear's directional levels are unverified and drift."** `_annotate_direction_against_price`
   (DEF231→DEF234) is wired **only** to the PM's `verdict.reason` (`room_runner.py:3242`), so the
   Bear's *"wait for a pullback toward $424.03"* is indeed unchecked. Measured anyway: 9 waiting-level
   mentions across 18 turns, **0 genuinely on the wrong side of the reference price** (the 2 flagged
   by a naive test were *"wait for a clear break above $4.06"* — correct by construction). Extending
   DEF231's machinery to a tenth agent buys nothing measurable and costs the four-round false-positive
   history that defect already has.
5. **REJECTED — "the range-label conflation is a systemic defect."** The kimi review's defect #1 is
   real but rare: **1/18 turns**, and on the single prompt still carrying the pre-DEF228 *"Recent
   range"* label rather than *"50-day range … (X% of that range)"*. n=18 cannot attribute that to the
   label change; it is enough to say the observed rate does not justify a prompt edit. Re-measure
   post-promotion, when all runs carry the DEF228 wording.
6. **REJECTED as this CR's scope — the three-way format conflict, `LearningStyle.QUICK`'s "tabular"
   vs "no tables", and the shared per-agent fact sheet.** Real, measured here (22% over budget, 33%
   bullet usage, 17% invalidator delivery), and owned by
   [CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md)
   Tier B/C as DEF236 / DEF235. This CR cross-references them and does not re-litigate them.
7. **REJECTED — "the duplicated max-drawdown paragraph and the sizing-ceiling note are noise to
   delete."** Both are cross-cutting prompt-assembly text (`_drawdown_snapshot_line`,
   `researcher_cap_note`), not Bear-local, and the sizing note exists because CR055 measured
   researchers proposing ~4× the enforced cap. Deleting text on a blind reviewer's aesthetic judgement
   is how CR055's defect returns. The Bear-specific ask here is the *opposite* — A7 adds arithmetic to
   that region rather than removing prose from it.
8. **NOT VERIFIED — forward P/E.** The kimi review lists it as a provider gap for AMD. On this epoch
   the question does not arise: **0/18 corpus fact sheets carry any forward P/E**, because DEF233's
   two-basis `pe_line` had not been promoted when the epoch was recorded (it is present in
   `assembled/room/bear_researcher.txt` from current `main`). Whether AMD specifically returns a
   `forwardPE` from the provider is unmeasured here and is DEF233's question, not this CR's.

## Acceptance

Every item is measurable and re-measurable against the same corpus queries used above, on a fresh
export after promotion. A prompt edit whose effect is not re-measured is the CR105 Amendment-1 trap.

1. **A1:** `-25%` appears in no agent prompt file. Re-export the PM verdict corpus after ≥30 convenes
   and re-run the frequency count: `-25%` must no longer be the modal downside magnitude, and no
   verdict may attribute a downside percentage to the Bear that is absent from that run's fact sheet.
2. **A2/A3:** market cap, % below the 52-week high and % above the 52-week low render with
   `field_state` provenance. The microcap constraint is checkable from the sheet alone. Bear turns
   stating a "% from the high" match the sheet's own figure — the SNDK 83%-vs-48% class is a regression.
3. **A4:** the fact sheet or portfolio block carries the run's total open risk, equal to
   `existing_open_risk_pct` for that user (asserted in a unit test against the same value the safety
   floor enforces — shown == enforced), with an explicit note covering stop-less rows.
4. **A5/A6:** when the 5-entry cap or the plan retention window binds, the journal block says so with
   the real total; when there is no history the block is **present** and says so; a store exception
   renders a distinguishable "lookup unavailable" line (CR040). Re-measure the 0-of-15 disclosure rate.
5. **A7:** RESEARCHERS-phase prompts carry a reference drawdown-contribution figure at the enforced
   cap size. Re-measure the direct move-vs-cap comparison rate; the baseline is **3/18 (17%)**.
6. **Tier B (if taken):** beta / realised volatility / short interest render with per-field
   provenance and a *reported-as-of* label on short interest; **no new network call appears on the
   convene path** — assert the fundamentals fetch count per convene is unchanged.
7. **Tier C:** whichever way the short question is ruled, `test_long_only_off_allows_shorts_in_bear`
   asserts the *new* contract and fails if the old text returns. A green test whose assertion is
   satisfied by the word "shorts" appearing anywhere is not acceptance.
8. **Unsourced-number rate:** re-measure on ≥30 convenes. Baselines to beat: **5.1%** of numeric
   tokens (18/351) and **44%** of turns carrying an unsourced downside magnitude.
9. `pytest backend/tests/unit/ -q` green throughout, including `test_prompt_data_parity.py` and
   `test_p16_prose_pattern_corpus_parity.py` (a refreshed PM verdict fixture is a deliberate act with
   `_EXPECTED` updated in the same commit — see that file's docstring).

## Out of scope

- Everything in **Tier D** — peer/sector baselines, segment revenue, options data, insider
  transactions. Each needs a new provider or a new dataset; each is a separate decision. The existing
  "not available" disclosures for these stay correct and must not be quietly dropped.
- DEF235, DEF236, `LearningStyle.QUICK`, and the per-agent fact sheet — CR145.
- The Bull Researcher's symmetric issues (its own `for` 18/18 stance, its own falsifier element). Same
  file pattern, different evidence; one CR per agent.
- Extending DEF231's directional-coherence check beyond the PM — see Rejected #4.

## Notes

A1 is one line and is the highest-value change in this CR: it removes a number that is demonstrably in
the permanent record of 22 real decisions. A3 is the number that should replace it — the Bear's most
common quantitative claim, currently manufactured. A5/A6/A7 are each a handful of lines against data
the process already has in memory. A2/A4 are the two that touch the shared block and should ride with
CR145 rather than race it. Tier B is genuinely cheap but adds field-availability variance to a sheet
whose provenance discipline is hard-won — take it only after Tier A is measured. Tier C needs Saiful
before any code.
