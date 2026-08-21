"""CR172 §10 steps 2–3 — the Room proposes a structure, and only one it costed.

The whole point of the design is a single sentence: **AMI computes, the PM picks
an index, the user consents.** So the tests that matter here are not the happy
path — they are the four ways a model can get an index wrong, and the one way it
can try to state a figure instead of indexing one.

`test_the_reply_may_not_state_a_single_figure_of_its_own` is the control. A
Chief Investment Officer that writes its own strike and premium beside a valid
`structure_id` must have those numbers discarded entirely, because `net_cost` is
what `open_option_structure` charges the portfolio: a premium that arrives from
the model on a short leg mints money, which is DEF059's shape with a cash
consequence. The verdict's legs are read off the candidate or the verdict does
not exist.

The gate has its own test that asserts an *absence*: a mandate that does not
permit derivatives must not reach the option board at all. Gating only the
rendering would leave the parser willing to honour an index into a list the CIO
was never shown.
"""

from __future__ import annotations

import datetime
import json

import pytest

from app.schemas import AgentId, Mandate
from app.schemas.room import VerdictAction
from app.services.classification_universe import default_classification_universe
from app.services.coach_engine import hydrate_coach_mandate
from app.services.market_data import (
    OptionChain,
    OptionQuote,
    Quote,
    set_market_data_provider,
)
from app.services.room_prompts import build_room_messages
from app.services.room_runner import (
    _build_room_option_candidates,
    _parse_pm_verdict,
    _RoomContext,
)
from app.services.sharia_universe import default_halal_universe

EXPIRY = datetime.date.today() + datetime.timedelta(days=45)
SPOT = 100.0


def _quote(strike: float, bid: float, ask: float) -> OptionQuote:
    return OptionQuote(
        strike=strike, bid=bid, ask=ask, last=None, volume=50,
        open_interest=500, implied_vol=0.30,
    )


class _ChainProvider:
    """A liquid board around $100, plus the `^IRX` yield the enrichment reads."""

    source = "test_chain"

    def quote(self, ticker: str):
        if ticker.upper() == "^IRX":
            return Quote(price=4.2, source="yfinance", change_pct=0.0)
        return Quote(price=SPOT, source="yfinance", change_pct=0.0)

    def earnings(self, ticker: str):
        return None

    def expiries(self, underlying: str):
        return [EXPIRY]

    def option_chain(self, underlying: str, expiry: datetime.date):
        if expiry != EXPIRY:
            return None
        calls = tuple(
            _quote(k, round(max(0.5, 105 - k) + 4.0, 2), round(max(0.5, 105 - k) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0, 115.0)
        )
        puts = tuple(
            _quote(k, round(max(0.5, k - 95) + 4.0, 2), round(max(0.5, k - 95) + 4.4, 2))
            for k in (90.0, 95.0, 100.0, 105.0, 110.0, 115.0)
        )
        return OptionChain(
            underlying=underlying.upper(), expiry=expiry, calls=calls, puts=puts,
            source="yfinance",
        )


class _RecordingProvider:
    """Records every read and answers emptily.

    Deliberately NOT a provider that raises. `_build_room_option_candidates`
    catches everything — a dead Room is worse than a missing menu — so a raising
    provider would be swallowed and the test would pass whether the gate held or
    not. It did: this was the one mutation that survived the first pass, and the
    TEST was what needed strengthening. Counting reads is the assertion the gate
    actually makes.
    """

    source = "recording"

    def __init__(self) -> None:
        self.reads: list[str] = []

    def quote(self, ticker: str):
        self.reads.append(f"quote:{ticker}")
        return None

    def earnings(self, ticker: str):
        self.reads.append(f"earnings:{ticker}")
        return None

    def expiries(self, underlying: str):
        self.reads.append(f"expiries:{underlying}")
        return []

    def option_chain(self, underlying: str, expiry: datetime.date):
        self.reads.append(f"chain:{underlying}")
        return None


@pytest.fixture
def chain_provider():
    set_market_data_provider(_ChainProvider())
    yield
    set_market_data_provider(None)


def _mandate(*, derivatives: bool, long_only: bool = False) -> Mandate:
    return hydrate_coach_mandate({
        "plan": "trader",
        "risk_score": 3,
        "compliance": {
            "derivatives_allowed": derivatives,
            "long_only": long_only,
        },
    })


def _ctx(mandate: Mandate, candidates: tuple = ()) -> _RoomContext:
    ctx = _RoomContext(
        ticker="AAPL",
        mandate=mandate,
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        halal_universe=default_halal_universe(),
        classification_universe=default_classification_universe(),
        locale_allowed_universe=None,
    )
    ctx.trader_entry = 100.0
    ctx.trader_stop = 94.0
    ctx.trader_target = 113.0
    ctx.option_candidates = candidates
    return ctx


def _menu(mandate: Mandate, **over) -> tuple:
    kwargs = {
        "ticker": "AAPL", "mandate": mandate, "portfolio_value": 100_000.0,
        "size_pct": 3.0, "entry": 100.0, "stop": 94.0, "target": 113.0,
        "horizon_days": 42, "shares_held": 0.0,
    }
    kwargs.update(over)
    return _build_room_option_candidates(**kwargs)


def _verdict_json(**over) -> str:
    body = {
        "action": "APPROVE", "size_pct": 3.0, "entry": 100.0, "stop": 94.0,
        "target": 113.0, "horizon_days": 42,
        "narration": "CIO: APPROVE. The thesis holds.",
    }
    body.update(over)
    return json.dumps(body)


# ── the gate ────────────────────────────────────────────────────────────────

def test_a_mandate_without_derivatives_never_reads_the_option_board():
    """Not "renders no block" — reads nothing. The gate is before the provider.

    The stronger assertion is the point: a gate that only hid the rendered block
    would leave the parser willing to honour an index into a list the CIO never
    saw, and a gate placed after the fetch would still pay for a board it
    discards on every convene.
    """
    provider = _RecordingProvider()
    set_market_data_provider(provider)
    try:
        candidates, spot = _menu(_mandate(derivatives=False))
    finally:
        set_market_data_provider(None)
    assert candidates == ()
    assert spot is None
    assert provider.reads == [], (
        f"the option board was read on a mandate that forbids derivatives: "
        f"{provider.reads}"
    )


def test_the_same_provider_IS_read_once_the_gate_opens():
    """The companion assertion — otherwise the test above passes on a builder
    that reads nothing under any mandate."""
    provider = _RecordingProvider()
    set_market_data_provider(provider)
    try:
        _menu(_mandate(derivatives=True))
    finally:
        set_market_data_provider(None)
    assert provider.reads, "an enabled mandate must reach the option board"


def test_the_gate_open_produces_a_costed_menu(chain_provider):
    candidates, spot = _menu(_mandate(derivatives=True))
    assert candidates, "a liquid bullish board must yield structures"
    assert spot == SPOT
    assert {c.strategy_name for c in candidates} >= {"long_call"}
    for c in candidates:
        assert c.legs and all(leg.premium > 0 for leg in c.legs)
        assert c.metrics.net_cost is not None


def test_an_incoherent_level_triple_yields_no_menu(chain_provider):
    """The stop at or above entry carries no computable risk to size against —
    `build_option_ladder` refuses the same triple for the same reason."""
    candidates, _ = _menu(_mandate(derivatives=True), stop=105.0)
    assert candidates == ()


def test_a_target_at_the_entry_yields_no_menu(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True), target=100.0)
    assert candidates == ()


