# DEF417 — `liquid_only` enforced only as prompt text, never structurally

**Filed:** 2026-09-24 (AT:R85), source: architect, CR231 stabilisation-programme sweep
**Category:** backend / safety floor
**Severity:** high — an uncoachable-mandate flag with no structural enforcement

---

## What's broken

The mandate's `liquid_only` constraint (`backend/app/schemas/mandate.py`, set
by the concierge's "ONLY liquid names (no microcaps)" chip, default `True`)
was rendered into every PM/Trader-lineage prompt —
`overlay_generator.py:268` ("Liquid only. Avoid microcaps (< $500M market
cap) and illiquid names.") and `concierge_engine.py:592` (the mandate-readback
flag list) — but `backend/app/agents/safety_floor.py::check_mandate_compliance`,
which deterministically enforces `halal` / `esg_lite` / `no_fossil_fuels` /
`no_tobacco_alcohol_gambling` / `long_only`, had no `liquid_only` branch at
all. Per CLAUDE.md's degrade-loudly rule: "prompt instructions are not
controls" — agents ignore even emphatic prompt-only instructions ~70% of the
time (CR038), and the alpha LLM (`qwen3.8-flash-next-abliterated`) is a
refusal-stripped build, so a prompt-only instruction holds even less
reliably than on a well-behaved model. A user with `liquid_only` set could
receive a microcap/illiquid recommendation the safety floor waved through,
believing the constraint was enforced when it was advisory only.

## Fix — a deterministic rule in `check_mandate_compliance`

### Data source: the SAME classification snapshot, no new socket

`backend/app/services/classification_universe.py` already opens one
`yf.Ticker(t).info` call per S&P parent constituent, once a day, off the
request path (DEF061/CR026: the daily `_classification_universe_refresh()`
background task). That `info` dict already carries `marketCap` and
`averageVolume` — the exact fields `fundamentals.py::fetch_live_fundamentals`
reads for the same purpose on its own (request-path, per-ticker) call. DEF417
captures those two fields in the SAME daily pass (`_network_classify`'s new
`market_caps_out`/`avg_volumes_out` side-channels, mirroring the `sectors_out`
side-channel CR026 added), persists them alongside `sectors` on
`ClassificationUniverseSnapshotRow` (new `market_caps`/`avg_volumes` JSON
columns, migration `def417a0b0c0d1`), and resolves them off the stored row —
**zero new sockets, zero new providers, zero paid feeds.**

### Threshold + source

- **Market cap floor: $500M** (`app.schemas.liquidity.MICROCAP_FLOOR_USD_M`).
  This is not a new number — it is the SAME $500M already hard-coded in
  `overlay_generator.py::_MICROCAP_FLOOR_USD_M` and printed into the PM/Trader
  prompt overlay ("Avoid microcaps (< $500M market cap)"), which
  `overlay_generator.py`'s own comment (line ~1072 in `fundamentals.py`, the
  market-cap rendering) already cites as the number the mandate advertises:
  *"the mandate carries 'Liquid only. Avoid microcaps (< $500M market cap)' as
  a HARD constraint in 17 of 18 prompts."* DEF417 makes `overlay_generator.py`
  IMPORT this constant from `app.schemas.liquidity` rather than defining its
  own copy, so the narrated number and the enforced number are structurally
  the same value (shown == enforced, CR046 C-a) — there is exactly one
  `500`, never two that could drift apart. $500M also sits inside the
  conventional microcap band cited by Nasdaq/Investopedia (roughly
  $50M–$300M "microcap", up to ~$2B "small-cap") and above the SEC's
  "smaller reporting company" public-float threshold ($250M) — a
  conservative, already-reviewed, already-user-facing cutoff, not an invented
  one.
- **Average dollar volume floor: $1M/day**
  (`app.schemas.liquidity.ILLIQUID_AVG_DOLLAR_VOLUME_USD`). Market cap alone
  answers "how big is the company", not "can this account's order move the
  tape" — `fundamentals.py`'s own comment on `volume_avg_3m` says exactly
  this: *"SNOA trades ~75k shares a day and NVDA ~45M, and the mandate's
  'Liquid only. Avoid microcaps' is a sizing constraint that market cap alone
  cannot settle."* $1M/day average dollar turnover is a conservative
  execution-risk floor even for a small simulated account (this account
  trades in the thousands of dollars; sub-$1M/day is commonly cited as a
  retail-illiquidity screen), leaving ample headroom before market impact
  becomes a real concern. Average VOLUME (shares/day, `averageVolume`) is
  what's persisted in the snapshot — the classify pass has no live price, so
  a persisted DOLLAR figure would go stale against the market the moment it's
  written. Dollar volume is derived at RESOLVE time
  (`ClassificationUniverse.resolve_liquidity(ticker, price=...)`), against
  the caller's own live quote for the proposed ticker — the same
  resolve-fresh/persist-the-source-datum split `single_name_cap_pct` already
  uses for percentages.

### Four-state resolution (DEF061 pattern, ONE deliberate divergence)

