# CR222 — Training-lane honesty: charged toll, passive twin, pre-registration, behaviour diagnostics

**Status:** in_progress · **Owner:** coder.api (backend first), coder.mobile (surfacing follow-on) · **Filed:** 2026-09-11 · **Tag:** `(AT:R76 CR222)`

**Origin:** AMI Research review of the repository against the retail-investor evidence base
(Barber & Odean 2000; Barber, Lee, Liu & Odean 2009; Odean 1998; Coval, Hirshleifer &
Shumway 2021; Ivković, Sialm & Weisbenner 2008; Cremers & Pareek 2016; Morningstar Mind
the Gap 2025/2026). Drafted outside the harness under the handle `training-lane-honesty`;
the original draft and its evidence CSVs are preserved verbatim in
[`docs/Research/RES007_individual_investor_evidence/`](../../Research/RES007_individual_investor_evidence/)
(renamed from `res007/` per Saiful's ruling). This document is the governing version: it
carries Saiful's rulings of 2026-09-11 and corrects seven factual errors in the draft
(§Corrections).

---

## Rulings (Saiful, 2026-09-11, in-session)

1. **Toll: option B — charge it, no backfill.** Ruled after the full display-vs-charge
   argument was presented (proxy error bars, twin confound, D-5 gate). Charging starts at
   flag-on only; existing portfolios and history are untouched. Per the draft's own terms
   for option B, the fill-path change carries **GATE: independent** (money path, D-5).
   The measured-spread upgrade (charge a live-quote half-spread instead of the flat proxy)
   is filed as follow-on handle `measured-toll`.
2. **Day Trader preset: EXEMPT from pre-registration.** Against the draft's
   recommendation, recorded here with the draft's contrary rationale intact: the draft
   argued the preset population most needs the field (lessons 366–370; CR129 removed risk
   limits, not process). Saiful ruled exempt.
3. **Research folder** renamed to `docs/Research/RES007_individual_investor_evidence/`.
4. **Build scope: all four features**, order 3 → 2 → 1 → 4 (pre-registration → passive
   twin → toll → diagnostics).

## What

Four additions to the **training lane only**. None touches the game lane, the safety
floor's compliance side beyond one new deterministic block, or agent prompts.

1. **Training toll (charged).** Every training fill computes an estimated transaction
   cost (spread + commission proxy) and **charges it against cash** via the same fill-fee
   mechanism the game lane already uses. Cumulative toll is stored and surfaced. No
   backfill: fills before flag-on are never re-costed.
2. **Passive twin.** For every training portfolio, the return of a mandate-matched
   passive holding that received the same cash flows on the same dates, shown beside the
   user's own dollar-weighted return in Portfolio Health.
3. **Pre-registration on the trade ticket.** `ProposedTrade` gains `thesis`,
   `invalidation`, `horizon_days`. When the flag is on and the mandate `path` is `active`
   or `both`, the deterministic compliance check refuses a training trade that lacks
   them, with `blocked_by="preregistration"`. Day Trader preset exempt (Ruling 2);
   `long_horizon` exempt by default.
4. **Behaviour diagnostics for every training user.** Generalise CR131's measures from
   the Day Trader preset's before/after comparison into a per-user block in Portfolio
   Health, under CR131's honesty rules verbatim, adding median holding period and
   attention-trade share (new measures — not present in CR131).

## Why

1. **The sim omits the one number that decides individual outcomes.**
   `backend/app/services/portfolio_finding.py:530` states the training lane charges no
   commissions, spreads or taxes. In the measured brokerage data the average household
   earned 18.7% gross and 16.4% net against a 17.9% market — the toll, not stock
   selection, converted a gross win into a net loss (Barber & Odean 2000). The game lane
   already charges 10 bps per side (`games_scoring.py:38`); the training lane charges and
   shows nothing.
2. **The user has no benchmark for their own decisions.** Portfolio Health builds Σ with
   SPY as a leg, so beta/TE/R² exist, but no surface says "with the same money on the
   same dates, held passively, you would have X". Every input exists in
   `portfolio_nav_daily` (CR109) and `price_history_daily`.
3. **Lesson 357 teaches pre-registration; the product does not require it.** The
   individuals with documented persistent outperformance are concentrated, patient and
   informed; concentration without a written reason is the profile of the losing
   majority. A schema field plus one deterministic check, not a model change.
4. **CR131 built the right instrument for the wrong population.** The before/after mirror
   exists only for Day-Trader-preset users; the modal loser in the evidence is the
   ordinary household at 75% annual turnover.

---

## 1. Training toll (charged — Ruling 1)

- **Mechanism:** reuse the game lane's fill-fee mechanism on the training fill path.
  Toll = `max(notional × TRAINING_TOLL_BPS, TRAINING_TOLL_MIN)` per side (defaults
  10.0 / 1.00 — parity with `FEE_BPS`/`FEE_MIN` in `games_scoring.py`). Option legs:
  `TRAINING_TOLL_OPTION_BPS` (default 50.0 — deliberately conservative vs Bryzgalova,
  Pavlova & Sikorskaya 2023's ~8%-of-premium round-trip retail spreads; labeled an
  estimate). Short legs keep the existing `short_borrow_rate.py` accrual — no double
  charge.
- **No backfill (Ruling 1):** charging begins at flag-on. Existing cash, NAV history and
  banked comparisons are untouched; every portfolio's cumulative toll starts at 0.
- **Storage:** toll on the trade row; cumulative toll on the portfolio.
- **Surfacing:** trade confirmation shows the fill's cost, labeled as an estimated
  spread+commission that IS charged in training; Portfolio Health §F block `toll` shows
  the cumulative figure and its share of gross P&L. Wording is M06/M09's; this CR ships
  machine states only.
- **Flag:** `TRAINING_TOLL_ENABLED` default `false` (renamed from the draft's
  `TRAINING_SHADOW_TOLL_ENABLED` — it is no longer shadow); compose parity.
- **GATE: independent** on the fill-path change before promotion (D-5).
- **Follow-on `measured-toll`:** capture the live bid-ask at fill time (Alpaca quotes,
  as `short_borrow_rate.py` already uses Alpaca) and charge the measured half-spread,
  with labeled fallback where no quote exists. Replaces the flat proxy.

## 2. Passive twin

- **Definition:** for a training portfolio with capital events `open` and `restart` (as
  `portfolio_nav_daily` already infers) the twin is a holding of the mandate's passive
  instrument bought with the same cash on the same dates and never traded. Twin and user
  NAV series share the same date grid.
- **Mandate mapping** (`PASSIVE_TWIN_MAP`, config, extendable): `compliance.halal=true`
  → configured Sharia-screened US equity ETF; otherwise SPY. If the mapped ticker has no
  price history for the window: `sufficient:false`, `insufficient_cause="twin_history"` —
  never a silent SPY fallback (CR040/DEF059).
- **Metrics:** dollar-weighted return (IRR over the cash-flow schedule) and time-weighted
  return for both series, plus the difference. **Correction to the draft:** there is no
  bootstrap in Portfolio Health; the difference ships with the existing
  prose-caveat/analytic treatment (the `portfolio_finding.py:521` pattern), and below
  `TWIN_MIN_MARKET_DAYS` (default 20) the block is insufficient; below
  `TWIN_MIN_MARKET_DAYS_FOR_SE` (default 60) the difference renders with the caveat that
  it carries no sampling-error estimate.
- **Toll symmetry (consequence of Ruling 1):** once `TRAINING_TOLL_ENABLED` is on, the
  twin's synthetic deposit-buys are charged the same toll rule from the same date, and
  the block's disclosure sentence states both sides' cost treatment (the twin remains
  untraded and untaxed).
- **Honesty rules (CR131's):** no grade, no warning, no verdict; identical shape ahead or
  behind; the block carries the twin ticker and its expense ratio.
- **Renders:** Portfolio Health §F, new block `passive_twin`, through the closed
  allow-list validator (`portfolio_finding.py` — see Corrections).
- **Flag:** `PORTFOLIO_PASSIVE_TWIN_ENABLED` default `false`; compose parity.

## 3. Pre-registration on the trade ticket

- **Schema:** `ProposedTrade` (`backend/app/schemas/trade.py:183`) gains
  `thesis: str | None` (min 40 chars when required), `invalidation: str | None` (min 20),
  `horizon_days: int | None` (ge=1). `blocked_by` Literal gains `preregistration`.
- **Enforcement:** in `backend/app/agents/safety_floor.py::check_mandate_compliance`
  (see Corrections — `app/agents/`, not `app/services/`), a new deterministic block after
  the existing risk-limit blocks: when `TRAINING_PREREGISTRATION_REQUIRED` is on AND the
  mandate `path` ∈ {`active`, `both`} AND the trade opens or adds to a position (never a
  close, never a stop/target evaluation) AND the Day Trader preset is NOT active
  (Ruling 2 — reuse the preset detection `day_trader_outcomes.py` relies on), missing or
  too-short fields ⇒ `passed=False`, `blocked_by="preregistration"`, one violation string
  naming the missing field (DEF197 shape). `long_horizon` mandates exempt by default;
  `PREREG_APPLIES_TO_LONG_HORIZON` default `false`.
- **Journal:** the three fields land on the journal entry with `mandate_version`. On
  close (`POST /v1/sim/trades/{user_id}/close`, `sim_engine.evaluate_outcomes`) the
  journal entry gains the realised outcome beside the registered thesis and horizon. No
  LLM in the write path.
- **Mobile (follow-on slice, DEF195 ordering):** three fields on the ticket, shown only
  when required; refusal renders the violation string. Backend to Alpha first, verified,
  then mobile.
- **Flag:** `TRAINING_PREREGISTRATION_REQUIRED` default `false`; compose parity.

## 4. Behaviour diagnostics

- **Module:** `backend/app/services/behaviour_diagnostics.py` — a function over any
  user's training trade log and NAV series: annualised turnover, median holding period
  (calendar days, closed lots via `cost_basis_lots.py`), attention-trade share (buys
  within 5 trading days of a ≥10% absolute move in the same ticker, or within 1 day of a
  Room convene on it), disposition ratio (PGR/PLR, Odean 1998, on closed lots).
  `day_trader_outcomes.py` calls the shared function for the measures it already has
  (byte-identical output for its existing fixtures); its before/after framing stays.
  Median holding period and attention-trade share are NEW measures, not lifts.
- **Honesty rules:** CR131's, unchanged. Below `MIN_TRADES_FOR_DIAGNOSTICS` (default 10
  closed lots) or `MIN_ELAPSED_DAYS` (default 60) the block is `too_early` with no
  numbers. Baselines beside each measure with provenance — extend CR131's
  `PUBLISHED_BASELINES`, never duplicate it.
- **Renders:** Portfolio Health §F block `behaviour`. No push, no alert, no streak
  interaction — this CR adds no attention surface.
- **Flag:** `PORTFOLIO_BEHAVIOUR_DIAGNOSTICS_ENABLED` default `false`; compose parity.

---

## Corrections to the draft (verified against code, 2026-09-11)

1. Barber & Odean is NOT cited at `portfolio_finding.py:531` — the zero-cost disclosure
   is there, the citation lives in `day_trader_outcomes.py`'s `PUBLISHED_BASELINES`.
2. `safety_floor.py` is under `backend/app/agents/`, not `app/services/`.
3. Settings live at `backend/app/core/config.py`, not `app/config.py`.
4. The price table is `price_history_daily` (CR136 M01), not `price_history`.
5. The closed allow-list validator lives in `portfolio_finding.py`
   (`Allowlist`/`build_allowlist`/`validate_sections`), not `portfolio_health.py`.
6. No bootstrap exists in Portfolio Health; the draft's "SE via the existing bootstrap"
   is replaced per §2 above. No bootstrap is built for this CR.
7. The handoff's deliverables table lists `etf_candidates_2019_2026.csv`, which was not
   delivered; the folder holds `etf_candidates_long_history.csv` and
   `etf_blends_2019_2026.csv` instead.

## Order of build

3 → 2 → 1 → 4 (Ruling 4). Pre-registration first: smallest surface, and it changes
behaviour rather than describing it. Passive twin second: highest information per line of
code. Toll third (carries the independent-audit gate). Diagnostics fourth.

## Acceptance

- `pytest backend/tests/unit/ -q` green, including `test_config_compose_parity.py` for
  all four flags; `backend/scripts/tests_for_changed.py --since <base>` (CR216) run and
  its selection executed; the full suite before promotion.
- Pre-registration: a training BUY without `thesis` on an `active` mandate is refused
  with `blocked_by="preregistration"` and a violation naming `thesis`; the same trade on
  a `long_horizon` mandate passes; **the same trade under the Day Trader preset passes
  without the fields (Ruling 2)**; a close never requires the fields; the journal entry
  round-trips all three fields and the mandate version; the DEF195 guard passes.
- Passive twin: a fixture portfolio that never trades shows user return = twin return to
  the cent when the twin is the portfolio's only holding; a `restart` event lands in both
  series on the same date; a twin ticker with no history yields `sufficient:false` with
  the named cause, never SPY; the block passes the closed allow-list validator with zero
  unregistered numbers.
- Toll: **flag OFF ⇒ byte-identical `Portfolio` on a replayed fixture** (regression
  guard); **flag ON ⇒ cash reduced by exactly `max(notional × bps, min)` per side**;
  option and short legs carry their own rates without double-charging borrow; the
  cumulative figure survives restart semantics as `portfolio_nav_daily` defines them; no
  charge attaches to any fill dated before flag-on (Ruling 1, no backfill).
- Diagnostics: `day_trader_outcomes.py` produces byte-identical output for its existing
  fixtures after the lift; a user with 9 closed lots gets `too_early` with no numeric
  field in the payload; PGR/PLR on a hand-built lot fixture matches Odean's definition; a
  buy the day after a convene on the same ticker counts as attention-triggered, a buy six
  days later does not.
- Every user-facing string names **AMI**, never "the AI"; wording is M06/M09's, none
  ships from this CR's backend code.
- Live check on Alpha that each flag is off after promotion and that flipping one
  produces the block (CR040).
- **Slice 1 (toll) passes the independent audit handshake
  (`orchestration/audit/PROTOCOL.md`) before promotion** — Ruling 1 accepts the draft's
  stated terms for option B.

## Guards (failure_patterns entries where a second occurrence exists)

- A twin that silently falls back to SPY is the DEF059 shape; pinned by the
  `insufficient_cause` test.
- A pre-registration check that runs on closes would trap users in positions; pinned by
  the close test.
- A toll that leaks into flag-off portfolios (or backfills old fills) is a D-5 money-path
  violation; pinned by the byte-identical-cash flag-off test and the no-charge-before-
  flag-on test.

## Out of scope

- Measured-spread charging — follow-on handle `measured-toll` (live Alpaca quote capture
  at fill, charge the real half-spread, labeled fallback).
- Any change to the game lane, leagues, streaks, or push.
- Surfacing `verdict_outcomes` to users (legal posture, Saiful 2026-09-02 ruling); the
  separate counsel question about a user's own pre-registered hit rate stands.
- A long-horizon loop of its own (annual review surface) — follow-on handle
  `long-horizon-loop`.
- Tax and withholding by domicile — follow-on handle `domicile-toll`.
- The BEDROCK build and DEFENSIBLE_PROCESS — personal-scope documents; no repo action.
  Archived in the RES007 folder. The Sharadar personal-use licence cannot feed the AMI
  product (BEDROCK §11).

## Related

CR109 (NAV spine, game trading cost), CR129/CR131 (preset, outcome mirror), CR136
(Portfolio Health, allow-list validator), CR164 (PIT fundamentals — reused by BEDROCK
Addendum E), CR216 (test selection), CR219/CR221 (fact sheet), DEF110, DEF195, DEF197,
D-5, D-058, D-060.
