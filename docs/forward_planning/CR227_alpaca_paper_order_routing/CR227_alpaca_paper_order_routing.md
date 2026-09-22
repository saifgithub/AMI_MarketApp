## CR227 — Alpaca paper-account order routing

## What

A trade ticket submission gains a **destination** choice: AMI sim, Alpaca paper, or
both. Today `trade_ticket_sheet.dart` always fills against AMI's own simulation engine
only; Alpaca is read-only (CR202/CR224 — key/secret/base-URL stored device-local,
`AlpacaClient` makes GET calls only). This CR adds the ability to also place — or
place *only* — the equivalent order against the user's own linked Alpaca **paper**
account.

## Why

Saiful: *"we need to create a CR to enable trading with the alpaca account."* Clarified
through discussion: this is Alpaca's own **paper** simulator, not a live brokerage
account — still simulated money, just a second simulator instead of (or alongside) AMI's.
Per-order destination choice ("AMI sim, Alpaca paper, or both") was Saiful's explicit
answer when asked whether this should auto-mirror sim trades or be a separate manual
control — he wants the choice made at order-entry time, not inferred.

## Decision-log amendment (must land before/with this CR's code)

D-004 and D-069 currently read as an absolute: *"no brokerage integration ever,"* *"we
never route an order, never connect to an execution venue"* (decision_log.md:36-39,
441-465). No live/paper qualifier exists today. This CR requires a new decision entry
— **D-0xx, next sequential number** — narrowing that prohibition:

> AMI may route an order to a linked brokerage account **only** when that account is
> confirmed paper/simulated (for Alpaca: the account resolves through Alpaca's paper
> endpoint, `https://paper-api.alpaca.markets` or a user's CR224 paper override — never
> a live/production Alpaca host). A live or production brokerage account remains
> strictly read-only/unsupported for order placement. D-004's "no brokerage
> integration" is narrowed to "no *live* brokerage order routing" — AMI still never
> touches real capital or a real execution venue.

