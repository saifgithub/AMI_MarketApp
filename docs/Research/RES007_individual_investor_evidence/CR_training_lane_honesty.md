# CR### — Training-lane honesty: shadow toll, passive twin, pre-registration, behaviour diagnostics

**Status:** proposed · **Owner:** coder.api (backend first), coder.mobile (surfacing) · **Filed:** 2026-09-10 · **Tag:** `(AT:R<N> CR###)` — ID to be minted by the Architect; this file was drafted outside the harness under the handle `training-lane-honesty`. Rename the folder and this file on mint. Do not hand-edit `cr_list.md`; write `_registry/CR###.row.md` and regenerate (CR081).

**Origin:** AMI Research review of the repository against the retail-investor evidence base (Barber & Odean 2000; Barber, Lee, Liu & Odean 2009; Coval, Hirshleifer & Shumway 2021; Ivković, Sialm & Weisbenner 2008; Cremers & Pareek 2016; Morningstar Mind the Gap 2025/2026). Saiful, 2026-09-10: the README is stale; this CR is written against the code as of `2026-09-03 research(CR221)`.

---

## What

Four additions to the **training lane only**. None touches the game lane, the safety floor's compliance side, `_execute_fill`, or agent prompts.

1. **Shadow toll.** Every training fill computes an *estimated* transaction cost (spread + commission proxy) and a running cumulative toll, displayed but **not charged**. The training lane's zero-cost design is unchanged; what changes is that the user can see the number the sim is not charging them.
2. **Passive twin.** For every training portfolio, the return of a mandate-matched passive holding that received the *same cash flows* on the *same dates* as the user's portfolio, shown beside the user's own dollar-weighted return in Portfolio Health.
3. **Pre-registration on the trade ticket.** `ProposedTrade` gains `thesis`, `invalidation`, `horizon_days`. When the flag is on and the mandate `path` is `active` or `both`, the deterministic compliance check refuses a training trade that lacks them, with `blocked_by="preregistration"`. Stored on the journal entry with the mandate version, and replayed beside the outcome at close.
4. **Behaviour diagnostics for every training user.** Generalise CR131's measures — turnover, median holding period, share of buys placed within 5 trading days of a ≥10% move or a Room convene on the same ticker, disposition ratio (proportion of gains realised vs proportion of losses realised, Odean 1998) — from the Day Trader preset's before/after comparison into a per-user block in Portfolio Health, under CR131's honesty rules verbatim.

## Why

1. **The sim omits the one number that decides individual outcomes.** `portfolio_finding.py:531` states the training lane charges no commissions, spreads or taxes, and cites Barber & Odean while doing so. In the measured brokerage data the average household earned 18.7% gross and 16.4% net against a 17.9% market — the toll, not stock selection, converted a gross win into a net loss. A sim that never shows the toll teaches the wrong expected value for every trade it approves. The game lane already charges 10 bps per side (`games_scoring.py:38`); the training lane shows nothing.

