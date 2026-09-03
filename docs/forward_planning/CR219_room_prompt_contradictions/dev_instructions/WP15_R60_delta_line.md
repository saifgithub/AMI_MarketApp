# WP15 — R60: "what changed since your last convene" delta line

**Worker model: Sonnet.** **Wave 3 — do NOT start until the dispatcher says
"WP14 accepted"** (`room_runner.py` / `room_prompts.py` are single-writer lanes
in this build; P33).

## Source design

`../fable/05_further_improvements.md` §14. Runs are persisted
(`RoomRunRow`, `models.py:665` — `user_id` + `ticker` indexed, `transcript` +
`verdict` JSONB). When a user re-convenes a ticker, the Room should explain what
changed instead of silently re-deciding. Pairs with R52's kill criterion: the
prior verdict's kill criterion is checked FIRST.

## Scope

1. **Persist the comparison basis** — at verdict-bank time (COMPLETED runs
   only), store into the verdict dict: a compact `sheet_state` map
   (`field → state` from this run's `field_state`) and the reference price the
   Room saw. No migration — it rides the existing JSONB. (If R52's
   `kill_criterion` isn't already in the verdict dict, locate where it lands and
   use that; do not duplicate it.)
2. **Prior-run lookup** — latest prior COMPLETED run for (user_id, ticker)
   before this one. Runs banked before this WP ships have no `sheet_state`;
   handle both shapes (price + verdict + kill criterion still usable; field
   diffs just absent).
3. **The delta line** — code-built, injected ONCE into the PM's VERDICT-phase
   prompt (near the R50 scoreboard block, `room_prompts.py:1731-1853` — follow
   its injection idiom): prior action + date, price move since (prior reference
   price → this run's price, %), `field_state` transitions (e.g.
   `margin_trend: LIVE → UNAVAILABLE`), and the prior kill criterion with the
   instruction to address whether it triggered. Built by code from stored data —
   the LLM never composes the delta itself.
4. **First convene / no usable prior** — no line at all. Not "no prior data":
   absence, not noise (the R38 note's no-segment framing, same logic). A prior
   run whose verdict was an outage abstain (`NO_VERDICT`, R51/DEF376) is NOT a
   usable prior for action/kill-criterion (skip to the next-older COMPLETED run
   with a real verdict, or render nothing); its date/price may still inform the
   line only if you keep the logic simple — prefer skipping entirely.
5. **API surface** — add the built delta (structured: prior_date, prior_action,
   price_move_pct, changed_fields, prior_kill_criterion) to the run response the
   card reads, so mobile can render it later. Backend-only in this WP: no
   Flutter work. Any human-readable string in it says "AMI", never "the AI".
   Flag in your report that the card copy is a NEW user-visible surface for the
   i18n lane when mobile picks it up.

## Tests

Bank-time persistence shape; lookup picks the right prior (ordering, other-user
isolation, other-ticker isolation); delta correctness on a two-run fixture
(price move %, field transitions); first-run ⇒ no injection and no API field;
abstain-prior skipped; injection appears exactly once in the assembled PM prompt
(extend the existing assembly-test idiom); old-shape prior (no `sheet_state`)
degrades to the partial line without error.

## Lane discipline (shared checkout, 30+ live sessions)

- Touch ONLY: `room_runner.py` (bank-time + lookup + injection call),
  `room_prompts.py` (the block builder), the run-response schema file, your
  tests.
- Pathspec-commit only (`…(AT:R75 CR219)`); `git add <exact path>` first for
  new files; never bare / `-am` / `add -A`. Never edit the registers.
- Tests: `backend/.venv/bin/pytest backend/tests/unit/ -q`; pass from both repo
  root and `backend/` CWDs.
- Report commit hashes + test tail; dispatcher verifies by forensics + rerun.
