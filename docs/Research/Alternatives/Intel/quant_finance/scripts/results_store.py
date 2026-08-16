#!/usr/bin/env python3
"""
Durable results store for batch fundamentals runs -- SQLite, one file.

WHY THIS EXISTS, AND WHY IT MATTERS MORE THAN IT LOOKS:

yfinance has NO point-in-time history. It serves current and *restated*
figures. That means a batch run is a PERISHABLE SNAPSHOT: the exact numbers the
model saw today cannot be reconstructed tomorrow, next week, or ever. If we
persist only the markdown prose, the numeric inputs behind every verdict are
lost permanently and the run becomes unauditable.

So the store keeps three layers per analysis:
  1. the structured numeric inputs   (queryable -> correlate verdicts vs ratios)
  2. the full brief text             (exact bytes the model was shown)
  3. the full response + verdict     (what it concluded)

Plus `price` and `as_of_utc` on every row. That is deliberate: it makes forward
returns computable later by joining future prices onto the analysis date, which
is the only honest way to ask "did the BUY calls actually work?" -- a question
Phase 1's feature-based prediction work could not answer.

SQLite over CSV/parquet because: single file, no server, real joins across runs
and models, safe concurrent readers, and it survives partial writes. Export to
DataFrame at analysis time with `to_frame()`.

Schema:
  runs        one row per (batch invocation, model)
  fundamentals one row per (run, ticker) -- numeric snapshot + brief text
  analyses    one row per (run, ticker, model) -- verdict + full response
  conflicts   one row per cross-verification disagreement (data-quality track)

Usage:
    from results_store import ResultsStore
    st = ResultsStore()                       # data/results.db
    rid = st.start_run(model_key="qwen", ...)
    st.save_fundamentals(rid, ticker, sector, info, ob, agree, conflict, brief)
    st.save_analysis(rid, ticker, "qwen", ...)
    st.finish_run(rid, n_ok=98)

    # later
    df = st.to_frame("SELECT * FROM v_analysis")
"""
import json
import os
import sqlite3
import hashlib
import datetime as dt

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_DB = os.path.join(ROOT, "data", "results.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    run_id        TEXT PRIMARY KEY,
    started_utc   TEXT NOT NULL,
    finished_utc  TEXT,
    model_key     TEXT,
    model_name    TEXT,
    prompt_sha    TEXT,      -- system+user template hash: which prompt version
    sample_source TEXT,
    seed          INTEGER,
    concurrency   INTEGER,
    n_requested   INTEGER,
    n_ok          INTEGER,
    note          TEXT
);

CREATE TABLE IF NOT EXISTS fundamentals (
    run_id      TEXT, ticker TEXT, sector TEXT, industry TEXT,
    as_of_utc   TEXT,
    price       REAL,        -- price at analysis time: enables forward returns
    market_cap  REAL,
    trailing_pe REAL, forward_pe REAL, peg REAL,
    roe REAL, roa REAL,
    gross_margin REAL, operating_margin REAL, profit_margin REAL,
    debt_to_equity REAL, current_ratio REAL, quick_ratio REAL,
    free_cash_flow REAL, beta REAL, dividend_yield REAL,
    revenue_growth REAL, earnings_growth REAL,
    ann_period TEXT, ann_assets REAL, ann_liabilities REAL, ann_equity REAL,
    ann_debt REAL, ann_cash REAL,
    n_agree INTEGER, n_conflict INTEGER,
    brief_chars INTEGER,
    brief       TEXT,        -- exact bytes shown to the model
    info_json   TEXT,        -- full yfinance .info, for anything not columnised
    PRIMARY KEY (run_id, ticker)
);

