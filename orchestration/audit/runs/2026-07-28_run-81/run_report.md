# CR098-MOBILE-VERDICT round 1 — audit run report

- **Item:** CR098-MOBILE-VERDICT (terminal verdict card under `NO_VERDICT` + `opinions_not_included`)
- **Round audited:** 1 (`SUBMITTED: round 1`)
- **Audited SHA:** `89d3f95` on `lane/CR098-MOBILE-VERDICT.coder.mobile` (commits `19f9acb` parse + `89d3f95` render)
- **Verdict:** `COMPLETE (round 1)` — BLOCKER 0 · MAJOR 0 · MINOR 0

## Measurements (all reproduced independently)

| Check | Lane claimed | I measured |
|---|---|---|
| Full `flutter test` | 143/143 | **143/143** ✅ |
| `flutter analyze --no-fatal-infos`, 4 touched non-generated files | clean | **No issues found** ✅ |
| M2 gate disclosure on `isNoVerdict` (D3 inversion) | RED, one test | **RED — exactly 'renders on an APPROVE with Social withheld'** ✅ |
| M5 `whereType` → `cast` | RED, one test | **RED — exactly 'a malformed opinions list does not take down the card'** ✅ |
| Tree after reverts | clean | **clean** ✅ |

## The "already safe on main" claim — verified on unmodified main

Second worktree at `origin/main`, lane test file reduced to the acceptance #3/#4 group (the full
file references the new `opinionsNotIncluded` getter and cannot compile on main): **3/3 pass**.
The assign's crash-risk premise was false; the null-safety was accidental and is now pinned. The
lane's "pinned, not fixed" framing is accurate.

## `_blockingAnalystId` fallback — unreachable, traced

- `NO_VERDICT` is built only by `_assemble_no_verdict` (`room_runner.py:1071`), called only when
  `MARKET_ANALYST ∈ ctx.withheld` (`room_runner.py:2197`), filling `opinions_not_included` from
  `ctx.withheld` — always non-empty, always containing `market_analyst`.
- Post-loop `model_copy` (`room_runner.py:2349`) overwrites the list on every verdict path.
- `_parse_pm_verdict` routes through `_normalize_pm_action`; `NO_VERDICT` is never LLM-parsed
  (enum comment, `schemas/room.py:18-21`).
- First branch (`contains(market)`) therefore always fires live; the constant fallback is dead
  code against the current backend. No finding.

## DoD spot-check (table rendered despite waiver)

Tests ✅, Manual verification = honest `NEEDS-DEVICE-CHECK` ✅, Register row `started` ✅,
commit tags `(AT:R65 CR098)` on both ✅, `share_service.dart` scope step disclosed and verified
(2 lines + comment) ✅. Imprecision not scored: Scope row says "5 files"; source diff is 9
(4 generated l10n outputs).

## Recorded, not scored

- 4 new `ar`/`ms` keys → DEF137 packet. No device/melehost (promotion hold). No live `NO_VERDICT`
  run — payload confirmed verbatim against `room_runner.py:1061-1081`. Share-card PNG not
  captured (accent mirrored by construction). Third `_resetDateStr` duplicate correctly not
  folded in.

## Environment

- Mac, two detached worktrees (lane SHA + `origin/main`), both reaped after. `flutter test` full
  suite once on the lane, targeted runs for both mutations and the on-main probe.
