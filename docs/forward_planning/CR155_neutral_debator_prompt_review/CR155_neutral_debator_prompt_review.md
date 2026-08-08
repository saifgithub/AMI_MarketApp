# CR155 — The Neutral Debator's opener costs it its stance, and its stance costs the user a number

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 — *"book CRs one for
each agent."* One CR per agent so each remedy is decided on its own evidence rather than bundled.
**Source:** CR143 Phase 1/3b + two independent reviews of the Neutral Debator — a blind
prompt-coherence audit ([`external_review/room/neutral_debator.md`](../CR143_agent_prompt_audit/external_review/room/neutral_debator.md))
and a codebase-verified data-sufficiency audit ([`external_review/room/kimi/neutral_debator_data_sufficiency.md`](../CR143_agent_prompt_audit/external_review/room/kimi/neutral_debator_data_sufficiency.md)).

**Method (inherited from CR143).** Every claim below carries a **supplier check** (does the code
inject the data the prompt claims?) and a **parser check** (does anything read the output this
instruction shapes?). CR105's Amendment 1 is the precedent: written from prompt files alone, two of
its four findings were wrong and the "fix" would have turned an existing guard red. Two of the
reviews' claims died here the same way — see *Rejected claims*. All rates are computed over the
CR143 epoch (`corpus/llm_audit_2026-08-07-epoch.json`, `corpus/room_runs_2026-08-07-epoch.json`),
**n=18 convenes**, and every one is re-derivable from those two files.

---

## Why

One line in `content/agents/neutral_debator.md` fights one line in `room_prompts._STANCE_FORMAT`,
and the collision is not cosmetic — it runs all the way down to a number AMI publishes to the user
under the words *"These are the figures of record."*

**The chain, verified end to end:**

1. `content/agents/neutral_debator.md:23` — *Open with: "Splitting the difference, I'd propose [X]"*.
2. `room_prompts._STANCE_FORMAT` (`room_prompts.py:264-277`) — *"your VERY FIRST line must be this
   one line"*, the `[STANCE: … | CONVICTION: … | HEADLINE: …]` envelope.
3. `parse_stance_envelope` (`room_runner.py:1728-1791`) searches **only the first and last non-blank
   line**. An envelope on line 2 is neither stripped nor read.
4. Measured: the opener appears in **18/18** turns. It takes the first line in **6/18**, and those
   are **exactly** the 6 turns with no stance. The cross-tab is degenerate — 12 turns stance-first
   with the opener demoted to line 2, 6 turns opener-first with no stance, **0 turns satisfying both
   instructions as written**.
5. Stance capture, read from the stored `room_runs.transcript[].stance` (live ground truth, not a
   re-implementation):

   | agent | stance stored | has an `Open with:` line |
   |---|---|---|
   | the eight other prose agents | **18/18 each (100%)** | no |
   | aggressive_debator | 17/18 (94.4%) | yes |
   | conservative_debator | 15/18 (83.3%) | yes |
   | **neutral_debator** | **12/18 (66.7%)** | yes |

   The three agents carrying an `Open with:` line are the only three that ever lose the envelope,
   and the Neutral Debator — whose opener is a full sentence with a placeholder for the proposal
   rather than a two-word fragment — loses it most.
6. In **2/18** the raw `[STANCE: …]` line survives into `transcript[].content` — i.e. into what the
   user reads *and* into the `Transcript so far:` the PM reasons from. That is DEF095's contagion
   vector with a machine channel in it.
7. And then the parser reads it. On the AMD convene the leaked envelope's HEADLINE field —
   `HEADLINE: 5.0% entry at $494.31` — is where `_LEVEL_PATTERNS["entry"]` found its match. That
   completed the entry/stop/target triple, `_verify_and_annotate_geometry` fired, and AMI published
   *"[AMI verified the trade geometry from the stated levels (entry $494.31 / stop $464.65 / target
   $608.23): R:R 3.8:1 … These are the figures of record.]"* **Strip the envelope where the prompt
   asked for it and `entry` does not match at all — the note is never published.** AMI read its own
   machine channel back as the agent's proposed entry.

