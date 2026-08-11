<!--
R68-BATCH7.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH7.architect.md.
-->

# R68-BATCH7 — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

3 MAJOR, 0 BLOCKER, 5 MINOR. The batch's *stated* real risk — keeping the three
absences distinct — is genuinely handled **in the builder** and genuinely broken
**at the call site**, which is the same DEF238 shape the submission names as its
own guiding lesson. Separately, one of the four rendered lines states a number
that is not the quantity its own label claims.

What the batch got right is real and was verified, not accepted: the call-site
threading is mutation-proven at both sites, the per-position stop rendering is
correct in every case I could construct, and the DEF241 deferral is an honest
decision rather than a re-scope. Details below.

Audited `e7efd472` from `git archive` into a detached scratch tree
(`scratchpad/audit_e7efd472/`), because `main` has since advanced past it —
`3e08d23e` touches both `room_prompts.py` and `room_runner.py` (DEF159).
Import resolution verified explicitly rather than assumed: my first pass of
standalone probe scripts resolved `app` to the **live shared checkout**
(`/Volumes/Extreme Pro/AMI_MarketApp/backend/app`) instead of the extracted
tree — every probe below was re-run from inside the extracted `backend/` and
the pytest path confirmed with a throwaway assertion
(`PYTEST IMPORTS: …/audit_e7efd472/backend/app/__init__.py`).

---

## MAJOR 1 — the "COULD NOT BE COMPUTED" branch for **open risk** is unreachable from the runner; a real outage renders SILENCE, which is byte-identical to "the caller supplied nothing"

Two of the three absences collapse into one rendering the moment a real caller
is on the other end.

`_build_room_risk_limit_context` (`room_runner.py:965`, `:973`) returns
`(CONTEXT_NOT_SUPPLIED, None, None)` on **both** of its failure paths — no
`user_id`, and any exception. Position 3 is `existing_open_risk_pct`, so on a
genuine outage that field arrives as `None`, **never** as the sentinel.
`_risk_state_block` (`room_prompts.py:419`) fires the loud branch only on
`is CONTEXT_NOT_SUPPLIED`; `None` falls to the `elif … is not None` at `:425`
and renders nothing at all.

Reproduced, extracted tree, real function (not a hand-built tuple):

```
returned: last_loss=CONTEXT_NOT_SUPPLIED | trade_open_timestamps= None | existing_open_risk_pct= None

--- rendered on the OUTAGE tuple ---
Live risk state — what the budget has ALREADY spent:
- Drawdown USED: 0.0 pt of the 30 pt cap — 30.0 pt of headroom remains. Size against the headroom, not against the cap.
- Last stop-out: COULD NOT BE COMPUTED this run — unknown, not 'none'. Any cooldown limit is being enforced blind.

--- rendered when the CALLER SUPPLIED NOTHING for these three ---
Live risk state — what the budget has ALREADY spent:
- Drawdown USED: 0.0 pt of the 30 pt cap — 30.0 pt of headroom remains. Size against the headroom, not against the cap.

open-risk line present on outage?  False
outage block == caller-supplied-nothing block for the OPEN-RISK line?  True (both render NO open-risk line at all)
```

Not the *most* dangerous direction — no fabricated `0.0` is printed, and the
stop-out line does degrade loudly — but the consequence is worse than "one
missing line", because of what the floor is doing at that exact moment.
`check_mandate_compliance` (`safety_floor.py:520-526`) treats
`existing_open_risk_pct is None` as **block every BUY**:

> `"total open-risk cap is set on the mandate but the caller did not supply existing_open_risk_pct — blocked rather than silently skipped (CR040)"`

So in precisely the state where the floor is refusing every buy, twelve agents
debate size with no open-risk line in their prompt, the PM's APPROVE is vetoed,
and **the one sentence written for this case never renders** —

> `"Treat it as unknown, not as zero — the safety floor is blocking on this, and you should not argue for added size as if the book were flat."`

That string is dead code in production. The submission's own table asserts three
distinct renderings; at the call site there are two.

`test_a_failed_computation_says_so_and_never_reads_as_zero` and
`test_the_sentinel_is_not_confused_with_a_falsy_value` both pass
`CONTEXT_NOT_SUPPLIED` **themselves** — the builder is proven, the caller says
nothing, which is the DEF238 blind spot the submission correctly identifies and
then walks into on its own sentinel handling. (The batch avoided it for the
*kwarg threading*; see CONFIRMED below.)

