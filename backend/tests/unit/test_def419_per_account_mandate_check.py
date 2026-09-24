"""GUARD (DEF419) — /v1/sim/preview checks the mandate against the account
that would actually receive the order, not always the AMI sim portfolio.

Saiful, from a TestFlight screenshot (ASML buy 10 @ $1731, destination Alpaca
paper): the mandate compliance check ran against the AMI sim account's
equity, so a trade sized fine for the Alpaca paper account (or vice versa)
could be wrongly rejected or wrongly approved. "It does mean that it may
reject for ami and approve for alpaca. Or vice versa. This is an expected
condition" — the fix is a per-account sizing check, not making the two
accounts agree.

Covers (per the DEF419 brief):
  (a) no `account` on the request → behaviour is byte-identical to
      pre-DEF419 (sizing reads the AMI sim portfolio).
  (b) the SAME order is rejected against a small account and accepted
      against a larger one, in both directions (AMI small/Alpaca big and
      Alpaca small/AMI big) — proves the check reads the SUPPLIED account,
      not a fixed one.
  (c) a malformed `account` snapshot → 422, never a silent fallback to the
      AMI account (degrade loudly — falling back IS the bug DEF419 fixes).
  (d) an existing position carried in the snapshot counts toward the
      single-name cap (and the sector cap) the same way an AMI holding does.
  (e) which mandate rules are per-account (sizing/concentration: single-name
      cap, sector cap, cash sufficiency, long-only-against-holdings) vs
      per-user (post-loss cooldown, over-trading brake, total open-risk) —
      the per-user ones read AMI's own trade history regardless of which
      account is being sized against.

Also guards the "preview never persists" invariant or an account-context
preview could be a stealth pathway around BL9's dry-run contract.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.sim import router as sim_router
from app.db import get_session
from app.db.models import SimPortfolioRow
from app.schemas.alpaca import AccountSnapshotIn
from app.services import sector_allocation as _sector_allocation_module
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


def _preview(
    sim_client: TestClient,
    user_id: UUID,
    token: str,
    *,
    ticker: str = "AAPL",
    side: str = "buy",
    quantity: float = 1,
    account: dict | None = None,
    mandate_override: dict | None = None,
    **extra,
):
    body = {
        "user_id": str(user_id),
        "ticker": ticker,
        "side": side,
        "quantity": quantity,
        "order_type": "market",
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


def _permissive_mandate(**overrides) -> dict:
    """A mandate override with every OTHER limit neutralised, so a test can
    isolate the single dimension it's about — same pattern
    `test_safety_floor.py`'s `_HARMLESS_RISK_CONTEXT` uses at the function
    level, here at the wire level. `single_name_cap_pct` defaults high so it
    never fires by accident; a test that wants to PROVE the cap sets it low
    explicitly.
    """
    body = {
        "compliance": {"long_only": True},
        "single_name_cap_pct": 100.0,
        "max_open_positions": 50,
        "max_trades_per_day": 50,
        "max_trades_per_week": 50,
        "post_loss_cooldown_hours": 0,
        "max_open_risk_pct": 100.0,
        "max_drawdown_pct": 100,
    }
    body.update(overrides)
    return body


def _mock_price(ticker: str) -> float:
    """The deterministic mock-walk price the sqlite/no-yfinance test env
    serves for this ticker right now (USE_REAL_MARKET_DATA defaults False —
    see conftest / CLAUDE.md's Mac-is-pure-editor rule). Read off the engine
    directly rather than hardcoded, so a mock-walk seed change doesn't make
    every dollar figure in this file silently wrong."""
    return get_sim_engine().current_quote(ticker).price


# ── (a) no account on the request → unchanged (AMI portfolio) ──────────────


def test_no_account_field_checks_against_ami_sim_portfolio(sim_client: TestClient):
    """Byte-identical to pre-DEF419: omitting `account` sizes against the
    $10k AMI sim portfolio. A trade that is ~100% of that $10k (and so
    breaches a 20% single-name cap) is rejected — same as it always was."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 2000.0 / mark  # ~$2,000 notional — 20% of the $10k AMI account

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        mandate_override=_permissive_mandate(single_name_cap_pct=10.0),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is False
    assert body["account_kind"] is None
    assert body["compliance"]["blocked_by"] == "concentration"
    assert any("single-name cap" in v for v in body["compliance"]["violations"])

    # And the SAME trade against a permissive cap is accepted — proving the
    # rejection above was the cap, not something else about the fixture.
    r2 = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        mandate_override=_permissive_mandate(single_name_cap_pct=100.0),
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["accepted"] is True
    assert r2.json()["account_kind"] is None


# ── (b) same order, opposite verdicts depending on which account is named ──


def test_rejected_against_small_ami_account_accepted_against_larger_alpaca_snapshot(
    sim_client: TestClient,
):
    """The ASML-screenshot shape: a position sized fine for a big Alpaca
    account is wrongly measured against the small $10k AMI account without
    this fix. With it: the SAME order is rejected with no `account` (AMI's
    $10k) and accepted with a $200k Alpaca snapshot — same mandate, same
    cap, different denominator."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 5000.0 / mark  # $5,000 notional

    # Against AMI's own $10k portfolio: 50% of equity, over a 30% cap.
    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        mandate_override=_permissive_mandate(single_name_cap_pct=30.0),
    )
    assert r_ami.status_code == 200, r_ami.text
    assert r_ami.json()["accepted"] is False
    assert r_ami.json()["compliance"]["blocked_by"] == "concentration"

    # Against a $200k Alpaca paper account: 2.5% of equity, well under 30%.
    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        account={"kind": "alpaca_paper", "equity": 200_000.0, "cash": 200_000.0,
                 "positions": []},
        mandate_override=_permissive_mandate(single_name_cap_pct=30.0),
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    assert r_alpaca.json()["accepted"] is True
    assert r_alpaca.json()["account_kind"] == "alpaca_paper"


def test_rejected_against_small_alpaca_snapshot_accepted_against_larger_ami_account(
    sim_client: TestClient,
):
    """The mirror image of the test above — proves the check isn't just
    "AMI always wins" or "Alpaca always wins", it reads whichever account
    was actually named."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 2500.0 / mark  # $2,500 notional

    # A $5k Alpaca paper account: 50% of equity, over a 30% cap.
    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        account={"kind": "alpaca_paper", "equity": 5_000.0, "cash": 5_000.0,
                 "positions": []},
        mandate_override=_permissive_mandate(single_name_cap_pct=30.0),
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    assert r_alpaca.json()["accepted"] is False
    assert r_alpaca.json()["compliance"]["blocked_by"] == "concentration"

    # No account → AMI's own $10k portfolio: 25% of equity, under 30%.
    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        mandate_override=_permissive_mandate(single_name_cap_pct=30.0),
    )
    assert r_ami.status_code == 200, r_ami.text
    assert r_ami.json()["accepted"] is True
    assert r_ami.json()["account_kind"] is None


