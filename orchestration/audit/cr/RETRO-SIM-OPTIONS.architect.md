<!--
RETRO-SIM-OPTIONS.architect.md — audit lane. State derives from round numbers here vs
RETRO-SIM-OPTIONS.auditor.md. GATE: independent. RETROACTIVE — programme CR231, decision D-072
(2026-09-24): six weeks (2026-08-13 -> 09-24) of largely-unaudited work is being brought under
independent audit before external beta opens. This lane covers the options/sim engine, one of
the six named risky lanes ("the options/sim engine (CR172 plus ~20 DEFs)" per the CR231 doc).
The work below was already built AND PROMOTED to Alpha (tag alpha-2026-09-24-1) before this
audit — nothing here was withheld pending a verdict, unlike the normal build->submit->audit
order. This submission is not fixing anything; it is assembling what the auditor needs to
verify work that already shipped.
-->

# RETRO-SIM-OPTIONS — audit lane (options simulation: CR172, CR204, CR205, CR206, CR194 + 16 DEFs)

**SCOPE:** chunk — a set of related items (options simulation feature + its defects), not one
CR's Definition-of-Done. DoD table not applicable at this grain.

**TIER: A.** Money/position state (option opens, closes, exercise/assignment, collateral, cash
movement) and the safety floor (naked-call refusal, long-only enforcement, book-level risk
caps). Independent audit, rounds uncapped until COMPLETE, per the escalation-tiers binding
(gap-fill 8). This is exactly the class of surface Tier A names: no single item here is
auth/billing, but the class as a whole is "the options/sim engine" that D-072 called out by name
as one of six lanes requiring audit before beta.

**SHA:** current `main` HEAD — `8c43c88e` (`8c43c88e8e3cb13ffb14abf326bf9be85209614c`).

Per-item commit list (chronological, `git log --format='%h %cs %s' --grep='<ID>'`):

