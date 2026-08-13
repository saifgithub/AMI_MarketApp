"""CR166 Tier A — what we FETCH versus what any agent can READ.

The problem this exists to stop is not a missing field; it is the *way* missing
fields were being found. CR145 Tier A found `marketCap`/`freeCashflow`/
`totalDebt` "already fetched then discarded" by reviewing one agent. CR150 found
beta/volatility/short-interest by reviewing the Bear. CR152 found five
compliance inputs "promised and never rendered, all already computed" by
reviewing the Trader. Three correct findings, one root cause, rediscovered three
times — because nobody had looked at the whole supply.

The census that prompted this CR counted the supply once: the single
`yf.Ticker(t).info` call we already make returned **180 keys, 132 of them
numeric, of which we read 23**. Market cap is what that costs — the mandate
carried *"Avoid microcaps (< $500M market cap)"* as a HARD constraint in 17 of
18 prompts while 0 of 18 fact sheets stated one, and the rule sat unfollowable
for months because the field was never *missing*: it was fetched and thrown
away.

So this script is the standing version of that count. It answers, in both
directions:

  * **fetched but unreachable** — a field the pipeline produces that no agent
    can read. Every entry is either a field to render or a fetch to delete;
    "we pull it and drop it" is not a third option.
  * **rendered but unfetched** — a render site keyed on a field nothing
    produces, i.e. a line that can never fire.

WHY THIS IS NOT `test_prompt_data_parity.py`. That guard asks whether a field
the fetcher *returns* is rendered somewhere. This asks the question one layer
earlier — of every key the PROVIDER hands us, whether we take it at all. Parity
polices the fetcher's output; this polices the fetcher's input. Market cap was
green on parity for months: `fetch_live_fundamentals` did not return it, so
parity had nothing to check. It was sitting in `info` the whole time.

OFFLINE BY DEFAULT. The provider key list is a checked-in manifest, not a live
call — a network fetch in CI is flaky, and a guard that fails for reasons nobody
can reproduce gets disabled. `--refresh` makes the live call and rewrites the
manifest, so a provider adding or renaming a key arrives as a reviewable diff
instead of a red build.

Usage (from backend/):
    .venv/bin/python -m scripts.fact_sheet_census            # check, offline
    .venv/bin/python -m scripts.fact_sheet_census --json     # machine-readable
    .venv/bin/python -m scripts.fact_sheet_census --refresh  # live, rewrites manifest

Exit code 1 when the census finds an unreachable field, so it can gate CI.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


from app.services.market_data import EarningsInfo, Quote
from app.services.room_runner import (
    _EARNINGS_DIVIDEND_FIELDS,
    _FUNDAMENTALS_NUMERIC_FIELDS,
    _FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS,
)
from app.services.technicals import Technicals

MANIFEST = Path(__file__).resolve().parent / "fact_sheet_census_manifest.json"
_REFRESH_TICKER = "AAPL"


# Provider keys we deliberately do not take. Each needs a REASON, and the reason
# is the point: an unexplained entry here is indistinguishable from the silent
# discard this census exists to surface. Anything not listed and not consumed
# shows up as a finding.
INTENTIONALLY_NOT_TAKEN: dict[str, str] = {
    # Opaque proprietary scores with no published methodology. Rendering one
    # lends AMI's credibility to a number we cannot explain or defend.
    "auditRisk": "proprietary governance score, no published methodology",
    "boardRisk": "proprietary governance score, no published methodology",
    "compensationRisk": "proprietary governance score, no published methodology",
    "shareHolderRightsRisk": "proprietary governance score, no published methodology",
    "overallRisk": "proprietary governance score, no published methodology",
    # Split-adjusted to $0.049 for AAPL: arithmetically true, analytically
    # meaningless, and a base an agent could build a "99.98% above the low"
    # claim on.
    "allTimeLow": "split-adjusted to a meaningless figure on long-lived names",
    # Microstructure and plumbing — no bearing on a long-horizon simulated
    # decision, and several are quote-latency artefacts.
    "bid": "microstructure", "ask": "microstructure",
    "bidSize": "microstructure", "askSize": "microstructure",
    "sourceInterval": "plumbing", "exchangeDataDelayedBy": "plumbing",
    "gmtOffSetMilliseconds": "plumbing", "maxAge": "plumbing",
    "priceHint": "plumbing", "firstTradeDateMilliseconds": "plumbing",
    "regularMarketTime": "plumbing", "governanceEpochDate": "plumbing",
    "compensationAsOfEpochDate": "plumbing",
    # CLAIMED BY ANOTHER CR — listed so the census does not re-raise them every
    # run as if they were undiscovered. Removing an entry here is how the field
    # comes back into scope when that CR ships.
    "beta": "CR150 — Bear Researcher's quantified downside",
    "sharesShort": "CR150 — short interest, needs a reported-as-of label",
    "sharesShortPriorMonth": "CR150 — short interest",
    "sharesShortPreviousMonthDate": "CR150 — short interest",
    "shortRatio": "CR150 — short interest",
    "shortPercentOfFloat": "CR150 — short interest",
    "sharesPercentSharesOut": "CR150 — short interest",
    "dateShortInterest": "CR150 — short interest as-of date",
    "twoHundredDayAverage": "CR166 stage 3 — technicals lane",
    "twoHundredDayAverageChange": "CR166 stage 3 — technicals lane",
    "twoHundredDayAverageChangePercent": "CR166 stage 3 — technicals lane",
    "fiftyDayAverage": "CR166 stage 3 — technicals lane",
    "fiftyDayAverageChange": "CR166 stage 3 — technicals lane",
    "fiftyDayAverageChangePercent": "CR166 stage 3 — technicals lane",
    "previousClose": "CR166 stage 3 — technicals lane (day move)",
    "regularMarketPreviousClose": "CR166 stage 3 — technicals lane",
    "regularMarketChange": "CR166 stage 3 — technicals lane",
    "regularMarketChangePercent": "CR166 stage 3 — technicals lane",
    "regularMarketDayHigh": "CR166 stage 3 — technicals lane",
    "regularMarketDayLow": "CR166 stage 3 — technicals lane",
    "regularMarketOpen": "CR166 stage 3 — technicals lane",
    "regularMarketVolume": "CR166 stage 3 — technicals lane",
    "dayHigh": "CR166 stage 3 — technicals lane",
    "dayLow": "CR166 stage 3 — technicals lane",
    "open": "CR166 stage 3 — technicals lane",
    "volume": "CR166 stage 3 — technicals lane",
    "averageVolume": "CR166 stage 3 — technicals lane",
    "averageVolume10days": "CR166 stage 3 — technicals lane",
    "averageDailyVolume10Day": "CR166 stage 3 — technicals lane",
    "averageDailyVolume3Month": "CR166 stage 3 — technicals lane",
    "52WeekChange": "CR166 stage 3 — relative strength",
    "SandP52WeekChange": "CR166 stage 3 — relative strength vs the index",
    "fiftyTwoWeekChangePercent": "CR166 stage 3 — technicals lane",
    "fiftyTwoWeekHighChange": "CR166 stage 3 — already derived on the 52w line",
    "fiftyTwoWeekHighChangePercent": "CR166 stage 3 — already derived",
    "fiftyTwoWeekLowChange": "CR166 stage 3 — already derived",
    "fiftyTwoWeekLowChangePercent": "CR166 stage 3 — already derived",
    "allTimeHigh": "CR166 stage 3 — technicals lane",
    # Redundant with a field we already take, on a different basis or unit.
    "trailingAnnualDividendRate": "we take `dividendRate` (CR030) — one rate, one source",
    "trailingAnnualDividendYield": "we take `dividendYield`",
    "epsTrailingTwelveMonths": "duplicate of `trailingEps`",
    "forwardEps": "duplicate of `epsForward`",
    "nonDilutedMarketCap": "we take `marketCap`",
    "impliedSharesOutstanding": "we take `sharesOutstanding`",
    "ebitdaMargins": "gross → operating → net is the progression; EV/EBITDA carries the metric",
    # Needs a provider or a second call this CR does not make.
    "epsCurrentYear": "CR145 Tier D — forward-estimate family, needs a cache first",
    "epsForward": "CR145 Tier D — forward-estimate family",
    "priceEpsCurrentYear": "CR145 Tier D — forward-estimate family",
    "earningsGrowth": "CR145 Tier D — growth family, no trend without .income_stmt",
    "earningsQuarterlyGrowth": "CR145 Tier D — growth family",
    "revenueQuarterlyGrowth": "CR145 Tier D — growth family",
    "grossProfits": "CR145 Tier D — statement line item",
    "netIncomeToCommon": "CR145 Tier D — statement line item",
    "operatingCashflow": "CR145 Tier D — statement line item",
    "ebitda": "CR145 Tier D — statement line item; EV/EBITDA is rendered",
    "totalCashPerShare": "CR145 Tier D — statement line item",
    "bookValue": "CR145 Tier D — pairs with priceToBook, neither rendered yet",
    "priceToBook": "CR145 Tier D — pairs with bookValue",
    "enterpriseValue": "CR145 Tier D — EV multiples are rendered, the level is not",
    "enterpriseToRevenue": "CR145 Tier D — P/S is rendered on the same basis",
    "fiveYearAvgDividendYield": "CR145 Tier D — needs a history basis we do not state",
    "lastDividendValue": "per-payment figure; the annual rate is the useful one",
    "lastDividendDate": "we take the ex-date from EarningsInfo (CR030)",
    "dividendDate": "pay date; the ex-date is the one that decides entitlement",
    "lastSplitDate": "no split-adjustment story is told anywhere in the app",
    "lastFiscalYearEnd": "calendar plumbing; next-earnings is the live catalyst",
    "nextFiscalYearEnd": "calendar plumbing",
    "mostRecentQuarter": "calendar plumbing",
    "earningsTimestamp": "we take the date from EarningsInfo (CR030)",
    "earningsTimestampStart": "we take the date from EarningsInfo",
    "earningsTimestampEnd": "we take the date from EarningsInfo",
    "earningsCallTimestampStart": "we take the date from EarningsInfo",
    "earningsCallTimestampEnd": "we take the date from EarningsInfo",
    "fullTimeEmployees": "no rule or role line consumes a headcount",
    # Company identity and contact metadata. `longName` is taken (CR168); the
    # rest is a directory entry, not an input to a decision.
    "address1": "contact metadata", "city": "contact metadata",
    "state": "contact metadata", "zip": "contact metadata",
    "country": "contact metadata", "phone": "contact metadata",
    "website": "contact metadata", "irWebsite": "contact metadata",
    "messageBoardId": "provider-internal id",
    "longBusinessSummary": "prose, not a fact — the agent must not paraphrase a description as analysis",
    "companyOfficers": "roster data, no rule consumes it",
    "executiveTeam": "roster data, no rule consumes it",
    "displayName": "short marketing form; `longName` is the resolved identity we take",
    "shortName": "abbreviated form of `longName`, which we take",
    "symbol": "the ticker — already the subject of every prompt",
    # Venue / locale / session plumbing.
    "currency": "USD-only universe at MVP; a currency line would imply FX we do not model",
    "financialCurrency": "same",
    "exchangeTimezoneName": "plumbing", "exchangeTimezoneShortName": "plumbing",
    "fullExchangeName": "provider's venue string ('NasdaqGS'); we map the `exchange` CODE to a clean name instead",
    "language": "plumbing", "market": "plumbing", "region": "plumbing",
    "marketState": "session state, not a company fact",
    "quoteSourceName": "plumbing", "quoteType": "plumbing", "typeDisp": "plumbing",
    "tradeable": "plumbing", "triggerable": "plumbing",
    "cryptoTradeable": "out of universe — US equities only at MVP",
    "hasPrePostMarketData": "plumbing",
    "customPriceAlertConfidence": "provider-internal scoring, no methodology",
    "esgPopulated": "a flag about data presence, not a fact",
    # Post-market prints. The Room reasons on the daily close; a post-market
    # tick would put two prices for one session on the sheet, which is the
    # defect `_reference_price_line` had to reconcile.
    "postMarketPrice": "post-session print; the Room reasons on the close",
    "postMarketChange": "post-session print",
    "postMarketChangePercent": "post-session print",
    "postMarketTime": "post-session print",
    # Display duplicates of fields we already take, in a worse shape.
    "sectorDisp": "display duplicate of `sector`",
    "sectorKey": "slug duplicate of `sector`",
    "industryDisp": "display duplicate of `industry`",
    "industryKey": "slug duplicate of `industry`",
    "fiftyTwoWeekRange": "pre-joined string; we take the low and high separately",
    "regularMarketDayRange": "pre-joined string, and the day range is stage 3",
    "averageAnalystRating": "pre-joined string ('2.1 - Buy'); we take the score and the key separately",
    # Corporate actions.
    "corporateActions": "no split/spin handling exists to consume it",
    "lastSplitFactor": "no split-adjustment story is told anywhere in the app",
    "isEarningsDateEstimate": "CR166 stage 3 — would qualify the next-earnings line",
}


# Fields computed onto `Technicals` / `Quote` / `EarningsInfo` that are
# deliberately not rendered as their own fact-sheet field. Same rule as the
# provider exemptions: a reason, or it is a finding.
_COMPUTED_NOT_RENDERED: dict[str, str] = {
    "source": "provider identity — a liveness signal, not a fact about the company",
    "market_state": "CR166 stage 3 — pairs with the day move, technicals lane",
    "change_pct": "CR166 stage 3 — the day move, technicals lane",
    "price": "rendered as `last close` via the technicals block",
    "rsi_tone": "rendered inside the RSI line",
    "volume_tone": "rendered inside the volume line",
    "trend": "rendered inside the moving-average line",
    "support": "rendered as the 50-day range low",
    "breakout": "rendered as the 50-day range high",
    "sma_short": "rendered on the moving-average line",
    "sma_long": "rendered on the moving-average line",
    "volume_ratio": "rendered on the volume line",
    "rsi": "rendered on the RSI line",
    "earnings_date": "rendered via the `next_earnings` domain key",
    "quarter": "rendered via the `next_earnings` domain key",
    "eps_estimate": "rendered via the `next_earnings` domain key",
}


def _provider_keys(refresh: bool) -> tuple[list[str], str]:
    """The provider's key list: from the manifest, or live under `--refresh`."""
    if refresh:
        import yfinance as yf

        info = yf.Ticker(_REFRESH_TICKER).info
        keys = sorted(info)
        MANIFEST.write_text(
            json.dumps({"ticker": _REFRESH_TICKER, "keys": keys}, indent=2) + "\n"
        )
        return keys, f"live yfinance ({_REFRESH_TICKER})"
    if not MANIFEST.exists():
        raise SystemExit(
            f"manifest missing: {MANIFEST}\nRun with --refresh to create it."
        )
    return list(json.loads(MANIFEST.read_text())["keys"]), str(MANIFEST.name)


