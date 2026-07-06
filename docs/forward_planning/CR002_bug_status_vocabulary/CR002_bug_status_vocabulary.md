# CR002 — Reconcile the `bug_reports` status vocabulary

**Status:** proposed · **Session:** AT:R49 · **Date:** 2026-07-06
**Source:** Flagged at the close of CR001 (AT:R48) — *"the `bug_reports` status
vocabularies still disagree … Worth its own small CR if you want it reconciled"* — and
picked up by Saiful: *"create and document the CR."*

## Problem

`bug_reports.status` is a free-text VARCHAR (deliberately not a Postgres enum — see the
docstring in [`backend/app/schemas/feedback.py`](../../../backend/app/schemas/feedback.py)).
Three sources define what values are legal, and they disagree:

| Source | Status values | Where |
|---|---|---|
| **Pydantic `BugStatus`** | `open`, `triaged`, `fixed`, `wont_fix` | [`backend/app/schemas/feedback.py:24`](../../../backend/app/schemas/feedback.py) |
| **Operational lifecycle** (`/fix-bugs` + session-config) | `open` → `in_progress` → `pending_review` → `resolved`, plus `wont_fix` | [`.claude/commands/fix-bugs.md`](../../../.claude/commands/fix-bugs.md), [`.claude/session-config.yml`](../../../.claude/session-config.yml) |
| **DB actual** (distinct values today) | `resolved`, `wont_fix`, `closed` | melehost `ami_postgres` |

Concretely:

- `triaged` and `fixed` exist **only** in the Pydantic Literal — never written, never queried, never in the DB.
- `in_progress`, `pending_review`, `resolved`, `closed` are written operationally and/or present in the DB but are **not** in the Pydantic Literal.
- `open` and `wont_fix` are the only two values all three sources agree on.

### Why it matters (latent, not yet live)

`BugStatus` gates `BugReportResponse.status` at
[`feedback.py:57`](../../../backend/app/schemas/feedback.py). The only endpoint returning
that schema today is the create path (`POST /v1/feedback/bug`), which always sets
`status="open"` — a legal value — so nothing breaks right now. **The moment a read / list /
detail / admin-triage endpoint returns a report in any operational state** (`in_progress`,
`pending_review`, `resolved`, `closed`), Pydantic raises a `ValidationError` on
serialization. The mismatch is a dormant landmine, not a current outage. Reconciling now
removes the trap before that endpoint is built.

This is a **CR, not a Defect**: nothing is broken versus spec today — we are changing the
schema of record to make it honest and future-proof. (The dormant risk it removes is why
it's worth doing before, not after, the triage endpoint exists.)

## Recommended approach

Adopt the **operational lifecycle** as canonical — it's what the system actually writes and
queries — and make the Pydantic Literal tell the truth.

**Canonical status set (5):** `open` · `in_progress` · `pending_review` · `resolved` · `wont_fix`

- **Drop** `triaged` and `fixed` (dead values, zero rows).
- **Fold** `closed` → `resolved`. `closed` appears on exactly one row (DEF011, `eeeb866f`,
  fixed AT:R34 commit `3f4022a`); it's semantically "resolved out-of-band." One-off, not
  worth a distinct terminal state.

Lifecycle (unchanged, just now the whole vocabulary): `open → in_progress → pending_review →
resolved`; `wont_fix` is terminal from any state. `/fix-bugs` only ever sets `in_progress`
and `pending_review`; `resolved` is the merge-confirmation flip (Saiful / post-merge hook).

*Alternative considered:* keep `closed` as a 6th terminal state (distinguish "fixed but not
via the review flow"). Rejected for a 1-row case — but it's a one-word change if Saiful
prefers to keep it.

## Scope

1. **Schema** — update `BugStatus` in [`backend/app/schemas/feedback.py:24`](../../../backend/app/schemas/feedback.py)
   to the canonical 5. (Category Literal is untouched — it already matches.)
2. **DB migration (one-off, on melehost)** — `UPDATE bug_reports SET status='resolved' WHERE status='closed';`
   (1 row). No DDL — column stays VARCHAR per the existing design note.
3. **Docs** — `def_list.md`: change DEF011 `closed` → `resolved`; drop `closed` from the
   "Status" legend line. `fix-bugs.md` recovery/lifecycle text already uses the canonical
   set — verify, no change expected.
4. **Test** — a small unit test asserting the round-trip of each canonical status through
   `BugReportResponse` (guards against re-drift and documents intent).

## Acceptance

- `BugStatus` Literal == the 5 canonical values == the distinct `status` values in the DB
  after migration (`SELECT DISTINCT status` returns a subset of the 5).
- No occurrence of `triaged`, `fixed`, or `closed` in `backend/`, `.claude/`, or `docs/`
  (grep clean).
- `BugReportResponse(status="resolved")` (and each other canonical value) validates instead
  of raising.
- `pytest backend/tests/unit/ -q` green.

## Out of scope / notes

- **No admin/triage endpoint** — that's separate work; this CR only makes the vocabulary
  ready for it.
- **No Postgres enum / CHECK constraint** — the app-level Literal stays the single source of
  truth; the DB column stays VARCHAR (keeps migrations trivial, per the feedback.py rationale).
- **Requires a promotion** — schema + DB-data change lands on Alpha via `/promote-to-alpha`
  (Saiful triggers). Because of that, this CR is filed `proposed` and held for the go-ahead
  rather than executed inline. Say the word and I'll ship steps 1–4 + promote.
