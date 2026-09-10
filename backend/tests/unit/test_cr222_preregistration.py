"""CR222 §3 — pre-registration on the trade ticket.

WHAT: the deterministic block in `safety_floor.check_mandate_compliance` that
refuses a training trade opening or adding to a position without a thesis, an
invalidation and a horizon — plus the journal round-trip that makes the
registration readable beside the realised outcome after the position closes.

WHY these tests and not others: every one of the four conditions that has to
hold before the block fires is a case where firing would be WRONG rather than
merely strict, and three of them are silent — a wrongly-firing check on a close
traps a user in a position, a wrongly-firing check on a Day Trader preset user
contradicts Saiful's ruling of 2026-09-11, and a flag that fires while off is a
feature shipping without a decision. Each gets its own test. The refusal
strings are asserted on the FIELD NAME they carry (DEF197: a refusal that does
not say what is missing teaches nothing), not on their full wording, which is
M06/M09's to change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.agents.safety_floor import check_mandate_compliance
from app.core.config import settings
from app.db import get_session
from app.db.models import JournalEntryRow
from app.schemas import Mandate, Path
from app.schemas.journal import EntryType
from app.schemas.trade import ProposedTrade, Side
from app.services.auth_service import AuthService
from app.services.day_trader_preset import DAY_TRADER_PRESET_OVERRIDES
from app.services.journal_store import get_journal_store
from app.services.sim_engine import SimTrade
from app.services.sim_trade_effects import (
    PREREGISTRATION_PAYLOAD_KEY,
    apply_post_fill_effects,
    registered_preregistration,
)


# The five limits CR129 made always-active resolve from the risk tier, so a
# call site not testing one of them needs this harmless real context or it
# picks up an unrelated cooldown/over-trading/open-risk violation. Lifted
# verbatim from `test_safety_floor.py`, which states the reasoning in full.
_HARMLESS_RISK_CONTEXT = dict(
    holdings=[], last_loss_closed_at=None, trade_open_timestamps=[],
    existing_open_risk_pct=0.0,
)

_VALID_THESIS = (
    "Margins have expanded four quarters running and the guide implies a "
    "fifth; the market is still pricing the 2024 trough."
)
_VALID_INVALIDATION = "Gross margin falls below 41% in any quarter."


class _Holding:
    """Duck-typed the way the floor consumes `holdings` — `.ticker`/`.quantity`
    and nothing else, exactly as `_held_quantity` reads it."""

    def __init__(self, ticker: str, quantity: float):
        self.ticker = ticker
        self.quantity = quantity
        self.avg_cost = 100.0


@pytest.fixture
def active_mandate(base_mandate: Mandate) -> Mandate:
    """The path the requirement binds. `base_mandate` is `long_horizon`, which
    is the exempt one — so every test that expects a refusal must say so."""
    return base_mandate.model_copy(update={"path": Path.ACTIVE.value})


@pytest.fixture
def preset_mandate(active_mandate: Mandate) -> Mandate:
    """The Day Trader preset applied verbatim (Ruling 2 — exempt). The seven
    values come from the preset's own constant, so this fixture cannot drift
    from what `api/mandate.py` recognises as the preset."""
    return active_mandate.model_copy(update=dict(DAY_TRADER_PRESET_OVERRIDES))


@pytest.fixture
def prereg_on(monkeypatch):
    monkeypatch.setattr(settings, "training_preregistration_required", True)
    monkeypatch.setattr(settings, "prereg_applies_to_long_horizon", False)


def _buy(**fields) -> ProposedTrade:
    return ProposedTrade(
        ticker="AAPL", side=Side.BUY, quantity=10, limit_price=100.0, **fields,
    )


def _check(proposed: ProposedTrade, mandate: Mandate, **overrides):
    context = {**_HARMLESS_RISK_CONTEXT, **overrides}
    return check_mandate_compliance(
        proposed,
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        **context,
    )


def _violations_naming(result, field: str) -> list[str]:
    return [v for v in result.violations if field in v]


# ── (a) the block fires ──────────────────────────────────────────────────


def test_buy_without_thesis_on_an_active_mandate_is_refused(
    prereg_on, active_mandate: Mandate,
):
    result = _check(_buy(), active_mandate)

    assert result.passed is False
    assert result.blocked_by == "preregistration"
    assert _violations_naming(result, "thesis")
    assert _violations_naming(result, "invalidation")
    assert _violations_naming(result, "horizon_days")


def test_the_refusal_says_ami_and_never_the_ai(prereg_on, active_mandate: Mandate):
    """Every one of these strings reaches a user on the ticket."""
    result = _check(_buy(), active_mandate)

    assert result.violations
    for violation in result.violations:
        assert "AMI" in violation
        assert "the AI" not in violation


# ── (b) all three fields present ─────────────────────────────────────────


def test_a_fully_registered_buy_passes_this_block(prereg_on, active_mandate: Mandate):
    result = _check(
        _buy(
            thesis=_VALID_THESIS,
            invalidation=_VALID_INVALIDATION,
            horizon_days=90,
        ),
        active_mandate,
    )

    assert result.passed is True
    assert result.blocked_by is None


def test_the_both_path_is_bound_too(prereg_on, active_mandate: Mandate):
    """§3 names `active` AND `both`. `both` includes an active leg, so a user
    on it is exactly the population the requirement is for."""
    both = active_mandate.model_copy(update={"path": Path.BOTH.value})

    assert _check(_buy(), both).blocked_by == "preregistration"


# ── (c) long_horizon is exempt by default ────────────────────────────────


def test_long_horizon_passes_without_the_fields(prereg_on, base_mandate: Mandate):
    assert base_mandate.path == Path.LONG_HORIZON.value

    result = _check(_buy(), base_mandate)

    assert result.passed is True
    assert result.blocked_by is None


def test_long_horizon_is_bound_once_its_own_flag_is_on(
    prereg_on, base_mandate: Mandate, monkeypatch,
):
    """The exemption is a SETTING, not a hard-coded carve-out — pinned so a
    future edit cannot quietly make `long_horizon` unreachable."""
    monkeypatch.setattr(settings, "prereg_applies_to_long_horizon", True)

    assert _check(_buy(), base_mandate).blocked_by == "preregistration"


# ── (d) the Day Trader preset is exempt (Ruling 2) ───────────────────────


def test_day_trader_preset_passes_without_the_fields(
    prereg_on, preset_mandate: Mandate,
):
    result = _check(_buy(), preset_mandate)

    assert result.passed is True
    assert result.blocked_by is None


def test_one_preset_value_short_is_not_the_preset(prereg_on, preset_mandate: Mandate):
    """The exemption is "the preset is applied", not "this mandate is
    permissive". A user who set six of the seven by hand has not taken the
    preset and its disclosure, so they are not exempt — and this is the
    assertion that keeps the check reading `DAY_TRADER_PRESET_OVERRIDES`
    wholesale rather than sampling one field."""
    almost = preset_mandate.model_copy(update={"post_loss_cooldown_hours": 4.0})

    assert _check(_buy(), almost).blocked_by == "preregistration"


# ── (e) a close never requires the fields ────────────────────────────────


def test_selling_a_held_position_never_requires_the_fields(
    prereg_on, active_mandate: Mandate,
):
    """The guard the CR names by name: a check that ran on closes would trap
    users in positions."""
    sell = ProposedTrade(
        ticker="AAPL", side=Side.SELL, quantity=10, limit_price=100.0,
    )

    result = _check(sell, active_mandate, holdings=[_Holding("AAPL", 40)])

    assert result.passed is True
    assert result.blocked_by is None


def test_an_undecidable_sell_is_treated_as_a_close(prereg_on, active_mandate: Mandate):
    """With `holdings` absent the floor cannot tell a sell-to-close from a
    sell-to-open. DEF169's rule applies: a check that could not run must not
    block — and here the direction that cannot trap a user is "close"."""
    sell = ProposedTrade(
        ticker="AAPL", side=Side.SELL, quantity=10, limit_price=100.0,
    )

    result = _check(sell, active_mandate, holdings=None)

    assert result.blocked_by != "preregistration"
    assert not _violations_naming(result, "thesis")


def test_a_sell_that_opens_a_short_does_require_them(
    prereg_on, active_mandate: Mandate,
):
    """A sell against a flat position OPENS exposure, so it is registrable in
    exactly the way a buy is. `long_only` off, or the mandate refuses it for a
    different reason and this test would prove nothing."""
    shorting = active_mandate.model_copy(
        update={
            "compliance": active_mandate.compliance.model_copy(
                update={"long_only": False}
            )
        }
    )
    sell = ProposedTrade(
        ticker="AAPL", side=Side.SELL, quantity=10, limit_price=100.0,
    )

    result = _check(sell, shorting, holdings=[])

    assert result.blocked_by == "preregistration"


# ── (f) the flag ─────────────────────────────────────────────────────────


def test_flag_off_never_fires(active_mandate: Mandate, monkeypatch):
    monkeypatch.setattr(settings, "training_preregistration_required", False)

    result = _check(_buy(), active_mandate)

    assert result.passed is True
    assert result.blocked_by is None


def test_the_shipped_default_is_off():
    """CR040: a behaviour change goes live by a deliberate env flip, not by a
    deploy. Read off a FRESH Settings so a monkeypatch elsewhere cannot make
    this pass."""
    from app.core.config import Settings

    fresh = Settings()
    assert fresh.training_preregistration_required is False
    assert fresh.prereg_applies_to_long_horizon is False


# ── (h) too-short fields ─────────────────────────────────────────────────


def test_a_too_short_thesis_is_refused_naming_thesis(
    prereg_on, active_mandate: Mandate,
):
    result = _check(
        _buy(
            thesis="Going up.",
            invalidation=_VALID_INVALIDATION,
            horizon_days=30,
        ),
        active_mandate,
    )

    assert result.passed is False
    assert result.blocked_by == "preregistration"
    assert _violations_naming(result, "thesis")
    assert not _violations_naming(result, "invalidation")


def test_a_too_short_invalidation_is_refused_naming_invalidation(
    prereg_on, active_mandate: Mandate,
):
    result = _check(
        _buy(thesis=_VALID_THESIS, invalidation="Drops.", horizon_days=30),
        active_mandate,
    )

    assert result.blocked_by == "preregistration"
    assert _violations_naming(result, "invalidation")
    assert not _violations_naming(result, "thesis")


def test_whitespace_is_not_a_thesis(prereg_on, active_mandate: Mandate):
    """Trimmed before measuring — otherwise 40 spaces clears a 40-char floor,
    which is a control that reports itself as enforced and is not."""
    result = _check(
        _buy(
            thesis=" " * 80,
            invalidation=_VALID_INVALIDATION,
            horizon_days=30,
        ),
        active_mandate,
    )

    assert result.blocked_by == "preregistration"
    assert _violations_naming(result, "thesis")


def test_a_missing_horizon_alone_is_refused_naming_horizon_days(
    prereg_on, active_mandate: Mandate,
):
    result = _check(
        _buy(thesis=_VALID_THESIS, invalidation=_VALID_INVALIDATION),
        active_mandate,
    )

    assert result.blocked_by == "preregistration"
    assert _violations_naming(result, "horizon_days")


def test_horizon_days_must_be_at_least_one_day():
    """`ge=1` on the schema, so a zero-day horizon is a 422 rather than a
    silently-accepted registration that means nothing."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        _buy(thesis=_VALID_THESIS, invalidation=_VALID_INVALIDATION, horizon_days=0)


