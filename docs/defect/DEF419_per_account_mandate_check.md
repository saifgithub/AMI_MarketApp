# DEF419 — per-account mandate check on `/v1/sim/preview`

**Filed:** 2026-09-24 (AT:R85), source: founder (TestFlight screenshot)
**Category:** backend / trading logic
**Severity:** high — a compliance verdict rendered against the wrong account's equity

---

## What's broken

Saiful, from a TestFlight screenshot (ASML buy 10 @ $1731, destination Alpaca
paper):

> When placing an order either for both or for alpaca paper only, the mandate
> is checked against the local AMI SIM account. The mandate should check
> limits based on the account in use. It does mean that it may reject for ami
> and approve for alpaca. Or vice versa. This is an expected condition.

The screenshot: "position size 137.2% exceeds single-name cap 100.0%" —
computed against the $10k AMI sim account's equity, not the (differently
sized) Alpaca paper account the order was actually destined for.

**Root cause.** `mobile/lib/screens/sim/trade_ticket_sheet.dart`'s
`_submitAlpacaOnly` (:663) calls `simNotifierProvider.preview()` →
`POST /v1/sim/preview`, which (pre-fix) always ran
`SimEngine.preview()` against `ensure_portfolio(user_id)` — the AMI sim
portfolio — regardless of which account the resulting order would settle
into. For the BOTH destination, the AMI leg's own preview/submit gates the
Alpaca leg too (`trade_ticket_sheet.dart:628-652`), so the same
wrong-denominator problem applied there as well. CR227 (Alpaca paper order
routing) added the *destination*; it never added a matching *sizing context*
— the mandate floor kept reading one account no matter which one the money
would actually move through.

This is not a bug in `check_mandate_compliance` itself — every rule it
enforces is correct for the account it is TOLD to measure. The bug is that
`/v1/sim/preview` never told it there might be a different account.

## Fix — backend half (this DEF)

**Scope note:** this DEF closes the backend half only. The mobile half
(fetching the Alpaca account/positions and passing them to `preview`) is
the mobile follow-up (not yet filed as its own CR) — see
"Mobile follow-up" below. `status: open` on the row file reflects that
follow-up is still owed.

### New schema: `AccountSnapshotIn` (`backend/app/schemas/alpaca.py`)

```python
class AccountPositionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(pattern=_SYMBOL_PATTERN)
    qty: FiniteFloat = Field(ge=0)
    market_value: FiniteFloat = Field(ge=0)


class AccountSnapshotIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: str = Field(pattern=r"^(alpaca_paper)$")
    equity: FiniteFloat = Field(gt=0)
    cash: FiniteFloat = Field(ge=0)
    positions: list[AccountPositionIn] = Field(default_factory=list, max_length=MAX_POSITIONS)
```

Reuses `FiniteFloat`/`_SYMBOL_PATTERN`/`MAX_POSITIONS` already defined in
that file for `AlpacaSnapshotIn`/`AlpacaOrderLogIn` (CR202/CR230) — same
bounding posture (`extra="forbid"`, finite floats, symbol pattern), same
custody rationale: the backend never holds the Alpaca credential (CR202), so
this is client-attested input the backend cannot independently verify
against Alpaca's own ledger. Unlike `AlpacaSnapshotIn` this never reaches an
LLM prompt (only the deterministic `check_mandate_compliance`), so the
prompt-injection rationale doesn't strictly apply — the bounding is kept
anyway, same reasoning CR230 already gives for its own schema: a sizing
calculation is not the place for a client to write arbitrary or non-finite
values either.

`kind` is a discriminator, `^(alpaca_paper)$` today — one more account type
than exists (D-071: AMI sim + Alpaca paper only), but the field exists so a
second paper-broker integration doesn't need a new request shape.

### Wire change: `SubmitTradeRequest.account` (`backend/app/api/sim.py`)

```python
account: AccountSnapshotIn | None = None
```

Added to `SubmitTradeRequest`, the schema `preview_trade` and `submit_trade`
share — but **only `preview_trade` reads it**. `submit_trade` (the AMI-sim
persist path) ignores the field entirely: an AMI submit writes to the AMI
ledger, so checking it against a different account's equity would let a fill
through the AMI ledger cannot actually support. The Alpaca leg's own order
never goes through AMI's `/v1/sim/submit` at all (CR227: mobile calls
Alpaca's `POST /v2/orders` directly) — `/v1/sim/preview` is the only AMI
route in the Alpaca path, which is why the account context only needed to
reach that one handler.