Note the asymmetry is only in this field: `last_loss_closed_at`'s omitted-state
sentinel genuinely IS `CONTEXT_NOT_SUPPLIED` (`safety_floor.py:186`), which is
why that line degrades loudly and this one does not. Either the renderer must
treat `None` as unknown for `existing_open_risk_pct` (matching what the floor
already believes `None` means for that field), or the caller must hand the
sentinel through. Direction offered, not prescribed.

## MAJOR 2 — `"Trades opened in the recent window: N"` is not a recent-window count. `N` is every trade the user has ever opened, and the line asserts it is "the pace an over-trading limit counts"

`_risk_limit_context` (`sim_engine.py`) builds the list as
`trades = self.list_trades(user_id)` — **no status filter, no date filter** —
then `trade_open_timestamps = [t.opened_at for t in trades]`. The docstring says
so in as many words: *"all trade opened_at timestamps"*. The windowing is the
floor's job and the floor does it itself
(`_trades_since(ts, _utc_day_start(now))` / `_utc_week_start`,
`safety_floor.py:494`, `:501`).

`_risk_state_block` (`room_prompts.py:440-444`) prints `len()` of that
unwindowed list and labels it a recent window.

Reproduced end-to-end against a real sim user with a real trade history
(scratch tree, `get_sim_engine()`, 40 trades all opened 90–130 days ago):

```
Live risk state — what the budget has ALREADY spent:
- Drawdown USED: 0.0 pt of the 30 pt cap — 30.0 pt of headroom remains. …
- Open risk already committed: 0.0% across open positions carrying a stop. …
- Trades opened in the recent window: 40 (the pace an over-trading limit counts).

lifetime trades in the list ......... 40
trades the DAY brake actually counts  0
trades the WEEK brake actually counts 0
```

Zero today, zero this week, "40 in the recent window". A second probe with 200
lifetime trades and exactly one today prints `200` against a true day-count of
`1` and week-count of `2`.

This is the class the batch cites as its own governing principle — a number
handed to the model with a meaning it does not have, in the same block whose
sibling line was carefully qualified *because* its figure was partial. The
direction is conservative (it overstates pace, so the Room over-refuses rather
than over-trades), which is why this is MAJOR and not BLOCKER: the floor is
unaffected, no wrong trade executes. But an agent reading "40 trades in the
recent window" against a mandate pace cap has been told something false, and the
submission's whole thesis is that the batch supplies numbers the agents
previously had to invent.

No coverage: no test in the repo passes a non-empty `trade_open_timestamps` to
`build_room_messages`. Every hit for that identifier under `tests/` is a
`check_mandate_compliance` call, not a prompt render.

## MAJOR 3 — `_stop_clause` ships with zero regression protection; mutating it into exactly the two behaviours the submission claims it avoids leaves the suite green

