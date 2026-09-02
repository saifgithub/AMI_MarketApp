# 01 — Review of the 17 findings and the evidence record

Verdict up front: **the findings hold.** Every load-bearing claim spot-checked during this
review resolved against primary sources. The record's discipline is above the bar for a
research folder — the in-code PM harness-artifact exclusion in `aggregate_arms.py`, the
"Two things the record does NOT support" caveats, and `verify_citations.py` guarding
against line-number rot are exactly the habits that make this reviewable. Two gaps and
two overlaps below.

## Spot-checks performed (all passed)

- `evidence/rendered/fundamentals_analyst.txt` carries both halves of the headline
  contradiction in one assembled prompt: "never describe a margin as rising, falling,
  expanding" (line 23) and "M&A history are **not available**" (line 42) against
  `Margin trend, YoY (LIVE)` (line 128), `Buybacks (LIVE)` (129), `Capital returned
  (LIVE)` (130).
- `backend/app/agents/overlay_generator.py:93` is the only `primary_goal` reference on
  the Room path (`- Primary goal: {mandate.primary_goal}`, an f-string print), and
  `:437` (`long_horizon = m.horizon in (Horizon.LONG, Horizon.VERY_LONG)`) is the only
  branch — finding #17 confirmed.
- The `:447` else-branch emits "Emphasise momentum in fundamentals (earnings revisions,
  surprise history), guidance." verbatim — Class C #15 confirmed live for every short-
  and medium-horizon user.
- `evidence/rendered/sheets/trader.txt` is byte-identical to `__FULL__.txt` (5,808
  bytes) while `rendered/trader.txt`'s `## Inputs` never mentions a fact sheet — Class D
  confirmed.
- The suppression measurement (margin trend 24.2% cited vs margin structure 95.5%,
  buybacks 13.3%) is computed from banked Alpha traffic by `citation_rates.py`,
  independent of the Gemini arms — the causal claim rests on production data, correctly.

## Gap 1 — an undisclosed harness artifact in the arms

`evidence/convene_gemini.py:77` hardcodes `path=Path.LONG_HORIZON` while `--horizon`
varies. The `h_short` arm therefore ran an internally incoherent mandate (`Horizon:
short` alongside `Path: long_horizon`), and four of its twelve agents dutifully reported
that incoherence as a contradiction. The record correctly does *not* count these as
production findings — but unlike the PM exclusion, nothing discloses it: the
`HARNESS_ARTIFACT` filter in `aggregate_arms.py` applies only to the PM, and neither
README's caveats section mentions it. A reviewer opening `h_short/` first meets four
artifact reports with nothing telling them so.

**Recommendation:** add it as the third item in `evidence/README.md`'s "Two things the
record does NOT support" (making it three), and extend the artifact filter to these
four reports or annotate them in the arm's log.

## Gap 2 — finding #8 is the weak link; say so where it's used

The record itself flags the social-baseline denial (#8) as weakest, and the measurement
section is honest that undenied Dividend also sits low (16.7%, n=18) — suppression by
omission is directional evidence, not proof, for any single field. This is handled
correctly in the CR doc; carry the same caveat into whatever combined reviewer summary
gets written, so the 24%-vs-95% margin-trend pair (where the mechanism was caught
verbatim in the reasoning traces) stays the headline and #8 does not.

## Overlap 1 — the uncommitted CR210 diffs, and what #12 actually needs

Four files sit uncommitted on `main` (CR210, in_progress): `risk_officer.py`
(`items`→`prefixItems`, fixing a measured 72%-vs-100% `one_per_size` regression),
`room_prompts.py` (the Trader HOLD/WAIT branch regains a pinned `Size: 0.00%` line,
fixing a measured 69%-vs-100% `size_within_cap` regression), and both CR210 test files.
Two issues:

1. **The 2026-08-27 measurements exist only in code comments.** 50/69 and 47/68 against
   100% unconstrained baselines are exactly the numbers CR210's acceptance needs, and
   nothing under `CR210_.../results/` records them. Commit the diffs with a results
   artifact, or the numbers die with the working tree.
2. **Finding #12 is an instruction fight, not a grammar gap — fix it on the instruction
   side.** The WAIT branch's own rationale (room_prompts.py, in the uncommitted hunk)
   is explicit: `Size: 0.00%` is the honest statement of no position, while
   "Entry/Target/Stop on a WAIT WOULD be fabrication, which is why those stay out."
   That rationale is correct — so the fix for #12 is not extending the regex to pin a
   `Stop:` line, it is scoping the persona/overlay demand ("never skip the stop-loss")
   to BUY turns explicitly. With the regex flag on, the grammar already makes a Stop
   line impossible on WAIT; the contradictory instruction remains in the prompt,
   burning reasoning and still firing on the flag-off and outage-fallback paths. One
   sentence in `trader.md` closes it. (If a Stop-presence checker ever scores WAIT
   turns the way the Size checker did, mirror the Size decision with a pinned
   `Stop: none — no position` rather than relaxing the checker; same shape of argument.)

## Overlap 2 — #13/#14 already have a house pattern

The CR names it correctly: these are CR179 Leg 4 inverted ("hand over the derived
figure rather than the two operands and an instruction"). The resolution in
[`03_scope_recommendations.md`](03_scope_recommendations.md) is therefore not a design
question, just an application: precompute the drawdown contribution per ladder rung in
code and print the derived figures, instead of handing the RO the cap and the size and
forbidding the multiplication.

## On the evidence being Gemini-generated

The record's framing — "Gemini's replies are used as evidence of what the prompt does
to a reader, never as ground truth about CAT" — is the right epistemics, and the
production citation-rate corpus (qwen3.8 on Alpha) independently corroborates the
suppression effect on the model that actually serves users. No change requested; noted
so the combined review doesn't re-litigate it.
