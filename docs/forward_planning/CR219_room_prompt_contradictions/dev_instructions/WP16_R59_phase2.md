# WP16 — R59 phase 2: the fixes and the guard

Dispatcher's build map over the accepted phase-1 inventory
([`R59_numbers_audit.md`](R59_numbers_audit.md) — READ IT FIRST, it is the spec;
its line numbers are pinned to commit `6394a3dc`). Sequencing follows the
audit's own §5 table, split by file-collision lanes (P33 single-writer rule).

## Wave A — dispatch immediately (files disjoint from every live lane)

| Lane | Finding | Model | Files | Spec |
|---|---|---|---|---|
| A1 | **F5** — wire numeric verification into the 1-on-1 surface | Sonnet | `backend/app/api/one_on_one.py` + tests | Audit §3-F5: `_verify_and_annotate_geometry` is a pure function of `(text, size_pct, reference_close)` (`room_runner.py:3269-3274`); call it on the 1-on-1 reply with the same reference close the sheet carries; annotate in the established `[AMI …]` voice. Also apply `_annotate_direction_against_price` if its inputs are available on this path — say in your report if they are not. Import from room_runner (or relocate nothing — do NOT move functions between modules in this pass) |
| A2 | **F2** — `key_number`/`decisive_number` check-or-strike | Sonnet | `backend/app/services/risk_officer.py` + tests | Audit §3-F2: at render time the sheet and ladder are in hand; a key_number whose numerals appear in neither is annotated `[AMI: unverifiable]` (the `_annotate_rr_against_levels` pattern) in the body and **demoted from the comb headline slot** (`risk_officer.py:416-418, 440`); the rung-derived fallback headline takes over. Numeral matching must tolerate formatting (1,234.5 vs 1234.50 vs $1.2B-style) — state your normalization rule in the module and test it |
| A3 | **Registry guard** — numeric-provenance registry + 3 enforcing checks | Sonnet | new `backend/app/services/numeric_provenance.py` (or house-style location) + one test file | Audit §5 verbatim: registry keyed (surface, field) → enum; check 1 walks `Verdict.model_fields` + `CostedStructure.model_fields` for numeric annotations and red-fails unregistered ones; check 2 pins no-silent-downgrade; check 3 asserts every CODE_CHECKED row's named callable is importable. The guard's documented non-goals (§5 "what it deliberately does not do") go in the module docstring verbatim — a green registry must never read as "every number is verified" |

## Wave B — queued (room_runner.py / cross-file; dispatch after WP15 lands)

| Lane | Finding | Model | Notes |
|---|---|---|---|
| B1 | **F1 + F3 + F6** — the sheet-figure checker for prose, headline, and kill criterion | Opus | Highest harm, largest build; audit says build it with the harness in place so it can be measured. Extract labelled numerals from analyst prose / envelope headline / kill_criterion, compare against the sheet's own values, annotate mismatches; do NOT attempt derived-arithmetic verification in the same pass |
| B2 | **F4** — `time_horizon_days` plausibility band | Haiku (mechanical; dispatcher verifies) | Clamp-and-disclose exactly like `size_pct` at `room_runner.py:2023-2025`, band mirroring `_level_is_implausible` (`room_runner.py:2750`) |
| B3 | **§13(a)** — per-rung dollar risk | Sonnet | Thread `portfolio_value` into `build_option_ladder` (`backend/app/trading_math/option_ladder.py`), add the field to `LadderOption`, render in `_rung_head`; the audit's caution binds: missing/zero portfolio value ⇒ render nothing, never `$0`. Touches risk_officer.py — MUST wait for A2's acceptance |

## Acceptance log

- **A3 ACCEPTED 2026-09-03** — `f1f641cd`, 26-row registry + 3 enforcing checks,
  10/10 on dispatcher rerun, red-fail checks empirically fired.
