# Audit run 2026-08-03 run-05 — CR136-M09 (mobile UI), round 1

Auditor track U. Submission `orchestration/audit/cr/CR136-M09.architect.md`.
SCOPE: chunk. GATE: independent. depends-on: none. **First Flutter lane in CR136.**

Verdict: **AWAITING_FIXES** — 1 MAJOR, 2 MINOR. Findings in
`orchestration/audit/cr/CR136-M09.auditor.md`.

## On §1 — was this round justified?

Partly, and less than M06's. This is the best-built lane I have audited in this
CR: every coercion I checked is conservative, the units pin throws rather than
guesses, all 11 unit values and all 3 refusal-code strings match the backend, and
the mandatory caveat is structurally coupled to the bars. The MAJOR is a
**durability** gap — nothing holds those parities correct over time — not a live
defect. That is still worth the round, because it is the architect's own §5.1 and
because DEF210 is the documented ten-week precedent, but the module itself came
back clean.

## The bindings gap — real, and fixed in this commit

`AMI_TRADE_BINDINGS.md` pins the independent regression suite as
`backend/.venv/bin/python -m pytest tests/unit/ -q`. That command executes **zero
lines** of this lane. The submission flagged it and asked that it be recorded
rather than the lane passed on a suite that never ran its code — correct call.
`AMI_TRADE_BINDINGS.md` is an auditor-owned path, so I have amended it in the same
commit as this verdict to name the Flutter equivalent
(`flutter analyze --no-fatal-infos` + `flutter test`, from `mobile/`) for
Dart-surface lanes. Recorded here so the amendment is traceable to the lane that
exposed it.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| module tests (5 files) | 85 passed | **85 passed** | match |
| `flutter test` (full) | 495 passed | **495 passed** | match |
| `flutter analyze --no-fatal-infos` | 6 issues, all pre-existing infos | **6 issues, 6 infos, 0 errors, 0 warnings** | match |

Analyzer detail: `main.dart:93` ×2 (`deprecated_member_use`),
`floor_screen.dart:74,329` and `push_notification_listener.dart:59`
(`use_build_context_synchronously`), `sign_in_email_disclosure_test.dart:27`
(`use_super_parameters`). None from this lane's files — the claim holds. The
submission's prose names three files where there are four (it omits `main.dart`);
the count and the substance are right, so this is a listing slip, not a finding.

Worktree `.claude/worktrees/audit-CR136-m09` detached at `d69d3cc7`, clean at
checkout. Flutter 3.41.9 stable.

## Revert-proof QA — re-performed

| Mutation | Submission | Auditor | Result |
|---|---|---|---|
| QA-A units pin corrupted (`realised_max_drawdown` percent→fraction) | `+49 -2` | **83 passed, 2 failed** | guard real |
| QA-B CR040 unknown-status guard disabled | `+33 -1` | **84 passed, 1 failed** | guard real |
| QA-C missing-gate fallback made permissive | `+0 -2` | **84 passed, 1 failed** (my substitute mutation) | guard real, evidence not |

Baseline and post-restore both **85 passed**; `git diff --stat` empty.

The submission ran narrower file subsets per QA (hence its different passed
counts), so only the failure counts are comparable. QA-A and QA-B match. QA-C is
m2 below.

## MAJOR M1 — two Python↔Dart parity contracts, neither with an automated guard

This is §5.1, and the architect's own prediction ("if you find one thing in this
lane, I expect it to be this") was right.

**Contract 1 — the units map.** `kMetricValueUnit`
(`mobile/lib/models/portfolio_health.dart:31-43`) must mirror
`METRIC_VALUE_UNIT` (`backend/app/services/portfolio_health_constants.py:202-214`).
I compared all 11 entries by hand; **every one agrees today**:

```
portfolio_volatility fraction · beta ratio · tracking_error fraction ·
effective_bets ratio · risk_contribution fraction · mcr fraction ·
weight_concentration ratio · typical_bad_month fraction · scenario_panel fraction ·
realised_max_drawdown percent · realised_return percent
```

**Contract 2 — the refusal codes**, which the submission does not mention as a
parity surface. `portfolio_health_finding_screen.dart:103,109,125` switch on three
literal strings; `health_gate.py:37-38` defines `GATE_CLOSED_CODE` /
`DAILY_CAP_CODE` and `portfolio.py:174` emits `portfolio_health_unavailable`. All
three agree today. A silent divergence here drops the user into the generic
`default` panel instead of the upgrade sheet or the daily-cap note — quieter than
a wrong number, but the same class.

Why MAJOR rather than MINOR, given both are correct today:

- **The client's own guard cannot catch it.** `HealthMetricBlock.unit` throws only
  for a metric it has *never seen*; a metric pinned to the *wrong* unit renders
  silently at 100× or with a spurious `%`. Verified directly: with `value: 0.25`,
  `fraction` → `25.0`, `percent` → `0.25`, `ratio` → throws, unknown metric →
  throws, empty metric name → throws. The throw covers the addition case and not
  the drift case.
