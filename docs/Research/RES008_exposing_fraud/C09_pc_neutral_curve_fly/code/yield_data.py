"""
U.S. Treasury daily par yield curve loader for C09.

Andreev's own primary data source (his slide 8 cites the same Treasury.gov
series). Used ONLY to estimate PCA loadings -- these yields are not
tradeable instruments, so no P&L or cost model is ever applied to them
directly (see PREREGISTRATION.md, "Disclosed deviations" #2-3). The
execution/P&L layer is `U-RATES` ETFs, loaded via `common/data.py`.

Downloads one CSV per calendar year from Treasury.gov's published endpoint
and caches locally (git-ignored, matching common/data.py's convention).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "cache"

TENORS = ["2 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]

_URL_TEMPLATE = (
    "https://home.treasury.gov/resource-center/data-chart-center/interest-rates/"
    "daily-treasury-rates.csv/{year}/all"
    "?type=daily_treasury_yield_curve&field_tdr_date_value={year}&page&_format=csv"
)


def _load_year(year: int) -> pd.DataFrame:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = CACHE_DIR / f"treasury_yield_curve_{year}.csv"

    if csv_path.exists():
        df = pd.read_csv(csv_path, index_col="date", parse_dates=["date"])
    else:
        raw = pd.read_csv(_URL_TEMPLATE.format(year=year))
        raw["date"] = pd.to_datetime(raw["Date"], format="%m/%d/%Y")
        df = raw.set_index("date")[TENORS].sort_index()
        df.to_csv(csv_path)

    return df


def load_yield_curve(start: str, end: str) -> pd.DataFrame:
    """Daily par yields (percent) for TENORS, columns renamed to '2y'..'30y'."""
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)

    frames = [_load_year(y) for y in range(start_ts.year, end_ts.year + 1)]
    df = pd.concat(frames).sort_index()
    df = df[~df.index.duplicated(keep="last")]
    df = df.loc[(df.index >= start_ts) & (df.index <= end_ts)]

    rename = {t: t.lower().replace(" ", "") for t in TENORS}
    df = df.rename(columns=rename)

    if df.isna().any().any():
        df = df.dropna()

    return df
