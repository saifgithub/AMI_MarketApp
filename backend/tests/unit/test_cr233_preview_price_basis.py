"""GUARD (CR233 round-2 gap closure) — `POST /v1/sim/preview`'s price basis
for non-market orders, and the bracket-validity check `preview` never ran.

CR233 (mobile-only, `662c11aa`) widened `AlpacaClient.submitOrder()` to real
order types and had mobile forward `order_type`/`limit_price`/`trigger_price`
on `/v1/sim/preview`. Its own architect doc named the gap explicitly:
`preview_trade`'s handler (`backend/app/api/sim.py`) forwarded `limit_price`
to `SimEngine.preview()` but that method had **no `trigger_price` parameter
at all** — a STOP/STOP_LIMIT preview sized cash-sufficiency and
concentration at the live mark, not the order's own trigger price, and
`preview()` ran no bracket-validity check whatsoever (only `submit_trade`'s
path did, via `_execute_fill`'s DEF312/DEF377 refusal).

This file is the WIRE-LEVEL guard — `test_sim_engine.py`'s
`test_preview_stop_*`/`test_preview_*bracket*` tests already pin the
`SimEngine.preview()` arithmetic directly; this proves the route actually
forwards `trigger_price`/`target` from `SubmitTradeRequest` through to it,
end to end over `/v1/sim/preview`, on both the AMI path and the DEF419
account-snapshot path.

Covers:
  (a) a STOP preview sizes cash-sufficiency at `trigger_price`, not mark —
      on the AMI (no-account) path.
  (b) the same, on the Alpaca-snapshot path (proves `trigger_price` reaches
      `check_mandate_compliance`'s `unit_price` regardless of which
      denominator is being sized against).
  (c) a wrong-side bracket (`stop`/`target`) is refused at PREVIEW, not
      just at `/submit` — the ticket must not say "accepted" for an order
      `/submit` would then reject outright.
  (d) a MARKET order preview is unaffected — no `trigger_price` in the
      request, sizing still reads the live mark, byte-identical to
      pre-CR233 behaviour.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services.auth_service import AuthService
from app.services.sim_engine import get_sim_engine


@pytest.fixture
def sim_client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app)


def _new_user() -> tuple[UUID, str]:
    auth = AuthService()
    u, t, _ = auth.ensure_anonymous(device_user_id=None)
    return u.id, t


def _mock_price(ticker: str) -> float:
    return get_sim_engine().current_quote(ticker).price


def _permissive_mandate(**overrides) -> dict:
    body = {
        "compliance": {"long_only": True},
        "single_name_cap_pct": 150.0,
        "max_open_positions": 50,
        "max_trades_per_day": 50,
        "max_trades_per_week": 50,
        "post_loss_cooldown_hours": 0,
        "max_open_risk_pct": 100.0,
        "max_drawdown_pct": 100,
    }
    body.update(overrides)
    return body


def _preview(
    sim_client: TestClient,
    user_id: UUID,
    token: str,
    *,
    ticker: str = "AAPL",
    side: str = "buy",
    quantity: float = 1,
    order_type: str = "market",
    account: dict | None = None,
    mandate_override: dict | None = None,
    **extra,
):
    body = {
        "user_id": str(user_id),
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "order_type": order_type,
    }
    if account is not None:
        body["account"] = account
    if mandate_override is not None:
        body["mandate_override"] = mandate_override
    body.update(extra)
    return sim_client.post(
        "/v1/sim/preview",
        json=body,
        headers={"Authorization": f"Bearer {token}"},
    )


# ── (a) STOP preview sizes at trigger_price, AMI path ───────────────────────


def test_stop_preview_sizes_at_trigger_price_not_mark_ami_path(
    sim_client: TestClient,
):
    """A BUY STOP well above the mark must be sized (cash sufficiency) at
    its own trigger, not the (cheaper) live mark — pre-fix this would have
    wrongly accepted on the mark's cash math."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    # Priced so 100 shares at MARK fits comfortably in $10k, but 100 shares
    # at a trigger well above mark does not.
    qty = 1000.0 / mark
    trigger = (10_000.0 / qty) * 1.5  # notional at trigger = 1.5x the $10k cash

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        order_type="stop", trigger_price=trigger,
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is False, body
    assert any("insufficient cash" in v for v in body["compliance"]["violations"]), body
    assert body["fill_price"] == trigger


def test_stop_preview_accepted_when_trigger_affordable_even_if_mark_is_not(
    sim_client: TestClient,
):
    """Inverse: a trigger UNDER the mark that fits cash must be accepted,
    proving the basis is genuinely the trigger and not some max/min of the
    two."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 1000.0 / mark
    trigger = (5_000.0 / qty)  # well within $10k cash

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        order_type="stop", trigger_price=trigger,
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body
    assert body["fill_price"] == trigger


# ── (b) same, on the DEF419 account-snapshot path ───────────────────────────


def test_stop_limit_preview_sizes_at_trigger_on_alpaca_snapshot_path(
    sim_client: TestClient,
):
    """The snapshot path reads `check_mandate_compliance`'s `unit_price` off
    the same `proposed.limit_price` chokepoint the AMI path does — a
    STOP_LIMIT previewed against a small Alpaca account must be sized at
    the trigger there too."""
    user_id, token = _new_user()

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=100,
        order_type="stop_limit", trigger_price=100.0, limit_price=101.0,
        account={"kind": "alpaca_paper", "equity": 5_000.0, "cash": 5_000.0,
                 "positions": []},
        # single_name_cap_pct raised well past 200% so the concentration
        # cap (fed by the same `unit_price` chokepoint) doesn't fire first
        # and mask the cash-sufficiency check this test is about.
        mandate_override=_permissive_mandate(single_name_cap_pct=500.0),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # 100 shares @ $100 trigger = $10,000 > $5,000 Alpaca cash.
    assert body["accepted"] is False, body
    assert any("insufficient cash" in v for v in body["compliance"]["violations"]), body
    assert body["fill_price"] == 100.0


# ── (c) bracket wrong-side refused on preview ───────────────────────────────


def test_preview_refuses_wrong_side_bracket_ami_path(sim_client: TestClient):
    """A long's stop above entry must be refused at preview — the same
    DEF312 rule `/submit` already enforces via `_execute_fill`. Before this
    fix, `preview()` had no `stop`/`target` bracket check at all, so this
    would have wrongly come back `accepted: true`."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        order_type="market",
        stop=mark * 1.05,  # wrong side — above entry for a long
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is False, body
    assert any(
        "must be BELOW the entry price" in v for v in body["compliance"]["violations"]
    ), body


def test_preview_accepts_right_side_bracket_ami_path(sim_client: TestClient):
    user_id, token = _new_user()
    mark = _mock_price("AAPL")

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        order_type="market",
        stop=mark * 0.95, target=mark * 1.10,
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is True, r.text


# ── (d) MARKET order preview unaffected ─────────────────────────────────────


def test_market_preview_still_sizes_at_mark(sim_client: TestClient):
    user_id, token = _new_user()
    mark = _mock_price("AAPL")

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=2,
        order_type="market",
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body
    assert body["fill_price"] == mark