`PreviewTradeResponse` gains `account_kind: str | None` — echoes
`req.account.kind` (or `None` for the AMI path), so the client can label
which account a verdict is about without re-deriving it from what it itself
sent.

### Engine change: `SimEngine.preview(..., account_snapshot=...)` (`backend/app/services/sim_engine.py`)

When `account_snapshot` is `None` (the default), every value the method
reads is exactly what it read before this DEF — the change is additive and
the no-account path is covered by a dedicated regression test
(`test_no_account_field_checks_against_ami_sim_portfolio`).

When `account_snapshot` is present, the method builds:

- `portfolio_value` = `account.equity`
- `holdings` = one `Holding` per `account.positions[]` entry (`avg_cost` set
  to `market_value / qty` — there is no separate cost basis on a snapshot,
  and nothing this floor evaluates reads `avg_cost` for anything other than
  weighting, which the `quotes` dict already carries)
- `quotes` = each position's own mark (`market_value / qty`), plus the
  proposed ticker's live AMI mark (needed to price a first-time buy of a
  name not already in the snapshot — the DEF149 rule, reapplied)
- `cash` = `account.cash` (drives the cash-sufficiency check and the
  response's `cash_available`)
- `shorts` = `None` — no shorts concept on an account snapshot today (CR227
  scope is long-only market orders); same "unknown, don't invent it" value
  every pre-CR171 caller of this floor passed
- `current_drawdown_pct` = `0.0` — see **Known limitation** below

Then calls the **same** `check_mandate_compliance`, with the **same**
`mandate` — nothing about the rule changes, only which account's numbers
feed it.

The execution price itself (`fill_price`/`mark`, from `SimEngine.current_quote`)
is unchanged either way: the market doesn't care which account is buying,
only the account's own balance sheet does.

## Per-account vs per-user rules

| Rule | Scope | Why |
|---|---|---|
| Single-name position cap | **per-account** | The cap is "% of THIS account's equity in one name" — a different account has a different denominator. |
| Sector-concentration cap | **per-account** | Same reasoning; also correctly sums EXISTING same-sector holdings from the snapshot (`_sector_cap_breach`/`_sector_values` already summed over `holdings`, unchanged logic, now fed snapshot holdings). |
| Cash sufficiency (BUY) | **per-account** | "Do you have the money" is a question about the account receiving the order. |
| Held-quantity-for-sell / long-only short detection | **per-account** | Whether a SELL closes a position or opens a short depends on what THAT account currently holds — an Alpaca account may hold a ticker the AMI sim portfolio has never touched, and vice versa. |
| Gross exposure on a sell-to-open (CR171 §6) | **per-account** | Same holdings-dependency as above; existing same-ticker exposure in the snapshot is summed into the short's gross value exactly as an AMI holding would be. |
| Drawdown breach | **per-account, but UNMEASURABLE on a snapshot — disclosed, not blocked (round 2)** | AMI has no NAV history for an externally-custodied account. Round 1 resolved this to a silent `0.0` ("never breaches"); round 2 (auditor u66 MAJOR-2) keeps the same `0.0` behaviour but now reports it explicitly via `unmeasured_rules` — see "Round 2" below. |
| Total open-risk cap | **split: the NEW trade's own risk is per-account; PRE-EXISTING risk from AMI's ledger is unmeasurable for a snapshot account — disclosed, not blocked (round 2)** | `existing_open_risk_pct` (the sum over AMI's own open positions/stops) is a percentage OF THE AMI PORTFOLIO — summing it against a cap measured in a different account's equity was DEF419's own defect, recurring in this one rule (auditor u66 MAJOR-1). Round 2: on the snapshot path this pre-existing figure is treated as unmeasured (0.0, reported), while the PROPOSED trade's own contribution (`proposed_stop` × its own notional) is still priced against the NAMED account's equity and can still breach the cap on its own — see "Round 2" below. |
| Post-loss cooldown | **per-user** | "Has this user had a recent stop-out" is a property of the person, not the account executing this particular order — and AMI's trade ledger is the only place that history exists at all (Alpaca paper trades placed directly from the device, CR227, leave no AMI trade row). |
| Over-trading brake (max trades/day, max trades/week) | **per-user** | Same reasoning — it constrains how often the USER trades, and the only trade history this floor can count is AMI's own. |
| Halal / long-only (as a blanket) / blocklist / allowlist / locale | **mandate-level (neither)** | These are rules about the INSTRUMENT or the USER's mandate, not about either account's balance sheet — they fire identically regardless of which account is named. Proven by `test_halal_flag_is_evaluated_regardless_of_account`. |
| Pre-registration (thesis/invalidation/horizon) | **mandate-level (neither)** | Same — it's a question about whether the user wrote down a plan, unrelated to account sizing. |

The dividing line: **sizing/concentration questions ("how big relative to
what") are per-account; behavioural/history questions ("how often has this
person...") are per-user, because AMI's ledger is the only ledger that
exists for that history.**

## Known limitation — drawdown on an externally-custodied account

`current_drawdown_pct` for the account-snapshot path is hardcoded `0.0`, not
because the account has never drawn down, but because AMI has no NAV history
for an account it doesn't custody — there is nothing to compute a drawdown
FROM. `0.0` is this codebase's established convention for "this input is
unmeasurable, and the convention is to never let an unmeasured input produce
a false breach" — see `backend/app/services/price_alert_evaluator.py`'s
identical `current_drawdown_pct=0.0` call for a SELL context that similarly
has no drawdown data available. The alternative (blocking every buy against
an Alpaca account because drawdown can't be proven safe) would be the DEF169
failure shape inverted: refusing on an unknown is exactly as wrong as
silently permitting on one, and this floor's own convention throughout
(`not_evaluated` rather than a false pass/fail) is to say plainly when a
check didn't run — a genuine drawdown circuit-breaker for Alpaca accounts
would need AMI to start tracking that account's NAV over time, which is a
future CR, not a schema fix.

**Round 1 shipped the `0.0` but never disclosed it** — round 2 (below) adds
the disclosure without changing this arithmetic at all.

## Round 2 — auditor u66 round-1 findings (MAJOR-1, MAJOR-2, MINOR-1)

Audit round 1 (`orchestration/audit/cr/DEF419-BE.auditor.md`) returned
AWAITING_FIXES on two MAJOR findings and asked Saiful for a ruling on both,
since both are product questions ("what should the preview say/do when it
cannot measure a rule for this account"), not implementation bugs.

**Saiful's ruling, 2026-09-24, verbatim: "Disclose, don't block."**

> For Alpaca-destination previews, the rules AMI cannot measure for that
> account — account drawdown and existing open risk (AMI has no NAV history
> and no stop data for the Alpaca account) — are NOT evaluated against
> fabricated or foreign-denominated numbers, and the preview response states
> it explicitly. Every measurable rule still applies; the NEW trade's own
> risk still counts against the open-risk cap measured against the Alpaca
> equity.

### MAJOR-1 — open risk was summed at the wrong denominator

`ctx.existing_open_risk_pct` (a percentage OF THE AMI PORTFOLIO, built by
`SimEngine._risk_limit_context` from AMI's own open trade rows and their
stops) was being added directly to a cap compared against the ALPACA
account's equity — the exact defect DEF419 itself was filed to fix,
recurring in this one rule (`sim_engine.py` `preview()`, pre-round-2).

**Fix:** on the account-snapshot path, `existing_open_risk_pct` passed to
`check_mandate_compliance` is now `0.0` — explicitly reported via
`unmeasured_rules` (below), not silently carried over from AMI's ledger at
the wrong scale. Per the ruling, the NEW trade's own risk still counts:
`SimEngine.preview()` gained a `stop` parameter (`preview_trade` now
forwards `req.stop`, previously dropped on every preview path, AMI or
Alpaca), forwarded to `check_mandate_compliance` as `proposed_stop` — so
`proposed_contribution` (position size × stop distance, priced against
`portfolio_value`, which is the snapshot's own equity on this path) is
still compared against the cap and can still breach it on its own.

### MAJOR-2 — drawdown was silently zeroed

Round 1 passed `current_drawdown_pct=0.0` with no signal to the caller that
the check had not actually run. **Fix:** same `0.0` arithmetic (see Known
limitation above — there genuinely is no better number), now paired with an
explicit entry in `unmeasured_rules`.

### The `unmeasured_rules` field

`PreviewTradeResponse.unmeasured_rules: list[{"rule": str, "reason": str}]`
— empty on the AMI (no-account) path; on the account-snapshot path, always
exactly `drawdown` and `existing_open_risk` (the two rules AMI structurally
cannot measure for an externally-custodied account). Built in
`SimEngine.preview()`'s account-snapshot branch, forwarded byte-for-byte
through `PreviewResult.unmeasured_rules` → `PreviewTradeResponse`. Mobile
(`SimPreviewResult.unmeasuredRules`, `UnmeasuredRule`) renders it as one
plain sentence — `tradeTicketUnmeasuredRulesNote` — in the ALPACA PAPER
outcome (a second SnackBar line, since an accepted single-leg Alpaca submit
pops the ticket sheet before the outcomes panel could show it) and in
BOTH's Alpaca leg (the outcomes panel, which does not pop). Only rendered
on an ACCEPTED outcome — a rejected preview shows the violation, not the
disclosure.

### MINOR-1 — the no-persistence guard was narrower than its claim

`test_account_context_preview_never_persists` counted only
`SimPortfolioRow` and dismissed the trade tables by comment rather than by
checking. Widened to also assert zero rows across `sim_trades`,
`sim_short_positions` and `sim_option_trades`, before and after an
account-context preview.

### Tests added (round 2)

`test_unmeasured_rules_empty_on_ami_path`,
`test_unmeasured_rules_names_drawdown_and_open_risk_on_snapshot_path`,
`test_unmeasured_rules_absent_when_every_rule_is_measurable`,
`test_open_risk_not_carried_over_from_ami_at_the_wrong_denominator` (the
MAJOR-1 regression itself — a real, large AMI position no longer blocks an
unrelated preview against a large, empty Alpaca account),
`test_new_trades_own_risk_still_counts_against_alpaca_equity` (the ruling's
own requirement — proves the SAME order/stop blocks against a small Alpaca
account and clears against a large one, by its own contribution alone).
`test_account_context_preview_never_persists` widened in place. All five
new tests were verified to fail when their fix is reverted (mutation
check, not merely asserted).

## Malformed input — 422, never a silent fallback

`AccountSnapshotIn`'s bounds are enforced by FastAPI/Pydantic before the
route handler ever runs: negative equity/cash, zero or non-finite equity, an
unrecognised `kind`, a negative position quantity, a malformed ticker
pattern, or an unexpected extra field all produce a `422` with no compliance
verdict at all. This is deliberate degrade-loudly (CLAUDE.md, CR040): a
caller that sends a broken snapshot must be told the snapshot was rejected,
never quietly routed to the AMI account's numbers instead — that fallback IS
the failure mode this DEF fixes, so introducing a *new* one to handle bad
input would be the same mistake with different packaging. Covered by
`test_malformed_account_snapshot_is_422_not_silent_fallback` (8 cases) +
`test_non_finite_equity_rejected_at_the_schema` (NaN/±inf, tested at the
schema level since standard JSON transport can't carry a NaN literal at
all — Python's own `json.dumps` refuses it before the request is even sent)
+ `test_malformed_account_never_silently_checks_against_ami_instead`
(the specific regression: a malformed snapshot sized to slip past a
tight AMI-side cap must still 422, not silently evaluate against AMI).

## Invariant preserved: preview never persists

The account-snapshot branch is pure arithmetic over the request body and the
live market quote — no new `get_session()` call, no write. Guarded by
`test_account_context_preview_never_persists`, which counts
`SimPortfolioRow` rows for the user before/after an account-context preview
and asserts the count grows by at most the pre-existing lazy
`ensure_portfolio()` create (unrelated to this DEF — happens on the very
first touch of any user's AMI portfolio, account snapshot or not) — **round
2 widened this to also assert zero rows across `sim_trades`,
`sim_short_positions` and `sim_option_trades`** (auditor u66 MINOR-1; see
"Round 2" above).

## Tests

`backend/tests/unit/test_def419_per_account_mandate_check.py`, 25 tests
(20 from round 1 + 5 from round 2):

1. No `account` on the request → byte-identical to pre-DEF419 (AMI portfolio).
2. Same order rejected against a small account, accepted against a larger
   one, in **both directions** (AMI-small/Alpaca-big and
   Alpaca-small/AMI-big) — proves the check reads the SUPPLIED account, not
   a fixed one either way.
3. Cash sufficiency reads the snapshot's own cash, not AMI's.
4. 8 malformed-snapshot → 422 cases (negative equity/cash, zero equity,
   unknown `kind`, negative position qty, bad ticker pattern, unexpected
   extra field) + a schema-level non-finite case + the
   never-silently-falls-back-to-AMI regression.
5. Existing snapshot holdings count toward the sector cap (genuinely
   additive by existing `_sector_cap_breach` design) and toward the CR171
   gross-exposure short path; a documented negative control proving the
   single-name cap on a plain BUY does NOT add an existing same-ticker
   holding — pre-existing, deliberate `check_mandate_compliance` design
   (its own §6 comment: "adding to a held position is the case
   `max_open_positions` deliberately permits"), unchanged by this DEF, and
   this test protects it from an incorrect "fix" later.
6. Per-account: long-only short-detection reads the SNAPSHOT's holdings
   (an Alpaca account already holding the ticker can sell-to-close there
   even with zero AMI history, and vice versa).
7. Per-user: over-trading brake and post-loss cooldown fire/don't-fire
   identically across both the no-account and account-snapshot paths.
8. Mandate-level: halal fires identically regardless of account.
9. Preview never persists, account-context or not — widened (round 2) to
   every trade table, not only the portfolio row.
10. (Round 2) `unmeasured_rules` is empty on the AMI path and carries
    exactly `drawdown` + `existing_open_risk` on the snapshot path.
11. (Round 2) The MAJOR-1 regression: a large, real AMI open-risk figure no
    longer blocks a preview against an unrelated, large, empty Alpaca
    account.
12. (Round 2) The ruling's own requirement: the SAME order/stop blocks
    against a small Alpaca account and clears against a large one, by the
    new trade's own contribution alone.

All 25 pass. Full existing `sim`/`safety_floor`/ticker-existence-guard/
wire-contract/CR101-BE2-call-site-guard/CR026-sector/Alpaca-schema suites
pass unchanged.

## Mobile follow-up — DELIVERED (was a spec, now implemented; see "Round 2")

This section originally specified the mobile work as a forward design (it
predates the mobile half landing). The mobile half has since been built,
audited (`DEF419-MOBILE`), and round-2'd alongside this backend round —
see `orchestration/audit/cr/DEF419-MOBILE.architect.md`. Left below for its
original design rationale, which still matches the shipped shape:

- **Alpaca-only (`_submitAlpacaOnly`, `trade_ticket_sheet.dart:663`).**
  Before calling `preview()`, fetch the linked account's current state via
  `AlpacaClient.account()` + `AlpacaClient.positions()` (both already exist
  per CR202/CR227 — used today only to render the Alpaca portfolio screen).
  Map the result to `{kind: "alpaca_paper", equity, cash, positions: [...]}`
  and pass it as `preview(...).account`. The existing accepted/rejected
  branch logic in `_submitAlpacaOnly` is otherwise unchanged — it already
  reads `preview.accepted`/`preview.violations`/`preview.blockedBy`, and
  `account_kind` on the response is available for the outcome label if
  wanted ("checked against your Alpaca paper account").
- **BOTH (`destination == TradeDestination.both`, :625-652).** Run **two
  independent previews** — one with no `account` (AMI) and one with the
  Alpaca snapshot — rather than gating the Alpaca leg on the AMI leg's own
  verdict as today. Each leg submits (AMI via `sim.submit()`, Alpaca via
  `AlpacaClient.submitOrder()`) **only on its own preview's acceptance** —
  the two accounts can legitimately disagree (the whole point of this DEF),
  so a rejection on one account must never veto an accepted trade on the
  other. The result panel (`_destinationOutcomes`) shows both outcomes
  independently, same shape it already renders when both legs fire today,
  just no longer coupled by the AMI leg's own accept/reject.
- Not itself part of that follow-up's scope: this backend change makes no
  assumption about UI copy or how a mixed outcome (accepted on one account,
  rejected on the other) is presented — that's a product/design decision
  for whoever picks up the mobile work.

## Status

`fixed` — both halves (backend + mobile) are implemented, tested, and have
been through round 2 of independent audit (`DEF419-BE`, `DEF419-MOBILE`;
see `orchestration/audit/cr/`), which found and closed MAJOR-1/MAJOR-2/
MINOR-1 on the backend side and MAJOR-1/MAJOR-2/MINOR-1 on the mobile side
(see those two `.architect.md` files' "## Round 2" sections for the
per-finding fix/test/mutation evidence). Not yet promoted to Alpha —
`/promote-to-alpha` still owed for the backend half; the mobile build ships
separately via TestFlight/Play.