# ── (g) the journal round-trip ───────────────────────────────────────────


@pytest.fixture
def user_id():
    auth = AuthService()
    user, _, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id


def _trade(user_id, *, horizon_days: int | None = 90) -> SimTrade:
    return SimTrade(
        id=uuid4(),
        user_id=user_id,
        portfolio_id=uuid4(),
        ticker="AAPL",
        side=Side.BUY,
        quantity=10,
        entry_price=100.0,
        stop=95.0,
        target=120.0,
        horizon_days=horizon_days,
        opened_at=datetime.now(timezone.utc),
    )


def _sim_trade_entries(user_id):
    with get_session() as s:
        from sqlalchemy import select

        rows = s.execute(
            select(JournalEntryRow)
            .where(
                JournalEntryRow.user_id == user_id,
                JournalEntryRow.entry_type == EntryType.SIM_TRADE.value,
            )
            .order_by(JournalEntryRow.created_at.asc())
        ).scalars().all()
        return [
            {
                "payload": dict(r.payload or {}),
                "mandate_version": r.mandate_version,
                "reference_id": r.reference_id,
            }
            for r in rows
        ]


def test_journal_entry_round_trips_all_three_fields_and_the_mandate_version(
    user_id,
):
    trade = _trade(user_id)

    apply_post_fill_effects(
        user_id=user_id,
        trade=trade,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        mandate_version=7,
    )

    entries = _sim_trade_entries(user_id)
    assert len(entries) == 1
    assert entries[0]["mandate_version"] == 7
    assert entries[0]["payload"][PREREGISTRATION_PAYLOAD_KEY] == {
        "thesis": _VALID_THESIS,
        "invalidation": _VALID_INVALIDATION,
        "horizon_days": 90,
    }


