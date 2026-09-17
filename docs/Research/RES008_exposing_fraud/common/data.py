"""
Price data loading for RES008 backtests.

Wraps yfinance with two guarantees the rest of `common/` depends on:

1. Bars are split-and-dividend adjusted on a total-return basis: raw
   open/high/low/close are scaled by `adj_close / close` for that row, so a
   strategy that never touches ex-dividend dates still sees the correct
   compounding. Using yfinance's `Adj Close` alone (and leaving O/H/L/close
   raw) would make gap/range-based signals (like `run_brackets`) see stale
   pre-adjustment prices.
2. Downloads are cached to CSV under `common/cache/` (git-ignored) with a
   sidecar `.meta` file recording the download date, so repeated runs across
   a research session do not re-hit the network and do not silently mix
   stale and fresh data without a record of when each ticker was pulled.

No look-ahead is enforced by `backtest.py`, not here — this module only
guarantees the bars themselves are internally consistent and adjusted.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

CACHE_DIR = Path(__file__).resolve().parent / "cache"

_OHLCV_COLS = ["open", "high", "low", "close", "volume"]

_INTRADAY_LIMITS_DAYS = {
    "60m": 730,
    "5m": 60,
}


def _cache_paths(ticker: str, tag: str) -> tuple[Path, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = CACHE_DIR / f"{ticker}_{tag}.csv"
    meta_path = csv_path.with_suffix(".meta")
    return csv_path, meta_path


def _flatten_columns(df: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        level0 = {c.lower() for c in df.columns.get_level_values(0)}
        if "open" in level0 or "close" in level0:
            df = df.xs(ticker, axis=1, level=1) if ticker in df.columns.get_level_values(1) else df.droplevel(1, axis=1)
        else:
            df = df.xs(ticker, axis=1, level=0) if ticker in df.columns.get_level_values(0) else df.droplevel(0, axis=1)
    df.columns = [str(c).lower().replace(" ", "_") for c in df.columns]
    return df


def _clean_bars(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        raise ValueError(f"yfinance returned no data for {ticker!r}")

    df = _flatten_columns(raw.copy(), ticker)

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{ticker!r}: missing columns {sorted(missing)} in yfinance response")

    df.index = pd.to_datetime(df.index)
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    df.index.name = "date"

    if "adj_close" in df.columns:
        adj_close = df["adj_close"]
    else:
        adj_close = df["close"]

    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = adj_close / df["close"]
    ratio = ratio.replace([np.inf, -np.inf], np.nan)

    for col in ("open", "high", "low", "close"):
        df[col] = df[col] * ratio

    df = df[_OHLCV_COLS]
    df = df.dropna(subset=["open", "high", "low", "close"])
    df = df[(df[["open", "high", "low", "close"]] > 0).all(axis=1)]
    df = df.sort_index()
    df = df[~df.index.duplicated(keep="last")]

    if df.empty:
        raise ValueError(f"{ticker!r}: no valid rows left after cleaning/adjustment")

    return df


def _read_cache(csv_path: Path) -> pd.DataFrame | None:
    if not csv_path.exists():
        return None
    df = pd.read_csv(csv_path, index_col="date", parse_dates=["date"])
    return df[_OHLCV_COLS]


def _write_cache(df: pd.DataFrame, csv_path: Path, meta_path: Path) -> None:
    df.to_csv(csv_path)
    meta_path.write_text(f"downloaded={_dt.date.today().isoformat()}\n")


def _cache_covers(cached: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp | None) -> bool:
    if cached.empty:
        return False
    if cached.index.min() > start:
        return False
    if end is not None and cached.index.max() < end - pd.Timedelta(days=1):
        return False
    return True


def load_daily(tickers: list[str], start: str, end: str | None = None) -> dict[str, pd.DataFrame]:
    """Load daily adjusted OHLCV bars for each ticker, one yfinance request per ticker."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end) if end is not None else None

    result: dict[str, pd.DataFrame] = {}
    for ticker in tickers:
        csv_path, meta_path = _cache_paths(ticker, "1d")
        cached = _read_cache(csv_path)

        if cached is not None and _cache_covers(cached, start_ts, end_ts):
            df = cached
        else:
            raw = yf.download(
                ticker,
                start=start_ts,
                end=end_ts,
                interval="1d",
                auto_adjust=False,
                progress=False,
            )
            df = _clean_bars(raw, ticker)
            _write_cache(df, csv_path, meta_path)

        mask = df.index >= start_ts
        if end_ts is not None:
            mask &= df.index <= end_ts
        result[ticker] = df.loc[mask].copy()

        if result[ticker].empty:
            raise ValueError(f"{ticker!r}: no data in requested range {start}..{end}")

    return result


def load_intraday(ticker: str, interval: str) -> pd.DataFrame:
    """Load intraday adjusted OHLCV bars for a single ticker ('60m' or '5m')."""
    if interval not in _INTRADAY_LIMITS_DAYS:
        raise ValueError(f"unsupported interval {interval!r}; use one of {sorted(_INTRADAY_LIMITS_DAYS)}")

    csv_path, meta_path = _cache_paths(ticker, interval)
    cached = _read_cache(csv_path)

    max_days = _INTRADAY_LIMITS_DAYS[interval]
    period = f"{max_days}d"

    if cached is not None and not cached.empty:
        df = cached
    else:
        raw = yf.download(
            ticker,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
        )
        df = _clean_bars(raw, ticker)
        _write_cache(df, csv_path, meta_path)

    return df.copy()
