# Audit run 2026-08-03 run-11 — CR136-M04, round 2

Auditor track U. Answers round 1's `AWAITING_FIXES` (1 MAJOR, 1 MINOR — run-09).
Audited at **`f2cc577c`** in `.claude/worktrees/audit-CR136-m04-r2`, detached and clean.
`f2cc577c` is docs-only over the code tree `8bbf3546` that the submission names.

Verdict: **COMPLETE** — zero BLOCKER, zero MAJOR, 2 non-gating MINOR.
Findings in `orchestration/audit/cr/CR136-M04.auditor.md`.

## Both round-1 findings closed

M1 was fixed by **inverting the branch** rather than by adding a `feed_unavailable`
case — the note is keyed on insufficiency and the cause only chooses the wording. I
re-performed the architect's MUT-A: the card suite goes 36 → **34 passed, 2 failed**,
and the second casualty (`a cause the card has no copy for still gets a note`) is what
makes it a closure of the class rather than of my one demonstrated cause. The generic
note also asserts the misaligned-benchmark copy is *absent*, so it cannot claim a cause
the engine never reported.

m1: MUT-C is my own round-1 MUT-1. It survived all 285 CR136 tests then; it now kills
exactly one test (module suite 40 → **1 failed, 39 passed**).

## Mutations — 9 run, 8 killed, 1 killed harder elsewhere

Three re-performed from the submission (MUT-A/B/C, all exact matches) and six of mine:

```
MUT-D  kInsufficientCauses emptied            parity  2 failed  (set + non-vacuity leg)
MUT-E  Dart cause VALUE drifts t_over_n→tn_ratio  parity  1 failed
MUT-F  backend mints cause 7 AND Dart declares
       it but omits it from the set           parity  1 failed
MUT-G  backend INSUFFICIENT_ prefix renamed   COLLECTION ERROR — the import graph
                                              rejects it before the guard runs
MUT-H  effective_bets inversion reverted      card    36 passed — SURVIVED
MUT-I  portfolio_volatility note deleted      card    36 passed — SURVIVED
```

MUT-D is what earns the `>= 6` non-vacuity assertion its place; MUT-G shows it is *not*
what catches a prefix rename. MUT-H/I are MINOR m3.

## MINOR m2 — `risk_contribution` is the fifth conditionally-rendered element and has no note branch

Executed, not argued. A cause the build has never seen on both share-basis blocks —
which is what a seventh `share_cause` produces, since `portfolio_health.py:377` feeds
`effective_bets` and `risk_contribution` from the same variable — leaves the entire
risk-vs-money bar section gone with only the effective-bets note on screen.

Not live, and I tried three ways to make it live:

- the only reachable share-basis cause on a populated card is `t_over_n`, whose copy
  already covers the bars (*"too few for AMI to attribute risk reliably"*);
- `share_cause = None` needs `covered_invested <= 0` — I built books with every mark
  `0.0` and with every quantity `0.0`; both return `status: no_holdings` and never
  assemble blocks;
- `cov_risky is None` while `estimator_ok` is unreachable by construction.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module suite | 40 | **40 passed, 1.64s** | match |
| parity suite | 4 | **4 passed, 0.70s** | match |
| card suite | 36 | **36 passed** | match |
| every CR136 suite | — | **296 passed, 1984 deselected, 11.52s** | — |
| `flutter test` | 497 passed | **497 passed** | exact |
| `flutter analyze --no-fatal-infos` | 6 issues, all pre-existing infos, 0 errors | **6 issues, 6 infos, 0 errors** — none in a CR136 file | exact |
| full `tests/unit/` | 2280 passed | **2280 passed, 13 warnings, 318.20s** | exact |

Every mutation restored; `git status --porcelain` clean for `backend/` and `mobile/lib`
after each battery, and the probe file was removed before the card suite was measured.
