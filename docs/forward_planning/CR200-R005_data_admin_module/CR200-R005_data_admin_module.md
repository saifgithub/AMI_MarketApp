# CR200-R005 — Data administration module (guarded CRUD for operators)

**Date:** 2026-10-18 · **Status:** proposed · **Track:** AT:K1
**Parent:** CR200 (Management Console) — the console's DATA module.
Grouped sub-CR per the CR200-R### convention.
**Study:** full schema + live-data inventory (2026-10-18, 64 tables
profiled on alpha; every landmine below was found in real rows, not
hypothesised).

**Filed from:** Saiful: *"I need some data manipulation tools, like
changing the user payment group etc. Study the structure and propose a
CRUD-like capability to update, query and display the data."*

There is no "payment group" entity — the thing he means is `users.plan`
(`floor_pass`/`trader`/`trial_trader`/`floor_manager`, live: 359/65/5/2).
That naming mismatch is itself finding #1 below.

---

## 1. The one design rule that decides everything

**Not blanket CRUD — three operation classes, enforced structurally:**

1. **Query/Display (read) — broad.** New admin read endpoints for every
   domain an operator must see: games (fields/entries detail), sim
   (portfolio/trade inspector), journal, market-data rows, notification
   prefs, mandates. Read-only, `get_admin`-gated, cheap to add.
2. **Corrective writes — only as verbs, never as row edits.** Every
   mutation is a purpose-built service function (or reuses an existing
   one) that keeps the ledgers and denormalised counters in lockstep in
   ONE transaction, then records `admin_audit`. There is no generic
   `UPDATE table SET …` surface, by design.
3. **No deletes** — except a designed multi-table erasure flow, which is
   its own future CR (§6). Append-only ledgers are never touched, only
   compensated.

Why: the live schema punishes naive writes everywhere —
`credit_balance` ↔ `subscription_events` and the monthly window
(`credits_period_start`/`credits_plan_at_grant`); `users.reputation` ↔
Σ `reputation_events`; `sim_portfolios.current_cash` ↔ trades + shorts +
orders; `game_fields.entrant_count` ↔ entries. Eleven landmines are
recorded in the study (NULL = "unmeasured" columns, partial unique
indexes, bare-UUID references with no FKs, the 6 house desks polluting
metrics, `token_version` invalidating every session in one write).

## 2. The headline verb — SetPlanGroup (his example, done right)

`PATCH /v1/admin/users/{id}/plan` exists but has a measured footgun:
**plan change does not re-grant credits.** The live audit trail proves
the pain — every one of the 74 `plan_changed` events is immediately
followed by a manual `credits_added` (58), each hand-paired. And 6 users
carry stale `trial_expires_at` against non-trial plans because bare plan
edits don't reconcile trial state.

`SetPlanGroup` bundles, atomically: plan change → credit re-grant to
the new plan's allowance (or explicit "keep balance" choice with the
delta shown) → trial column reconciliation → one `subscription_events`
row describing the whole transition → one `admin_audit` row. Preview
endpoint first (shows from→to plan, balance before/after, trial
effect), send second. This replaces the two-step psql ritual entirely.

## 3. Slices (priority order, each independently shippable)

1. **S1 — Billing/group admin:** SetPlanGroup (+preview); credit
   reconcile view (live anomaly: 7 users hold 1,802 / 6 hold 950 /
   4 hold 1,960 — versus allowances of 13/150/500); trial consistency
   repair for the 6 stale rows; `client_release_floors` retraction
   endpoint (raising exists, retracting is psql-only today).
2. **S2 — Support ops:** user profile corrections (display name, handle
   regen, locale/timezone, `title_ineligible`) with house-desk warning;
   `token_version` bump as an explicit confirm-gated "kill sessions"
   action; lessons/challenge progress reset for one user; journal
   tombstone restore; `notification_preferences` server-side flip.
3. **S3 — Ops repair verbs:** `game_fields` force-transition (stuck
   `entry_open` → abandon/close/archive, join_code rotate);
   `game_entries` void/withdraw; `room_runs` abort-stuck (10 rows are
   `running` now) + force `refund_recorded`; `bug_reports` status
   vocabulary aligned with reality (live rows already carry
   `investigating`/`wont_fix` written by psql lanes — the API's 3-state
   machine is fiction); market-data repair (retract a bad bar,
   deactivate a ticker).
4. **S4 — Read surface:** the query/display half of §1 — domain viewers
   feeding both the SPA tab and AMI Ops tools.

## 4. Surface

1. Admin API verbs (new `api/admin_data.py`, `get_admin`-gated,
   `AdminIdentity` operator attribution throughout).
2. Console SPA: one DATA tab per domain, reusing the users tab's
   detail-panel pattern; write actions behind the same structural
   preview/confirm pattern as CR103/CR200.
3. AMI Ops: one Dify tool per verb after each slice promotes.

## 5. Non-goals (this CR)

1. Generic row editors, SQL consoles, or table-wide update endpoints.
2. User erasure/delete (S-future, own CR — bare-UUID references with no
   FKs make it a designed sweep, plus `llm_audit`/`one_on_one_messages`
   content questions).
3. Writes to append-only ledgers except via compensating rows from the
   verbs above.
4. Housekeeping: `credit_backup_20260814` (252-row stray backup table
   not in `models.py`) is a cleanup candidate — separate defect.

## 6. Acceptance (per slice)

1. Every verb: preview → confirm → one-transaction write →
   `admin_audit` row naming operator + payload; ledgers and denorms
   provably consistent (suite asserts the lockstep).
2. SetPlanGroup: no plan change can leave credit window or trial state
   inconsistent; the two-step manual ritual is deleted from the runbook.
3. Each slice: `pytest backend/tests/unit/ -q` green; console tab +
   Dify tool live on alpha after promotion.