def test_the_budget_is_the_equity_trades_own_risk_not_its_size(chain_provider):
    """3% of $1m at a 6% stop risks $1,800 — the shares' own loss at the stop.

    Sized off the POSITION value instead it would be $30,000, and the at-the-
    money call costs ~$920 a contract, so the menu would offer 32 contracts of
    an option against a share trade that risked 1,800. One contract is the
    right answer; anything above two means the wrong number reached the
    strategist.
    """
    candidates, _ = _menu(_mandate(derivatives=True), portfolio_value=1_000_000.0)
    long_call = next(c for c in candidates if c.strategy_name == "long_call")
    assert long_call.contracts == 1


# ── the prompt ──────────────────────────────────────────────────────────────

def _pm_prompt(candidates: tuple) -> str:
    system, messages = build_room_messages(
        agent_id=AgentId.PORTFOLIO_MANAGER,
        mandate=_mandate(derivatives=bool(candidates)),
        ticker="AAPL",
        profile={"name": "Apple", "sector": "Technology"},
        transcript=[],
        option_candidates=candidates,
        option_spot=SPOT,
    )
    # The Room block lands on the SYSTEM prompt (`build_agent_prompt`'s
    # composition), the user message is the one-line convene instruction. Join
    # both so a block that moves between them still counts as present.
    return system + "\n" + messages[0].content


def test_no_menu_means_the_verdict_contract_is_unchanged():
    """A run that issues no structures must not mention one. This is what keeps
    every existing user's PM prompt byte-identical to pre-CR172."""
    prompt = _pm_prompt(())
    assert "structure_id" not in prompt
    assert "Option structures" not in prompt


