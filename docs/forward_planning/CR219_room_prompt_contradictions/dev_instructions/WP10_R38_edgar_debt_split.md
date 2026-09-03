# WP10 — R38: EDGAR debt split, industrial vs. captive finance

**Worker model: Opus** (load-bearing: dimensional XBRL parsing + fact-sheet shape).
**Wave 1 — may run immediately, in parallel with WP11/WP12/WP13.**

## The spec IS the design note

Read [`R38_edgar_design_note.md`](R38_edgar_design_note.md) in full before writing
anything. It is the acknowledged, gate-lifted spec: problem, source endpoint,
cache strategy, failure modes, config flag, and an 8-point test plan. This WP adds
only the dispatcher rulings the note left open, plus lane discipline.

## Dispatcher rulings (2026-09-03, closing the note's open questions)

1. **Cache strategy: option 1** — dimensional parsing lands in `parse_companyfacts`
   (`backend/scripts/ingest_edgar_facts.py:117`), the captive-finance registry in
   `backend/app/services/edgar_tags.py`, and the Room's live path reads the split
   off the same point-in-time `edgar_facts` store the backtest trusts. No second
   EDGAR-calling code path.
2. **Flag-OFF framing: no `field_state` key at all.** A flag that is off by
   design/rollout is "feature doesn't exist yet", not "data unavailable this run".
   The note's test 5 pins exactly this.
3. **No alembic migration in this WP.** Store member-resolved dimensional facts in
   the existing `EdgarFactRow` shape under **synthetic tag names** (e.g. a clear
   `ami:` — or similarly namespaced — tag per resolved member figure), which is
   what the note's option 1 sketches ("the new dimensional facts get their own
   tags"). WP11 owns the only migration in this wave; two concurrent alembic heads
   is a known collision. If you conclude a schema change is genuinely unavoidable,
   that is the escape hatch firing: **stop and report back**, do not migrate.
4. **Ops is not yours.** Do not run the ingest against live SEC endpoints beyond
   what a test needs (fixtures are hand-built per the note's test plan — no
   network in unit tests), do not touch `infra/alpha.env`, do not enable the flag
   anywhere. `use_edgar_debt_split` defaults `False` in code and compose; the
   melehost ingest refresh + flag enable happen at promotion, dispatcher-run.

## Scope (build all of it)

- Dimensional parse: `parse_companyfacts` learns to read the per-fact `"segment"`
  axis/member object it currently discards, for the note's debt tags only
  (`DEBT_ANCHOR`/`DEBT_OPTIONAL_ADD`), resolved once for a matched
  captive-finance member and derived as whole-company-minus-member for the
  industrial remainder (the note explains why the remainder is computed, not
  looked up).
- Entity registry: CAT/Caterpillar Financial, DE/John Deere Capital, PCAR/PACCAR
  Financial as the initial three; name-matching tolerant of the real-world XBRL
  member-name variants (test 3 pins each entry).
- Live read + render: `field_state["debt_split"]` set from the store;
  `_format_profile` renders the split line with `(LIVE)` provenance per CR104.
  **The R13 exhaustive guard forces the rest**: the new rendered line needs its
  `sheet_registry.py` entry and availability-guard mapping or
  `test_cr219_sheet_registry_sync.py` / `test_cr219_availability_guard.py` go
  red — that is the mechanism working; author the entries, don't allowlist
  around them.
- The three non-error states render exactly as the note's failure-mode section
  says (no-segment ⇒ nothing extra; unresolvable-this-period ⇒ explicit
  UNAVAILABLE line; outage ⇒ loud log + UNAVAILABLE, blended total untouched).
- Config: `use_edgar_debt_split: bool = False` in `backend/app/core/config.py`,
  forwarded in `docker-compose.yml`'s `api-alpha` block
  (`test_config_compose_parity.py` enforces).
- Tests: the note's 8-point plan, every point.

## Escape hatch (verbatim from the ruling)

If the dimensional-parser work balloons beyond a contained change to
`parse_companyfacts` plus a small entity registry, **stop and report back** —
reversing to a declared-absent entry with its own CR is Saiful's call, not a
worker's.

## Lane discipline (shared checkout, 30+ live sessions)

- Touch ONLY: `backend/scripts/ingest_edgar_facts.py`,
  `backend/app/services/edgar_tags.py`, the fundamentals fetch/render seam
  (`backend/app/services/fundamentals.py` and the `_format_profile` site),
  `backend/app/services/sheet_registry.py`, `backend/app/core/config.py`,
  `docker-compose.yml` (one env line), new/extended test files.
- Pathspec-commit only: `git commit -m "…(AT:R75 CR219)" -- <your files>`. Never
  bare `git commit`, `-am`, or `git add -A`. `git add <exact path>` first for new
  files.
- Never edit `issue_register.md`, `cr_list.md`, `def_list.md` — dispatcher-only /
  generated.
- Tests run as `backend/.venv/bin/pytest backend/tests/unit/ -q` (bare `pytest`
  is broken on this Mac). New tests must pass from BOTH repo root and `backend/`
  CWDs — derive any data path from `__file__`, never CWD (DEF398's gate lesson).
- Report completion with commit hashes + the test command you ran and its tail.
  Acceptance is by dispatcher git forensics + rerun, not your claim.