def test_an_unregistered_fill_carries_no_registration_block(user_id):
    """None, not a dict of nulls: "nothing was registered" and "three empty
    fields were registered" are different facts (CR040)."""
    apply_post_fill_effects(user_id=user_id, trade=_trade(user_id, horizon_days=None))

    entries = _sim_trade_entries(user_id)
    assert PREREGISTRATION_PAYLOAD_KEY not in entries[0]["payload"]


def test_the_registration_reads_back_for_the_close_entry(user_id):
    """What `api/sim.py`'s two close paths call to put the outcome beside the
    thesis. Asserted on the reader rather than through the route so it pins the
    behaviour both paths share."""
    trade = _trade(user_id)
    apply_post_fill_effects(
        user_id=user_id,
        trade=trade,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        mandate_version=3,
    )

    assert registered_preregistration(user_id, trade.id) == {
        "thesis": _VALID_THESIS,
        "invalidation": _VALID_INVALIDATION,
        "horizon_days": 90,
    }


def test_the_readback_finds_the_opening_entry_not_a_later_one(user_id):
    """A close writes a SECOND entry against the same trade id. The registration
    lives on the first, so the readback must be oldest-first — reading newest
    would find the close, and on a replay would find itself."""
    from app.schemas.journal import JournalEntryCreate, Outcome

    trade = _trade(user_id)
    apply_post_fill_effects(
        user_id=user_id,
        trade=trade,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        mandate_version=3,
    )
    get_journal_store().append(JournalEntryCreate(
        user_id=user_id,
        entry_type=EntryType.SIM_TRADE,
        reference_id=trade.id,
        title="Closed AAPL (WON) — $+200.00",
        ticker="AAPL",
        tags=["sim_trade", "closed", "won"],
        outcome=Outcome.WIN,
        payload={"trade": trade.to_json()},
    ))

    assert registered_preregistration(user_id, trade.id) is not None


