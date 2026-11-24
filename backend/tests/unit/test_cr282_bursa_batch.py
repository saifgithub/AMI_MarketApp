"""CR282 Bursa batch tooling: universe build, stratified sampler, driver plan/resume, report.

Network is never touched: the screener is a fake callable, the driver is exercised
through its pure helpers and `--dry-run`, and the report runs over fixture records.
"""

from __future__ import annotations

import json
import sys
from collections import Counter

import httpx
import pytest

from scripts import bursa_batch, bursa_batch_report, bursa_sample, bursa_universe


# ---------------------------------------------------------------- universe


def _quote(sym, cap=1e8, price=1.0, vol=1000):
    return {"symbol": sym, "shortName": sym, "longName": sym + " Bhd", "marketCap": cap,
            "regularMarketPrice": price, "averageDailyVolume3Month": vol, "currency": "MYR"}


def test_build_universe_filters_codes_and_attaches_sector_industry():
    quotes = [_quote("1155.KL"), _quote("0166.KL"), _quote("1163PA.KL"), _quote("03068.KL")]

    def screen(sector, industry, offset):
        if sector is None and industry is None:
            return {"total": 4, "quotes": quotes if offset == 0 else []}
        if sector == "Financial Services":
            return {"total": 1, "quotes": [quotes[0]]}
        if industry == "Banks":
            return {"total": 1, "quotes": [quotes[0]]}
        return {"total": 0, "quotes": []}

    rows, stats = bursa_universe.build_universe(
        screen, ["Financial Services", "Technology"], ["Banks"], pulled_at="t", log=lambda _: None,
    )
    by = {r["symbol"]: r for r in rows}
    assert set(by) == {"1155.KL", "0166.KL", "03068.KL"}
    assert stats["rejected_by_is_bursa_code"] == ["1163PA.KL"]
    assert by["1155.KL"]["sector"] == "Financial Services" and by["1155.KL"]["industry"] == "Banks"
    assert by["0166.KL"]["sector"] == "" and stats["no_sector"] == 2
    assert all(r["board"] == "unknown" for r in rows)
    assert by["0166.KL"]["code_series"] == "0xxx" and by["1155.KL"]["code_series"] == "other"


def test_page_all_follows_offsets_until_total():
    pages = {0: [_quote("0001.KL"), _quote("0002.KL")], 2: [_quote("0003.KL")]}
    calls = []

    def screen(sector, industry, offset):
        calls.append(offset)
        return {"total": 3, "quotes": pages.get(offset, [])}

    assert [q["symbol"] for q in bursa_universe.page_all(screen)] == ["0001.KL", "0002.KL", "0003.KL"]
    assert calls == [0, 2]


def test_yahoo_screen_retries_429_then_gives_up_loudly(tmp_path, monkeypatch):
    import yfinance

    class RateLimit(Exception):
        pass

    attempts = []

    def boom(*a, **k):
        attempts.append(1)
        raise RateLimit("Too Many Requests")

    monkeypatch.setattr(yfinance, "screen", boom)
    slept = []
    screen = bursa_universe.make_yahoo_screen(tmp_path, refresh=True, sleep=slept.append)
    with pytest.raises(RateLimit):
        screen(None, None, 0)
    assert len(attempts) == bursa_universe.MAX_ATTEMPTS
    assert max(slept) >= bursa_universe.BACKOFF_BASE_S * 2
    assert not list(tmp_path.glob("screen_*"))


def test_yahoo_screen_serves_from_disk_cache(tmp_path, monkeypatch):
    import yfinance

    monkeypatch.setattr(yfinance, "screen", lambda *a, **k: pytest.fail("network used"))
    path = bursa_universe._cache_path(tmp_path, None, None, 0)
    path.write_text(json.dumps({"total": 1, "quotes": [_quote("0001.KL")]}))
    screen = bursa_universe.make_yahoo_screen(tmp_path, refresh=False)
    assert screen(None, None, 0)["quotes"][0]["symbol"] == "0001.KL"


# ----------------------------------------------------------------- sampler


