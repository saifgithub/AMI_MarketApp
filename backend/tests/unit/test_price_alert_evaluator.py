"""price_alert_evaluator — CR027 §4."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db import get_session
from app.db.models import NotificationRow, PriceAlertRow
from app.schemas import Compliance
from app.schemas.price_alert import PriceAlertCreate
from app.services import market_data as _md
from app.services import price_alert_evaluator as pae
from app.services.mandate_store import get_mandate_store
from app.services.price_alert_store import get_price_alert_store


class _FixedPriceProvider:
    def __init__(self, prices: dict[str, float | None]):
        self.prices = prices
        self.calls: list[str] = []

    def quote(self, ticker):
        self.calls.append(ticker)
        price = self.prices.get(ticker)
        if price is None:
            return None
        return _md.Quote(price=price, source="test")


class _FakeLLMGateway:
    def __init__(self, text: str = "mock commentary"):
        self.text = text
        self.calls: list[dict] = []

    async def stream_chat(self, *, system_prompt, messages, model_tier, max_tokens, **kw):
        self.calls.append({"system_prompt": system_prompt, "messages": messages})
        yield self.text


class _BoomLLMGateway:
    async def stream_chat(self, **kwargs):
        raise RuntimeError("boom")
        yield  # pragma: no cover — unreachable, makes this an async generator


def _alert_row(alert_id):
    with get_session() as s:
        return s.get(PriceAlertRow, alert_id)


# ── threshold semantics ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "threshold_type,price,threshold,expected",
    [
        ("stop", 90.0, 100.0, True),      # falls below -> fires
        ("stop", 110.0, 100.0, False),     # still above -> no fire
        ("manual_below", 90.0, 100.0, True),
        ("manual_below", 100.0, 100.0, False),  # equal is not "below"
        ("target", 110.0, 100.0, True),    # rises above -> fires
        ("target", 90.0, 100.0, False),
        ("manual_above", 110.0, 100.0, True),
        ("manual_above", 100.0, 100.0, False),  # equal is not "above"
    ],
)
def test_threshold_semantics(threshold_type, price, threshold, expected):
    assert pae._threshold_breached(threshold_type, price, threshold) is expected


# ── implied-short heuristic ─────────────────────────────────────────────────


def test_manual_below_no_trade_ref_long_only_is_implied_short(base_mandate):
    alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="manual_below", threshold_price=100.0, trade_ref=None,
    )
    assert pae._implies_short_entry(alert, base_mandate) is True


def test_manual_below_with_trade_ref_is_not_implied_short(base_mandate):
    alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="manual_below", threshold_price=100.0, trade_ref=uuid4(),
    )
    assert pae._implies_short_entry(alert, base_mandate) is False


def test_stop_type_is_never_implied_short(base_mandate):
    alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="stop", threshold_price=100.0, trade_ref=None,
    )
    assert pae._implies_short_entry(alert, base_mandate) is False


# ── concurrent-fire guard ───────────────────────────────────────────────────


def test_fire_alert_is_atomic_second_call_returns_false():
    store = get_price_alert_store()
    user_id = uuid4()
    created = store.create(
        user_id, PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=150.0),
    )
    first = pae._fire_alert(created.id, "commentary")
    second = pae._fire_alert(created.id, "commentary")
    assert first is True
    assert second is False
    row = _alert_row(created.id)
    assert row.status == "fired"


# ── commentary ───────────────────────────────────────────────────────────


async def test_commentary_framing_differs_by_threshold_type(monkeypatch, base_mandate):
    gateway = _FakeLLMGateway()
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: gateway)
    stop_alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="stop", threshold_price=100.0, trade_ref=None,
    )
    target_alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="target", threshold_price=100.0, trade_ref=None,
    )
    await pae.generate_alert_commentary(stop_alert, 95.0, base_mandate)
    await pae.generate_alert_commentary(target_alert, 105.0, base_mandate)
    assert len(gateway.calls) == 2
    stop_msg = gateway.calls[0]["messages"][0].content
    target_msg = gateway.calls[1]["messages"][0].content
    assert "risk-management" in stop_msg
    assert "profit-taking" in target_msg


async def test_commentary_generation_failure_falls_back_to_template(monkeypatch, base_mandate):
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _BoomLLMGateway())
    alert = pae._AlertSnapshot(
        id=uuid4(), user_id=uuid4(), ticker="AAPL",
        threshold_type="stop", threshold_price=150.0, trade_ref=None,
    )
    text = await pae.generate_alert_commentary(alert, 140.0, base_mandate)
    assert "AAPL" in text
    assert "150.0" in text or "150" in text


# ── full evaluation loop ────────────────────────────────────────────────────


async def test_alert_fires_exactly_once_never_duplicate_on_second_cycle(monkeypatch):
    _md.set_market_data_provider(_FixedPriceProvider({"AAPL": 90.0}))
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _FakeLLMGateway())
    notify_calls: list[tuple] = []
    monkeypatch.setattr(pae, "notify", lambda *a, **k: notify_calls.append((a, k)))

    store = get_price_alert_store()
    user_id = uuid4()
    created = store.create(
        user_id, PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=100.0),
    )

    stats1 = await pae.evaluate_price_alerts()
    assert stats1["fired"] == 1
    assert len(notify_calls) == 1
    assert _alert_row(created.id).status == "fired"

    stats2 = await pae.evaluate_price_alerts()
    assert stats2["fired"] == 0
    assert stats2["tickers"] == 0  # no active alerts left to evaluate
    assert len(notify_calls) == 1  # never fires twice


async def test_missing_price_data_never_fires(monkeypatch):
    _md.set_market_data_provider(_FixedPriceProvider({"AAPL": None}))
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _FakeLLMGateway())
    notify_calls: list = []
    monkeypatch.setattr(pae, "notify", lambda *a, **k: notify_calls.append((a, k)))

    store = get_price_alert_store()
    created = store.create(
        uuid4(), PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=1_000_000.0),
    )
    stats = await pae.evaluate_price_alerts()
    assert stats["skipped_price_error"] == 1
    assert stats["fired"] == 0
    assert notify_calls == []
    assert _alert_row(created.id).status == "active"


async def test_mandate_blocked_ticker_leaves_alert_active(monkeypatch, base_mandate):
    _md.set_market_data_provider(_FixedPriceProvider({"AAPL": 90.0}))
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _FakeLLMGateway())
    notify_calls: list = []
    monkeypatch.setattr(pae, "notify", lambda *a, **k: notify_calls.append((a, k)))

    user_id = uuid4()
    blocked_mandate = base_mandate.model_copy(update={
        "user_id": user_id,
        "compliance": Compliance(ticker_blocklist=["AAPL"], long_only=True, liquid_only=True),
    })
    get_mandate_store().upsert(user_id, blocked_mandate)

    store = get_price_alert_store()
    created = store.create(
        user_id, PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=100.0),
    )
    stats = await pae.evaluate_price_alerts()
    assert stats["mandate_blocked"] == 1
    assert stats["fired"] == 0
    assert notify_calls == []
    assert _alert_row(created.id).status == "active"


async def test_one_price_fetch_per_ticker_not_per_alert(monkeypatch):
    provider = _FixedPriceProvider({"AAPL": 90.0})
    _md.set_market_data_provider(provider)
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _FakeLLMGateway())
    monkeypatch.setattr(pae, "notify", lambda *a, **k: None)

    store = get_price_alert_store()
    store.create(uuid4(), PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=100.0))
    store.create(uuid4(), PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=100.0))

    await pae.evaluate_price_alerts()
    assert provider.calls.count("AAPL") == 1


async def test_notification_row_written_on_fire(monkeypatch):
    """End-to-end through the real notify() (not mocked) -- confirms the
    evaluator's fire path actually reaches the durable notifications row."""
    _md.set_market_data_provider(_FixedPriceProvider({"AAPL": 90.0}))
    monkeypatch.setattr(pae, "get_llm_gateway", lambda: _FakeLLMGateway(text="AAPL dipped"))

    store = get_price_alert_store()
    user_id = uuid4()
    created = store.create(
        user_id, PriceAlertCreate(ticker="AAPL", threshold_type="stop", threshold_price=100.0),
    )
    await pae.evaluate_price_alerts()

    with get_session() as s:
        rows = s.execute(
            select(NotificationRow).where(NotificationRow.source_ref == str(created.id))
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].type == "price_alert"
    assert rows[0].deep_link == {"route": "open_holding_detail", "ticker": "AAPL"}