def test_the_close_payload_carries_the_outcome_beside_the_registration(user_id):
    """The end state §3 is for: one row a review can read as thesis →
    invalidation → what happened."""
    from app.api.sim import _closed_trade_payload

    trade = _trade(user_id)
    apply_post_fill_effects(
        user_id=user_id,
        trade=trade,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        mandate_version=3,
    )

    payload = _closed_trade_payload(
        user_id=user_id,
        trade=trade,
        closed_price=120.0,
        realised_pnl=200.0,
        status="won",
    )

    assert payload["outcome"] == {
        "status": "won", "closed_price": 120.0, "realised_pnl": 200.0,
    }
    assert payload[PREREGISTRATION_PAYLOAD_KEY]["thesis"] == _VALID_THESIS
    assert payload[PREREGISTRATION_PAYLOAD_KEY]["invalidation"] == _VALID_INVALIDATION
    assert payload[PREREGISTRATION_PAYLOAD_KEY]["horizon_days"] == 90


def test_a_close_of_an_unregistered_position_still_carries_its_outcome(user_id):
    """No registration is not an error — a position opened before the flag was
    on has none, and the close entry must still say how it ended."""
    from app.api.sim import _closed_trade_payload

    trade = _trade(user_id, horizon_days=None)
    apply_post_fill_effects(user_id=user_id, trade=trade)

    payload = _closed_trade_payload(
        user_id=user_id,
        trade=trade,
        closed_price=90.0,
        realised_pnl=-100.0,
        status="lost",
    )

    assert payload["outcome"]["realised_pnl"] == -100.0
    assert PREREGISTRATION_PAYLOAD_KEY not in payload


# ── through the routes ───────────────────────────────────────────────────
#
# The unit tests above pin the floor and the journal in isolation. These two
# pin the WIRING, which is the half that silently rots: two new request fields
# that never reach the floor would leave every test above green while the
# shipped ticket refused every registered trade.


@pytest.fixture
def client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.sim import router as sim_router

    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)


def _user_and_token():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, token


def _make_active_path_user():
    """A user on the `active` path with room to take a position — the mandate
    store's default single-name cap is a risk-tier preset a $10k portfolio
    cannot buy through, and this test is about pre-registration, not caps."""
    from app.services.mandate_store import get_mandate_store

    user_id, token = _user_and_token()
    get_mandate_store().patch(
        user_id, {"path": Path.ACTIVE.value, "single_name_cap_pct": 100.0},
    )
    return user_id, token