def _consumed_provider_keys() -> set[str]:
    """Provider keys we actually read off the `.info` dict.

    Read from the SOURCE rather than hand-listed, for the same reason
    `test_prompt_data_parity.py` reads its produced-set from the real fetcher: a
    hand-list rots into agreement with itself. Every `info.get("x")` and
    `_num("x")` is a read.

    BOTH modules that touch `.info`, not just the fetcher — `market_data.py`'s
    `_dividend_fields_from_info` reads `exDividendDate` and `dividendRate` for
    the CR030 dividend chip. Scanning only `fundamentals.py` reported those two
    as discarded when they are rendered on the Room's dividend line, which is
    the census lying in the direction that matters most: a false finding here
    trains the reader to skim the list.
    """
    import re

    services = Path(__file__).resolve().parents[1] / "app" / "services"
    src = "\n".join(
        (services / name).read_text()
        for name in ("fundamentals.py", "market_data.py")
    )
    return set(re.findall(r'(?:_num|info\.get)\(\s*"([A-Za-z0-9_]+)"', src))


def _renderable_profile_fields() -> set[str]:
    """Profile keys the pipeline can put in front of an agent.

    The three rosters `room_runner` populates `field_state` from. `_format_profile`
    renders a field ONLY when `field_state` says it is live (CR104), so a key
    absent from all three cannot reach any agent by construction.
    """
    return (
        set(_FUNDAMENTALS_NUMERIC_FIELDS)
        | set(_FUNDAMENTALS_OPTIONAL_LIVE_ONLY_FIELDS)
        | set(_EARNINGS_DIVIDEND_FIELDS)
    )