def test_the_menu_is_numbered_and_the_contract_gains_exactly_one_key(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    prompt = _pm_prompt(candidates)
    assert "## Option structures" in prompt
    assert "**[0]" in prompt
    assert "structure_id" in prompt
    for c in candidates:
        assert c.strategy_name.replace("_", " ") in prompt


def test_a_forbidden_structure_is_listed_and_marked_not_hidden(chain_provider):
    """§10's teaching moment: the PM must be able to say why the natural
    structure here is the one the mandate forbids."""
    candidates, _ = _menu(_mandate(derivatives=True, long_only=True))
    forbidden = [c for c in candidates if c.mandate_violations]
    assert forbidden, "long_only must forbid the sell-to-open structures"
    prompt = _pm_prompt(candidates)
    assert "FORBIDDEN" in prompt
    for c in forbidden:
        assert c.strategy_name.replace("_", " ") in prompt


# ── the parser ──────────────────────────────────────────────────────────────

def test_an_equity_verdict_carries_no_structure(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(_verdict_json(), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.strategy is None
    assert verdict.legs is None


def test_a_valid_index_attaches_that_candidates_legs(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(_verdict_json(structure_id=0), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.strategy == candidates[0].strategy_name
    assert verdict.legs is not None
    assert len(verdict.legs) == len(candidates[0].legs)
    for got, want in zip(verdict.legs, candidates[0].legs):
        assert (got.right, got.strike, got.quantity, got.premium) == (
            want.right, want.strike, want.quantity, want.premium
        )
    assert candidates[0].strategy_name.replace("_", " ") in verdict.reason


def test_the_reply_may_not_state_a_single_figure_of_its_own(chain_provider):
    """THE control. A CIO that writes its own strike and premium beside a valid
    index gets them discarded — every figure comes off the candidate."""
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(
        _verdict_json(
            structure_id=0,
            strike=1.0, premium=0.01, legs=[{"right": "call", "strike": 1.0,
                                             "quantity": 99.0, "premium": 0.01}],
            strategy="naked_call",
        ),
        ctx,
    )
    assert verdict is not None
    assert verdict.strategy == candidates[0].strategy_name != "naked_call"
    assert verdict.legs is not None
    assert all(leg.premium > 0.01 for leg in verdict.legs)
    assert all(leg.strike > 1.0 for leg in verdict.legs)
    assert sum(abs(leg.quantity) for leg in verdict.legs) < 99.0


def test_an_index_outside_the_issued_set_fails_safe_to_pass(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(
        _verdict_json(structure_id=len(candidates) + 5), ctx
    )
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert verdict.overridden_from_llm is True
    assert "did not cost" in verdict.reason
    assert verdict.legs is None


def test_an_index_on_a_run_that_issued_no_menu_fails_safe_to_pass():
    """The gate's second half: with no menu there is nothing to index, so an
    index is by definition invented."""
    ctx = _ctx(_mandate(derivatives=False), ())
    _text, verdict = _parse_pm_verdict(_verdict_json(structure_id=0), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert "no option structures were offered" in verdict.reason


def test_a_forbidden_candidate_may_not_be_chosen(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True, long_only=True))
    index = next(i for i, c in enumerate(candidates) if c.mandate_violations)
    ctx = _ctx(_mandate(derivatives=True, long_only=True), candidates)
    _text, verdict = _parse_pm_verdict(_verdict_json(structure_id=index), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert "does not permit" in verdict.reason
    assert verdict.legs is None


def test_a_non_numeric_structure_id_fails_safe_to_pass(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(
        _verdict_json(structure_id="a bull call spread"), ctx
    )
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert "not one of the numbered structures" in verdict.reason


@pytest.mark.parametrize("value", [None, "", "none", "N/A", "null"])
def test_a_stated_absence_is_an_equity_verdict_not_a_refusal(value, chain_provider):
    """Omitting the key is the documented answer, but a model handed an optional
    field sometimes writes a word instead of leaving it out. None of these names
    a structure, so none of them may cost the user an approval."""
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(_verdict_json(structure_id=value), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.APPROVE
    assert verdict.strategy is None


def test_a_structure_on_a_pass_changes_nothing(chain_provider):
    candidates, _ = _menu(_mandate(derivatives=True))
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(
        json.dumps({
            "action": "PASS", "structure_id": 0,
            "narration": "CIO: PASS. The risk/reward does not clear the bar.",
        }),
        ctx,
    )
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert verdict.strategy is None
    assert verdict.legs is None


@pytest.mark.parametrize("value", [1.7, True, "1.7"])
def test_a_number_that_is_not_an_index_is_refused_not_truncated(value, chain_provider):
    """`int(1.7)` is 1, and 1 is a real structure — so a silent truncation opens
    a trade the CIO did not choose, which is worse than refusing one it chose
    badly. A bool is an int in Python and names nothing either."""
    candidates, _ = _menu(_mandate(derivatives=True))
    assert len(candidates) > 1, "the truncation has to have somewhere to land"
    ctx = _ctx(_mandate(derivatives=True), candidates)
    _text, verdict = _parse_pm_verdict(_verdict_json(structure_id=value), ctx)
    assert verdict is not None
    assert verdict.action == VerdictAction.PASS
    assert verdict.legs is None
