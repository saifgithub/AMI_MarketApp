"""CR283 — company name -> ticker, per market.

The Floor search box has to tell "CIMB" the Malaysian bank from a US ticker
"CIMB", and no name->code table is stored anywhere (the SC Shariah list names
only its compliant stocks). Yahoo's search endpoint resolves short and company
names; this module asks it, then keeps only the listings on the requested
market's exchanges (MY: `KLS`; US: the US venues). It is already Alpha's Bursa
price source, so the lookup shares the price feed's licence status (CR282).

Degrade loudly (CR040): an upstream failure raises `TickerResolveUnavailable`
and is never cached, so the caller can say "can't look up names right now"
rather than imply there is no such company. An empty candidate list therefore
always means Yahoo answered and nothing matched.

Network is isolated in `_fetch_search` so tests mock one function.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import httpx

from app.core.logging import logger
from app.trading_math.markets import Market, is_bursa_code

SEARCH_URL = "https://query2.finance.yahoo.com/v1/finance/search"

# Yahoo rejects non-browser clients on this host.
_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT_S = 6.0
_QUOTES_COUNT = 10

# Yahoo's `exchange` is a venue code (same vocabulary as fundamentals._EXCHANGE_NAMES).
_EXCHANGES: dict[Market, frozenset[str]] = {
    Market.MY: frozenset({"KLS"}),
    Market.US: frozenset({"NMS", "NGM", "NCM", "NAS", "NYQ", "NYS", "ASE", "AMX", "PCX", "BTS"}),
}
_QUOTE_TYPES = frozenset({"EQUITY", "ETF"})

# Names do not change by the hour; a long TTL keeps a typing user off Yahoo.
CACHE_TTL_SECONDS = 6 * 60 * 60.0
_CACHE_MAX = 512
_cache: dict[tuple[Market, str], tuple[float, list["TickerCandidate"]]] = {}


class TickerResolveUnavailable(RuntimeError):
    """The upstream name search failed; the caller must not read this as 'no match'."""


@dataclass(frozen=True)
class TickerCandidate:
    ticker: str
    market: Market
    short_name: str
    long_name: str


def _fetch_search(q: str, client: httpx.Client | None = None) -> dict:
    params = {"q": q, "quotesCount": _QUOTES_COUNT, "newsCount": 0}
    try:
        if client is not None:
            r = client.get(SEARCH_URL, params=params)
        else:
            with httpx.Client(timeout=_TIMEOUT_S, headers={"User-Agent": _USER_AGENT}) as c:
                r = c.get(SEARCH_URL, params=params)
        r.raise_for_status()
        body = r.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("ticker_resolve_upstream_error", error=str(exc)[:200])
        raise TickerResolveUnavailable(f"Yahoo search failed: {type(exc).__name__}") from exc
    if not isinstance(body, dict) or not isinstance(body.get("quotes"), list):
        logger.warning("ticker_resolve_bad_shape")
        raise TickerResolveUnavailable("Yahoo search returned an unexpected payload")
    return body


def _to_candidate(entry: object, market: Market) -> TickerCandidate | None:
    if not isinstance(entry, dict):
        return None
    if entry.get("exchange") not in _EXCHANGES[market]:
        return None
    if entry.get("quoteType") not in _QUOTE_TYPES:
        return None
    symbol = str(entry.get("symbol") or "").upper().strip()
    if not symbol:
        return None
    if market is Market.MY:
        if not is_bursa_code(symbol):
            return None
    else:
        symbol = symbol.replace("-", ".")
    short = str(entry.get("shortname") or entry.get("longname") or symbol).strip()
    long = str(entry.get("longname") or entry.get("shortname") or symbol).strip()
    return TickerCandidate(ticker=symbol, market=market, short_name=short, long_name=long)


def resolve(q: str, market: Market, *, client: httpx.Client | None = None) -> list[TickerCandidate]:
    key = (market, q.strip().lower())
    now = time.monotonic()
    hit = _cache.get(key)
    if hit is not None and hit[0] > now:
        return hit[1]
    body = _fetch_search(q.strip(), client)
    seen: set[str] = set()
    out: list[TickerCandidate] = []
    for entry in body["quotes"]:
        cand = _to_candidate(entry, market)
        if cand is not None and cand.ticker not in seen:
            seen.add(cand.ticker)
            out.append(cand)
    if len(_cache) >= _CACHE_MAX:
        _cache.clear()
    _cache[key] = (now + CACHE_TTL_SECONDS, out)
    return out


def clear_cache() -> None:
    _cache.clear()
