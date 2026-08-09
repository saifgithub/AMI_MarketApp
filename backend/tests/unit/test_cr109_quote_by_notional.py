"""Sizing a game quote by dollars — CR109, found on a real device.

The 3-tap ticket sizes by percentage of book (Amendment D), which is a
notional amount. The client cannot turn that into a share count without a
price it does not have, so it sent `notional` — and both trade endpoints
required `quantity`. Every attempt to price a trade returned 422 and the app
said "Couldn't price that trade". Caught by tapping the ticket on a phone,
not by either suite: each side was tested against its own idea of the shape.

The asymmetry below is deliberate and is the interesting part:

  * `/trade/quote` ACCEPTS notional. A quote is a preview and already calls
    `current_quote`, so resolving dollars to shares there costs nothing.

  * `/trade` does NOT accept notional. Outside market hours it QUEUES, and
    `submit_trade` never touches `current_price` on that path — pricing a
    queued order at queue time is exactly the stale-price hindsight exploit
    the market-hours rule exists to prevent. Converting dollars would force a
    price fetch and the fence would be gone.

So the client quotes by dollars, then places the share count the quote
returned. That round-trip is not overhead; it is what keeps the fence intact.
"""

from __future__ import annotations

import pytest

from app.api.games import GameQuoteRequest, GameTradeRequest


def test_quote_accepts_notional_only() -> None:
    req = GameQuoteRequest(ticker="AMD", notional=2500.0)
    assert req.notional == 2500.0
    assert req.quantity is None


def test_quote_accepts_quantity_only() -> None:
    req = GameQuoteRequest(ticker="AMD", quantity=5.0)
    assert req.quantity == 5.0
    assert req.notional is None


def test_quote_refuses_both_sizes() -> None:
    """Both is ambiguous: the two would disagree the moment the price moved,
    and silently honouring one would size a real order by the wrong number."""
    with pytest.raises(ValueError):
        GameQuoteRequest(ticker="AMD", quantity=5.0, notional=2500.0)


def test_quote_refuses_neither_size() -> None:
    with pytest.raises(ValueError):
        GameQuoteRequest(ticker="AMD")


def test_trade_still_requires_shares_and_rejects_notional() -> None:
    """The fence. If this ever starts accepting `notional`, a queued order
    has to be priced at queue time to convert it — which is the exploit."""
    with pytest.raises(ValueError):
        GameTradeRequest(ticker="AMD")  # quantity is required

    req = GameTradeRequest(ticker="AMD", quantity=5.1721)
    assert req.quantity == 5.1721
    assert not hasattr(req, "notional") or getattr(req, "notional", None) is None


def test_a_zero_share_order_is_refused() -> None:
    """The guard that would have caught the cash bug on the first tap.

    When the client's cash silently read 0.0, every percentage sized to zero
    and this endpoint accepted it: five orders sat queued for 0.0000 shares,
    each reported to the player as placed. Nothing would ever have filled.
    A 422 at the boundary turns that silent no-op into an immediate, visible
    failure.
    """
    for bad in (0.0, -1.0):
        with pytest.raises(ValueError):
            GameTradeRequest(ticker="AMD", quantity=bad)


def test_a_zero_size_quote_is_refused() -> None:
    for bad in (0.0, -5.0):
        with pytest.raises(ValueError):
            GameQuoteRequest(ticker="AMD", quantity=bad)
        with pytest.raises(ValueError):
            GameQuoteRequest(ticker="AMD", notional=bad)
