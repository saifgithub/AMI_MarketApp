<!--
RETRO-CR221-S13.architect.md — audit lane. State derives from round numbers here vs
RETRO-CR221-S13.auditor.md. RETROACTIVE audit under programme CR231 / decision D-072
(2026-09-24). This lane is CR231's Phase 1 lane 5 ("CR221 slots 1 and 3, plus the CR170/CR171
backend halves"). GATE: independent. This submission is not a build; it is the record assembled
for the auditor to verify work that already shipped without going through this handshake.
CR221 slots 2, 4 and 5 already have their own lane files (CR221-SLOT2/SLOT4/SLOT5) and are
excluded here — do not re-audit them from this lane.
-->

# RETRO-CR221-S13 — audit lane (CR221 slots 1+3+history-arm, CR170/CR171 backend, retroactive)

**SCOPE:** chunk — CR221's slot 1 (A1+A3), slot 3 (C3+C4+DEF400), and the "history arm" (C2/C5,
B2) that CR221's own doc places between slots 3 and 4; plus CR170-BE (resting orders) and
CR171-BE (short selling), which never went through this handshake either. Bundled because the
dispatching brief (CR231 Phase 1 lane 5) bundles them, not because they share one code path — CR221
is Room fact-sheet data-sourcing, CR170/CR171 are simulated trading mechanics. DoD table not
applicable at this grain.

**TIER: B** for CR221's slot 1 / slot 3 / history arm — new Room-sheet lines rendered from
external data, flag-gated and off by default on Alpha, same tier as the already-audited
CR221-SLOT4 (also Tier B, "three new Room-sheet lines"). One independent round, cap 3; a
MAJOR/BLOCKER promotes to Tier A rounds. **TIER A for CR170-BE / CR171-BE** — these move real
(simulated) money: order fill pricing, cash reservation, short-position cost/margin/borrow, and
the compliance-advisory routing on sell-to-open. Not flag-gated (shipped as unconditional
features per Saiful's explicit instruction, not behind a default-off flag), so unlike CR221's
slots this is live on every trade a user places today. Independent audit, rounds uncapped until
COMPLETE.

**SHA:** current `main` HEAD —

```
34941fa19cdc5bfa1a4739d5ad79386c75583232
```

(moved from `8c43c88e` while this lane file was being written, same as RETRO-PM-FLOOR's own note
— the one intervening commit, `34941fa1`, is the CR231 governance doc that authorizes this very
retroactive audit; it does not touch any file this lane discusses.)

This is a shared checkout, other lanes active concurrently — do not attribute commits below to
this lane that are not listed.

**depends-on:** none.

**Promoted:** yes — all items here are already live on Alpha as of `alpha-2026-09-24-1` (CR221's
flags default OFF, so slot 1/3/history-arm code is deployed but dark until Saiful flips a flag;
CR170/CR171 are unconditional and have been live since their own promotion in August).

## Per-item commit list, existence verified by `git show --stat`

### CR221 slot 1 — A1 (debt maturity ladder) + A3 (cost of debt)

```
472efbfc feat(CR221): A1 debt maturity ladder + A3 cost of debt, both EDGAR-sourced (AT:R75 CR221)
  backend/app/core/config.py | services/debt_maturity.py (new) | services/edgar_tags.py |
  services/interest_cost.py (new) | trading_math/valuation.py |
  test_cr221_a1_debt_maturity.py (new, 198 lines) | test_cr221_a3_interest_cost.py (new, 184 lines) |
  docker-compose.yml
95e7dbec feat(CR221): render A1+A3 on the fact sheet, flag-gated, with a loud dark-ingest warning (AT:R75 CR221)
  services/edgar_pit.py | services/fundamentals.py | services/room_prompts.py |
  services/room_runner.py | test_cr221_debt_structure_render.py (new, 177 lines)
```

Both commits exist, both confirmed via `git show --stat`. Flags: `room_debt_maturity_enabled`,
`room_cost_of_debt_enabled` — both `False` by default in `backend/app/core/config.py:883,891`,
both forwarded in `docker-compose.yml` (grep-confirmed, 1 match each).

### CR221 "history arm" — C2/C5 (multi-year FCF/capex/conversion) + B2 (cycle ROE + median)

```
2f372e2d feat(CR221): C2/C5 — multi-year FCF, capex and conversion history (AT:R75 CR221)
ee8fcb86 feat(CR221): B2 — cycle ROE history and its median (AT:R75 CR221)
```

Both exist. FCF here is DERIVED (OCF − capex), never the frame's own `Free Cash Flow` row — the
same DEF400 discipline slot 3 below states explicitly, applied here for the same reason (a stated
and a checkable figure can disagree; the sheet states the checkable one). B2's balance-sheet join
is explicitly BY PERIOD, not by positional index — the commit message states XOM returns four
balance columns against five income columns, so a positional zip would silently misalign years;
I did not independently re-verify that XOM shape this round. Flags: `room_fcf_history_enabled`,
`room_fcf_conversion_enabled`, `room_roe_history_enabled` — three separate flags for two work
items, all `False` by default, all three forwarded in `docker-compose.yml` (grep-confirmed).

### CR221 slot 3 — C3/C4 (cash-flow bridge) + DEF400 (derived FCF, shipped in the same commit)

```
8b4f189c feat(CR221): C3/C4 cash-flow bridge + DEF400's derived FCF, both flag-gated (AT:R75 CR221)
dcdc5afb fix(DEF400): derive FCF from the statements, flag-gated; row carries the Room evidence (AT:R75 DEF400)
```

`8b4f189c` is the code (`fundamentals._ttm_millions` + cash-flow bridge line, both surfaces).
`dcdc5afb` is DEF400's own docs/register commit (2-line diff, `docs/defect/_registry/DEF400.row.md`
+ `docs/defect/def_list.md`, status `open` → `in_progress`) — the code fix landed **inside**
`8b4f189c`, not in `dcdc5afb`, per `dcdc5afb`'s own commit message ("Code fix landed in 8b4f189c
alongside CR221's bridge — one file, one hunk set"). Flags: `room_cashflow_bridge_enabled` (off
by default), `fundamentals_fcf_from_statements_enabled` — **note this flag's default flipped to
`True` at `backend/app/core/config.py:916`** as of current HEAD, meaning DEF400's derived-FCF
fix is LIVE on Alpha today, not dark. I did not trace which commit flipped it from the `False`
`2f372e2d` shows it forwarded as — worth the auditor confirming when that happened and whether it
was its own reviewed decision or an incidental default change.