`grep -rn "_stop_clause\|NO stop recorded" backend --include="*.py"` returns
**only** `room_runner.py` — four hits, no test file. (The one grep near-miss,
`test_cr156_def239_def255_pm_verdict.py:134`, is Batch 8's horizon note.)

Mutated the function into the DEF235 sin the lane says it refused, plus the
CR040 silence it says it closed:

- average the stops instead of listing them
  (`return f" — stop ${sum(have)/len(have):g}"`)
- render `""` instead of `" — NO stop recorded (this position is unprotected)"`

Result: `58 passed` across the four closest files
(`test_cr055_room_holdings.py`, `test_cr153_risk_state_in_prompt.py`,
`test_cr156_def239_def255_pm_verdict.py`,
`test_def136_room_convene_does_not_block_loop.py`) — **the mutation survives
every one of them.** Unmutated, the same four plus
`test_cr101_be2_round2_room_wiring.py` give `64 passed in 81.91s`, so nothing
was skipped into a false green. The full-suite confirmation of the same mutation
is still executing (see the regression note at the bottom); the grep is already
decisive — no test file in the repo contains either string, so no test can be
asserting on the rendering.

The **behaviour is correct today** — I verified every case I could construct and
found no defect (see CONFIRMED below). The finding is that nothing holds it
there. This is the same shape and the same severity as the CR095 round-2 MAJOR
in this repo's own trail ("the paid-path `was_duplicate` early-return exists and
is correct but had zero test coverage … reproduced by deleting the six-line
guard and showing all 30 tests stay green"), and gap-fill 8 puts mutation proof
in the submission rather than the verdict. One test file closes it.

Related and worth stating plainly: the submission carries **no mutation proof of
its own**. Its "call site, not just the builder" section cites *DEF241's*
MUT-1/MUT-2 as the reason the end-to-end test exists — it does not report
mutating anything in this batch. MUT-1 through MUT-4 above are all mine. Under
gap-fill 8 that budget was supposed to be spent attacking claims, not
discovering which of them were never exercised.

---

## MINORs

**MINOR 1 — "there IS no proposal" is not literally true.** The DEF241 deferral
comment (`room_prompts.py:611-629`) and the lane both argue that at RESEARCHERS
and SYNTHESIS *"the Trader has not spoken, so there IS no proposal."* The call
site passes a fully populated dict unconditionally
(`room_runner.py:4068-4072`: `size_pct/entry/stop` from `ctx.trader_*`), which
before EXECUTION holds the initialisation values `base`, `base × 0.94`,
`base × 1.13`. What is absent is a *real* proposal, not a proposal. The
substantive argument — any figure at those phases is minted from an invented
stop — is exactly right and is CR151's own reasoning; only the phrasing
overstates, and it is the phrasing a later reader will rely on.

**MINOR 2 — two lots at the same stop lose their lot count.** `stops` is a
`dict[str, set[float]]` (`room_runner.py:856`), so two open lots both stopped at
$210 render `" — stop $210"`, singular, with no indication there are two. The
level is correct and nothing is invented; the count is only ever surfaced when a
lot is *un*stopped. Reproduced end-to-end (TSLA, two lots at 210.0).

**MINOR 3 — `if stop:` is itself a falsy collapse,** in the batch that is about
falsy collapses (`room_runner.py:864`). A `stop` of `0.0` is counted as
*unstopped*. That is the right answer for a price, so there is no practical
effect — but `if stop is not None` says what is meant and costs nothing.

**MINOR 5 — the submission's regression number is a shared-checkout count, which
is the exact shape DEF159 rules out as evidence.** The lane states *"Full
**shared-checkout** suite at `e7efd472`: 3408 passed, 1 skipped, 521.94s"* — the
label is honest, and that is the problem: the bindings' DEF159 row says a number
measured in the shared working tree *"is not evidence about the repository"* and
must be taken against the committed SHA. At `b79dd445` that distinction was the
difference between `1589 passed` and `1588 passed, 1 failed`. My own count,
taken from a `git archive` of `e7efd472`, is at the bottom of this file — and I
could not complete a full-suite run on this machine under the load it was
carrying, so this round has **no** reproduced full-suite count from either side.
That is a gap to close in round 2, not a reason to accept the shared-checkout
figure.

**MINOR 4 — CR158's `prompt_version` does not move for eleven of the twelve
agents whose prompts this batch changed.** Measured, both trees, correct import
resolution:

```
                        e7efd472^      e7efd472
  fundamentals_analyst  1a6bbf829b1f → 1a6bbf829b1f   (10 more, all unchanged)
     portfolio_manager  cecd1bb6f197 → f57d70c1c368   (moves — Batch 8's _PM_VERDICT_FORMAT)
```

`_assemble_reference_prompt` (`prompt_version.py:166`) calls
`build_room_messages` with `user_id=None` and no risk-state kwargs, so
`_risk_state_block` returns `""` and contributes nothing — not just the
per-user *values* (correctly excluded) but none of the new static instruction
text either. Structural to CR158's reference matrix, not introduced here (the
sector and journal blocks have the same property), which is why it is MINOR.
Recorded because this batch's own acceptance is a post-promotion re-measure, and
for eleven agents the stamp will read identically on both sides of it — anchor
that comparison on the promotion SHA/epoch, not on `prompt_version`.

---

## CONFIRMED — verified independently, no finding

**The call site really is covered, at both sites.** This is the submission's
strongest claim and it holds. `test_the_runner_actually_threads_the_risk_state`
drives the real `RoomRunner.run()`, and I killed it from each site separately:

- **MUT-1** — deleted the four kwargs from `_compute_agent_text`
  (`room_runner.py:4097-4100`): `1 failed, 20 passed`,
  `AssertionError: these agents' prompts carry no risk state … ['aggressive_debator', 'bear_researcher', 'bull_researcher', 'conservative_debator', 'fundamentals_analyst', 'market_analyst', 'neutral_debator', 'news_analyst', 'research_manager', 'social_media_analyst', 'trader']`
  — note `portfolio_manager` correctly survives, proving the two sites are
  independently covered rather than jointly.
- **MUT-2** — deleted them from `_stream_pm_response`
  (`room_runner.py:4328-4331`): `1 failed, 20 passed`,
  `AssertionError: … ['portfolio_manager']`.

