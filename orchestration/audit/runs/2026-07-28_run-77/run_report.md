# Audit run — 2026-07-28 run-77

**Item:** CR098-MOBILE-LIVE round 1 · **SHA** `dca1051` (`lane/CR098-MOBILE-LIVE.coder.mobile`) · **Verdict:** AWAITING_FIXES · **BLOCKER 0 · MAJOR 1 · MINOR 1**

Worktree `.claude/worktrees/audit-CR098-LIVE` (`git worktree add --detach`), reaped after. Flutter is
on the Mac, so unlike the backend lanes this was fully verifiable locally.

## Order of operations

1. Scope diff `ce6d55e..dca1051` — **11 files, +707/−12**. Exact match.
2. Full `flutter test` — **122/122**, before any mutation.
3. Read the three deltas that carry behaviour (`api_client.dart` parse, `room_providers.dart` state,
   `room_screen.dart` render) and traced the recovery path they interact with.
4. Probe group A — locked chair vs stream interruption (A0 control + A1 break).
5. Probe group B — six malformed / partial `agent_withheld` payload shapes.
6. Checked the **only producer** (`backend/app/api/room.py:248`, `room_runner.py:2084`,
   `entitlements.py`) to decide whether group B has a live instance.
7. Prototyped the MAJOR's fix and measured it, including the full suite.
8. Mutation battery — the Architect's M1/M2/M3 re-derived, plus my M4/M5.
9. `flutter analyze` on the 5 touched non-generated files.

## Results

| | | Result |
|---|---|---|
| Baseline `test/services/ test/widgets/` | lane claimed 86/86 | **86/86** |
| Full `flutter test` | lane claimed 122/122 | **122/122** |
| `flutter analyze`, 5 touched files | 0 issues | **No issues found** |
| **M1** | rename `agent_withheld` in `api_client.dart` (real wire parse) | **RED** (2) |
| **M2** | rename `agent_withheld` in `room_providers.dart` (state half) | **RED** (2) |
| **M3** | remove tenure's own CTA — the DEF059 inversion | **RED** (1) |
| **M4** ᵐⁱⁿᵉ | drop the `order` mirroring | **RED** (1) |
| **M5** ᵐⁱⁿᵉ | null out `nextStepDays` | **RED** (1) |
| **A0** | stream ends normally | `RENDERS_CHAIR=true` |
| **A1** | stream breaks after `agent_withheld` | **`RENDERS_CHAIR=false`**, `done=true`, `err=null` |
| **B1/B2/B3/B5/B6** | malformed payloads | throw → recovery, disclosure lost, no error |
| **B4** | `reason` absent | handled (`?? 'upgrade'`) |
| **Fix prototype** | re-seat withheld ids in `_recoverViaPolling` | A1 → `RENDERS_CHAIR=true`; **130 passed**, 0 regressions |

`dirty(lib)=0` after every revert; 86 baseline restored at the end.

## Findings

- **MAJOR** — `_recoverViaPolling` rebuilds `order` from the transcript, and a locked chair is never
  in the transcript, so an ordinary dropped connection erases the withheld-analyst disclosure with
  `done=true` and no error. `RoomRunSnapshot` has no withhold field, so recovery cannot restore it.
  CR090's `liveDataNotice` on the same screen survives the same path — it renders independent of
  `order` — which is what makes this a lane defect rather than a design limit. Fix measured.
- **MINOR** — three hard casts (`ev['agent_id'] as String`, `as int?`, `as String?`) throw on
  malformed payloads and divert to the same silent-loss path. **No live instance**: checked the only
  producer — `AgentId.value`, the literal `"upgrade"`, and a pydantic-`int` subtraction.

## Recorded

- `roomNotifierProvider` is `.autoDispose` **and** self-starting; a test that awaits `start()` is
  awaiting a no-op if the microtask won, and re-reading the provider can hand back a fresh notifier.
  My first A1 attempt read an empty state because of this and I nearly reported it as the finding.
  **My harness bug, not the lane's** — logged so the next probe holds a `container.listen`.
- 4 new user-visible strings need `ar` + `ms`; one carries an `int` plural.
