"""CR136 M05 — fire/no-fire boundaries at ±ε per Rev 4 acceptance, hysteresis round-trips, R0 agreement with the trade-time mandate gate, slot registration.

Every threshold in Rev 4's rule table was fixed by a measurement, so a rule that
fires one tenth of a point off is a different product from the one that was
justified. The boundary cases below are therefore the substance of this file,
not its edge cases.

The R0 agreement test is the one that matters most: R0 exists to remove a
contradiction between what the report SAYS the user's cap is and what the trade
ticket ENFORCES, so a test that merely checks R0's own arithmetic would miss the
entire point.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest

from app.agents.safety_floor import check_holdings_against_mandate, single_name_cap_pct
from app.schemas import Mandate
from app.services.portfolio_health_constants import (
    ETF_OVERLAP_DISCLOSURE,
    LOW_R2_THRESHOLD,
    RULE_R1_TEXTBOOK_THRESHOLD_PCT,
)
from app.services.portfolio_rules import (
    RULE_IDS,
    RULE_TEMPLATES,
    HoldingInput,
    evaluate_rules,
)
from app.services.sector_allocation import sector_concentration_cap


def _holding(
    ticker: str, weight: float, *, sector: str = "Tech", included: bool = True,
    risk_share: float | None = None, drop_reason: str | None = None,
) -> HoldingInput:
    return HoldingInput(
        ticker=ticker,
        invested_weight_pct=weight,
        sector=sector,
        included=included,
        drop_reason=drop_reason,
        risk_share_pct=risk_share,
    )


def _evaluate(mandate: Mandate, **overrides):
    kwargs = {
        "mandate": mandate,
        "holdings": [],
        "dr2": None,
        "beta": None,
        "se_beta": None,
        "r2": None,
        "beta_window_days": None,
        "cash_pct_total": 0.0,
        "pairwise_rho": None,
        "contains_etfs": False,
        "rule_states": None,
    }
    kwargs.update(overrides)
    return evaluate_rules(**kwargs)


def _by_id(results: list[dict]) -> dict[str, dict]:
    return {r["rule_id"]: r for r in results}


# ── R0 — the mandate mirror ─────────────────────────────────────────────────


def test_r0_single_name_cap_is_strict_and_from_the_gate(base_mandate: Mandate) -> None:
    """Strict `>`, mirroring the floor's own `position_pct > cap` — a holding
    exactly AT its cap is compliant at the trade ticket and must be compliant
    here too, or the two layers contradict each other at the boundary."""
    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 35.0})
    assert single_name_cap_pct(mandate) == 35.0

    for weight, should_fire in ((35.1, True), (35.0, False), (34.9, False)):
        results, _ = _evaluate(mandate, holdings=[_holding("AAA", weight)])
        assert _by_id(results)["R0"]["fired"] is should_fire, weight


def test_r0_uses_the_cr129_risk_tier_preset_not_the_fifty_percent_backstop(
    base_mandate: Mandate,
) -> None:
    """CR129 moved the unset-cap fallback from the flat 50% backstop to the
    risk-tier preset. Hard-coding 50 here would show every user a cap 11-16x
    looser than the one that actually blocks their trade."""
    mandate = base_mandate.model_copy(update={"single_name_cap_pct": None})
    assert mandate.risk_score == 3
    assert single_name_cap_pct(mandate) == 3.0

    results, _ = _evaluate(mandate, holdings=[_holding("AAA", 3.1)])
    r0 = _by_id(results)["R0"]
    assert r0["fired"] is True
    assert r0["slots"]["breaches"][0]["cap_pct"] == 3.0

    results, _ = _evaluate(mandate, holdings=[_holding("AAA", 2.9)])
    assert _by_id(results)["R0"]["fired"] is False


def test_r0_sector_cap_and_the_other_bucket(base_mandate: Mandate) -> None:
    mandate = base_mandate.model_copy(update={"sector_cap_pct": None})
    assert sector_concentration_cap(mandate) == pytest.approx(0.40)

    over = [_holding("AAA", 20.1, sector="Tech"), _holding("BBB", 20.0, sector="Tech")]
    results, _ = _evaluate(mandate, holdings=over)
    sectors = [
        b for b in _by_id(results)["R0"]["slots"]["breaches"] if b["scope"] == "sector"
    ]
    assert [b["name"] for b in sectors] == ["Tech"]
    assert sectors[0]["cap_pct"] == pytest.approx(40.0)

    under = [_holding("AAA", 19.9, sector="Tech"), _holding("BBB", 20.0, sector="Tech")]
    results, _ = _evaluate(mandate, holdings=under)
    assert not [
        b for b in _by_id(results)["R0"]["slots"].get("breaches", [])
        if b["scope"] == "sector"
    ]

    # The unclassified bucket is our ignorance about the book, not a fact about
    # it — it can never breach (the DEF059 inversion guard).
    unknown = [_holding("AAA", 60.0, sector="Other")]
    results, _ = _evaluate(mandate, holdings=unknown)
    assert not [
        b for b in _by_id(results)["R0"]["slots"].get("breaches", [])
        if b["scope"] == "sector"
    ]


def test_r0_agrees_with_the_trade_time_gate_on_the_same_book(
    base_mandate: Mandate,
) -> None:
    """The reason R0 exists. At cash=0 the invested-sleeve and total-value bases
    coincide exactly, so the two layers must flag the same holdings — and flip
    together at the cap boundary."""
    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 35.0})
    cap = single_name_cap_pct(mandate)

    from app.schemas.trade import Holding

    for weight, expected in ((35.1, True), (34.9, False)):
        # The SAME book, expressed the way each layer wants it. At cash = 0 the
        # invested-sleeve basis R0 uses and the total-value basis the gate uses
        # are the same denominator, which is what makes the comparison exact.
        portfolio_value = 10_000.0
        price = 100.0
        quantity = weight / 100.0 * portfolio_value / price
        holdings = [Holding(
            ticker="AAA", quantity=quantity, avg_cost=price,
            opened_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        )]
        report = check_holdings_against_mandate(
            holdings=holdings,
            marks={"AAA": price},
            portfolio_value=portfolio_value,
            current_drawdown_pct=0.0,
            mandate=mandate,
        )
        gate_flagged = any(
            v.ticker == "AAA" and any("cap" in issue.lower() for issue in v.issues)
            for v in report.violations
        )

        results, _ = _evaluate(mandate, holdings=[_holding("AAA", weight)])
        r0_flagged = any(
            b["scope"] == "name" and b["name"] == "AAA"
            for b in _by_id(results)["R0"]["slots"].get("breaches", [])
        )
        assert r0_flagged is expected, weight
        assert r0_flagged == gate_flagged, (
            f"R0 and the trade gate disagree at {weight}% against a {cap}% cap — "
            f"which is exactly the contradiction R0 was added to remove"
        )


def test_r0_carries_the_etf_disclosure_only_when_it_fires(
    base_mandate: Mandate,
) -> None:
    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 35.0})
    results, _ = _evaluate(
        mandate, holdings=[_holding("SPY", 40.0)], contains_etfs=True,
    )
    r0 = _by_id(results)["R0"]
    assert r0["fired"] is True
    assert r0["slots"]["etf_disclosure"] is True
    assert r0["slots"]["basis"] == "total_value"

    results, _ = _evaluate(
        mandate, holdings=[_holding("SPY", 10.0)], contains_etfs=True,
    )
    assert _by_id(results)["R0"]["slots"] == {}, "a cleared rule registers nothing"


# ── R1 — concentration ──────────────────────────────────────────────────────


def _r1_book(top_share: float, n: int = 4) -> list[HoldingInput]:
    rest = (100.0 - top_share) / (n - 1)
    return [_holding("TOP", 25.0, risk_share=top_share)] + [
        _holding(f"H{i}", 25.0, risk_share=rest) for i in range(1, n)
    ]


def test_r1_boundaries() -> None:
    for share, fires in ((41.6, True), (41.5, True), (41.4, False)):
        results, _ = _evaluate(_MANDATE, holdings=_r1_book(share))
        assert _by_id(results)["R1"]["fired"] is fires, share


def test_r1_n_gate_keeps_small_books_silent() -> None:
    """Measured: a correctly-diversified 60/40 SPY+AGG book reads 94.5% top
    risk share. The always-present contribution table carries that fact; the
    rule stays silent rather than calling it a problem."""
    results, _ = _evaluate(_MANDATE, holdings=_r1_book(45.0, n=3))
    assert _by_id(results)["R1"]["fired"] is False
    results, _ = _evaluate(_MANDATE, holdings=_r1_book(45.0, n=4))
    assert _by_id(results)["R1"]["fired"] is True


def test_r1_hysteresis_and_forced_clear() -> None:
    fired = {"R1": "fired"}
    for share, still_fired in ((38.6, True), (38.4, False)):
        results, states = _evaluate(
            _MANDATE, holdings=_r1_book(share), rule_states=fired,
        )
        assert _by_id(results)["R1"]["fired"] is still_fired, share
        assert states["R1"] == ("fired" if still_fired else "cleared")

    # The n-gate dropping below its floor forces a clear: a fired rule with no
    # current number to cite is an alarm with nothing behind it.
    results, states = _evaluate(
        _MANDATE, holdings=_r1_book(45.0, n=3), rule_states=fired,
    )
    assert _by_id(results)["R1"]["fired"] is False
    assert states["R1"] == "cleared"


def test_r1_registers_the_literal_forty_in_its_own_template() -> None:
    """F15 corollary. The template says "40%" in prose, not as a format slot —
    without registering it, M06's allow-list would reject the engine's own
    mandated sentence."""
    results, _ = _evaluate(_MANDATE, holdings=_r1_book(45.0))
    slots = _by_id(results)["R1"]["slots"]
    assert slots["threshold_mention"] == RULE_R1_TEXTBOOK_THRESHOLD_PCT == 40
    assert slots["risk_share"] == 45.0
    assert slots["ticker"] == "TOP"


# ── R2 / R2b ────────────────────────────────────────────────────────────────


def _n_holdings(n: int) -> list[HoldingInput]:
    return [_holding(f"H{i}", 100.0 / n, risk_share=100.0 / n) for i in range(n)]


def test_r2_boundaries_and_n_gate() -> None:
    for dr2, fires in ((1.84, True), (1.86, False)):
        results, _ = _evaluate(_MANDATE, holdings=_n_holdings(8), dr2=dr2)
        assert _by_id(results)["R2"]["fired"] is fires, dr2

    results, _ = _evaluate(_MANDATE, holdings=_n_holdings(7), dr2=1.5)
    assert _by_id(results)["R2"]["fired"] is False
    results, _ = _evaluate(_MANDATE, holdings=_n_holdings(8), dr2=1.5)
    assert _by_id(results)["R2"]["fired"] is True


def test_r2_hysteresis_and_none() -> None:
    fired = {"R2": "fired"}
    for dr2, still in ((2.14, True), (2.16, False)):
        results, _ = _evaluate(
            _MANDATE, holdings=_n_holdings(8), dr2=dr2, rule_states=fired,
        )
        assert _by_id(results)["R2"]["fired"] is still, dr2

    results, states = _evaluate(
        _MANDATE, holdings=_n_holdings(8), dr2=None, rule_states=fired,
    )
    assert _by_id(results)["R2"]["fired"] is False
    assert states["R2"] == "cleared"


def test_r2b_catches_what_r2_structurally_cannot() -> None:
    """Rev 4 F21: R2's n>=8 gate silences every small book — measured, DR² < 2.0
    on every overlap book tested at n=2-5 and R2 fired on none of them. R2b is
    the rule that actually catches SPY+QQQ (ρ = 0.952 measured)."""
    book = [_holding("SPY", 50.0, risk_share=50.0), _holding("QQQ", 50.0, risk_share=50.0)]
    results, _ = _evaluate(
        _MANDATE, holdings=book, dr2=1.02, pairwise_rho=[("SPY", "QQQ", 0.952)],
    )
    by = _by_id(results)
    assert by["R2"]["fired"] is False, "R2's n-gate silences a two-name book"
    assert by["R2b"]["fired"] is True
    assert by["R2b"]["slots"] == {"a": "SPY", "b": "QQQ", "rho": 0.95}


def test_r2b_boundaries_and_weight_floor() -> None:
    book = [_holding("A", 6.0, risk_share=50.0), _holding("B", 6.0, risk_share=50.0)]
    for rho, fires in ((0.901, True), (0.900, True), (0.899, False)):
        results, _ = _evaluate(
            _MANDATE, holdings=book, pairwise_rho=[("A", "B", rho)],
        )
        assert _by_id(results)["R2b"]["fired"] is fires, rho

    for weight, fires in ((5.1, True), (4.9, False)):
        thin = [
            _holding("A", weight, risk_share=50.0),
            _holding("B", weight, risk_share=50.0),
        ]
        results, _ = _evaluate(
            _MANDATE, holdings=thin, pairwise_rho=[("A", "B", 0.95)],
        )
        assert _by_id(results)["R2b"]["fired"] is fires, weight


def test_r2b_picks_the_highest_rho_qualifying_pair_and_clears_correctly() -> None:
    book = [_holding(t, 10.0, risk_share=25.0) for t in ("A", "B", "C", "D")]
    pairs = [("A", "B", 0.91), ("C", "D", 0.97), ("A", "C", 0.93)]
    results, _ = _evaluate(_MANDATE, holdings=book, pairwise_rho=pairs)
    assert _by_id(results)["R2b"]["slots"]["rho"] == 0.97

    fired = {"R2b": "fired"}
    for rho, still in ((0.86, True), (0.84, False)):
        results, _ = _evaluate(
            _MANDATE, holdings=book, pairwise_rho=[("A", "B", rho)],
            rule_states=fired,
        )
        assert _by_id(results)["R2b"]["fired"] is still, rho

    # A pair that drops below the weight floor stops qualifying, and with no
    # other qualifying pair the rule clears.
    thin = [_holding("A", 4.0, risk_share=50.0), _holding("B", 4.0, risk_share=50.0)]
    results, states = _evaluate(
        _MANDATE, holdings=thin, pairwise_rho=[("A", "B", 0.99)], rule_states=fired,
    )
    assert _by_id(results)["R2b"]["fired"] is False
    assert states["R2b"] == "cleared"


# ── R3 — market sensitivity ─────────────────────────────────────────────────


def test_r3_band_scales_with_the_standard_error() -> None:
    """Rev 4 R3's band is ±0.6·SE(β̂), not a fixed width — it self-scales with
    sample size, which is why CI-gating was rejected in favour of it."""
    common = {"se_beta": 0.05, "r2": 0.5, "beta_window_days": 126}
    for beta, fires in ((1.3301, True), (1.3299, False)):
        results, _ = _evaluate(_MANDATE, beta=beta, **common)
        assert _by_id(results)["R3"]["fired"] is fires, beta

    fired = {"R3": "fired"}
    for beta, still in ((1.271, True), (1.269, False)):
        results, _ = _evaluate(_MANDATE, beta=beta, rule_states=fired, **common)
        assert _by_id(results)["R3"]["fired"] is still, beta


def test_r3_r2_co_gate_is_the_low_explanatory_power_threshold() -> None:
    """The co-gate is deliberately the SAME constant that sets
    `low_explanatory_power`: a beta the engine has already flagged as barely
    explained by the market must not be the beta a rule fires on."""
    assert LOW_R2_THRESHOLD == 0.2
    common = {"beta": 1.35, "se_beta": 0.05, "beta_window_days": 126}
    for r2, fires in ((0.21, True), (0.19, False)):
        results, _ = _evaluate(_MANDATE, r2=r2, **common)
        assert _by_id(results)["R3"]["fired"] is fires, r2

    results, states = _evaluate(
        _MANDATE, r2=0.19, rule_states={"R3": "fired"}, **common,
    )
    assert _by_id(results)["R3"]["fired"] is False
    assert states["R3"] == "cleared"

    results, _ = _evaluate(
        _MANDATE, beta=None, se_beta=0.05, r2=0.5, beta_window_days=126,
        rule_states={"R3": "fired"},
    )
    assert _by_id(results)["R3"]["fired"] is False


def test_r3_slots_render_the_trigger_values() -> None:
    results, _ = _evaluate(
        _MANDATE, beta=1.4321, se_beta=0.05, r2=0.6249, beta_window_days=126,
    )
    slots = _by_id(results)["R3"]["slots"]
    assert slots == {"beta": 1.43, "r2_pct": 62, "window": 126}


# ── R4 / R5 ─────────────────────────────────────────────────────────────────


def test_r4_boundaries_and_hysteresis() -> None:
    for cash, fires in ((41.1, True), (41.0, True), (40.9, False)):
        results, _ = _evaluate(_MANDATE, cash_pct_total=cash)
        assert _by_id(results)["R4"]["fired"] is fires, cash

    fired = {"R4": "fired"}
    for cash, still in ((39.1, True), (38.9, False)):
        results, _ = _evaluate(_MANDATE, cash_pct_total=cash, rule_states=fired)
        assert _by_id(results)["R4"]["fired"] is still, cash


def test_r5_covers_the_invested_basis() -> None:
    book = [
        _holding("A", 40.0, risk_share=57.1),
        _holding("B", 30.0, risk_share=42.9),
        _holding("C", 30.0, included=False, drop_reason="short_history"),
    ]
    results, _ = _evaluate(_MANDATE, holdings=book)
    r5 = _by_id(results)["R5"]
    assert r5["fired"] is True
    assert r5["slots"]["dropped"] == ["C"]
    assert r5["slots"]["reasons"] == ["short history"]
    assert r5["slots"]["covered"] == 70.0, (
        "covered is the invested-value basis the template's own words claim"
    )

    clean = [h for h in book if h.included]
    results, _ = _evaluate(_MANDATE, holdings=clean)
    assert _by_id(results)["R5"]["fired"] is False


def test_r5_deduplicates_reasons() -> None:
    book = [
        _holding("A", 90.0, risk_share=100.0),
        _holding("B", 5.0, included=False, drop_reason="data_quality"),
        _holding("C", 5.0, included=False, drop_reason="data_quality"),
    ]
    results, _ = _evaluate(_MANDATE, holdings=book)
    assert _by_id(results)["R5"]["slots"]["reasons"] == ["data quality"]


# ── Shape, hysteresis round-trip, template audit ────────────────────────────


def test_the_result_shape_is_fixed() -> None:
    results, states = _evaluate(_MANDATE)
    assert [r["rule_id"] for r in results] == list(RULE_IDS)
    assert set(states) == set(RULE_IDS)
    for result in results:
        assert set(result) == {"rule_id", "fired", "state", "slots", "based_on"}
        assert result["state"] in {"fired", "cleared"}
        assert result["fired"] == (result["state"] == "fired")
        assert states[result["rule_id"]] == result["state"]


def test_a_first_finding_starts_every_rule_cleared() -> None:
    _results, states = _evaluate(_MANDATE)
    assert set(states.values()) == {"cleared"}

    # An unrecognised stored value must not be able to start a rule fired.
    _results, states = _evaluate(_MANDATE, rule_states={"R1": "banana", "R9": "fired"})
    assert set(states.values()) == {"cleared"}


def test_between_the_lines_preserves_whatever_state_it_was_in() -> None:
    """The whole mechanism: values inside the band leave the state untouched, so
    a metric sitting near its threshold does not make the report contradict
    itself week to week."""
    mid = {
        "holdings": _r1_book(40.0, n=8) if False else [
            _holding("TOP", 12.5, risk_share=40.0),
            *[_holding(f"H{i}", 12.5, risk_share=60.0 / 7) for i in range(1, 8)],
        ],
        "dr2": 2.00,
        "beta": 1.30,
        "se_beta": 0.05,
        "r2": 0.5,
        "beta_window_days": 126,
        "cash_pct_total": 40.0,
        "pairwise_rho": [("TOP", "H1", 0.87)],
    }
    banded = ("R1", "R2", "R2b", "R3", "R4")

    _results, from_cleared = _evaluate(_MANDATE, **mid)
    for rule_id in banded:
        assert from_cleared[rule_id] == "cleared", rule_id

    all_fired = {rule_id: "fired" for rule_id in RULE_IDS}
    _results, from_fired = _evaluate(_MANDATE, rule_states=all_fired, **mid)
    for rule_id in banded:
        assert from_fired[rule_id] == "fired", rule_id


def test_feeding_the_states_back_unchanged_is_idempotent() -> None:
    book = _r1_book(45.0)
    results_a, states_a = _evaluate(_MANDATE, holdings=book)
    results_b, states_b = _evaluate(_MANDATE, holdings=book, rule_states=states_a)
    assert states_a == states_b
    assert results_a == results_b


def test_template_literals_are_closed() -> None:
    """F15's closure. Every digit-run in every template is either registered as
    a slot (R1's "40") or on M06's fixed-constants list (R3's "500"). A new
    literal added to a template without registering it fails here rather than
    at the validator, months later, as a discarded model output."""
    literals: set[str] = set()
    for template in RULE_TEMPLATES.values():
        without_slots = re.sub(r"\{[^}]*\}", " ", template)
        literals.update(re.findall(r"\d+(?:\.\d+)?", without_slots))
    assert literals == {"40", "500"}, literals


def test_templates_carry_no_deleted_clause() -> None:
    """Two sentences Rev 4 removed on measurement, pinned so they cannot come
    back: R1's per-dollar claim (F3 — it named the holding whose trim was 2.23x
    LESS effective) and R3's projection clause (F5 — a forecast in the grammar
    of a fact)."""
    r1, r3, r4 = RULE_TEMPLATES["R1"], RULE_TEMPLATES["R3"], RULE_TEMPLATES["R4"]
    for banned in ("per dollar", "for every dollar", "trimming"):
        assert banned not in r1.lower(), banned
    for banned in ("would fall", "would drop", "if the market", "10%"):
        assert banned not in r3.lower(), banned
    assert "dilut" not in r4.lower(), "F9: cash does not dilute every risk number"
    assert "scales" in r4


def test_templates_are_conditional_educational_not_imperative() -> None:
    """Rev 4's §F5 speech-act pin: general textbook practice with the user's own
    number as the trigger, never an instruction. The publisher's exclusion is
    unavailable to us and the live site states the product does not give
    investment advice — on every path, including this deterministic one."""
    for rule_id, template in RULE_TEMPLATES.items():
        lowered = template.lower()
        for imperative in ("you should", "we recommend", "you must", "sell ", "buy "):
            assert imperative not in lowered, (rule_id, imperative)


def test_no_threshold_literal_lives_in_the_engine() -> None:
    """Rev 4's "never scattered literals": every number a rule decides on
    arrives by name from the constants module, where it carries the measurement
    that justified it."""
    from pathlib import Path

    from app.services import portfolio_rules

    source = Path(portfolio_rules.__file__).read_text()
    code = "\n".join(
        line for line in source.splitlines()
        if not line.strip().startswith("#")
    )
    # Strip the template block — its "40" and "500" are prose, audited above.
    code = re.sub(r'RULE_TEMPLATES.*?^\}', "", code, flags=re.S | re.M)
    for literal in ("41.5", "38.5", "1.85", "2.15", "0.90", "0.85", "1.3", "0.6", "41.0", "39.0", "50"):
        assert not re.search(rf"(?<![\w.]){re.escape(literal)}(?![\w.])", code), literal


def test_the_etf_disclosure_is_the_shared_constant() -> None:
    assert "looked through" in ETF_OVERLAP_DISCLOSURE
    assert ETF_OVERLAP_DISCLOSURE.endswith("can be higher.")


# Module-level mandate for the rules that do not exercise R0.
_MANDATE: Mandate = None  # type: ignore[assignment]


@pytest.fixture(autouse=True)
def _bind_mandate(base_mandate: Mandate) -> None:
    global _MANDATE
    _MANDATE = base_mandate.model_copy(update={"single_name_cap_pct": 100.0})


def test_r0_agrees_with_the_gate_on_a_book_holding_CASH(
    base_mandate: Mandate,
) -> None:
    """The case the cash=0 agreement test structurally cannot catch, and the one
    that matters: R0 is the ONE deliberate exception to the SHARE/LEVEL rule —
    total-value weights, not invested-sleeve, because the gate's own denominator
    is the whole portfolio.

    Measured before this was fixed: a $10k book with 50% cash had the trade gate
    reporting ZERO violations while an invested-sleeve R0 reported three. That is
    the shown-vs-enforced split CR046 closed, inverted — the report accusing the
    user of a breach their own trade ticket denies."""
    from datetime import datetime, timezone

    from app.schemas.trade import Holding

    mandate = base_mandate.model_copy(update={"single_name_cap_pct": 35.0})
    # $10,000 total: $5,000 cash, AAA $2,000, BBB $3,000.
    # Total-value weights 20% / 30% — both compliant.
    # Invested-sleeve weights 40% / 60% — both would falsely breach.
    holdings = [
        _holding("AAA", 40.0, sector="Tech"),
        _holding("BBB", 60.0, sector="Health"),
    ]
    results, _ = _evaluate(mandate, holdings=holdings, cash_pct_total=50.0)
    r0 = _by_id(results)["R0"]

    gate = check_holdings_against_mandate(
        holdings=[
            Holding(ticker="AAA", quantity=20.0, avg_cost=100.0,
                    opened_at=datetime(2026, 1, 5, tzinfo=timezone.utc)),
            Holding(ticker="BBB", quantity=30.0, avg_cost=100.0,
                    opened_at=datetime(2026, 1, 5, tzinfo=timezone.utc)),
        ],
        marks={"AAA": 100.0, "BBB": 100.0},
        portfolio_value=10_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
    )
    gate_flagged = {
        v.ticker for v in gate.violations
        if any("cap" in issue.lower() for issue in v.issues)
    }
    assert gate_flagged == set(), "vacuity guard — the gate must be silent here"
    assert r0["fired"] is False, (
        "R0 fired on a book the trade ticket finds fully compliant — the "
        "contradiction R0 exists to remove, inverted"
    )

    # ...and it still fires where the gate DOES, on the same book.
    over = [_holding("AAA", 80.0, sector="Tech"), _holding("BBB", 20.0, sector="Health")]
    results, _ = _evaluate(mandate, holdings=over, cash_pct_total=50.0)
    r0 = _by_id(results)["R0"]
    assert r0["fired"] is True
    breach = next(b for b in r0["slots"]["breaches"] if b["scope"] == "name")
    assert breach["name"] == "AAA"
    assert breach["weight_pct"] == 40.0, "quoted on the total-value basis"


def test_r0_declares_its_basis_and_says_so_in_words() -> None:
    """Rev 4: R0's `basis` field reads total_value and its copy says "of your
    total portfolio value", so no sentence silently mixes bases."""
    assert "of your total portfolio value today" in RULE_TEMPLATES["R0"]
    assert "of invested value" not in RULE_TEMPLATES["R0"]