**DEF399/DEF400 follow-on, out of this lane's commit list but adjacent — and with a real
dependency on slot 1's A3, not just a naming coincidence.** `83e9c6e6` (2026-09-17, AT:R77)
withdrew `interest_coverage` (a quarterly ratio in `fundamentals.py`) for provider-drift reasons,
and its fix function `_gate_interest_coverage` directly CONSUMES slot 1's A3 output — confirmed by
reading `83e9c6e6`'s diff: the docstring states "A3's EDGAR numerator is annual and the ratio is
one quarter's EBIT... `_gate_interest_coverage` annualises it against `interest_cost`'s
consolidated figure," and `fundamentals.py`'s `interest_coverage` block (lines 461-465) sits
immediately beside the `room_runner._gate_interest_coverage` reference. So a regression in A3's
`resolve_interest_cost`/`cost_of_debt_pct` (`backend/app/services/interest_cost.py`) would silently
propagate into DEF399's gate too — worth the auditor treating A3 and the DEF399 gate as one
combined attack surface rather than two independent ones. `83e9c6e6` itself does not touch
`training_toll.py` or CR221's cash-flow bridge files, so it stays out of this lane's own commit
list, but it is not merely "the same lineage" as stated in an earlier draft of this note — it has
a live code dependency on slot 1.

### CR170-BE / CR171-BE — resting orders, short selling

```
eba1dcaf feat(CR170-BE): the order type that finally means what it says (AT:R69 CR170)
fcca82fc feat(CR170-BE): what the book ties up, without pretending the money left (AT:R69 CR170)
7f90bff2 test(CR170-BE): the sweep's guards, exercised through the sweep (AT:R69 CR170)          [not in dispatch brief — found in git log --grep]
e6ae1448 test(CR170-BE): a stop-loss that only fires when you open the app is not a stop-loss (AT:R69 CR170)  [not in dispatch brief]
dd8a4f3f feat(CR171-BE): the short that costs what a short costs (AT:R69 CR171 DEF262)
c7a39ee7 fix(CR171-BE): the gross rule belongs on the sell path, not on every buy (AT:R69 CR171)
bf6209c1 feat(CR170,CR171): the short the user can finally see, and the notice they can finally read (AT:R69 CR170 CR171 DEF259)
227ce5a4 docs(CR170,CR171): both backends complete — the register rows (AT:R69 CR170 CR171)       [not in dispatch brief — docs-only]
```

All eight exist (`git show --stat` on each). **Two commits beyond the dispatch brief's six**
(`7f90bff2`, `e6ae1448`) are test-only commits for CR170-BE found via `git log --grep='CR170'`;
including them because they're load-bearing test coverage for this exact lane, not because the
brief missed something material — `227ce5a4` is docs-only (register rows) and doesn't change
behavior.