def _submit(client, user_id, token, **overrides):
    body = {
        "user_id": str(user_id),
        "ticker": "AAPL",
        "side": "buy",
        "quantity": 1,
        "order_type": "market",
    }
    body.update(overrides)
    return client.post(
        "/v1/sim/submit", json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


def test_the_ticket_refuses_an_unregistered_trade(client, prereg_on):
    user_id, token = _make_active_path_user()

    response = _submit(client, user_id, token)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["compliance"]["blocked_by"] == "preregistration"
    assert any("thesis" in v for v in body["compliance"]["violations"])


def test_the_ticket_accepts_and_journals_a_registered_trade(client, prereg_on):
    user_id, token = _make_active_path_user()

    response = _submit(
        client, user_id, token,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        horizon_days=45,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is True, body["compliance"]

    entries = _sim_trade_entries(user_id)
    assert len(entries) == 1
    assert entries[0]["payload"][PREREGISTRATION_PAYLOAD_KEY] == {
        "thesis": _VALID_THESIS,
        "invalidation": _VALID_INVALIDATION,
        "horizon_days": 45,
    }
    # The version the trade was actually judged under, not the schema default.
    from app.services.mandate_store import get_mandate_store

    assert entries[0]["mandate_version"] == get_mandate_store().get(user_id).version


def test_a_manual_close_writes_the_outcome_beside_the_registration(
    client, prereg_on,
):
    """The end-to-end shape §3 exists for, through the two shipped routes."""
    user_id, token = _make_active_path_user()
    opened = _submit(
        client, user_id, token,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        horizon_days=45,
    ).json()
    trade_id = opened["trade"]["id"]

    closed = client.post(
        f"/v1/sim/trades/{user_id}/close",
        json={"trade_id": trade_id},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert closed.status_code == 200, closed.text

    entries = _sim_trade_entries(user_id)
    assert len(entries) == 2
    close_entry = entries[-1]["payload"]
    assert close_entry["outcome"]["status"] == "manual"
    assert close_entry["outcome"]["realised_pnl"] is not None
    assert close_entry[PREREGISTRATION_PAYLOAD_KEY]["thesis"] == _VALID_THESIS
    assert close_entry[PREREGISTRATION_PAYLOAD_KEY]["horizon_days"] == 45


def test_a_resting_order_is_refused_at_fill_not_silently_filled(
    client, prereg_on,
):
    """The scope boundary, pinned rather than left to be discovered.

    `sim_resting_orders` carries no thesis column, so a resting BUY reaches
    `fill_resting_order` with nothing registered and the floor refuses it —
    loudly, on `blocked_by="preregistration"`, journaled like any other
    fill-time refusal. Refusing is the correct direction (a resting order must
    never become a time-delayed bypass of the requirement); carrying
    registration onto the book is the mobile follow-on slice. This test fails
    the day someone makes that path silently fill instead.
    """
    from app.agents.safety_floor import check_mandate_compliance as _check_fn

    user_id, _token = _make_active_path_user()
    from app.services.mandate_store import get_mandate_store

    mandate = get_mandate_store().get(user_id)
    # The shape `fill_resting_order` builds: the order row's five fields, no
    # registration, because the row has nowhere to keep one.
    from_the_book = ProposedTrade(
        ticker="AAPL", side=Side.BUY, quantity=1, limit_price=100.0,
    )

    result = _check_fn(
        from_the_book,
        portfolio_value=100_000.0,
        current_drawdown_pct=0.0,
        mandate=mandate,
        **_HARMLESS_RISK_CONTEXT,
    )

    assert result.passed is False
    assert result.blocked_by == "preregistration"


def test_no_llm_in_the_pre_registration_write_path(monkeypatch, user_id):
    """§3: "No LLM in the write path." Pinned at `LLMProvider.stream_chat` —
    the ONE method every provider (mock, Anthropic, vLLM) overrides, so a call
    through any of them lands here. Patching module-level names would have been
    vacuous: the gateway exposes none."""
    from app.services.llm_gateway import LLMProvider

    def _boom(*args, **kwargs):
        raise AssertionError("the pre-registration write path called an LLM")

    assert hasattr(LLMProvider, "stream_chat")
    monkeypatch.setattr(LLMProvider, "stream_chat", _boom)

    trade = _trade(user_id)
    apply_post_fill_effects(
        user_id=user_id,
        trade=trade,
        thesis=_VALID_THESIS,
        invalidation=_VALID_INVALIDATION,
        mandate_version=1,
    )

    assert registered_preregistration(user_id, trade.id) is not None