This must be written into `docs/initial_specs/11_decisions/decision_log.md` following
the existing D-069 "partial amendment" pattern (state what changes, state what does
NOT change, and why), and the CLAUDE.md decision-pointer table row ("Endpoint of the
journey") updated to reflect the narrowed rule. Both are content changes, not code —
land them in the same commit as the CR227 row file, ahead of implementation.

**DEF145** (closed wontfix, "no order to a brokerage, paper or otherwise") is
superseded by this CR for the Alpaca-paper case specifically. Its guard test,
`backend/tests/unit/test_def145_alpaca_stays_read_only.py`, must be consciously
rewritten — not deleted — to assert the *new* boundary: no call to a **live** Alpaca
host, and (since routing is mobile-side per the design below) no backend code path
that could reach `/v2/orders` at all, live or paper. The backend's read-only posture is
unchanged by this CR.

## Scope

**Paper-only, mobile-initiated, mandate-gated on both legs.** Three decisions locked in
by discussion with Saiful before this doc was written:

1. **Paper accounts only.** A live/production Alpaca account can never receive an
   order from AMI. Enforced by checking the linked account's `baseUrl` (CR224) against
   Alpaca's known paper host pattern before any order call — never trust a label, check
   the endpoint.
2. **Same mandate/compliance floor for both destinations.** The PM safety-floor check
   (`SimEngine`'s `check_mandate_compliance`, sim_engine.py:1454-1478 — sector limits,
   halal universe, drawdown, cooldown-after-loss, bracket validity) gates an
   Alpaca-only order exactly as it gates a sim fill. A trade the mandate refuses is
   refused everywhere, not just in the sim — otherwise the floor is trivially bypassed
   by picking "Alpaca only." "Uncoachable" stays meaningful.
3. **Mobile places the Alpaca order directly.** The backend never receives the
   Alpaca key/secret, even transiently — preserves the CR202 guarantee ("Alpaca
   credentials are device-local only, never sent to or stored by the AMI backend").
   The backend's job stops at telling mobile whether the trade is compliance-clean;
   mobile does the actual `POST /v2/orders` call itself, using the same
   `AlpacaCredentialStore`-sourced client CR224 already built.

## Design

### Destination selector (`trade_ticket_sheet.dart`)

A three-way control (AMI Sim / Alpaca Paper / Both) on the ticket, defaulting to **AMI
Sim** (today's behavior — no surprise for existing users) and visible/enabled only when
`alpacaLinkedProvider` reports linked (an unlinked user sees no Alpaca option, matching
how the Portfolio screen's Alpaca section already hides itself when unlinked).

### Submission flow, by destination

- **AMI Sim only** (today's behavior, unchanged): `POST /v1/sim/submit` as now.
- **Alpaca Paper only**: call `POST /v1/sim/preview` (already exists, sim.py:642-694 —
  runs the identical mandate/compliance pre-flight as submit but persists nothing) to
  get a compliance verdict without writing a `SimTradeRow`. If `ok: true`, mobile then
  places the order directly against Alpaca (`AlpacaClient`, new `submitOrder()` method
  — see below). If `ok: false`, surface the same amber compliance-violation banner the
  sim path already has; no Alpaca call is made.
- **Both**: call `POST /v1/sim/submit` as today (writes the sim fill). If the response
  is `ok: true` (any of the three success branches — resting, short, or trade — per
  sim.py:759-828), mobile also places the Alpaca order with the same ticker/side/
  quantity. If `ok: false`, neither leg proceeds — the existing refusal banner covers
  both destinations, since neither fired.

No backend endpoint changes are required for the compliance gate — `preview` already
exists and already runs the exact same `check_mandate_compliance` path as `submit`.

### New mobile Alpaca capability

`alpaca_client.dart` gains exactly one new method, `Future<AlpacaOrder> submitOrder({
required String symbol, required String side, required double qty })`  — a single
`POST $baseUrl/v2/orders` with `type: market`, `time_in_force: day` (matching AMI's own
"no partial fill, single price" semantics — see Non-goals). Before constructing the
request, it re-validates `creds.baseUrl` is a recognized Alpaca **paper** host and
throws rather than calls if not — a second, client-side enforcement of the paper-only
rule, independent of whatever the UI already checked.

Order type is deliberately narrowed to market-only for v1 (see Non-goals) — AMI's
LIMIT/STOP/STOP_LIMIT resting-order lifecycle (`sim_resting_orders`, seven states,
`order_pricing.py`'s trigger/fill rules) has no Alpaca equivalent to mirror yet; mixing
"AMI's resting order triggers three days later" with "Alpaca fills immediately today"
for the same ticket is a correctness problem this CR does not attempt to solve.

### Result surfacing

The ticket's success/failure UI needs a per-destination result, not one combined
banner — "Both" can legitimately fill on one leg and fail on the other (e.g. Alpaca
rejects for insufficient paper buying power while AMI's sim, which has its own
independent cash balance, accepts). Show each destination's outcome separately.

## Non-goals (this CR)

- **No resting/limit/stop orders on the Alpaca leg.** Market orders (immediate fill)
  only, for both "Alpaca only" and "Both." AMI's LIMIT/STOP/STOP_LIMIT tickets remain
  AMI-sim-only until a follow-up CR designs the cross-system resting-order story.
- **No cover-a-short or sell-from-Alpaca-holding flows.** `coverTicker`/`sellTicker`
  prefills (trade_ticket_sheet.dart:46-60) are keyed to AMI's own holdings and don't
  translate to Alpaca's independent position sizes. The destination selector is
  hidden/forced to AMI-Sim-only on those two entry paths.
- **No options.** `OptionVerdictCta`/option legs stay AMI-sim-only; Alpaca options
  order semantics are unexplored.
- **No live/production Alpaca support**, ever, per the decision-log amendment above.
- **No backend order-placement path.** Confirmed no `alpaca_service.py` function or
  `backend/app/api/alpaca.py` route needs to exist for this — mobile-direct only, per
  the CR202 custody decision restated above.

## Acceptance

- [x] Decision log carries the new entry (D-071); CLAUDE.md's decision-pointer table
  reflects the narrowed rule. (commit b2da0fd5)
- [x] `test_def145_alpaca_stays_read_only.py` is rewritten (not deleted) to assert the new
  boundary and passes. (commit a04842cc)
- [x] Destination selector defaults to AMI Sim; hidden when Alpaca isn't linked, and on
  the cover/sell-from-holding entry paths.
- [x] Alpaca-only submission runs mandate compliance via `/v1/sim/preview` and is refused
  identically to a sim submission when the mandate blocks it — verified by
  `cr227_destination_routing_test.dart`'s "a mandate-blocking preview leaves the Alpaca
  order call unmade" test.
- [x] Alpaca order call refuses (client-side) against any non-paper `baseUrl`, verified by
  `alpaca_client_paper_only_test.dart`, independent of whatever the UI enforces.
- [x] "Both" surfaces independent per-destination results when one leg succeeds and the
  other fails (`_DestinationOutcome` list, rendered per-destination in the sheet).
- [x] `flutter analyze` clean (0 new issues); new/changed tests passing (mobile suite
  1483/1483 at final SHA); backend unit suite `pytest backend/tests/unit/ -q` 6691 passed /
  9 skipped (3 pre-existing failures from other tracks — CR228 row-status typo, DEF412 path
  check — unrelated to CR227, independently reproduced by the auditor at the base commit
  before any CR227 code).
- [x] Non-market order types (LIMIT/STOP/STOP_LIMIT) never reach the Alpaca leg — added in
  round 2 after the independent auditor found the gap (round-1 MAJOR-1): the destination
  selector hides on a non-market order type, and `AlpacaClient.submitOrder()` independently
  refuses any non-market type before even checking link state. Both proven load-bearing by
  mutation, both by the builder and independently re-verified by the auditor.

## Independent audit (CR005 protocol)

Routed to the audit handshake (`orchestration/audit/cr/CR227.architect.md` /
`CR227.auditor.md`) per Saiful's explicit instruction. **Round 1: AWAITING_FIXES** — 1 MAJOR
(a LIMIT/STOP ticket routed to Alpaca silently converted to an immediate market fill; the
CR's own stated non-goal had no enforcing check), 1 MINOR (a stray dispatch-layer artifact
mischaracterized as uncommitted). **Round 2: COMPLETE** — both fixed, neither contested,
independently re-verified and the attack table widened by the auditor. Full transcript in
the audit lane files; commits: `a17b33b2` (MAJOR-1 fix), `9a7e810c` (MINOR-1 fix).

## Status

`done` — decision-log amendment (D-071), DEF145 guard-test rewrite, and mobile
implementation landed 2026-09-22/23 (commits b2da0fd5, a04842cc, 4a0fba94, 30a3a6e3), audit
round-1 findings fixed (a17b33b2, 9a7e810c), independent auditor verdict `COMPLETE (round 2)`
2026-09-23 (`orchestration/audit/cr/CR227.auditor.md`). **Not yet promoted or shipped** — no
backend change exists to promote (mobile-direct design, per CR202); the mobile change awaits
Saiful's own hands-on acceptance pass before TestFlight/Play submission, per this handshake's
gap-fill 4 (auditor COMPLETE is not the same checkpoint as Saiful's own device test) and per
Saiful's own instruction that "ready" means after this audit process has closed.