`app/schemas/liquidity.py` (`LiquidityVerdict`, `LiquidityStatus`) mirrors
`ClassificationVerdict` exactly:

| State | Meaning | Blocks? |
|---|---|---|
| PERMITTED | Both known figures clear their floor | No |
| EXCLUDED | A REAL, measured reading (market cap or dollar volume) is below its floor | **Yes** |
| UNKNOWN | Neither figure is available (ticker outside the ~503-name classified universe, or genuinely un-priced) | No — permitted + disclosed |
| UNAVAILABLE | The classification snapshot is stale/absent/disabled | No — **this is the divergence, see below** |

UNKNOWN must never block — the DEF059 inversion trap, and specifically the
wrong direction for THIS flag: a name AMI hasn't classified skews SMALLER
(more likely outside the S&P-500-derived parent set this snapshot covers),
i.e. more likely to be exactly what a `liquid_only` user wants filtered — but
AMI did not MEASURE it, so it cannot claim the ruling. Blocking on UNKNOWN
would silently reject every small/mid-cap name outside the classified
universe by default, since `liquid_only` defaults `True`.

**The one deliberate divergence from `ClassificationVerdict.is_blocking`:**
for the DEF061 flags (`no_fossil_fuels`/`no_tobacco_alcohol_gambling`/
`esg_lite`), UNAVAILABLE blocks (the screen "pauses" by refusing every trade
those opt-in flags would otherwise judge). Those three flags default `False`,
so a classification-source outage only silences enforcement for the minority
of mandates that explicitly turned one on. `liquid_only` defaults `True` on
`Compliance` — essentially every mandate carries it — so treating the SAME
snapshot's outage as blocking here would refuse a BUY for nearly every user
in the app the instant the daily refresh lags, the DB row ages past its hold
window, or `CLASSIFICATION_SCREEN_ENABLED` is (mis)configured off. That is a
materially larger blast radius than the pattern was built for, and it is
exactly the CR040 question turned around: *if this fires constantly and
silently blocks, what does the user end up believing?* — that AMI is
refusing to trade, with no way to tell the difference between "your mandate
correctly blocked this" and "the classification pipeline is down." DEF417
instead routes UNAVAILABLE to `ComplianceResult.advisories` — disclosed
loudly (CR040: `"AMI couldn't refresh its liquidity classification... The
'Liquid only' filter is paused until it can."` travels on the wire, in
`ComplianceBlock.liquidity_verdict`/`advisories`, the same way every other
advisory does), never silently, but never blocking either.
`LiquidityVerdict.is_blocking` / `.is_disclosed_pause` make this an explicit,
named split rather than an unstated exception.

### Call sites — came "for free" (no new wiring)

Every existing call site of `check_mandate_compliance` /
`enforce_safety_floor` already threads `classification_universe=` (for the
DEF061 checks) and a price for the proposed ticker (`quotes=` and/or
`proposed.limit_price`, for the single-name/sector caps). Since
`resolve_liquidity` lives ON `ClassificationUniverse` and needs only those
same two inputs, the `liquid_only` check fires wherever those already reach
the floor — **no call site needed new parameters.** Verified, not assumed:
`backend/tests/unit/test_def417_liquid_only_enforcement.py`'s "per-call-site
wiring" section exercises all four:

1. `SimEngine.submit()` (`sim_engine.py:1465`)
2. `SimEngine.preview()` (`sim_engine.py:1976`)
3. `SimEngine` short-open path (`sim_engine.py:2617`) — same
   `_compliance_context` builder as 1/2, not separately tested (identical
   wiring, covered by the CR026-BE-lesson principle that the shared builder
   is the single point of truth)
4. `room_runner._assemble_verdict` (the scripted path, `room_runner.py:4011`)
5. `room_runner`'s live-PM `enforce_safety_floor(...)` call
   (`room_runner.py:5696`)

Each wiring test would go red if its call site dropped
`classification_universe=` from the compliance call — the CR026-BE lesson
("call-site wiring fails OPEN") applied to this flag.

`price_for_liquidity = proposed.limit_price or (quotes or {}).get(t)` mirrors
the SAME fallback `check_mandate_compliance`'s own single-name-cap pricing
(step 6) already uses, so the liquidity check is exactly as resilient to a
market order / missing quote as the caps it sits beside.

### Buy-only, mirrors `long_only`

The check only fires on `proposed.is_buy`. A SELL is never blocked by
`liquid_only` — it constrains what enters a position, not what a user
already holds and wants to exit. If a name's market cap or volume slipped
below the floor after purchase, `liquid_only` must not trap the user in it —
the same "a check that could not run must not block" / "never force-sell on
a tightened limit" doctrine `long_only` and the CR101-BE2 retro-tightening
rules already establish elsewhere in this file. **Existing holdings that now
violate a newly-set `liquid_only` flag are NEVER force-sold** — they can
still be sold at will (not blocked), and would surface via
`check_holdings_against_mandate`'s BL12 audit path if extended to include a
liquidity check in a future CR (out of scope here — DEF417 covers the
`check_mandate_compliance` proposed-trade path only, matching the row's
scope).

