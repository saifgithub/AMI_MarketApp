"""CR136 M05 — deterministic Portfolio Health rule engine (R0–R5): hysteresis state machines over the stripped metric context; every interpolated number registered for the M06 validator allow-list. No LLM, no DB.

The LLM never invents advice. It is handed a fixed template and a dict of slot
values that this engine computed, and the validator downstream rejects any
number in the generated text that is not one of them — which only works because
every value a template interpolates, INCLUDING the literal "40" inside R1's own
sentence, is registered here.

**Hysteresis is mandatory, not a refinement.** Under EWMA the measured
boundary-flip rate is 21.3% (against 8.9% for an equal-weight window): without
a band, a metric sitting near its threshold crosses back and forth week to week
and the report contradicts itself for reasons that have nothing to do with the
portfolio. Each estimated-quantity rule is therefore a two-line state machine —
fire on the fire line, stay fired until the clear line — with state persisted in
the Finding payload and read back next time. CI-lower-bound gating was measured
as the alternative and REJECTED: detection collapsed to 50.8% on a genuinely
high-beta book, worse on both axes.

**Gate unmet ⇒ forced cleared.** When a rule's n-gate fails or an input arrives
as `None` (the block was insufficient and M06 stripped it), the rule has no
current number to cite, so it cannot stay fired. An alarm with nothing behind it
is exactly the failure CR040 exists to prevent, and a fired rule with stripped
inputs would have no registered slots to render anyway.

**R0 mirrors the trade gate rather than re-deriving it.** Its caps come from
`safety_floor.single_name_cap_pct` and `sector_allocation.sector_concentration_cap`
at call time — the same resolvers the trade ticket enforces — so the cap number
this report SHOWS can never differ from the number the gate ENFORCES. Copying
the values instead would reintroduce exactly the shown-vs-enforced split CR046
closed.

Pure: no I/O, no clock, no randomness. State in, state out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from app.agents.safety_floor import single_name_cap_pct
from app.schemas import Mandate
from app.services.portfolio_health_constants import (
    ETF_OVERLAP_DISCLOSURE,
    LOW_R2_THRESHOLD,
    RULE_R1_CLEAR_TOP_RISK_SHARE_PCT,
    RULE_R1_FIRE_TOP_RISK_SHARE_PCT,
    RULE_R1_MIN_RISKY_HOLDINGS,
    RULE_R1_TEXTBOOK_THRESHOLD_PCT,
    RULE_R2_CLEAR_DR2,
    RULE_R2_FIRE_DR2,
    RULE_R2_MIN_HOLDINGS,
    RULE_R2B_CLEAR_RHO,
    RULE_R2B_FIRE_RHO,
    RULE_R2B_MIN_PAIR_WEIGHT_PCT,
    RULE_R3_BETA_BASE,
    RULE_R3_SE_BAND_MULT,
    RULE_R4_CLEAR_CASH_PCT,
    RULE_R4_FIRE_CASH_PCT,
)
from app.services.sector_allocation import OTHER, sector_concentration_cap

RULE_IDS: tuple[str, ...] = ("R0", "R1", "R2", "R2b", "R3", "R4", "R5")

FIRED = "fired"
CLEARED = "cleared"

# Sector-weight comparison epsilon, mirroring `sector_allocation`'s own breach
# test exactly. Copied deliberately with its source named: R0 must agree with
# the allocation surface on the same book, and a different epsilon is a
# disagreement waiting for a boundary case.
_SECTOR_EPSILON = 1e-9

# Rev 4's rule table, verbatim. M06 renders these and the deterministic fallback
# ships these same strings, so any drift here changes what the product says.
# retranslate:[ar,ms]
RULE_TEMPLATES: dict[str, str] = {
    "R0": (
        "Your mandate caps a single {scope} at {cap}%. {name} is at {weight}% "
        "of invested value today."
    ),
    "R1": (
        "When a single position accounts for more than 40% of a portfolio's "
        "risk, the textbook response is to consider whether the concentration "
        "is intentional. Here, {ticker} accounts for {risk_share}% of risk "
        "while holding {weight}% of invested value."
    ),
    "R2": (
        "You hold {n} positions but about {dr2} effective independent bets — "
        "they have tended to move together. Textbook practice adds exposures "
        "that behave differently, not more of the same."
    ),
    "R2b": (
        "{a} and {b} moved almost identically over the window (correlation "
        "{rho}). Two holdings that move together provide less diversification "
        "than two that don't."
    ),
    "R3": (
        "β = {beta} (market explains {r2_pct}% of daily moves; {window}-day "
        "window) — this book has moved about {beta}× the S&P 500 over the "
        "measured window."
    ),
    "R4": (
        "{cash}% of your book is cash. Cash scales the whole-book volatility "
        "and beta down in proportion — it does not change how concentrated the "
        "invested sleeve is: risk shares and effective bets are unchanged by it."
    ),
    "R5": (
        "Metrics exclude {dropped} ({reasons}). Treat the numbers as describing "
        "{covered}% of your invested value."
    ),
}

_DROP_REASON_COPY = {
    "short_history": "short history",
    "data_quality": "data quality",
}


@dataclass(frozen=True)
class HoldingInput:
    """One risky holding as the rule engine sees it. Cash is never a row here.

    `invested_weight_pct` is over the FULL invested sleeve — dropped holdings
    included in the denominator — because a holding excluded from Σ for want of
    history still occupies its share of the user's money, and R0's cap and R5's
    coverage figure both have to say so.
    """

    ticker: str
    invested_weight_pct: float
    sector: str
    included: bool
    drop_reason: str | None = None
    risk_share_pct: float | None = None


def _step(
    state: str,
    value: float,
    fire_line: float,
    clear_line: float,
    *,
    low_is_bad: bool = False,
) -> str:
    """One hysteresis transition. Boundary operators are Rev 4's exactly.

    High-is-bad: fire at `value >= fire_line`, clear at `value < clear_line`.
    Low-is-bad (R2, where a SMALL DR² is the alarm): fire at `value <
    fire_line`, clear at `value > clear_line`. Anything between the lines leaves
    the state untouched — that is the whole mechanism.
    """
    if low_is_bad:
        if state == CLEARED:
            return FIRED if value < fire_line else CLEARED
        return CLEARED if value > clear_line else FIRED
    if state == CLEARED:
        return FIRED if value >= fire_line else CLEARED
    return CLEARED if value < clear_line else FIRED


def _result(rule_id: str, state: str, slots: dict, based_on: list[str]) -> dict:
    return {
        "rule_id": rule_id,
        "fired": state == FIRED,
        "state": state,
        "slots": slots if state == FIRED else {},
        "based_on": based_on,
    }


def _prior(rule_states: dict[str, str] | None, rule_id: str) -> str:
    """A missing or unrecognised state is `cleared`. A first Finding has no
    prior state, and an unknown value must not be able to make a rule start
    life already fired."""
    if not rule_states:
        return CLEARED
    return FIRED if rule_states.get(rule_id) == FIRED else CLEARED


def evaluate_rules(
    *,
    mandate: Mandate,
    holdings: list[HoldingInput],
    dr2: float | None,
    beta: float | None,
    se_beta: float | None,
    r2: float | None,
    beta_window_days: int | None,
    cash_pct_total: float,
    pairwise_rho: list[tuple[str, str, float]] | None,
    contains_etfs: bool,
    rule_states: dict[str, str] | None = None,
) -> tuple[list[dict], dict[str, str]]:
    """Evaluate all seven rules. Returns `(results, updated_rule_states)`.

    `results` is always seven entries in the order R0, R1, R2, R2b, R3, R4, R5;
    `updated_rule_states` always carries all seven keys, so M06 can persist it
    verbatim and hand it straight back next time.
    """
    included = [h for h in holdings if h.included]
    dropped = [h for h in holdings if not h.included]
    states: dict[str, str] = {}
    results: list[dict] = []

    # ── R0 — mandate check. Accounting: mirrors the gate, carries no band. ──
    name_cap = float(single_name_cap_pct(mandate))
    sector_cap_frac = float(sector_concentration_cap(mandate))
    sector_cap_pct = sector_cap_frac * 100.0

    breaches: list[dict] = []
    for holding in holdings:
        # Strict `>`, mirroring the floor's own `position_pct > cap` test — a
        # holding exactly AT its cap is compliant at the trade ticket and must
        # be compliant here too.
        if holding.invested_weight_pct > name_cap:
            breaches.append({
                "scope": "name",
                "cap_pct": name_cap,
                "name": holding.ticker,
                "weight_pct": round(holding.invested_weight_pct, 1),
            })

    by_sector: dict[str, float] = {}
    for holding in holdings:
        by_sector[holding.sector] = (
            by_sector.get(holding.sector, 0.0) + holding.invested_weight_pct
        )
    for sector, weight_pct in sorted(by_sector.items()):
        # The unclassified bucket never breaches — it is our ignorance about the
        # book, not a fact about it (the DEF059 inversion guard).
        if sector == OTHER:
            continue
        if (weight_pct / 100.0) > sector_cap_frac + _SECTOR_EPSILON:
            breaches.append({
                "scope": "sector",
                "cap_pct": sector_cap_pct,
                "name": sector,
                "weight_pct": round(weight_pct, 1),
            })

    states["R0"] = FIRED if breaches else CLEARED
    results.append(_result(
        "R0", states["R0"],
        {
            "breaches": breaches,
            "etf_disclosure": bool(contains_etfs),
        },
        ["invested_weights", "sector_weights"],
    ))

    # ── R1 — concentration ──────────────────────────────────────────────────
    shares = [
        (h, h.risk_share_pct) for h in included if h.risk_share_pct is not None
    ]
    r1_gate = len(included) >= RULE_R1_MIN_RISKY_HOLDINGS and bool(shares)
    if not r1_gate:
        states["R1"] = CLEARED
        results.append(_result("R1", CLEARED, {}, ["risk_contribution"]))
    else:
        top, top_share = max(shares, key=lambda pair: pair[1])
        states["R1"] = _step(
            _prior(rule_states, "R1"), top_share,
            RULE_R1_FIRE_TOP_RISK_SHARE_PCT, RULE_R1_CLEAR_TOP_RISK_SHARE_PCT,
        )
        results.append(_result(
            "R1", states["R1"],
            {
                "ticker": top.ticker,
                "risk_share": round(top_share, 1),
                "weight": round(top.invested_weight_pct, 1),
                # Not a format slot — the template says "40" in prose. Registered
                # anyway, or M06's allow-list would reject the engine's own
                # mandated sentence (F15).
                "threshold_mention": RULE_R1_TEXTBOOK_THRESHOLD_PCT,
            },
            ["risk_contribution"],
        ))

    # ── R2 — correlated cluster ─────────────────────────────────────────────
    if dr2 is None or len(included) < RULE_R2_MIN_HOLDINGS:
        states["R2"] = CLEARED
        results.append(_result("R2", CLEARED, {}, ["effective_bets"]))
    else:
        states["R2"] = _step(
            _prior(rule_states, "R2"), dr2,
            RULE_R2_FIRE_DR2, RULE_R2_CLEAR_DR2, low_is_bad=True,
        )
        results.append(_result(
            "R2", states["R2"],
            {"n": len(included), "dr2": round(dr2, 1)},
            ["effective_bets"],
        ))

    # ── R2b — pairwise overlap ──────────────────────────────────────────────
    # The rule R2's n>=8 gate structurally silences: measured, DR² < 2.0 on every
    # overlap book tested at n=2–5 and R2 fired on none of them.
    weight_of = {h.ticker: h.invested_weight_pct for h in included}
    qualifying: list[tuple[str, str, float]] = []
    if pairwise_rho is not None:
        for a, b, rho in pairwise_rho:
            if (
                weight_of.get(a, 0.0) >= RULE_R2B_MIN_PAIR_WEIGHT_PCT
                and weight_of.get(b, 0.0) >= RULE_R2B_MIN_PAIR_WEIGHT_PCT
            ):
                qualifying.append((a, b, rho))

    if pairwise_rho is None or not qualifying:
        states["R2b"] = CLEARED
        results.append(_result("R2b", CLEARED, {}, ["correlation_pairs"]))
    else:
        a, b, rho = max(qualifying, key=lambda triple: triple[2])
        states["R2b"] = _step(
            _prior(rule_states, "R2b"), rho,
            RULE_R2B_FIRE_RHO, RULE_R2B_CLEAR_RHO,
        )
        results.append(_result(
            "R2b", states["R2b"],
            {"a": a, "b": b, "rho": round(rho, 2)},
            ["correlation_pairs"],
        ))

    # ── R3 — market sensitivity ─────────────────────────────────────────────
    r3_gate = (
        beta is not None and se_beta is not None and r2 is not None
        and beta_window_days is not None and r2 >= LOW_R2_THRESHOLD
    )
    if not r3_gate:
        states["R3"] = CLEARED
        results.append(_result("R3", CLEARED, {}, ["beta"]))
    else:
        band = RULE_R3_SE_BAND_MULT * se_beta
        states["R3"] = _step(
            _prior(rule_states, "R3"), beta,
            RULE_R3_BETA_BASE + band, RULE_R3_BETA_BASE - band,
        )
        results.append(_result(
            "R3", states["R3"],
            {
                "beta": round(beta, 2),
                "r2_pct": round(r2 * 100),
                "window": beta_window_days,
            },
            ["beta"],
        ))

    # ── R4 — cash drag ──────────────────────────────────────────────────────
    states["R4"] = _step(
        _prior(rule_states, "R4"), cash_pct_total,
        RULE_R4_FIRE_CASH_PCT, RULE_R4_CLEAR_CASH_PCT,
    )
    results.append(_result(
        "R4", states["R4"], {"cash": round(cash_pct_total, 1)}, ["cash_fraction"],
    ))

    # ── R5 — data limits. Accounting: mirrors the current condition. ────────
    if not dropped:
        states["R5"] = CLEARED
        results.append(_result("R5", CLEARED, {}, ["dropped_holdings"]))
    else:
        reasons: list[str] = []
        for holding in dropped:
            copy = _DROP_REASON_COPY.get(
                holding.drop_reason or "", holding.drop_reason or "unknown",
            )
            if copy not in reasons:
                reasons.append(copy)
        covered = sum(h.invested_weight_pct for h in included)
        states["R5"] = FIRED
        results.append(_result(
            "R5", FIRED,
            {
                "dropped": [h.ticker for h in dropped],
                "reasons": reasons,
                "covered": round(covered, 1),
            },
            ["dropped_holdings"],
        ))

    ordered = {rule_id: states[rule_id] for rule_id in RULE_IDS}
    return results, ordered


__all__ = [
    "ETF_OVERLAP_DISCLOSURE",
    "HoldingInput",
    "RULE_IDS",
    "RULE_TEMPLATES",
    "evaluate_rules",
]