**Not flag-gated.** `sim_resting_order_tick_interval_seconds` (a tuning knob, not a kill switch)
is the only CR170/171-related config key; `grep` for a `resting_order`/`short_sell` boolean flag
in `config.py` found none. This matches the commit history: Saiful's instruction was to build all
four order types and shorting as ordinary features, not behind a flag — CR171-BE's halal-advisory
question (below) was resolved as "inform, don't block" rather than a feature flag.

**DEF262 resolved inline, not via a separate fix commit:** `dd8a4f3f`'s own message states the
halal ruling landed IN this commit — `safety_floor.py`'s `long_only` branch had been a bare `pass`
comment claiming the decision was "delegated to trade service" with nowhere that actually read
the flag; `_execute_fill` now refuses correctly. **DEF259 resolved in `bf6209c1`**, three bugs at
once: the halal advisory computed server-side but never rendered client-side (CR040 shape — a
disclosure nobody sees informs nobody, fixed by holding the success pop until acknowledged); a
successful short reported as a "resting order... waiting at $0.00" (wrong confirmation copy);
and a short position with no route to `cover_short` (unbounded-loss position with no closing
path — DEF259's core finding, since a short is the one position type whose loss is unbounded).

## Compose parity — checked, clean

```
grep -c ROOM_DEBT_MATURITY_ENABLED docker-compose.yml        → 1
grep -c ROOM_COST_OF_DEBT_ENABLED docker-compose.yml         → 1
grep -c ROOM_CASHFLOW_BRIDGE_ENABLED docker-compose.yml      → 1
grep -c FUNDAMENTALS_FCF_FROM_STATEMENTS_ENABLED docker-compose.yml → 1
grep -c ROOM_FCF_HISTORY_ENABLED docker-compose.yml          → 1
grep -c ROOM_FCF_CONVERSION_ENABLED docker-compose.yml       → 1
grep -c ROOM_ROE_HISTORY_ENABLED docker-compose.yml          → 1
```

All seven CR221-family flags this lane touches are forwarded — CR040's degrade-loudly rule
(a config-gated feature must fail visibly, never silently) is not violated by a missing compose
line here. Confirmed by the guard directly:

```
cd backend && .venv/bin/python -m pytest tests/unit/test_config_compose_parity.py -q
9 passed in 3.16s
```

## Tests, per item, run individually against the shared checkout at current HEAD

```
cd backend && .venv/bin/python -m pytest tests/unit/test_cr221_a1_debt_maturity.py tests/unit/test_cr221_a3_interest_cost.py tests/unit/test_cr221_debt_structure_render.py -q
41 passed in 7.59s
```

```
cd backend && .venv/bin/python -m pytest tests/unit/test_cr221_c3c4_cashflow_bridge.py -q
22 passed in 4.64s
```

```
cd backend && .venv/bin/python -m pytest tests/unit/test_cr221_c2c5_fcf_history.py tests/unit/test_cr221_b2_roe_history.py -q
32 passed in 7.60s
```

```
cd backend && .venv/bin/python -m pytest tests/unit/test_cr170_order_pricing.py tests/unit/test_cr170_resting_orders.py tests/unit/test_cr171_short_selling.py tests/unit/test_cr171_shorts_on_the_wire.py -q
93 passed in 19.93s
```

All four green, 188 tests total across this lane's own files, zero failures.

## Attack surface (named for the auditor, not defended here)

- **Fabricated/stale data presented as measured in Room prompts.** Slot 1/3/history-arm all
  render EDGAR-sourced figures onto the fact sheet. `95e7dbec`'s commit message claims "a loud
  dark-ingest warning" when the underlying fact store is unreachable — I did not independently
  drive that path this round (e.g. confirm the warning actually renders when EDGAR ingest has
  never run for a ticker, vs. silently omitting the line). This is exactly the CR219 pattern this
  whole CR exists to close (a persona/sheet contradiction from a field that silently doesn't
  degrade the way its own commit message claims) — worth the auditor's first attack.
- **Flag-off paths truly dark.** Compose parity confirmed above, but that only proves the flag
  reaches the container — it does not prove the code path is inert when `False`. Not independently
  driven this round: I did not start a server with each flag off and confirm the corresponding
  Room-sheet line is absent (vs. present-but-empty, which would be a different and worse bug —
  CR040's exact concern). CR221-SLOT4's own audit lane (already COMPLETE) may have established a
  pattern for how to drive this cheaply; worth reusing rather than reinventing.
- **Source failures degrade loudly, not silently.** Same concern as above, narrower: does an
  EDGAR fetch timeout/4xx/5xx produce a visible "data unavailable" line, or does it produce a
  wrong number, an absent line indistinguishable from "nothing to report", or a crash? I read the
  commit messages' claims about this (`7a9854eb`, mentioned in the CR221 doc as "an unreachable
  fact store degrades the block instead of killing every Room run") but that commit is NOT in my
  per-item list above (it's dated 2026-09-03 between slot-1's two commits, addressing a slot-1
  render-path robustness issue) — flagging it here as adjacent evidence I did not independently
  verify, not as a commit I'm claiming coverage for.
- **CR170/CR171: fill-price worse-of-two-prices rule.** `eba1dcaf`'s core claim is that a
  resting order fills at the WORSE of (named price, observed price) specifically to remove a
  hindsight edge from 15-minute-delayed marks — I did not independently construct a case where
  the rule picks the better price for the user and confirm it's rejected. The 93 passing tests
  above are the builder's own test suite, not an adversarial re-derivation.
- **CR170: read-time, non-reserved cash-committed accounting.** `fcca82fc`'s `cash_available` is
  deliberately NOT floored at zero — an over-committed book is reachable by design, refused at
  fill time instead. Worth confirming a fill-time refusal actually fires rather than allowing
  negative cash to settle.
- **Short cover / unbounded-loss path.** DEF259's fix added `cover_short` routing; worth the
  auditor confirming a short position can actually be closed end-to-end (open short → price moves
  against the user → margin call / forced buy-in path in `dd8a4f3f`'s §7 "forced buy-in" — I did
  not independently drive this sequence).
- **Halal advisory rendering.** `bf6209c1` claims the advisory now "HOLDS the pop until it is
  acknowledged, with the submit CTA disabled underneath" — a mobile-side UI claim I did not verify
  against the actual widget (no mobile test run in this lane; this lane is backend-only per its
  own name, "CR170/CR171 backend halves" — the mobile halves, if any beyond `bf6209c1`'s stated
  scope, are out of this lane's scope and should be confirmed as covered elsewhere or flagged as a
  gap).

## Independent regression suite (full backend, run once, shared across this lane and Lane A / Lane C)

```
cd backend && python -m pytest tests/unit/ -q -p no:cacheprovider 2>&1 | tail -3
```

Full unit suite: not cited this round — 5 concurrent full-suite runs on the shared Mac checkout
(Architect's dispatch error); per-lane suites above are the builder evidence. Auditor re-runs the
independent suite on melehost per BINDINGS.

## Governance

Register status, confirmed by reading each row's own status cell: `CR170.row.md` → `done`,
`CR171.row.md` → `done`, `CR221.row.md` → `in_progress` (per CR231's programme doc, CR221 stays
`in_progress` until the five flags built-but-off are decided — separate from this lane's own
audit closing). This lane's COMPLETE would clear the audit half of CR221's remaining work but not
by itself flip its row status; that's Saiful's/the Architect's call on the flag decisions named in
CR231 Phase 1b.

## Known limits, stated rather than left to be found

- **No scratch-worktree measurement** — same limit RETRO-PM-FLOOR, RETRO-SIM-OPTIONS and
  RETRO-MIGRATIONS all name, a retroactive record-review choice. Per-file test commands above ran
  in the shared Mac tree at current HEAD.
- **No live flag-flip drive.** Named under Attack surface above — I did not start a server and
  toggle any of the seven CR221 flags to confirm dark-when-off behaviour live; this is asserted by
  the builder's commit messages and the compose-parity guard only.
- **No adversarial re-derivation of the pricing/margin math** (worse-of-two-prices, cash
  reservation, short cost/borrow) beyond running the existing test suite — a real attack pass on
  CR170/CR171's Tier-A money logic is squarely the auditor's job for this round, not attempted by
  me beyond reading the commits' own stated reasoning.
- **`bf6209c1`'s mobile-side claims (the held pop, disabled CTA) not independently verified** —
  this lane is scoped backend-only; if the mobile half of that commit needs its own coverage, flag
  it and I'll either fold it in or point to where it should live.
- **XOM's stated 4-vs-5-column balance/income mismatch (B2)** not re-measured live this round —
  taken from the commit message.
- **The `fundamentals_fcf_from_statements_enabled` default-flip to `True`** (noted under slot 3
  above) is stated but its originating commit not traced — worth the auditor pinning down whether
  that was a deliberate, reviewed decision to make DEF400's fix live, or an incidental default.

SUBMITTED: round 1
