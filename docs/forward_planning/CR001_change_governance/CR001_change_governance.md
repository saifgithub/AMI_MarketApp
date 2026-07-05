# CR001 — Change governance: CR/Defect registers + docs restructure

**Status:** done · **Session:** AT:R48 · **Date:** 2026-07-05
**Source:** Saiful — *"we need to put some governance on this project. any changes now must
be documented as a CR or as a Defect. we have this in the DB from the user reports and
responses, but we dont have this from the prompt somehow."*

This CR dogfoods the process it introduces: it is filed as CR001 and its own commits carry
the `CR001` tag.

## Problem

Change arrived through two doors, only one of which was tracked:

- **User-reported defects** had a full pipeline — in-app report → `bug_reports` table on
  melehost → [`/fix-bugs`](../../../.claude/commands/fix-bugs.md) triage → `fix(bug:<short-id>)`
  commit. Traceable end to end.
- **Prompt-originated change** — Saiful asking Claude to build or change something in a
  session — left no register entry. The only trace was a session-tagged commit `(AT:R<N>)`,
  which says *which session* but not *what change* or *why*. No before-the-fact record of
  intent, scope, or acceptance.

The gap: no register for planned change, and no single place that answers "what changed and
why" for prompt-driven work.

## Decision (see D-058)

Every change is documented as a **CR** (planned change) or a **Defect** (fixing something
broken), captured in a docs-based register.

- **Registers live in `docs/`**, not the DB. The DB (`bug_reports`) stays the *intake* for
  user reports; the markdown lists are the *processed record*.
- **Enforcement is convention-only** — documented rule, Claude self-enforces each session.
  No git hooks, no promotion-time gate. (Enforcement can harden later without changing the
  registers.)
- **CR flow is auto-file-proceed** — the prompt is the approval.
- **Exemptions:** process commits (handover wraps, version bumps, docs-only) need no ID.
- **Processed user-reported defects** are appended to `def_list.md`, so the register is the
  full picture regardless of source.

## Scope

Delivered in this CR:

1. **Docs restructure** — the 12 numbered spec folders (`00_overview`…`11_decisions`) moved
   under `docs/initial_specs/`, separating the *original build spec* from the new
   *forward-planning* and *defect* trees. All ~85 inbound path references rewritten;
   relative links inside the moved tree corrected for the extra directory level.
2. **`docs/defect/def_list.md`** — defect register, backfilled with DEF001–DEF036 (every
   processed in-app report). Per-major-defect folders `DEF###_<topic>/` created on demand.
3. **`docs/forward_planning/cr_list.md`** — CR register + this `CR001_change_governance/`
   folder.
4. **`CLAUDE.md`** — new "Change governance" section; all doc links repointed.
5. **`docs/initial_specs/08_tech/coding_conventions.md`** — commit-message convention written
   down for the first time (type/scope/summary + `(AT:R<N> [CR###|DEF###])` + exemptions +
   the `fix(bug:<short-id>)` rule).
6. **`docs/initial_specs/11_decisions/decision_log.md`** — D-058.
7. **`/fix-bugs`** — on fixing a report, also assigns a DEF ID and appends to `def_list.md`.
8. **`/handover`** — consistency scan surfaces (non-blocking) session commits missing a
   CR/DEF tag and checks the registers were updated.

Out of scope (deliberately): DB schema changes, admin/triage endpoints, git hooks, any
promotion gate. The `bug_reports` status-vocabulary mismatch (Pydantic `BugStatus` vs the
operational `in_progress`/`pending_review` set) is noted but not reconciled here.

## Acceptance

- `git grep -E 'docs/(00|…|11)_'` (excluding `Silent_Scout/`, `history/`, command archive)
  returns zero bare references — every one is `docs/initial_specs/…`.
- Clickable doc links resolve from their new depth (spot-checked: CLAUDE.md, infra READMEs,
  decision-log `Affects`, promotion_protocol command links).
- `def_list.md` holds 36 backfilled rows; `cr_list.md` holds CR001 = done with this folder.
- `pytest backend/tests/unit/ -q` green and `flutter analyze --no-fatal-infos` clean —
  proving the rewrite touched only comments/docstrings, no runtime behaviour.
- CLAUDE.md, coding_conventions.md, and the decision log all describe the same convention.

No promotion — docs and code comments only, zero backend/mobile behaviour change.