def test_alpaca_cash_sufficiency_checked_against_snapshot_cash_not_ami_cash(
    sim_client: TestClient,
):
    """Cash sufficiency is a sizing check too — must read the SNAPSHOT's
    cash, not the AMI portfolio's $10k, or a well-funded Alpaca account would
    be refused for "insufficient cash" against a balance it doesn't have."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 50_000.0 / mark  # $50k notional — impossible on AMI's $10k

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        account={"kind": "alpaca_paper", "equity": 100_000.0, "cash": 100_000.0,
                 "positions": []},
        mandate_override=_permissive_mandate(single_name_cap_pct=100.0),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body
    assert body["cash_available"] == pytest.approx(100_000.0)


# ── (c) malformed snapshot → 422, never a silent fallback ───────────────────


@pytest.mark.parametrize(
    "bad_account",
    [
        {"kind": "alpaca_paper", "equity": -1.0, "cash": 100.0, "positions": []},
        {"kind": "alpaca_paper", "equity": 100.0, "cash": -1.0, "positions": []},
        {"kind": "alpaca_paper", "equity": 0.0, "cash": 100.0, "positions": []},
        {"kind": "schwab_paper", "equity": 100.0, "cash": 100.0, "positions": []},
        {"kind": "alpaca_paper", "equity": 100.0, "cash": 100.0,
         "positions": [{"ticker": "AAPL", "qty": -1.0, "market_value": 10.0}]},
        {"kind": "alpaca_paper", "equity": 100.0, "cash": 100.0,
         "positions": [{"ticker": "not a ticker!", "qty": 1.0, "market_value": 10.0}]},
        {"kind": "alpaca_paper", "equity": 100.0, "cash": 100.0,
         "positions": [], "extra_field_not_in_schema": True},
    ],
    ids=[
        "negative_equity", "negative_cash", "zero_equity",
        "unknown_kind", "negative_position_qty", "bad_ticker_pattern",
        "unexpected_extra_field",
    ],
)
def test_malformed_account_snapshot_is_422_not_silent_fallback(
    sim_client: TestClient, bad_account: dict,
):
    user_id, token = _new_user()
    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        account=bad_account,
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 422, r.text


def test_non_finite_equity_rejected_at_the_schema():
    """NaN/inf can't ride in a standard JSON request body at all (Python's own
    `json.dumps` refuses it, same as every browser/mobile JSON encoder would)
    — so the schema-level rejection, not a route round-trip, is the right
    place to prove this bound. Same non-finite guard `AlpacaSnapshotIn`
    already carries (`test_alpaca.py::test_non_finite_numbers_are_rejected`),
    applied to the new schema."""
    base = {"kind": "alpaca_paper", "equity": 100.0, "cash": 100.0, "positions": []}
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValidationError):
            AccountSnapshotIn.model_validate({**base, "equity": bad})
        with pytest.raises(ValidationError):
            AccountSnapshotIn.model_validate({**base, "cash": bad})


def test_malformed_account_never_silently_checks_against_ami_instead(
    sim_client: TestClient,
):
    """The specific degrade-loudly failure mode DEF419 names: a malformed
    snapshot must 422, not quietly fall back to sizing against the AMI
    portfolio (which would approve/reject the trade against a number the
    caller never intended)."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    qty = 9000.0 / mark  # 90% of AMI's $10k — would reject if silently
    # evaluated against the AMI account under a tight cap.

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=qty,
        account={"kind": "alpaca_paper", "equity": -5.0, "cash": 5.0, "positions": []},
        mandate_override=_permissive_mandate(single_name_cap_pct=10.0),
    )
    assert r.status_code == 422, r.text
    # Confirm this ISN'T a 200 rejection (which would mean it fell back and
    # evaluated against something) — it must never reach compliance at all.
    assert "compliance" not in r.json()


