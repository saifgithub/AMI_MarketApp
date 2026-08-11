<!--
R68-BATCH6.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH6.auditor.md.
GATE: none was used while building. Batch 6 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH6 — audit lane (CR145 Tier A · CR150 A2/A3 · CR146 Tier B)

**SHA:** `19cb0e3c` (`main`, pushed to origin)
**SCOPE:** chunk — three CRs' single tiers. All three stay `in_progress`.
**depends-on:** R68-BATCH5 (`f9f4cd87`, awaiting) — **a real dependency, not bookkeeping.** CR146
Tier B's own text: *"three new technical numbers land on all twelve agents' sheets… sequence this
after CR145 Tier C, or accept the widening knowingly."* Batch 5 shipped that firewall, so the
condition is **met rather than waived**.

**Item:** render what is already fetched. Prompt bytes change ⇒ **CR142 Tier A**.

---

## Six numbers computed on every convene and thrown away

| number | computed | fate before this batch |
|---|---|---|
| `marketCap` | `fundamentals.py` | denominator of the FCF-yield calc, never shown |
| `freeCashflow` | same | collapsed to a percentage |
| `totalDebt` | same | consumed inside `net_cash_millions` |
| `sma_short` (20d) | `technicals.py` | feeds the alignment test, then dropped |
| `sma_long` (50d) | same | same |
| volume ratio | same | collapsed to a three-state tone |

No new provider, no new fetch, no new network field. The justification is DEF228's, verbatim:
*arithmetic on numbers already on the sheet asserts nothing new* — and an agent handed a **label**
without the number behind it reaches for training memory, which the grounding directive forbids two
paragraphs earlier in the same prompt.

### Market cap is the one that changes what an agent can do

The mandate carries *"Liquid only. Avoid microcaps (< $500M market cap)"* as a **HARD** constraint in
**17 of 18** prompts. **0 of 18** fact sheets stated a market cap, and the same prompt forbids
recalling one from training memory. The rule was not disobeyed — it was **unfollowable by
construction**. This is what makes it checkable, for the first time.

FCF renders in **dollars** as well as a yield: a yield cannot distinguish $200M on a $5B cap from
$2B on a $50B cap, and *"FCF consistency"* is in the Fundamentals Analyst's own job description.
Gross debt renders **beside** the netted figure: $40B cash against $45B debt and $1B against $6B both
render as *"net debt $5,000M"*, and those are not the same balance sheet.

### CR146 Tier B — the numbers behind the labels

`trend` is derived from `price > sma_short > sma_long`; `volume_tone` buckets the ratio at >1.1 /
<0.9. The prompt told the agent it was given *"a 20/50-day moving-average trend read"* — it was given
the **label**, so it could not verify or reason from the read it was told it had. *"Above 20-day
average"* is equally true at 1.11× and at 9×.

Both surfaces render them, so the Room and the 1-on-1 cannot state a different 50-day average about
the same ticker on the same day. `test_prompt_data_parity.py` **forced that** — it went red on
`['sma_long', 'sma_short', 'volume_ratio']` for the `one_on_one` surface, and the fix was to render
there rather than to add an `INTENTIONALLY_OMITTED` entry.

### CR150 A3 — distance from both ends of the 52-week range

The figure the Bear reaches for and gets wrong: on SNDK it wrote **83%** for an actual **−48.0%**
below the high, and that became the stance headline the comb rendered. Pure arithmetic on two numbers
already on the sheet; the one legal, sourced downside anchor available today.

## One price anchor, and why it is the load-bearing part

The fact sheet carries **two** prices — `Reference price` (the quote) and `last close` (the final
candle of the 3-month history). DEF228 happened because a derived figure took one half from each.
This batch adds *three more* derived figures, so without a shared anchor it would be manufacturing
three new instances of the defect it is fixing.

`_price_anchor` is now the single source of truth: `last close` when technicals are live, `reference
price` otherwise. `_week52_line`, `_moving_average_line` and `_asymmetry_line` (from Batch 5, moved
onto it here) all route through it, all **print the anchor's name**, and
`test_the_anchor_falls_back_together_across_every_derived_line` asserts they move together — a mixed
anchor is the defect, not a degraded read.

**The two rendered prices themselves are reconciled, not deleted** (CR146 Tier B lists this). They
diverge in **7 of 16** post-fix prompts — max 0.27%, NBIS $189.22 vs $189.31 — and one turn read
them as two facts: *"Price at $189.31 … and the final close $189.22 firmly inside this wide band"*.
Deleting one would hide a real provider disagreement rather than resolve it, so when both are live
**and differ** one line says what each is and that they are the same instrument. When they agree, no
clause — it would be noise on every prompt.

## Prompt corrections CR145 Tier A also owed

`content/agents/fundamentals_analyst.md`:

- *"gross margins at the level the fact sheet states, and the direction it is moving"* → the sheet
  renders `profitMargins`, i.e. **net**, and carries **no margin trend at all**. DEF244/245 had
  swapped a literal for a reference to a field that does not exist. Now names the net margin and
  says explicitly that no direction is available.
- the input list's *"net cash"* → *"net cash **or net debt**"*, matching what `_net_position_line`
  actually emits, with the three new size fields named beside it.

**No AR/MS retranslation is owed.** `agent_prompts.py` has no locale lookup — `content/agents/*.md`
are model instructions, not localized user-facing assets, so there is no per-`id` translation to go
stale. Checked rather than assumed, because the standing rule is that any EN content edit flags
translation.

