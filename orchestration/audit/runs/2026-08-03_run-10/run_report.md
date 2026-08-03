# Audit run 2026-08-03 run-10 — CR136-M06, round 4

Auditor track U. Answers round 3's `AWAITING_FIXES` (1 BLOCKER, 1 MAJOR — run-08).
Audited at **`28acbd8a`** in `.claude/worktrees/audit-CR136-m06-r4`, detached and clean.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR, 2 non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M06.auditor.md`.

## B2 closed — self-labelling slots

My two round-3 attacks, re-run through the real chain:

```
realistic swap   - CCC drives an invested weight of 33% of your risk.
loud swap        - Your portfolio volatility has been a beta of 1.19 a year.
correct          - CCC drives a risk share of 38% of your risk.
```

Neither is rejected and neither is false. I then tried four ways to make a *labelled*
figure read as a true claim about the wrong metric — "CCC sits at an invested weight of
33%", "The concentration here is an invested weight of 33%", "Your book carries a beta
of 1.19", "Risk is dominated by CCC, at an invested weight of 33%". Every one is true.
The label travels with the figure and I could not build a sentence that separates them.

That is the property I asked for: misplacement is not prevented, it is stripped of its
ability to lie.

## M5 closed

All eight compounds plus the widened run reject. `\w*fold` is a rule over a productive
family rather than another list entry — `twentyfold` and `n-fold` reject without being
enumerated. Ordinary prose re-measured and still passes.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| validator + renderer suites | 81 passed | **81 passed, 3.27s** | match |
| QA-I self-labelling removed | 1 failed, 80 passed | **1 failed, 80 passed**, same test | exact |
| QA-J `\w*fold` dropped | 3 failed, 78 passed | **3 failed, 78 passed** — `[twofold] [tenfold] [hundredfold]` | exact |
| restored | 81 passed | **81 passed**, tree clean | match |
| full `tests/unit/` | 2278 passed, 13 warnings, 287.28s | **2278 passed, 13 warnings, 297.88s** | exact |

QA-I and QA-J were also the two mutations I chose before reading §9's QA block.

Round-4 measurements were taken in the tree being submitted rather than a child of it —
the round-3 bookkeeping correction, applied without being asked twice.

## MINOR m3 — the second assertion B2 wants is over the map, not another sentence

The submission asked directly whether B2 wants a second independent assertion. It does.
Dropping `top_risk_weight_pct`'s label is caught only because the regression test names
that slot; `_SLOT_LABEL` appears in no test file at all, and `put()` reads
`_SLOT_LABEL.get(name)` with a silent fallback to the bare value. A **new** figure slot
added without a label reopens B2 for that slot with nothing red — and `mcr` and
`scenario_panel` are unslotted blocks, so it is a live growth path.

Better than a test: `_SLOT_LABEL[name]` with an explicit exemption for
`top_risk_ticker`, so the guard is the code.

## MINOR m4 — a small finite family of collective counts

Still accepted: `trio duo quartet quintet brace gross fourscore myriad trillion
quadrillion billionth`. `trillion` outside a set containing `billion`/`billions` is a
plain inconsistency; the Latin collectives are quantity claims in the same sense
`pair`, `couple` and `dozen` already are.

MINOR rather than MAJOR because nothing here reproduces a demonstrated attack (M5's
`twofold` was the round-3 attack in new clothing), the error is vaguer in kind, and
unlike `-fold` this is a finite list enumeration genuinely closes. Stated so the
architect can push back.

## Availability — measured, since the fix spends the headline budget

Self-labelling costs ~4 words per slot and headline length is checked after
substitution (`:779-782`):

```
pre= 8w  PUBLISHED(13w)   pre= 9w  PUBLISHED(14w)   pre= 7w  PUBLISHED(16w)
pre=10w  REJECTED(headline_length)
```

A seven-word two-slot headline lands at exactly the 16-word cap, so a three-slot
headline is now structurally impossible. The one rejection is the model repeating the
metric name alongside its label, which the prompt forbids at `:1036` — an instruction
ignored, not the fix being over-tight.

## Closing

Four rounds: allow-list → digits → words → the sentence itself, each round closing the
notation rather than the class. Round 4 is the first fix with no next notation, because
the figure and its metric name are one token. Naming that pattern rather than only
patching it is why this closes at COMPLETE.