def _universe(n=600):
    sectors = ["Industrials"] * 5 + ["Technology"] * 3 + ["Real Estate"] * 2
    rows = []
    for i in range(n):
        rows.append({
            "symbol": f"{i + 1000:04d}.KL" if i % 3 else f"{i % 900:04d}.KL",
            "short_name": f"N{i}", "long_name": "", "sector": sectors[i % len(sectors)],
            "industry": "", "market_cap": str(1_000_000 * (i * 7919 % n + 1)),
            "avg_daily_volume_3m": "1000", "price": "1.0", "currency": "MYR",
            "board": "unknown", "code_series": "0xxx" if i % 3 == 0 else "other",
        })
    for i, r in enumerate(rows):
        r["symbol"] = f"{i + 1:04d}.KL"
    return rows


def test_sample_is_deterministic_for_a_seed_and_differs_across_seeds():
    rows = _universe()
    a, _ = bursa_sample.draw_sample(rows, 120, seed=7)
    b, _ = bursa_sample.draw_sample(rows, 120, seed=7)
    c, _ = bursa_sample.draw_sample(rows, 120, seed=8)
    assert [r["symbol"] for r in a] == [r["symbol"] for r in b]
    assert [r["symbol"] for r in a] != [r["symbol"] for r in c]
    assert len({r["symbol"] for r in a}) == len(a) == 120


def test_sample_sector_quotas_are_proportional():
    rows = _universe()
    picked, meta = bursa_sample.draw_sample(rows, 100, seed=1)
    share = Counter(r["sector"] for r in picked)
    # 50% / 30% / 20% of the universe
    assert share["Industrials"] == 50 and share["Technology"] == 30 and share["Real Estate"] == 20
    assert meta["sampled"] == 100


def test_sample_splits_terciles_evenly_within_sector():
    rows = _universe()
    picked, _ = bursa_sample.draw_sample(rows, 99, seed=3)
    by_sector: dict[str, Counter] = {}
    for r in picked:
        by_sector.setdefault(r["sector"], Counter())[r["tercile"]] += 1
    for sector, c in by_sector.items():
        assert max(c.values()) - min(c.values()) <= 1, (sector, c)
    assert set(Counter(r["tercile"] for r in picked)) == set(bursa_sample.TERCILES)


def test_sample_keeps_code_series_mix_close_to_the_universe():
    rows = _universe()
    picked, _ = bursa_sample.draw_sample(rows, 120, seed=5)
    share = sum(1 for r in picked if r["code_series"] == "0xxx") / len(picked)
    assert abs(share - 1 / 3) < 0.08


def test_sample_drops_unusable_rows_and_counts_each_reason():
    rows = _universe(60)
    rows[0]["price"] = ""
    rows[1]["price"] = "0"
    rows[2]["avg_daily_volume_3m"] = "0"
    rows[3]["avg_daily_volume_3m"] = ""
    rows[4]["market_cap"] = ""
    picked, meta = bursa_sample.draw_sample(rows, 30, seed=1)
    assert meta["dropped"] == {"no_price": 2, "zero_or_missing_volume": 2, "no_market_cap": 1}
    assert meta["dropped_total"] == 5 and meta["eligible"] == 55
    dropped = {rows[i]["symbol"] for i in range(5)}
    assert not dropped & {r["symbol"] for r in picked}


def test_sample_caps_at_eligible_count_and_never_duplicates():
    rows = _universe(20)
    picked, meta = bursa_sample.draw_sample(rows, 200, seed=1)
    assert len(picked) == 20 == len({r["symbol"] for r in picked}) == meta["sampled"]


def test_sample_with_no_eligible_rows_fails_loudly():
    rows = _universe(5)
    for r in rows:
        r["price"] = ""
    with pytest.raises(ValueError):
        bursa_sample.draw_sample(rows, 10, seed=1)


def test_largest_remainder_respects_caps():
    q = bursa_sample.largest_remainder({"a": 90, "b": 10}, 20, {"a": 5, "b": 100})
    assert q == {"a": 5, "b": 15}


# ------------------------------------------------------------------ driver