2. **The user has no benchmark for their own decisions.** `portfolio_health.py` builds Σ with SPY as a leg, so beta, TE and R² exist; the game lane scores benchmark-relative. But no surface tells a training user "with the same money on the same dates, held passively, you would have X". The evidence says most active individuals are behind that number and do not know it (Barber & Odean; Morningstar's 1.2-point gap, which for US stock-fund holders who did nothing was near zero). This is the single most informative figure the app can show, and every input already exists in `portfolio_nav_daily` (the equity-curve spine, CR109 slice 1) and `price_history`.

3. **Lesson 357 teaches pre-registration; the product does not require it.** `ProposedTrade` (`schemas/trade.py:183`) carries ticker, side, quantity, order type, limit. No thesis, no invalidation, no horizon. The individuals with documented persistent outperformance are concentrated, patient (holding durations over two years) and informed (Coval et al.; Ivković et al.; Cremers & Pareek). Concentration without a written reason is the profile of the losing majority. Requiring the paragraph before the fill is the product form of that distinction, and it is a schema field plus one deterministic check, not a model change.

4. **CR131 built the right instrument for the wrong population.** The before/after mirror exists only for users who switched on the Day Trader preset. The modal loser in the evidence is the ordinary household at 75% annual turnover, not the day trader. The measures, the too-early refusal, the no-moralising rule and the published baselines all transfer unchanged.

---

## 1. Shadow toll (training lane)

**Design decision offered to Saiful, default = A:**

- **A — display only (default).** No change to `_execute_fill` or cash. A `TollEstimate` (spread_bps, commission, total) is computed per fill from the fill notional and stored on the trade row; `Portfolio` gains `cumulative_toll_estimate`. Rationale: `_execute_fill` is the money path (D-5, independent audit on touch); the game lane already proves the fee plumbing, so display-only ships without re-auditing the fill.
- **B — charge it.** Reuse the game lane's `fee` parameter on `_execute_fill` for training fills. Changes every user's cash and every historical comparison; requires `GATE: independent` and a decision on backfilling existing portfolios. Not recommended in this CR.

**Estimate:** `SHADOW_TOLL_BPS` (default 10.0, matching `FEE_BPS`), applied to notional on both sides, plus `SHADOW_TOLL_MIN` (default 1.00). Short legs: add the borrow accrual `short_borrow_rate.py` already computes. Option legs: `SHADOW_TOLL_OPTION_BPS` (default 50.0 — retail option spreads are an order of magnitude wider; Bryzgalova, Pavlova & Sikorskaya 2023 measure round-trip spreads near 8% of premium; the default is deliberately conservative and named as an estimate).

**Surfacing:** trade confirmation shows `Estimated cost of this fill: $x (not charged in training)`; Portfolio Health §F block `toll` shows cumulative estimate and its share of gross P&L. Wording is M06/M09's; this CR ships machine states only.

**Flag:** `TRAINING_SHADOW_TOLL_ENABLED` default `false`; forwarded in `docker-compose.yml` `api-alpha` block (`test_config_compose_parity.py`).

## 2. Passive twin

**Definition.** For a training portfolio with capital events `open` and `restart` (as `portfolio_nav_daily` already infers) and deposits of `starting_capital`, the twin is a holding of the mandate's passive instrument bought with the same cash on the same dates and never traded. Twin NAV series and user NAV series share the same date grid.

**Mandate mapping** (`PASSIVE_TWIN_MAP`, config, extendable): `compliance.halal=true` → a Sharia-screened US equity ETF (configured ticker); otherwise SPY. The map is data, not code, so a mid-cap or sector mandate can map elsewhere later. If the mapped ticker has no price history for the window, the block is `sufficient:false` with `insufficient_cause="twin_history"` — never a fallback to SPY without saying so (CR040).

**Metrics.** Both series report the same two numbers: dollar-weighted return (IRR over the cash-flow schedule, the Morningstar definition) and time-weighted return, plus the difference. Standard error via the existing bootstrap in `portfolio_health.py`. Below `TWIN_MIN_MARKET_DAYS` (default 20) the block is insufficient; below `TWIN_MIN_MARKET_DAYS_FOR_SE` (default 60) the difference renders without an SE and says so.

**Honesty rules (CR131's, verbatim in spirit):** no grade, no warning, no verdict; identical shape for a user ahead of the twin and a user behind it; the block carries the twin ticker, its expense ratio, and the sentence that the twin is untraded and untaxed exactly as the user's portfolio is.

**Where it renders:** Portfolio Health §F, new block `passive_twin`, through the same closed allow-list validator — every number it emits is registered.

**Flag:** `PORTFOLIO_PASSIVE_TWIN_ENABLED` default `false`; compose parity.

## 3. Pre-registration on the trade ticket

**Schema.** `ProposedTrade` gains:

```
thesis: str | None            # min 40 chars when required
invalidation: str | None      # min 20 chars when required
horizon_days: int | None      # ge=1
```

**Enforcement.** In `safety_floor.check_mandate_compliance`, a new deterministic block after the existing risk-limit blocks: when `TRAINING_PREREGISTRATION_REQUIRED` is on AND the mandate `path` ∈ {`active`, `both`} AND the trade opens or adds to a position (not a close, not a stop/target evaluation), missing or too-short fields ⇒ `passed=False`, `blocked_by="preregistration"`, one violation string naming the missing field. `long_horizon` mandates are exempt by default (their loop is annual, not per-trade); `PREREG_APPLIES_TO_LONG_HORIZON` default `false`.

**Day Trader preset:** not exempt. CR129 removed risk limits; it did not remove process. Ruling requested if Saiful disagrees — the evidence (lessons 366–370) says this is the population that most needs the field.

**Journal.** The three fields land on the journal entry with `mandate_version`, as trades already do. On close (`/trades/{user_id}/close` and `evaluate_outcomes`), the journal entry gains the realised outcome beside the registered thesis and horizon, so a review reads thesis → invalidation → what happened. No LLM in the write path.

**Mobile.** Three fields on the trade ticket, shown only when the flag is on and the mandate path requires them; the refusal renders the violation string (the DEF197 shape: name the field, not "trade blocked").

**Flag:** `TRAINING_PREREGISTRATION_REQUIRED` default `false`; compose parity. Backend to Alpha first, verified, then mobile (the DEF195 ordering) — a client that sends fields the backend lacks gets a 200 that drops them.

## 4. Behaviour diagnostics

**Module.** `services/behaviour_diagnostics.py`, lifting the measures from `day_trader_outcomes.py` into a function over any user's training trade log and NAV series: annualised turnover, median holding period (calendar days, closed positions), attention-trade share (buys within 5 trading days of a ≥10% absolute move in the same ticker, or within 1 day of a Room convene on it), disposition ratio (PGR/PLR, Odean 1998, on closed lots via `cost_basis_lots.py`). `day_trader_outcomes.py` should call the shared function rather than keep its own copy; its before/after framing stays.

**Honesty rules:** CR131's, unchanged. Below `MIN_TRADES_FOR_DIAGNOSTICS` (default 10 closed lots) or `MIN_ELAPSED_DAYS` (default 60) the block is `too_early` with no numbers. Baselines rendered beside each measure with provenance (Barber & Odean turnover 75%/250%; Odean 1998 disposition; the same `PUBLISHED_BASELINES` register CR131 uses, extended, not duplicated).

**Where it renders:** Portfolio Health §F block `behaviour`. No push, no alert, no streak interaction — this CR adds no attention surface.

**Flag:** `PORTFOLIO_BEHAVIOUR_DIAGNOSTICS_ENABLED` default `false`; compose parity.

---

## Order of build

3 → 2 → 1 → 4. Pre-registration first: smallest surface, one schema and one deterministic check, and it is the piece that changes user behaviour rather than describing it. Passive twin second: highest information per line of code, all inputs present. Shadow toll third. Diagnostics fourth, because it is mostly a refactor of CR131.

## Acceptance

- `pytest backend/tests/unit/ -q` green, including `test_config_compose_parity.py` for all four flags.
- `backend/scripts/tests_for_changed.py --since <base>` (CR216) run and its selection executed; the full suite before promotion.
- Pre-registration: a training BUY without `thesis` on an `active` mandate is refused with `blocked_by="preregistration"` and a violation naming `thesis`; the same trade on a `long_horizon` mandate passes; a close never requires the fields; the journal entry round-trips all three fields and the mandate version; the DEF195 guard passes (every key the client PATCHes/POSTs exists on the deployed backend).
- Passive twin: a fixture portfolio that never trades shows user return = twin return to the cent for a twin that is the portfolio's only holding; a portfolio with a `restart` event has the second deposit reflected in both series on the same date; a twin ticker with no history yields `sufficient:false` and the named cause, never SPY; the block passes the closed allow-list validator with zero unregistered numbers.
- Shadow toll: a fill's estimate equals `max(notional × bps, min)` on both sides; cash after the fill is unchanged from before this CR (byte-identical `Portfolio` for a replayed fixture); option and short legs carry their own rates; the cumulative figure survives restart semantics as `portfolio_nav_daily` defines them.
- Diagnostics: `day_trader_outcomes.py` produces byte-identical output for its existing fixtures after the lift; a user with 9 closed lots gets `too_early` with no numeric field in the payload; PGR/PLR computed on a hand-built lot fixture matches Odean's definition; a buy the day after a convene on the same ticker counts as attention-triggered, a buy six days later does not.
- Every user-facing string names **AMI**, never "the AI"; every string is M06/M09's and none ships from this CR's backend code.
- Live check on Alpha that each flag is off after promotion and that flipping one produces the block (CR040: a feature that is dark must be dark loudly).

## Guards (failure_patterns entries where a second occurrence exists)

- A twin that silently falls back to SPY is the DEF059 shape; pinned by the `insufficient_cause` test.
- A pre-registration check that runs on closes would trap users in positions; pinned by the close test.
- A charged toll in the training lane without `GATE: independent` is a D-5 violation; pinned by the byte-identical-cash test.

## Out of scope

- Charging the toll (option B) — separate CR with independent audit if ruled.
- Any change to the game lane, leagues, streaks, or push.
- Surfacing `verdict_outcomes` to users (legal posture, Saiful 2026-09-02 ruling) — a separate question for counsel: whether a user's *own* decision record (their hit rate on their own pre-registered trades) is the user's data rather than an AMI performance claim.
- A long-horizon loop of its own (annual review surface) — filed as a follow-on handle `long-horizon-loop`.
- Tax and withholding by domicile — follow-on handle `domicile-toll`, content plus a mandate field, not a sim change.

## Related

CR109 (NAV spine, game trading cost), CR129/CR131 (preset, outcome mirror), CR136 (Portfolio Health, allow-list validator), CR164 (PIT fundamentals), CR216 (test selection), CR219/CR221 (fact sheet), DEF110 (evaluate_outcomes phantom shares — the close path this CR's journal replay depends on), DEF195, DEF197, D-5, D-058, D-060.