**The second half of the story is the one DEF235 already knows about, but the epoch says it belongs
to this agent, not the Trader.** `_verify_and_annotate_geometry` published a *"figures of record"*
note on exactly **2 turns in the whole 18-convene epoch**. Both were the Neutral Debator's. The
Trader — the agent `_LEVEL_PATTERNS` was written for (`room_runner.py:1836-1850`, *"principally the
Trader"*) — published **0/18**.

The ANET one is the sharpest object in this CR. The same prompt, sixty lines above the transcript,
already printed the right answer:

> `Reference position (risk-tier ceiling 3.0% size, entry 188.62, stop 177.30) → stop 6.0% below entry → portfolio-drawdown contribution ≈ 0.18 pt of the 30 pt cap`

The agent restated those two levels as its proposal and wrote the size as a word:
*"a **MEDIUM** size entry at **$188.62** with a tight **6.0%** stop at **$177.30**"*.
`_LEVEL_PATTERNS["size"]` matched `\bsize\b` then the next number and returned **188.62** as a
position size; `drawdown_contribution(188.62, 188.62, 177.30)` returned **11.32 pt**; AMI published
11.32 pt under *"These are the figures of record"* — **63× the 0.18 pt the same prompt had already
computed correctly from the same two levels.** That turn also had no stance envelope at all.

Both published notes attached to a convene where the **Trader had said WAIT**. Across the epoch the
Trader proposed WAIT in 11/18; the Neutral Debator proposed an actionable entry in 3 of those. So
AMI stamped "figures of record" onto a trade geometry nobody in the Room had proposed.

**What produces the phrasing is this agent's own output-style block.**
`content/agents/neutral_debator.md:26` — *"Propose specific compromise: size, entry, stop, hedge"* —
asks for four level labels, and `:23` asks for them in one opening sentence. Measured: **5/18**
opening sentences carry two or more level labels inline, which is precisely the surface
`_LEVEL_PATTERNS` collides with. Of the 7 turns where the `size` pattern matched anything, **2**
returned a value implausible as a percentage (188.62 and 307.63) — and the 307.63 came, again, from
a leaked HEADLINE field.

---

## Scope — three tiers, ordered by cost

### Tier A — the opener (one line, three files, no code)

Reshape or delete `content/agents/neutral_debator.md:23`, and the identical construction in
`aggressive_debator.md:23` and `conservative_debator.md:23`. Preferred form keeps the voice and
yields the first line:

> *After the STANCE line, open your prose with "Splitting the difference, I'd propose …"*

Fallback if that does not move the number: delete the bullet.

**The fix is on the prompt side and must stay there.** `tests/unit/test_cr106_stance_envelope.py::test_a_stance_line_mid_argument_is_prose_not_the_machine_channel`
deliberately asserts that a `[STANCE: …]` line between two prose lines **is prose**, because an
agent quoting the format mid-paragraph is writing about it. Widening `parse_stance_envelope` to
accept a mid-turn envelope turns that guard red for a good reason — the exact CR105 Amendment-1
trap this method exists to avoid. Do not touch the parser.

All three debators ship in one commit: fixing one and leaving the others confounds the
re-measurement, since all three draw from the same 18 convenes.

### Tier B — the four labels and the unsuppliable fourth (editorial, this agent's file)

`content/agents/neutral_debator.md:26`, three separate edits:

- **`hedge` is unsuppliable and the prompt forbids the only honest answer.** Supplier check: there
  is no `option_chain` call anywhere in `app/` — the entire yfinance surface is `.info`
  (`fundamentals.py:141`, `classification_universe.py:271`), `.fast_info` / `.history()` / `.news` /
  calendar (`market_data.py:530/549/576/613`). The mandate is LONG-ONLY (`_compliance_block`), so no
  instrument-based hedge is permissible even if one existed. Parser check: nothing anywhere reads
  the word. Measured: **3/18** turns use hedge language, **0/18** name an instrument — the three are
  *"hedging against the 14.2% drawdown risk"* (a smaller size), *"hedged by holding the position only
  through the FOMC decision"* (a time stop), and *"no entry, no stop, no hedge"*. Replace `hedge`
  with **"protective measure (size or stop distance)"**.
- **Ask for the size in the unit the system enforces.** *"size, entry, stop"* invites
  *"a MEDIUM size entry at $188.62"*. Ask for **"size as a % of portfolio"** — the single change
  that removes the shape which produced the 63× figure, on the agent that produced it.
- **Forbid restating the Street's target as its own.** Both published notes used the fact sheet's
  `Analyst consensus … target $608.23 / $238.63` as one leg of "the stated levels". The sheet already
  labels that line *"Street view — NOT company guidance"*; the agent's own target is a different
  object and it does not have one.

The `_LEVEL_PATTERNS` regex fix itself is **DEF235's, owned by CR145** — cross-referenced, not
re-solved. What is in scope here is not writing the sentence that trips it.

### Tier C — render the open-risk total the mandate makes it enforce (small; data already in memory)

The mandate block tells every agent *"Total open-risk cap: 60.0% — the sum of (position size % ×
stop distance %)/100 across all open positions, including this one"*
(`overlay_generator._max_open_risk_pct_text`). The portfolio block gives weights and unrealised P&L
and **no stops** (`room_runner._build_sim_holdings_block:752-755`), so the sum is under-determined.
Measured: **4/18** turns assert a fact about total open risk anyway — *"keeps total open risk within
the 60.0% limit"*, *"Aggressive overstates capital availability by ignoring current open-risk
usage"*. That is the CR040 class: a rule stated as hard, enforced against a number the agent is
never shown and forbidden to invent.

