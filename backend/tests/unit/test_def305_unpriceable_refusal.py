"""DEF305 — a fabricated price must never move a real ledger.

On 2026-08-14 one `sweep_resting_orders` tick closed **8 bracketed positions
across 2 portfolios** at prices drawn from `market_data._walk_for`'s
`50 + rng.uniform(0, 400)` band, and credited the proceeds as real cash. The
eight closes, from the incident:

    HPQ    target  32.23  ->  334.96      (real HPQ that day: ~$30.11)
    BAC    target  68.77  ->  420.78      (real: ~$64.49)
    DIS    target 114.99  ->  335.89      (real: ~$106.85)
    GOOGL  stop   340.68  ->  222.46      (real: ~$345.90)
    NVDA   stop   206.07  ->  138.50      (real: ~$225.16)
    HSBC   target 117.66  ->  131.14
    ANET   stop   191.40  ->  147.79
    MCD    stop   259.81  ->  257.74      (real: ~$272.83)

One portfolio read $10,000 -> $12,390.29 (+23.9%) when its true marked value was
$9,432.24 (-5.7%). It reconciled internally to the cent, which is why nothing
else flagged it.

The guard existed the whole time — `_quote_is_fillable`, one file away, applied
to the ENTRY book. The exit book took a bare `float` and could not consult a
source it never received. DEF190's shape: the guard is real, it is just not on
the path that moves the money. So the tests below are aimed at the PATHS, not
only at the predicate — a predicate that is correct and uncalled is what this
defect already was.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from uuid import uuid4

from app.schemas.trade import OrderType, Side
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import Quote
from app.trading_math.quote_fillability import is_fillable, refusal_reason

_ENGINE = Path(__file__).resolve().parents[2] / "app" / "services" / "sim_engine.py"

#: Prices from the real incident. Every one sits inside the mock walk's
#: [50, 450] band, which is the signature that identified it.
INCIDENT_CLOSES = [
    ("HPQ", 334.96), ("BAC", 420.78), ("DIS", 335.89), ("GOOGL", 222.46),
    ("NVDA", 138.50), ("HSBC", 131.14), ("ANET", 147.79), ("MCD", 257.74),
]


# --------------------------------------------------------------------------
# The rule.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("ticker,price", INCIDENT_CLOSES)
def test_every_price_from_the_incident_is_refused(ticker, price, monkeypatch):
    """Not invented fixtures — the eight closes that actually happened."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    assert is_fillable(Quote(price=price, source="mock_walk")) is False
    assert "mock walk" in (refusal_reason(Quote(price=price, source="mock_walk")) or "")


def test_a_real_quote_is_still_fillable(monkeypatch):
    """The guard must not close the simulator. A fix that refuses everything
    passes every test above and ships a dead product."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", True)
    assert is_fillable(Quote(price=30.11, source="yfinance")) is True
    assert refusal_reason(Quote(price=30.11, source="yfinance")) is None


def test_mock_walk_is_fine_when_it_is_the_intended_provider(monkeypatch):
    """With real data off the walk IS the provider. Refusing it there would
    stop the simulator working at all, which is why the rule reads the setting
    rather than the source alone."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "use_real_market_data", False)
    assert is_fillable(Quote(price=334.96, source="mock_walk")) is True


def test_the_unavailable_sentinel_is_refused():
    """`current_quote`'s $0.01 sentinel would fire every sell stop in the book
    at once — the same all-positions-at-once shape as the incident."""
    assert is_fillable(Quote(price=0.01, source="unavailable")) is False
    assert is_fillable(None) is False
    assert is_fillable(Quote(price=0.0, source="yfinance")) is False


# --------------------------------------------------------------------------
# The paths. A correct predicate nobody calls is what DEF305 already was.
# --------------------------------------------------------------------------

