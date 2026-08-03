# Audit run 2026-08-03 run-06 — CR136-M06, round 2

Auditor track U. Answers round 1's `AWAITING_FIXES` (1 BLOCKER, 1 MAJOR, 2 MINOR —
run-04). Audited at **`5465334a`** in `.claude/worktrees/audit-CR136-m06-r2`, clean
at checkout. Per the r1 closing rule: diffs plus a full-suite reproduction.

Verdict: **AWAITING_FIXES** — B1 and r1-M1 both genuinely CLOSED, but 2 new MAJOR.
Findings in `orchestration/audit/cr/CR136-M06.auditor.md`.

## First, the fix is good

The re-injection direction is the right call and it is well executed. B1's
mechanism is not mitigated, it is **removed**: the model cannot emit a digit, so
the flat set, the ±1 ulp window and the both-signs registration no longer gate
anything it can influence. Choosing it over metric-binding on the grounds that
metric-binding is another matching heuristic — and that r1-M1 was a matching
heuristic failing 9 times in 10 — is exactly the right reasoning. The two new
MAJORs below are on the boundary of the new guard, not on the design.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| validator + renderer suites | 53 passed | **53 passed, 2.58s** | match |
| full `tests/unit/` | 2247 passed, 13 warnings, 292.93s | **2247 passed, 13 warnings, 295.54s** | match |
| QA-D digit guard removed | 4 fail | **4 failed, 49 passed**, same 4 names | exact |
| QA-E §F5 fence removed | 1 fail | **1 failed, 52 passed** (`test_f5_is_never_taken_from_the_model`) | exact |

Restored → 53 passed, `git diff --stat` empty. (QA-E's submitted `27 passed` is a
narrower subset; the failure count and name match.)

## B1 — CLOSED, verified rather than accepted

Measured through the real chain (`substitute_slots` → `validate_sections` →
`register_check`) against a slot map and allow-list built from a real
`compute_health` payload:

```
--- the intended path ---
ACCEPTED -> 'Your volatility has been 14.2% a year.'      ({{vol_ann_pct}}, true 14.19%)

--- digits ---
'Your volatility is 89%.'    -> REJECTED(unsubstituted_digit)
'Your volatility is 4%.'     -> REJECTED(unsubstituted_digit)
'Your volatility is 14.19%.' -> REJECTED(unsubstituted_digit)

--- non-ASCII numerals ---
'Your volatility is ٢٠%.'  -> REJECTED(unsubstituted_digit)     (Arabic-Indic)
'Your volatility is ２０%.'  -> REJECTED(unsubstituted_digit)     (fullwidth)
```

The Unicode cases matter and they pass: `_DIGIT_RE = re.compile(r"\d")` on a `str`
pattern matches the whole Nd category, so an Arabic-Indic or fullwidth numeral is
caught. Worth recording because AR ships at v1.0 and `[0-9]` would have been the
natural thing to write.

**The "two renderings cannot disagree" claim holds.** `build_slot_map` uses `_pct`
and `_fmt` — the deterministic path's own helpers — and correctly uses `_fmt`
(no ×100) for the already-percent Tier-2 values `realised_max_drawdown_pct`,
`realised_return_pct` and `cash_pct`. The units discipline that produced the
round-0 "1969.00%" blocker is preserved in the new path.

**The regression test is non-vacuous.** It draws its attack figure from the
allow-list itself rather than hard-coding one, asserts the set is non-empty (so it
fails if B1 stops being reproducible), and asserts the chosen figure is not
coincidentally the true volatility. It runs end to end through a fake gateway.

## r1-M1 (§F5) — CLOSED structurally

Verified at the wiring, not the prose: the prompt now asks only for `f1`, `f2`,
`f4`, and the assembled `sections` dict takes **both** `"f3": deterministic["f3"]`
and `"f5": deterministic["f5"]`. The model neither sees §F5 nor can supply it.
QA-E kills. CR138 filed for the classifier with my 10 probes as its bar and the
note that replacing a hard fence needs a higher bar than beating a denylist —
correct framing.

## r1-m2 — CLOSED (accepted as written). r1-m1 — moot on the LLM path, correctly reasoned.

## MAJOR M3 — a digit is not the only way to write a number

The guard bans digits. The prompt bans digits (`**NEVER WRITE A DIGIT.**`). Neither
bans *numbers*. Every one of these passed the full chain and would be published:

```
ACCEPTED -> 'Your portfolio volatility is about twenty percent a year.'   (true 14.2%)
ACCEPTED -> 'Nearly ninety percent of the risk sits in one name.'         (true 82%)
ACCEPTED -> "The market explains about two thirds of this book's moves."  (true 72%)
ACCEPTED -> 'Your beta is roughly double the market.'                     (true 0.89)
ACCEPTED -> 'Roughly a fifth of your book moves with the market each year.'
ACCEPTED -> 'Your largest holding is about half of your risk.'            (true 82%)
ACCEPTED -> 'About one in three of your holdings drives the risk.'
ACCEPTED -> 'Your volatility is XX percent.'
ACCEPTED -> 'Your volatility is ½ of the market.'
```

"Your beta is roughly double the market" against a true beta of **0.89** is a book
slightly *less* volatile than the market being described as twice as volatile.
That is the same failure class as B1 — a figure attached to a metric it does not
belong to — at a coarser resolution.

This is not merely theoretical pressure: the prompt asks for **plain language**
while forbidding digits, and spelling a number out is the obvious way to satisfy
both. The model has no legal way to express an approximation — a slot yields
"14.2%", never "about a fifth" — so the instruction set actively pushes toward the
one form the guard does not see.

**It also falsifies three sentences in the methodology document as newly
published** (`PORTFOLIO_REVIEW_METHODOLOGY.md`, corrected in this same commit):

- `:39` **"The language layer never writes a number."** It can, in words.
- `:42-44` "A figure therefore **cannot** be attached to a metric it does not
  belong to." The beta example above is exactly that.
- `:56` "The residual risk is **availability, not correctness**." The residual
  includes correctness.

The r1 finding was partly that the published claim overstated the control. The
correction replaced one overstatement with a narrower one that is still false, and
this document goes to professional reviewers.

Fix is the same shape as the guard that already works: a closed number-word screen
over `f1`/`f2`/`f4` post-substitution (one…twenty, thirty…ninety, hundred, half,
third, quarter, fifth, double, twice, triple, "one in three", …), rejecting with
its own reason code, plus prompt wording that bans *numbers in any form* rather
than digits. Then re-word the three methodology sentences to what the controls
actually deliver.

## MAJOR M4 — malformed slot syntax is published verbatim into the artefact

`_SLOT_RE = re.compile(r"\{\{([a-z_]+)\}\}")` matches one exact form. Anything else
is not a slot for the unknown-name check and carries no digit for the stray-digit
check, so it passes through untouched:

```
'{{vol_ann_pct}}'     -> '14.2%'                    (correct)
'{{ vol_ann_pct }}'   -> '{{ vol_ann_pct }}'        <-- published as-is
'{{VOL_ANN_PCT}}'     -> '{{VOL_ANN_PCT}}'          <-- published as-is
'{{vol-ann-pct}}'     -> '{{vol-ann-pct}}'          <-- published as-is
'{vol_ann_pct}'       -> '{vol_ann_pct}'            <-- published as-is
'{{vol_ann_pct2}}'    -> REJECTED(unsubstituted_digit)   (caught, by accident of the digit)
'{{not_a_slot}}'      -> REJECTED(unknown_slot)          (caught)
'{{{vol_ann_pct}}}'   -> '{14.2%}'
```

A model writing `{{ vol_ann_pct }}` with padding spaces — a very ordinary thing for
a model to do with a template — ships the literal string `{{ vol_ann_pct }}` into a
permanently archived financial report. It fails *visibly* rather than misleadingly,
which is the better direction, but it does not fail into the fallback: the module's
own invariant is that any failure discards the whole narration and serves the
deterministic report, and this path violates it.

Fix: after substitution, reject on any residual `{` or `}` (or match a permissive
`\{\{?\s*[A-Za-z0-9_\- ]+\s*\}?\}` and treat every hit not resolved as
`unknown_slot`). Note the near-miss above — `{{vol_ann_pct2}}` is caught only
because the typo contains a digit, which is luck rather than design.

## Round 2 scope

M3 (number-word screen + prompt wording + the three methodology sentences), M4
(reject residual braces). B1's digit half, the §F5 fence, the slot-map formatting
discipline, the regression test's construction and the ERROR-level telemetry all
stand as audited.