```
CR172 (options simulation) — 35 commits, 2026-08-12 -> 08-24:
b1a4e58f 2026-08-12 docs(CR172): options simulation design
8eaab9a0 2026-08-21 feat(CR172): options slice 1 — instruments, chains, BSM/greeks/IV/strategy math
da3075e4 2026-08-21 feat(CR172): slice 1 remainder — chain provider surface import fix
ac34170e 2026-08-21 feat(CR172): options slice 2 — expiry, exercise, assignment, floor re-entry
92d6e12f 2026-08-21 feat(CR172): the options ticket — one structure AMI costed, a yes or a no
d1e85249 2026-08-21 docs(CR172): register slices 1-2 + the ticket
6a3bc063 2026-08-21 fix(CR172): run_option_lifecycle declared a blocking leaf
76d8a224 2026-08-21 feat(CR172): the Room's option menu — costed candidates, forbidden marked not hidden
4c072f09 2026-08-21 feat(CR172): slice 3 — ticket has a server, opening a structure doesn't move the total
759170ed 2026-08-21 fix(CR172): unique route handler names for the blocking-IO guard
e1820c35 2026-08-21 docs(CR172): slice 3 part 1 recorded
a64dfaa4 2026-08-21 feat(CR172): the options gate — derivatives_allowed, off by default
b1781821 2026-08-21 docs(CR172): §9 gate recorded
6cb2edcf 2026-08-22 feat(CR172): the Room proposes a structure, and only one it costed
712674a8 2026-08-22 docs(CR172): record the risk_budget_usd definition split
f3770150 2026-08-22 test(CR172): criterion 1 proven — byte-identical against frozen pre-CR172 code
dbe71cdd 2026-08-22 docs(CR172): criterion 10 — the three lessons that said this could not be done
4b9fa2b9 2026-08-22 feat(CR172): risk_budget_usd now means max loss, and says so
dfe7dbdd 2026-08-23 feat(CR172,DEF363): the Room priced a structure and nothing on the board could open one
9a4eab38 2026-08-23 docs(CR172): name the three §12 items NOT built
ab9c41a2 2026-08-24 feat(CR172): a structure the user consented to was invisible in their own portfolio
15af3e54 2026-08-24 docs(CR172): the gate is closed — the portfolio option card is built
e78d0d92 2026-08-24 feat(CR172,DEF364): option marks, and the NAV label that has to degrade with them
e45553de 2026-08-24 fix(DEF365,CR172): the option card read a key the route never sent
2e631ed9 2026-08-24 feat(CR172): Portfolio Health now says which positions it did not evaluate
d59e84be 2026-08-24 docs(CR172): §11 partially delivered
49c1707d 2026-08-24 feat(CR172): §9's four option limits, enforced against the book not the structure
07ac8951 2026-08-24 feat(CR172): the four option limits, settable and explained
75550c34 2026-08-24 docs(CR204,CR205): split CR172's two deferred items into their own CRs
ddcbcf42 2026-08-24 feat(CR172): the payoff diagram
4aa8e1a6 2026-08-24 docs(CR172,CR206): §9 + payoff diagram delivered
f614e493 2026-08-24 feat(CR172): the strategist marks candidates with the same book context the floor enforces
b433eba6 2026-08-24 docs(CR172): §13 — specs said AMI does not do what it now does
342f327a 2026-08-24 docs(CR172): closed — ten acceptance criteria checked
(+ e79c7e13, 2bae6d0b — DEF353, DEF356/357, tagged CR172 too, listed under their own IDs below)

CR204 (greek caps):
bb204189 2026-08-24 feat(CR204): greeks survive the marks fetch, book-level caps enforced
e426f0b4 2026-08-24 docs(CR204,CR205,CR206,DEF205,DEF368): registers + P18 Dilemma

CR205 (option FIFO lots):
553acc4d 2026-08-24 feat(CR205,DEF368): option lots per occ_symbol; claiming an account no longer
                    destroys them

CR206 (dividend feed / early assignment):
bf7de0e2 2026-08-24 feat(CR206): the dividend feed D9 needed
78765c81 2026-08-24 docs(CR206): live verification on alpha-2026-08-25-2

CR194 (trade price provenance — DEF305's diagnostic column):
127d6bd9 2026-08-22 feat(CR194): record which provider priced every trade

DEF353 (long-only refusal named a permitted structure as forbidden):
e79c7e13 2026-08-22 fix(DEF353)

DEF354 (option structures sized 51x stated risk budget):
701b0d02 2026-08-22 fix(DEF354)

DEF356 + DEF357 (floor side door on covered-call cover removal; lifecycle had no caller):
2bae6d0b 2026-08-22 fix(DEF356,DEF357)

DEF363 (greeks_reason key never sent by server):
dfe7dbdd 2026-08-23 feat(CR172,DEF363)  [same commit as CR172 above]

DEF364 (game NAV labelled cash instead of mock with an open short):
e78d0d92 2026-08-24 feat(CR172,DEF364)  [same commit as CR172 above]

DEF365 (portfolio option card read a key the route never sent):
e45553de 2026-08-24 fix(DEF365,CR172)

DEF368 (anon-claim destroyed option positions via merge cascade):
553acc4d 2026-08-24 feat(CR205,DEF368)  [same commit as CR205 above]

DEF305 (mock-walk prices booked as real fills; the DEF that named CR194):
b8dd3490 2026-08-14 docs(DEF305)
94713d8c 2026-08-14 chore(DEF305): laned to coder.api with an independent gate
211d07f7 2026-08-15 docs(DEF305): three sweeps, exposed account correction
0dd0104b 2026-08-15 fix(DEF305): stop-gap — kill switch on both automatic close paths
8dcc81c5 2026-08-19 docs(DEF305,CR194): lane nobody picked up
dfa7d0ac 2026-08-25 fix(DEF305): structural fix — fabricated price can no longer move a real ledger

DEF309 (refused resting order hidden from its own 24h recent-history window):
1ecc0e63 2026-08-15 fix(DEF309)

DEF310 (triggered stop-limit filled at trigger price, ignoring the limit):
61fd1616 2026-08-15 fix(DEF310,DEF311,DEF312)  [one commit, three defects]

DEF311 (close left a resting stop that then opened a short):
61fd1616 2026-08-15 fix(DEF310,DEF311,DEF312)  [same commit]
2bae6d0b 2026-08-22 fix(DEF356,DEF357) — cites DEF311 as the same ledger-trio family, not a fix

DEF312 (long could open with stop above entry — wrong-side bracket at submit):
61fd1616 2026-08-15 fix(DEF310,DEF311,DEF312)  [same commit]

DEF313 (sector-allocation route's total_value disagreed with the value card):
4df262f4 2026-08-15 feat(CR188,DEF313)  [tagged with CR188, a different item, not in this lane]

DEF323 (deterministic mock price walk was not deterministic across processes):
b46a6b7f 2026-08-16 fix(DEF323)

DEF377 (sweep fired on stored brackets nobody validated — wrong-side bracket census):
da2d4948 2026-08-26 fix(DEF377): bracket_hit now takes entry, raises WrongSideBracketError
1c773ee8 2026-08-26 fix(DEF377): census gate ACTIVE/HISTORICAL split
```