def _functions() -> dict[str, ast.FunctionDef]:
    tree = ast.parse(_ENGINE.read_text(encoding="utf-8"))
    return {
        n.name: n for n in ast.walk(tree)
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


#: Every function in `sim_engine` that turns a quote into a ledger movement.
#: Named explicitly so adding a new one is a deliberate edit here, and so the
#: list can be read against the defect's own inventory.
MONEY_MOVING = [
    "evaluate_outcomes",            # the sweep that caused the incident
    "evaluate_short_brackets",      # the short book's version of it
    "force_close_breached_shorts",  # a margin call computed off a fiction
    "accrue_short_borrow",          # a real cash debit sized off a mark
    "submit",                       # books a fill
    "manual_close",                 # books a close
    "cover_short",                  # stamps realised P&L
    "run_option_lifecycle",         # already guarded before this defect
]


@pytest.mark.parametrize("name", MONEY_MOVING)
def test_every_money_moving_path_consults_fillability(name):
    fns = _functions()
    assert name in fns, f"{name} no longer exists in sim_engine — update this list"
    body = ast.unparse(fns[name])
    assert "is_fillable" in body, (
        f"{name} moves a user's ledger off a quote and never asks whether that "
        "quote may be booked. That is DEF305 exactly: the guard was real and "
        "simply not on the path that moved the money."
    )


def test_the_sweep_skips_rather_than_closing_when_it_cannot_price():
    """`continue`, not a close at a fallback price. A position left open is
    recoverable on the next tick; a position closed at a fabricated price is
    not — the shares are gone and `realised_pnl` has stamped the fiction."""
    src = ast.unparse(_functions()["evaluate_outcomes"])
    idx = src.index("is_fillable")
    assert "continue" in src[idx : idx + 200], (
        "the fillability check in evaluate_outcomes must skip the position"
    )


def _mandate():
    return hydrate_coach_mandate({
        "plan": "trader",
        "single_name_cap_pct": 100.0,
        "max_open_risk_pct": 100.0,
        "compliance": {"long_only": True},
    })


class _Pinned:
    """A provider that answers with a chosen price AND a chosen source."""

    def __init__(self, prices: dict[str, float], source: str = "yfinance"):
        self.prices = {k.upper(): v for k, v in prices.items()}
        self.source = source

    def quote(self, ticker: str):
        return Quote(price=self.prices.get(ticker.upper(), 100.0), source=self.source)

    def history(self, *a, **k):  # pragma: no cover
        return []

    def news(self, *a, **k):  # pragma: no cover
        return []

    def earnings(self, *a, **k):  # pragma: no cover
        return None


def test_an_unpriceable_fill_is_refused_loudly_not_silently(monkeypatch):
    """Behavioural, not a grep. CR040: doing nothing when a user taps a button
    is its own defect, so the refusal must reach them — and it must not blame
    their mandate, because nothing about their settings caused it."""
    from app.core.config import settings
    from app.services.sim_engine import SimEngine

    monkeypatch.setattr(settings, "use_real_market_data", True)
    sim = SimEngine(provider=_Pinned({"HPQ": 334.96}, source="mock_walk"))
    result = sim.submit(
        user_id=uuid4(), ticker="HPQ", side=Side.BUY, quantity=1,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert result.accepted is False
    assert result.trade is None
    assert result.compliance.blocked_by == "unpriceable", (
        "a feed outage must not be reported as a mandate rejection"
    )
    assert any("could not be priced" in v for v in result.compliance.violations)


def test_the_same_order_fills_on_a_real_quote(monkeypatch):
    """Non-vacuity: if submit refused everything this file would still be green
    and the product would be dead."""
    from app.core.config import settings
    from app.services.sim_engine import SimEngine

    monkeypatch.setattr(settings, "use_real_market_data", True)
    sim = SimEngine(provider=_Pinned({"HPQ": 30.11}, source="yfinance"))
    result = sim.submit(
        user_id=uuid4(), ticker="HPQ", side=Side.BUY, quantity=1,
        mandate=_mandate(), order_type=OrderType.MARKET,
    )
    assert result.accepted is True


def test_unpriceable_is_not_folded_into_a_compliance_reason():
    """Telling a user their own risk rules blocked a trade when the feed was
    down is a confident, wrong explanation of their own settings."""
    from app.schemas.trade import ComplianceResult
    allowed = ComplianceResult.model_fields["blocked_by"].annotation
    assert "unpriceable" in str(allowed)


def test_the_rule_has_exactly_one_implementation():
    """DEF098 — two derivations of one rule disagree the first time either
    moves, and this rule's two halves disagreeing IS DEF305. `sim_resting_orders`
    must delegate, not re-implement."""
    resting = (_ENGINE.parent / "sim_resting_orders.py").read_text(encoding="utf-8")
    assert "from app.trading_math.quote_fillability import is_fillable" in resting
    assert 'q.source == "mock_walk"' not in resting, (
        "sim_resting_orders re-implements the fillability rule instead of "
        "importing it"
    )