- **A1 ACCEPTED 2026-09-03** — `9ca2ada9`, geometry verification on the 1-on-1
  path, 7/7 on dispatcher rerun. Two dispatcher rulings on its flagged items:
  (1) **the audit trail stays raw by design** — `record_one_on_one_message`
  keeps the unannotated model turn (an LLM audit trail's job is raw
  provenance); the Journal + SSE carry the annotated text; the divergence is
  intentional, do not "fix" it. (2) `_annotate_direction_against_price` stays
  unwired here — confirmed inert without a Verdict/profile `levels` source, not
  merely unavailable; revisit only if the 1-on-1 ever grows structured levels.
  Client-visible note: the 1-on-1 reply now buffers to completion before
  presenting (the Room's own buffer-verify-present pattern) — a beat of
  latency instead of token-live streaming, so a wrong triple is never shown
  live.

- **A2 ACCEPTED 2026-09-03** — `0f9cc06d`, unconditional key_number/decisive_number
  verification with headline demotion, 80/80 on dispatcher rerun (52 new + the
  CR197/CR201 pins). The dark opt-in flag it initially shipped was removed on
  dispatcher instruction; the two reconciled fixtures were verified honest (the
  `"RSI 43"` placeholder was genuinely unquotable; pins survive on the rung's
  own `0.18`). **Two follow-ups queued:** (1) the production call site does not
  thread `profile` yet — ladder-only verification would strike honest SHEET
  quotes, so promotion hold `CR219-F2-PROFILE` is ACTIVE in
  `infra/PROMOTION_HOLD.md` until the runner-lane hunk + wiring test land
  (queue: WP14 → WP11 hook → this); (2) A3's registry rows for
  `("risk_rung", "key_number"/"decisive_number")` upgrade to `CODE_CHECKED`
  citing the risk_officer sites — A3's own commit, dispatched.

- **A2 profile thread ACCEPTED 2026-09-03** — `466c7500`: `profile=ctx.profile`
  threaded at `render_officer_turns`' single production call site
  (`room_runner.py` `_run_risk_officer`), wiring test spies the REAL call and
  asserts the built sheet arrives; sheet-only quote proven unstruck end-to-end;
  both tests sabotage-verified load-bearing. 67/67 on dispatcher rerun.
  Dispatcher verified the path is LIVE: `render_officer_turns` has exactly one
  production call site and `ROOM_RISK_OFFICER_ENABLED=true` on Alpha.
  **CR219-F2-PROFILE's clear precondition is met** — awaiting Saiful's clear.

- **B2 ACCEPTED 2026-09-03** — `0ab65a8b` (Haiku lane, hard-verified):
  `time_horizon_days` clamped to [1, 365] (mirroring
  `_MAX_EVIDENCED_HORIZON_DAYS`) with an AMI-voiced disclosure in the reason,
  exactly the `size_pct` idiom. The CR156 pin reconciliation is honest
  (docstring records the why; never-veto preserved). 147/147 on dispatcher
  rerun. Registry row upgrade for `verdict.time_horizon_days` dispatched to A3.

- **A3 final upgrades ACCEPTED 2026-09-03** — `25559c82` (key_number/
  decisive_number → CODE_CHECKED after A2) and `665477e0`
  (time_horizon_days → CODE_CHECKED after B2, both cited to real sites).
  **The registry now carries ZERO `LLM_UNVERIFIED` rows**, pinned by a
  dedicated test whose docstring scopes the claim honestly (field registry
  only — prose surfaces are B1's checker, not this). En route, the
  exhaustiveness guard made its FIRST REAL CATCH: red-failed on R60's two
  new `Verdict` fields (`reference_price`, `next_convene_delta`), which A3
  classified COMPUTED by reading the code. 14/14 on dispatcher rerun.

## Lane discipline (all lanes)

Shared checkout, many sessions: touch ONLY your lane's files; pathspec-commit
(`git commit -m "…(AT:R75 CR219)" -- <files>`), `git add <exact path>` first for
new files, never bare/`-am`/`add -A`; never edit the registers. Tests:
`backend/.venv/bin/pytest backend/tests/unit/ -q`, passing from repo root AND
`backend/` CWDs. Report = commit hashes + test tails; acceptance by dispatcher
forensics + rerun.
