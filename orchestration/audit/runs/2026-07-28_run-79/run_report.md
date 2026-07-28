# DEF131 round 2 — audit run report

- **Item:** DEF131 (audit handshake never checked delivery)
- **Round audited:** 2 (`SUBMITTED: round 2`)
- **Audited SHA:** `83ff107` on `main` — fresh detached worktree `.claude/worktrees/audit-DEF131/`
- **Round-2 commit scope:** 6 files, +228/−55 (`watcher.sh`, `dispatch.sh`, bridge, `DEF131.row.md`, `DEF135.row.md`, `def_list.md`)
- **Verdict:** `AWAITING_FIXES (round 2)` — BLOCKER 0 · MAJOR 1 · MINOR 1

## Method

Independent two-clone reconstruction built from scratch at `/tmp/def131r2` (scratch bare remote +
`arch`/`aud` clones). Real scripts from the audited SHA, driven via `DISPATCH_LANE_DIR` /
`DISPATCH_AUDIT_DIR` / `HANDSHAKE_CR_DIR`. Probe script `/tmp/def131r2_probe.sh`. Nothing
inherited from the bridge's T-table; my numbering is my own.

## Probe results (all reproduced)

| Probe | Observed |
|---|---|
| T1 submission written, not committed | `UNCOMMITTED_SUBMIT`, inbox hot, exit 1 |
| T2 committed, NOT pushed (literal DEF131 event) | `UNPUSHED_SUBMIT`, inbox exit 1; auditor clone `(no lanes yet)` |
| T3 pushed | `IN_AUDIT`, inbox exit 0; auditor `AWAITING_AUDIT` |
| T4 verdict committed, not pushed | `UNPUSHED` on both boards in the same clone — round-1 "Not verified" closed by measurement |
| T5 verdict pushed + fetch | `AUDIT_PASSED`, inbox exit 1; watcher `COMPLETE` |
| T6 no remote | silent — `IN_AUDIT`, never `*_SUBMIT` |
| T7 not a git repo | silent — `IN_AUDIT` / `AWAITING_AUDIT` |
| T8 orphan (no assign file = this lane's shape), unpushed | inbox hot `(self-executed)`, exit 1 |
| T9 orphan pushed | clears |
| T10 `DISPATCH: ACCEPTED` + unpushed submission | `UNPUSHED_SUBMIT`, not DONE |

Structural checks:

- Placement: `dispatch.sh:138-152`, after `sub_round` read, ahead of `DISPATCH: ACCEPTED` (:162).
- `needs_architect` + inbox exit-1 set carry both new tokens; heading renamed off "AUDITOR DONE".
- `unpushed()` / `undelivered()` code lines byte-identical across both scripts (comments stripped,
  `diff` clean). Both scripts pass `sh -n`.
- No consumer outside the two scripts references the state strings (`grep -rn` over `*.sh`/`*.py`).
- Live board: 0 `*_SUBMIT` rows on either board; `dispatch.sh inbox` exit 0.
- `python3 scripts/registers/gen_registers.py verify def` → `OK — 135 rows, content identical`.
- Backend suite intentionally not run: zero backend files in the commit; the shell scripts' test
  command is the probe battery + `sh -n`.

## Findings

- Round-1 MAJOR 1 (submission side unguarded): **FIXED** — T1–T3, T8–T10.
- Round-1 MAJOR 2 (false root cause, unfiled liveness gap): **CLOSED** — retraction in bridge,
  row, and commit message; boundary drawn correctly; real cause filed as DEF135, row accurate
  against run-76.
- Round-1 MINOR (overconfident staleness comment): **FIXED** — both scripts, sentence only.
- Three invited attack points (distinct tokens / ACCEPTED-ordering / editing window): all
  accepted with measurements T1, T10 and the consumer grep.
- **MAJOR 1 (round 2):** no DoD table on a `SCOPE: cr` submission. DEFINITION_OF_DONE.md rule 5:
  missing table = MAJOR. 38 sibling lanes carry the table. The Docs row would have caught this
  round's MINOR.
- **MINOR:** vocabulary drift — `watcher.sh` comment still says "UNCOMMITTED" above the
  `UNCOMMITTED_SUBMIT` emit; `DISPATCH_PROTOCOL.md:153` exit-1 enumeration missing `UNPUSHED` and
  both `*_SUBMIT` tokens.

## Recorded, not scored

- Pre-assignment submission (assign file without ASSIGNED line) is delivery-invisible: lane_state
  returns UNASSIGNED first, orphan sweep skips lanes with assign files. Contrived, no live instance.
- DEF132 (`watcher.sh state` exit 1 on populated read) still present, correctly out of lane.
- Not verified (both sides, unchanged): shallow clone/detached CI; concurrent-push races;
  relative-`HANDSHAKE_CR_DIR` correct-by-ordering.

## Environment

- Mac, shared checkout untouched; all git work in `/tmp/def131r2` and the detached worktree.
- Pre-flight green: pytest 9.0.3 (backend venv), melehost stack healthy, api-alpha health ok,
  origin reachable.

## Addendum — stakeholder ruling (2026-07-28)

Saiful waived DoD-table enforcement until he starts it formally. Round-2 MAJOR 1 (missing DoD
table) downgraded to recorded-not-scored; verdict amended to `COMPLETE (round 2)`. Waiver on
record in `AMI_TRADE_BINDINGS.md` gap-fill 7. Substance of this report unchanged.
