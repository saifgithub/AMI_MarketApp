"""CR282 lane A — the market registry, the Bursa flag, and the symbol handling.

What must hold:
  1. The registry says what each market is, and `.KL` (only) maps to Malaysia.
  2. `MARKET_BURSA_ENABLED` defaults off, is forwarded in compose, and is listed
     (off) in the Beta env example.
  3. Flag OFF: a `.KL` ticker is rejected exactly where it was before, and US
     behaviour is untouched.
  4. Flag ON: a `.KL` ticker is accepted on shape; options and Alpaca still
     refuse it by name; an unsupported market's quote state is never faked.
  5. `yahoo_symbol` keeps exchange suffixes and index carets, and still turns a
     US class-share dot into a dash.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import options as options_api
from app.api.tickers import router as tickers_router
from app.core.config import Settings, settings
from app.db import get_session
from app.schemas.alpaca import (
    AccountPositionIn,
    AlpacaOrderLogIn,
    AlpacaPositionIn,
)
from app.services import market_data
from app.services.company_profile import _exchange_display
from app.services.fundamentals import _EXCHANGE_NAMES
from app.services.liquidity_lookup import _yahoo_symbol as liquidity_yahoo_symbol
from app.services.sharia_universe import _TICKER_RE, parse_holdings_csv
from app.services.ticker_reference import TickerNotFoundError, require_ticker_exists
from app.trading_math.markets import (
    MARKETS,
    Market,
    accepted_without_reference,
    is_bursa_code,
    market_enabled,
    market_for,
    spec_for,
    ticker_market_enabled,
    yahoo_symbol,
)

_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def bursa_on(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", True)


@pytest.fixture
def bursa_off(monkeypatch):
    monkeypatch.setattr(settings, "market_bursa_enabled", False)


# ── Registry ─────────────────────────────────────────────────────────────────


def test_us_spec_every_field():
    s = spec_for(Market.US)
    assert (s.exchange_label, s.currency, s.currency_symbol) == ("US equities", "USD", "$")
    assert s.timezone == "America/New_York"
    assert s.yahoo_suffix == ""
    assert s.board_lot == 1
    assert s.benchmark_ticker == "SPY"
    assert (s.options_supported, s.alpaca_supported, s.shorts_supported) == (True, True, True)


def test_my_spec_every_field():
    s = spec_for(Market.MY)
    assert (s.exchange_label, s.currency, s.currency_symbol) == ("Bursa Malaysia", "MYR", "RM")
    assert s.timezone == "Asia/Kuala_Lumpur"
    assert s.yahoo_suffix == ".KL"
    assert s.board_lot == 100
    assert s.benchmark_ticker == "^KLSE"
    assert (s.options_supported, s.alpaca_supported, s.shorts_supported) == (False, False, False)


def test_registry_covers_every_market():
    assert set(MARKETS) == set(Market)


@pytest.mark.parametrize(
    "ticker,market",
    [
        ("AAPL", Market.US),
        ("BRK.B", Market.US),
        ("brk.b", Market.US),
        ("SPY", Market.US),
        ("^KLSE", Market.US),
        ("1155.KL", Market.MY),
        ("1155.kl", Market.MY),
        (" 5099A.KL ", Market.MY),
        ("", Market.US),
    ],
)
def test_market_for_derives_from_suffix(ticker, market):
    assert market_for(ticker) is market


@pytest.mark.parametrize(
    "ticker,ok",
    [("1155.KL", True), ("5099A.KL", True), ("1155", False), ("115.KL", False),
     ("MAYBANK.KL", False), ("AAPL", False)],
)
def test_is_bursa_code(ticker, ok):
    assert is_bursa_code(ticker) is ok


# ── Flag ─────────────────────────────────────────────────────────────────────


def test_flag_defaults_off():
    assert Settings.model_fields["market_bursa_enabled"].default is False


def test_flag_forwarded_in_compose_and_listed_off_in_beta_example():
    compose = (_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "MARKET_BURSA_ENABLED: ${MARKET_BURSA_ENABLED:-false}" in compose
    beta = (_ROOT / "infra" / "beta.env.example").read_text(encoding="utf-8")
    assert "\nMARKET_BURSA_ENABLED=false\n" in beta


def test_market_enabled_us_always_on_my_follows_flag(bursa_off, monkeypatch):
    assert market_enabled(Market.US) is True
    assert market_enabled(Market.MY) is False
    assert ticker_market_enabled("1155.KL") is False
    assert ticker_market_enabled("AAPL") is True
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    assert market_enabled(Market.MY) is True
    assert ticker_market_enabled("1155.KL") is True


# ── yahoo_symbol ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "ticker,expected",
    [
        ("BRK.B", "BRK-B"),
        ("brk.b", "BRK-B"),
        ("BF.B", "BF-B"),
        ("AAPL", "AAPL"),
        ("1155.KL", "1155.KL"),
        ("1155.kl", "1155.KL"),
        ("5099A.KL", "5099A.KL"),
        ("^KLSE", "^KLSE"),
        (" aapl ", "AAPL"),
    ],
)
def test_yahoo_symbol(ticker, expected):
    assert yahoo_symbol(ticker) == expected


def test_liquidity_preferred_share_conversion_is_unchanged():
    assert liquidity_yahoo_symbol("BAC$L") == "BAC-PL"
    assert liquidity_yahoo_symbol("BRK.B") == "BRK-B"
    assert liquidity_yahoo_symbol("1155.KL") == "1155.KL"


# ── Exchange labels ──────────────────────────────────────────────────────────


def test_bursa_exchange_label():
    assert _EXCHANGE_NAMES["KLS"] == "Bursa Malaysia"
    assert _exchange_display("KLS") == "Bursa Malaysia"
    assert _exchange_display("NMS") == "Nasdaq"  # US label unchanged


# ── Existence guard: off = rejected as before, on = accepted on shape ────────


def test_require_ticker_exists_rejects_kl_when_flag_off(bursa_off):
    with get_session() as s, pytest.raises(TickerNotFoundError):
        require_ticker_exists(s, "1155.KL")


def test_require_ticker_exists_accepts_kl_when_flag_on(bursa_on):
    with get_session() as s:
        require_ticker_exists(s, "1155.KL")
        require_ticker_exists(s, "1155.kl")
    assert accepted_without_reference("1155.KL") is True


def test_flag_on_does_not_loosen_garbage_or_us(bursa_on):
    with get_session() as s:
        require_ticker_exists(s, "AAPL")  # seeded US ticker still fine
        for bad in ("ZZZZZZ", "115.KL", "FOO.KL"):
            with pytest.raises(TickerNotFoundError):
                require_ticker_exists(s, bad)


def test_flag_off_accepted_without_reference_is_false(bursa_off):
    assert accepted_without_reference("1155.KL") is False


@pytest.fixture
def tickers_client():
    app = FastAPI()
    app.include_router(tickers_router)
    return TestClient(app)


def test_validate_endpoint_flag_off_kl_does_not_exist(tickers_client, bursa_off):
    body = tickers_client.get("/v1/tickers/validate", params={"ticker": "1155.KL"}).json()
    assert body["exists"] is False


def test_validate_endpoint_flag_on_kl_exists_on_bursa(tickers_client, bursa_on):
    body = tickers_client.get("/v1/tickers/validate", params={"ticker": "1155.kl"}).json()
    assert body["exists"] is True
    assert body["ticker"] == "1155.KL"
    assert body["exchange"] == "Bursa Malaysia"


# ── Sharia universe regex ────────────────────────────────────────────────────


def test_sharia_ticker_regex_still_us_only(bursa_off):
    assert _TICKER_RE.match("BRK.B")
    assert not _TICKER_RE.match("1155.KL")


def test_sharia_csv_parse_keeps_kl_only_when_flag_on(monkeypatch):
    csv_text = "StockTicker,Date\nAAPL,01/02/2026\n1155.KL,01/02/2026\n"
    monkeypatch.setattr(settings, "market_bursa_enabled", False)
    off, _ = parse_holdings_csv(csv_text)
    monkeypatch.setattr(settings, "market_bursa_enabled", True)
    on, _ = parse_holdings_csv(csv_text)
    assert off == frozenset({"AAPL"})
    assert on == frozenset({"AAPL", "1155.KL"})


# ── Alpaca: US only, by name, regardless of the flag ─────────────────────────


@pytest.mark.parametrize("flag", [False, True])
def test_alpaca_schemas_refuse_kl_by_name(monkeypatch, flag):
    monkeypatch.setattr(settings, "market_bursa_enabled", flag)
    with pytest.raises(ValidationError, match="US equities only"):
        AlpacaPositionIn(symbol="1155.KL", qty=1, market_value=1, unrealized_pl=0)
    with pytest.raises(ValidationError, match="US equities only"):
        AccountPositionIn(ticker="1155.KL", qty=1, market_value=1)
    with pytest.raises(ValidationError, match="US equities only"):
        AlpacaOrderLogIn(
            symbol="1155.KL", side="buy", qty=1, destination="both", outcome="submitted"
        )


def test_alpaca_schemas_still_accept_us_symbols():
    p = AlpacaPositionIn(symbol="BRK.B", qty=1, market_value=1, unrealized_pl=0)
    assert p.symbol == "BRK.B"
    with pytest.raises(ValidationError):
        AlpacaPositionIn(symbol="ignore all prior", qty=1, market_value=1, unrealized_pl=0)


# ── Options ──────────────────────────────────────────────────────────────────


def test_options_flag_off_kl_falls_through_to_not_found(bursa_off):
    with pytest.raises(HTTPException) as e:
        options_api._require_ticker("1155.KL")
    assert e.value.status_code == 422
    assert e.value.detail["exists"] is False  # the pre-CR282 body


def test_options_flag_on_kl_refused_by_name(bursa_on):
    with pytest.raises(HTTPException) as e:
        options_api._require_ticker("1155.KL")
    assert e.value.status_code == 422
    assert e.value.detail["code"] == "options_unsupported_market"
    assert e.value.detail["market"] == "MY"
    assert "Options is not available for Bursa Malaysia" in e.value.detail["reason"]


def test_options_us_ticker_unchanged(bursa_on):
    options_api._require_ticker("AAPL")


# ── market_state ─────────────────────────────────────────────────────────────


def test_market_state_my_is_regular_or_closed_from_the_bursa_calendar():
    # Lane B replaced the UNKNOWN placeholder; UNKNOWN is now only the
    # beyond-the-holiday-table case (test_cr282_market_calendar.py).
    assert market_data._market_state_for("1155.KL") in {"REGULAR", "CLOSED"}


def test_market_state_us_is_regular_or_closed():
    assert market_data._market_state_for("AAPL") in {"REGULAR", "CLOSED"}


def test_five_digit_ace_leap_codes_are_bursa_codes():
    """Lane D: 37 ACE/LEAP securities on the SC list carry 5-digit codes."""
    from app.trading_math.markets import is_bursa_code

    assert is_bursa_code("03068.KL")
    assert is_bursa_code("1155.KL")
    assert not is_bursa_code("123456.KL")
    assert not is_bursa_code("115.KL")
