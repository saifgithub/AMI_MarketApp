# WP03 — Class B: instruction fights instruction (R15–R20)

Six collisions where one instruction contradicts another in the same assembled prompt.
Read the assembled prompt first (`../evidence/rendered/<agent>.txt`, regenerate with
`../evidence/assemble_room.py`) — every collision exists only in the concatenation, not
in any single file.

## R15 — finding #9: technical overlay demands a trend the persona forbids

Mostly resolved by WP01's R4 (market analyst may now cite window/primary trend/RS).
Remaining work: add one clause to the overlay's market-analyst branch
(`backend/app/agents/overlay_generator.py`) naming the trends **the sheet states**
(64-day window, primary trend, RS) as the ones to use — phrased in the same vocabulary
the sheet renders, so the WP02 R11 mapping resolves. Acceptance: R11 check green;
no overlay branch demands an indicator trajectory.

## R16 — finding #10: Bull conviction collision (ruled 2026-09-02)

**Disambiguate, keep both.** The trailing CONVICTION is the machine-parsed stance
envelope — template at `backend/app/services/room_prompts.py:679`, prompt-side regex at
`:756`, parser at `backend/app/services/room_runner.py:2888–3005` (`_CONVICTION_FIELD_RE`
at `:2902`, values low|medium|high). It must stay. In
`content/agents/bull_researcher.md`, rename the persona's own top-of-case strength
term to something that cannot collide (e.g. **"case strength"**), so the word
CONVICTION appears only in envelope instructions. Check `bear_researcher.md` for the
same pattern while there. Acceptance: grep of both personas shows CONVICTION only in
envelope context; the envelope regexes in `room_prompts.py` untouched; stance
extraction tests still green.

## R17 — finding #11: Bull date-pairing vs no-speculation

The "date every claim" rule collides with the no-speculation ban when the date is the
analyst's own inference. **Scope the no-speculation ban to factual claims**; dating
your own inference is honesty, not speculation — reword the ban to say exactly that.
File: `content/agents/bull_researcher.md`.

## R18 — finding #12: Trader WAIT vs mandatory stop-loss

The persona demands a stop-loss on every plan; a WAIT/HOLD turn opens no position, so
a stop would be fabrication. **Fix in `content/agents/trader.md` only**: add the
WAIT/HOLD carve-out — on a no-position turn the money block states
`Size: 0.00% of portfolio` and omits Entry/Target/Stop, matching what the already-
landed CR210 regex enforces (commit `49380813`,
`backend/app/services/room_prompts.py` trader regex + `risk_officer.py`). **This is a
persona-text change, not a regex change** — the CR210 grammar work is done and has its
own open item (post-fix arm re-run) that is NOT this WP's concern. Acceptance:
`test_cr210_room_wiring.py` / `test_cr210_schemas.py` stay green (37 tests);
persona and regex now say the same thing.

## R19 — findings #13–14: Risk Officers handed operands, forbidden to compute

The three debators receive raw operands (position size, drawdown figures) plus a
prohibition on multiplying them — so they either disobey or hand-wave. Two steps, in
order:

1. **Diagnostic convene at HEAD first** — code has moved since the CR was written.
   Rerun `../evidence/assemble_room.py`, read the three debator prompts as assembled
   today, and confirm the operand+prohibition pair still exists (cite the current
   lines in your commit message). If it's gone, close the row with the evidence and
   stop.
2. **Precompute per-rung drawdown contribution** in code (likely
   `backend/app/services/risk_officer.py` where the ladder is built) and render the
   derived figure into the debator prompts, so the prohibition costs nothing. Follow
   the `Asymmetry` line as the template for how AMI mints and labels a derived number
   (R20).

## R20 — global derivation policy (ruled in QWEN's session)

**Agents never do arithmetic on sheet figures; AMI mints and labels every derived
number.** Implement as: (a) the shared prompt tail gets one policy sentence (quote
figures, never compute new ones — computed lines are provided and labeled), (b) any
place a persona currently implies computing (the R19 debators are the known case)
gets the precomputed line instead. The `Asymmetry` line on the sheet is the existing
template — new derived lines copy its labeling style. Acceptance: WP02 guard's R11
mapping still resolves (derived lines are sheet lines like any other); no persona
instructs computing ratios from raw sheet numbers (add a grep-style assertion to the
guard for the known phrasings).