CREATE TABLE IF NOT EXISTS analyses (
    run_id TEXT, ticker TEXT, model_key TEXT,
    as_of_utc TEXT,
    ok INTEGER, rating TEXT, conviction TEXT, timeframe TEXT,
    -- Two SEPARATE self-reported numbers, deliberately not blended:
    --   confidence      = P(rating is the right call) over the time frame
    --   data_confidence = trust in the underlying figures, independent of view
    -- Keeping them apart is what makes calibration testable: data_confidence
    -- can be checked against the objective `conflicts` count for the same
    -- ticker, so we can see whether the model's stated doubt actually responds
    -- to evidence. A single blended number would make that impossible.
    confidence INTEGER, data_confidence INTEGER, uncertainty TEXT,
    lens TEXT,   -- 'fundamental' | 'market' | 'quality'
    -- The quality lens's BUY/HOLD/SELL is NOT comparable to the other lenses:
    -- it answers "is the accounting clean?", and for S&P 500 large caps the
    -- answer is usually yes (69/99 BUY). Its DISCRIMINATING output is this
    -- grade, so it gets its own column.
    quality_grade TEXT,   -- HIGH | ADEQUATE | QUESTIONABLE | POOR
    -- Scenario distribution supplied by the model. The PROBABILITIES and
    -- PRICE TARGETS come from the LLM; ev_price / ev_return are computed in
    -- Python from those inputs. Never ask the model to do the arithmetic --
    -- it supplies judgement, we do the maths.
    bear_prob REAL, bear_target REAL,
    base_prob REAL, base_target REAL,
    bull_prob REAL, bull_target REAL,
    prob_sum  REAL,             -- sanity check: should be ~100
    ev_price  REAL,             -- sum(p_i * target_i)
    ev_return REAL,             -- ev_price / price_at_analysis - 1
    fair_value REAL,            -- the model's single-point fair value, if given
    completion_tokens INTEGER, elapsed_s REAL,
    err TEXT,
    response TEXT,
    PRIMARY KEY (run_id, ticker, model_key)
);

CREATE TABLE IF NOT EXISTS conflicts (
    run_id TEXT, ticker TEXT, label TEXT,
    yf_value REAL, other_value REAL, rel_gap REAL
);

CREATE INDEX IF NOT EXISTS ix_an_ticker ON analyses(ticker);
CREATE INDEX IF NOT EXISTS ix_an_rating ON analyses(rating);
CREATE INDEX IF NOT EXISTS ix_fu_sector ON fundamentals(sector);
CREATE INDEX IF NOT EXISTS ix_cf_ticker ON conflicts(ticker);

-- Flat join for analysis: one row per verdict with its numeric context.
CREATE VIEW IF NOT EXISTS v_analysis AS
SELECT a.run_id, a.as_of_utc, a.ticker, f.sector, f.industry,
       a.model_key, a.rating, a.conviction, a.timeframe,
       a.lens, a.quality_grade, a.confidence, a.data_confidence, a.uncertainty,
       a.bear_prob, a.bear_target, a.base_prob, a.base_target,
       a.bull_prob, a.bull_target, a.prob_sum,
       a.ev_price, a.ev_return, a.fair_value,
       f.price, f.market_cap, f.trailing_pe, f.forward_pe, f.peg,
       f.roe, f.profit_margin, f.debt_to_equity, f.current_ratio,
       f.free_cash_flow, f.beta, f.revenue_growth,
       f.ann_equity, f.ann_debt, f.ann_cash,
       f.n_conflict, a.completion_tokens, a.elapsed_s, a.ok
FROM analyses a JOIN fundamentals f
  ON a.run_id = f.run_id AND a.ticker = f.ticker;

-- Is stated data_confidence actually responsive to real data conflicts?
-- If the two columns don't move together, the model's self-reported doubt is
-- decorative and should not be trusted as a signal.
CREATE VIEW IF NOT EXISTS v_confidence_calibration AS
SELECT a.model_key,
       f.n_conflict,
       COUNT(*)                 AS n,
       ROUND(AVG(a.confidence), 1)      AS avg_confidence,
       ROUND(AVG(a.data_confidence), 1) AS avg_data_confidence
FROM analyses a JOIN fundamentals f
  ON a.run_id = f.run_id AND a.ticker = f.ticker
WHERE a.ok = 1
GROUP BY a.model_key, f.n_conflict;

-- Where the two models disagree on the same name in the same run.
CREATE VIEW IF NOT EXISTS v_model_disagreement AS
SELECT q.run_id, q.ticker, f.sector,
       q.rating AS qwen_rating, n.rating AS nemotron_rating,
       q.conviction AS qwen_conv, n.conviction AS nemotron_conv
FROM analyses q
JOIN analyses n ON q.ticker = n.ticker AND q.run_id = n.run_id
JOIN fundamentals f ON f.run_id = q.run_id AND f.ticker = q.ticker
WHERE q.model_key = 'qwen' AND n.model_key = 'nemotron'
  AND q.rating <> n.rating;