**Per-position stops are correct in every case I could build.** Lists, never
averages; unstopped is loud and per-position; mixed lots are named individually.
Direct calls plus an end-to-end render through `_build_sim_holdings_block` with
a real sim user (8 open lots across 4 names):

```
  AAPL ×4 (15.0% of portfolio, unrealised +1,097.68) — stops $88.5, $94
  MSFT ×4 (14.7% of portfolio, unrealised +1,067.56) — NO stop recorded (this position is unprotected)
  NVDA ×4 (4.5% of portfolio, unrealised +46.00) — stops $500, and 1 lot with NO stop recorded
  TSLA ×4 (18.0% of portfolio, unrealised +1,399.72) — stop $210
```

**The open-risk qualifier is true, not decorative.** `_risk_limit_context`
(`sim_engine.py`) skips every trade with `t.stop is None` when summing, so
*"across open positions carrying a stop"* is literally what the figure is. The
qualifier sits on the same line as the number (the only place the number is
rendered — no other prompt surface emits it; `overlay_generator.py:101` renders
the *cap*, not the consumption), and the holdings block does name the excluded
positions individually, as shown above.

**A real `0.0` is stated as fact, and the author used `is`-identity rather than
truthiness at every value decision in the block** (`room_prompts.py:410`,
`:419`, `:425`, `:432`, `:437`, plus `isinstance(…, list)` at `:440`). The
falsy-collapse the batch set out to avoid is genuinely avoided *within* the
builder — `0.0`, `[]`, `None` and the sentinel each take their own branch.
MAJOR 1 is about which value the caller sends, not about this logic.

**Not phase-gating is safe.** The block renders for all 12 agents across all 6
phases (verified per-agent), contains no proposal-derived or stop-derived
figure, and adds a flat **467 chars** to every agent — 4.2% (PM) to 7.2%
(neutral debator) of the assembled system prompt. Nothing in it can contradict
an earlier phase, which is what a gate would have been protecting.

**The DEF241 deferral is honest, not a re-scope passed off as a decision.**
Checked against the primary sources rather than the lane's summary:

- CR151's rejected item 2 is quoted accurately and in context
  (`CR151_research_manager_prompt_review.md:178-183`) — *"would hand the RM a
  drawdown-contribution figure derived from a −6% stop nobody proposed,
  labelled as a reference and read as a measurement."* That adjudication covers
  `research_manager` (SYNTHESIS).
- It does **not** cover `bull_researcher` (RESEARCHERS) — but DEF244 does, and
  DEF244's remedy was to **cut the sizing demand entirely**
  (`bull_researcher.md` now ends with CONVICTION and names the four stages that
  own sizing), having explicitly rejected the supply-the-figure remedy as
  impossible: *"the percentage move … depends on a downside target the Bull
  invents in the same sentence, so there is no figure to precompute."* Widening
  the gate is moot there too.
- `DEF241.row.md` at this SHA still ends `| open | — | AT:R66 |`. The only diff
  to that row in this commit is the appended deferral paragraph; the status
  field is untouched. **Verified, as claimed.**
- The pin has teeth. **MUT-4** — widened the gate to
  `proposal = trade_proposal` (every phase):
  `AssertionError: bull_researcher got a worked figure from a proposal that does not exist at its phase — see CR151's rejected item 2`, `1 failed, 20 passed`.

**Registry states are as claimed.** CR153/CR154/CR155/CR156 all still
`in_progress` at this SHA.

**No stateful construct introduced,** so the protocol's full-lifecycle clause
has nothing to bite on: `_risk_state_block` and `_stop_clause` are pure
functions of their arguments, the stop/unstopped dicts are rebuilt per call
inside `_build_sim_holdings_block`, and nothing new is cached, pooled, or held
across calls. The one module-level cache in reach — `prompt_version._cache` —
is untouched and, per MINOR 4, cannot see this change at all.

---

## The shared commit with Batch 8 — justified enough, and it obscured nothing here

Recorded because the lane asked. The declaration is honest and the per-lane
scoping is stated up front, which is the part that matters. The stated
*justification* is weaker than claimed, though: the two batches' hunks in
`room_prompts.py` and `room_runner.py` occupy **disjoint regions**
(`_risk_state_block` + the two threading sites + `_stop_clause` vs
`_PM_VERDICT_FORMAT` + `_pm_narration` + `_horizon_coherence_note`), so a
Batch-7-only tree would have been a valid, non-broken intermediate — hunk-level
staging would have been awkward, not risky. Cost here was zero: every Batch 7
hunk is separately identifiable and I audited each one. No action; not scored.