Supplier check — **already wired, not rendered**: `existing_open_risk_pct` is summed per open trade
row in `sim_engine.py:481-501`, fetched once per run at `room_runner.py:2864`, held as
`ctx.risk_existing_open_risk_pct` (`:314`) and handed to the safety floor at `:1914` and `:3193`.
`grep -n "open_risk" app/services/room_prompts.py` returns **nothing** — it reaches zero prompts.
Rendering it is one line in the RISK/VERDICT mandate snapshot beside the existing drawdown reference.
No new fetch, no rate-limit exposure, no cache question.

Three constraints on the render, all load-bearing:

- The sum is per **open trade row**, not per aggregated holding (`sim_engine.py:481-483`) — the
  portfolio block aggregates lots per ticker, so render the precomputed total, never a per-holding
  figure the reader could re-derive differently.
- Rows with `stop=None` contribute **0** (`sim_engine.py:493`). Render the count of unstopped rows
  explicitly or the agent reads a protected book that isn't — a DEF059-class silent fallback.
- `None` must render loudly as *"unavailable this run"*, never be omitted. The floor already fails
  closed on `None` (`safety_floor.py:520-534`); the prompt must degrade the same way.

Blast radius is the three RISK debators and the PM, not all 12 — the snapshot is already gated to
RISK/VERDICT (DEF066, `room_prompts.py:400-401`).

---

## Verified findings

| # | Finding | Supplier / parser evidence | Measured (n=18) |
|---|---|---|---|
| 1 | The opener displaces the stance envelope and the envelope is then lost | `neutral_debator.md:23` vs `_STANCE_FORMAT` (`room_prompts.py:264`); `parse_stance_envelope` bounds its search to the first/last non-blank line (`room_runner.py:1737-1767`) | opener used 18/18; opener-first 6/18; stance stored **12/18 (66.7%)**, worst of the 11 prose agents (8 agents with no `Open with:` line: 18/18) |
| 2 | The lost envelope leaks the machine channel into the transcript | stored `room_runs.transcript[].content` | **2/18** carry a literal `[STANCE:` (aggressive 1/18, conservative 1/18, all others 0) |
| 3 | The leaked envelope is then read by the level parser | `_LEVEL_PATTERNS["entry"]` matched inside `HEADLINE: 5.0% entry at $494.31`; removing that line kills the match | 1 of the 2 published geometry notes exists only because of the leak; a second turn's `size` match (307.63) came from a HEADLINE too |
| 4 | This agent, not the Trader, is where the geometry parser actually fires | `_verify_and_annotate_geometry` runs on **every** agent (`room_runner.py:3469`), not just the Trader | *"figures of record"* notes published: **neutral 2/18, every other agent 0/18** (trader 0/18) |
| 5 | The 63× drawdown figure (DEF235) is produced against a correct figure already in the same prompt | `_drawdown_snapshot_line` printed `≈ 0.18 pt` from entry 188.62 / stop 177.30; `_LEVEL_PATTERNS["size"]` read 188.62 as a size; AMI published `≈ 11.32 pt` | 1/18, and it is the same turn that lost its stance |
| 6 | Both published notes describe a trade nobody proposed | Trader ticket `Side: WAIT`, `Entry/Stop/Target: N/A` on both convenes | Trader WAIT in 11/18; neutral proposed an actionable entry in 3 of those; both notes are in that 3 |
| 7 | The output-style line manufactures the collision surface | `neutral_debator.md:26` asks for size+entry+stop+hedge; `:23` asks for them in one opening sentence | **5/18** opening sentences carry ≥2 level labels inline; `size` matched 7/18, implausible-as-a-percent 2/7 |
| 8 | `hedge` cannot be supplied, cannot be permitted, and is read by nothing | no `option_chain` in `app/`; LONG-ONLY hard constraint; no consumer of the word | 3/18 use hedge language, **0/18** name an instrument |
| 9 | The total open-risk cap is unverifiable from the prompt, and asserted anyway | `existing_open_risk_pct` computed (`sim_engine.py:481-501`), on `ctx` (`room_runner.py:2864`), to the floor (`:1914`) — zero occurrences in `room_prompts.py` | **4/18** assert an open-risk fact the block cannot support |