def test_mandate_is_risk_5_with_liquid_only_and_filters_off():
    m = bursa_batch.BURSA_MANDATE_OVERRIDE
    assert m["risk_score"] == 5
    c = m["compliance"]
    assert c["liquid_only"] is False and c["halal"] is False and c["esg_lite"] is False
    assert c["no_tobacco_alcohol_gambling"] is False and c["no_fossil_fuels"] is False
    assert c["ticker_blocklist"] == [] and c["ticker_allowlist"] is None
    from app.schemas.mandate import Compliance
    assert Compliance(**c).liquid_only is False


def test_pending_skips_completed_and_permanent_but_retries_transient():
    latest = {
        "A.KL": {"status": "completed"}, "B.KL": {"status": "permanent_failure"},
        "C.KL": {"status": "failed_after_retries"}, "D.KL": {"status": "script_error"},
    }
    todo, skipped = bursa_batch.pending_tickers(["A.KL", "B.KL", "C.KL", "D.KL", "E.KL", "E.KL"], latest, False)
    assert todo == ["C.KL", "D.KL", "E.KL"]
    assert skipped == {"completed": 1, "permanent_failure": 1}
    todo, _ = bursa_batch.pending_tickers(["B.KL"], latest, True)
    assert todo == ["B.KL"]


def _status_error(code):
    req = httpx.Request("POST", "http://x/v1/room/stream")
    return httpx.HTTPStatusError("e", request=req, response=httpx.Response(code, request=req, text="body"))


@pytest.mark.parametrize("code,kind", [(422, "permanent"), (404, "permanent"), (401, "permanent"),
                                       (429, "transient"), (503, "transient"), (409, "transient")])
def test_classify_error_http(code, kind):
    assert bursa_batch.classify_error(_status_error(code))[0] == kind


def test_classify_error_transport_is_transient():
    assert bursa_batch.classify_error(httpx.ConnectError("down"))[0] == "transient"


class _Args:
    batch_id = "b"
    base_url = "http://h"
    max_attempts = 3
    retry_backoff = 1.0
    credit_grant = 2000
    poll_interval = 0.0
    run_timeout = 1.0
    no_snapshot = True


def test_run_ticker_retries_transient_then_succeeds(monkeypatch):
    seq = iter([httpx.ConnectError("blip"), ("run1", False, False)])

    def fake_convene(*a, **k):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(bursa_batch, "convene", fake_convene)
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {"status": "completed", "verdict": {"action": "PASS"}})
    slept = []
    rec = bursa_batch.run_ticker(None, _Args, {"user_id": "u", "token": "t"}, "1155.KL", {"risk_score": 5}, sleep=slept.append)
    assert rec["status"] == "completed" and len(rec["attempts"]) == 2
    assert rec["attempts"][0]["kind"] == "transient" and slept == [1.0]