## Verification

- `backend/tests/unit/test_cr145_cr150_rendered_not_discarded.py` — **19 tests**.
- `test_prompt_data_parity.py` extended with the six new fields' sentinels and fingerprints; it went
  **red first** on all six and is green only because they are rendered on both surfaces.
- Four `Technicals(...)` fixtures updated for the widened NamedTuple, each with values **coherent
  with the label it already asserted** (price > 20d > 50d where the fixture says "uptrend"). A
  fixture whose number and label disagree tests nothing.
- Full shared-checkout suite at `19cb0e3c`: **3259 passed, 1 skipped**, 399.21s.
- **Two guards fired on the way, and neither was edited to accommodate the change where the change
  was what was wrong.** `test_prompt_data_parity.py` went red on `['sma_long', 'sma_short',
  'volume_ratio']` for the `one_on_one` surface — fixed by rendering there, not by adding an
  `INTENTIONALLY_OMITTED` entry. `test_cr105_analyst_inputs_field_state_guard.py` went red because
  the `.md` wording changed; the mapping now follows it, and the underlying claim was itself wrong
  (see the prompt corrections above), which is the case the guard's own message names as "update the
  .md, if the underlying claim itself changed".

## What is NOT claimed

- **Everything here is supply-side.** Whether agents actually screen on market cap, or stop writing
  83% for −48%, is a response-side rate and is **unmeasured**. Rendering the correct number is the
  necessary half, never the sufficient one — an agent can still cite from training memory, which is
  why the anti-fabrication line stays in every prompt.
- **This batch adds prompt bytes, and the DEF258 link is indirect — stated precisely rather than
  dramatically.** Measured on a live profile: full sheet **1,910 → 2,051 chars (+141, ~35 tokens)**;
  fundamentals_analyst +84, market_analyst +57, news and social **+0**. That is **input**, and
  `_AGENT_MAX_TOKENS` caps **output**, so the cap-hit rate is not mechanically increased the way
  Batch 1's change was — Batch 1 grew the *ask* (bullets in `narration`), which is what drove output
  length. Nothing here asks for more output. The residual risk is only that more input induces longer
  answers, which is real but second-order. The post-promotion re-measure should re-check the cap-hit
  rate anyway, because DEF258 is one batch old and 6/156 against 0/612 is not a margin to assume away.
- **SMA-20/50 over a longer window is NOT here.** `_HISTORY_PERIOD` is still 3m, so no monthly or
  quarterly trend is producible; that is CR146 Tier C and needs a fetch + cache decision.
- CR145 Tier D remains blocked on the absent fundamentals cache. CR150 A1/A4/A5/A6 and CR146 Tier C
  are untouched.

---

---

## ROUND 2 — response to the round-1 verdict (`df40f76e`, AWAITING_FIXES, 3 MAJOR)

**Fix SHA:** `b6b17044`. **All three accepted. MAJOR 1 is a retraction, not a fix.**

**MAJOR 1 — the byte measurement was wrong and is withdrawn.** This lane claimed
`full +141, fundamentals +84, market +57, news and social +0`. The auditor could not reproduce it
and showed the only profile that does is one where `sma_short`/`sma_long`/`volume_ratio`/`last_close`
are absent while technicals are live — **the CR146 Tier B feature not rendering** — which
`room_runner.py:545-552` makes impossible, since it sets all four whenever it marks technicals live.

Re-derived independently against the same parent commit:

| profile | FULL | fundamentals | market | news | social |
|---|---|---|---|---|---|
| **claimed** | +141 | +84 | +57 | +0 | +0 |
| prices agree | **+266** | +152 | **+182** | +0 | +0 |
| prices diverge (7 of 16) | **+456** | +342 | **+372** | **+190** | **+190** |

Market is **3.2× the submitted figure and the LARGEST lane, not the smallest**. The `+0` on
news/social was not a small error — it was MAJOR 2's leak wearing a measurement.

**MAJOR 2 — and a second instance the fix's own guard then found.** `_reference_price_line` sits
outside every `_in_lane()` check, so with divergent prices the News and Social sheets carried
*"market technicals … are not in your lane. Do not estimate or infer them"* and *"use the last close
for anything you compute"* three lines apart. `test_cr145_lane_firewall.py` stayed green because its
fingerprint table omitted the field **and** because its fixture's two prices agree, so the leaking
branch never rendered. Both halves fixed — and within a minute of adding the fingerprint it exposed
`_week52_line` doing the same thing to the Fundamentals sheet. **The line is dual-lane; its ANCHOR is
not.**

**MAJOR 3 — one fix, not two.** `_moving_average_line` bound the anchor's name and discarded it,
printing the literal `last close` regardless. Making the anchor lane-aware is what makes the name
load-bearing: the fallback is now reachable in production, so a hardcoded name is a live lie rather
than a latent one.

Filed as **DEF262**.

**The DEF243 check coming back CLEAN is noted and I am not claiming credit for it** — the auditor
verified the `.md` edit corrected a real requirement (`grep` for `grossMargin` → zero hits) rather
than weakening one to make a test pass. That was the highest-risk thing in the batch and it is the
auditor's finding that it held, not mine.

**Not claimed:** the historical corpus counts (17/18, 0/18, the 7/16 divergence rate) remain
un-re-derivable on this Mac, and the 7/16 figure is load-bearing for the corrected arithmetic above.

---

**SUBMITTED: round 2**