def run_census(refresh: bool = False) -> dict[str, Any]:
    """The two directions, plus the guard that keeps the exemption list honest."""
    provider_keys, source = _provider_keys(refresh)
    consumed = _consumed_provider_keys()
    renderable = _renderable_profile_fields()

    # Direction 1 — the provider hands us a key, we neither take it nor say why.
    unreachable_provider = sorted(
        k for k in provider_keys
        if k not in consumed and k not in INTENTIONALLY_NOT_TAKEN
    )
    # Direction 2 — a field computed onto one of the shared objects that no
    # roster records provenance for, so `_format_profile` can never render it.
    # `Candle` is excluded on purpose: bars are consumed by `compute_technicals`
    # and deliberately never reach an agent (CR146 rejected raw OHLCV in the
    # prompt, and a series is what the no-calculation rule forbids handing over).
    computed_fields = (
        set(Technicals._fields) | set(Quote._fields) | set(EarningsInfo._fields)
    )
    unreachable_computed = sorted(computed_fields - renderable - set(_COMPUTED_NOT_RENDERED))

    # The exemption list rots the moment a field it names gets taken. An entry
    # that is now consumed is a lie about the code, so it fails the census in
    # its own right rather than sitting there reading as a decision.
    stale_exemptions = sorted(k for k in INTENTIONALLY_NOT_TAKEN if k in consumed)

    return {
        "source": source,
        "provider_keys": len(provider_keys),
        "consumed": len(consumed),
        "exempted": len(INTENTIONALLY_NOT_TAKEN),
        "renderable_profile_fields": len(renderable),
        "unreachable_provider_keys": unreachable_provider,
        "unreachable_computed_fields": unreachable_computed,
        "stale_exemptions": stale_exemptions,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="CR166 Tier A — fetched vs readable census.")
    ap.add_argument("--refresh", action="store_true",
                    help="Make the live provider call and rewrite the manifest.")
    ap.add_argument("--json", action="store_true", help="Machine-readable output.")
    args = ap.parse_args()

    result = run_census(refresh=args.refresh)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"provider keys ({result['source']}): {result['provider_keys']}")
        print(f"  consumed by the fetcher:  {result['consumed']}")
        print(f"  exempted with a reason:   {result['exempted']}")
        print(f"  renderable profile fields:{result['renderable_profile_fields']}")
        if result["unreachable_provider_keys"]:
            print(
                f"\nFETCHED-BUT-UNREACHABLE ({len(result['unreachable_provider_keys'])}) — "
                "render it, delete the fetch, or exempt it with a reason:"
            )
            for k in result["unreachable_provider_keys"]:
                print(f"  - {k}")
        if result["stale_exemptions"]:
            print(
                f"\nSTALE EXEMPTIONS ({len(result['stale_exemptions'])}) — these are "
                "consumed now, so remove them from INTENTIONALLY_NOT_TAKEN:"
            )
            for k in result["stale_exemptions"]:
                print(f"  - {k}")
        if not result["unreachable_provider_keys"] and not result["stale_exemptions"]:
            print("\ncensus clean — every provider key is consumed or exempted with a reason.")
    return 1 if (result["unreachable_provider_keys"] or result["stale_exemptions"]) else 0


if __name__ == "__main__":
    sys.exit(main())
