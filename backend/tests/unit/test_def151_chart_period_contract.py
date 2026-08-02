"""DEF151 — the chart period token is a contract between two files in two
languages with nothing tying them together, and it drifted.

`ticker_chart.dart:29` declares the chips as `['1D','1W','1M','3M','1Y','5Y']`
and passed the label straight onto the wire. `market_data._PERIOD_MAP` is keyed
lowercase. Measured against live Alpha before the fix: **18/18 HTTP 422** across
6 periods x 3 tickers, while omitting the parameter entirely returned a full
candle series — so market data, yfinance, the cache and the serialiser were all
healthy and the entire feature was dark on letter case alone.

It went unreported because it degraded into `Chart unavailable. Tap to retry.`
— copy describing a *transient* fault. There is no state in which that button
can succeed, so every user read a permanent server rejection as their own bad
connection and retried forever. That is the CR040 question answered the wrong
way: if this fires constantly and silently, what does the user end up believing?

Two guards, because the two halves fail differently:

1. **The allow-list is pinned.** A server-side rename or removal is caught here
   even in a checkout with no `mobile/` directory.
2. **The two languages are tied together.** Every chip label the Dart file
   declares must normalise into that allow-list. This is the guard the defect
   asks for: the lists cannot drift again without a red test.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sim import router as sim_router
from app.services.market_data import VALID_PERIODS


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(sim_router)
    return TestClient(app, raise_server_exceptions=False)

_TICKER_CHART = (
    Path(__file__).resolve().parents[3] / "mobile/lib/widgets/ticker_chart.dart"
)
_PERIODS_DECL = re.compile(
    r"_kPeriods\s*=\s*\[(?P<body>[^\]]*)\]", re.MULTILINE
)


def test_the_allow_list_is_exactly_the_seven_canonical_lowercase_tokens():
    """Pinned so the server half cannot drift on its own — this runs even where
    the Flutter source is not checked out (the container image ships only
    `app/`, `tests/` and `alembic/`).

    `"2y"` joined the map in CR136 M01 (the Portfolio Health engine needs ≥126
    daily returns; `"3m"` tops out at 65 bars). It is deliberately server-only —
    no seventh chip ships, so the Dart vacuity guard below still reads 6."""
    assert VALID_PERIODS == ("1d", "1w", "1m", "3m", "1y", "2y", "5y")


@pytest.mark.skipif(
    not _TICKER_CHART.exists(),
    reason=f"Flutter source not in this checkout ({_TICKER_CHART})",
)
def test_every_chip_the_client_offers_is_accepted_by_the_server():
    """The cross-language contract, asserted rather than assumed.

    Reads the Dart declaration itself, so adding a seventh chip without a
    matching `_PERIOD_MAP` entry turns this red — which is the failure DEF151
    was, one release earlier.
    """
    match = _PERIODS_DECL.search(_TICKER_CHART.read_text())
    assert match, (
        "could not find `_kPeriods = [...]` in ticker_chart.dart — if that "
        "declaration was renamed, this guard must be re-pointed, not deleted"
    )
    labels = re.findall(r"'([^']+)'", match.group("body"))
    assert len(labels) == 6, f"vacuity guard — expected 6 chips, read {labels}"

    for label in labels:
        assert label.strip().lower() in VALID_PERIODS, (
            f"chip {label!r} has no server period; this is exactly DEF151 — "
            f"the client offers a token the API answers 422 to, and the user "
            f"sees a retry button that can never succeed"
        )


@pytest.mark.skipif(
    not _TICKER_CHART.exists(),
    reason=f"Flutter source not in this checkout ({_TICKER_CHART})",
)
def test_the_chips_are_still_declared_in_the_case_that_caused_this():
    """Vacuity guard on the test above. The chip labels are UI copy and are
    *meant* to stay uppercase — the fix normalises the wire token, it does not
    lowercase the user-visible chips. If this ever goes red because the labels
    were lowercased, the contract test above stopped proving anything.
    """
    labels = re.findall(
        r"'([^']+)'", _PERIODS_DECL.search(_TICKER_CHART.read_text()).group("body")
    )
    assert any(label != label.lower() for label in labels), (
        "every chip is already lowercase, so the contract test above would "
        "pass even with no normalisation anywhere"
    )


# ── the endpoint itself, in the exact shape the client sends ────────────────


@pytest.mark.parametrize("period", ["1D", "1W", "1M", "3M", "1Y", "5Y"])
def test_the_uppercase_tokens_the_shipped_builds_send_now_return_candles(
    client: TestClient, period: str
) -> None:
    """The six labels `ticker_chart.dart` puts on the wire today, verbatim.
    Every one of these was a 422 on live Alpha; every one must now serve."""
    r = client.get(f"/v1/sim/history/AAPL?period={period}")
    assert r.status_code == 200, r.text
    assert r.json()["candles"], "200 with no candles is the outage wearing a hat"


def test_the_response_echoes_the_canonical_token_it_actually_served() -> None:
    """Not the caller's spelling. The client keys its 60s cache and its chip
    selection off this field, and CR046's shown-equals-enforced rule applies to
    a period the same as to a number: report what was served."""
    app = FastAPI()
    app.include_router(sim_router)
    with TestClient(app, raise_server_exceptions=False) as c:
        assert c.get("/v1/sim/history/AAPL?period=1M").json()["period"] == "1m"
        assert c.get("/v1/sim/history/AAPL?period=+%201m+").json()["period"] == "1m"


def test_a_genuinely_unknown_period_is_still_refused(client: TestClient) -> None:
    """Normalising case must not become normalising meaning. `bogus` and an
    empty token are still 422 — the fix widens spelling, not the allow-list."""
    for bad in ("bogus", "", "1month", "1 m"):
        r = client.get(f"/v1/sim/history/AAPL?period={bad}")
        assert r.status_code == 422, f"{bad!r} -> {r.status_code}"
