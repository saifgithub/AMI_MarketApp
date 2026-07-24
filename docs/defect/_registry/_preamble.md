# Defect register — AMI Trade

<!-- GENERATED FILE — do not hand-edit. Source of truth: docs/defect/_registry/<DEF###>.row.md
     (one file per defect). Rebuild: python scripts/registers/gen_registers.py gen def. CR081. -->
> **Generated — do not hand-edit this table.** Each row's source is
> `_registry/<DEF###>.row.md` (one file per defect); rebuild with
> `scripts/registers/gen_registers.py gen def`. See [How to add a defect](#how-to-add-a-defect).

The processed record of every **defect** — a thing that is broken or wrong versus the
spec. Two sources feed it:

- **User-reported** — filed in-app (`POST /v1/feedback/bug` → `bug_reports` table on
  melehost), triaged by [`/fix-bugs`](../../.claude/commands/fix-bugs.md). The DB is the
  intake queue; **this file is the processed record.** When a report is worked, it gets a
  `DEF###` here.
- **Prompt-reported** — a defect Saiful (or Claude) spots in a session with no in-app
  report behind it. No `bug_reports` row; still gets a `DEF###` here when processed.

Sibling register for *planned* change (new work, not fixes): [`../forward_planning/cr_list.md`](../forward_planning/cr_list.md).
Governance rationale: decision **D-058** in [`../initial_specs/11_decisions/decision_log.md`](../initial_specs/11_decisions/decision_log.md).

## How to add a defect

**This table is generated** — never edit it by hand. A shared monolithic table gets
*swept*: on the shared `main` checkout the second committer captures the whole index and
silently steals another track's uncommitted rows (the 2026-07-24 DEF095/096 incident —
[CR081](../forward_planning/CR081_registers_are_architect_write_only/CR081_registers_are_architect_write_only.md)).
One file per item removes the shared write entirely. Instead:

1. **The Architect mints the ID.** Ask for the next `DEF###` (zero-padded, sequential,
   never reused) — one minter avoids the ID-collision race. Pre-triage items use a
   topic-slug handle until the ID is assigned.
2. **The item's domain owner writes one row file** — `_registry/DEF###.row.md` containing
   that defect's single markdown table row (columns below). One file per item is a disjoint
   write-path, so two tracks never collide. **Source** is `bug:<short-id>` (first 8 chars of
   the `bug_reports.id` UUID) for user-reported, or `prompt` for prompt-reported.
3. **Regenerate + pathspec-commit:** `python scripts/registers/gen_registers.py gen def`,
   then `git commit -m "…" -- docs/defect/_registry/DEF###.row.md docs/defect/def_list.md`.
   Never bare `git commit` / `-am` / `git add -A` (those re-introduce the sweep).
4. Fix it on a branch; the fix commit carries `fix(bug:<short-id>): <summary> (AT:R<N> DEF###)`
   (user-reported) or `fix(<scope>): <summary> (AT:R<N> DEF###)` (prompt-reported). Update
   your row file's **Fix** hash + **Status** and regenerate.
5. For a defect needing its own root-cause / design write-up, create
   `docs/defect/DEF###_<snake_case_topic>/` and link it from the row.

**Status** mirrors the operational lifecycle: `resolved` · `wont_fix` · `closed` (fixed
out-of-band) · `open` (in the DB, not yet worked — not usually listed here until processed).

## Register

DEF001–DEF036 are the backfill of every processed in-app report as of 2026-07-05
(the `bug_reports` table had 32 `resolved`, 3 `wont_fix`, 1 `closed`, 0 `open`).

| DEF | Date | Source | Category | Title | Status | Fix | Session |
|---|---|---|---|---|---|---|---|