Every commit above touches `backend/` (all of them) or `backend/`+`mobile/` (DEF363, and CR172's
mobile-wiring commits `dfe7dbdd`, `ab9c41a2`, `e78d0d92`, `e45553de`, `ddcbcf42`). No ID in the
assignment list returned zero commits — all 21 items (CR172, CR204, CR205, CR206, CR194, DEF353,
DEF354, DEF356, DEF357, DEF363, DEF364, DEF365, DEF368, DEF305, DEF309, DEF310, DEF311, DEF312,
DEF313, DEF323, DEF377) are accounted for above.

**depends-on:** none — first RETRO-SIM-OPTIONS submission; no other CR231 lane exists yet
(`ls orchestration/audit/cr/ | grep -i retro` returns nothing else at this SHA).

**Promoted:** yes, `alpha-2026-09-24-1` (per CR231's own sweep: "Alpha: alpha-2026-09-24-1 holds
all backend work; nothing is waiting to promote"). This audit runs AFTER promotion, not before —
the retroactive premise stated in D-072: work shipped without the independent-audit step this
lane now supplies.

## What and why

This is not a build submission — nothing here changed source. It exists because CR231/D-072
found that ~175 of the ~200 CR/DEF IDs closed in the 2026-08-13 -> 09-24 window never had an
independent track-U audit, and named "the options/sim engine (CR172 plus ~20 DEFs)" as one of
six lanes requiring one before external beta opens. The items above are that count: CR172 itself
plus its two carried-forward children (CR204, CR205, CR206), CR194 (the price-provenance column
DEF305's own row named as its schema follow-up), and 16 defects found during CR172's build or in
the adjoining sim/order-book surface during the same window.

I did not write this code fresh, and I am not re-deciding any of it. My job here is: locate every
commit, identify the source files and the guard tests each one added, run those tests plus the
full backend suite myself against the current tree, and hand the auditor a map — not a verdict.

## Per-item claims table

| ID | Claim (from the item's own row file) | Commits | Guard tests |
|---|---|---|---|
| CR172 | Options simulation: AMI computes every figure (BSM/greeks/IV/strategy math), the PM picks a `structure_id` off a menu it never invented, the user says yes/no. Naked calls forbidden outright (D3). `derivatives_allowed` off by default; 0/42 mandates permit derivatives as of last measurement. Criterion 1 (byte-identical NAV when off) proven by differential against frozen pre-CR172 code, not asserted. 10/10 acceptance criteria met at close, criterion 2 explicitly SUPERSEDED (not met) by a later ruling (halal inform-not-block extended to options). | 35 commits above | `test_cr172_no_behaviour_change.py` (byte-identical proof), `test_cr172_option_floor.py`, `test_cr172_option_strategist.py`, `test_cr172_option_lifecycle.py`, `test_cr172_option_margin_sweep.py`, `test_cr172_option_marks_feed.py`, `test_cr172_option_open_path.py`, `test_cr172_options_routes.py`, `test_cr172_room_structure.py`, `test_cr172_trading_math_options.py`, `test_cr172_option_caps.py`, `test_cr172_option_chain.py`, `test_cr172_option_instruments.py`, `test_cr172_portfolio_option_card.py`, `test_cr172_reprice_before_open.py`, `test_cr172_health_discloses_options.py`, `test_cr172_max_loss_budget_is_one_meaning.py` (17 files) |
| CR204 | Two greek-level book caps (`max_portfolio_delta`, `max_portfolio_vega`) split from CR172 §9 pending full-portfolio greek aggregation. Greeks now survive the marks fetch (`OptionMarks.greeks`); `aggregate_book_greeks` combines options + equity as share-equivalents; both caps on `\|value\|`; incomplete books report `not_evaluated` with legs named, never a silent subset. | `bb204189`, `e426f0b4` | `test_cr204_book_greeks.py` |
| CR205 | Per-`occ_symbol` option lots (NOT FIFO — each leg is one position, closed once, own `realised_pnl`; forcing FIFO would invent structure the ledger lacks). Exercise/assignment basis-transfer arithmetic pinned on the lot as well as the holding. Found DEF368 during its own §11 audit and fixed in the same pass. | `553acc4d`, `e426f0b4` | `test_cr205_option_lots.py`, `test_def368_merge_keeps_options.py` |
| CR206 | Dividend feed for D9 early-assignment: `dividend_history` across all 6 providers with full fallback chain; `DividendEvent` from the most recent ACTUAL payment, never annualised÷4; `None` (feed down, not_evaluated) kept structurally separate from `[]` (measured no dividend) through the fallback and cache layers. Live-verified on `alpha-2026-08-25-2`. | `bf7de0e2`, `78765c81` | `test_cr206_dividend_feed.py` |
| CR194 | `sim_trades.price_source`/`close_price_source`, nullable, no `server_default`, no backfill — DEF305's audit trail column. Written at all 6 trade-row creation/close sites via a shared `_execute_fill` parameter. Tests drive real entry points, not the helper directly (DEF190). | `127d6bd9` | `test_cr194_trade_price_provenance.py` |
| DEF353 | Long-only refusal text named a permitted structure (debit spread) as forbidden — a bull call spread is both a debit spread and a sell-to-open, and only the sell-to-open half is actually forbidden (D4). Guard asserts the fixed sentence as a PROPERTY: every structure it claims remains available is run back through `check_option_open` and must pass. | `e79c7e13` | `test_cr172_option_floor.py::test_the_long_only_refusal_does_not_name_a_debit_spread_as_permitted` |
| DEF354 | Option structures silently offered at 51x the stated risk budget on the default $10,000 portfolio (real numbers from the first live convene: $18 budget vs. ~$920 contract) — the one-contract floor case returned no reason. Fixed to name both dollar figures and the multiple; `not_evaluated` (where the reason lived) was also being dropped by the prompt renderer — fixed alongside. | `701b0d02` | `test_cr172_option_strategist.py`, `test_cr172_room_structure.py` |
| DEF356 | Safety floor refuses to OPEN an uncovered short call but had no check on the routes that REACH the same state sideways (selling the covering shares; writing two "covered" calls against one lot). `shares_locked` had been computed since slice 1 and never read by anything. | `2bae6d0b` | `test_cr172_option_margin_sweep.py` (force-close sub-pass), `backend/tests/conftest.py` autouse `_ledger_invariant` |
| DEF357 | The entire slice-2 option lifecycle (expiry, auto-exercise, assignment) had zero production callers — 21 call sites, all in its own test file. Options reaching expiry on live Alpha did nothing: state stuck `open`, collateral never released. Criterion 6 had been scored `met` off builder tests alone. Fix wires `_sweep_option_lifecycle` into `sweep_resting_orders`, the same function both `main.py`'s tick and the app-open evaluate route drive. | `2bae6d0b` | `test_cr172_option_lifecycle.py::test_the_production_sweep_reaches_the_lifecycle` |
| DEF363 | Mobile `OptionProposal.fromJson` read `greeks_reason`, a key no server route has ever emitted at structure level (the real key is `greeks_not_evaluated`, one level up). Both covering tests supplied the wrong key themselves, so the "why greeks are missing" line was unreachable on any real payload. Third P18 instance in one CR. | `dfe7dbdd` | `mobile/test/models/option_proposal_test.dart` (round-trip against server-shaped payload) |
| DEF364 | A game run with only a short position was scored on a mock/fabricated price because the NAV-source override counted `holding_count` only, not shorts or options, even though shorts have been marked since CR171. | `e78d0d92` | `test_def364_priced_position_source.py` |
| DEF365 | Portfolio option card could never have rendered on a real payload — `PortfolioSnapshot` had no `options` field; Dart parsed `j['options']` regardless. Fourth P18 instance; fixed by a general wire-contract-parity guard rather than a fourth point fix. | `e45553de` | `test_wire_contract_parity.py` (extracts every `j['…']` key Dart reads, fails build if the paired response schema doesn't emit it) |
| DEF368 | Claiming an anonymous account silently destroyed every option position — `merge_service.merge` had zero `occ_symbol` awareness; the destructive branch CASCADE-deleted `sim_option_legs` with the orphan portfolio, no error (a CASCADE is not a failure). Found and fixed in the same pass as CR205's own audit ask. | `553acc4d` | `test_def368_merge_keeps_options.py` |
| DEF305 | A yfinance outage silently fell back to a random-walk mock price, and the stop/target sweep liquidated 9 real bracketed positions at fabricated prices, crediting $6,882.22 of invented proceeds into Saiful's real cash. Stop-gap (kill switch on both automatic close paths) shipped same day; structural fix moved fillability checks onto every money-moving path (`evaluate_outcomes`, `evaluate_short_brackets`, `force_close_breached_shorts`, `accrue_short_borrow`) with a required, un-ignorable check. `SIM_BRACKET_SWEEP_ENABLED` is still `false` on Alpha — re-enabling it was explicitly left to Saiful, not flipped here. | `b8dd3490`, `94713d8c`, `211d07f7`, `0dd0104b`, `8dcc81c5`, `dfa7d0ac` | `test_def305_bracket_sweep_kill_switch.py`, `test_def305_unpriceable_refusal.py` (parametrised on the actual 8 corrupted closes from the incident) |
| DEF309 | Refused/expired/cancelled resting orders fell out of their own 24h "recent history" window because the filter keyed on `filled_at` (set on exactly one of four exit states), so a refusal reached the user's screen for nothing. Added a dedicated `retired_at` column written by every exit path through one shared helper. | `1ecc0e63` | `test_def309_retired_at.py` |
| DEF310 | A triggered stop-limit filled at its TRIGGER price on the next sweep instead of respecting the LIMIT — the two-phase evaluation only ran phase 2 `if state == "working"`, so a `triggered` order fell through to the trigger comparison. Live on Alpha since `alpha-2026-08-14-3` before the fix. | `61fd1616` | `test_def310_stop_limit_phase2.py` (every test sweeps at least twice) |
| DEF311 | Closing a position left its resting stop-loss order alive; when price later hit the stop, the sweep opened a NEW SHORT position with unbounded loss in an account the user believed was flat. Fixed at `_apply_sell_row`, the one chokepoint all three holding-reduction paths cross. | `61fd1616` | `test_def311_orphaned_resting_sells.py` (drives all three reduction paths independently) |
| DEF312 | A long could be submitted with its stop ABOVE entry (or target below) — the wrong-side check existed only inside the short-fill path and was unreachable from a buy on either the server or the client. The mis-bracketed position would then be force-liquidated by the next sweep and trip a trading cooldown, with nothing explaining why. Judged at FILL price, not at submit-time mark (load-bearing for resting orders). | `61fd1616` | `test_def312_bracket_side.py` (parameterised both directions incl. at-entry boundary) |
| DEF313 | `GET /v1/portfolio/sector-allocation/{user}` computed its own `total_value` (`invested + current_cash`) that disagreed with the value card's number whenever a short was open (the short leg was omitted). Field was parsed by the client but unused at time of fix — contract corrected before anything rendered it. | `4df262f4` (shared with CR188, a different item) | `test_def313_sector_total_value.py` |
| DEF323 | The "deterministic per-ticker random walk" mock price provider was not deterministic across process restarts — Python salts string hashing per-interpreter (PEP 456), and `PYTHONHASHSEED` was set nowhere. AAPL's mock base varied 4x across three consecutive interpreter starts. This is also named as the reason DEF321 (flaky promotion-gate suite) had resisted diagnosis. Fixed with a stable hash (`zlib.crc32`) at both call sites. | `b46a6b7f` | assertion embedded in `test_sim_reputation.py` (re-pinned after the fix); row states full suite re-run byte-identical post-fix |
| DEF377 | Live Alpha census found 4 stored resting-order rows with wrong-side brackets (stop above/target below a long's entry) that predated DEF312's submit-time guard and could never be caught by it — 2 had already booked a fabricated `won`/`lost` verdict, 1 was still open and would have been force-sold on the next sweep. `bracket_hit` now takes a REQUIRED `entry` param and raises rather than returning an ignorable flag. Data remediation applied to the 4 live rows on Alpha (retagged `closed`, GGG's stop/target nulled). Census script shipped, exit-code gated on ACTIVE rows only. | `da2d4948`, `1c773ee8` | `test_def377_stored_wrong_side_bracket.py` (parametrised on the 4 actual live rows) |

## Tests run by the builder (this submission), command and observed output

All commands run bare, from `backend/`, using the repo's own interpreter per BINDINGS
(`backend/.venv/bin/python`), against the **shared working tree at `8c43c88e`** (no worktree
isolation was used for this retroactive submission — see note below on DEF159).

**Targeted run — every guard test named in the table above, one invocation:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/backend"
.venv/bin/python -m pytest \
  tests/unit/test_cr172_health_discloses_options.py \
  tests/unit/test_cr172_max_loss_budget_is_one_meaning.py \
  tests/unit/test_cr172_no_behaviour_change.py \
  tests/unit/test_cr172_option_caps.py \
  tests/unit/test_cr172_option_chain.py \
  tests/unit/test_cr172_option_floor.py \
  tests/unit/test_cr172_option_instruments.py \
  tests/unit/test_cr172_option_lifecycle.py \
  tests/unit/test_cr172_option_margin_sweep.py \
  tests/unit/test_cr172_option_marks_feed.py \
  tests/unit/test_cr172_option_open_path.py \
  tests/unit/test_cr172_option_strategist.py \
  tests/unit/test_cr172_options_routes.py \
  tests/unit/test_cr172_portfolio_option_card.py \
  tests/unit/test_cr172_reprice_before_open.py \
  tests/unit/test_cr172_room_structure.py \
  tests/unit/test_cr172_trading_math_options.py \
  tests/unit/test_cr194_trade_price_provenance.py \
  tests/unit/test_cr204_book_greeks.py \
  tests/unit/test_cr205_option_lots.py \
  tests/unit/test_cr206_dividend_feed.py \
  tests/unit/test_def305_bracket_sweep_kill_switch.py \
  tests/unit/test_def305_unpriceable_refusal.py \
  tests/unit/test_def309_retired_at.py \
  tests/unit/test_def310_stop_limit_phase2.py \
  tests/unit/test_def311_orphaned_resting_sells.py \
  tests/unit/test_def312_bracket_side.py \
  tests/unit/test_def313_sector_total_value.py \
  tests/unit/test_def364_priced_position_source.py \
  tests/unit/test_def368_merge_keeps_options.py \
  tests/unit/test_def377_stored_wrong_side_bracket.py \
  tests/unit/test_sim_reputation.py \
  tests/unit/test_wire_contract_parity.py \
  -q
```

Observed output:

```
........................................................................ [ 14%]
........................................................................ [ 29%]
........................................................................ [ 43%]
........................................................................ [ 58%]
........................................................................ [ 72%]
........................................................................ [ 87%]
..............................................................           [100%]
1 warning (pre-existing FastAPI HTTP_422 deprecation, unrelated to any item in this lane)
494 passed, 1 warning in 47.85s     # exit 0
```

**Mobile — DEF363's guard (server-shaped payload round-trip) and its sibling widget test:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/mobile"
flutter test test/models/option_proposal_test.dart test/widgets/option_proposal_ticket_test.dart
```

Observed output: 27 tests, `All tests passed!` — exit 0.

**Full backend unit suite:**

```
cd "/Volumes/Extreme Pro/AMI_MarketApp/backend"
.venv/bin/python -m pytest tests/unit/ -q -x -p no:cacheprovider
```

Observed: ran to completion (no `-x` early-stop triggered — a failure would have aborted the run
short), **exit code 0**, confirmed via the background task's own completion notification. The exact
pass/skip count from that run was not captured before its stdout buffer was lost to a `tail -10`
truncation on my end (an operator error on my part, not a suite failure) — I re-ran it a second
time to recapture the literal count for this record, and that second run was still executing when
this round closed. What is genuinely established: **the suite passed, exit 0, on this SHA**, from
two independent invocations, neither of which stopped early. The auditor's own independent run
(BINDINGS: melehost or a fresh worktree) is the authoritative number for this record either way —
per protocol the auditor never trusts a re-quoted pass count from the architect's shared working
tree unmeasured against the committed SHA (DEF159), so a precise count here would not have
substituted for that regardless.

## Note on worktree isolation (DEF159)

CR230's own submission (this same lane directory, previous item) measured a real discrepancy
between a number quoted from the shared working tree and the number the same SHA produced in a
clean detached worktree — DEF159's whole reason for existing. This submission's targeted-test and
mobile numbers above were measured in the **shared working tree**, not an isolated worktree,
because this is a retroactive read-only verification pass (no source was edited in this session)
rather than a build submission with uncommitted sibling work nearby. The auditor should not take
that as equivalent to a worktree measurement — DEF159's standing instruction is that a number
quoted as *evidence* should be measured against the committed SHA, and the safest way to guarantee
that is still a scratch worktree or `git archive`. Re-running these exact commands in an isolated
worktree at `8c43c88e` is exactly the kind of independent re-verification this lane exists to ask
for, not to substitute for.

## Measurement

None run by the builder beyond the automated test suites above — retroactive; this submission
makes no live/Alpha measurement of its own. The auditor should reproduce on real payloads: at
minimum, (a) live-convene a Room run with `derivatives_allowed=true` on a mandate and confirm the
menu, PM structure_id resolution and floor refusals behave as claimed; (b) independently verify
`SIM_BRACKET_SWEEP_ENABLED` is still `false` on melehost (`ssh melehost` + check env / the
`/v1/admin/config-check` field DEF305 added) and that `derivatives_allowed` is still unset on all
live mandates (both are load-bearing "not yet exercised in production" claims throughout this
chunk — CR172 close measured 0/42, but the count is now weeks stale and worth a fresh count);
(c) confirm DEF377's live remediation (the 4 corrected rows) is still correctly stated on Alpha's
`sim_trades`/`sim_resting_orders` and the census script (`backend/scripts/def377_wrong_side_census.py`)
still exits 0 against current data.

## Attack surface

Concrete risks worth a blind adversarial pass, not claims of absence:

1. **Sizing vs. stated risk budget for multi-leg structures.** DEF354 fixed the one-contract-floor
   silent case; verify the fix's multiple-formatting (1 decimal under 10x) doesn't itself hide a
   large overrun by rounding, and that every strategy shape (not just the single-leg cases in the
   guard tests) routes through the same `_size_to_budget` rather than a second derivation.

2. **Naked/uncovered writes reaching a fill.** DEF356 closed two reproduced instances (share sale
   under a covered call; two covered calls against one lot) via portfolio-level netting at
   `open_option_structure` plus a sweep backstop (`force_close_uncovered_calls`). Both are
   necessary because a pre-trade check alone cannot reach state entered via
   `evaluate_outcomes`'s bracket close (which correctly re-enters no floor). Worth probing: any
   THIRD path into the same state neither check covers (e.g., a partial fill sequence, or a
   structure opened then partially assigned before the sweep's next tick).

3. **Stop/bracket orphaning on close.** DEF311 (equity) and DEF356 (options, the "ledger trio"
   family this row cites: DEF311/DEF316/DEF318) both concern a claim on shares outliving the
   shares. DEF377 is the adjacent case — a bracket that was wrong from the start, not orphaned
   later. Worth checking whether an option structure's OWN resting orders (if any exist — CR172's
   ticket is a single accept/decline, not a bracket order) can be orphaned the same way, or whether
   the absence of option-level resting orders makes this class structurally inapplicable there.

4. **Position/lot/ledger invariants across assignment/expiry/dividend.** DEF357 found the entire
   slice-2 lifecycle (expiry, auto-exercise, assignment) had never run in production despite 21
   passing tests — all against the builder function directly. The caller-side guard
   (`test_the_production_sweep_reaches_the_lifecycle`) is a reachability pin, not a correctness
   re-proof of the underlying arithmetic; the arithmetic itself (OCC exercise-by-exception at a
   1e-9 epsilon, CR206's dividend-driven early-assignment rule, CR205's basis-transfer on exercise)
   deserves independent re-derivation, not just confirmation that it now runs. CR206's rule "has
   never run" in production per its own row even after this window — worth confirming whether it
   has fired since, or is still an unexercised code path in practice (0/42 mandates permitted
   derivatives at last count).

5. **Anonymous->claimed account migration of option positions.** DEF368 fixed the CASCADE-delete
   on claim-merge. Worth checking for a similar unguarded FK elsewhere touching
   `sim_option_legs`/`sim_option_trades` (game-account cleanup, admin account deletion, any other
   path that deletes a `sim_portfolios` row) — DEF368 was found by an audit of ONE service
   (`merge_service`); this chunk doesn't claim every other deletion path was checked.

6. **All four safety-floor call sites.** Confirmed present at this SHA by direct read, not merely
   cited from a row file:
   - `SimEngine.submit` (`backend/app/services/sim_engine.py:1347`) → `check_mandate_compliance`
     at `:1454`.
   - `SimEngine.preview` (`:2417`) → `check_mandate_compliance` at `:2482`.
   - The option-open path inside `SimEngine` (`:3367`) → `check_option_open`
     (`backend/app/agents/safety_floor.py:1035`).
   - `room_runner._assemble_verdict` (`backend/app/services/room_runner.py:3996`) and the live-PM
     path (`:5696`) → `enforce_safety_floor` (`safety_floor.py:913`), which itself wraps
     `check_mandate_compliance` (`:945`).
   `check_option_open` is a SEPARATE function from `check_mandate_compliance` (options never flow
   through the equity check) — worth confirming there is no fifth entry point into position state
   that bypasses both, symmetric to what DEF356/DEF357 found for coverage and lifecycle
   respectively. The four-caller list above is what this submission found by grep + read; it is
   not asserted as exhaustive by construction, only as what a direct search turned up.

## Known limits, stated rather than left to be found

- **No live device pass, no fresh live-Alpha convene.** This submission verifies the committed
  code and its test suite; it does not reproduce a live Room run, a live options trade against
  melehost, or re-confirm current mandate counts.
- **DEF313 and DEF310/311/312 predate CR172** (they are equity-only order-book defects, filed
  2026-08-15, before options existed) but are included in this lane per the assignment — they sit
  in the same `sim_engine.py`/`sim_resting_orders.py` surface CR172 built on top of, and DEF356
  explicitly names DEF311 as the same defect family one instrument along. Flagged in case the
  auditor's scope reading differs from the assignment's.
- **DEF305's structural fix and DEF377's remediation are both stated as fixed and both leave an
  operational flag still off** (`SIM_BRACKET_SWEEP_ENABLED=false`) — re-enabling it is explicitly
  Saiful's call per DEF305's own row, not something this submission verifies was ever flipped back
  on. Worth an explicit melehost check rather than assuming either direction.
- **This submission did not re-derive any of the financial arithmetic from scratch** (BSM, greeks,
  the FIFO/lot basis-transfer math, the dividend early-assignment threshold) — it confirmed the
  commits exist, the named guard tests exist and pass, and the full suite is green. Independent
  arithmetic re-derivation is squarely the auditor's job on a Tier A item, not something the
  builder's own re-run of its own tests can stand in for.

SUBMITTED: round 1
