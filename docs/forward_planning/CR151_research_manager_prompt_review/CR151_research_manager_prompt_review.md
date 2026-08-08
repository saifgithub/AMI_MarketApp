# CR151 — Give the adjudicator the arithmetic it adjudicates, and one output shape instead of three

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.
**Source:** CR143 Phase 1/3b plus two independent reviews of the Research Manager — a blind
prompt-coherence audit ([`external_review/room/research_manager.md`](../CR143_agent_prompt_audit/external_review/room/research_manager.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/research_manager_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/research_manager_data_sufficiency.md)).

Every figure below was re-derived in this session against the CR143 corpus
(`corpus/llm_audit_2026-08-07-epoch.json`, 216 turns with verbatim `system_prompt`, and
`corpus/room_runs_2026-08-07-epoch.json`, 18 convenes). **n = 18 Research Manager turns**, epoch
2026-08-07, unless stated otherwise. Both reviews were treated as hypotheses; five of their claims
are rejected below on the supplier and parser checks.

## Why

The Research Manager is the **hinge of the Room**, and that is measurable rather than rhetorical. It
is the only agent in the SYNTHESIS phase, it runs sequentially against the live transcript, and its
turn reaches the prompt of the Trader, all three Risk Debators and the PM in **18 of 18** convenes.
The Trader names it back in **8 of 18** replies; the PM names it in **9 of 18**; and the PM's
`verdict.reason` — the string CR106 renders to the user as the decision's justification — names it
in **9 of 18** (*"The Research Manager correctly identified…"*, *"I align with the Research
Manager…"*). Anything wrong in this turn is wrong five prompts downstream and, half the time, in the
sentence the user reads as the verdict.

### 1. The adjudicator cannot check the numbers it adjudicates, so it launders them

The prompt asks for *"asymmetry numbers"* (`_LENGTH_GUIDE`, `room_prompts.py:74`). It supplies none.
**6 of 18** turns produce one anyway. Checked against each turn's own fact sheet:

| run | what the RM stated | the truth from its own prompt | where the number came from |
|---|---|---|---|
| GRAB 19:18 | *"the **44%** upside to the Street target of $5.89"* | **+60.5%** (ref $3.67) | the **Bull's** number, echoed by the Bear |
| AMD 19:26 | *"the **30%** upside to the $608.23 target"* | **+26.7%** (ref $480.23) | the **Bull's** number |
| NVDA 19:27 | *"the 35.8% upside toward $302.83"* | +35.9% | correct |
| SNDK 19:30 | *"an 18.5% downside"* to the $998.19 50-day low | −18.5% | correct |
| ANET 19:28 | *"a re-rating to a 30x P/E would trigger a **−40%** downside"* | unverifiable — a hypothesis, not a distance | Bear's scenario |
| NBIS 19:30 | *"the **30%** drawdown cap on the table … exposes you to **30%** downside risk"* | category error — that is the **portfolio-level** cap | the mandate line that warns against exactly this (DEF066) |

Add the AMD 13:33 sample both reviews were written from, where the error is qualitative rather than
numeric: *"the **$494.31** price sits exactly between the **$424.03** support and **$608.23** target,
creating a symmetric risk-reward that offers no edge."* It is not symmetric — **+23.0%** against
**−14.2%**, and the midpoint of that range is **$516.13**. The `neutral` stance the Room then
inherited rests on a false premise, with the Bull's own correct **+22.9%** sitting in the same
prompt.

**The GRAB case is the class in its purest form.** The Bull invented 44%, the Bear repeated it, and
the Research Manager promoted it to *"Both acknowledge … the **44%** upside"* — a point of
agreement. That is the one rhetorical move that makes an unchecked number look verified, and it is
this agent's job description. Nothing in the code checks it: `_verify_and_annotate_geometry` fires on
**0 of 18** RM turns (it needs a full entry/stop/target triple; the RM never states one), and
`_annotate_direction_against_price` is wired to `verdict.reason` only (`room_runner.py:3299`).
Across all 18 convenes there are exactly **2** `[AMI …]` annotations, both on the neutral_debator.

**This is not a fabrication problem.** Of **412** numeric tokens across the 18 turns, **1** appears
nowhere in its own prompt — **0.2%**, which *corrects the 1.0% carried in this CR's stub*. The
grounding directive holds. What the model cannot do is arithmetic, and it is asked for arithmetic
it was never given the result of.

### 2. Three prompt layers give this agent three output shapes, and the wrong one wins 72% of the time

All three ship in **18 of 18** prompts:

| layer | what it says |
|---|---|
| `content/agents/research_manager.md:21-27` | *"## Output structure (in 1-on-1) … **In the Room, follow the format instruction appended at the end of your prompt instead.** 1. Points of agreement. 2. Points of dispute. 3. Recommended stance."* |
| `overlay_generator.py:385` (`_research_manager_block`) | *"- 3-part output: (1) Points of agreement, (2) Points of dispute, (3) Recommended stance."* — **no surface carve-out, no deferral, imperative** |
| `room_prompts.py:210` (`_PROSE_FORMAT`) | *"lead with a one-sentence thesis, then short bullet points"* |

Measured: the 1-on-1 three-part structure appears in the Room in **13 of 18** turns (**72%**);
bold labels used as headings against *"no headings"* in **11 of 18**; bullet points in **7 of 18**
(**39%**, matching CR143's baseline).

**Both reviews blamed the wrong layer.** The blind review's CUT list and the data-sufficiency
review's slice item #5 both target the base prompt's 1-on-1 section — but that section already
carries the correct carve-out and points at the Room format. The instruction that actually lands is
the overlay's, which carries no carve-out at all and sits ~50 lines closer to the data. **Cutting
only the base-prompt section leaves the operative instruction in place.** No test asserts on either
string (`grep "3-part output\|Points of agreement" tests/` → one unrelated fixture line), so the
blast radius is small — but the effect must be re-measured, not assumed.

### 3. What the guide asks for is largely unsupplied, and correspondingly largely unmet

`_LENGTH_GUIDE` names three deliverables. Measured:

| asked for | delivered | supplied by the prompt? |
|---|---|---|
| asymmetry numbers | 6/18 (2 of the 6 wrong, 1 a category error) | **no** |
| lean | 18/18 — the stance envelope parsed in every turn | yes |
| size implication | 4/18 | the single-name cap yes (`researcher_cap_note`, 18/18); no risk budget, no sector weights |

The sentence-count half of the guide (4–6 vs a measured **median 9**, **61%** over) is DEF236's and
belongs to CR145. The *content* half is this agent's and is scoped here.

## Scope — four tiers, ordered by cost

### Tier A — render the asymmetry, from two numbers already on the sheet

One derived line in `_format_profile`, anchored on a **named** price, each half independently gated
on its own `field_state` entry per CR104:

> *From the last close **$480.23**: **+26.7%** to the consensus target **$608.23**, **−11.7%** to the
> 50-day range low **$424.03**. AMI's arithmetic on the two lines above — the Street's target is not
> a trade target and the range low is not a stop.*

No new provider, no new fetch, no new field: reference price / last close, analyst target and the
50-day range low are all already rendered and already labelled `(LIVE)`. The precedent is exact —
DEF228 added the range-position figure on the reasoning *"this is arithmetic on two numbers already
on the sheet — it asserts nothing new"* (`room_prompts.py:706-708`), for the same reason: an agent
joined two rendered numbers wrongly and the whole Room adopted it.

Two things this tier must get right or not ship:

- **One anchor, named in the line.** The sheet already carries two prices (`Reference price` from
  fundamentals, `last close` from technicals). Deriving one half from each is how DEF228 happened.
  Anchor both halves on `last_close` when technicals are live, on `base_price` otherwise, and say
  which.
- **`_format_profile` is shared by all 12 agents** (`_format_profile(profile)` takes no `agent_id`).
  That is CR145 Tier C's ground, and this line lands in every prompt. That is the right call here
  rather than a SYNTHESIS-only gate: **the errors originate upstream at the Bull and Bear** — the RM
  inherited every wrong figure in the table above — so the fix belongs where they read too. Say so
  in CR145 Tier C's matrix rather than letting the two decisions drift.

### Tier B — cut the 3-part instruction where it actually lives

`overlay_generator.py:385`. `_research_manager_block` serves both surfaces, so the line cannot simply
be deleted; the cheap form is to reword it to name the *content* the synthesis owes (what the two
sides share, where they diverge, the lean) without mandating a three-section layout, leaving the
appended `_PROSE_FORMAT` as the only shape instruction in the Room. Threading a surface flag is the
expensive alternative and is not justified by the measurement.

**Staged deliberately:** change the overlay line only, re-measure the 72% leak, and cut the base
prompt's 1-on-1 section (`research_manager.md:21-27`) only if it does not fall. Cutting both at once
makes the result unattributable, and the 1-on-1 section is genuinely used on the surface it names.

### Tier C — stance vocabulary that a long-only mandate can survive

`research_manager.md:27` is the only place in the entire assembled prompt that offers *"lean short"*
as a stance, in a prompt that also carries *"LONG-ONLY. No short recommendations."* in 18 of 18.
Measured leak: **1 of 18** — KTOS 20:14 opened its recommended stance with **"LEAN SHORT (via
AVOID)"**, visible in the transcript and carried into the Trader, Risk and PM prompts. Not a
compliance breach (it did say AVOID, and **0 of 18** turns propose a short) but it is forbidden
vocabulary being emitted because a prompt layer supplies it. Replace with the envelope's own
`for / against / neutral` plus long-only-safe wording. One line, same file as Tier B.

Also here, same cost bracket: *"PASS — nothing fits the user's mandate today"* is specified as the
output for *"if both Bull and Bear advocate trades that violate compliance"*, and appears in **5 of
18** replies as a generic pass. Nothing parses it — the PM's verdict is independent — so this is a
copy fix, not a control.

### Tier D — sector weights for the agent asked for a size implication (decision, not code)

`sector_weights` is computed every run (`room_runner.py:302-305`) and rendered by
`_format_sector_allocation`, gated to the PORTFOLIO_MANAGER (`room_prompts.py:454`). The RM carries
the **20% sector-concentration cap** in its mandate (18/18) and gets **0/18** sector weights, so the
one cap that could bind its size implication is invisible to it. The safety floor does hard-block a
BUY that breaches it (`safety_floor.py:389-393`).

**Measured yield in this epoch: zero.** 15 of 18 verdicts were PASS; the 3 APPROVEs sized at
2.0/3.0/4.0%, and no verdict was blocked or narrated on the sector cap. The AMD sample makes the
scenario plausible (NVDA 9.4% + HPQ 6.3%, both Technology, plus a 10% AMD add) but it did not happen
in 18 convenes. **Do not ship this on the strength of a hypothetical**; it is a one-condition change
whenever the re-measure on ≥30 convenes shows a bind, and it belongs with CR145 Tier C's visibility
matrix rather than as a standalone gate flip.

## What this CR REJECTS, and why

1. **"Wire `trade_asymmetry` into the RM prompt"** (data-sufficiency review §4 row 1, slice item #1)
   — **rejected as specified.** `trade_asymmetry` *is* computed every run
   (`room_runner.py:2980`), but on `ctx.trader_entry / trader_stop / trader_target`, which are set
   once at `room_runner.py:2967-2969` to `base`, `base × 0.94`, `base × 1.13` and **never updated
   from the Trader's actual output**. Its result is therefore **13.0% upside vs 6.0% downside for
   every ticker in every run** — a constant. `trading_math/trade.py`'s own module docstring names
   the defect this would recreate: *"a Research Manager stating a fixed '28% upside vs 18% downside'
   for every ticker"* is precisely what CR046 M08 was filed to kill. Tier A computes the asymmetry
   from live per-ticker fields instead; the two are not the same change.

2. **"Extend the deterministic reference position to SYNTHESIS"** (slice item #1's second half) —
   **rejected**, same root. `_drawdown_snapshot_line`'s `Reference position` clause is fed the same
   invariant geometry. Extending the gate at `room_prompts.py:400` would hand the RM a
   drawdown-contribution figure derived from a −6% stop nobody proposed, labelled as a reference and
   read as a measurement. DEF066's clarification text (already in 18/18 prompts) is the part that
   earns its place; the numbers behind it do not, at this phase.

3. **"Un-gate the Decision Journal for the RM"** (slice item #2) — **deferred, yield measured at
   1/18.** The block does render on Alpha (3 of 18 Bull prompts, 3 of 18 Bear). Exactly one Bear turn
   cited it to the RM (AMD 13:33, *"prior AMD positions hit stop losses around $502.59"*) — and the
   claim was **true**: the block in that Bear's prompt reads *"Stop hit at $502.59"* twice. So the
   measured cost of the gap in this epoch is one unverifiable-but-correct claim, against ~900 chars
   added to a prompt already at a 14,252-char median. Revisit on the ≥30-convene re-measure.

4. **"Delete the duplicate mandate snapshot to pay for the additions in tokens"** (gap #6, slice item
   #4) — **rejected on both halves.** (a) It is not pure duplication: the snapshot's `long_only`
   line carries the CR055 clarification *"It does NOT forbid buying, adding to, or holding a name"*,
   which the mandate block above it does not. The drawdown line genuinely is near-verbatim
   duplication and could go, but that is a whole-Room edit, not this agent's. (b) The token argument
   is dead: **0 of 18** RM turns were truncated (no `_TRUNCATION_MARK` anywhere in 216 transcript
   turns), and the longest RM turn in the epoch is **2,414 chars ≈ 56%** of its 900-token budget.
   See the correction below.

5. **"The stance line's missing `]` is a violation worth fixing"** (review §8 item 4) — **rejected as
   a non-defect.** **7 of 18** RM first lines omit the closing bracket, and **18 of 18** parsed:
   stance, conviction and headline all extracted, 17 headlines non-null, 1 nulled for exceeding 32
   chars. DEF147 split find-and-strip from parse precisely so a missing terminator costs nothing
   (`room_runner.py:1755-1760`). The guard is working; touching it is the CR105 Amendment-1 trap.

6. **"The RM is told it is first to speak / has no Bull and Bear to adjudicate"** (blind review's
   core hypothesis, three of its five contradictions and two of its unfollowables) — **killed on the
   corpus, not just in code.** `[bull_researcher]` and `[bear_researcher]` are present in **18 of
   18** RM prompts, along with all four analysts; *"(You are first to speak.)"* appears in **0 of
   18**. `_format_transcript` renders it only for an empty transcript and the RM always follows a
   sequential RESEARCHERS phase (`room_runner.py:157-158`, `3606-3617`). The RM names the Bull or
   Bear in 15 of 18 replies and fabricates no attribution.

7. **"Extend DEF231's directional check to the RM"** — **rejected on measurement.** Running
   `_direction_contradictions` over all 18 RM turns against each run's own levels and reference
   close: **0 fires**. The RM does issue directional triggers (a `break/reclaim/pull back to $X`
   phrase in 8 of 18, which is real scope bleed into the Trader's lane) but never from the wrong
   side of the price in this epoch.

## Acceptance

- **Tier A** — every Room prompt renders the asymmetry line, both halves anchored on one named
  price, each half omitted independently when its input is not `live`. `pytest backend/tests/unit/`
  green, including `test_prompt_data_parity.py` and `test_cr104_no_fabricated_numeric_reaches_room_prompt.py`.
- **Tier A, the measurement that matters** — re-run the table in §1 on ≥30 convenes: of the RM turns
  that state an upside/downside figure, the share contradicted by their own fact sheet must fall from
  **2 of 6**. A tier that does not move that number did not work, whatever the prompt now says.
- **Tier B** — the 1-on-1 three-part structure falls materially from **13/18 (72%)**; bullet usage
  rises from **7/18 (39%)**; bold-label pseudo-headings fall from **11/18**. Measured
  post-promotion, on the same script, ≥30 convenes.
- **Tier C** — *"lean short"* at **0/N** (from 1/18); still **0** proposed shorts; stance envelope
  still parses at **18/18** with no regression in null-stance rate (currently 0% for this agent
  against 5.1% Room-wide).
- **Nothing regresses downstream** — the RM's turn still reaches the Trader/Risk/PM prompt in N/N,
  and truncation stays at **0**. If a re-measure shows the truncation class returning, that is a
  DEF125 reopening, not a CR151 acceptance failure.
- Every rate above is epoch-scoped and stated with its n. A prompt edit whose effect is not
  re-measured is the CR105 Amendment-1 trap.

## Notes — corrections, and what could not be verified

**Corrections to figures this CR was handed.**

- *"Numbers stated that are in neither the fact sheet nor the transcript: 1.0%"* → **0.2%** (1 of 412
  numeric tokens over 18 turns).
- *"DEF125's truncation class lived here"* → it **lived** here (66.1% of 884 turns over 30 days
  pre-fix, `room_prompts.py:90`) and is **dead now**: **0 of 18** RM turns truncated, **0 of 216**
  turns across all 12 agents in the epoch. The RM is still the longest prose agent by median (1,559
  chars, next is bull_researcher at 1,754 max-heavy, then bear at 1,197) but its worst turn uses 56%
  of its 900-token budget. Anything in this CR that was justified by "the RM is the truncation-worst
  agent" — chiefly the token-budget argument for cutting blocks — has no current basis.
- Median 9 sentences, 61% over budget, 39% bullets, ~14.2k prompt chars: all **confirmed**
  (median 9.0, 11/18 over 6, 7/18 with bullets, median 14,252 chars).

**A caveat about the sample both reviews read.** `real_samples/research_manager.prompt.txt` is one of
only **2 of 18** epoch prompts that predate DEF228 — it renders *"Recent range: $424.03–$584.73"*
where the other 16 render *"50-day range: $424.03–$584.73, last close $480.23 (35% of that range)"*.
The false-symmetry claim in §1's last paragraph is therefore argued against a fact sheet that no
longer ships. DEF228's range-position figure partially closes that specific hole already — but only
partially: it gives the position inside the 50-day range and says nothing about the distance to the
consensus target, which is where 2 of the 2 wrong figures in §1 live. Tier A is still warranted; its
motivating example is weaker than it looks.

**Could not be verified.**

- Whether the sector cap would ever bind an RM size implication in practice — 0 observed in 18
  convenes (Tier D).
- Whether Tier B's reword actually moves the 72%. The overlay line is the best-evidenced cause, not a
  proven one; the base-prompt section and `_PROSE_FORMAT`'s own ambiguity are alive as
  co-explanations, which is why the tier is staged.
- The `finish_reason` field is not in the corpus export, so truncation was measured via the
  `_TRUNCATION_MARK` that `_mark_if_truncated` appends before the transcript commit. That is the
  right proxy, not a direct read of the provider's stop reason.

**Two findings outside this CR, recorded so they are not lost.**

- Running DEF231's `_direction_contradictions` over the whole epoch: it would fire on **2 of 18
  Trader** turns (*"reclaim the $737.88"* with the close at $875.18, 18.6% above it; *"move above the
  $998.19"* with the close at $1,212.21) and **1 of 18 conservative_debator** turns. The check is
  wired to `verdict.reason` only, so all three reached the PM's prompt unannotated. That belongs to
  the Trader's and the Risk Debators' CRs, not here — flag-only if it is taken up at all, since
  DEF059 makes the safety floor the sole vetoer.
- `_LEVEL_PATTERNS` (`room_runner.py:1151-1155`) captures `(\d+(?:\.\d+)?)` with no comma group,
  where `_LEVEL_NUMBER` in the direction family handles thousands separators. One RM turn shows the
  consequence: *"target of $1,507…"* parses as **1**. Latent only — no RM turn produced the full
  triple that `_verify_and_annotate_geometry` requires, and 0 Trader/PM turns hit it in this epoch —
  but it is the same shape as DEF234 in the family DEF235 already owns. CR145 Tier B's ground.

**Cross-cutting items NOT re-litigated here** — owned by
[CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md):
the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (DEF236, open), `_LEVEL_PATTERNS`
vs the prose format (DEF235, fixed), `LearningStyle.QUICK`'s *"terse, tabular"* against *"no
tables"*, and the per-agent fact sheet (`_format_profile` takes no `agent_id`). DEF237 stays open
against its own owner.

**Ordering.** Tier B and Tier C are the same file, cost hours, and can ship together and alone. Tier
A is the one that changes what the Room can know; it touches the shared fact sheet, so it should land
with — or be explicitly sequenced against — CR145 Tier C. Tier D waits for evidence it binds.