- **DEF210 is the documented precedent for exactly this shape** — a backend enum
  member never mirrored into Dart, a `??` coercion making the entry impersonate a
  different type, ten weeks dark, nothing red.
- **The repo already has the mechanism and the standing rule.**
  `test_config_compose_parity.py` fails the build on env-var parity, and the DEF137
  l10n gate does it for ARB keys — CR027's own audit caught a real failure through
  it. `CLAUDE.md`: "Second occurrence of anything ⇒ add an entry **with a guard**."
- It is cheap: a backend pytest that reads the `.dart` file and compares the two
  maps is ~20 lines, in the same shape as
  `test_def141_audit_pins_are_collected.py`, which already parses files rather
  than importing them.

## MINOR m1 — `(json['metrics'] as Map?) ?? json` is not a real dual-shape contract

`PortfolioHealth.fromJson:287`. The comment justifies the root fallback as
forward-compatibility ("a backend that ever flattens the envelope is a
one-`fromJson` fix rather than a dead card"). But M07 has a single return path,
`_health_envelope` (`backend/app/api/portfolio.py:113-124`), which **always**
nests under `metrics`. There is no second shape today.

What the fallback does to a `metrics`-less envelope, measured:

```
status          = ok
isOk            = true
blocks.length   = 0
holdingsCount   = 0
totalValue      = 0.0
```

Because `status` is hoisted to the root, it still reads `ok` — so the card takes
the **populated** branch (`health_card.dart:121` `if (health.status != 'ok')` is
false) with zero blocks, routing *around* the unknown-status guard this lane added
in `0762f02d` for precisely this class. The fallback defends by guessing rather
than failing visibly, which is what CR040 forbids.

MINOR, not MAJOR: not reachable while M07 is the only producer, and the values it
yields (0 blocks, 0 holdings) render amber/empty rather than a wrong number. Fix
is either to drop the fallback and let a shape change surface as the unknown-status
state, or to make the root reading conditional on `metrics` being genuinely absent
*and* the payload carrying block-shaped keys.

## MINOR m2 — QA-C's evidence does not demonstrate its claim

QA-C states the mutation as `HealthGateStatus.closed` → `.open`. **There is no
`open` constant** — `grep -c "static const open"` → `0`; the only static const on
that class is `closed` (`portfolio_health.dart:73`). That mutation cannot compile,
and the reported `+0 -2` (zero passed, two failed) is the signature of a load
failure, not of assertions catching a behaviour change. A mutation that does not
compile proves nothing about whether the test is a guard.

The guard **is** real — I substituted an equivalent that does compile (flipping
`planHasAccess` to `true` inside the `closed` constant) and got **84 passed, 1
failed**. So this is an evidence defect, not a coverage defect. Worth fixing
because the whole point of the revert-proof section is that the numbers in it are
load-bearing.

## Verified clean

- **Units pin behaviour** — exactly as specified, measured per metric (above).
- **All 11 unit values and all 3 refusal-code strings match the backend.**
- **Refusal panels** (§5.3): the `default` branch renders a real panel
  (`portfolioHealthErrorBody`) with a retry `onTap`, not an empty one. The rate
  limiter's 429 carries no CR136 `code` and so lands in `default` — acceptable, if
  slightly generic for a rate-limit refusal.
- **Coercion review** (§5.2): `sufficient` defaults `false` (renders insufficient),
  `planHasAccess` defaults `false`, `value`/`standardError`/`tEff` stay nullable
  with no substituted number, a missing `gate` object yields
  `HealthGateStatus.closed`. All conservative. The one non-conservative fallback is
  m1.
- **The mandatory caveat cannot be drawn without the bars** (§5.6):
  `portfolioHealthBarsCaption` sits unconditionally inside the same
  `if (_open) ...[ ]` block as `RiskMoneyBars` (`health_card.dart:665-673`); only
  the *extra* negative note is conditional, which is correct.
- **The negative-share caveat boundary** (§5.4) — keyed on the displayed figure
  (`(r.risk * 100).round() < 0`) with the rationale written at `:310-313`: a caveat
  explaining a negative number with no negative number on screen explains nothing,
  and the bar geometry still uses the true value. Defensible; I agree with the call.

## Not verified — stated rather than implied

- **§5.5, the CR120 scroll-budget re-pin (3.0 → 3.75 screens).** Not re-measured. It
  moves an already-accepted acceptance criterion, so it is a stakeholder call as
  much as a technical one; flagged for Saiful rather than graded.
- **§5.7, loading state as a stuck terminal state.** Not exercised.
- **Device passes (checklist 3.2-3.3, iPhone 13 / iPhone 17).** `NEEDS-DEVICE-CHECK`
  — no build has shipped and melehost is off-LAN, as the submission says. Saiful's
  acceptance test is expected to cover it.