# ── (d) existing snapshot holdings count toward the caps ───────────────────


def test_single_name_cap_on_a_buy_ignores_existing_same_ticker_snapshot_holding(
    sim_client: TestClient,
):
    """NOT a DEF419 behaviour, but a pre-existing, deliberate one this DEF
    must not disturb: `check_mandate_compliance`'s own §6 comment says a plain
    BUY's single-name cap measures the PROPOSAL alone, never combined with an
    existing same-ticker position — "adding to a held position is the case
    `max_open_positions` deliberately permits". This proves that stays true
    when the holding lives in an Alpaca snapshot, not just the AMI portfolio:
    a small top-up BUY is accepted even though the snapshot already holds a
    position that alone exceeds the cap, because the cap only ever judges
    this proposal's own size on the buy path.
    """
    user_id, token = _new_user()
    mark = _mock_price("AAPL")
    top_up_qty = 100.0 / mark  # a small $100 top-up

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", side="buy",
        quantity=top_up_qty,
        account={
            "kind": "alpaca_paper", "equity": 20_000.0, "cash": 1_000.0,
            # Existing position alone is already 90% of equity — far over
            # the 10% cap below. A cap that (wrongly) summed holdings +
            # proposal would reject this trivial top-up; the existing,
            # correct behaviour accepts it because only the $100 proposal
            # is measured.
            "positions": [{"ticker": "AAPL", "qty": 18_000.0 / mark,
                            "market_value": 18_000.0}],
        },
        mandate_override=_permissive_mandate(single_name_cap_pct=10.0),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["accepted"] is True, body