"""

# yfinance .info key -> our column. Kept explicit rather than dumping .info so
# the schema is stable even as yfinance adds/renames fields (info_json keeps
# the rest anyway).
INFO_MAP = {
    "price": "currentPrice", "market_cap": "marketCap",
    "trailing_pe": "trailingPE", "forward_pe": "forwardPE", "peg": "pegRatio",
    "roe": "returnOnEquity", "roa": "returnOnAssets",
    "gross_margin": "grossMargins", "operating_margin": "operatingMargins",
    "profit_margin": "profitMargins", "debt_to_equity": "debtToEquity",
    "current_ratio": "currentRatio", "quick_ratio": "quickRatio",
    "free_cash_flow": "freeCashflow", "beta": "beta",
    "dividend_yield": "dividendYield", "revenue_growth": "revenueGrowth",
    "earnings_growth": "earningsGrowth",
}


def _f(v):
    """Coerce to float or None -- SQLite will not take numpy/NaN cleanly."""
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def prompt_sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update((p or "").encode())
    return h.hexdigest()[:12]


class ResultsStore:
    # Columns added after the first schema shipped. CREATE TABLE IF NOT EXISTS
    # is a no-op on an existing DB, so new fields must be ALTERed in or an
    # older store silently keeps the old shape and inserts fail.
    MIGRATIONS = {
        "analyses": [
            ("confidence", "INTEGER"), ("data_confidence", "INTEGER"),
            ("uncertainty", "TEXT"),
            ("bear_prob", "REAL"), ("bear_target", "REAL"),
            ("base_prob", "REAL"), ("base_target", "REAL"),
            ("bull_prob", "REAL"), ("bull_target", "REAL"),
            ("prob_sum", "REAL"), ("ev_price", "REAL"),
            ("ev_return", "REAL"), ("fair_value", "REAL"),
            ("lens", "TEXT"), ("quality_grade", "TEXT"),
        ],
    }

    def __init__(self, path=DEFAULT_DB):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.path = path
        self.cx = sqlite3.connect(path, timeout=30,
                                  check_same_thread=False)
        self.cx.executescript(SCHEMA)
        self._migrate()
        self._rebuild_views()
        self.cx.commit()

    def _rebuild_views(self):
        """Views are pure derived definitions, so drop and recreate them every
        open. `CREATE VIEW IF NOT EXISTS` is a no-op against an existing view,
        which means a schema change silently leaves the OLD view in place --
        exactly how `v_analysis` ended up without the `lens` column after it was
        added to `analyses`."""
        for v in ("v_analysis", "v_confidence_calibration",
                  "v_model_disagreement", "v_lens_disagreement"):
            self.cx.execute(f"DROP VIEW IF EXISTS {v}")
        body = SCHEMA[SCHEMA.index("-- Flat join"):]
        self.cx.executescript(body)
        # Same name, two lenses: where the tape and the statements disagree.
        self.cx.execute("""
        CREATE VIEW IF NOT EXISTS v_lens_disagreement AS
        SELECT f.ticker, x.sector,
               f.rating AS fundamental_rating, m.rating AS market_rating,
               f.confidence AS fund_conf, m.confidence AS mkt_conf,
               f.ev_return AS fund_ev, m.ev_return AS mkt_ev
        FROM analyses f
        JOIN analyses m ON f.ticker = m.ticker AND f.model_key = m.model_key
        JOIN fundamentals x ON x.run_id = f.run_id AND x.ticker = f.ticker
        WHERE f.lens = 'fundamental' AND m.lens = 'market'
          AND f.ok = 1 AND m.ok = 1 AND f.rating <> m.rating""")
        self.cx.commit()

    def _migrate(self):
        for table, cols in self.MIGRATIONS.items():
            have = {r[1] for r in self.cx.execute(
                f"PRAGMA table_info({table})")}
            if not have:
                continue
            for name, typ in cols:
                if name not in have:
                    self.cx.execute(
                        f"ALTER TABLE {table} ADD COLUMN {name} {typ}")
        self.cx.commit()

    # -- runs ------------------------------------------------------------
    def start_run(self, model_key, model_name, prompt_hash, sample_source,
                  seed, concurrency, n_requested, note=""):
        rid = f"{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%S}-{model_key}"
        self.cx.execute(
            "INSERT OR REPLACE INTO runs (run_id,started_utc,model_key,"
            "model_name,prompt_sha,sample_source,seed,concurrency,"
            "n_requested,note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rid, utcnow(), model_key, model_name, prompt_hash, sample_source,
             seed, concurrency, n_requested, note))
        self.cx.commit()
        return rid

    def finish_run(self, run_id, n_ok):
        self.cx.execute("UPDATE runs SET finished_utc=?, n_ok=? WHERE run_id=?",
                        (utcnow(), n_ok, run_id))
        self.cx.commit()

    # -- data ------------------------------------------------------------
    def save_fundamentals(self, run_id, ticker, sector, industry, info, ob,
                          agree, conflict, brief):
        row = {k: _f(info.get(src)) for k, src in INFO_MAP.items()}
        # Annual balance-sheet figures, on a clearly different basis from the
        # TTM/MRQ summary above -- stored separately so analysis never mixes
        # them by accident (the exact bug that broke both models earlier).
        ann = {"ann_period": None, "ann_assets": None, "ann_liabilities": None,
               "ann_equity": None, "ann_debt": None, "ann_cash": None}
        bal = ob.get("balance") if ob else None
        if bal is not None and not bal.empty:
            r = (bal.sort_values("period_ending").iloc[-1]
                 if "period_ending" in bal.columns else bal.iloc[-1])
            ann["ann_period"] = str(r.get("period_ending", ""))[:10] or None
            ann["ann_assets"] = _f(r.get("total_assets"))
            ann["ann_liabilities"] = _f(
                r.get("total_liabilities_net_minority_interest"))
            ann["ann_equity"] = _f(r.get("common_stock_equity"))
            ann["ann_debt"] = _f(r.get("total_debt"))
            ann["ann_cash"] = _f(r.get("cash_and_cash_equivalents"))

        cols = (["run_id", "ticker", "sector", "industry", "as_of_utc"]
                + list(INFO_MAP) + list(ann)
                + ["n_agree", "n_conflict", "brief_chars", "brief",
                   "info_json"])
        vals = ([run_id, ticker, sector, industry, utcnow()]
                + [row[k] for k in INFO_MAP] + [ann[k] for k in ann]
                + [len(agree), len(conflict), len(brief), brief,
                   json.dumps({k: v for k, v in info.items()
                               if isinstance(v, (int, float, str, bool,
                                                 type(None)))})])
        self.cx.execute(
            f"INSERT OR REPLACE INTO fundamentals ({','.join(cols)}) "
            f"VALUES ({','.join('?' * len(cols))})", vals)

        self.cx.execute("DELETE FROM conflicts WHERE run_id=? AND ticker=?",
                        (run_id, ticker))
        for label, a, b in conflict:
            denom = max(abs(a or 0), abs(b or 0), 1e-9)
            self.cx.execute(
                "INSERT INTO conflicts (run_id,ticker,label,yf_value,"
                "other_value,rel_gap) VALUES (?,?,?,?,?,?)",
                (run_id, ticker, label, _f(a), _f(b),
                 _f(abs((a or 0) - (b or 0)) / denom)))
        self.cx.commit()

    def save_analysis(self, run_id, ticker, model_key, ok, rating, conviction,
                      timeframe, confidence, data_confidence, uncertainty,
                      completion_tokens, elapsed_s, err, response,
                      scenarios=None, lens="fundamental"):
        """`scenarios` is the dict from parse_verdict(): bear/base/bull
        probabilities and price targets, plus the EV we computed in Python."""
        s = scenarios or {}
        cols = ["run_id", "ticker", "model_key", "as_of_utc", "ok", "rating",
                "conviction", "timeframe", "confidence", "data_confidence",
                "uncertainty", "completion_tokens", "elapsed_s", "err",
                "response", "bear_prob", "bear_target", "base_prob",
                "base_target", "bull_prob", "bull_target", "prob_sum",
                "ev_price", "ev_return", "fair_value", "lens",
                "quality_grade"]
        vals = [run_id, ticker, model_key, utcnow(), int(bool(ok)), rating,
                conviction, timeframe, confidence, data_confidence,
                uncertainty, completion_tokens, elapsed_s, err, response,
                s.get("bear_prob"), s.get("bear_target"), s.get("base_prob"),
                s.get("base_target"), s.get("bull_prob"), s.get("bull_target"),
                s.get("prob_sum"), s.get("ev_price"), s.get("ev_return"),
                s.get("fair_value"), lens, s.get("quality_grade")]
        self.cx.execute(
            f"INSERT OR REPLACE INTO analyses ({','.join(cols)}) "
            f"VALUES ({','.join('?' * len(cols))})", vals)
        self.cx.commit()

    # -- derived ---------------------------------------------------------
    def recompute_ev(self, fn=None, dry_run=True):
        """Recompute ev_price / ev_return from the STORED raw components.

        The model never does this arithmetic -- it only supplies probabilities
        and price targets. Everything needed to derive EV is persisted, so the
        derived columns are disposable and can be regenerated at any time, or
        replaced with a different formula entirely (risk-adjusted, downside-
        weighted, probability-of-loss, whatever) without re-querying any model.

        `fn(bear_p, bear_t, base_p, base_t, bull_p, bull_t, price) -> ev_price`
        overrides the default probability-weighted mean.

        Returns a DataFrame of what changed. dry_run=True by default so a
        formula change can be inspected before it is written.
        """
        df = self.to_frame(
            "SELECT run_id, ticker, model_key, price, bear_prob, bear_target,"
            " base_prob, base_target, bull_prob, bull_target, prob_sum,"
            " ev_price, ev_return FROM v_analysis")
        need = ["bear_prob", "bear_target", "base_prob", "base_target",
                "bull_prob", "bull_target"]
        out = []
        for r in df.itertuples():
            vals = [getattr(r, c) for c in need]
            if any(v is None or pd.isna(v) for v in vals) or not r.price:
                continue
            bp, bt, sp, st_, up, ut = vals
            tot = bp + sp + up
            if not (95 <= tot <= 105):
                continue
            ev = (fn(bp, bt, sp, st_, up, ut, r.price) if fn
                  else (bp * bt + sp * st_ + up * ut) / tot)
            out.append({"run_id": r.run_id, "ticker": r.ticker,
                        "model_key": r.model_key,
                        "old_ev_price": r.ev_price, "new_ev_price": round(ev, 2),
                        "old_ev_return": r.ev_return,
                        "new_ev_return": round(ev / r.price - 1, 4)})
        res = pd.DataFrame(out)
        if not dry_run and not res.empty:
            for r in res.itertuples():
                self.cx.execute(
                    "UPDATE analyses SET ev_price=?, ev_return=? WHERE "
                    "run_id=? AND ticker=? AND model_key=?",
                    (r.new_ev_price, r.new_ev_return, r.run_id, r.ticker,
                     r.model_key))
            self.cx.commit()
        return res

    # -- read ------------------------------------------------------------
    def to_frame(self, sql="SELECT * FROM v_analysis", params=()):
        return pd.read_sql_query(sql, self.cx, params=params)

    def export(self, outdir):
        """Dump every table to CSV -- for sharing or non-SQL tooling."""
        os.makedirs(outdir, exist_ok=True)
        names = [r[0] for r in self.cx.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table','view')")]
        written = []
        for n in names:
            if n.startswith("sqlite_"):
                continue
            df = pd.read_sql_query(f"SELECT * FROM {n}", self.cx)
            # brief/response are huge; keep them in the DB, not the CSVs
            df = df.drop(columns=[c for c in ("brief", "response", "info_json")
                                  if c in df.columns], errors="ignore")
            p = os.path.join(outdir, f"{n}.csv")
            df.to_csv(p, index=False)
            written.append((n, len(df), p))
        return written


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="inspect the results store")
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--sql", default=None)
    ap.add_argument("--export", default=None, help="dump all tables to CSV dir")
    a = ap.parse_args()
    st = ResultsStore(a.db)
    if a.export:
        for n, k, p in st.export(a.export):
            print(f"{n:22s} {k:6d} rows -> {p}")
    elif a.sql:
        print(st.to_frame(a.sql).to_string())
    else:
        for t in ("runs", "fundamentals", "analyses", "conflicts"):
            n = st.cx.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            print(f"{t:14s} {n:7d} rows")