**Context measures (not scope, but they set the acceptance baselines).** Assembled prompt median
**17,890 chars** — second largest of the 12, behind the PM's 22,788 (the AMD sample is 18,318).
Reply median **1,043 chars** — 70% longer than the other two debators (aggressive 601, conservative
612) against an identical 600-token budget (`_AGENT_MAX_TOKENS`), and **0/18** truncated. Length
guide *"2 sentences"* vs median **5**, **18/18** over, **17/18 (94%)** bullets — DEF236's, not this
CR's. Format compliance is otherwise clean: **0/18** tables, headings, code fences or
*"As the …"* prefaces.

---

## Rejected claims and why

Six claims from the two reviews do not survive a check. Recording them is the point of the method.

1. **"The Trader's, Aggressive's and Conservative's arguments are not supplied"** (blind review,
   Unfollowable A + B; its Failure Mode 1, hallucinated synthesis). **Rejected — structurally
   false.** RISK is a sequential phase: `_Phase.parallel` defaults to `False` and only ANALYSTS sets
   it (`room_runner.py:144-166`), guarded by
   `test_cr077_phase_parallelism.py::test_parallel_phases_are_exactly_the_independent_phases` and
   `::test_debate_phases_are_never_parallel`. The Neutral Debator speaks third in RISK, so
   `_format_transcript` (`room_prompts.py:378, 470`) hands it every prior turn including both
   debators. The blind review audited an older AAPL sample with no transcript.

2. **"The 5.0% reference position conflicts with the 3.0% single-name cap"** (blind review,
   Contradiction D; its Failure Mode 3, oversized position). **Rejected — impossible in current
   code.** `ctx.trader_size_pct = _risk_tier_size_ceiling(mandate)` (`room_runner.py:2913`) is the
   same `resolved_single_name_cap_pct` the cap line renders and the PM clamps to, so the reference
   size *is* the ceiling by construction. Verified on both live samples: AMD cap 10.0% / reference
   10.0%; ANET cap 3.0% / reference 3.0%. And the failure mode is not observed — **0/18** turns
   propose a size above the stated cap (three regex candidates were drawdown and stop percentages,
   inspected individually, not sizes).

3. **"Widen the `sector_weights` render gate from PM-only to the three RISK debators"**
   (data-sufficiency review, Gap 2 / §6.2). **Rejected for this agent — no demand.** The supplier
   claim is correct (`ctx.sector_weights` is computed once per run in `_build_room_sector_context`,
   `room_runner.py:774-789`, and rendered only for the PM, `room_prompts.py:453-455`), but **0/18**
   Neutral Debator turns mention a sector at all. The review inferred the need from the
   *Conservative's* and the *Trader's* turns. If it is a real gap it belongs to those agents' CRs
   with their own measurement; it is not this agent's.

4. **"Surface the deterministic `neu_size` in the mandate snapshot"** (Gap 4). **Rejected as
   scope, recorded as an open design question.** Supplier claim verified: `risk_debator_sizes`
   (`sizing.py:111-127`) returns `neutral = trader_size` and the values land in the f-string
   `formatter` at `room_runner.py:2954-2956`, which feeds the canned `_TEMPLATES` fallback only,
   never `build_room_messages`. But AMI's computed "neutral" size **is the single-name ceiling** —
   showing it to an agent whose whole job is judgment between two extremes replaces the judgment
   with the ceiling. The review reached the same conclusion; noted here so a later session does not
   re-open it as free wiring.

5. **"Tone preference: terse, tabular vs Plain text — no tables"** (blind review, Contradiction C)
   and **"Senior-PM voice vs minimise prose"** (Contradiction E). **Not scope here.** The first is
   `LearningStyle.QUICK` and is owned by CR145. Both are asserted as contradictions with no observed
   consequence for this agent: **0/18** tables, **0/18** headings, **0/18** code fences. Cross-
   referenced, not re-solved.

