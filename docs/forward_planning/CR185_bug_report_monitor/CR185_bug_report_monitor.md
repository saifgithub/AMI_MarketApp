# CR185 — Autonomous 6-hourly bug-report monitor

**Status:** proposed · **Owner:** Track R (Development) · **Date filed:** 2026-08-15

## Summary

Establish a standing, autonomous bug-report monitor that polls `melehost.ami_postgres.bug_reports`
every 6 hours, diagnoses new reports, files defects, and marks them tracked — with zero
manual intervention per cycle and no live decision gates.

This **supersedes** the 3-hourly Track-R protocol documented in
`memory/feedback_track_r_bug_monitor.md` (2026-07-20), which surfaced each report via
`AskUserQuestion` and waited for Saiful's call before touching anything. The new design is
fully autonomous at the documentation/tracking layer (silent, no interruptions) while
preserving the unchanged invariant: **never touch code** — file a DEF and move on.

## Motivation

**Status quo (before this CR):**
- 3-hourly manual polling via `AskUserQuestion`, conditional on a Claude session happening
  to start.
- Saiful's decision gate on every report: file DEF, close as wont_fix, or skip/defer.
- Watermark in user memory (not version-controlled) drifted 7 days out of sync once (2026-07-29
  cycle 11 — accumulated 6 unseen reports).
- The `/fix-bugs` manual command is the real bug-fixing path; the monitor's DEF filings
  just annotated what happened.

**New design:**
- Autonomous 6-hourly cycle via `/loop` (self-paced, runs headless, needs no session
  management).
- Filing is deterministic: diagnose each report, collapse duplicates into one DEF, file
  immediately.
- DB status is the watermark: `WHERE status='open'` picks up only unprocessed reports; once
  triaged, status → `investigating` so the same report is never reprocessed (robust against
  missed cycles).
- No live decision gates — surface the DEF passively via git log + the daily 13:00 CR-Defect
  review (CR085), so Saiful sees it when he checks in anyway, not via an interrupt.

## Scope: exactly what the monitor does

### Per cycle (every 6 hours):

1. Query melehost `bug_reports` for all `status='open'` rows.
2. Diagnose root cause for each:
   - Read `title`, `category`, `steps`, `route`, `app_version`, `platform`, `attachment_path`.
   - Spot patterns (e.g., three identical "Cannot remove mandate" rows within seconds → one
     root cause, one DEF covering all three).
3. **Route by category:**
   - `feature_request` → file as a **CR** (proposed), not a DEF.
   - Everything else (`ui_glitch`, `wrong_data`, `crash`, `performance`, `other`) → file as
     a **DEF** (open).
4. **File the defect/CR:**
   - Mint the next free `DEF###` or `CR###` by reading highest in `_registry/`.
   - Write row file + regenerate register (pathspec-commit, tag `AT:R<N> DEF###`).
5. **Mark investigated:** Only after commit succeeds, flip `status → investigating` for every
   report folded into the DEF. If commit fails, leave status `open` so it retries next cycle
   (degrade loudly, never silently drop).

### What the monitor does NOT do:

- Never call `AskUserQuestion`.
- Never set `status=resolved` or `wont_fix` (those stay Saiful's decision, unchanged from
  `/fix-bugs.md`'s existing rule).
- Never touch code or attempt a fix (the `/fix-bugs` manual command or a dev CR lane handles
  that — completely separate).
- Never push to GitHub (commits stay local; Saiful pushes `main` when he's ready).

## Technical changes

### 1. New status value: `investigating`

**File:** `backend/app/schemas/feedback.py:30-36` (`BugStatus` Literal)

```python
BugStatus = Literal[
    "open",
    "investigating",    # ← NEW: triaged, filed a DEF, not yet assigned to coding
    "in_progress",      # (paired with /fix-bugs branch claim)
    "pending_review",
    "resolved",
    "wont_fix",
]
```

**Rationale:** Keeps the semantics clean. `in_progress` means "someone is actively coding
a fix on a branch" (per `/fix-bugs.md` convention); `investigating` means "we looked at it,
filed a defect, haven't assigned to code yet." The DB column is unconstrained VARCHAR (per
`alembic/versions/a8e3c1b50006` docstring: "extend vocabulary without migrations"), so no
schema change or migration required.

**Tests:** Update parametrize lists in `test_feedback_updates.py:99` and `:169` to include
`investigating` (both assert it does NOT trigger the reporter toast — same guarantee as
`in_progress`; only `resolved` fires the notification).

### 2. Permissions: narrow UPDATE allowlist

**File:** `.claude/settings.local.json`

A headless `/loop` cycle can't click through permission prompts, so add a pre-approved
pattern for the specific UPDATE the monitor will run:

```json
"Bash(ssh -o ConnectTimeout=10 melehost \"docker exec ami_postgres psql -U postgres -d ami_trade -c \\\"UPDATE bug_reports SET status='investigating' WHERE id IN (...) AND status='open' RETURNING count(*);\\\"\")"
```

Scoped to the exact pattern: UPDATE only `status` column, only to `investigating`, only
rows that are currently `open`.

### 3. The `/loop` prompt

A self-contained prompt (since loop wakes may not carry session context) that:
- Polls `WHERE status='open'` via SSH+psql.
- Diagnoses and collapses duplicates.
- Routes by category (feature_request → CR, else → DEF).
- Files DEF/CR row file + regenerates register + pathspec-commits.
- Flips status to `investigating` only after commit succeeds.
- Never calls `AskUserQuestion`, never modifies code, never pushes.

**Invocation:** `claude /loop 6h "<prompt-text>"` (self-paced 6-hour cadence).

## Superseded: the old Track-R protocol

**File:** `memory/feedback_track_r_bug_monitor.md`

Mark at the top: "SUPERSEDED 2026-08-15 by CR185." Keep the historical cycle log for
context (cycles 1–11, 2026-07-20 to 2026-07-29) but note:
- Cadence changed: 3h → 6h.
- Mechanism changed: manual AskUserQuestion → autonomous /loop.
- Status vocabulary: introduced `investigating` (old protocol only knew about `open`/filed-DEF/Saiful's-call).
- DB interaction: new protocol marks status in DB; old one only modified memory watermark.

## Acceptance & verification

**Acceptance:** The monitor runs unattended every 6 hours, detects new bug reports,
diagnoses and files DEFs deterministically, and marks them `investigating` in the DB.
Saiful sees the DEF entries via git log / daily 13:00 review and decides next steps
(close as wontfix, lane to /fix-bugs, etc.) from the register, not via a live interrupt.

**Verification steps:**
1. After the schema change lands: `pytest backend/tests/unit/test_feedback_updates.py -q`
   passes (investigating status is recognized, doesn't fire toasts).
2. Manual test: run the `/loop` prompt once manually with the 10 open reports in the DB.
   Verify:
   - At least one DEF is filed (spot the new row in `_registry/DEF###.row.md`).
   - The register regenerated cleanly (`python scripts/registers/gen_registers.py verify all`).
   - At least one `bug_reports` row flipped to `investigating` (re-query the DB).
3. Leave the loop running 6-hourly for 1 week; confirm no errors, no orphaned open reports.

## Related

- **Supersedes:** `memory/feedback_track_r_bug_monitor.md` (Track R 3-hourly protocol, 2026-07-20).
- **Cross-ref:** `/fix-bugs` manual workflow (unchanged; still the way to code actual fixes).
- **Cross-ref:** CR085 (daily CR/Defect review — where Saiful will passively see the DEFs filed).
- **Depends on:** BugStatus Literal + investigating status + permissions allowlist (tight coupling).