## Wire shape

`ComplianceResult.liquidity_verdict: LiquidityVerdict | None` (new field,
`backend/app/schemas/trade.py`) — present whenever `liquid_only` is on for a
BUY, `None` otherwise, mirroring `sharia_verdict`/`classification_verdicts`.
Forwarded to `ComplianceBlock` (`backend/app/api/sim.py`, the
`/v1/sim/preview` response model) and `_compliance_json` (the
`/v1/sim/submit` inline dict), so a PERMITTED-but-UNKNOWN verdict's
disclosure — "AMI hasn't measured this name's market cap or trading volume"
— reaches the client even on an accepted trade, the same non-negotiable CR040
requirement the DEF061 verdicts already meet.

## Tests

`backend/tests/unit/test_def417_liquid_only_enforcement.py`, 25 tests:

- Resolver: permits a liquid large-cap; excludes a real microcap; excludes on
  dollar-volume alone (a large-cap name that trades thin); UNKNOWN when
  neither figure is available; judges on market cap alone when volume can't
  be priced (no price supplied); a missing price never fabricates a volume
  breach; a stale universe resolves UNAVAILABLE and is confirmed
  non-blocking + disclosed.
- Enforcement: microcap blocked (`blocked_by="compliance"`); illiquid-by-
  volume blocked; the SAME name allowed once the flag is off (proves the
  check reads the flag, not a fixed always-on rule); a liquid large-cap
  passes; UNKNOWN permitted with disclosure, not blocked (the DEF059
  regression, load-bearing here because the flag defaults on); a SELL is
  never blocked; a bare object with no `resolve_liquidity` degrades to an
  advisory; `None` universe degrades to an advisory (the divergence from
  DEF061's blocking UNAVAILABLE, asserted explicitly against the sibling
  `no_fossil_fuels` test in `test_def061_compliance_enforcement.py`); a stale
  universe degrades to an advisory; `liquid_only`'s True default is
  confirmed on the shared `base_mandate` fixture.
- Shown == enforced: the enforced `MICROCAP_FLOOR_USD_M` equals
  `overlay_generator._MICROCAP_FLOOR_USD_M` (one import, not two literals);
  both thresholds are named constants, not magic numbers in the resolver.
- Per-call-site wiring (5 tests, see above): `SimEngine.submit`,
  `SimEngine.preview`, `room_runner._assemble_verdict`,
  `room_runner`'s live-PM `enforce_safety_floor` call — each proven to
  reject a microcap end-to-end, plus one contrast test proving the wiring
  test isn't blocking for an unrelated reason (cash/cap/etc.).

Also re-ran green, unchanged: `test_safety_floor.py`, `test_sim_engine.py`,
`test_room_runner.py`, `test_def419_per_account_mandate_check.py`,
`test_config_compose_parity.py`, `test_def061_compliance_enforcement.py`
(two of its fixtures needed a mechanical update — the injected-fetcher
contract grew two trailing maps, same shape CR026 grew it with `sectors`),
`test_cr129_risk_limits_from_risk_tolerance.py`,
`test_cr101_be2_new_risk_limits.py`, `test_cr101_be1_settable_risk_caps.py`,
`test_cr101_be2_round2_room_wiring.py`, `test_cr026_sector_allocation.py`,
`test_def149_sector_cap_includes_cash.py`,
`test_def153_single_name_cap_market_order.py`, `test_cr069_halal_guard.py`,
`test_def084_halal_flag_copy_guard.py`, `test_cr098_room_analyst_pullback.py`,
`test_def169_single_name_cap_unevaluated_when_portfolio_value_zero.py`,
`test_cr219_r49_floor_state_preview.py`, `test_cr222_preregistration.py`,
`test_cr171_short_selling.py`, `test_cr172_option_strategist.py`,
`test_cr172_option_open_path.py`, `test_cr172_option_floor.py`. Full
`tests/unit/` suite run bare, see architect doc for the exit code.

## Existing-user impact — does it block sells?

No. The check gates on `proposed.is_buy` only. An existing holding that would
now fail `liquid_only` (bought before this DEF shipped, or before the name's
market cap fell) can still be sold freely — `liquid_only` never appears on
the sell path, so there is no new refusal an existing position could trigger
by holding still. New BUYS of a name already below the floor are the only
thing this DEF changes the outcome of.

## Migration

`backend/alembic/versions/def417a0b0c0d1_classification_snapshot_liquidity.py`
— adds nullable `market_caps`/`avg_volumes` JSON columns to
`classification_universe_snapshots`, chained after `cr230a0order0log` (the
head at filing time). Back-fills existing rows to `{}` (server default),
which resolves every ticker's liquidity to UNKNOWN until the next daily
refresh appends a row carrying real figures — permitted + disclosed, never a
false EXCLUDED, for the gap between promotion and the first post-DEF417
refresh.

## Status

`fixed`.