## OUT-OF-SCOPE (gap-fill 1 — pre-existing; architect mints the ID, I never do)

**The mandate overlay and the new risk-state line now disagree, in the same
prompt, about what the open-risk sum covers.** `overlay_generator.py:101`
describes the cap as *"the sum of (position size % × stop distance %)/100 across
**all** open positions"*. That is wrong about the code — `_risk_limit_context`
skips every trade with `t.stop is None` — and it predates this batch. Batch 7's
line is the accurate one, which is exactly why the pair is now incoherent.
Rendered together, verified in one assembled prompt:

```
- Total open-risk cap: 10.5% — the sum of (position size % × stop distance %)/100 across all open positions, including this one.
- Open risk already committed: 4.2% across open positions carrying a stop. Positions with no stop recorded are NOT in this figure — see the portfolio block.
```

Not a bounce — the batch did not cause it and does not depend on it. But the
submission's own reasoning for adding the qualifier (*"an unqualified 'open risk
4.2%' reads as complete when the book may hold unstopped positions the number
cannot see"*) applies with equal force to the sentence sitting four lines above
it, and this batch is what puts them side by side.

## Recorded, not scored

`SCOPE: chunk`, so no Definition-of-Done table is owed — and gap-fill 7 waives
enforcement regardless. Noted, not graded.

`existing_open_risk_pct` is typed `Any` and coerced with `float()`, so a string
`"4.2"` renders as a figure and a `[]`/`{}` raises `TypeError` inside prompt
assembly. Unreachable from `ctx` (typed `float | None`) — noted for the record
only.

`_build_sim_holdings_block`'s own failure branch renders *"Portfolio unavailable
this run"*, at which point the open-risk line's *"see the portfolio block"*
pointer dangles. Both halves degrade loudly, so this is cosmetic; flagging it
only because the two blocks now reference each other.

## What I could not verify

- **No live/Alpha reproduction.** This batch changes prompt text only; its own
  acceptance ("whether agents actually size against the headroom") is explicitly
  and correctly declared unmeasured, and a post-promotion epoch is the only
  thing that can answer it. Nothing here is device-gated, so no
  `NEEDS-DEVICE-CHECK`.
- **The DEF258 interaction is unresolved and stays that way.** The submission
  discloses that this adds prompt bytes to all twelve agents including the eight
  that clipped. I measured the input side (+467 chars, flat) but the clipping is
  an *output* `max_tokens` ceiling — whether a longer prompt lengthens replies is
  not answerable off-line. Correctly declared, not a finding.

---

## Regression — what I actually measured, and what I did not

Everything below was run by me, with the bindings' absolute interpreter, from
the extracted `e7efd472` tree's `backend/`:

```text
/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python -m pytest \
  tests/unit/test_cr153_risk_state_in_prompt.py \
  tests/unit/test_cr055_room_holdings.py \
  tests/unit/test_cr156_def239_def255_pm_verdict.py \
  tests/unit/test_def136_room_convene_does_not_block_loop.py \
  tests/unit/test_cr101_be2_round2_room_wiring.py -q
64 passed in 81.91s (0:01:21)
```

Plus the four mutation runs (MUT-1/2/4 on
`test_cr153_risk_state_in_prompt.py`: `1 failed, 20 passed` each; MUT-3 on the
four-file set: `58 passed`, survived).

**The full `tests/unit/` suite is NOT quoted here, because I do not have a number
I measured.** I started it twice against the extracted SHA. The first run was
killed by the harness after ~70 min without emitting a line; the second
(`nohup`, `-p no:cacheprovider`) was still executing at write-up. Cause is
environmental, not the code: this Mac was carrying **20–30 concurrent
`pytest tests/unit/` processes** from other agents' worktrees for the entire
window (`load averages: 52.97 45.90 40.25` at the peak), and my process was
getting ~17–25% of one core — 83 s of CPU in the last ten minutes of wall clock
against the ~522 s the suite needs. Stating the architect's `3408 passed` as
though I had reproduced it would be exactly the thing this role exists to
refuse, and none of the three MAJORs above depends on it: each is a
reproduction, a mutation, or a read of the code at `file:line`.

Round 2 owes a clean full-suite number from whichever side runs it on a quiet
machine — and per MINOR 5, from the committed SHA rather than the shared
checkout.

Run report and `audit-trail.md` row not written — this lane was dispatched with
an explicit single-file instruction, matching R68-BATCH1/2/3, whose auditor lanes
also carry neither.

## VERDICT: AWAITING_FIXES (round 1)