6. **"Fix `parse_stance_envelope` to find the envelope wherever it lands."** Not proposed by either
   review — rejected pre-emptively because it is the obvious fix and it is wrong.
   `test_cr106_stance_envelope.py::test_a_stance_line_mid_argument_is_prose_not_the_machine_channel`
   asserts the current bound deliberately. This is the CR105 Amendment-1 shape: a prompt-derived fix
   that turns a green guard red. The remedy is Tier A, in the prompt.

---

## Acceptance

Every criterion is a **re-measurement of a stated baseline**, run post-promotion against `llm_audit`
and `room_runs` on melehost with the same queries used here. A prompt edit whose effect is not
re-measured is the CR105 Amendment-1 trap (CR145's acceptance says the same thing for the same
reason). Minimum **30 convenes** for the rate criteria; the n=18 baselines below are the epoch's.

- **Tier A.** `room_runs.transcript[].stance` non-null for `neutral_debator` ≥ **95%** (baseline
  12/18 = 66.7%). `aggressive_debator` and `conservative_debator` no worse than their baselines
  (17/18, 15/18) — they are edited in the same commit, so a regression there is this CR's.
- **Tier A.** Turns whose `transcript[].content` contains the literal substring `[STANCE:` = **0**
  across all 11 prose agents (baseline: neutral 2/18, aggressive 1/18, conservative 1/18).
- **Tier A.** **0** published `[AMI verified the trade geometry …]` notes whose `entry`, `stop`,
  `target` or `size` was matched inside a stance envelope (baseline 1 — AMD). Re-run the exact
  replication: strip the envelope per `parse_stance_envelope`, then apply `_LEVEL_PATTERNS`, and
  diff the triple against the un-stripped text.
- **Tier B.** Opening sentences carrying ≥2 level labels inline ≤ **1/30** (baseline 5/18).
  `size`-pattern matches returning a value implausible as a percentage (>100) = **0** (baseline
  2/7 of the matches).
- **Tier B.** The word "hedge" in a `neutral_debator` turn = **0** (baseline 3/18). It cannot be
  satisfied honestly while LONG-ONLY holds and no derivatives provider exists, so its absence is the
  correct outcome, not a suppressed one.
- **Tier B.** **0** geometry notes whose `target` leg is the fact sheet's `Analyst consensus` figure
  (baseline 2/2 — both published notes).
- **Tier C.** Every turn asserting a total-open-risk fact is checkable against a rendered number.
  Measure **agreement**, not absence: of the turns citing open risk, the fraction whose figure
  matches the rendered `existing_open_risk_pct` within 0.1 pt. Baseline is undefined by construction
  — there is nothing to agree with — which is the finding. Target ≥ 90%.
- **Tier C.** A run with `existing_open_risk_pct is None` renders a visible "unavailable this run"
  line; asserted by a unit test, not by inspection (CR040).
- `pytest backend/tests/unit/ -q` green throughout, and specifically `test_cr106_stance_envelope.py`
  **unmodified** and green — the fix must not reach the parser.

---

## Out of scope

Owned by **[CR145](../CR145_fundamentals_data_and_lane_discipline/CR145_fundamentals_data_and_lane_discipline.md)**,
cross-referenced only: the `_LENGTH_GUIDE` / `_PROSE_FORMAT` / `_STANCE_FORMAT` conflict (**DEF236**)
and the `_AGENT_MAX_TOKENS` sizing behind it; the `_LEVEL_PATTERNS` regex fix and its
structured-field replacement (**DEF235**); `LearningStyle.QUICK`'s *"tabular"* against *"no tables"*;
and the per-agent fact sheet (`_format_profile` takes no `agent_id`).

Rejected above and not to be re-opened without new measurement: sector weights for the debators;
surfacing `neu_size`; any hedging instrument (needs a new provider *and* a change to the LONG-ONLY
compliance floor — two decisions, neither this CR's).

Not measured and not claimed: whether speaking last before the PM gives this agent disproportionate
weight in the verdict. It is the 4th largest contributor to the pre-PM transcript (median **10.5%**,
range 6.3–14.8%, behind bull 17.6% / RM 14.9% / bear 11.3%), and the epoch has only 3 APPROVE
verdicts — too few to test recency against. Stated as an open question, not a finding.

## Notes

Tier A is one line in three markdown files and carries findings 1, 2 and 3 — it is the cheapest
item in this CR and the only one that closes a user-visible wrong number. Tier B is editorial and
independent. Tier C is the only one that touches Python, and it is a single render line against a
float already sitting on `_RoomContext`.