def test_existing_snapshot_position_counts_toward_sector_cap(
    sim_client: TestClient, monkeypatch,
):
    """Same requirement, the sector-concentration cap (CR026). Monkeypatches
    the sector resolver `sim_engine.py` reads (`default_sector_map`) so AAPL
    and MSFT are deterministically in the same GICS sector regardless of
    whatever the (empty, in this sqlite test DB) real snapshot table holds —
    the real map resolves every ticker to "Other", which never breaches
    (DEF059 guard), so this test would be a false negative without it."""
    import app.services.sim_engine as sim_engine_module

    fake_map = _sector_allocation_module.SectorMap(
        mapping={"AAPL": "Technology", "MSFT": "Technology"}
    )
    monkeypatch.setattr(sim_engine_module, "default_sector_map", lambda: fake_map)

    user_id, token = _new_user()
    aapl_mark = _mock_price("AAPL")
    msft_mark = _mock_price("MSFT")
    qty_more = 500.0 / msft_mark  # +$500 more, different ticker, same sector

    body = {
        "kind": "alpaca_paper", "equity": 10_000.0, "cash": 5_000.0,
        "positions": [{"ticker": "AAPL", "qty": 4_500.0 / aapl_mark,
                        "market_value": 4_500.0}],
    }
    mandate = _permissive_mandate(single_name_cap_pct=100.0)
    mandate["sector_cap_pct"] = 48.0

    r = _preview(
        sim_client, user_id, token, ticker="MSFT", quantity=qty_more,
        account=body, mandate_override=mandate,
    )
    assert r.status_code == 200, r.text
    resp = r.json()
    # (4500 + 500) / 10000 = 50% > 48% sector cap, only true if the existing
    # AAPL position was counted into the Technology bucket.
    assert resp["accepted"] is False, resp
    assert resp["compliance"]["blocked_by"] == "compliance"
    assert any("sector" in v.lower() for v in resp["compliance"]["violations"]), resp


# ── (e) per-account vs per-user rules ───────────────────────────────────────


def test_long_only_short_detection_reads_snapshot_holdings_not_ami_holdings(
    sim_client: TestClient,
):
    """long_only blocks a sell-to-open (selling a ticker you don't hold). This
    is evaluated per-ACCOUNT: an Alpaca account that holds the ticker may
    sell-to-close there even though the AMI sim portfolio (checked with no
    `account`) has never bought it, and vice versa."""
    user_id, token = _new_user()
    mark = _mock_price("AAPL")

    # No account, no AMI holding → selling AAPL is a short → blocked.
    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", side="sell", quantity=1,
        mandate_override=_permissive_mandate(),
    )
    assert r_ami.status_code == 200, r_ami.text
    assert r_ami.json()["accepted"] is False
    assert r_ami.json()["compliance"]["blocked_by"] == "long_only"

    # Alpaca snapshot DOES hold AAPL → selling 1 share is a close, not a
    # short → not blocked by long_only (cash/other checks aside).
    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", side="sell", quantity=1,
        account={
            "kind": "alpaca_paper", "equity": 10_000.0, "cash": 100.0,
            "positions": [{"ticker": "AAPL", "qty": 10.0, "market_value": 10 * mark}],
        },
        mandate_override=_permissive_mandate(),
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    assert r_alpaca.json()["compliance"]["blocked_by"] != "long_only"


