# WP11 — R55: verdict-outcome ledger (internal calibration floor)

**Worker model: Opus** (schema + scoring semantics + exclusion correctness).
**Wave 1 with a held-back step** — build everything EXCEPT the room_runner hook
immediately; the hook lands only after the dispatcher messages "WP13 accepted"
(WP13 owns `room_runner.py` in wave 1; two lanes co-editing one file is the P33
sweep that bit this project three times).

## Source design

`../fable/05_further_improvements.md` §9 is the design. Framing discipline is
load-bearing and goes in the docstrings: this is a **sanity floor** ("APPROVEs
are not systematically worse than PASSes"; "high conviction means something"),
**never** a performance claim. Simulation-only education product. Internal-only:
no user-facing surface of any kind before v1.0 — Saiful's 2026-09-02 ruling on
the internal-only half still binds; only the "own future CR" half was superseded
by "Build all" (2026-09-03): it now rides CR219.

## Scope

1. **Table + migration** — a `verdict_outcomes` table (name yours to house
   style): `room_run_id` (FK to the Room-runs table — verify the real table name
   off `RoomRunRow`, `backend/app/db/models.py:665`), `user_id`, `ticker`,
   `verdict_action`, `conviction` (if the verdict dict carries one), `size_pct`,
   `reference_price`, `reference_at`, `horizon_days`, `status`
   (`pending`/`scored`/`unscorable`), `outcome_price`, `forward_return`,
   `scored_at`, `exclusion_reason`. **You own the ONLY alembic migration in this
   wave** — run `alembic heads` before and after; a second head means another
   lane broke the rule: stop and report, don't merge heads silently.
2. **Writer hook** (HELD BACK until "WP13 accepted") — at the site where a
   COMPLETED run's verdict is banked, insert one `pending` row. Reference price =
   the price the Room actually saw this run (locate it in the run's stored
   context/verdict; if genuinely absent, capture it at bank time from the same
   profile the Room read — never a fresh quote fetched later, which would score
   the Room against data it never saw). Horizon from the run's mandate path
   (map LONG/short/medium horizons to concrete `horizon_days`; document the
   mapping in the module docstring).
3. **Scorer** — `backend/scripts/score_verdict_outcomes.py`: idempotent batch;
   rows past `reference_at + horizon_days` get the matched-horizon close via the
   existing market-data service (respect its mock fallback: a `mock_walk`-sourced
   price must mark the row `unscorable`, never silently score against a random
   walk — that is CR040 degrade-loudly applied here). Computes `forward_return`;
   flips status. No cron install — melehost ops is the dispatcher's; document
   intended cadence (daily) in the script header.
4. **Exclusions** — the standing Alpha analytics exclusions apply: the CR035
   room-benchmark synthetic users and the 2026-05-24 05:10 seed rows. Find the
   deterministic filter in the repo's analytics/reports code (CR051 lineage) and
   reuse or mirror it; if no repo copy exists, implement the filter from the
   run/user metadata pattern and document precisely what it matches. Excluded
   rows get `status=unscorable`, `exclusion_reason` set — never silently dropped.
5. **Internal surface** — one admin-gated endpoint (follow the
   `/v1/admin/config-check` gating pattern exactly) returning aggregates:
   APPROVE vs PASS forward-return distribution summary, conviction-vs-hit-rate
   buckets, counts by status. JSON only, no user-facing copy. (Where any string
   could ever reach a user, the AI is "AMI" — applies even though this endpoint
   is admin-only.)
6. **Tests** — migration up/down clean on the sqlite fixture; writer-hook unit
   (COMPLETED run ⇒ pending row; failed/outage run ⇒ none; DEF376/R51 abstain
   verdicts (`NO_VERDICT`) ⇒ none — an abstain has no call to score); scorer unit
   with mocked prices (scores past-horizon only, idempotent re-run, mock_walk ⇒
   unscorable); exclusion filter unit; endpoint auth test (403 bare, 200 with
   admin bearer).

## Lane discipline (shared checkout, 30+ live sessions)

- Touch ONLY: `backend/app/db/models.py` (append your table),
  `backend/alembic/versions/<your new file>`, your new service/script/endpoint
  files, the API router registration line, tests — and `room_runner.py` ONLY
  after the dispatcher's "WP13 accepted" message, hook-hunk only.
- Pathspec-commit only: `git commit -m "…(AT:R75 CR219)" -- <your files>`; `git
  add <exact path>` first for new files. Never bare commit / `-am` / `add -A`.
- Never edit `issue_register.md`, `cr_list.md`, `def_list.md`.
- Tests: `backend/.venv/bin/pytest backend/tests/unit/ -q`; new tests must pass
  from BOTH repo root and `backend/` CWDs (derive paths from `__file__`).
- Report commit hashes + test tail; dispatcher verifies by forensics + rerun.