def test_run_ticker_permanent_failure_is_recorded_not_retried(monkeypatch):
    calls = []

    def fake_convene(*a, **k):
        calls.append(1)
        raise _status_error(422)

    monkeypatch.setattr(bursa_batch, "convene", fake_convene)
    rec = bursa_batch.run_ticker(None, _Args, {"user_id": "u", "token": "t"}, "9999.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "permanent_failure" and len(calls) == 1
    assert "422" in rec["error_message"]


def test_run_ticker_exhausts_retries_loudly(monkeypatch):
    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: (_ for _ in ()).throw(httpx.ReadTimeout("slow")))
    rec = bursa_batch.run_ticker(None, _Args, {"user_id": "u", "token": "t"}, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "failed_after_retries" and len(rec["attempts"]) == 3
    assert "ReadTimeout" in rec["error_message"]


def test_run_ticker_grants_credits_on_402_and_retries(monkeypatch):
    seq = iter([_status_error(402), ("r", False, False)])

    def fake_convene(*a, **k):
        v = next(seq)
        if isinstance(v, Exception):
            raise v
        return v

    grants = []
    monkeypatch.setattr(bursa_batch, "convene", fake_convene)
    monkeypatch.setattr(bursa_batch.rb, "grant_credits", lambda c, b, u, d, note: grants.append((u, d, note)) or 1990)
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {"status": "completed", "verdict": {"action": "PASS"}})
    rec = bursa_batch.run_ticker(None, _Args, {"user_id": "u", "token": "t"}, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "completed" and grants == [("u", 2000, bursa_batch.CREDIT_NOTE)]
    assert rec["attempts"][0]["credit_grant"]["balance"] == 1990


def test_failed_room_is_retried_not_banked_as_pass(monkeypatch):
    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: ("r", False, False))
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {"status": "failed", "error_message": "llm down"})
    rec = bursa_batch.run_ticker(None, _Args, {"user_id": "u", "token": "t"}, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "failed_after_retries" and rec.get("verdict") is None


def test_dry_run_prints_plan_and_touches_nothing(tmp_path, monkeypatch, capsys):
    sample = tmp_path / "s.csv"
    sample.write_text("symbol,short_name\n1155.KL,MAYBANK\n0166.KL,INARI\n")
    out = tmp_path / "out"
    monkeypatch.setattr(httpx.Client, "__init__", lambda *a, **k: pytest.fail("network client created"))
    monkeypatch.setattr(sys, "argv", ["bursa_batch", str(sample), "--batch-id", "t1", "--out-dir", str(out), "--dry-run"])
    assert bursa_batch.main() == 0
    text = capsys.readouterr().out
    assert "PLAN" in text and "2 to run" in text and '"risk_score": 5' in text and "liquid_only" in text
    assert not out.exists()


# ------------------------------------------------------------------ report


def _coded(outcome, answers, reasons=(), close=()):
    return {
        "outcome": outcome, "reasons": list(reasons), "close_questions": list(close),
        "answers": [{"question": q, "answer": a, "close": q in close} for q, a in answers.items()],
    }


ALL_YES = {"bear_objection_answered": "yes", "catalyst_in_horizon": "yes", "terminal_vulnerability": "no",
           "event_risk_wait": "no", "thesis_material_directional": "yes", "trade_proposed": "yes"}


def _rec(ticker, action, coded=None, status="completed", **extra):
    verdict = None if action is None else {
        "action": action, "reason": "because " + ticker + " | pipe", "entry": 1.5, "stop": 1.2,
        "target": 2.0, "size_pct": 2.0, "time_horizon_days": 30, "coded_decision": coded,
    }
    return {"ticker": ticker, "status": status, "verdict": verdict, **extra}


def _fixture():
    sample = {
        "1.KL": {"symbol": "1.KL", "short_name": "A", "sector": "Tech", "tercile": "large", "code_series": "other"},
        "2.KL": {"symbol": "2.KL", "short_name": "B", "sector": "Tech", "tercile": "small", "code_series": "0xxx"},
        "3.KL": {"symbol": "3.KL", "short_name": "C", "sector": "Real Estate", "tercile": "small", "code_series": "0xxx"},
        "4.KL": {"symbol": "4.KL", "short_name": "D", "sector": "Real Estate", "tercile": "mid", "code_series": "other"},
        "5.KL": {"symbol": "5.KL", "short_name": "E", "sector": "Real Estate", "tercile": "mid", "code_series": "other"},
        "6.KL": {"symbol": "6.KL", "short_name": "F", "sector": "Tech", "tercile": "mid", "code_series": "other"},
        "7.KL": {"symbol": "7.KL", "short_name": "G", "sector": "Tech", "tercile": "mid", "code_series": "other"},
    }
    pass_terminal = _coded("PASS", {**ALL_YES, "terminal_vulnerability": "yes"},
                           ["whether an unresolved terminal vulnerability remains: yes"])
    pass_trade = _coded("PASS", {**ALL_YES, "trade_proposed": "no"},
                        ["whether the desk proposed a trade: no", "whether an unresolved terminal vulnerability remains: yes"])
    latest = {
        "1.KL": _rec("1.KL", "APPROVE", _coded("APPROVE", ALL_YES, ["every deciding question cleared this mandate's bar"])),
        "2.KL": _rec("2.KL", "PASS", pass_terminal),
        "3.KL": _rec("3.KL", "PASS", pass_terminal),
        "4.KL": _rec("4.KL", "PASS", pass_trade),
        "5.KL": _rec("5.KL", "PASS", _coded("CONTESTED", ALL_YES, ["x was too close to call"], close=["event_risk_wait"])),
        "6.KL": _rec("6.KL", None),
        "7.KL": _rec("7.KL", None, status="permanent_failure", error_message="HTTP 422: no such ticker"),
    }
    return sample, latest


def test_report_rows_classify_actions_and_deciding_question():
    sample, latest = _fixture()
    rows = {r["symbol"]: r for r in bursa_batch_report.build_rows(sample, latest, bursa_batch_report._labels())}
    assert rows["1.KL"]["action"] == "APPROVE" and rows["1.KL"]["deciding"] == ""
    assert rows["2.KL"]["action"] == "PASS" and rows["2.KL"]["deciding"] == "terminal_vulnerability"
    assert rows["4.KL"]["deciding"] == "trade_proposed"
    assert rows["5.KL"]["rule_outcome"] == "CONTESTED" and rows["5.KL"]["deciding"] == "event_risk_wait"
    assert rows["6.KL"]["action"] == "NO_VERDICT"
    assert rows["7.KL"]["action"] == "FAILED"


def test_report_aggregates_rates_blockers_and_lists_approvals():
    sample, latest = _fixture()
    labels = bursa_batch_report._labels()
    rows = bursa_batch_report.build_rows(sample, latest, labels)
    md = bursa_batch_report.render(rows, "t1", "s.csv", labels)
    assert "| APPROVE | 1 |" in md and "| PASS | 4 |" in md and "| NO_VERDICT | 1 |" in md and "| FAILED | 1 |" in md
    assert "Decided (APPROVE+MODIFY+PASS+REJECT): **5** · APPROVE: **1** (20.0%)" in md
    assert "| large | 1 | 1 | 100.0% |" in md and "| small | 2 | 0 | 0.0% |" in md
    assert "| Tech | 2 | 1 | 50.0% |" in md and "| Real Estate | 3 | 0 | 0.0% |" in md
    assert "Most frequent blocker: **terminal_vulnerability** (3 of 4" in md
    assert "### 1.KL A" in md and "entry 1.5 · stop 1.2 · target 2.0" in md and "because 1.KL \\| pipe" in md
    assert "FAILED (not PASS): 7.KL" in md
    assert "HTTP 422: no such ticker" in md


def test_report_says_so_when_nothing_was_approved():
    sample, latest = _fixture()
    latest["1.KL"] = _rec("1.KL", "PASS", _coded("PASS", {**ALL_YES, "terminal_vulnerability": "yes"},
                                                  ["whether an unresolved terminal vulnerability remains: yes"]))
    labels = bursa_batch_report._labels()
    md = bursa_batch_report.render(bursa_batch_report.build_rows(sample, latest, labels), "t1", "s.csv", labels)
    assert "**None.** No sampled ticker was approved." in md


def test_report_warns_on_missing_coded_record_unavailable_and_not_run():
    sample, latest = _fixture()
    latest["2.KL"] = _rec("2.KL", "PASS", None)
    latest["3.KL"] = _rec("3.KL", "PASS", _coded("UNAVAILABLE", {}, ["the grader failed: down"]))
    del latest["4.KL"]
    labels = bursa_batch_report._labels()
    md = bursa_batch_report.render(bursa_batch_report.build_rows(sample, latest, labels), "t1", "s.csv", labels)
    assert "carry NO coded_decision record" in md and "2.KL" in md.split("NO coded_decision record")[1].splitlines()[0]
    assert "rule outcome UNAVAILABLE" in md
    assert "never ran: 4.KL" in md


def test_report_cli_writes_markdown_and_fails_loudly_without_runs(tmp_path, monkeypatch):
    sample, latest = _fixture()
    (tmp_path / "s.csv").write_text(
        "symbol,short_name,sector,tercile,code_series\n"
        + "\n".join(f"{s['symbol']},{s['short_name']},{s['sector']},{s['tercile']},{s['code_series']}" for s in sample.values()) + "\n")
    monkeypatch.setattr(sys, "argv", ["r", str(tmp_path / "s.csv"), "--batch-id", "t1", "--out-dir", str(tmp_path)])
    assert bursa_batch_report.main() == 1
    (tmp_path / "runs_t1.jsonl").write_text("\n".join(json.dumps(r) for r in latest.values()) + "\n")
    assert bursa_batch_report.main() == 0
    assert (tmp_path / "report_t1.md").read_text().startswith("# Bursa batch report")