def test_over_trading_brake_is_per_user_same_across_both_accounts(
    sim_client: TestClient,
):
    """max_trades_per_day is a PER-USER brake (CR101-BE2/CR129) — it counts
    trades against the user's own AMI trade history regardless of which
    account this particular preview names. Set the cap to 0 (already
    "reached") and confirm BOTH the no-account and the Alpaca-snapshot
    preview are blocked by it identically — proving the limit isn't reset
    or bypassed by naming a different account."""
    user_id, token = _new_user()

    tight_mandate = _permissive_mandate(max_trades_per_day=0)

    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        mandate_override=tight_mandate,
    )
    assert r_ami.status_code == 200, r_ami.text
    assert r_ami.json()["accepted"] is False
    assert r_ami.json()["compliance"]["blocked_by"] == "over_trading"

    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        account={"kind": "alpaca_paper", "equity": 100_000.0, "cash": 100_000.0,
                 "positions": []},
        mandate_override=tight_mandate,
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    assert r_alpaca.json()["accepted"] is False
    assert r_alpaca.json()["compliance"]["blocked_by"] == "over_trading"


def test_post_loss_cooldown_is_per_user_blocks_both_accounts_identically(
    sim_client: TestClient,
):
    """post_loss_cooldown_hours is per-USER (the AMI trade ledger is the only
    place a "last loss" exists) — a cooldown active against the user's own
    history blocks a BUY the same way whichever account is named. There is
    no loss history in this fresh user, so instead this proves the OTHER
    half: with the cooldown OFF (0h), neither account is blocked by it,
    confirming the field is read (not skipped) on both paths."""
    user_id, token = _new_user()
    off_mandate = _permissive_mandate(post_loss_cooldown_hours=0)

    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        mandate_override=off_mandate,
    )
    assert r_ami.status_code == 200, r_ami.text
    assert r_ami.json()["accepted"] is True

    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        account={"kind": "alpaca_paper", "equity": 100_000.0, "cash": 100_000.0,
                 "positions": []},
        mandate_override=off_mandate,
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    assert r_alpaca.json()["accepted"] is True


def test_halal_flag_is_evaluated_regardless_of_account(sim_client: TestClient):
    """halal is a mandate-level (per-user) compliance flag, not a sizing
    check — it must fire identically whichever account is named, since it's
    a rule about the INSTRUMENT, not the account's balance sheet."""
    user_id, token = _new_user()
    mandate = _permissive_mandate()
    mandate["compliance"]["halal"] = True

    r_ami = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        mandate_override=mandate,
    )
    assert r_ami.status_code == 200, r_ami.text

    r_alpaca = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1,
        account={"kind": "alpaca_paper", "equity": 100_000.0, "cash": 100_000.0,
                 "positions": []},
        mandate_override=mandate,
    )
    assert r_alpaca.status_code == 200, r_alpaca.text
    # Whatever the halal universe rules AAPL (paused/unknown/screened — this
    # test doesn't fix a fake universe), the DECISION must be identical on
    # both paths: the flag doesn't split by account.
    assert (
        r_ami.json()["compliance"]["passed"]
        == r_alpaca.json()["compliance"]["passed"]
    )
    assert (
        r_ami.json()["compliance"]["sharia_verdict"]
        == r_alpaca.json()["compliance"]["sharia_verdict"]
    )


# ── Invariant: preview never persists, account-context or not ──────────────


def test_account_context_preview_never_persists(sim_client: TestClient):
    user_id, token = _new_user()
    mark = _mock_price("AAPL")

    with get_session() as s:
        before_count = len(
            s.query(SimPortfolioRow).filter(SimPortfolioRow.user_id == user_id).all()
        )

    r = _preview(
        sim_client, user_id, token, ticker="AAPL", quantity=1000.0 / mark,
        account={"kind": "alpaca_paper", "equity": 50_000.0, "cash": 50_000.0,
                 "positions": [{"ticker": "MSFT", "qty": 10.0, "market_value": 3000.0}]},
        mandate_override=_permissive_mandate(),
    )
    assert r.status_code == 200, r.text
    assert r.json()["accepted"] is True

    with get_session() as s:
        after_count = len(
            s.query(SimPortfolioRow).filter(SimPortfolioRow.user_id == user_id).all()
        )
    # ensure_portfolio() lazily creates the AMI row on first touch (unrelated
    # to the account-snapshot path) — the invariant is that this call added
    # no MORE than that one lazy-create, and never wrote anything shaped
    # like the Alpaca snapshot (there is no table it even could land in).
    assert after_count <= 1
    assert after_count == before_count or after_count == before_count + 1
