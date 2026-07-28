<!-- dispatch lane hand-off. CR052. -->
# CR098-MOBILE-VERDICT — hand-off

Built by the **Architect directly**, not by a `coder.mobile` worker. Saiful asked for it built so
CR098 can close; four lane workers died mid-flight in 27h on this project, and the two files this
touches were edited by me an hour earlier in CR098-MOBILE-LIVE round 2. The `GATE: independent` is
unchanged — track U audits this exactly as it would a worker's lane.

BRANCH: `lane/CR098-MOBILE-VERDICT.coder.mobile` @ `89d3f95` (off `main`, after LIVE integrated)
WORKTREE: `.claude/worktrees/coder.mobile-CR098-VERDICT`

## Acceptance, one line each

| # | Criterion | Result |
|---|---|---|
| 1 | `flutter test` green; `analyze --no-fatal-infos` exit 0 | **143/143**; exit 0, the 5 predicted pre-existing infos |
| 2 | **Record current behaviour first** | **Renders. Does not throw.** `exception=null`, all levels null. The lane's premise was wrong — detail in the bridge |
| 3 | `NO_VERDICT` + all-null renders via the real parse path | ✅ — and it already did on `main`; now pinned |
| 4 | Level fields **absent**, not `—`/`0`/empty row | ✅ — exact-match assertion on all 6 labels |
| 5 | Disclosure on **every** action, asserted on `APPROVE` | ✅ — **M2** proves the inversion would ship silently |
| 6 | Empty list ⇒ identical to today's card | ✅ — equal to the key being absent from the wire (weaker than a byte-diff; flagged) |
| 7 | No upgrade language / plan names / pricing in agent copy | ✅ — asserted on the reason **widget**, so concatenating chrome into the PM's voice fails |
| 8 | CTA visually distinct from the PM's voice | ✅ — `OutlinedButton` under a `Divider`, outside the reason block |
| 9 | Unknown/future action does not crash | ✅ — `DEFERRED_PENDING_EARNINGS` renders raw, no throw |

## Measured

- Full `flutter test` **128 → 143**, foreground, this worktree.
- **5 mutations**, each applied physically, each **RED at exactly one test**, each reverted; tree
  `git status --porcelain` empty afterwards and 143 restored.
- `flutter analyze --no-fatal-infos` exit **0**.

## Not verified — named, not omitted

- **Nothing on a device or against melehost.** Promotion hold is active and this lane is unmerged.
- **No live `NO_VERDICT` convene.** Payloads are hand-built from `room_runner.py::_assemble_no_verdict`,
  read at the source.
- **`ar`/`ms` for 4 new strings** — adds to the 24 already filed as **DEF137**.
- **The rendered share PNG.** Accent input changed; image not captured.

## Found, NOT fixed

- `room_screen.dart` already carried **two** copies of `_resetDateStr`; I added a third rather than
  refactor another lane's code. Worth one cleanup lane, not this one.
- **CR106** (`proposed`, specced today) covers `NO_VERDICT` rendering on this same screen. Its own
  row says *"rebase behind CR098"*, so the ordering holds — but the overlap is real and someone
  should reconcile the two before CR106 builds.

---

STATUS: READY_FOR_AUDIT (round 1)
